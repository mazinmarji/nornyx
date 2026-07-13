from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

import nornyx.governance as governance_api
from nornyx.governance import GovernanceRegistry, compose_governance
from nornyx.governance.approvals import (
    normalize_approval,
    trusted_normalized_approval,
)
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


def _ordinary_approval(**updates: Any) -> dict[str, Any]:
    approval: dict[str, Any] = {
        "name": "HumanGate",
        "required_roles": ["reviewer"],
        "eligible_roles": ["reviewer"],
        "denied_actor_types": [
            "ai_tool",
            "execution_surface",
            "autonomous_agent",
            "model",
            "connector",
            "generated_output",
        ],
        "required_evidence": ["approval_record"],
        "required_for": ["merge"],
        "accountable_authority": "user:owner",
        "revision_binding": {
            "kind": "git",
            "revision": "git:0123456789abcdef",
            "exact": True,
        },
        "invalidation_conditions": ["revision_changed"],
        "expires_at": "2027-01-01T00:00:00Z",
    }
    approval.update(updates)
    return approval


@pytest.mark.parametrize(
    "authority",
    [
        "ai_tool",
        "execution_surface",
        "autonomous_agent",
        "model",
        "connector",
        "generated_output",
        "tool:approval_bot",
        "agent:approval_bot",
        "autonomous_agent:approval_bot",
        "model:approval_model",
        "connector:approval_connector",
        "system:approval_service",
        "service:approval_service",
        "external_service:approval_service",
        "execution_surface:editor",
        "ToOl:Approval_Bot",
    ],
)
def test_aud003_non_human_accountable_authority_is_intrinsically_invalid(
    authority: str,
) -> None:
    normalized = normalize_approval(
        _ordinary_approval(accountable_authority=authority),
        shape="ordinary_approval",
        path="approvals[0]",
        fallback_id="approval-0",
    )

    assert normalized.resolution == "invalid"
    assert "APPROVAL_NON_HUMAN_AUTHORITY" in {
        item.code for item in normalized.diagnostics
    }
    assert trusted_normalized_approval(normalized.to_dict()) is None


def _normalized_gate() -> dict[str, Any]:
    return normalize_approval(
        {
            "id": "source_gate",
            "required_roles": ["reviewer"],
            "eligible_approver_roles": ["reviewer"],
            "required_evidence": ["approval_record"],
            "actions": ["merge"],
            "accountable_authority": "user:owner",
            "revision_binding": {
                "kind": "git",
                "revision": "git:0123456789abcdef",
                "exact": True,
            },
            "invalidation_conditions": ["revision_changed"],
        },
        shape="governed_package_gate",
        path="approvals[0]",
        fallback_id="approval-0",
    ).to_dict()


@pytest.mark.parametrize(
    "mutation",
    [
        "changed_id",
        "deleted_source_id",
        "conflicting_source_shape",
        "changed_source_path",
        "case_mutation",
        "whitespace_mutation",
        "unicode_confusable",
    ],
)
def test_aud004_normalized_identity_is_independently_derived(mutation: str) -> None:
    payload = _normalized_gate()
    assert trusted_normalized_approval(payload) is not None
    mutated = deepcopy(payload)

    if mutation == "changed_id":
        mutated["id"] = "HumanGovernanceGate"
    elif mutation == "deleted_source_id":
        del mutated["source"]["raw"]["id"]
    elif mutation == "conflicting_source_shape":
        mutated["source"]["shape"] = "ordinary_approval"
    elif mutation == "changed_source_path":
        mutated["source"]["path"] = "approvals[999]"
    elif mutation == "case_mutation":
        mutated["id"] = "SOURCE_GATE"
    elif mutation == "whitespace_mutation":
        mutated["id"] = " source_gate "
    else:
        mutated["id"] = "sourcе_gate"

    assert trusted_normalized_approval(mutated) is None


@pytest.mark.parametrize(
    "conditions",
    [
        [True],
        [7],
        [{"condition": "scope_changed"}],
        [""],
        ["   "],
        ["revision_changed", "revision_changed"],
    ],
)
def test_aud005_invalidation_conditions_never_coerce(
    conditions: list[object],
) -> None:
    normalized = normalize_approval(
        _ordinary_approval(invalidation_conditions=conditions),
        shape="ordinary_approval",
        path="approvals[0]",
        fallback_id="approval-0",
    )

    assert normalized.resolution == "invalid"
    assert "APPROVAL_INVALIDATION_CONDITION_INVALID" in {
        item.code for item in normalized.diagnostics
    }


def test_aud006_standalone_approval_must_match_governed_revision() -> None:
    document = _document()
    document["project"]["modules"] = ["human_approval"]
    document.pop("changes", None)
    document.pop("exceptions", None)
    document.pop("separation_of_duties", None)
    document["approvals"][0]["revision_binding"]["revision"] = "git:WRONG"

    assert "APPROVAL_REVISION_MISMATCH" in _codes(document)


@pytest.mark.parametrize(
    ("roles", "irreversible_authority", "expected"),
    [
        (["reviewer", "ai_tool"], None, "CHANGE_NON_HUMAN_APPROVER"),
        (["reviewer", "untrusted_role"], None, "CHANGE_APPROVER_ROLE_UNAUTHORIZED"),
        (["reviewer", "ai_tool"], "ai_tool", "CHANGE_NON_HUMAN_AUTHORITY"),
    ],
)
def test_aud007_high_risk_change_roles_are_a_strict_human_subset(
    roles: list[str],
    irreversible_authority: str | None,
    expected: str,
) -> None:
    document = _document()
    change = document["changes"][0]
    change["approver_roles"] = roles
    if irreversible_authority is not None:
        change["reversibility"] = "irreversible"
        change["irreversible_authority"] = irreversible_authority
        change["rollback_required"] = True
        change["rollback_plan_artifact"] = "artifact:rollback-plan"

    assert expected in _codes(document)


def test_aud012_effective_approvals_are_independently_verifiable() -> None:
    verifier = getattr(governance_api, "trusted_effective_approval", None)
    assert callable(verifier), "effective approvals require a dedicated public verifier"
    composition = compose_governance(
        GovernanceRegistry.builtins(),
        profile_identity="architecture_governance",
    )
    payloads = composition.to_dict()["approval_requirements"]
    assert payloads
    for payload in payloads:
        assert verifier(payload) is not None
        tampered = deepcopy(payload)
        tampered["eligible_roles"] = ["untrusted_role"]
        assert verifier(tampered) is None
