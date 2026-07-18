from __future__ import annotations

import builtins
from copy import deepcopy
from dataclasses import replace
import hashlib
from importlib import resources
import json
import os
from pathlib import Path
import socket
import subprocess
from typing import Any, Callable

import pytest
import yaml
from jsonschema import Draft202012Validator

from nornyx.governance import (
    GovernanceBlockSchema,
    GovernanceError,
    GovernanceRegistry,
    LockEntry,
    ProfileLock,
    compose_governance,
    lock_for_packs,
)
from nornyx.governance.loader import load_local_pack, load_pack_bytes
from nornyx.governance.runtime import evaluate_document_governance
from nornyx.governance.schemas import canonical_pack_hash
from nornyx.profiles import PROFILE_NAMES, profile_document

from symlink_support import create_symlink_or_skip


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "agentic_network.nyx"
AS_OF = "2026-07-17T00:00:00Z"
REGISTRY = GovernanceRegistry.builtins()


def _document() -> dict[str, Any]:
    return yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))


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


def _error_codes(error: GovernanceError) -> set[str]:
    return {item.code for item in error.diagnostics}


def test_agentic_network_profile_module_and_example_are_bounded_and_valid() -> None:
    registry = GovernanceRegistry.builtins()
    profile = registry.resolve_profile("agentic_network")
    module = registry.resolve_module("agentic_network_governance")
    composition = compose_governance(registry, profile_identity=profile.name)

    assert PROFILE_NAMES[-1] == "agentic_network"
    assert len(registry.profile_names) == 13
    assert len(registry.module_names) == 7
    assert profile.version == module.version == "0.1.0"
    assert profile.required_modules == (module.id,)
    assert module.dependencies == ("nornyx.builtin.module.human_approval",)
    assert [item.name for item in composition.modules] == [
        "evidence_integrity",
        "human_approval",
        "agentic_network_governance",
    ]
    assert composition.structural_checks == (
        "agentic_network_foundation.v1",
        "evidence_integrity.v1",
        "human_approval.v1",
    )
    assert _diagnostics(_document()) == ()


def test_agentic_network_starter_is_deterministic_static_and_fail_closed() -> None:
    first = profile_document("agentic_network", "AgenticNetworkDemo")
    second = profile_document("agentic_network", "AgenticNetworkDemo")

    assert first == second
    assert first["project"]["profile"] == "agentic_network"
    assert len(first["agent_identities"]) == 2
    assert len(first["capabilities"]) == 2
    assert first["agentic_network"]["protocol_targets"][0]["execution_mode"] == "contract_only"
    assert first["agentic_network"]["protocol_targets"][0]["live_connector_execution"] is False
    assert not {
        "endpoint",
        "command",
        "credential",
        "token",
        "runtime",
    } & set(first["agentic_network"]["protocol_targets"][0])
    codes = _codes(first)
    assert "EVIDENCE_REQUIRED_MISSING" in codes
    assert "GOVERNANCE_BLOCK_SCHEMA_INVALID" not in codes


def _duplicate_identity(document: dict[str, Any]) -> None:
    document["agent_identities"].append(deepcopy(document["agent_identities"][0]))


def _duplicate_subject(document: dict[str, Any]) -> None:
    document["agent_identities"][1]["namespace"] = "local.research"
    document["agent_identities"][1]["subject"] = "researcher"


def _duplicate_binding(document: dict[str, Any]) -> None:
    document["agent_identities"][1]["framework_bindings"] = [
        {"framework": "contract_fixture", "agent_key": "researcher"}
    ]


def _unknown_role(document: dict[str, Any]) -> None:
    document["agent_identities"][0]["role_ref"] = "MissingRole"


def _unknown_capability(document: dict[str, Any]) -> None:
    document["agent_identities"][0]["capability_refs"].append("missing_capability")


def _unknown_identity(document: dict[str, Any]) -> None:
    document["agentic_network"]["memberships"][0]["identity_ref"] = "identity.missing"


def _unknown_zone(document: dict[str, Any]) -> None:
    document["agentic_network"]["memberships"][0]["trust_zone_ref"] = "zone.missing"


def _unknown_gate(document: dict[str, Any]) -> None:
    document["capabilities"][0]["required_gate_refs"] = ["gate.missing"]


def _unknown_approval(document: dict[str, Any]) -> None:
    document["capabilities"][0]["required_approval_refs"] = ["approval.missing"]


def _unknown_evidence(document: dict[str, Any]) -> None:
    document["capabilities"][0]["required_evidence_refs"] = ["evidence.missing"]


def _unknown_policy(document: dict[str, Any]) -> None:
    document["agentic_network"]["network_gates"][0]["required_policy_refs"] = ["PolicyMissing"]


def _capability_escalation(document: dict[str, Any]) -> None:
    document["agentic_network"]["memberships"][1]["capability_refs"].append(
        "propose_research_finding"
    )


def _invalid_interval(document: dict[str, Any]) -> None:
    document["agent_identities"][0]["valid_from"] = "2099-01-01T00:00:00Z"


def _expired_membership(document: dict[str, Any]) -> None:
    document["agentic_network"]["memberships"][0]["expires_at"] = "2026-07-01T00:00:00Z"


def _high_risk_without_gate(document: dict[str, Any]) -> None:
    document["capabilities"][0]["risk"] = "high"
    document["capabilities"][0]["required_gate_refs"] = []


def _sensitive_external_share(document: dict[str, Any]) -> None:
    document["agentic_network"]["protocol_targets"][0]["share"].append("tokens")


Mutation = Callable[[dict[str, Any]], None]


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (_duplicate_identity, "AN_IDENTITY_DUPLICATE"),
        (_duplicate_subject, "AN_IDENTITY_SUBJECT_DUPLICATE"),
        (_duplicate_binding, "AN_IDENTITY_BINDING_DUPLICATE"),
        (_unknown_role, "AN_IDENTITY_ROLE_UNKNOWN"),
        (_unknown_capability, "AN_CAPABILITY_UNKNOWN"),
        (_unknown_identity, "AN_IDENTITY_UNKNOWN"),
        (_unknown_zone, "AN_TRUST_ZONE_UNKNOWN"),
        (_unknown_gate, "AN_GATE_UNKNOWN"),
        (_unknown_approval, "AN_APPROVAL_UNKNOWN"),
        (_unknown_evidence, "AN_EVIDENCE_UNKNOWN"),
        (_unknown_policy, "AN_POLICY_UNKNOWN"),
        (_capability_escalation, "AN_CAPABILITY_ESCALATION"),
        (_invalid_interval, "AN_AUTHORIZATION_INTERVAL_INVALID"),
        (_expired_membership, "AN_AUTHORIZATION_EXPIRED"),
        (_high_risk_without_gate, "AN_GATE_REQUIRED"),
        (_sensitive_external_share, "AN_SENSITIVE_SHARE_BOUNDARY_MISSING"),
    ],
)
def test_agentic_network_relationships_fail_closed(
    mutation: Mutation,
    expected: str,
) -> None:
    document = _document()
    mutation(document)

    assert expected in _codes(document)


@pytest.mark.parametrize("field", ["endpoint", "command", "credential", "token"])
def test_protocol_target_rejects_runtime_and_secret_material(field: str) -> None:
    document = _document()
    document["agentic_network"]["protocol_targets"][0][field] = "forbidden"

    assert "GOVERNANCE_BLOCK_SCHEMA_INVALID" in _codes(document)


def test_effective_revocations_fail_closed() -> None:
    document = _document()
    document["agentic_network"]["revocations"] = [
        {
            "id": "revocation.researcher",
            "target": {
                "kind": "agent_identity",
                "identity_ref": "identity.researcher.local",
            },
            "effective_at": "2026-07-01T00:00:00Z",
            "reason": "authorization withdrawn",
            "required_approval_refs": ["agentic_network_authority"],
            "required_evidence_refs": ["agentic_network_contract_review"],
        }
    ]
    document["agent_identities"][0]["revocation_refs"] = ["revocation.researcher"]

    assert "AN_AUTHORIZATION_REVOKED" in _codes(document)


def test_schema_mirrors_are_byte_identical_and_closed() -> None:
    for name in (
        "agentic_network_v1.schema.json",
        "agent_identities_v1.schema.json",
        "agentic_capabilities_v1.schema.json",
    ):
        root = (ROOT / "schemas" / name).read_bytes()
        bundled = (ROOT / "nornyx" / "schemas" / name).read_bytes()
        assert root == bundled
        schema = json.loads(root)
        closed_schema = schema if schema.get("type") == "object" else schema["items"]
        if "$ref" in closed_schema:
            closed_schema = schema["$defs"][closed_schema["$ref"].rsplit("/", 1)[-1]]
        assert closed_schema["additionalProperties"] is False
        Draft202012Validator(schema).validate(_document()[schema["x-nornyx-governance-block"]])


def test_unknown_revocation_target_fails_closed() -> None:
    document = _document()
    document["agentic_network"]["revocations"] = [
        {
            "id": "revocation.missing",
            "target": {
                "kind": "membership",
                "membership_ref": "membership.missing",
            },
            "effective_at": "2026-07-01T00:00:00Z",
            "reason": "test missing target",
            "required_approval_refs": ["agentic_network_authority"],
            "required_evidence_refs": ["agentic_network_contract_review"],
        }
    ]

    assert "AN_REVOCATION_TARGET_UNKNOWN" in _codes(document)


def test_expired_active_identity_fails_closed() -> None:
    document = _document()
    document["agent_identities"][0]["expires_at"] = "2026-07-01T00:00:00Z"

    assert "AN_AUTHORIZATION_EXPIRED" in _codes(document)


def test_effective_membership_revocation_fails_closed() -> None:
    document = _document()
    document["agentic_network"]["revocations"] = [
        {
            "id": "revocation.membership",
            "target": {
                "kind": "membership",
                "membership_ref": "membership.researcher",
            },
            "effective_at": "2026-07-01T00:00:00Z",
            "reason": "authorization withdrawn",
            "required_approval_refs": ["agentic_network_authority"],
            "required_evidence_refs": ["agentic_network_contract_review"],
        }
    ]
    document["agentic_network"]["memberships"][0]["revocation_refs"] = ["revocation.membership"]

    assert "AN_AUTHORIZATION_REVOKED" in _codes(document)


def _revocation(identifier: str, target: dict[str, str]) -> dict[str, Any]:
    return {
        "id": identifier,
        "target": target,
        "effective_at": "2026-07-16T00:00:00Z",
        "reason": "authorization withdrawn",
        "required_approval_refs": ["agentic_network_authority"],
        "required_evidence_refs": ["agentic_network_contract_review"],
    }


@pytest.mark.parametrize(
    ("record_index", "expected_path"),
    [
        (1, "governance_evidence.records[1].subject_revision"),
        (2, "governance_evidence.records[2].subject_revision"),
    ],
)
def test_agentic_evidence_revision_mismatch_fails_closed(
    record_index: int,
    expected_path: str,
) -> None:
    document = _document()
    document["governance_evidence"]["records"][record_index]["subject_revision"] = "git:different"

    assert ("AN_REVISION_MISMATCH", expected_path) in _pairs(document)


def test_network_evidence_and_approval_revisions_are_one_exact_value() -> None:
    document = _document()
    document["agentic_network"]["subject_revision"] = "git:different"
    pairs = _pairs(document)

    assert (
        "AN_REVISION_MISMATCH",
        "governance_evidence.subject_revision",
    ) in pairs
    assert (
        "AN_REVISION_MISMATCH",
        "approvals[0].revision_binding.revision",
    ) in pairs


def test_approval_binding_revision_mismatch_has_precise_path() -> None:
    document = _document()
    document["approvals"][0]["revision_binding"]["revision"] = "git:different"

    assert (
        "AN_REVISION_MISMATCH",
        "approvals[0].revision_binding.revision",
    ) in _pairs(document)


@pytest.mark.parametrize(
    ("target", "expected_path"),
    [
        ("network", "agentic_network.subject_revision"),
        ("evidence", "governance_evidence.subject_revision"),
        ("contract-review", "governance_evidence.records[1].subject_revision"),
        ("approval-record", "governance_evidence.records[2].subject_revision"),
        ("approval-binding", "approvals[0].revision_binding.revision"),
    ],
)
def test_every_required_revision_fails_closed_when_missing(
    target: str,
    expected_path: str,
) -> None:
    document = _document()
    if target == "network":
        document["agentic_network"].pop("subject_revision")
    elif target == "evidence":
        document["governance_evidence"].pop("subject_revision")
    elif target == "contract-review":
        document["governance_evidence"]["records"][1].pop("subject_revision")
    elif target == "approval-record":
        document["governance_evidence"]["records"][2].pop("subject_revision")
    else:
        document["approvals"][0]["revision_binding"].pop("revision")

    assert ("AN_REVISION_REQUIRED", expected_path) in _pairs(document)


def test_non_exact_approval_revision_is_rejected_as_ambiguous() -> None:
    document = _document()
    document["approvals"][0]["revision_binding"]["exact"] = False

    assert (
        "AN_REVISION_MISMATCH",
        "approvals[0].revision_binding.revision",
    ) in _pairs(document)


@pytest.mark.parametrize("status", ["suspended", "revoked", "expired"])
def test_protocol_rejects_inactive_identity(status: str) -> None:
    document = _document()
    document["agent_identities"][1]["status"] = status

    assert (
        "AN_PROTOCOL_IDENTITY_UNAUTHORIZED",
        "agentic_network.protocol_targets[0].identity_refs",
    ) in _pairs(document)


@pytest.mark.parametrize("status", ["suspended", "revoked", "expired"])
def test_protocol_rejects_inactive_membership(status: str) -> None:
    document = _document()
    document["agentic_network"]["memberships"][1]["status"] = status

    assert (
        "AN_PROTOCOL_MEMBERSHIP_UNAUTHORIZED",
        "agentic_network.protocol_targets[0].source_membership_refs",
    ) in _pairs(document)


def test_protocol_rejects_not_yet_valid_identity_and_expired_membership() -> None:
    document = _document()
    document["agent_identities"][1]["valid_from"] = "2026-07-18T00:00:00Z"
    document["agentic_network"]["memberships"][1]["expires_at"] = "2026-07-17T00:00:00Z"
    pairs = _pairs(document)

    assert (
        "AN_PROTOCOL_IDENTITY_UNAUTHORIZED",
        "agentic_network.protocol_targets[0].identity_refs",
    ) in pairs
    assert (
        "AN_PROTOCOL_MEMBERSHIP_UNAUTHORIZED",
        "agentic_network.protocol_targets[0].source_membership_refs",
    ) in pairs


def test_protocol_capability_requires_identity_and_membership_assignment() -> None:
    document = _document()
    document["agentic_network"]["protocol_targets"][0]["capability_refs"] = [
        "propose_research_finding"
    ]

    assert (
        "AN_PROTOCOL_CAPABILITY_UNAUTHORIZED",
        "agentic_network.protocol_targets[0].capability_refs",
    ) in _pairs(document)


def test_protocol_source_membership_must_match_identity_and_zone() -> None:
    document = _document()
    protocol = document["agentic_network"]["protocol_targets"][0]
    protocol["source_membership_refs"] = ["membership.researcher"]
    pairs = _pairs(document)

    assert (
        "AN_PROTOCOL_MEMBERSHIP_WRONG_IDENTITY",
        "agentic_network.protocol_targets[0].source_membership_refs",
    ) in pairs
    assert (
        "AN_PROTOCOL_MEMBERSHIP_REQUIRED",
        "agentic_network.protocol_targets[0].source_membership_refs",
    ) in pairs


def test_protocol_source_membership_must_match_source_zone() -> None:
    document = _document()
    document["agentic_network"]["memberships"][1]["trust_zone_ref"] = "zone.external_contract"
    pairs = _pairs(document)

    assert (
        "AN_PROTOCOL_MEMBERSHIP_WRONG_ZONE",
        "agentic_network.protocol_targets[0].source_membership_refs",
    ) in pairs
    assert (
        "AN_PROTOCOL_MEMBERSHIP_REQUIRED",
        "agentic_network.protocol_targets[0].source_membership_refs",
    ) in pairs


@pytest.mark.parametrize(
    ("target", "expected_code", "expected_path"),
    [
        (
            {"kind": "agent_identity", "identity_ref": "identity.reviewer.local"},
            "AN_PROTOCOL_IDENTITY_REVOKED",
            "agentic_network.protocol_targets[0].identity_refs",
        ),
        (
            {"kind": "membership", "membership_ref": "membership.reviewer"},
            "AN_PROTOCOL_MEMBERSHIP_REVOKED",
            "agentic_network.protocol_targets[0].source_membership_refs",
        ),
        (
            {
                "kind": "capability_assignment",
                "principal_type": "membership",
                "principal_ref": "membership.reviewer",
                "capability_ref": "read_governed_context",
            },
            "AN_PROTOCOL_CAPABILITY_REVOKED",
            "agentic_network.protocol_targets[0].capability_refs",
        ),
    ],
)
def test_protocol_effective_revocation_precedes_authorization(
    target: dict[str, str],
    expected_code: str,
    expected_path: str,
) -> None:
    document = _document()
    document["agentic_network"]["revocations"] = [_revocation("revocation.protocol-source", target)]

    assert (expected_code, expected_path) in _pairs(document)


def test_protocol_requires_semantically_applicable_gate() -> None:
    document = _document()
    document["agentic_network"]["protocol_targets"][0]["required_gate_refs"] = []
    pairs = _pairs(document)

    assert (
        "AN_PROTOCOL_GATE_REQUIRED",
        "agentic_network.protocol_targets[0].required_gate_refs",
    ) in pairs
    assert (
        "AN_PROTOCOL_GATE_ACTION_MISMATCH",
        "agentic_network.protocol_targets[0].required_gate_refs",
    ) in pairs


def test_wrong_gate_source_target_and_action_fail_closed() -> None:
    document = _document()
    document["agentic_network"]["protocol_targets"][0]["required_gate_refs"] = [
        "gate.reviewed_proposal"
    ]
    pairs = _pairs(document)

    assert (
        "AN_PROTOCOL_GATE_TARGET_MISMATCH",
        "agentic_network.protocol_targets[0].required_gate_refs",
    ) in pairs
    assert (
        "AN_PROTOCOL_GATE_ACTION_MISMATCH",
        "agentic_network.protocol_targets[0].required_gate_refs",
    ) in pairs


def test_referenced_gate_must_cover_protocol_source_zone() -> None:
    document = _document()
    document["agentic_network"]["network_gates"][1]["source_zone_refs"] = ["zone.external_contract"]
    pairs = _pairs(document)

    assert (
        "AN_PROTOCOL_GATE_SOURCE_MISMATCH",
        "agentic_network.protocol_targets[0].required_gate_refs",
    ) in pairs


def test_protocol_requires_allowed_transition_and_zone_gate_bindings() -> None:
    document = _document()
    document["agentic_network"]["trust_zones"][0]["allowed_transition_targets"] = []
    document["agentic_network"]["trust_zones"][0]["egress_gate_refs"] = []
    document["agentic_network"]["trust_zones"][1]["ingress_gate_refs"] = []
    pairs = _pairs(document)

    assert (
        "AN_PROTOCOL_TRANSITION_NOT_ALLOWED",
        "agentic_network.protocol_targets[0].trust_zone_ref",
    ) in pairs
    assert (
        "AN_PROTOCOL_EGRESS_GATE_MISSING",
        "agentic_network.protocol_targets[0].required_gate_refs",
    ) in pairs
    assert (
        "AN_PROTOCOL_INGRESS_GATE_MISSING",
        "agentic_network.protocol_targets[0].required_gate_refs",
    ) in pairs


def test_external_protocol_requires_approval_and_evidence_on_target_and_gate() -> None:
    document = _document()
    protocol = document["agentic_network"]["protocol_targets"][0]
    gate = document["agentic_network"]["network_gates"][1]
    protocol["required_approval_refs"] = []
    protocol["required_evidence_refs"] = []
    gate["required_approval_refs"] = []
    gate["required_evidence_refs"] = []
    codes = _codes(document)

    assert {
        "AN_PROTOCOL_APPROVAL_REQUIRED",
        "AN_PROTOCOL_EVIDENCE_REQUIRED",
        "AN_PROTOCOL_GATE_APPROVAL_MISSING",
        "AN_PROTOCOL_GATE_EVIDENCE_MISSING",
    } <= codes


@pytest.mark.parametrize("producer_type", ["tool", "system", "external_service", "agent"])
def test_approval_record_must_be_human(producer_type: str) -> None:
    document = _document()
    document["governance_evidence"]["records"][2]["producer"]["type"] = producer_type

    assert (
        "AN_APPROVAL_HUMAN_REQUIRED",
        "governance_evidence.records[2].producer.type",
    ) in _pairs(document)


def test_approval_record_role_action_and_presence_fail_closed() -> None:
    document = _document()
    document["governance_evidence"]["records"][2]["producer"]["id"] = "human.developer"
    document["approvals"][0]["required_for"] = ["approve_agentic_network_contract"]
    pairs = _pairs(document)

    assert ("AN_APPROVAL_ROLE_INVALID", "governance_evidence.records[2].producer.id") in pairs
    assert ("AN_APPROVAL_ACTION_MISSING", "approvals[0].required_for") in pairs

    document = _document()
    document["governance_evidence"]["records"].pop(2)
    assert (
        "AN_APPROVAL_RECORD_MISSING",
        "governance_evidence.records",
    ) in _pairs(document)


def test_approval_expiry_is_bounded_and_revocable() -> None:
    document = _document()
    document["governance_evidence"]["records"][2]["expires_at"] = "2026-07-25T00:00:00Z"
    assert (
        "AN_APPROVAL_EXPIRY_EXCESSIVE",
        "governance_evidence.records[2].expires_at",
    ) in _pairs(document)


def test_approval_time_and_status_fail_closed() -> None:
    document = _document()
    approval = document["governance_evidence"]["records"][2]
    approval["generated_at"] = "2026-07-18T00:00:00Z"
    pairs = _pairs(document)
    assert (
        "AN_APPROVAL_NOT_YET_VALID",
        "governance_evidence.records[2].generated_at",
    ) in pairs

    document = _document()
    approval = document["governance_evidence"]["records"][2]
    approval["generated_at"] = "2026-07-09T00:00:00Z"
    approval["expires_at"] = "2026-07-16T00:00:00Z"
    assert (
        "AN_APPROVAL_EXPIRED",
        "governance_evidence.records[2].expires_at",
    ) in _pairs(document)

    document = _document()
    document["governance_evidence"]["records"][2]["status"] = "fail"
    assert (
        "AN_APPROVAL_RECORD_INVALID",
        "governance_evidence.records[2].status",
    ) in _pairs(document)

    document = _document()
    document["agentic_network"]["revocations"] = [
        _revocation(
            "revocation.approval",
            {"kind": "approval_record", "approval_record_ref": "approval_record"},
        )
    ]
    assert (
        "AN_APPROVAL_REVOKED",
        "governance_evidence.records[2].id",
    ) in _pairs(document)


@pytest.mark.parametrize(
    ("source_allowlist", "target_allowlist", "category", "expected"),
    [
        (["source_only"], [], "source_only", "AN_SHARE_NOT_ALLOWED_TARGET"),
        ([], ["target_only"], "target_only", "AN_SHARE_NOT_ALLOWED_SOURCE"),
        ([], [], "unknown_data", "AN_SHARE_CATEGORY_UNKNOWN"),
    ],
)
def test_protocol_sharing_requires_both_zone_allowlists(
    source_allowlist: list[str],
    target_allowlist: list[str],
    category: str,
    expected: str,
) -> None:
    document = _document()
    document["agentic_network"]["trust_zones"][0]["share_allowlist"] = source_allowlist
    document["agentic_network"]["trust_zones"][1]["share_allowlist"] = target_allowlist
    document["agentic_network"]["protocol_targets"][0]["share"] = [category]

    assert (expected, "agentic_network.protocol_targets[0].share") in _pairs(document)


def test_protocol_sharing_rejects_duplicate_and_missing_allowlist() -> None:
    document = _document()
    document["agentic_network"]["protocol_targets"][0]["share"] = [
        "evidence_digest",
        "evidence_digest",
    ]
    assert (
        "AN_SHARE_CATEGORY_DUPLICATE",
        "agentic_network.protocol_targets[0].share",
    ) in _pairs(document)

    document = _document()
    document["agentic_network"]["trust_zones"][0].pop("share_allowlist")
    assert (
        "AN_SHARE_NOT_ALLOWED_SOURCE",
        "agentic_network.protocol_targets[0].share",
    ) in _pairs(document)


def test_delegation_is_rejected_by_schema_and_structural_check() -> None:
    document = _document()
    document["capabilities"][0]["delegable"] = True
    pairs = _pairs(document)

    assert ("AN_DELEGATION_FORBIDDEN", "capabilities[0].delegable") in pairs
    assert "GOVERNANCE_BLOCK_SCHEMA_INVALID" in _codes(document)


@pytest.mark.parametrize(
    ("scope_ref", "expected"),
    [
        ("MissingScope", "AN_CAPABILITY_SCOPE_UNKNOWN"),
        ("Researcher", "AN_CAPABILITY_SCOPE_WRONG_KIND"),
    ],
)
def test_capability_scope_resolution_is_closed(scope_ref: str, expected: str) -> None:
    document = _document()
    document["capabilities"][0]["scope_refs"] = [scope_ref]

    assert (expected, "capabilities[0].scope_refs") in _pairs(document)


def test_capability_scope_class_is_closed() -> None:
    document = _document()
    document["capabilities"][0]["scope_type"] = "agent"

    assert (
        "AN_CAPABILITY_SCOPE_CLASS_UNSUPPORTED",
        "capabilities[0].scope_type",
    ) in _pairs(document)


def test_capability_scope_collision_and_duplicates_fail_closed() -> None:
    document = _document()
    document["contexts"].append({"name": "Researcher", "include": ["README.md"], "exclude": []})
    document["capabilities"][0]["scope_refs"] = ["Researcher", "Researcher"]
    codes = _codes(document)

    assert {"AN_CAPABILITY_SCOPE_AMBIGUOUS", "AN_CAPABILITY_SCOPE_DUPLICATE"} <= codes


def test_structured_capability_revocation_round_trips_canonically() -> None:
    document = _document()
    revocation = _revocation(
        "revocation.assignment",
        {
            "kind": "capability_assignment",
            "principal_type": "membership",
            "principal_ref": "membership.reviewer",
            "capability_ref": "read_governed_context",
        },
    )
    document["agentic_network"]["revocations"] = [revocation]

    serialized = yaml.safe_dump(revocation, sort_keys=True)
    assert yaml.safe_load(serialized) == revocation
    assert "GOVERNANCE_BLOCK_SCHEMA_INVALID" not in _codes(document)


def test_agentic_diagnostic_order_is_deterministic() -> None:
    document = _document()
    document["capabilities"][0]["delegable"] = True
    document["capabilities"][0]["scope_refs"] = ["MissingScope"]
    first = [
        (item.code, item.path, item.message)
        for item in _diagnostics(document)
        if item.source_id == "agentic_network_foundation.v1"
    ]
    second = [
        (item.code, item.path, item.message)
        for item in _diagnostics(document)
        if item.source_id == "agentic_network_foundation.v1"
    ]

    assert first == second == sorted(first)


def test_agent_identity_cannot_approve() -> None:
    document = _document()
    document["agent_identities"][0]["can_approve"] = True

    assert {
        "AN_NON_HUMAN_APPROVAL_INVALID",
        "GOVERNANCE_BLOCK_SCHEMA_INVALID",
    } <= _codes(document)


@pytest.mark.parametrize("field", ["api_key", "private_key", "credential_ref"])
def test_identity_rejects_key_and_credential_material(field: str) -> None:
    document = _document()
    document["agent_identities"][0][field] = "forbidden"

    assert "GOVERNANCE_BLOCK_SCHEMA_INVALID" in _codes(document)


def test_remote_schema_reference_is_rejected() -> None:
    registry = GovernanceRegistry.builtins()
    payload = registry.resolve_module("agentic_network_governance").as_dict()
    payload["id"] = "org.example.remote_schema"
    payload["name"] = "remote_schema"
    payload["dependencies"] = []
    payload["block_schemas"][0]["schema_id"] = "https://example.invalid/schema.json"
    payload["provenance"]["source_tier"] = "project"
    payload["integrity"]["content_hash"] = canonical_pack_hash(payload)

    with pytest.raises(GovernanceError) as caught:
        load_pack_bytes(
            yaml.safe_dump(payload, sort_keys=False).encode(),
            source_path="remote-schema.yaml",
            source_tier="project",
        )
    assert _error_codes(caught.value) == {"PACK_SCHEMA_INVALID"}


def test_malicious_project_module_schema_conflict_fails_closed() -> None:
    registry = GovernanceRegistry.builtins()
    original = registry.resolve_module("agentic_network_governance")
    malicious = replace(
        original,
        id="org.example.agentic_conflict",
        name="agentic_conflict",
        dependencies=(),
        provenance=replace(
            original.provenance,
            source_tier="project",
            source_path=".nornyx/modules/agentic_conflict.yaml",
        ),
        block_schemas=(
            GovernanceBlockSchema(
                "agentic_network",
                "https://nornyx.dev/schemas/governance_evidence_v1.schema.json",
                "org.example.agentic_conflict",
            ),
        ),
    )
    registry.register_module(malicious)

    with pytest.raises(GovernanceError) as caught:
        compose_governance(
            registry,
            profile_identity="agentic_network",
            module_ids=(malicious.id,),
        )
    assert _error_codes(caught.value) == {"PACK_BLOCK_SCHEMA_CONFLICT"}


def test_builtin_identity_shadow_attempt_is_rejected() -> None:
    registry = GovernanceRegistry.builtins()
    original = registry.resolve_module("agentic_network_governance")
    shadow = replace(
        original,
        provenance=replace(
            original.provenance,
            source_tier="project",
            source_path=".nornyx/modules/shadow.yaml",
        ),
    )

    with pytest.raises(GovernanceError) as caught:
        registry.register_module(shadow)
    assert _error_codes(caught.value) == {"PACK_RESERVED_NAMESPACE"}


def test_module_permutation_and_profile_lock_are_deterministic() -> None:
    registry = GovernanceRegistry.builtins()
    module_ids = (
        "nornyx.builtin.module.agentic_network_governance",
        "nornyx.builtin.module.human_approval",
    )
    first = compose_governance(
        registry,
        profile_identity="agentic_network",
        module_ids=module_ids,
    )
    second = compose_governance(
        registry,
        profile_identity="agentic_network",
        module_ids=reversed(module_ids),
    )
    assert first.to_dict() == second.to_dict()

    packs = [*first.modules, first.profile]
    lock = lock_for_packs(packs)  # type: ignore[arg-type]
    entry = lock.resolved[0]
    tampered = ProfileLock(
        (
            LockEntry(
                entry.id,
                entry.version,
                entry.source_tier,
                "sha256:" + "0" * 64,
                entry.path_hint,
            ),
            *lock.resolved[1:],
        )
    )
    with pytest.raises(GovernanceError) as caught:
        compose_governance(
            registry,
            profile_identity="agentic_network",
            lock=tampered,
        )
    assert "PACK_LOCK_MISMATCH" in _error_codes(caught.value)


def _write_valid_local_profile(path: Path) -> None:
    fixture = ROOT / "tests" / "fixtures" / "governance_extension" / "valid_profile_v1.yaml"
    payload = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    payload["integrity"]["content_hash"] = canonical_pack_hash(payload)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_project_local_path_and_symlink_escape_are_rejected(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.yaml"
    _write_valid_local_profile(outside)
    with pytest.raises(GovernanceError) as traversal:
        load_local_pack(outside, allowed_root=allowed)
    assert _error_codes(traversal.value) == {"PACK_PATH_OUTSIDE_ROOT"}

    target = allowed / "target.yaml"
    link = allowed / "link.yaml"
    _write_valid_local_profile(target)
    create_symlink_or_skip(link, target)
    with pytest.raises(GovernanceError) as symlink:
        load_local_pack(link, allowed_root=allowed)
    assert _error_codes(symlink.value) == {"PACK_SYMLINK_REJECTED"}


@pytest.mark.parametrize(
    "path",
    [
        "https://example.invalid/profile.yaml",
        r"\\server\share\profile.yaml",
        r"\\?\C:\profile.yaml",
        r"C:\CON\profile.yaml",
    ],
)
def test_uri_unc_and_device_pack_paths_are_rejected(path: str, tmp_path: Path) -> None:
    with pytest.raises(GovernanceError) as caught:
        load_local_pack(path, allowed_root=tmp_path)
    assert _error_codes(caught.value) == {"PACK_REMOTE_SOURCE_REJECTED"}


def test_existing_starters_mappings_and_source_resources_are_preserved() -> None:
    manifest = json.loads(
        (
            ROOT
            / "tests"
            / "fixtures"
            / "governance_extension"
            / "starter_golden"
            / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    previous = manifest["profiles"][:-1]
    assert len(previous) == 12
    for entry in previous:
        raw = (
            ROOT / "tests" / "fixtures" / "governance_extension" / "starter_golden" / entry["file"]
        ).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry["sha256"]

    registry = GovernanceRegistry.builtins()
    for name in registry.profile_names[:-1]:
        required = registry.resolve_profile(name).required_modules
        if name == "architecture_governance":
            assert required == ("nornyx.builtin.module.architecture_conformance",)
        else:
            assert required == ()

    profile_resources = resources.files("nornyx") / "profiles_data"
    assert len(list(profile_resources.iterdir())) == 21
    assert len(registry.profile_names) == 13
    assert len(registry.module_names) == 7


def test_static_evaluation_does_not_use_network_or_processes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("static governance attempted an external operation")

    original_import = builtins.__import__

    def guarded_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.split(".", 1)[0] in {"crewai", "langgraph"}:
            raise AssertionError("static governance attempted framework construction")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)

    assert _diagnostics(_document()) == ()
