"""AN-002 tests: static delegation, handoff, and network-relation governance."""

from __future__ import annotations

import builtins
from copy import deepcopy
import os
from pathlib import Path
import socket
import subprocess
from typing import Any, Callable

import pytest
import yaml

from nornyx.governance import GovernanceRegistry, compose_governance
from nornyx.governance.runtime import evaluate_document_governance


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "agentic_network.nyx"
AS_OF = "2026-07-17T00:00:00Z"
REGISTRY = GovernanceRegistry.builtins()

VALID_FROM = "2026-01-01T00:00:00Z"
EXPIRES_AT = "2026-08-01T00:00:00Z"


def _base_delegation() -> dict[str, Any]:
    return {
        "id": "delegation.research",
        "delegator_ref": "identity.researcher.local",
        "delegate_ref": "identity.reviewer.local",
        "capability_ref": "propose_research_finding",
        "purpose": "Bounded review-cycle finding proposals",
        "actions": ["propose_finding"],
        "scope_refs": ["GovernedNetworkContext"],
        "status": "active",
        "valid_from": VALID_FROM,
        "expires_at": EXPIRES_AT,
        "max_depth": 2,
        "current_depth": 0,
        "onward_delegation": "allowed_with_policy",
        "source_zone_ref": "zone.local_governed",
        "target_zone_ref": "zone.local_governed",
        "required_gate_refs": [],
        "required_policy_refs": [],
        "required_approval_refs": [],
        "required_evidence_refs": [],
        "revocation_refs": [],
    }


def _base_handoff() -> dict[str, Any]:
    return {
        "id": "handoff.review",
        "from_identity_ref": "identity.researcher.local",
        "to_identity_ref": "identity.reviewer.local",
        "purpose": "Transfer finding-review responsibility",
        "mission_ref": "GOAL-001",
        "from_zone_ref": "zone.local_governed",
        "to_zone_ref": "zone.local_governed",
        "required_capability_refs": ["read_governed_context"],
        "delegation_refs": [],
        "shared_context": ["finding_summary"],
        "never_share": ["secrets", "credentials", "tokens", "private_memory"],
        "status": "initiated",
        "valid_from": VALID_FROM,
        "expires_at": EXPIRES_AT,
        "required_gate_refs": [],
        "required_approval_refs": [],
        "required_evidence_refs": [],
        "revocation_refs": [],
    }


def _base_relation() -> dict[str, Any]:
    return {
        "id": "relation.delegation",
        "type": "delegates_to",
        "source": {"kind": "agent_identity", "ref": "identity.researcher.local"},
        "target": {"kind": "agent_identity", "ref": "identity.reviewer.local"},
        "delegation_ref": "delegation.research",
    }


def _document() -> dict[str, Any]:
    document = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    capability = document["capabilities"][1]
    assert capability["name"] == "propose_research_finding"
    capability["delegable"] = True
    capability["max_delegation_depth"] = 2
    network = document["agentic_network"]
    network["delegations"] = [_base_delegation()]
    network["handoffs"] = [_base_handoff()]
    network["relations"] = [_base_relation()]
    return document


def _diagnostics(document: dict[str, Any]) -> tuple[Any, ...]:
    return evaluate_document_governance(
        document,
        registry=REGISTRY,
        as_of=AS_OF,
        document_root=EXAMPLE.parent,
    )


def _codes(document: dict[str, Any]) -> set[str]:
    return {item.code for item in _diagnostics(document)}


def _pairs(document: dict[str, Any]) -> set[tuple[str, str | None]]:
    return {(item.code, item.path) for item in _diagnostics(document)}


def _add_external_membership(document: dict[str, Any], identity: str) -> None:
    document["agentic_network"]["memberships"].append(
        {
            "id": f"membership.external.{identity.rsplit('.', 2)[-2]}",
            "identity_ref": identity,
            "trust_zone_ref": "zone.external_contract",
            "capability_refs": [],
            "status": "authorized",
            "valid_from": VALID_FROM,
            "expires_at": EXPIRES_AT,
            "revocation_refs": [],
        }
    )


def _revocation(target: dict[str, Any], *, effective: str = "2026-07-01T00:00:00Z") -> dict[str, Any]:
    return {
        "id": "revocation.delegation-test",
        "target": target,
        "effective_at": effective,
        "reason": "test revocation",
        "required_approval_refs": [],
        "required_evidence_refs": [],
    }


def test_valid_delegation_handoff_and_relations_pass() -> None:
    assert _diagnostics(_document()) == ()


def test_delegation_records_are_deterministic_across_input_permutations() -> None:
    document = _document()
    first = [
        (item.code, item.path, item.message) for item in _diagnostics(document)
    ]
    reordered = _document()
    network = reordered["agentic_network"]
    network["delegations"] = list(reversed(network["delegations"]))
    for key in ("trust_zones", "memberships", "network_gates"):
        network[key] = list(reversed(network[key]))
    second = [
        (item.code, item.path, item.message) for item in _diagnostics(reordered)
    ]
    assert first == second == []


def test_valid_multi_hop_bounded_delegation() -> None:
    document = _document()
    escalation_identity = deepcopy(document["agent_identities"][1])
    escalation_identity.update(
        {
            "id": "identity.escalation.local",
            "namespace": "local.escalation",
            "subject": "escalation",
            "framework_bindings": [
                {"framework": "contract_fixture", "agent_key": "escalation"}
            ],
            "capability_refs": ["read_governed_context"],
        }
    )
    document["agent_identities"].append(escalation_identity)
    document["agentic_network"]["memberships"].append(
        {
            "id": "membership.escalation",
            "identity_ref": "identity.escalation.local",
            "trust_zone_ref": "zone.local_governed",
            "capability_refs": ["read_governed_context"],
            "status": "authorized",
            "valid_from": VALID_FROM,
            "expires_at": EXPIRES_AT,
            "revocation_refs": [],
        }
    )
    onward = _base_delegation()
    onward.update(
        {
            "id": "delegation.onward",
            "delegator_ref": "identity.reviewer.local",
            "delegate_ref": "identity.escalation.local",
            "parent_delegation_ref": "delegation.research",
            "current_depth": 1,
            "onward_delegation": "denied",
        }
    )
    document["agentic_network"]["delegations"].append(onward)

    # The chained delegator holds the capability only through the delegation,
    # so identity-level possession is not re-asserted for chained hops? It is:
    # chains still require declared possession; grant it explicitly.
    document["agent_identities"][1]["capability_refs"].append(
        "propose_research_finding"
    )
    document["agentic_network"]["memberships"][1]["capability_refs"].append(
        "propose_research_finding"
    )
    assert _diagnostics(document) == ()


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda doc: doc["agentic_network"]["delegations"].append(
                _base_delegation()
            ),
            "AN_DELEGATION_DUPLICATE",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"delegator_ref": "identity.missing"}
            ),
            "AN_DELEGATOR_UNKNOWN",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"delegate_ref": "identity.missing"}
            ),
            "AN_DELEGATE_UNKNOWN",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"capability_ref": "missing_capability"}
            ),
            "AN_CAPABILITY_UNKNOWN",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"capability_ref": "read_governed_context", "actions": ["read_context"]}
            ),
            "AN_CAPABILITY_NOT_DELEGABLE",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"delegate_ref": "identity.researcher.local"}
            ),
            "AN_SELF_DELEGATION",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"scope_refs": ["GovernedNetworkContext", "OtherScope"]}
            ),
            "AN_DELEGATION_SCOPE_ESCALATION",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"actions": ["external_share"]}
            ),
            "AN_DELEGATION_ACTION_ESCALATION",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"max_depth": 3}
            ),
            "AN_DELEGATION_DEPTH_POLICY_EXCEEDED",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"current_depth": 2}
            ),
            "AN_DELEGATION_DEPTH_EXCEEDED",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"current_depth": 1}
            ),
            "AN_DELEGATION_DEPTH_INVALID",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"parent_delegation_ref": "delegation.missing", "current_depth": 1}
            ),
            "AN_DELEGATION_PARENT_UNKNOWN",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"valid_from": EXPIRES_AT, "expires_at": VALID_FROM}
            ),
            "AN_AUTHORIZATION_INTERVAL_INVALID",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"expires_at": "2026-07-01T00:00:00Z"}
            ),
            "AN_AUTHORIZATION_EXPIRED",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"scope_refs": ["GovernedNetworkContext", "secrets"]}
            ),
            "AN_DELEGATION_SENSITIVE_SHARING",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"required_gate_refs": ["gate.missing"]}
            ),
            "AN_GATE_UNKNOWN",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"required_approval_refs": ["approval.missing"]}
            ),
            "AN_APPROVAL_UNKNOWN",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"required_evidence_refs": ["evidence.missing"]}
            ),
            "AN_EVIDENCE_UNKNOWN",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"required_policy_refs": ["PolicyMissing"]}
            ),
            "AN_POLICY_UNKNOWN",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"revocation_refs": ["revocation.missing"]}
            ),
            "AN_REVOCATION_UNKNOWN",
        ),
        (
            lambda doc: doc["agentic_network"]["delegations"][0].update(
                {"source_zone_ref": "zone.missing"}
            ),
            "AN_TRUST_ZONE_UNKNOWN",
        ),
    ],
)
def test_delegation_negative_matrix(
    mutate: Callable[[dict[str, Any]], Any], expected: str
) -> None:
    document = _document()
    mutate(document)
    assert expected in _codes(document)


def test_delegator_without_capability_or_membership_fails() -> None:
    document = _document()
    document["agentic_network"]["delegations"][0].update(
        {
            "delegator_ref": "identity.reviewer.local",
            "delegate_ref": "identity.researcher.local",
        }
    )
    assert "AN_DELEGATOR_CAPABILITY_MISSING" in _codes(document)

    document = _document()
    document["agentic_network"]["memberships"][0]["capability_refs"] = [
        "read_governed_context"
    ]
    assert "AN_DELEGATOR_MEMBERSHIP_REQUIRED" in _codes(document)


def test_delegate_requires_target_zone_membership() -> None:
    document = _document()
    document["agentic_network"]["delegations"][0]["target_zone_ref"] = (
        "zone.external_contract"
    )
    assert "AN_DELEGATE_NOT_ELIGIBLE" in _codes(document)


def test_onward_delegation_denied_and_chain_consistency() -> None:
    document = _document()
    document["agentic_network"]["delegations"][0]["onward_delegation"] = "denied"
    onward = _base_delegation()
    onward.update(
        {
            "id": "delegation.onward",
            "delegator_ref": "identity.reviewer.local",
            "delegate_ref": "identity.researcher.local",
            "parent_delegation_ref": "delegation.research",
            "current_depth": 1,
        }
    )
    document["agentic_network"]["delegations"].append(onward)
    codes = _codes(document)
    assert "AN_ONWARD_DELEGATION_DENIED" in codes

    document = _document()
    onward = _base_delegation()
    onward.update(
        {
            "id": "delegation.onward",
            "parent_delegation_ref": "delegation.research",
            "current_depth": 1,
        }
    )
    document["agentic_network"]["delegations"].append(onward)
    assert "AN_DELEGATION_CHAIN_BROKEN" in _codes(document)


def test_delegation_chain_cycle_fails_closed() -> None:
    document = _document()
    first = document["agentic_network"]["delegations"][0]
    first["parent_delegation_ref"] = "delegation.cycle"
    first["current_depth"] = 1
    second = _base_delegation()
    second.update(
        {
            "id": "delegation.cycle",
            "delegator_ref": "identity.reviewer.local",
            "delegate_ref": "identity.researcher.local",
            "parent_delegation_ref": "delegation.research",
            "current_depth": 1,
        }
    )
    document["agentic_network"]["delegations"].append(second)
    assert "AN_DELEGATION_CHAIN_CYCLE" in _codes(document)


def test_chained_delegation_interval_must_nest() -> None:
    document = _document()
    document["agent_identities"][1]["capability_refs"].append(
        "propose_research_finding"
    )
    document["agentic_network"]["memberships"][1]["capability_refs"].append(
        "propose_research_finding"
    )
    onward = _base_delegation()
    onward.update(
        {
            "id": "delegation.onward",
            "delegator_ref": "identity.reviewer.local",
            "delegate_ref": "identity.researcher.local",
            "parent_delegation_ref": "delegation.research",
            "current_depth": 1,
            "expires_at": "2026-09-01T00:00:00Z",
        }
    )
    document["agentic_network"]["delegations"].append(onward)
    assert "AN_DELEGATION_INTERVAL_EXCEEDS_PARENT" in _codes(document)


def test_delegation_revocation_timing_controls_effectiveness() -> None:
    document = _document()
    document["agentic_network"]["revocations"] = [
        _revocation({"kind": "delegation", "delegation_ref": "delegation.research"})
    ]
    assert "AN_DELEGATION_REVOKED" in _codes(document)

    document = _document()
    document["agentic_network"]["revocations"] = [
        _revocation(
            {"kind": "delegation", "delegation_ref": "delegation.research"},
            effective="2026-07-18T00:00:00Z",
        )
    ]
    assert "AN_DELEGATION_REVOKED" not in _codes(document)


def test_revoked_delegator_and_delegate_fail() -> None:
    document = _document()
    document["agentic_network"]["revocations"] = [
        _revocation(
            {"kind": "agent_identity", "identity_ref": "identity.researcher.local"}
        )
    ]
    assert "AN_DELEGATOR_REVOKED" in _codes(document)

    document = _document()
    document["agentic_network"]["revocations"] = [
        _revocation(
            {"kind": "agent_identity", "identity_ref": "identity.reviewer.local"}
        )
    ]
    assert "AN_DELEGATE_REVOKED" in _codes(document)


def test_revoked_capability_assignment_blocks_delegation() -> None:
    document = _document()
    document["agentic_network"]["revocations"] = [
        _revocation(
            {
                "kind": "capability_assignment",
                "principal_type": "agent_identity",
                "principal_ref": "identity.researcher.local",
                "capability_ref": "propose_research_finding",
            }
        )
    ]
    assert "AN_DELEGATOR_CAPABILITY_REVOKED" in _codes(document)


def test_cross_zone_delegation_requires_gate_approval_and_evidence() -> None:
    document = _document()
    _add_external_membership(document, "identity.reviewer.local")
    delegation = document["agentic_network"]["delegations"][0]
    delegation["target_zone_ref"] = "zone.external_contract"
    codes = _codes(document)
    assert {
        "AN_DELEGATION_GATE_REQUIRED",
        "AN_DELEGATION_APPROVAL_REQUIRED",
        "AN_DELEGATION_EVIDENCE_REQUIRED",
        "AN_APPROVAL_ACTION_MISSING",
    } <= codes


def test_cross_zone_delegation_with_full_controls_passes() -> None:
    document = _document()
    _add_external_membership(document, "identity.reviewer.local")
    document["agentic_network"]["network_gates"].append(
        {
            "id": "gate.delegate_external",
            "action_classes": ["delegate"],
            "source_zone_refs": ["zone.local_governed"],
            "target_zone_refs": ["zone.external_contract"],
            "required_policy_refs": ["AgenticNetworkSafety"],
            "required_approval_refs": ["agentic_network_authority"],
            "required_evidence_refs": ["agentic_network_contract_review"],
        }
    )
    delegation = document["agentic_network"]["delegations"][0]
    delegation.update(
        {
            "target_zone_ref": "zone.external_contract",
            "required_gate_refs": ["gate.delegate_external"],
            "required_approval_refs": ["agentic_network_authority"],
            "required_evidence_refs": ["agentic_network_contract_review"],
        }
    )
    document["approvals"][0]["required_for"].append("delegate")
    assert _diagnostics(document) == ()


def test_high_risk_delegation_requires_human_authority() -> None:
    document = _document()
    document["capabilities"][1]["risk"] = "high"
    codes = _codes(document)
    assert {
        "AN_DELEGATION_APPROVAL_REQUIRED",
        "AN_DELEGATION_EVIDENCE_REQUIRED",
    } <= codes


def test_normalization_collision_is_rejected() -> None:
    document = _document()
    second = _base_delegation()
    second["id"] = "DELEGATION.RESEARCH"
    document["agentic_network"]["delegations"].append(second)
    assert "AN_NORMALIZATION_COLLISION" in _codes(document)


def test_malformed_collections_fail_closed() -> None:
    document = _document()
    document["agentic_network"]["delegations"] = "not-a-list"
    assert "AN_COLLECTION_MALFORMED" in _codes(document)

    document = _document()
    document["agentic_network"]["handoffs"] = [42]
    assert "AN_COLLECTION_MALFORMED" in _codes(document)


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda doc: doc["agentic_network"]["handoffs"].append(_base_handoff()),
            "AN_HANDOFF_DUPLICATE",
        ),
        (
            lambda doc: doc["agentic_network"]["handoffs"][0].update(
                {"from_identity_ref": "identity.missing"}
            ),
            "AN_HANDOFF_SOURCE_UNKNOWN",
        ),
        (
            lambda doc: doc["agentic_network"]["handoffs"][0].update(
                {"to_identity_ref": "identity.missing"}
            ),
            "AN_HANDOFF_TARGET_UNKNOWN",
        ),
        (
            lambda doc: doc["agentic_network"]["handoffs"][0].update(
                {"to_identity_ref": "identity.researcher.local"}
            ),
            "AN_HANDOFF_SELF",
        ),
        (
            lambda doc: doc["agentic_network"]["handoffs"][0].update(
                {"mission_ref": "GOAL-MISSING"}
            ),
            "AN_HANDOFF_MISSION_UNKNOWN",
        ),
        (
            lambda doc: doc["agentic_network"]["handoffs"][0].update(
                {"required_capability_refs": ["propose_research_finding"]}
            ),
            "AN_HANDOFF_AUTHORITY_ESCALATION",
        ),
        (
            lambda doc: doc["agentic_network"]["handoffs"][0].update(
                {"shared_context": ["finding_summary", "tokens"]}
            ),
            "AN_HANDOFF_SENSITIVE_SHARING",
        ),
        (
            lambda doc: doc["agentic_network"]["handoffs"][0].update(
                {"never_share": ["secrets"]}
            ),
            "AN_HANDOFF_SENSITIVE_SHARING",
        ),
        (
            lambda doc: doc["agentic_network"]["handoffs"][0].update(
                {"shared_context": ["undeclared_category"]}
            ),
            "AN_HANDOFF_SHARE_NOT_ALLOWED",
        ),
        (
            lambda doc: doc["agentic_network"]["handoffs"][0].update(
                {"expires_at": "2026-07-01T00:00:00Z"}
            ),
            "AN_AUTHORIZATION_EXPIRED",
        ),
        (
            lambda doc: doc["agentic_network"]["handoffs"][0].update(
                {"superseded_by_ref": "handoff.other"}
            ),
            "AN_HANDOFF_STATUS_CONTRADICTION",
        ),
        (
            lambda doc: doc["agentic_network"]["handoffs"][0].update(
                {"status": "superseded", "superseded_by_ref": "handoff.missing"}
            ),
            "AN_HANDOFF_SUPERSEDED_REF_INVALID",
        ),
        (
            lambda doc: doc["agentic_network"]["handoffs"][0].update(
                {"delegation_refs": ["delegation.missing"]}
            ),
            "AN_HANDOFF_DELEGATION_UNKNOWN",
        ),
    ],
)
def test_handoff_negative_matrix(
    mutate: Callable[[dict[str, Any]], Any], expected: str
) -> None:
    document = _document()
    mutate(document)
    assert expected in _codes(document)


def test_handoff_transfers_responsibility_via_valid_delegation() -> None:
    document = _document()
    handoff = document["agentic_network"]["handoffs"][0]
    handoff["required_capability_refs"] = ["propose_research_finding"]
    handoff["delegation_refs"] = ["delegation.research"]
    assert _diagnostics(document) == ()


def test_handoff_delegation_mismatch_cannot_bypass_restrictions() -> None:
    document = _document()
    delegation = document["agentic_network"]["delegations"][0]
    delegation["delegate_ref"] = "identity.researcher.local"
    delegation["delegator_ref"] = "identity.reviewer.local"
    handoff = document["agentic_network"]["handoffs"][0]
    handoff["required_capability_refs"] = ["propose_research_finding"]
    handoff["delegation_refs"] = ["delegation.research"]
    codes = _codes(document)
    assert "AN_HANDOFF_DELEGATION_MISMATCH" in codes
    assert "AN_HANDOFF_AUTHORITY_ESCALATION" in codes


def test_handoff_expired_delegation_does_not_supply_capability() -> None:
    document = _document()
    delegation = document["agentic_network"]["delegations"][0]
    delegation["expires_at"] = "2026-07-01T00:00:00Z"
    handoff = document["agentic_network"]["handoffs"][0]
    handoff["required_capability_refs"] = ["propose_research_finding"]
    handoff["delegation_refs"] = ["delegation.research"]
    assert "AN_HANDOFF_AUTHORITY_ESCALATION" in _codes(document)


def test_revoked_handoff_cannot_stay_active() -> None:
    document = _document()
    document["agentic_network"]["revocations"] = [
        _revocation({"kind": "handoff", "handoff_ref": "handoff.review"})
    ]
    assert "AN_HANDOFF_REVOKED" in _codes(document)


def test_cross_zone_handoff_requires_controls() -> None:
    document = _document()
    _add_external_membership(document, "identity.reviewer.local")
    handoff = document["agentic_network"]["handoffs"][0]
    handoff["to_zone_ref"] = "zone.external_contract"
    codes = _codes(document)
    assert {
        "AN_HANDOFF_GATE_REQUIRED",
        "AN_HANDOFF_APPROVAL_REQUIRED",
        "AN_HANDOFF_EVIDENCE_REQUIRED",
        "AN_APPROVAL_ACTION_MISSING",
    } <= codes


def test_handoff_source_membership_is_required() -> None:
    document = _document()
    document["agentic_network"]["memberships"][0]["status"] = "suspended"
    codes = _codes(document)
    assert "AN_HANDOFF_MEMBERSHIP_REQUIRED" in codes


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda doc: doc["agentic_network"]["relations"].append(_base_relation()),
            "AN_RELATION_DUPLICATE",
        ),
        (
            lambda doc: doc["agentic_network"]["relations"][0]["source"].update(
                {"ref": "identity.missing"}
            ),
            "AN_RELATION_SOURCE_UNKNOWN",
        ),
        (
            lambda doc: doc["agentic_network"]["relations"][0]["target"].update(
                {"ref": "identity.missing"}
            ),
            "AN_RELATION_TARGET_UNKNOWN",
        ),
        (
            lambda doc: doc["agentic_network"]["relations"][0]["source"].update(
                {"kind": "trust_zone", "ref": "zone.local_governed"}
            ),
            "AN_RELATION_ENDPOINT_KIND_INVALID",
        ),
        (
            lambda doc: doc["agentic_network"]["relations"][0].pop("delegation_ref"),
            "AN_RELATION_DELEGATION_REF_REQUIRED",
        ),
        (
            lambda doc: doc["agentic_network"]["relations"][0].update(
                {"delegation_ref": "delegation.missing"}
            ),
            "AN_RELATION_DELEGATION_UNKNOWN",
        ),
        (
            lambda doc: doc["agentic_network"]["relations"][0].update(
                {
                    "source": {
                        "kind": "agent_identity",
                        "ref": "identity.reviewer.local",
                    },
                    "target": {
                        "kind": "agent_identity",
                        "ref": "identity.researcher.local",
                    },
                }
            ),
            "AN_RELATION_REFERENCE_INCONSISTENT",
        ),
    ],
)
def test_relation_negative_matrix(
    mutate: Callable[[dict[str, Any]], Any], expected: str
) -> None:
    document = _document()
    mutate(document)
    assert expected in _codes(document)


def test_relation_self_reference_is_rejected() -> None:
    document = _document()
    document["agentic_network"]["relations"] = [
        {
            "id": "relation.self",
            "type": "communicates_with",
            "source": {"kind": "agent_identity", "ref": "identity.researcher.local"},
            "target": {"kind": "agent_identity", "ref": "identity.researcher.local"},
        }
    ]
    assert "AN_RELATION_SELF_REFERENCE" in _codes(document)


def test_relation_cannot_assert_revoked_delegation() -> None:
    document = _document()
    document["agentic_network"]["revocations"] = [
        _revocation({"kind": "delegation", "delegation_ref": "delegation.research"})
    ]
    codes = _codes(document)
    assert "AN_RELATION_CONTRADICTORY" in codes


def test_relation_requires_approval_from_human_role_only() -> None:
    document = _document()
    document["agentic_network"]["relations"] = [
        {
            "id": "relation.approval",
            "type": "requires_approval_from",
            "source": {"kind": "capability", "ref": "propose_research_finding"},
            "target": {"kind": "human_role", "ref": "network_governance_owner"},
        }
    ]
    assert _diagnostics(document) == ()

    document["agentic_network"]["relations"][0]["target"]["ref"] = "unknown_role"
    assert "AN_RELATION_TARGET_UNKNOWN" in _codes(document)


def test_relation_advertise_requires_declared_capability() -> None:
    document = _document()
    document["agentic_network"]["relations"] = [
        {
            "id": "relation.advertise",
            "type": "advertises_capability",
            "source": {"kind": "agent_identity", "ref": "identity.reviewer.local"},
            "target": {"kind": "capability", "ref": "propose_research_finding"},
        }
    ]
    assert "AN_RELATION_UNDECLARED_AUTHORITY" in _codes(document)


def test_relation_zone_crossing_requires_declared_transition() -> None:
    document = _document()
    document["agentic_network"]["relations"] = [
        {
            "id": "relation.cross",
            "type": "crosses_trust_zone",
            "source": {"kind": "agent_identity", "ref": "identity.researcher.local"},
            "target": {"kind": "trust_zone", "ref": "zone.external_contract"},
        }
    ]
    assert _diagnostics(document) == ()

    reversed_direction = _document()
    reversed_direction["agentic_network"]["relations"] = [
        {
            "id": "relation.cross",
            "type": "crosses_trust_zone",
            "source": {
                "kind": "membership",
                "ref": "membership.reviewer",
            },
            "target": {"kind": "trust_zone", "ref": "zone.local_governed"},
        }
    ]
    codes = _codes(reversed_direction)
    assert {"AN_RELATION_UNDECLARED_AUTHORITY", "AN_RELATION_SELF_REFERENCE"} & codes


def test_relation_sensitive_sharing_is_rejected() -> None:
    document = _document()
    document["agentic_network"]["relations"] = [
        {
            "id": "relation.share",
            "type": "shares_with",
            "source": {"kind": "trust_zone", "ref": "zone.local_governed"},
            "target": {"kind": "trust_zone", "ref": "zone.external_contract"},
            "share_categories": ["private_memory"],
        }
    ]
    assert "AN_RELATION_SENSITIVE_SHARING" in _codes(document)

    document["agentic_network"]["relations"][0]["share_categories"] = [
        "unlisted_category"
    ]
    assert "AN_RELATION_SHARE_NOT_ALLOWED" in _codes(document)


def test_relation_binding_field_misuse_is_rejected() -> None:
    document = _document()
    document["agentic_network"]["relations"] = [
        {
            "id": "relation.misuse",
            "type": "shares_with",
            "source": {"kind": "trust_zone", "ref": "zone.local_governed"},
            "target": {"kind": "trust_zone", "ref": "zone.external_contract"},
            "delegation_ref": "delegation.research",
        }
    ]
    assert "AN_RELATION_REFERENCE_INCONSISTENT" in _codes(document)


def test_existing_profiles_see_no_delegation_regression() -> None:
    for profile in ("minimal", "standard", "ai_coding", "regulated"):
        composition = compose_governance(REGISTRY, profile_identity=profile)
        assert "agentic_network_delegation.v1" not in (
            composition.structural_checks or ()
        )


def test_delegation_validation_uses_no_network_or_processes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("delegation validation attempted an external operation")

    original_import = builtins.__import__

    def guarded_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.split(".", 1)[0] in {"crewai", "langgraph"}:
            raise AssertionError("delegation validation constructed a framework")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)

    assert _diagnostics(_document()) == ()
