from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .approvals import normalize_approval
from .errors import GovernanceError, error
from .locks import verify_lock
from .models import (
    CompositionResult,
    GovernanceModule,
    NormalizedApproval,
    ProfileLock,
    ProfilePack,
    Rule,
    immutable_mapping,
)
from .registry import GovernanceRegistry


Pack = ProfilePack | GovernanceModule

# Non-removable core denials: no pack may make an AI tool or an execution
# surface an eligible approver, and every composed approval carries these
# denials regardless of what the pack declared.
CORE_DENIED_ACTOR_TYPES = ("ai_tool", "execution_surface")
CORE_DENIED_EXECUTION_SURFACES = ("execution_surface",)


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
                (str(item) for item in result.get(field, [])),
                (str(item) for item in incoming.get(field, [])),
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
                (str(item) for item in result.get(field, [])),
                (str(item) for item in incoming.get(field, [])),
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
    normalized = normalize_approval(
        item,
        shape="generated_profile_approval",
        path=f"{source_id}.approval_requirements[{index}]",
        fallback_id=str(item.get("id", f"approval-{index}")),
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
    contradictory = set(normalized.eligible_roles) & (
        set(CORE_DENIED_ACTOR_TYPES) | set(CORE_DENIED_EXECUTION_SURFACES)
    )
    if contradictory:
        raise error(
            "PACK_MONOTONICITY_APPROVAL",
            f"Approval {normalized.id!r} makes core-denied actors eligible: "
            f"{sorted(contradictory)}.",
            source_id=source_id,
        )
    return replace(
        normalized,
        denied_actor_types=_ordered_union(
            normalized.denied_actor_types, CORE_DENIED_ACTOR_TYPES
        ),
        denied_execution_surfaces=_ordered_union(
            normalized.denied_execution_surfaces, CORE_DENIED_EXECUTION_SURFACES
        ),
    )


def _merge_approval(existing: NormalizedApproval, incoming: NormalizedApproval) -> NormalizedApproval:
    for field in ("timing", "accountable_authority", "expires_at"):
        left = getattr(existing, field)
        right = getattr(incoming, field)
        if left not in (None, "unspecified") and right not in (None, "unspecified") and left != right:
            raise error(
                "PACK_MONOTONICITY_APPROVAL",
                f"Approval {existing.id!r} has conflicting {field} values.",
            )
    if existing.revision_binding and incoming.revision_binding and dict(existing.revision_binding) != dict(incoming.revision_binding):
        raise error(
            "PACK_MONOTONICITY_APPROVAL",
            f"Approval {existing.id!r} has conflicting revision bindings.",
        )
    eligible_roles = _ordered_union(existing.eligible_roles, incoming.eligible_roles)
    denied_actor_types = _ordered_union(
        existing.denied_actor_types,
        incoming.denied_actor_types,
    )
    denied_execution_surfaces = _ordered_union(
        existing.denied_execution_surfaces,
        incoming.denied_execution_surfaces,
    )
    contradictory = set(eligible_roles) & (
        set(denied_actor_types) | set(denied_execution_surfaces)
    )
    if contradictory:
        raise error(
            "PACK_MONOTONICITY_APPROVAL",
            f"Approval {existing.id!r} makes denied actors eligible: {sorted(contradictory)}.",
        )
    source_raw = {
        "merged_sources": [existing.source_path, incoming.source_path],
    }
    return NormalizedApproval(
        id=existing.id,
        required_roles=_ordered_union(existing.required_roles, incoming.required_roles),
        eligible_roles=eligible_roles,
        denied_actor_types=denied_actor_types,
        denied_execution_surfaces=denied_execution_surfaces,
        required_evidence=_ordered_union(existing.required_evidence, incoming.required_evidence),
        actions_requiring_approval=_ordered_union(
            existing.actions_requiring_approval,
            incoming.actions_requiring_approval,
        ),
        timing=existing.timing if existing.timing != "unspecified" else incoming.timing,
        accountable_authority=existing.accountable_authority or incoming.accountable_authority,
        revision_binding=existing.revision_binding or incoming.revision_binding,
        invalidation_conditions=_ordered_union(
            existing.invalidation_conditions,
            incoming.invalidation_conditions,
        ),
        expires_at=existing.expires_at or incoming.expires_at,
        resolution="complete",
        diagnostics=existing.diagnostics + incoming.diagnostics,
        source_shape="generated_profile_approval",
        source_path=f"composed.{existing.id}",
        source_raw=source_raw,
        role_field="eligible_roles" if existing.eligible_roles or incoming.eligible_roles else "none",
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
    non_goals: tuple[str, ...] = ()
    policies: dict[str, Mapping[str, Any]] = {}
    evidence: dict[str, Mapping[str, Any]] = {}
    approvals: dict[str, NormalizedApproval] = {}
    evaluations: dict[str, Mapping[str, Any]] = {}
    rules: dict[str, Rule] = {}
    provenance: list[Mapping[str, Any]] = []

    for pack in selected:
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

        for item in source_policies:
            item_id = _item_id(item, "policy", pack.id)
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
            provenance.append(
                _provenance_record(
                    pack,
                    element_kind="approval",
                    element_id=normalized.id,
                )
            )
            approvals[normalized.id] = (
                _merge_approval(approvals[normalized.id], normalized)
                if normalized.id in approvals
                else normalized
            )
        for item in source_evaluations:
            item_id = _item_id(item, "evaluation", pack.id)
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

    fragments = profile.starter_fragments if profile else ()
    return CompositionResult(
        profile=profile,
        modules=modules,
        required_blocks=required_blocks,
        policies=tuple(policies[key] for key in sorted(policies)),
        evidence_requirements=tuple(evidence[key] for key in sorted(evidence)),
        approval_requirements=tuple(approvals[key] for key in sorted(approvals)),
        evaluations=tuple(evaluations[key] for key in sorted(evaluations)),
        rules=tuple(rules[key] for key in sorted(rules)),
        non_goals=non_goals,
        starter_fragments=tuple(
            sorted(fragments, key=lambda item: (item.target, item.source_index))
        ),
        provenance=tuple(provenance),
        diagnostics=(),
    )
