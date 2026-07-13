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
# _matches reasons that are structural (malformed document), as opposed to the
# ordinary missing/non-match semantics. Structural reasons fail closed in
# `when` conditions instead of silently disabling the rule.
STRUCTURAL_MATCH_REASONS = {
    "RULE_SCALAR_TYPE_ERROR",
    "RULE_COLLECTION_TYPE_ERROR",
    "RULE_REFERENCE_TYPE_ERROR",
    "RULE_OPERATOR_UNKNOWN",
}
# Actor categories that can never satisfy references_role, even in forged
# pre-normalized approval payloads.
CORE_DENIED_APPROVER_ACTORS = ("ai_tool", "execution_surface")


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
    type_errors: tuple[GovernanceDiagnostic, ...] = ()


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
            # A pre-normalized approval is only trusted when its own
            # normalization succeeded, and never if it claims a core-denied
            # actor as a role — a forged payload must fail closed.
            if item.get("resolution") == "invalid":
                return None
            values = [*item.get("required_roles", []), *item.get("eligible_roles", [])]
            if any(str(value) in CORE_DENIED_APPROVER_ACTORS for value in values):
                return None
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
    type_errors: list[GovernanceDiagnostic] = []
    matched = False
    for item in resolution.values:
        passes, reason = _matches(item.value, operator, operand)
        if passes:
            matched = True
            if resolution.deepest_prefix:
                successes.setdefault(resolution.deepest_prefix, set()).add(item.binding)
        elif reason in STRUCTURAL_MATCH_REASONS:
            type_errors.append(
                GovernanceDiagnostic(
                    "error",
                    reason,
                    f"Structural type error evaluating {path!r}.",
                    path=item.path,
                    binding=item.binding,
                )
            )
    return PredicateOutcome(
        matched=matched,
        successes={key: frozenset(value) for key, value in successes.items()},
        resolution=resolution,
        type_errors=tuple(type_errors),
    )


def _binding_prefix(
    binding: tuple[tuple[str, int], ...], prefix: str
) -> tuple[tuple[str, int], ...] | None:
    for index, (name, _) in enumerate(binding):
        if name == prefix:
            return binding[: index + 1]
    return None


def _project_selections(
    outcomes: list[PredicateOutcome], mode: str
) -> tuple[bool, dict[str, frozenset[tuple[tuple[str, int], ...]]]]:
    """Project successful bindings onto every traversed collection level.

    Predicates that traverse a shared ancestor collection (e.g. changes[].risk
    and changes[].evidence[].kind both traverse changes[]) must, under `all`,
    be satisfied by the same ancestor element. Returns (joint_ok, selections):
    joint_ok is False when two or more predicates traverse a prefix but no
    single element satisfies them all.
    """
    outcome_bindings: list[set[tuple[tuple[str, int], ...]]] = []
    prefixes: set[str] = set()
    for outcome in outcomes:
        bindings: set[tuple[tuple[str, int], ...]] = set()
        for group in outcome.successes.values():
            bindings |= set(group)
        outcome_bindings.append(bindings)
        for binding in bindings:
            for name, _ in binding:
                prefixes.add(name)
    joint_ok = True
    selections: dict[str, frozenset[tuple[tuple[str, int], ...]]] = {}
    for prefix in sorted(prefixes):
        groups: list[set[tuple[tuple[str, int], ...]]] = []
        for bindings in outcome_bindings:
            projected = {
                projection
                for binding in bindings
                if (projection := _binding_prefix(binding, prefix)) is not None
            }
            if projected:
                groups.append(projected)
        if not groups:
            continue
        selected = set.intersection(*groups) if mode == "all" else set.union(*groups)
        if mode == "all" and len(groups) >= 2 and not selected:
            joint_ok = False
        selections[prefix] = frozenset(selected)
    return joint_ok, selections


def _condition_outcome(
    document: Mapping[str, Any],
    condition: Mapping[str, Any] | None,
) -> tuple[
    bool,
    dict[str, frozenset[tuple[tuple[str, int], ...]]],
    tuple[GovernanceDiagnostic, ...],
]:
    if condition is None:
        return True, {}, ()
    if "all" in condition or "any" in condition:
        mode = "all" if "all" in condition else "any"
        outcomes = [_predicate_outcome(document, item) for item in condition[mode]]
        structural = tuple(
            diagnostic
            for item in outcomes
            for diagnostic in (*item.resolution.structural_errors, *item.type_errors)
        )
        matched = all(item.matched for item in outcomes) if mode == "all" else any(item.matched for item in outcomes)
        joint_ok, selections = _project_selections(outcomes, mode)
        if mode == "all" and not joint_ok:
            # Per-element semantics: an element is selected only if every
            # predicate traversing the same collection matches that element.
            matched = False
        return matched, selections, structural
    outcome = _predicate_outcome(document, condition)
    _, selections = _project_selections([outcome], "any")
    return (
        outcome.matched,
        selections,
        (*outcome.resolution.structural_errors, *outcome.type_errors),
    )


def evaluate_rule(document: Mapping[str, Any], rule: Rule) -> tuple[GovernanceDiagnostic, ...]:
    matched, selections, when_errors = _condition_outcome(document, rule.when)
    if when_errors:
        # A malformed document must never silently disable a rule: structural
        # errors while evaluating `when` fail closed at the rule's severity.
        return tuple(
            GovernanceDiagnostic(
                rule.severity,
                item.code,
                rule.message,
                path=item.path,
                source_id=rule.namespaced_id,
                binding=item.binding,
            )
            for item in when_errors
        )
    if not matched:
        return ()
    return _evaluate_requirements(document, rule, selections)


def _evaluate_requirements(
    document: Mapping[str, Any],
    rule: Rule,
    selections: dict[str, frozenset[tuple[tuple[str, int], ...]]],
) -> tuple[GovernanceDiagnostic, ...]:
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
