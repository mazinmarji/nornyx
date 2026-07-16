from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from nornyx.governance import GovernanceRegistry
from nornyx.governance.runtime import evaluate_document_governance


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
AS_OF = "2026-06-01T00:00:00Z"


def _document() -> dict[str, Any]:
    return yaml.safe_load(
        (EXAMPLES / "governance_foundations.nyx").read_text(encoding="utf-8")
    )


def _codes(document: dict[str, Any]) -> set[str]:
    return {
        item.code
        for item in evaluate_document_governance(
            document,
            registry=GovernanceRegistry.builtins(),
            as_of=AS_OF,
            document_root=EXAMPLES,
        )
    }


def _evidence_record(document: dict[str, Any], identifier: str) -> dict[str, Any]:
    return next(
        record
        for record in document["governance_evidence"]["records"]
        if record["id"] == identifier
    )


def test_aud008_empty_sod_assignment_fails_schema_and_structure() -> None:
    document = _document()
    document["separation_of_duties"]["assignments"][0]["approvers"] = []

    codes = _codes(document)
    assert "GOVERNANCE_BLOCK_SCHEMA_INVALID" in codes
    assert "SOD_APPROVER_REQUIRED" in codes


@pytest.mark.parametrize(
    ("approvers", "expected"),
    [
        ([7], "SOD_APPROVER_INVALID"),
        ([{"role": "reviewer"}], "SOD_APPROVER_INVALID"),
        ([" reviewer"], "SOD_APPROVER_INVALID"),
        (["user:reviewer", "user:reviewer"], "SOD_APPROVER_INVALID"),
        (["tool:review_bot"], "SOD_NON_HUMAN_APPROVER"),
        (["agent:review_bot"], "SOD_NON_HUMAN_APPROVER"),
    ],
)
def test_aud008_malformed_duplicate_and_nonhuman_approvers_fail(
    approvers: list[object],
    expected: str,
) -> None:
    document = _document()
    document["separation_of_duties"]["assignments"][0]["approvers"] = approvers

    codes = _codes(document)
    assert "GOVERNANCE_BLOCK_SCHEMA_INVALID" in codes
    assert expected in codes


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("unknown_subject", "SOD_SUBJECT_UNKNOWN"),
        ("risk_mismatch", "SOD_RISK_TIER_MISMATCH"),
        ("author_role", "SOD_AUTHOR_ROLE_MISMATCH"),
        ("approver_role", "SOD_APPROVER_ROLE_MISMATCH"),
        ("approval_gate", "SOD_APPROVAL_GATE_MISMATCH"),
        ("evidence_producer", "SOD_EVIDENCE_PRODUCER_UNKNOWN"),
        ("partial_producer_overlap", "SOD_EVIDENCE_PRODUCER_SOLE_APPROVER"),
    ],
)
def test_aud008_assignments_are_linked_to_change_gate_and_evidence(
    mutation: str,
    expected: str,
) -> None:
    document = _document()
    assignment = document["separation_of_duties"]["assignments"][0]
    change = document["changes"][0]
    if mutation == "unknown_subject":
        assignment["subject"] = "change:missing"
    elif mutation == "risk_mismatch":
        assignment["risk_tier"] = "critical"
    elif mutation == "author_role":
        assignment["author"] = "user:writer"
    elif mutation == "approver_role":
        assignment["approvers"] = ["user:security"]
    elif mutation == "approval_gate":
        assignment["approvers"] = ["user:security"]
        change["approver_roles"] = ["security"]
        change["separation_of_duties"]["approver_role"] = "security"
    elif mutation == "evidence_producer":
        assignment["evidence_producers"] = ["tool:missing"]
    else:
        assignment["approvers"] = ["user:reviewer", "user:security"]
        assignment["evidence_producers"] = ["user:reviewer"]
        change["approver_roles"] = ["reviewer", "security"]

    assert expected in _codes(document)


def test_aud008_valid_assignment_remains_linked_and_independent() -> None:
    codes = _codes(_document())

    assert not {
        "SOD_APPROVER_REQUIRED",
        "SOD_APPROVER_INVALID",
        "SOD_SUBJECT_UNKNOWN",
        "SOD_RISK_TIER_MISMATCH",
        "SOD_AUTHOR_ROLE_MISMATCH",
        "SOD_APPROVER_ROLE_MISMATCH",
        "SOD_APPROVAL_GATE_MISMATCH",
        "SOD_EVIDENCE_PRODUCER_UNKNOWN",
        "SOD_EVIDENCE_PRODUCER_SOLE_APPROVER",
    } & codes


@pytest.mark.parametrize("subject", ["change:change-example", "change-example"])
def test_aud008_change_assignment_cannot_omit_the_change_collection(
    subject: str,
) -> None:
    document = _document()
    document["separation_of_duties"]["assignments"][0]["subject"] = subject
    document.pop("changes")

    assert "SOD_SUBJECT_UNKNOWN" in _codes(document)


def test_aud008_sod_module_declares_its_cross_block_change_contract() -> None:
    module = GovernanceRegistry.builtins().resolve_module("separation_of_duties")

    assert "changes" in module.required_blocks
    assert {
        schema.block: schema.schema_id for schema in module.block_schemas
    }["changes"].endswith("/change_v1.schema.json")


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("empty_assignments", "SOD_ASSIGNMENT_REQUIRED"),
        ("scalar_assignments", "SOD_ASSIGNMENT_INVALID"),
        ("scalar_entry", "SOD_ASSIGNMENT_INVALID"),
        ("semantic_duplicate", "SOD_APPROVER_INVALID"),
        ("malformed_producer", "SOD_EVIDENCE_PRODUCER_INVALID"),
        ("robot_approver", "SOD_NON_HUMAN_APPROVER"),
        ("case_varied_tool", "SOD_NON_HUMAN_APPROVER"),
        ("exact_nonhuman", "SOD_NON_HUMAN_APPROVER"),
        ("case_varied_exact_nonhuman", "SOD_NON_HUMAN_APPROVER"),
    ],
)
def test_aud008_all_assignment_shapes_fail_closed(
    mutation: str,
    expected: str,
) -> None:
    document = _document()
    assignment = document["separation_of_duties"]["assignments"][0]
    if mutation == "empty_assignments":
        document["separation_of_duties"]["assignments"] = []
    elif mutation == "scalar_assignments":
        document["separation_of_duties"]["assignments"] = "assignment"
    elif mutation == "scalar_entry":
        document["separation_of_duties"]["assignments"] = [True]
    elif mutation == "semantic_duplicate":
        assignment["approvers"] = ["reviewer", "user:reviewer"]
    elif mutation == "malformed_producer":
        assignment["evidence_producers"] = [{"tool": "example_tool"}]
    elif mutation == "robot_approver":
        assignment["approvers"] = ["robot:reviewer"]
    elif mutation == "case_varied_tool":
        assignment["approvers"] = ["ToOl:reviewer"]
    elif mutation == "exact_nonhuman":
        assignment["approvers"] = ["ai_tool"]
    else:
        assignment["approvers"] = ["MoDeL"]

    assert expected in _codes(document)


def test_aud008_all_linked_approval_gates_compose_restrictively() -> None:
    document = _document()
    second = deepcopy(document["approvals"][0])
    second["name"] = "DisjointGate"
    second["required_roles"] = ["security_reviewer"]
    second["eligible_roles"] = ["security_reviewer"]
    document["approvals"].append(second)
    document["changes"][0]["approval_ids"].append("DisjointGate")

    assert "SOD_APPROVAL_GATE_MISMATCH" in _codes(document)


def test_aud008_producer_must_belong_to_corresponding_evidence_component() -> None:
    document = _document()
    orphan = deepcopy(_evidence_record(document, "evidence_manifest"))
    orphan["id"] = "orphan_record"
    orphan["type"] = "orphan_record"
    orphan["tool"]["name"] = "orphan_tool"
    document["governance_evidence"]["records"].append(orphan)
    document["separation_of_duties"]["assignments"][0][
        "evidence_producers"
    ] = ["tool:orphan_tool"]

    assert "SOD_EVIDENCE_PRODUCER_UNKNOWN" in _codes(document)


def test_aud008_undeclared_actual_producer_cannot_overlap_approver() -> None:
    document = _document()
    _evidence_record(document, "change_record")["producer"] = {
        "id": "human.reviewer",
        "type": "human",
    }

    assert "SOD_EVIDENCE_PRODUCER_SOLE_APPROVER" in _codes(document)


def test_aud008_evidence_type_cannot_hide_actual_producer_overlap() -> None:
    document = _document()
    change_record = _evidence_record(document, "change_record")
    change_record["producer"] = {
        "id": "human.reviewer",
        "type": "human",
    }
    change_record["type"] = "approval_record"

    assert "SOD_EVIDENCE_PRODUCER_SOLE_APPROVER" in _codes(document)


def test_aud008_subject_aliases_cannot_duplicate_one_change_assignment() -> None:
    document = _document()
    duplicate = deepcopy(document["separation_of_duties"]["assignments"][0])
    duplicate["subject"] = "change-example"
    document["separation_of_duties"]["assignments"].append(duplicate)

    assert "SOD_DUPLICATE_SUBJECT" in _codes(document)


@pytest.mark.parametrize("mutation", ["expired_without_closure", "overlap"])
def test_aud013_expired_and_overlapping_exceptions_fail(mutation: str) -> None:
    document = _document()
    exception = document["exceptions"]["entries"][0]
    if mutation == "expired_without_closure":
        exception["status"] = "expired"
        exception["expires_at"] = "2026-05-15T00:00:00Z"
        exception["closure_evidence"] = []
        expected = "EXCEPTION_CLOSURE_EVIDENCE_MISSING"
    else:
        overlapping = deepcopy(exception)
        overlapping["id"] = "EXC-OVERLAP"
        document["exceptions"]["entries"].append(overlapping)
        expected = "EXCEPTION_SCOPE_OVERLAP"

    assert expected in _codes(document)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_start",
        "malformed_start",
        "overflow_start",
        "equal_end",
        "end_before_start",
    ],
)
def test_aud013_missing_or_malformed_intervals_fail_closed(mutation: str) -> None:
    document = _document()
    exception = document["exceptions"]["entries"][0]
    if mutation == "missing_start":
        exception.pop("starts_at")
    elif mutation == "malformed_start":
        exception["starts_at"] = "not-a-time"
    elif mutation == "overflow_start":
        exception["starts_at"] = "0001-01-01T00:00:00+23:59"
    elif mutation == "equal_end":
        exception["expires_at"] = exception["starts_at"]
    else:
        exception["expires_at"] = "2025-12-31T23:59:59Z"

    codes = _codes(document)
    if mutation in {"missing_start", "malformed_start", "overflow_start"}:
        if mutation != "overflow_start":
            assert "GOVERNANCE_BLOCK_SCHEMA_INVALID" in codes
        assert "EXCEPTION_TIME_INVALID" in codes
    else:
        assert "EXCEPTION_INTERVAL_INVALID" in codes


def test_aud013_declared_active_after_expiry_is_closed_fail_closed() -> None:
    document = _document()
    exception = document["exceptions"]["entries"][0]
    exception["expires_at"] = "2026-05-15T00:00:00Z"
    exception["closure_evidence"] = []

    codes = _codes(document)
    assert "EXCEPTION_EXPIRED" in codes
    assert "EXCEPTION_CLOSURE_EVIDENCE_MISSING" in codes


@pytest.mark.parametrize(
    ("mutation", "overlaps"),
    [
        ("intersecting_scope", True),
        ("disjoint_scope", False),
        ("different_control", False),
        ("adjacent_interval", False),
        ("closed_record", False),
    ],
)
def test_aud013_overlap_requires_same_control_scope_time_and_active_status(
    mutation: str,
    overlaps: bool,
) -> None:
    document = _document()
    first = document["exceptions"]["entries"][0]
    second = deepcopy(first)
    second["id"] = "EXC-SECOND"
    if mutation == "disjoint_scope":
        second["scope"] = ["change:other"]
    elif mutation == "different_control":
        second["control"] = "project.other_control"
    elif mutation == "adjacent_interval":
        second["starts_at"] = first["expires_at"]
        second["expires_at"] = "2100-01-01T00:00:00Z"
    elif mutation == "closed_record":
        second["status"] = "closed"
        second["closure_evidence"] = ["exception_review_record"]
    document["exceptions"]["entries"].append(second)

    assert ("EXCEPTION_SCOPE_OVERLAP" in _codes(document)) is overlaps


def _renewal_document() -> tuple[dict[str, Any], dict[str, Any]]:
    document = _document()
    prior = document["exceptions"]["entries"][0]
    prior["status"] = "expired"
    prior["expires_at"] = "2026-05-15T00:00:00Z"
    prior["closure_evidence"] = ["exception_review_record"]
    renewal = deepcopy(prior)
    renewal["id"] = "EXC-RENEWAL"
    renewal["status"] = "active"
    renewal["starts_at"] = prior["expires_at"]
    renewal["expires_at"] = "2027-05-15T00:00:00Z"
    renewal["closure_evidence"] = []
    renewal["renews"] = prior["id"]
    renewal_approval = deepcopy(_evidence_record(document, "approval_record"))
    renewal_approval["id"] = "renewal_approval_record"
    renewal_approval["type"] = "approval_record"
    renewal_approval["producer"] = {
        "id": "human.exception_approver",
        "type": "human",
    }
    renewal_approval[
        "artifact"
    ] = "governance_evidence/renewal_approval_record.json"
    renewal_approval[
        "content_hash"
    ] = "sha256:78f95e8453361cae124f2b96c9412f895b1cc09cd32d2728fa379f292b481aac"
    renewal_approval["generated_at"] = renewal["starts_at"]
    renewal_approval["dependencies"] = ["exception_review_record"]
    document["governance_evidence"]["records"].append(renewal_approval)
    renewal["renewal_approval_evidence"] = ["renewal_approval_record"]
    document["exceptions"]["entries"].append(renewal)
    renewal_gate = deepcopy(document["approvals"][0])
    renewal_gate["name"] = "ExplicitExceptionRenewalGate"
    renewal_gate["required_roles"] = ["exception_approver"]
    renewal_gate["eligible_roles"] = ["exception_approver"]
    renewal_gate["required_for"] = [f"renew_exception:{renewal['id']}"]
    renewal_gate["required_evidence"] = ["renewal_approval_record"]
    document["approvals"].append(renewal_gate)
    return document, renewal


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("missing_approval", "EXCEPTION_RENEWAL_APPROVAL_MISSING"),
        ("unknown_prior", "EXCEPTION_RENEWAL_REFERENCE_INVALID"),
        ("self_reference", "EXCEPTION_RENEWAL_REFERENCE_INVALID"),
        ("overlap", "EXCEPTION_RENEWAL_INTERVAL_INVALID"),
    ],
)
def test_aud013_renewal_is_explicit_separate_and_nonoverlapping(
    mutation: str,
    expected: str,
) -> None:
    document, renewal = _renewal_document()
    if mutation == "missing_approval":
        renewal["renewal_approval_evidence"] = []
    elif mutation == "unknown_prior":
        renewal["renews"] = "EXC-MISSING"
    elif mutation == "self_reference":
        renewal["renews"] = renewal["id"]
    else:
        renewal["starts_at"] = "2026-05-01T00:00:00Z"

    assert expected in _codes(document)


def test_aud013_valid_explicit_renewal_remains_accepted() -> None:
    document, _ = _renewal_document()
    assert _codes(document) == set()


def test_aud013_renewal_requires_exact_approval_evidence_type() -> None:
    document, _ = _renewal_document()
    _evidence_record(document, "renewal_approval_record")[
        "type"
    ] = "disapproval_record"

    assert "EXCEPTION_RENEWAL_APPROVAL_MISSING" in _codes(document)


def test_aud013_relabelled_old_approval_is_not_new_renewal_evidence() -> None:
    document, _ = _renewal_document()
    record = _evidence_record(document, "renewal_approval_record")
    original = _evidence_record(document, "approval_record")
    record["artifact"] = original["artifact"]
    record["content_hash"] = original["content_hash"]
    record["generated_at"] = original["generated_at"]

    assert "EXCEPTION_RENEWAL_APPROVAL_MISSING" in _codes(document)


@pytest.mark.parametrize(
    "generated_at",
    ["2025-12-31T23:59:59Z", "2026-05-15T00:00:01Z"],
)
def test_aud013_renewal_approval_must_follow_prior_start_and_precede_activation(
    generated_at: str,
) -> None:
    document, _ = _renewal_document()
    _evidence_record(document, "renewal_approval_record")[
        "generated_at"
    ] = generated_at

    assert "EXCEPTION_RENEWAL_APPROVAL_MISSING" in _codes(document)


def test_aud013_renewal_can_be_preapproved_before_prior_expiry() -> None:
    document, _ = _renewal_document()
    _evidence_record(document, "renewal_approval_record")[
        "generated_at"
    ] = "2026-05-14T00:00:00Z"

    assert _codes(document) == set()


def test_aud013_renewal_can_be_preapproved_after_prior_expiry() -> None:
    document, renewal = _renewal_document()
    renewal["starts_at"] = "2026-05-20T00:00:00Z"
    _evidence_record(document, "renewal_approval_record")[
        "generated_at"
    ] = "2026-05-18T00:00:00Z"

    assert _codes(document) == set()


def test_aud013_fresh_extra_evidence_cannot_launder_reused_gate_proof() -> None:
    document, renewal = _renewal_document()
    renewal["renewal_approval_evidence"] = [
        "approval_record",
        "renewal_approval_record",
    ]
    document["approvals"][-1]["required_evidence"] = ["approval_record"]

    assert "EXCEPTION_RENEWAL_APPROVAL_MISSING" in _codes(document)


def test_aud013_ancestor_renewal_evidence_cannot_be_reused() -> None:
    document, renewal = _renewal_document()
    next_renewal = deepcopy(renewal)
    next_renewal["id"] = "EXC-RENEWAL-2"
    next_renewal["status"] = "approved"
    next_renewal["renews"] = renewal["id"]
    next_renewal["starts_at"] = renewal["expires_at"]
    next_renewal["expires_at"] = "2028-05-15T00:00:00Z"
    document["exceptions"]["entries"].append(next_renewal)
    next_gate = deepcopy(document["approvals"][-1])
    next_gate["name"] = "SecondExplicitExceptionRenewalGate"
    next_gate["required_for"] = [f"renew_exception:{next_renewal['id']}"]
    document["approvals"].append(next_gate)

    assert "EXCEPTION_RENEWAL_APPROVAL_MISSING" in _codes(document)


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("active_before_start", "EXCEPTION_LIFECYCLE_INVALID"),
        ("expired_before_expiry", "EXCEPTION_LIFECYCLE_INVALID"),
        ("renewal_prohibited", "EXCEPTION_RENEWAL_NOT_ALLOWED"),
        ("renewal_rejected_prior", "EXCEPTION_RENEWAL_REFERENCE_INVALID"),
        ("renewal_unknown_evidence", "EXCEPTION_RENEWAL_APPROVAL_MISSING"),
        ("renewal_reused_evidence", "EXCEPTION_RENEWAL_APPROVAL_MISSING"),
        ("renewal_failed_evidence", "EXCEPTION_RENEWAL_APPROVAL_MISSING"),
        ("renewal_wrong_producer", "EXCEPTION_RENEWAL_APPROVAL_MISSING"),
        ("renewal_cycle", "EXCEPTION_RENEWAL_REFERENCE_INVALID"),
        ("renewal_fork", "EXCEPTION_RENEWAL_FORK_INVALID"),
        ("renewal_gate_missing", "EXCEPTION_RENEWAL_APPROVAL_MISSING"),
        ("renewal_gate_unbound", "EXCEPTION_RENEWAL_APPROVAL_MISSING"),
        ("renewal_gate_disjoint", "EXCEPTION_RENEWAL_APPROVAL_MISSING"),
        ("approval_without_reference", "EXCEPTION_RENEWAL_REFERENCE_INVALID"),
    ],
)
def test_aud013_lifecycle_and_renewal_bypasses_fail_closed(
    mutation: str,
    expected: str,
) -> None:
    if mutation in {"active_before_start", "expired_before_expiry"}:
        document = _document()
        exception = document["exceptions"]["entries"][0]
        if mutation == "active_before_start":
            exception["starts_at"] = "2026-07-01T00:00:00Z"
        else:
            exception["status"] = "expired"
            exception["closure_evidence"] = ["exception_review_record"]
    else:
        document, renewal = _renewal_document()
        prior = document["exceptions"]["entries"][0]
        if mutation == "renewal_prohibited":
            prior["renewal_policy"] = "prohibited"
        elif mutation == "renewal_rejected_prior":
            prior["status"] = "rejected"
        elif mutation == "renewal_unknown_evidence":
            renewal["renewal_approval_evidence"] = ["missing_record"]
        elif mutation == "renewal_reused_evidence":
            renewal["renewal_approval_evidence"] = ["exception_review_record"]
        elif mutation == "renewal_failed_evidence":
            _evidence_record(document, "renewal_approval_record")["status"] = "fail"
        elif mutation == "renewal_wrong_producer":
            _evidence_record(document, "renewal_approval_record")["producer"] = {
                "id": "human.unrelated",
                "type": "human",
            }
        elif mutation == "renewal_cycle":
            prior["renews"] = renewal["id"]
            prior["renewal_approval_evidence"] = ["renewal_approval_record"]
        elif mutation == "renewal_fork":
            fork = deepcopy(renewal)
            fork["id"] = "EXC-RENEWAL-FORK"
            document["exceptions"]["entries"].append(fork)
        elif mutation == "renewal_gate_missing":
            document["approvals"].pop()
        elif mutation == "renewal_gate_unbound":
            document["approvals"][-1]["required_for"] = ["merge"]
        elif mutation == "renewal_gate_disjoint":
            document["approvals"][-1]["required_roles"] = ["risk_owner"]
            document["approvals"][-1]["eligible_roles"] = ["risk_owner"]
        else:
            renewal.pop("renews")

    assert expected in _codes(document)


@pytest.mark.parametrize(
    "control",
    [
        "nornyx.core",
        "nornyx.core.pack_integrity",
        "nornyx.builtin.module.human_approval",
        "control:PACK_INTEGRITY",
        "PACK_SYMLINK_REJECTED",
        "GOVERNANCE_BLOCK_SCHEMA_INVALID",
        "control:CHANGE_SCOPE_HASH_MISMATCH",
        "control:GOVERNANCE_BLOCK_SCHEMA_INVALID",
        "FILE_ATTRIBUTE_REPARSE_POINT",
        "PROFILE_PROJECTION_UNSUPPORTED",
        "non_human_authority_denied",
        "APR-001",
        "control:SOD-001",
        "control:nornyx.core.pack_integrity",
    ],
)
def test_aud013_core_safety_checker_controls_cannot_be_exempted(
    control: str,
) -> None:
    document = _document()
    document["exceptions"]["entries"][0]["control"] = control

    assert "EXCEPTION_CORE_CONTROL_FORBIDDEN" in _codes(document)


def test_aud013_project_control_identifier_is_not_a_reserved_diagnostic() -> None:
    document = _document()
    document["exceptions"]["entries"][0]["control"] = "PROJECT_CUSTOM_CONTROL"

    assert "EXCEPTION_CORE_CONTROL_FORBIDDEN" not in _codes(document)


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("requester", "exception_approver", "EXCEPTION_SELF_APPROVAL"),
        ("requester", "USER:exception_approver", "EXCEPTION_SELF_APPROVAL"),
        ("requester", "robot:requester", "EXCEPTION_NON_HUMAN_AUTHORITY"),
        ("approving_authority", "bot:approver", "EXCEPTION_NON_HUMAN_AUTHORITY"),
        ("accountable_owner", "workflow:risk", "EXCEPTION_NON_HUMAN_AUTHORITY"),
    ],
)
def test_aud013_authority_aliases_cannot_bypass_human_separation(
    field: str,
    value: str,
    expected: str,
) -> None:
    document = _document()
    document["exceptions"]["entries"][0][field] = value

    assert expected in _codes(document)


def test_aud013_expired_boundary_is_half_open_and_requires_closure() -> None:
    document = _document()
    exception = document["exceptions"]["entries"][0]
    exception["status"] = "expired"
    exception["expires_at"] = AS_OF
    exception["closure_evidence"] = ["exception_review_record"]

    codes = _codes(document)
    assert "EXCEPTION_LIFECYCLE_INVALID" not in codes
    assert "EXCEPTION_CLOSURE_EVIDENCE_MISSING" not in codes


@pytest.mark.parametrize(
    ("record_id", "status", "expected"),
    [
        ("approval_record", "fail", "APPROVAL_EVIDENCE_MISSING"),
        ("approval_record", "inconclusive", "APPROVAL_EVIDENCE_MISSING"),
        ("approval_record", "observed", "APPROVAL_EVIDENCE_MISSING"),
        ("change_record", "fail", "CHANGE_EVIDENCE_MISSING"),
        ("exception_review_record", "fail", "EXCEPTION_EVIDENCE_MISSING"),
        ("evidence_manifest", "fail", "EVIDENCE_DEPENDENCY_UNSATISFIED"),
    ],
)
def test_adjacent_nonpassing_evidence_cannot_authorize_governance(
    record_id: str,
    status: str,
    expected: str,
) -> None:
    document = _document()
    _evidence_record(document, record_id)["status"] = status

    assert expected in _codes(document)


@pytest.mark.parametrize("value", [{}, [], True, 7])
@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("approval_schema", "APPROVAL_DECLARATION_INVALID"),
        ("sod_risk_tier", "SOD_RISK_TIER_MISMATCH"),
        ("exception_status", "EXCEPTION_LIFECYCLE_INVALID"),
        ("change_risk_tier", "CHANGE_RISK_TIER_INVALID"),
        ("architecture_impact", "CHANGE_ARCHITECTURE_IMPACT_INVALID"),
    ],
)
def test_adjacent_malformed_enum_values_fail_closed_without_exceptions(
    mutation: str,
    expected: str,
    value: object,
) -> None:
    document = _document()
    if mutation == "approval_schema":
        document["approvals"][0]["schema"] = deepcopy(value)
    elif mutation == "sod_risk_tier":
        document["separation_of_duties"]["assignments"][0][
            "risk_tier"
        ] = deepcopy(value)
    elif mutation == "exception_status":
        document["exceptions"]["entries"][0]["status"] = deepcopy(value)
    elif mutation == "change_risk_tier":
        document["changes"][0]["risk_tier"] = deepcopy(value)
    else:
        document["changes"][0]["impacts"]["architecture"] = deepcopy(value)

    assert expected in _codes(document)


def test_adjacent_maximum_length_evidence_chain_is_iterative() -> None:
    document = _document()
    document["project"]["modules"] = ["evidence_integrity"]
    template = _evidence_record(document, "evidence_manifest")
    records: list[dict[str, Any]] = []
    for index in range(1000):
        record = deepcopy(template)
        record["id"] = f"chain_{index:04d}"
        record["type"] = "evidence_manifest"
        record["dependencies"] = (
            [f"chain_{index + 1:04d}"] if index < 999 else []
        )
        records.append(record)
    document["governance_evidence"]["records"] = records

    assert _codes(document) == set()
