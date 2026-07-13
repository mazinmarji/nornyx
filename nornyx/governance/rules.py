from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
import re
from typing import Any, Iterable, Mapping

from .approvals import normalize_approval
from .models import GovernanceDiagnostic, Rule


PATH_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\[\])?(?:\.[A-Za-z_][A-Za-z0-9_]*(?:\[\])?){0,7}$"
)
COLLECTION_OPERATORS = {"contains", "contains_all", "min_count", "max_count"}
SCALAR_OPERATORS = {"equals", "not_equals", "in", "not_in", "matches_id"}
REFERENCE_OPERATORS = {"references_role", "references_evidence", "references_approval"}
MAX_EVALUATION_STEPS = 100_000
MISSING = object()


@dataclass(frozen=True, slots=True)
class Segment:
    name: str
    collection: bool


@dataclass(frozen=True, slots=True)
class ResolvedValue:
    value: Any
    path: str
    binding: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class Resolution:
    values: tuple[ResolvedValue, ...]
    structural_errors: tuple[GovernanceDiagnostic, ...]
    had_collection: bool
    deepest_prefix: str | None


@dataclass(frozen=True, slots=True)
class PredicateOutcome:
    matched: bool
    successes: Mapping[str, frozenset[tuple[tuple[str, int], ...]]]
    resolution: Resolution


def parse_path(path: str) -> tuple[Segment, ...]:
    if not PATH_RE.fullmatch(path):
        raise ValueError(f"invalid governance path {path!r}")
    return tuple(
        Segment(part[:-2], True) if part.endswith("[]") else Segment(part, False)
        for part in path.split(".")
    )


def _resolve(document: Mapping[str, Any], path: str) -> Resolution:
    segments = parse_path(path)
    values: list[ResolvedValue] = []
    errors: list[GovernanceDiagnostic] = []
    collection_names: list[str] = []
    steps = 0

    def walk(
        current: Any,
        index: int,
        concrete: list[str],
        binding: tuple[tuple[str, int], ...],
        logical: list[str],
    ) -> None:
        nonlocal steps
        steps += 1
        if steps > MAX_EVALUATION_STEPS:
            errors.append(
                GovernanceDiagnostic(
                    "error",
                    "RULE_STEP_LIMIT_EXCEEDED",
                    f"Rule path evaluation exceeded {MAX_EVALUATION_STEPS} steps.",
                    path=path,
                )
            )
            return
        segment = segments[index]
        logical_path = ".".join([*logical, segment.name])
        if current is MISSING:
            child = MISSING
        elif not isinstance(current, Mapping):
            errors.append(
                GovernanceDiagnostic(
                    "error",
                    "RULE_PATH_TYPE_ERROR",
                    f"Cannot read field {segment.name!r} from a non-mapping value.",
                    path=".".join(concrete) or path,
                    binding=binding,
                )
            )
            return
        else:
            child = current.get(segment.name, MISSING)

        if segment.collection:
            if logical_path not in collection_names:
                collection_names.append(logical_path)
            if child is MISSING:
                return
            if not isinstance(child, list):
                errors.append(
                    GovernanceDiagnostic(
                        "error",
                        "RULE_COLLECTION_TYPE_ERROR",
                        f"Collection segment {logical_path!r} must resolve to a list.",
                        path=".".join([*concrete, segment.name]),
                        binding=binding,
                    )
                )
                return
            for child_index, item in enumerate(child):
                next_binding = (*binding, (logical_path, child_index))
                next_concrete = [*concrete, f"{segment.name}[{child_index}]"]
                if index == len(segments) - 1:
                    values.append(ResolvedValue(item, ".".join(next_concrete), next_binding))
                else:
                    walk(item, index + 1, next_concrete, next_binding, [*logical, segment.name])
            return

        next_concrete = [*concrete, segment.name]
        if index == len(segments) - 1:
            values.append(ResolvedValue(child, ".".join(next_concrete), binding))
        else:
            walk(child, index + 1, next_concrete, binding, [*logical, segment.name])

    walk(document, 0, [], (), [])
    unique: dict[str, ResolvedValue] = {}
    for item in values:
        unique.setdefault(item.path, item)
    return Resolution(
        values=tuple(unique.values()),
        structural_errors=tuple(errors),
        had_collection=bool(collection_names),
        deepest_prefix=collection_names[-1] if collection_names else None,
    )


def _operator(predicate: Mapping[str, Any]) -> tuple[str, Any]:
    operators = [(key, value) for key, value in predicate.items() if key != "path"]
    if len(operators) != 1:
        raise ValueError("predicate must contain exactly one operator")
    return operators[0]


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _approval_roles(value: Any) -> tuple[str, ...] | None:
    items = value if isinstance(value, list) else [value]
    roles: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            return None
        if item.get("schema") == "nornyx.normalized_approval.v1":
            values = [*item.get("required_roles", []), *item.get("eligible_roles", [])]
        else:
            governed = "id" in item and (
                "required_evidence" in item
                or any(
                    field in item
                    for field in (
                        "eligible_approver_roles",
                        "approver_roles",
                        "approvers",
                        "eligible_approvers",
                    )
                )
            )
            normalized = normalize_approval(
                item,
                shape="governed_package_gate" if governed else "ordinary_approval",
                path=f"approvals[{index}]",
                fallback_id=f"approval-{index}",
            )
            if normalized.resolution == "invalid":
                return None
            values = [*normalized.required_roles, *normalized.eligible_roles]
        for role in values:
            text = str(role)
            if text not in roles:
                roles.append(text)
    return tuple(roles)


def _reference_ids(value: Any) -> tuple[str, ...] | None:
    if isinstance(value, Mapping):
        if "required" in value and isinstance(value["required"], list):
            value = value["required"]
        else:
            value = [value]
    if not isinstance(value, list):
        return None
    result: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            candidate = item.get("id") or item.get("name")
        else:
            candidate = item
        if not isinstance(candidate, str):
            return None
        if candidate not in result:
            result.append(candidate)
    return tuple(result)


def _matches(value: Any, operator: str, operand: Any) -> tuple[bool, str | None]:
    if value is MISSING:
        if operator == "not_exists":
            return True, None
        return False, "RULE_PATH_MISSING"
    if operator == "exists":
        return True, None
    if operator == "not_exists":
        return False, "RULE_REQUIREMENT_FAILED"
    if operator in SCALAR_OPERATORS:
        if not _is_scalar(value):
            return False, "RULE_SCALAR_TYPE_ERROR"
        if operator == "equals":
            return value == operand, None
        if operator == "not_equals":
            return value != operand, None
        if operator == "in":
            return value in operand, None
        if operator == "not_in":
            return value not in operand, None
        if not isinstance(value, str):
            return False, "RULE_SCALAR_TYPE_ERROR"
        return fnmatchcase(value, str(operand)), None
    if operator in COLLECTION_OPERATORS:
        if not isinstance(value, list):
            return False, "RULE_COLLECTION_TYPE_ERROR"
        if operator == "contains":
            return operand in value, None
        if operator == "contains_all":
            return all(item in value for item in operand), None
        if operator == "min_count":
            return len(value) >= operand, None
        return len(value) <= operand, None
    if operator == "references_role":
        roles = _approval_roles(value)
        if roles is None:
            return False, "RULE_REFERENCE_TYPE_ERROR"
        return str(operand) in roles, None
    if operator in {"references_evidence", "references_approval"}:
        references = _reference_ids(value)
        if references is None:
            return False, "RULE_REFERENCE_TYPE_ERROR"
        return str(operand) in references, None
    return False, "RULE_OPERATOR_UNKNOWN"


def _predicate_outcome(document: Mapping[str, Any], predicate: Mapping[str, Any]) -> PredicateOutcome:
    path = str(predicate["path"])
    resolution = _resolve(document, path)
    operator, operand = _operator(predicate)
    successes: dict[str, set[tuple[tuple[str, int], ...]]] = {}
    matched = False
    for item in resolution.values:
        passes, _ = _matches(item.value, operator, operand)
        if passes:
            matched = True
            if resolution.deepest_prefix:
                successes.setdefault(resolution.deepest_prefix, set()).add(item.binding)
    return PredicateOutcome(
        matched=matched,
        successes={key: frozenset(value) for key, value in successes.items()},
        resolution=resolution,
    )


def _condition_outcome(
    document: Mapping[str, Any],
    condition: Mapping[str, Any] | None,
) -> tuple[bool, dict[str, frozenset[tuple[tuple[str, int], ...]]]]:
    if condition is None:
        return True, {}
    if "all" in condition or "any" in condition:
        mode = "all" if "all" in condition else "any"
        outcomes = [_predicate_outcome(document, item) for item in condition[mode]]
        matched = all(item.matched for item in outcomes) if mode == "all" else any(item.matched for item in outcomes)
        prefixes = {prefix for item in outcomes for prefix in item.successes}
        selections: dict[str, frozenset[tuple[tuple[str, int], ...]]] = {}
        for prefix in prefixes:
            groups = [set(item.successes[prefix]) for item in outcomes if prefix in item.successes]
            if not groups:
                continue
            selected = set.intersection(*groups) if mode == "all" else set.union(*groups)
            selections[prefix] = frozenset(selected)
        return matched, selections
    outcome = _predicate_outcome(document, condition)
    return outcome.matched, dict(outcome.successes)


def evaluate_rule(document: Mapping[str, Any], rule: Rule) -> tuple[GovernanceDiagnostic, ...]:
    matched, selections = _condition_outcome(document, rule.when)
    if not matched:
        return ()
    diagnostics: list[GovernanceDiagnostic] = []
    for predicate in rule.requirements:
        path = str(predicate["path"])
        resolution = _resolve(document, path)
        operator, operand = _operator(predicate)
        if resolution.structural_errors:
            for item in resolution.structural_errors:
                diagnostics.append(
                    GovernanceDiagnostic(
                        rule.severity,
                        item.code,
                        rule.message,
                        path=item.path,
                        source_id=rule.namespaced_id,
                        binding=item.binding,
                    )
                )
            continue
        values = list(resolution.values)
        # `when` selections scope requirements by binding prefix: a requirement
        # value is kept only if, for every selection prefix its binding
        # traverses, the sub-binding up to that prefix was selected. This also
        # scopes paths that descend deeper than the selected collection
        # (e.g. when changes[].risk selects, changes[].evidence[].kind binds
        # only under the selected changes). Unrelated prefixes are unaffected.
        for prefix, selected in selections.items():
            kept = []
            for item in values:
                position = next(
                    (
                        index
                        for index, (name, _) in enumerate(item.binding)
                        if name == prefix
                    ),
                    None,
                )
                if position is None or item.binding[: position + 1] in selected:
                    kept.append(item)
            values = kept
        if resolution.had_collection and not values:
            diagnostics.append(
                GovernanceDiagnostic(
                    rule.severity,
                    "RULE_EMPTY_COLLECTION",
                    rule.message,
                    path=path,
                    source_id=rule.namespaced_id,
                )
            )
            continue
        for item in values:
            passes, reason = _matches(item.value, operator, operand)
            if not passes:
                diagnostics.append(
                    GovernanceDiagnostic(
                        rule.severity,
                        reason or "RULE_REQUIREMENT_FAILED",
                        rule.message,
                        path=item.path,
                        source_id=rule.namespaced_id,
                        binding=item.binding,
                    )
                )
    return tuple(diagnostics)


def evaluate_rules(
    document: Mapping[str, Any],
    rules: Iterable[Rule],
) -> tuple[GovernanceDiagnostic, ...]:
    diagnostics = []
    for rule in sorted(rules, key=lambda item: item.namespaced_id):
        diagnostics.extend(evaluate_rule(document, rule))
    return tuple(diagnostics)
