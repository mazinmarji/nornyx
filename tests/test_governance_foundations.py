from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
from typing import Any

import pytest

from nornyx.governance import GovernanceError, GovernanceRegistry, compose_governance
from nornyx.governance.runtime import evaluate_document_governance
from nornyx.governance.schemas import validate_governance_block_schema


AS_OF = "2026-06-01T00:00:00Z"
REVISION = "git:0123456789abcdef"
FOUNDATIONAL_MODULES = (
    "evidence_integrity",
    "exception_management",
    "human_approval",
    "separation_of_duties",
)
NON_HUMAN_AUTHORITIES = [
    "ai_tool",
    "execution_surface",
    "autonomous_agent",
    "model",
    "connector",
    "generated_output",
]


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _document(tmp_path: Path) -> dict[str, Any]:
    records = []
    for evidence_type in (
        "evidence_manifest",
        "approval_record",
        "independent_review_record",
        "exception_review_record",
    ):
        artifact = Path("reports") / f"{evidence_type}.json"
        target = tmp_path / artifact
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f'{{"type":"{evidence_type}"}}\n', encoding="utf-8")
        records.append(
            {
                "id": evidence_type,
                "type": evidence_type,
                "schema_id": "nornyx.test_evidence.v1",
                "producer": {"id": "local.test", "type": "tool"},
                "artifact": artifact.as_posix(),
                "content_hash": _sha256(target),
                "subject_revision": REVISION,
                "tool": {"name": "test_tool", "version": "1.0.0"},
                "generated_at": "2026-05-01T00:00:00Z",
                "expires_at": "2027-05-01T00:00:00Z",
                "status": "pass",
                "dependencies": [],
            }
        )
    return {
        "nornyx": "0.2",
        "project": {
            "name": "FoundationalGovernance",
            "modules": ["exception_management"],
        },
        "approvals": [
            {
                "name": "HumanGate",
                "required_roles": ["reviewer"],
                "eligible_roles": ["reviewer", "security_reviewer"],
                "denied_actor_types": NON_HUMAN_AUTHORITIES,
                "required_evidence": ["approval_record"],
                "required_for": ["merge"],
                "timing": "before_merge",
                "accountable_authority": "governance_owner",
                "revision_binding": {
                    "kind": "git",
                    "revision": REVISION,
                    "exact": True,
                },
                "invalidation_conditions": ["revision_changed", "scope_changed"],
                "expires_at": "2027-05-01T00:00:00Z",
            }
        ],
        "governance_evidence": {
            "schema": "nornyx.governance_evidence.v1",
            "subject_revision": REVISION,
            "records": records,
        },
        "changes": [
            {
                "id": "foundation",
                "type": "governance",
                "risk_tier": "high",
                "required_evidence": ["independent_review_record"],
                "approver_roles": ["reviewer"],
                "approval_ids": ["HumanGate"],
                "separation_of_duties": {
                    "author_role": "author",
                    "approver_role": "reviewer",
                    "disjoint": True,
                },
            }
        ],
        "separation_of_duties": {
            "schema": "nornyx.separation_of_duties.v1",
            "assignments": [
                {
                    "subject": "change:foundation",
                    "risk_tier": "high",
                    "author": "user:author",
                    "approvers": ["user:reviewer"],
                    "evidence_producers": ["tool:test_tool"],
                    "require_evidence_independence": True,
                    "release_requester": "user:release_requester",
                    "final_release_approver": "user:release_approver",
                    "exception_requester": "user:exception_requester",
                    "exception_approver": "user:exception_approver",
                }
            ],
        },
        "exceptions": {
            "schema": "nornyx.governance_exceptions.v1",
            "source": "project_contract",
            "entries": [
                {
                    "id": "EXC-001",
                    "control": "project.review_window",
                    "reason": "Temporary review-window adjustment.",
                    "scope": ["change:foundation"],
                    "risk_tier": "high",
                    "requester": "user:exception_requester",
                    "accountable_owner": "user:risk_owner",
                    "approving_authority": "user:exception_approver",
                    "compensating_controls": ["control:independent_review"],
                    "evidence": ["exception_review_record"],
                    "starts_at": "2026-05-01T00:00:00Z",
                    "expires_at": "2026-12-01T00:00:00Z",
                    "renewal_policy": "manual_reapproval",
                    "closure_evidence": [],
                    "status": "active",
                }
            ],
        },
    }


def _diagnostics(document: dict[str, Any], tmp_path: Path) -> tuple[Any, ...]:
    return evaluate_document_governance(
        document,
        registry=GovernanceRegistry.builtins(),
        as_of=AS_OF,
        document_root=tmp_path,
    )


def _codes(diagnostics: tuple[Any, ...]) -> set[str]:
    return {item.code for item in diagnostics}


def test_foundational_modules_are_packaged_integrity_locked_and_composable() -> None:
    registry = GovernanceRegistry.builtins()
    assert set(FOUNDATIONAL_MODULES) <= set(registry.module_names)
    modules = [registry.resolve_module(name) for name in FOUNDATIONAL_MODULES]
    assert all(module.content_hash.startswith("sha256:") for module in modules)
    assert all(module.provenance.source_tier == "builtin" for module in modules)
    assert all(module.structural_checks for module in modules)

    first = compose_governance(
        registry,
        profile_identity=None,
        module_ids=["human_approval", "evidence_integrity"],
    ).to_dict()
    second = compose_governance(
        registry,
        profile_identity=None,
        module_ids=["evidence_integrity", "human_approval"],
    ).to_dict()
    assert first == second


def test_foundational_governance_accepts_a_complete_local_contract(tmp_path: Path) -> None:
    document = _document(tmp_path)
    assert _diagnostics(document, tmp_path) == ()
    assert _diagnostics(document, tmp_path) == ()


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("ai_approver", "APPROVAL_DECLARATION_INVALID"),
        ("missing_revision", "APPROVAL_REVISION_BINDING_REQUIRED"),
        ("expired_approval", "APPROVAL_EXPIRED"),
        ("non_human_accountable", "APPROVAL_NON_HUMAN_AUTHORITY"),
        ("non_string_accountable", "APPROVAL_DECLARATION_INVALID"),
        ("approval_evidence_reference", "APPROVAL_EVIDENCE_MISSING"),
        ("evidence_revision", "EVIDENCE_REVISION_MISMATCH"),
        ("evidence_hash", "EVIDENCE_ARTIFACT_HASH_MISMATCH"),
        ("evidence_stale", "EVIDENCE_STALE"),
        ("evidence_dependency", "EVIDENCE_DEPENDENCY_INVALID"),
        ("self_approval", "SOD_SELF_APPROVAL"),
        ("producer_approval", "SOD_EVIDENCE_PRODUCER_SOLE_APPROVER"),
        ("non_human_sod_approver", "SOD_NON_HUMAN_APPROVER"),
        ("release_conflict", "SOD_RELEASE_AUTHORITY_CONFLICT"),
        ("core_exception", "EXCEPTION_CORE_CONTROL_FORBIDDEN"),
        ("self_exception", "EXCEPTION_SELF_APPROVAL"),
        ("non_human_exception", "EXCEPTION_NON_HUMAN_AUTHORITY"),
        ("non_human_exception_owner", "EXCEPTION_NON_HUMAN_AUTHORITY"),
        ("expired_exception", "EXCEPTION_EXPIRED"),
        ("exception_evidence_reference", "EXCEPTION_EVIDENCE_MISSING"),
        ("missing_closure", "EXCEPTION_CLOSURE_EVIDENCE_MISSING"),
        ("unknown_closure", "EXCEPTION_CLOSURE_EVIDENCE_MISSING"),
    ],
)
def test_foundational_checks_fail_closed(
    mutation: str,
    expected: str,
    tmp_path: Path,
) -> None:
    document = _document(tmp_path)
    if mutation == "ai_approver":
        document["approvals"][0]["eligible_roles"].append("ai_tool")
    elif mutation == "missing_revision":
        document["approvals"][0].pop("revision_binding")
    elif mutation == "expired_approval":
        document["approvals"][0]["expires_at"] = "2026-05-01T00:00:00Z"
    elif mutation == "non_human_accountable":
        document["approvals"][0]["accountable_authority"] = "tool:approval_bot"
    elif mutation == "non_string_accountable":
        document["approvals"][0]["accountable_authority"] = 123
    elif mutation == "approval_evidence_reference":
        document["approvals"][0]["required_evidence"] = ["missing-approval-record"]
    elif mutation == "evidence_revision":
        document["governance_evidence"]["records"][0]["subject_revision"] = "other"
    elif mutation == "evidence_hash":
        document["governance_evidence"]["records"][0]["content_hash"] = "sha256:" + "0" * 64
    elif mutation == "evidence_stale":
        document["governance_evidence"]["records"][0]["expires_at"] = "2026-05-01T00:00:00Z"
    elif mutation == "evidence_dependency":
        document["governance_evidence"]["records"][0]["dependencies"] = ["missing"]
    elif mutation == "self_approval":
        document["separation_of_duties"]["assignments"][0]["approvers"] = ["user:author"]
    elif mutation == "producer_approval":
        document["separation_of_duties"]["assignments"][0]["approvers"] = ["tool:test_tool"]
    elif mutation == "non_human_sod_approver":
        document["separation_of_duties"]["assignments"][0]["approvers"] = [
            "tool:approval_bot"
        ]
    elif mutation == "release_conflict":
        document["separation_of_duties"]["assignments"][0]["final_release_approver"] = (
            "user:release_requester"
        )
    elif mutation == "core_exception":
        document["exceptions"]["entries"][0]["control"] = "pack_integrity"
    elif mutation == "self_exception":
        document["exceptions"]["entries"][0]["approving_authority"] = (
            "user:exception_requester"
        )
    elif mutation == "non_human_exception":
        document["exceptions"]["entries"][0]["approving_authority"] = (
            "tool:exception_bot"
        )
    elif mutation == "non_human_exception_owner":
        document["exceptions"]["entries"][0]["accountable_owner"] = (
            "system:risk_service"
        )
    elif mutation == "expired_exception":
        document["exceptions"]["entries"][0]["expires_at"] = "2026-05-15T00:00:00Z"
    elif mutation == "exception_evidence_reference":
        document["exceptions"]["entries"][0]["evidence"] = ["missing-exception-record"]
    elif mutation == "unknown_closure":
        document["exceptions"]["entries"][0]["status"] = "closed"
        document["exceptions"]["entries"][0]["closure_evidence"] = ["missing-closure-record"]
    else:
        document["exceptions"]["entries"][0]["status"] = "closed"

    assert expected in _codes(_diagnostics(document, tmp_path))


def test_selected_modules_enforce_required_blocks_and_schema_shape(tmp_path: Path) -> None:
    missing = {
        "nornyx": "0.2",
        "project": {"name": "Missing", "modules": ["evidence_integrity"]},
    }
    assert "GOVERNANCE_REQUIRED_BLOCK_MISSING" in _codes(_diagnostics(missing, tmp_path))

    malformed = _document(tmp_path)
    malformed["governance_evidence"]["records"][0]["artifact"] = "../outside.json"
    assert "GOVERNANCE_BLOCK_SCHEMA_INVALID" in _codes(_diagnostics(malformed, tmp_path))


@pytest.mark.parametrize(
    "mode",
    ["remote_ref", "ref_cycle", "nested_ref_cycle", "missing_local_ref"],
)
def test_governance_block_schema_subset_rejects_unsafe_references(
    mode: str,
    monkeypatch,
) -> None:
    from nornyx.governance import schemas

    schema_id = "https://nornyx.dev/schemas/adversarial.schema.json"
    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_id,
        "x-nornyx-governance-block": "adversarial",
        "type": "object",
    }
    if mode == "remote_ref":
        schema["$ref"] = "https://example.invalid/remote.schema.json"
        expected = "PACK_BLOCK_SCHEMA_REF_REJECTED"
    elif mode == "ref_cycle":
        schema["$defs"] = {
            "a": {"$ref": "#/$defs/b"},
            "b": {"$ref": "#/$defs/a"},
        }
        expected = "PACK_BLOCK_SCHEMA_REF_CYCLE"
    elif mode == "nested_ref_cycle":
        schema["$defs"] = {
            "a": {
                "type": "object",
                "properties": {"child": {"$ref": "#/$defs/b"}},
            },
            "b": {
                "type": "array",
                "items": {"$ref": "#/$defs/a"},
            },
        }
        expected = "PACK_BLOCK_SCHEMA_REF_CYCLE"
    else:
        schema["properties"] = {
            "missing": {"$ref": "#/$defs/not_declared"},
        }
        expected = "PACK_BLOCK_SCHEMA_REF_REJECTED"
    monkeypatch.setattr(schemas, "bundled_schema_catalog", lambda: {schema_id: schema})
    with pytest.raises(GovernanceError) as caught:
        validate_governance_block_schema("adversarial", schema_id)
    assert {item.code for item in caught.value.diagnostics} == {expected}


def test_foundational_validation_does_not_mutate_the_document(tmp_path: Path) -> None:
    document = _document(tmp_path)
    original = deepcopy(document)
    _diagnostics(document, tmp_path)
    assert document == original
