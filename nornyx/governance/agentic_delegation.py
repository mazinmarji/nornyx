"""AN-002 fixed structural check: static delegation, handoff, and relation governance.

Every record validated here is a declaration. Nothing in this module executes a
delegation, transfers work, opens a connection, or grants authority; validation
proves internal consistency of the contract at an explicit ``as_of`` time.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
import unicodedata
from typing import Any

from .models import CompositionResult, GovernanceDiagnostic
from .agentic_network import (
    AGENTIC_APPROVAL_ID,
    CONTRACT_REVIEW_ID,
    SENSITIVE_CATEGORIES,
    _authorization_problem,
    _check_governance_references,
    _composition_reference_sets,
    _index_unique,
    _mapping_items,
    _name_set,
    _parse_time,
    _revocation_target_key,
    _strings,
    _unknown_references,
    _validate_interval,
)

CHECK_ID = "agentic_network_delegation.v1"
DEFAULT_MAX_DELEGATION_DEPTH = 1
MAX_CHAIN_WALK = 16
HIGH_RISK = frozenset({"high", "critical"})

RELATION_ENDPOINT_KINDS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "identifies": (
        frozenset({"agent_identity"}),
        frozenset({"membership", "protocol_target"}),
    ),
    "owns": (
        frozenset({"agent_identity", "human_role"}),
        frozenset({"capability", "trust_zone", "protocol_target"}),
    ),
    "advertises_capability": (
        frozenset({"agent_identity", "protocol_target"}),
        frozenset({"capability"}),
    ),
    "delegates_to": (frozenset({"agent_identity"}), frozenset({"agent_identity"})),
    "hands_off_to": (frozenset({"agent_identity"}), frozenset({"agent_identity"})),
    "communicates_with": (
        frozenset({"agent_identity"}),
        frozenset({"agent_identity", "protocol_target"}),
    ),
    "crosses_trust_zone": (
        frozenset({"agent_identity", "membership", "protocol_target"}),
        frozenset({"trust_zone"}),
    ),
    "shares_with": (
        frozenset({"agent_identity", "trust_zone"}),
        frozenset({"agent_identity", "trust_zone", "protocol_target"}),
    ),
    "requires_approval_from": (
        frozenset(
            {"agent_identity", "capability", "delegation", "handoff", "protocol_target"}
        ),
        frozenset({"human_role"}),
    ),
    "revokes": (
        frozenset({"revocation"}),
        frozenset(
            {
                "agent_identity",
                "membership",
                "protocol_target",
                "delegation",
                "handoff",
                "approval",
            }
        ),
    ),
    "observed_by": (
        frozenset({"agent_identity", "delegation", "handoff", "protocol_target"}),
        frozenset({"agent_identity", "human_role"}),
    ),
}
RELATION_BINDING_FIELDS = {
    "delegates_to": "delegation_ref",
    "hands_off_to": "handoff_ref",
    "communicates_with": "protocol_target_ref",
}
REVOCATION_KIND_BY_ENDPOINT = {
    "agent_identity": "agent_identity",
    "membership": "membership",
    "protocol_target": "protocol_target",
    "delegation": "delegation",
    "handoff": "handoff",
    "approval": "approval_record",
}


def _diagnostic(code: str, message: str, *, path: str) -> GovernanceDiagnostic:
    return GovernanceDiagnostic(
        "error",
        code,
        message,
        path=path,
        source_id=CHECK_ID,
    )


def _normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _collection(
    network: Mapping[str, Any],
    field: str,
    *,
    diagnostics: list[GovernanceDiagnostic],
) -> list[Mapping[str, Any]]:
    raw = network.get(field)
    if raw is None:
        return []
    if not isinstance(raw, list):
        diagnostics.append(
            _diagnostic(
                "AN_COLLECTION_MALFORMED",
                f"agentic_network.{field} must be a list of records.",
                path=f"agentic_network.{field}",
            )
        )
        return []
    malformed = [index for index, item in enumerate(raw) if not isinstance(item, Mapping)]
    for index in malformed:
        diagnostics.append(
            _diagnostic(
                "AN_COLLECTION_MALFORMED",
                f"agentic_network.{field}[{index}] must be a mapping.",
                path=f"agentic_network.{field}[{index}]",
            )
        )
    return _mapping_items(raw)


def _normalization_collisions(
    items: list[Mapping[str, Any]],
    *,
    field: str,
    path: str,
    diagnostics: list[GovernanceDiagnostic],
) -> None:
    seen: dict[str, str] = {}
    for item in items:
        value = item.get(field)
        if not isinstance(value, str):
            continue
        key = _normalized(value)
        previous = seen.get(key)
        if previous is not None and previous != value:
            diagnostics.append(
                _diagnostic(
                    "AN_NORMALIZATION_COLLISION",
                    f"Identifiers {previous!r} and {value!r} collide after "
                    "Unicode normalization.",
                    path=path,
                )
            )
        else:
            seen.setdefault(key, value)


def _effective_interval(item: Mapping[str, Any]) -> tuple[datetime | None, datetime | None]:
    return _parse_time(item.get("valid_from")), _parse_time(item.get("expires_at"))


def _authorized_memberships(
    memberships: list[Mapping[str, Any]],
    *,
    identity_ref: Any,
    zone_ref: Any,
    as_of: datetime | None,
    effective_revocations: set[tuple[str, ...]],
) -> list[Mapping[str, Any]]:
    result = []
    for membership in memberships:
        if membership.get("identity_ref") != identity_ref:
            continue
        if membership.get("trust_zone_ref") != zone_ref:
            continue
        if _authorization_problem(membership, active_status="authorized", as_of=as_of):
            continue
        if ("membership", str(membership.get("id"))) in effective_revocations:
            continue
        result.append(membership)
    return result


def _identity_effectiveness(
    identity: Mapping[str, Any] | None,
    identity_ref: Any,
    *,
    noun: str,
    unknown_code: str,
    not_effective_code: str,
    revoked_code: str,
    path: str,
    as_of: datetime | None,
    effective_revocations: set[tuple[str, ...]],
    diagnostics: list[GovernanceDiagnostic],
) -> bool:
    if identity is None:
        diagnostics.append(
            _diagnostic(
                unknown_code,
                f"Unknown {noun} identity {identity_ref!r}.",
                path=path,
            )
        )
        return False
    problem = _authorization_problem(identity, active_status="active", as_of=as_of)
    if problem is not None:
        diagnostics.append(
            _diagnostic(
                not_effective_code,
                f"{noun.capitalize()} identity is not effective: {problem}.",
                path=path,
            )
        )
    if ("agent_identity", str(identity_ref)) in effective_revocations:
        diagnostics.append(
            _diagnostic(
                revoked_code,
                f"{noun.capitalize()} identity has an effective revocation.",
                path=path,
            )
        )
    return True


def _cross_zone_controls(
    item: Mapping[str, Any],
    *,
    action_class: str,
    source_zone_ref: Any,
    target_zone_ref: Any,
    zone_by_id: dict[str, Mapping[str, Any]],
    gate_by_id: dict[str, Mapping[str, Any]],
    prefix: str,
    path: str,
    transition_field: str,
    diagnostics: list[GovernanceDiagnostic],
) -> None:
    source_zone = zone_by_id.get(str(source_zone_ref))
    if source_zone is not None and target_zone_ref not in _strings(
        source_zone.get("allowed_transition_targets")
    ):
        diagnostics.append(
            _diagnostic(
                f"{prefix}_TRANSITION_NOT_ALLOWED",
                "Cross-zone transition is not explicitly allowed by the source zone.",
                path=f"{path}.{transition_field}",
            )
        )
    gate_refs = _strings(item.get("required_gate_refs"))
    if not gate_refs:
        diagnostics.append(
            _diagnostic(
                f"{prefix}_GATE_REQUIRED",
                "Cross-zone records require at least one governing network gate.",
                path=f"{path}.required_gate_refs",
            )
        )
        return
    covered: set[str] = set()
    for gate_ref in gate_refs:
        gate = gate_by_id.get(gate_ref)
        if gate is None:
            continue
        covered.update(_strings(gate.get("action_classes")))
        if source_zone_ref not in _strings(gate.get("source_zone_refs")):
            diagnostics.append(
                _diagnostic(
                    f"{prefix}_GATE_SOURCE_MISMATCH",
                    f"Gate {gate_ref!r} does not cover the source zone.",
                    path=f"{path}.required_gate_refs",
                )
            )
        if target_zone_ref not in _strings(gate.get("target_zone_refs")):
            diagnostics.append(
                _diagnostic(
                    f"{prefix}_GATE_TARGET_MISMATCH",
                    f"Gate {gate_ref!r} does not cover the target zone.",
                    path=f"{path}.required_gate_refs",
                )
            )
    if action_class not in covered:
        diagnostics.append(
            _diagnostic(
                f"{prefix}_GATE_ACTION_MISSING",
                f"No referenced gate covers the {action_class!r} action class.",
                path=f"{path}.required_gate_refs",
            )
        )


def _require_authority_references(
    item: Mapping[str, Any],
    *,
    prefix: str,
    path: str,
    diagnostics: list[GovernanceDiagnostic],
) -> None:
    if AGENTIC_APPROVAL_ID not in _strings(item.get("required_approval_refs")):
        diagnostics.append(
            _diagnostic(
                f"{prefix}_APPROVAL_REQUIRED",
                "Human agentic-network approval is required for this record.",
                path=f"{path}.required_approval_refs",
            )
        )
    if CONTRACT_REVIEW_ID not in _strings(item.get("required_evidence_refs")):
        diagnostics.append(
            _diagnostic(
                f"{prefix}_EVIDENCE_REQUIRED",
                "Contract-review evidence is required for this record.",
                path=f"{path}.required_evidence_refs",
            )
        )


def _check_revocation_refs(
    item: Mapping[str, Any],
    *,
    kind: str,
    revocation_ids: set[str],
    revocation_target_by_id: dict[str, tuple[str, ...]],
    path: str,
    diagnostics: list[GovernanceDiagnostic],
) -> None:
    _unknown_references(
        _strings(item.get("revocation_refs")),
        revocation_ids,
        path=f"{path}.revocation_refs",
        code="AN_REVOCATION_UNKNOWN",
        noun="revocation",
        diagnostics=diagnostics,
    )
    for revocation_ref in _strings(item.get("revocation_refs")):
        target_key = revocation_target_by_id.get(revocation_ref)
        if target_key is not None and target_key != (kind, item.get("id")):
            diagnostics.append(
                _diagnostic(
                    "AN_REVOCATION_REFERENCE_MISMATCH",
                    "Revocation reference targets another subject.",
                    path=f"{path}.revocation_refs",
                )
            )


def _approval_action_coverage(
    document: Mapping[str, Any],
    *,
    action: str,
    diagnostics: list[GovernanceDiagnostic],
) -> None:
    declarations = _mapping_items(document.get("approvals"))
    declaration_index = next(
        (
            index
            for index, item in enumerate(declarations)
            if item.get("id") == AGENTIC_APPROVAL_ID
            or item.get("name") == AGENTIC_APPROVAL_ID
        ),
        None,
    )
    if declaration_index is None:
        # The foundation check already reports the missing declaration.
        return
    declared = _strings(declarations[declaration_index].get("required_for"))
    if action not in declared:
        diagnostics.append(
            _diagnostic(
                "AN_APPROVAL_ACTION_MISSING",
                f"Approval declaration does not cover required action {action!r}.",
                path=f"approvals[{declaration_index}].required_for",
            )
        )


def agentic_network_delegation_check(
    document: Mapping[str, Any],
    composition: CompositionResult,
    *,
    as_of: datetime | None,
    document_root: Path | None,
) -> tuple[GovernanceDiagnostic, ...]:
    """Validate AN-002 delegation, handoff, and relation declarations."""

    del document_root
    network = document.get("agentic_network")
    if not isinstance(network, Mapping):
        return ()

    diagnostics: list[GovernanceDiagnostic] = []
    delegations = _collection(network, "delegations", diagnostics=diagnostics)
    handoffs = _collection(network, "handoffs", diagnostics=diagnostics)
    relations = _collection(network, "relations", diagnostics=diagnostics)

    identities = _mapping_items(document.get("agent_identities"))
    capabilities = _mapping_items(document.get("capabilities"))
    zones = _mapping_items(network.get("trust_zones"))
    memberships = _mapping_items(network.get("memberships"))
    protocols = _mapping_items(network.get("protocol_targets"))
    gates = _mapping_items(network.get("network_gates"))
    revocations = _mapping_items(network.get("revocations"))

    identity_by_id = {
        str(item["id"]): item for item in identities if isinstance(item.get("id"), str)
    }
    capability_by_name = {
        str(item["name"]): item
        for item in capabilities
        if isinstance(item.get("name"), str)
    }
    zone_by_id = {
        str(item["id"]): item for item in zones if isinstance(item.get("id"), str)
    }
    gate_by_id = {
        str(item["id"]): item for item in gates if isinstance(item.get("id"), str)
    }
    protocol_by_id = {
        str(item["id"]): item for item in protocols if isinstance(item.get("id"), str)
    }
    membership_ids = _name_set(memberships, "id")
    revocation_ids = _name_set(revocations, "id")
    approval_refs, evidence_refs, policy_refs = _composition_reference_sets(
        document, composition
    )

    revocation_target_by_id: dict[str, tuple[str, ...]] = {}
    effective_revocations: set[tuple[str, ...]] = set()
    for revocation in revocations:
        target_key = _revocation_target_key(revocation.get("target"))
        revocation_id = revocation.get("id")
        if target_key is None or not isinstance(revocation_id, str):
            continue
        revocation_target_by_id[revocation_id] = target_key
        effective_at = _parse_time(revocation.get("effective_at"))
        if effective_at is not None and as_of is not None and as_of >= effective_at:
            effective_revocations.add(target_key)

    delegation_by_id = _index_unique(
        delegations,
        field="id",
        path="agentic_network.delegations",
        code="AN_DELEGATION_DUPLICATE",
        noun="Delegation",
        diagnostics=diagnostics,
    )
    handoff_by_id = _index_unique(
        handoffs,
        field="id",
        path="agentic_network.handoffs",
        code="AN_HANDOFF_DUPLICATE",
        noun="Handoff",
        diagnostics=diagnostics,
    )
    _index_unique(
        relations,
        field="id",
        path="agentic_network.relations",
        code="AN_RELATION_DUPLICATE",
        noun="Relation",
        diagnostics=diagnostics,
    )
    for items, path in (
        (delegations, "agentic_network.delegations"),
        (handoffs, "agentic_network.handoffs"),
        (relations, "agentic_network.relations"),
    ):
        _normalization_collisions(items, field="id", path=path, diagnostics=diagnostics)

    goal_ids = _name_set(_mapping_items(document.get("goals")), "id")
    intent_names = _name_set(_mapping_items(document.get("intents")), "name")
    mission_refs = goal_ids | intent_names

    needs_delegate_approval = False
    needs_handoff_approval = False

    for index, delegation in enumerate(delegations):
        path = f"agentic_network.delegations[{index}]"
        delegator_ref = delegation.get("delegator_ref")
        delegate_ref = delegation.get("delegate_ref")
        capability_ref = delegation.get("capability_ref")
        source_zone_ref = delegation.get("source_zone_ref")
        target_zone_ref = delegation.get("target_zone_ref")

        delegator = identity_by_id.get(str(delegator_ref))
        delegate = identity_by_id.get(str(delegate_ref))
        _identity_effectiveness(
            delegator,
            delegator_ref,
            noun="delegator",
            unknown_code="AN_DELEGATOR_UNKNOWN",
            not_effective_code="AN_DELEGATOR_NOT_EFFECTIVE",
            revoked_code="AN_DELEGATOR_REVOKED",
            path=f"{path}.delegator_ref",
            as_of=as_of,
            effective_revocations=effective_revocations,
            diagnostics=diagnostics,
        )
        _identity_effectiveness(
            delegate,
            delegate_ref,
            noun="delegate",
            unknown_code="AN_DELEGATE_UNKNOWN",
            not_effective_code="AN_DELEGATE_NOT_EFFECTIVE",
            revoked_code="AN_DELEGATE_REVOKED",
            path=f"{path}.delegate_ref",
            as_of=as_of,
            effective_revocations=effective_revocations,
            diagnostics=diagnostics,
        )
        if (
            isinstance(delegator_ref, str)
            and isinstance(delegate_ref, str)
            and delegator_ref == delegate_ref
        ):
            diagnostics.append(
                _diagnostic(
                    "AN_SELF_DELEGATION",
                    "An identity cannot delegate a capability to itself.",
                    path=f"{path}.delegate_ref",
                )
            )

        capability = capability_by_name.get(str(capability_ref))
        if capability is None:
            diagnostics.append(
                _diagnostic(
                    "AN_CAPABILITY_UNKNOWN",
                    f"Unknown capability reference {capability_ref!r}.",
                    path=f"{path}.capability_ref",
                )
            )
        else:
            if capability.get("delegable") is not True:
                diagnostics.append(
                    _diagnostic(
                        "AN_CAPABILITY_NOT_DELEGABLE",
                        f"Capability {capability_ref!r} is not delegable.",
                        path=f"{path}.capability_ref",
                    )
                )
            actions = set(_strings(delegation.get("actions")))
            capability_actions = set(_strings(capability.get("actions")))
            if not actions or not actions <= capability_actions:
                diagnostics.append(
                    _diagnostic(
                        "AN_DELEGATION_ACTION_ESCALATION",
                        "Delegated actions must be a non-empty subset of the "
                        "capability actions.",
                        path=f"{path}.actions",
                    )
                )
            scopes = set(_strings(delegation.get("scope_refs")))
            capability_scopes = set(_strings(capability.get("scope_refs")))
            if not scopes or not scopes <= capability_scopes:
                diagnostics.append(
                    _diagnostic(
                        "AN_DELEGATION_SCOPE_ESCALATION",
                        "Delegated scopes must be a non-empty subset of the "
                        "capability scopes.",
                        path=f"{path}.scope_refs",
                    )
                )
            policy_depth = capability.get("max_delegation_depth")
            allowed_depth = (
                policy_depth
                if isinstance(policy_depth, int) and not isinstance(policy_depth, bool)
                else DEFAULT_MAX_DELEGATION_DEPTH
            )
            max_depth = delegation.get("max_depth")
            if (
                isinstance(max_depth, int)
                and not isinstance(max_depth, bool)
                and max_depth > allowed_depth
            ):
                diagnostics.append(
                    _diagnostic(
                        "AN_DELEGATION_DEPTH_POLICY_EXCEEDED",
                        "Delegation max_depth exceeds the capability delegation "
                        "policy.",
                        path=f"{path}.max_depth",
                    )
                )

        sensitive_uses = SENSITIVE_CATEGORIES & (
            set(_strings(delegation.get("scope_refs")))
            | set(_strings(delegation.get("actions")))
        )
        if sensitive_uses:
            diagnostics.append(
                _diagnostic(
                    "AN_DELEGATION_SENSITIVE_SHARING",
                    "Delegations must not carry sensitive categories: "
                    + ", ".join(sorted(sensitive_uses))
                    + ".",
                    path=path,
                )
            )

        for field, zone_ref in (
            ("source_zone_ref", source_zone_ref),
            ("target_zone_ref", target_zone_ref),
        ):
            if isinstance(zone_ref, str) and zone_ref not in zone_by_id:
                diagnostics.append(
                    _diagnostic(
                        "AN_TRUST_ZONE_UNKNOWN",
                        f"Delegation references unknown trust zone {zone_ref!r}.",
                        path=f"{path}.{field}",
                    )
                )
        _unknown_references(
            _strings(delegation.get("required_gate_refs")),
            set(gate_by_id),
            path=f"{path}.required_gate_refs",
            code="AN_GATE_UNKNOWN",
            noun="network gate",
            diagnostics=diagnostics,
        )

        if delegator is not None and capability is not None:
            capability_name = str(capability_ref)
            if capability_name not in _strings(delegator.get("capability_refs")):
                diagnostics.append(
                    _diagnostic(
                        "AN_DELEGATOR_CAPABILITY_MISSING",
                        "Delegator identity does not possess the delegated "
                        "capability.",
                        path=f"{path}.capability_ref",
                    )
                )
            else:
                assigned = [
                    membership
                    for membership in _authorized_memberships(
                        memberships,
                        identity_ref=delegator_ref,
                        zone_ref=source_zone_ref,
                        as_of=as_of,
                        effective_revocations=effective_revocations,
                    )
                    if capability_name in _strings(membership.get("capability_refs"))
                ]
                if not assigned:
                    diagnostics.append(
                        _diagnostic(
                            "AN_DELEGATOR_MEMBERSHIP_REQUIRED",
                            "Delegator requires an authorized source-zone membership "
                            "carrying the delegated capability.",
                            path=f"{path}.source_zone_ref",
                        )
                    )
                if (
                    "capability_assignment",
                    "agent_identity",
                    str(delegator_ref),
                    capability_name,
                ) in effective_revocations or any(
                    (
                        "capability_assignment",
                        "membership",
                        str(membership.get("id")),
                        capability_name,
                    )
                    in effective_revocations
                    for membership in assigned
                ):
                    diagnostics.append(
                        _diagnostic(
                            "AN_DELEGATOR_CAPABILITY_REVOKED",
                            "The delegator's capability assignment has an effective "
                            "revocation.",
                            path=f"{path}.capability_ref",
                        )
                    )
        if delegate is not None and not _authorized_memberships(
            memberships,
            identity_ref=delegate_ref,
            zone_ref=target_zone_ref,
            as_of=as_of,
            effective_revocations=effective_revocations,
        ):
            diagnostics.append(
                _diagnostic(
                    "AN_DELEGATE_NOT_ELIGIBLE",
                    "Delegate requires an authorized membership in the delegation "
                    "target zone.",
                    path=f"{path}.target_zone_ref",
                )
            )

        _validate_interval(
            delegation,
            path=path,
            active_status="active",
            as_of=as_of,
            diagnostics=diagnostics,
        )

        max_depth = delegation.get("max_depth")
        current_depth = delegation.get("current_depth")
        depths_valid = all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in (max_depth, current_depth)
        )
        parent_ref = delegation.get("parent_delegation_ref")
        if parent_ref is None:
            if depths_valid and current_depth != 0:
                diagnostics.append(
                    _diagnostic(
                        "AN_DELEGATION_DEPTH_INVALID",
                        "A root delegation must declare current_depth 0.",
                        path=f"{path}.current_depth",
                    )
                )
        else:
            parent = delegation_by_id.get(str(parent_ref))
            if parent is None:
                diagnostics.append(
                    _diagnostic(
                        "AN_DELEGATION_PARENT_UNKNOWN",
                        f"Unknown parent delegation {parent_ref!r}.",
                        path=f"{path}.parent_delegation_ref",
                    )
                )
            else:
                if parent.get("onward_delegation") != "allowed_with_policy":
                    diagnostics.append(
                        _diagnostic(
                            "AN_ONWARD_DELEGATION_DENIED",
                            "The parent delegation denies onward delegation.",
                            path=f"{path}.parent_delegation_ref",
                        )
                    )
                if parent.get("delegate_ref") != delegator_ref:
                    diagnostics.append(
                        _diagnostic(
                            "AN_DELEGATION_CHAIN_BROKEN",
                            "The delegator must be the parent delegation's delegate.",
                            path=f"{path}.delegator_ref",
                        )
                    )
                if parent.get("capability_ref") != capability_ref:
                    diagnostics.append(
                        _diagnostic(
                            "AN_DELEGATION_CHAIN_CAPABILITY_MISMATCH",
                            "Chained delegations must delegate the same capability.",
                            path=f"{path}.capability_ref",
                        )
                    )
                parent_depth = parent.get("current_depth")
                if (
                    depths_valid
                    and isinstance(parent_depth, int)
                    and not isinstance(parent_depth, bool)
                    and current_depth != parent_depth + 1
                ):
                    diagnostics.append(
                        _diagnostic(
                            "AN_DELEGATION_DEPTH_INVALID",
                            "current_depth must be exactly one more than the parent "
                            "delegation depth.",
                            path=f"{path}.current_depth",
                        )
                    )
                parent_max = parent.get("max_depth")
                if (
                    depths_valid
                    and isinstance(parent_max, int)
                    and not isinstance(parent_max, bool)
                    and max_depth > parent_max
                ):
                    diagnostics.append(
                        _diagnostic(
                            "AN_DELEGATION_DEPTH_POLICY_EXCEEDED",
                            "Delegation max_depth exceeds the parent delegation bound.",
                            path=f"{path}.max_depth",
                        )
                    )
                for field in ("actions", "scope_refs"):
                    child_values = set(_strings(delegation.get(field)))
                    parent_values = set(_strings(parent.get(field)))
                    if child_values and parent_values and not child_values <= parent_values:
                        code = (
                            "AN_DELEGATION_ACTION_ESCALATION"
                            if field == "actions"
                            else "AN_DELEGATION_SCOPE_ESCALATION"
                        )
                        diagnostics.append(
                            _diagnostic(
                                code,
                                "Chained delegations cannot widen the parent "
                                f"delegation {field}.",
                                path=f"{path}.{field}",
                            )
                        )
                child_from, child_until = _effective_interval(delegation)
                parent_from, parent_until = _effective_interval(parent)
                if (
                    None not in (child_from, child_until, parent_from, parent_until)
                    and not (parent_from <= child_from and child_until <= parent_until)
                ):
                    diagnostics.append(
                        _diagnostic(
                            "AN_DELEGATION_INTERVAL_EXCEEDS_PARENT",
                            "A chained delegation's validity must fit inside the "
                            "parent delegation's validity.",
                            path=f"{path}.expires_at",
                        )
                    )
        if depths_valid and current_depth >= max_depth:
            diagnostics.append(
                _diagnostic(
                    "AN_DELEGATION_DEPTH_EXCEEDED",
                    "Delegation depth reaches or exceeds the declared maximum.",
                    path=f"{path}.current_depth",
                )
            )

        walked: list[str] = []
        cursor: Mapping[str, Any] | None = delegation
        for _ in range(MAX_CHAIN_WALK):
            if cursor is None:
                break
            cursor_id = cursor.get("id")
            if isinstance(cursor_id, str):
                if cursor_id in walked:
                    diagnostics.append(
                        _diagnostic(
                            "AN_DELEGATION_CHAIN_CYCLE",
                            "Delegation chains must not form cycles.",
                            path=f"{path}.parent_delegation_ref",
                        )
                    )
                    break
                walked.append(cursor_id)
            parent_pointer = cursor.get("parent_delegation_ref")
            cursor = (
                delegation_by_id.get(str(parent_pointer))
                if isinstance(parent_pointer, str)
                else None
            )
        else:
            diagnostics.append(
                _diagnostic(
                    "AN_DELEGATION_CHAIN_CYCLE",
                    "Delegation chain exceeds the bounded walk limit.",
                    path=f"{path}.parent_delegation_ref",
                )
            )

        delegation_id = delegation.get("id")
        if (
            isinstance(delegation_id, str)
            and ("delegation", delegation_id) in effective_revocations
            and delegation.get("status") == "active"
        ):
            diagnostics.append(
                _diagnostic(
                    "AN_DELEGATION_REVOKED",
                    "An active delegation has an effective revocation.",
                    path=f"{path}.status",
                )
            )
        _check_revocation_refs(
            delegation,
            kind="delegation",
            revocation_ids=revocation_ids,
            revocation_target_by_id=revocation_target_by_id,
            path=path,
            diagnostics=diagnostics,
        )
        _check_governance_references(
            delegation,
            path=path,
            approval_refs=approval_refs,
            evidence_refs=evidence_refs,
            policy_refs=policy_refs,
            diagnostics=diagnostics,
        )

        cross_zone = (
            isinstance(source_zone_ref, str)
            and isinstance(target_zone_ref, str)
            and source_zone_ref != target_zone_ref
        )
        high_risk = capability is not None and capability.get("risk") in HIGH_RISK
        if cross_zone:
            _cross_zone_controls(
                delegation,
                action_class="delegate",
                source_zone_ref=source_zone_ref,
                target_zone_ref=target_zone_ref,
                zone_by_id=zone_by_id,
                gate_by_id=gate_by_id,
                prefix="AN_DELEGATION",
                path=path,
                transition_field="target_zone_ref",
                diagnostics=diagnostics,
            )
        if cross_zone or high_risk:
            needs_delegate_approval = True
            _require_authority_references(
                delegation,
                prefix="AN_DELEGATION",
                path=path,
                diagnostics=diagnostics,
            )

    for index, handoff in enumerate(handoffs):
        path = f"agentic_network.handoffs[{index}]"
        from_ref = handoff.get("from_identity_ref")
        to_ref = handoff.get("to_identity_ref")
        from_zone_ref = handoff.get("from_zone_ref")
        to_zone_ref = handoff.get("to_zone_ref")
        source = identity_by_id.get(str(from_ref))
        target = identity_by_id.get(str(to_ref))
        _identity_effectiveness(
            source,
            from_ref,
            noun="handoff source",
            unknown_code="AN_HANDOFF_SOURCE_UNKNOWN",
            not_effective_code="AN_HANDOFF_SOURCE_NOT_EFFECTIVE",
            revoked_code="AN_HANDOFF_SOURCE_REVOKED",
            path=f"{path}.from_identity_ref",
            as_of=as_of,
            effective_revocations=effective_revocations,
            diagnostics=diagnostics,
        )
        _identity_effectiveness(
            target,
            to_ref,
            noun="handoff target",
            unknown_code="AN_HANDOFF_TARGET_UNKNOWN",
            not_effective_code="AN_HANDOFF_TARGET_NOT_EFFECTIVE",
            revoked_code="AN_HANDOFF_TARGET_REVOKED",
            path=f"{path}.to_identity_ref",
            as_of=as_of,
            effective_revocations=effective_revocations,
            diagnostics=diagnostics,
        )
        if isinstance(from_ref, str) and isinstance(to_ref, str) and from_ref == to_ref:
            diagnostics.append(
                _diagnostic(
                    "AN_HANDOFF_SELF",
                    "An identity cannot hand off to itself.",
                    path=f"{path}.to_identity_ref",
                )
            )
        mission_ref = handoff.get("mission_ref")
        if isinstance(mission_ref, str) and mission_ref not in mission_refs:
            diagnostics.append(
                _diagnostic(
                    "AN_HANDOFF_MISSION_UNKNOWN",
                    f"Handoff mission {mission_ref!r} is not a declared goal or "
                    "intent.",
                    path=f"{path}.mission_ref",
                )
            )
        for field, zone_ref in (
            ("from_zone_ref", from_zone_ref),
            ("to_zone_ref", to_zone_ref),
        ):
            if isinstance(zone_ref, str) and zone_ref not in zone_by_id:
                diagnostics.append(
                    _diagnostic(
                        "AN_TRUST_ZONE_UNKNOWN",
                        f"Handoff references unknown trust zone {zone_ref!r}.",
                        path=f"{path}.{field}",
                    )
                )
        if source is not None and not _authorized_memberships(
            memberships,
            identity_ref=from_ref,
            zone_ref=from_zone_ref,
            as_of=as_of,
            effective_revocations=effective_revocations,
        ):
            diagnostics.append(
                _diagnostic(
                    "AN_HANDOFF_MEMBERSHIP_REQUIRED",
                    "Handoff source requires an authorized membership in the "
                    "source zone.",
                    path=f"{path}.from_zone_ref",
                )
            )
        target_memberships = (
            _authorized_memberships(
                memberships,
                identity_ref=to_ref,
                zone_ref=to_zone_ref,
                as_of=as_of,
                effective_revocations=effective_revocations,
            )
            if target is not None
            else []
        )
        if target is not None and not target_memberships:
            diagnostics.append(
                _diagnostic(
                    "AN_HANDOFF_MEMBERSHIP_REQUIRED",
                    "Handoff target requires an authorized membership in the "
                    "target zone.",
                    path=f"{path}.to_zone_ref",
                )
            )

        delegation_refs = _strings(handoff.get("delegation_refs"))
        supporting: dict[str, Mapping[str, Any]] = {}
        for delegation_ref in delegation_refs:
            supplied = delegation_by_id.get(delegation_ref)
            if supplied is None:
                diagnostics.append(
                    _diagnostic(
                        "AN_HANDOFF_DELEGATION_UNKNOWN",
                        f"Handoff references unknown delegation {delegation_ref!r}.",
                        path=f"{path}.delegation_refs",
                    )
                )
                continue
            if supplied.get("delegate_ref") != to_ref:
                diagnostics.append(
                    _diagnostic(
                        "AN_HANDOFF_DELEGATION_MISMATCH",
                        f"Delegation {delegation_ref!r} does not delegate to the "
                        "handoff target.",
                        path=f"{path}.delegation_refs",
                    )
                )
                continue
            supporting[delegation_ref] = supplied

        high_risk_handoff = False
        for capability_ref in _strings(handoff.get("required_capability_refs")):
            capability = capability_by_name.get(capability_ref)
            if capability is None:
                diagnostics.append(
                    _diagnostic(
                        "AN_CAPABILITY_UNKNOWN",
                        f"Unknown capability reference {capability_ref!r}.",
                        path=f"{path}.required_capability_refs",
                    )
                )
                continue
            if capability.get("risk") in HIGH_RISK:
                high_risk_handoff = True
            held = target is not None and (
                capability_ref in _strings(target.get("capability_refs"))
                and any(
                    capability_ref in _strings(membership.get("capability_refs"))
                    for membership in target_memberships
                )
            )
            if held:
                continue
            delegated = False
            for delegation_ref, supplied in supporting.items():
                if supplied.get("capability_ref") != capability_ref:
                    continue
                if supplied.get("status") != "active":
                    continue
                if supplied.get("target_zone_ref") != to_zone_ref:
                    continue
                if ("delegation", delegation_ref) in effective_revocations:
                    continue
                if _authorization_problem(
                    supplied, active_status="active", as_of=as_of
                ):
                    continue
                delegated = True
                break
            if not delegated:
                diagnostics.append(
                    _diagnostic(
                        "AN_HANDOFF_AUTHORITY_ESCALATION",
                        f"Handoff requires capability {capability_ref!r} that the "
                        "target neither holds nor validly receives by delegation; "
                        "a handoff cannot grant authority.",
                        path=f"{path}.required_capability_refs",
                    )
                )

        shared = set(_strings(handoff.get("shared_context")))
        never_share = set(_strings(handoff.get("never_share")))
        missing_categories = SENSITIVE_CATEGORIES - never_share
        leaked = SENSITIVE_CATEGORIES & shared
        if missing_categories or leaked:
            diagnostics.append(
                _diagnostic(
                    "AN_HANDOFF_SENSITIVE_SHARING",
                    "Handoffs must never share sensitive categories and must "
                    "declare them in never_share.",
                    path=f"{path}.shared_context" if leaked else f"{path}.never_share",
                )
            )
        from_zone = zone_by_id.get(str(from_zone_ref))
        to_zone = zone_by_id.get(str(to_zone_ref))
        for category in sorted(shared - SENSITIVE_CATEGORIES):
            allowed_source = from_zone is None or category in _strings(
                from_zone.get("share_allowlist")
            )
            allowed_target = to_zone is None or category in _strings(
                to_zone.get("share_allowlist")
            )
            if not allowed_source or not allowed_target:
                diagnostics.append(
                    _diagnostic(
                        "AN_HANDOFF_SHARE_NOT_ALLOWED",
                        f"Shared context {category!r} is not allowed by both zone "
                        "allowlists.",
                        path=f"{path}.shared_context",
                    )
                )

        valid_from, expires_at = _effective_interval(handoff)
        if valid_from is None or expires_at is None or valid_from >= expires_at:
            diagnostics.append(
                _diagnostic(
                    "AN_AUTHORIZATION_INTERVAL_INVALID",
                    "Handoff validity must use offset timestamps with valid_from "
                    "before expires_at.",
                    path=path,
                )
            )
        elif handoff.get("status") in {"initiated", "accepted"} and as_of is not None:
            if as_of < valid_from:
                diagnostics.append(
                    _diagnostic(
                        "AN_AUTHORIZATION_NOT_YET_VALID",
                        "Handoff authorization is not yet valid.",
                        path=f"{path}.valid_from",
                    )
                )
            if as_of >= expires_at:
                diagnostics.append(
                    _diagnostic(
                        "AN_AUTHORIZATION_EXPIRED",
                        "Handoff authorization is expired.",
                        path=f"{path}.expires_at",
                    )
                )

        status = handoff.get("status")
        superseded_by = handoff.get("superseded_by_ref")
        if status == "superseded":
            if not isinstance(superseded_by, str) or superseded_by not in handoff_by_id:
                diagnostics.append(
                    _diagnostic(
                        "AN_HANDOFF_SUPERSEDED_REF_INVALID",
                        "A superseded handoff must reference a declared successor.",
                        path=f"{path}.superseded_by_ref",
                    )
                )
            elif superseded_by == handoff.get("id"):
                diagnostics.append(
                    _diagnostic(
                        "AN_HANDOFF_SUPERSEDED_REF_INVALID",
                        "A handoff cannot supersede itself.",
                        path=f"{path}.superseded_by_ref",
                    )
                )
        elif superseded_by is not None:
            diagnostics.append(
                _diagnostic(
                    "AN_HANDOFF_STATUS_CONTRADICTION",
                    "Only superseded handoffs may declare superseded_by_ref.",
                    path=f"{path}.superseded_by_ref",
                )
            )
        handoff_id = handoff.get("id")
        if (
            isinstance(handoff_id, str)
            and ("handoff", handoff_id) in effective_revocations
            and status in {"initiated", "accepted", "completed"}
        ):
            diagnostics.append(
                _diagnostic(
                    "AN_HANDOFF_REVOKED",
                    "A revoked handoff cannot remain in an active or completed "
                    "status.",
                    path=f"{path}.status",
                )
            )
        _check_revocation_refs(
            handoff,
            kind="handoff",
            revocation_ids=revocation_ids,
            revocation_target_by_id=revocation_target_by_id,
            path=path,
            diagnostics=diagnostics,
        )
        _check_governance_references(
            handoff,
            path=path,
            approval_refs=approval_refs,
            evidence_refs=evidence_refs,
            policy_refs=policy_refs,
            diagnostics=diagnostics,
        )
        _unknown_references(
            _strings(handoff.get("required_gate_refs")),
            set(gate_by_id),
            path=f"{path}.required_gate_refs",
            code="AN_GATE_UNKNOWN",
            noun="network gate",
            diagnostics=diagnostics,
        )

        cross_zone = (
            isinstance(from_zone_ref, str)
            and isinstance(to_zone_ref, str)
            and from_zone_ref != to_zone_ref
        )
        if cross_zone:
            _cross_zone_controls(
                handoff,
                action_class="handoff",
                source_zone_ref=from_zone_ref,
                target_zone_ref=to_zone_ref,
                zone_by_id=zone_by_id,
                gate_by_id=gate_by_id,
                prefix="AN_HANDOFF",
                path=path,
                transition_field="to_zone_ref",
                diagnostics=diagnostics,
            )
        if cross_zone or high_risk_handoff:
            needs_handoff_approval = True
            _require_authority_references(
                handoff,
                prefix="AN_HANDOFF",
                path=path,
                diagnostics=diagnostics,
            )

    module_roles: set[str] = set()
    for requirement in composition.approval_requirements:
        if requirement.id != AGENTIC_APPROVAL_ID:
            continue
        module_roles.update(requirement.required_roles)
        module_roles.update(requirement.eligible_roles)
        if requirement.accountable_authority is not None:
            module_roles.add(requirement.accountable_authority)
    declared_roles: set[str] = set()
    for declaration in _mapping_items(document.get("approvals")):
        declared_roles.update(_strings(declaration.get("required_roles")))
        declared_roles.update(_strings(declaration.get("eligible_roles")))
        authority = declaration.get("accountable_authority")
        if isinstance(authority, str):
            declared_roles.add(authority)

    endpoint_sets: dict[str, set[str]] = {
        "agent_identity": set(identity_by_id),
        "capability": set(capability_by_name),
        "trust_zone": set(zone_by_id),
        "membership": set(membership_ids),
        "protocol_target": set(protocol_by_id),
        "delegation": set(delegation_by_id),
        "handoff": set(handoff_by_id),
        "approval": set(approval_refs),
        "revocation": set(revocation_ids),
        "human_role": module_roles | declared_roles,
    }

    def _zone_allowlists(endpoint: Mapping[str, Any]) -> set[str] | None:
        kind = endpoint.get("kind")
        ref = endpoint.get("ref")
        if kind == "trust_zone":
            zone = zone_by_id.get(str(ref))
            if zone is None:
                return None
            return set(_strings(zone.get("share_allowlist")))
        if kind == "agent_identity":
            allow: set[str] = set()
            found = False
            for membership in memberships:
                if membership.get("identity_ref") != ref:
                    continue
                if _authorization_problem(
                    membership, active_status="authorized", as_of=as_of
                ):
                    continue
                zone = zone_by_id.get(str(membership.get("trust_zone_ref")))
                if zone is not None:
                    found = True
                    allow.update(_strings(zone.get("share_allowlist")))
            return allow if found else None
        return None

    for index, relation in enumerate(relations):
        path = f"agentic_network.relations[{index}]"
        relation_type = relation.get("type")
        source = relation.get("source")
        target = relation.get("target")
        if (
            not isinstance(relation_type, str)
            or relation_type not in RELATION_ENDPOINT_KINDS
            or not isinstance(source, Mapping)
            or not isinstance(target, Mapping)
        ):
            diagnostics.append(
                _diagnostic(
                    "AN_COLLECTION_MALFORMED",
                    "Relations require a supported type and mapping endpoints.",
                    path=path,
                )
            )
            continue
        allowed_sources, allowed_targets = RELATION_ENDPOINT_KINDS[relation_type]
        endpoints_known = True
        for name, endpoint, allowed, unknown_code in (
            ("source", source, allowed_sources, "AN_RELATION_SOURCE_UNKNOWN"),
            ("target", target, allowed_targets, "AN_RELATION_TARGET_UNKNOWN"),
        ):
            kind = endpoint.get("kind")
            ref = endpoint.get("ref")
            if not isinstance(kind, str) or kind not in endpoint_sets:
                diagnostics.append(
                    _diagnostic(
                        "AN_RELATION_ENDPOINT_KIND_INVALID",
                        f"Relation {name} kind {kind!r} is not supported.",
                        path=f"{path}.{name}.kind",
                    )
                )
                endpoints_known = False
                continue
            if kind not in allowed:
                diagnostics.append(
                    _diagnostic(
                        "AN_RELATION_ENDPOINT_KIND_INVALID",
                        f"Relation type {relation_type!r} does not allow {name} "
                        f"kind {kind!r}.",
                        path=f"{path}.{name}.kind",
                    )
                )
            if not isinstance(ref, str) or ref not in endpoint_sets[kind]:
                diagnostics.append(
                    _diagnostic(
                        unknown_code,
                        f"Relation {name} {ref!r} does not exist as {kind!r}.",
                        path=f"{path}.{name}.ref",
                    )
                )
                endpoints_known = False
        if (
            endpoints_known
            and source.get("kind") == target.get("kind")
            and source.get("ref") == target.get("ref")
        ):
            diagnostics.append(
                _diagnostic(
                    "AN_RELATION_SELF_REFERENCE",
                    "Relations must not reference the same endpoint twice.",
                    path=f"{path}.target",
                )
            )

        for field in ("delegation_ref", "handoff_ref", "protocol_target_ref"):
            value = relation.get(field)
            if value is not None and RELATION_BINDING_FIELDS.get(relation_type) != field:
                diagnostics.append(
                    _diagnostic(
                        "AN_RELATION_REFERENCE_INCONSISTENT",
                        f"Relation type {relation_type!r} does not use {field}.",
                        path=f"{path}.{field}",
                    )
                )

        if relation_type == "identifies" and endpoints_known:
            target_kind = target.get("kind")
            target_ref = str(target.get("ref"))
            if target_kind == "membership":
                membership = next(
                    (item for item in memberships if item.get("id") == target_ref),
                    None,
                )
                consistent = (
                    membership is not None
                    and membership.get("identity_ref") == source.get("ref")
                )
            else:
                protocol = protocol_by_id.get(target_ref)
                consistent = protocol is not None and source.get("ref") in _strings(
                    protocol.get("identity_refs")
                )
            if not consistent:
                diagnostics.append(
                    _diagnostic(
                        "AN_RELATION_REFERENCE_INCONSISTENT",
                        "identifies relations must match the target record's "
                        "declared identity.",
                        path=f"{path}.target.ref",
                    )
                )

        if relation_type == "delegates_to":
            delegation_ref = relation.get("delegation_ref")
            if not isinstance(delegation_ref, str):
                diagnostics.append(
                    _diagnostic(
                        "AN_RELATION_DELEGATION_REF_REQUIRED",
                        "delegates_to relations must bind a delegation record.",
                        path=f"{path}.delegation_ref",
                    )
                )
            else:
                bound = delegation_by_id.get(delegation_ref)
                if bound is None:
                    diagnostics.append(
                        _diagnostic(
                            "AN_RELATION_DELEGATION_UNKNOWN",
                            f"Unknown delegation {delegation_ref!r}.",
                            path=f"{path}.delegation_ref",
                        )
                    )
                else:
                    if bound.get("delegator_ref") != source.get("ref") or bound.get(
                        "delegate_ref"
                    ) != target.get("ref"):
                        diagnostics.append(
                            _diagnostic(
                                "AN_RELATION_REFERENCE_INCONSISTENT",
                                "delegates_to endpoints must match the bound "
                                "delegation record.",
                                path=f"{path}.delegation_ref",
                            )
                        )
                    if bound.get("status") != "active" or (
                        ("delegation", delegation_ref) in effective_revocations
                    ):
                        diagnostics.append(
                            _diagnostic(
                                "AN_RELATION_CONTRADICTORY",
                                "delegates_to relations cannot assert an inactive "
                                "or revoked delegation.",
                                path=f"{path}.delegation_ref",
                            )
                        )
        elif relation_type == "hands_off_to":
            handoff_ref = relation.get("handoff_ref")
            if not isinstance(handoff_ref, str):
                diagnostics.append(
                    _diagnostic(
                        "AN_RELATION_HANDOFF_REF_REQUIRED",
                        "hands_off_to relations must bind a handoff record.",
                        path=f"{path}.handoff_ref",
                    )
                )
            else:
                bound = handoff_by_id.get(handoff_ref)
                if bound is None:
                    diagnostics.append(
                        _diagnostic(
                            "AN_RELATION_HANDOFF_UNKNOWN",
                            f"Unknown handoff {handoff_ref!r}.",
                            path=f"{path}.handoff_ref",
                        )
                    )
                else:
                    if bound.get("from_identity_ref") != source.get("ref") or bound.get(
                        "to_identity_ref"
                    ) != target.get("ref"):
                        diagnostics.append(
                            _diagnostic(
                                "AN_RELATION_REFERENCE_INCONSISTENT",
                                "hands_off_to endpoints must match the bound "
                                "handoff record.",
                                path=f"{path}.handoff_ref",
                            )
                        )
                    if bound.get("status") in {"revoked", "rejected"} or (
                        isinstance(handoff_ref, str)
                        and ("handoff", handoff_ref) in effective_revocations
                    ):
                        diagnostics.append(
                            _diagnostic(
                                "AN_RELATION_CONTRADICTORY",
                                "hands_off_to relations cannot assert a revoked or "
                                "rejected handoff.",
                                path=f"{path}.handoff_ref",
                            )
                        )
        elif relation_type == "revokes":
            expected = revocation_target_by_id.get(str(source.get("ref")))
            target_kind = REVOCATION_KIND_BY_ENDPOINT.get(str(target.get("kind")))
            if expected is not None and (
                target_kind is None
                or expected[0] != target_kind
                or (len(expected) > 1 and expected[1] != target.get("ref"))
            ):
                diagnostics.append(
                    _diagnostic(
                        "AN_RELATION_REFERENCE_INCONSISTENT",
                        "revokes relations must match the revocation record target.",
                        path=f"{path}.target",
                    )
                )
        elif relation_type == "requires_approval_from":
            role = target.get("ref")
            if isinstance(role, str) and role not in module_roles:
                diagnostics.append(
                    _diagnostic(
                        "AN_RELATION_APPROVER_NOT_HUMAN",
                        "requires_approval_from must target a declared human "
                        "approval role.",
                        path=f"{path}.target.ref",
                    )
                )
        elif relation_type == "advertises_capability":
            source_kind = source.get("kind")
            source_ref = str(source.get("ref"))
            capability_ref = str(target.get("ref"))
            holder = (
                identity_by_id.get(source_ref)
                if source_kind == "agent_identity"
                else protocol_by_id.get(source_ref)
            )
            if holder is not None and capability_ref not in _strings(
                holder.get("capability_refs")
            ):
                diagnostics.append(
                    _diagnostic(
                        "AN_RELATION_UNDECLARED_AUTHORITY",
                        "advertises_capability requires the source to hold the "
                        "capability.",
                        path=f"{path}.target.ref",
                    )
                )
        elif relation_type == "crosses_trust_zone":
            source_kind = source.get("kind")
            source_ref = source.get("ref")
            target_zone = str(target.get("ref"))
            allowed = False
            if source_kind == "agent_identity":
                for membership in memberships:
                    if membership.get("identity_ref") != source_ref:
                        continue
                    zone = zone_by_id.get(str(membership.get("trust_zone_ref")))
                    if zone is not None and target_zone in _strings(
                        zone.get("allowed_transition_targets")
                    ):
                        allowed = True
            elif source_kind == "membership":
                membership = next(
                    (
                        item
                        for item in memberships
                        if item.get("id") == source_ref
                    ),
                    None,
                )
                zone = (
                    zone_by_id.get(str(membership.get("trust_zone_ref")))
                    if membership is not None
                    else None
                )
                allowed = zone is not None and target_zone in _strings(
                    zone.get("allowed_transition_targets")
                )
            elif source_kind == "protocol_target":
                protocol = protocol_by_id.get(str(source_ref))
                zone = (
                    zone_by_id.get(str(protocol.get("source_zone_ref")))
                    if protocol is not None
                    else None
                )
                allowed = zone is not None and target_zone in _strings(
                    zone.get("allowed_transition_targets")
                )
            if endpoints_known and not allowed:
                diagnostics.append(
                    _diagnostic(
                        "AN_RELATION_UNDECLARED_AUTHORITY",
                        "crosses_trust_zone requires a declared allowed transition.",
                        path=f"{path}.target.ref",
                    )
                )
        elif relation_type == "shares_with":
            categories = set(_strings(relation.get("share_categories")))
            sensitive = categories & SENSITIVE_CATEGORIES
            if sensitive:
                diagnostics.append(
                    _diagnostic(
                        "AN_RELATION_SENSITIVE_SHARING",
                        "shares_with relations must not carry sensitive "
                        "categories: " + ", ".join(sorted(sensitive)) + ".",
                        path=f"{path}.share_categories",
                    )
                )
            for endpoint_name, endpoint in (("source", source), ("target", target)):
                allowlist = _zone_allowlists(endpoint)
                if allowlist is None:
                    continue
                uncovered = sorted(categories - SENSITIVE_CATEGORIES - allowlist)
                if uncovered:
                    diagnostics.append(
                        _diagnostic(
                            "AN_RELATION_SHARE_NOT_ALLOWED",
                            f"Relation {endpoint_name} does not allow shared "
                            "categories: " + ", ".join(uncovered) + ".",
                            path=f"{path}.share_categories",
                        )
                    )
        elif relation_type == "communicates_with":
            protocol_ref = relation.get("protocol_target_ref")
            if protocol_ref is not None:
                protocol = protocol_by_id.get(str(protocol_ref))
                if protocol is None:
                    diagnostics.append(
                        _diagnostic(
                            "AN_RELATION_PROTOCOL_UNKNOWN",
                            f"Unknown protocol target {protocol_ref!r}.",
                            path=f"{path}.protocol_target_ref",
                        )
                    )
                elif source.get("ref") not in _strings(
                    protocol.get("identity_refs")
                ):
                    diagnostics.append(
                        _diagnostic(
                            "AN_RELATION_REFERENCE_INCONSISTENT",
                            "communicates_with source must appear in the bound "
                            "protocol target identities.",
                            path=f"{path}.protocol_target_ref",
                        )
                    )

    if needs_delegate_approval:
        _approval_action_coverage(document, action="delegate", diagnostics=diagnostics)
    if needs_handoff_approval:
        _approval_action_coverage(document, action="handoff", diagnostics=diagnostics)

    return tuple(
        sorted(
            diagnostics,
            key=lambda item: (item.code, item.path or "", item.message),
        )
    )
