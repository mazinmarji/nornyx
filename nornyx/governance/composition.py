from __future__ import annotations

from copy import deepcopy
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .approvals import compose_effective_approval, normalize_approval
from .errors import GovernanceError, error
from .locks import verify_lock
from .models import (
    CompositionResult,
    GovernanceBlockSchema,
    GovernanceModule,
    NormalizedApproval,
    ProfileLock,
    ProfilePack,
    Rule,
    immutable_mapping,
)
from .registry import GovernanceRegistry


Pack = ProfilePack | GovernanceModule

MAX_COMPOSED_RULES = 2000
MAX_COMPOSED_BLOCK_SCHEMAS = 64
MAX_COMPOSED_STRUCTURAL_CHECKS = 64


def _provenance_record(
    pack: Pack,
    *,
    element_kind: str,
    element_id: str,
) -> Mapping[str, Any]:
    return MappingProxyType(
        {
            "element_kind": element_kind,
            "element_id": element_id,
            "source_id": pack.id,
            "source_version": pack.version,
            "layer": "module" if isinstance(pack, GovernanceModule) else "profile",
            **pack.provenance.to_dict(),
        }
    )


def _ordered_union(*groups: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for group in groups:
        for value in group:
            if value not in result:
                result.append(value)
    return tuple(result)


def _strict_merge_strings(
    value: Any,
    *,
    field: str,
    source_id: str,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise error(
            "PACK_MONOTONICITY_CONFLICT",
            f"Composed field {field!r} must be a list of source strings.",
            source_id=source_id,
        )
    result: list[str] = []
    for item in value:
        if (
            not isinstance(item, str)
            or not item.strip()
            or item != item.strip()
        ):
            raise error(
                "PACK_MONOTONICITY_CONFLICT",
                f"Composed field {field!r} contains a non-canonical source value.",
                source_id=source_id,
            )
        if item not in result:
            result.append(item)
    return tuple(result)


def _item_id(item: Mapping[str, Any], kind: str, source_id: str) -> str:
    value = item.get("id") or item.get("name")
    if not isinstance(value, str) or not value:
        raise error(
            "PACK_ITEM_ID_MISSING",
            f"{kind} entries require an id or name.",
            source_id=source_id,
        )
    return value


def _merge_policy(existing: Mapping[str, Any], incoming: Mapping[str, Any], *, source_id: str) -> Mapping[str, Any]:
    result = deepcopy(dict(existing))
    for field, value in incoming.items():
        if field in ("deny", "require"):
            continue
        if field in result and result[field] != value:
            raise error(
                "PACK_MONOTONICITY_CONFLICT",
                f"Policy field {field!r} conflicts for {result.get('id')!r}.",
                source_id=source_id,
            )
        if field not in result:
            result[field] = deepcopy(value)
    for field in ("deny", "require"):
        result[field] = list(
            _ordered_union(
                _strict_merge_strings(
                    result.get(field, []),
                    field=field,
                    source_id=source_id,
                ),
                _strict_merge_strings(
                    incoming.get(field, []),
                    field=field,
                    source_id=source_id,
                ),
            )
        )
    return immutable_mapping(result)


def _merge_evidence(existing: Mapping[str, Any], incoming: Mapping[str, Any], *, source_id: str) -> Mapping[str, Any]:
    result = deepcopy(dict(existing))
    for field, value in incoming.items():
        if field == "required":
            if field in result and bool(result[field]) != bool(value):
                raise error(
                    "PACK_MONOTONICITY_EVIDENCE",
                    "Mandatory evidence cannot be made optional.",
                    source_id=source_id,
                )
            result[field] = bool(value)
            continue
        if field in result and result[field] != value:
            raise error(
                "PACK_MONOTONICITY_CONFLICT",
                f"Evidence field {field!r} conflicts for {result.get('id')!r}.",
                source_id=source_id,
            )
        result[field] = deepcopy(value)
    return immutable_mapping(result)


def _merge_evaluation(existing: Mapping[str, Any], incoming: Mapping[str, Any], *, source_id: str) -> Mapping[str, Any]:
    result = deepcopy(dict(existing))
    for field in ("metrics", "required_evidence"):
        result[field] = list(
            _ordered_union(
                _strict_merge_strings(
                    result.get(field, []),
                    field=field,
                    source_id=source_id,
                ),
                _strict_merge_strings(
                    incoming.get(field, []),
                    field=field,
                    source_id=source_id,
                ),
            )
        )
    for field, value in incoming.items():
        if field in {"metrics", "required_evidence"}:
            continue
        if field in result and result[field] != value:
            raise error(
                "PACK_MONOTONICITY_CONFLICT",
                f"Evaluation field {field!r} conflicts for {result.get('id')!r}.",
                source_id=source_id,
            )
        result[field] = deepcopy(value)
    return immutable_mapping(result)


def _normalize_pack_approval(item: Mapping[str, Any], *, source_id: str, index: int) -> NormalizedApproval:
    raw_identity = item.get("id")
    normalized = normalize_approval(
        item,
        shape="generated_profile_approval",
        path=f"{source_id}.approval_requirements[{index}]",
        fallback_id=(
            raw_identity
            if isinstance(raw_identity, str)
            and raw_identity.strip()
            and raw_identity == raw_identity.strip()
            else f"approval-{index}"
        ),
    )
    if normalized.resolution == "invalid":
        raise GovernanceError(*normalized.diagnostics)
    if not (
        normalized.required_roles
        or normalized.eligible_roles
        or normalized.required_evidence
        or normalized.actions_requiring_approval
    ):
        raise error(
            "APPROVAL_EMPTY_REQUIREMENT",
            "Governance approval requirements may not be empty.",
            source_id=source_id,
        )
    return normalized


def _approval_provenance(
    pack: Pack,
    *,
    index: int,
    approval_path: str,
) -> Mapping[str, Any]:
    return MappingProxyType(
        {
            "source_id": pack.id,
            "source_kind": "module" if isinstance(pack, GovernanceModule) else "profile",
            "source_version": pack.version,
            "source_tier": pack.provenance.source_tier,
            "source_path": pack.provenance.source_path,
            "approval_path": approval_path,
            "source_index": index,
            "content_hash": pack.content_hash,
        }
    )


def _effective_approval_facade(
    source_values: list[tuple[NormalizedApproval, Mapping[str, Any]]],
) -> NormalizedApproval:
    effective = compose_effective_approval(source_values)
    return NormalizedApproval(
        id=effective.id,
        required_roles=effective.required_roles,
        eligible_roles=effective.eligible_roles,
        denied_actor_types=effective.denied_actor_types,
        denied_execution_surfaces=effective.denied_execution_surfaces,
        required_evidence=effective.required_evidence,
        actions_requiring_approval=effective.actions_requiring_approval,
        timing=effective.timing,
        accountable_authority=effective.accountable_authority,
        revision_binding=effective.revision_binding,
        invalidation_conditions=effective.invalidation_conditions,
        expires_at=effective.expires_at,
        resolution="complete",
        diagnostics=(),
        source_shape="generated_profile_approval",
        source_path=f"composed.{effective.id}",
        source_raw={
            "effective_schema": "nornyx.effective_approval.v1",
            "source_count": len(effective.sources),
        },
        role_field="eligible_roles" if effective.eligible_roles else "none",
        exact_revision_required=effective.exact_revision_required,
        expires_after=effective.expires_after,
        effective_approval=effective,
    )


def compose_governance(
    registry: GovernanceRegistry,
    *,
    profile_identity: str | None,
    module_ids: Iterable[str] = (),
    lock: ProfileLock | None = None,
) -> CompositionResult:
    profile = registry.resolve_profile(profile_identity) if profile_identity else None
    modules = registry.dependency_order(profile, module_ids)
    conflicts = registry.selected_conflicts(profile, modules)
    if conflicts:
        rendered = ", ".join(f"{left} <-> {right}" for left, right in conflicts)
        raise error("PACK_DECLARED_CONFLICT", f"Selected governance inputs conflict: {rendered}.")
    selected = [*modules, *([profile] if profile else [])]
    if lock is None and any(
        pack.provenance.source_tier == "org" for pack in selected
    ):
        raise error(
            "PACK_LOCK_REQUIRED",
            "Organization-tier governance inputs require a committed profile lock.",
        )
    if lock is not None:
        verify_lock(lock, selected)

    required_blocks: tuple[str, ...] = ()
    block_schemas: dict[str, GovernanceBlockSchema] = {}
    structural_checks: tuple[str, ...] = ()
    non_goals: tuple[str, ...] = ()
    policies: dict[str, Mapping[str, Any]] = {}
    evidence: dict[str, Mapping[str, Any]] = {}
    approval_sources: dict[
        str,
        list[tuple[NormalizedApproval, Mapping[str, Any]]],
    ] = {}
    evaluations: dict[str, Mapping[str, Any]] = {}
    rules: dict[str, Rule] = {}
    provenance: list[Mapping[str, Any]] = []

    for pack in selected:
        # Duplicate ids within one pack are always author errors and are fatal;
        # merge-by-id semantics apply only across layers.
        pack_seen: set[tuple[str, str]] = set()

        def _claim(kind: str, item_id: str) -> None:
            key = (kind, item_id)
            if key in pack_seen:
                raise error(
                    "PACK_DUPLICATE_ID",
                    f"Pack {pack.id!r} declares {kind} id {item_id!r} more than once.",
                    source_id=pack.id,
                )
            pack_seen.add(key)

        provenance.append(
            _provenance_record(pack, element_kind="pack", element_id=pack.id)
        )
        required_blocks = _ordered_union(required_blocks, pack.required_blocks)
        non_goals = _ordered_union(non_goals, pack.non_goals)
        provenance.extend(
            _provenance_record(pack, element_kind="required_block", element_id=item)
            for item in pack.required_blocks
        )
        provenance.extend(
            _provenance_record(pack, element_kind="non_goal", element_id=item)
            for item in pack.non_goals
        )
        source_policies = pack.policies if isinstance(pack, GovernanceModule) else pack.default_policies
        source_evidence = (
            pack.evidence_requirements if isinstance(pack, GovernanceModule) else pack.required_evidence
        )
        source_approvals = pack.approval_requirements
        source_evaluations = pack.evaluations if isinstance(pack, GovernanceModule) else pack.default_evaluations
        source_rules = pack.rules if isinstance(pack, GovernanceModule) else pack.validation_rules

        if isinstance(pack, GovernanceModule):
            structural_checks = _ordered_union(structural_checks, pack.structural_checks)
            for binding in pack.block_schemas:
                existing = block_schemas.get(binding.block)
                if existing is not None and existing.schema_id != binding.schema_id:
                    raise error(
                        "PACK_BLOCK_SCHEMA_CONFLICT",
                        f"Block {binding.block!r} is claimed by both {existing.schema_id!r} "
                        f"and {binding.schema_id!r}.",
                        source_id=pack.id,
                    )
                block_schemas[binding.block] = binding
                provenance.append(
                    _provenance_record(
                        pack,
                        element_kind="block_schema",
                        element_id=f"{binding.block}:{binding.schema_id}",
                    )
                )
            provenance.extend(
                _provenance_record(
                    pack,
                    element_kind="structural_check",
                    element_id=check_id,
                )
                for check_id in pack.structural_checks
            )

        for item in source_policies:
            item_id = _item_id(item, "policy", pack.id)
            _claim("policy", item_id)
            provenance.append(
                _provenance_record(pack, element_kind="policy", element_id=item_id)
            )
            policies[item_id] = (
                _merge_policy(policies[item_id], item, source_id=pack.id)
                if item_id in policies
                else immutable_mapping(item)
            )
        for item in source_evidence:
            item_id = _item_id(item, "evidence", pack.id)
            _claim("evidence", item_id)
            provenance.append(
                _provenance_record(pack, element_kind="evidence", element_id=item_id)
            )
            evidence[item_id] = (
                _merge_evidence(evidence[item_id], item, source_id=pack.id)
                if item_id in evidence
                else immutable_mapping(item)
            )
        for index, item in enumerate(source_approvals):
            normalized = _normalize_pack_approval(item, source_id=pack.id, index=index)
            _claim("approval", normalized.id)
            provenance.append(
                _provenance_record(
                    pack,
                    element_kind="approval",
                    element_id=normalized.id,
                )
            )
            approval_sources.setdefault(normalized.id, []).append(
                (
                    normalized,
                    _approval_provenance(
                        pack,
                        index=index,
                        approval_path=normalized.source_path,
                    ),
                )
            )
        for item in source_evaluations:
            item_id = _item_id(item, "evaluation", pack.id)
            _claim("evaluation", item_id)
            provenance.append(
                _provenance_record(pack, element_kind="evaluation", element_id=item_id)
            )
            evaluations[item_id] = (
                _merge_evaluation(evaluations[item_id], item, source_id=pack.id)
                if item_id in evaluations
                else immutable_mapping(item)
            )
        for rule in source_rules:
            if rule.namespaced_id in rules:
                raise error("PACK_DUPLICATE_RULE", f"Duplicate rule {rule.namespaced_id!r}.")
            rules[rule.namespaced_id] = rule
            provenance.append(
                _provenance_record(
                    pack,
                    element_kind="rule",
                    element_id=rule.namespaced_id,
                )
            )
        if isinstance(pack, ProfilePack):
            provenance.extend(
                _provenance_record(
                    pack,
                    element_kind="starter_fragment",
                    element_id=f"{item.target}:{item.source_index}",
                )
                for item in pack.starter_fragments
            )

    if len(rules) > MAX_COMPOSED_RULES:
        raise error(
            "PACK_LIMIT_EXCEEDED",
            f"Composition produced {len(rules)} rules; the limit is {MAX_COMPOSED_RULES}.",
        )
    if len(block_schemas) > MAX_COMPOSED_BLOCK_SCHEMAS:
        raise error(
            "PACK_LIMIT_EXCEEDED",
            f"Composition produced {len(block_schemas)} block schemas; "
            f"the limit is {MAX_COMPOSED_BLOCK_SCHEMAS}.",
        )
    if len(structural_checks) > MAX_COMPOSED_STRUCTURAL_CHECKS:
        raise error(
            "PACK_LIMIT_EXCEEDED",
            f"Composition produced {len(structural_checks)} structural checks; "
            f"the limit is {MAX_COMPOSED_STRUCTURAL_CHECKS}.",
        )

    fragments = profile.starter_fragments if profile else ()
    return CompositionResult(
        profile=profile,
        modules=modules,
        required_blocks=required_blocks,
        block_schemas=tuple(block_schemas[key] for key in sorted(block_schemas)),
        structural_checks=tuple(sorted(structural_checks)),
        policies=tuple(policies[key] for key in sorted(policies)),
        evidence_requirements=tuple(evidence[key] for key in sorted(evidence)),
        approval_requirements=tuple(
            _effective_approval_facade(approval_sources[key])
            for key in sorted(approval_sources)
        ),
        evaluations=tuple(evaluations[key] for key in sorted(evaluations)),
        rules=tuple(rules[key] for key in sorted(rules)),
        non_goals=non_goals,
        starter_fragments=tuple(
            sorted(fragments, key=lambda item: (item.target, item.source_index))
        ),
        provenance=tuple(provenance),
        diagnostics=(),
    )
