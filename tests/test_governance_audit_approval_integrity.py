from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
from itertools import permutations
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import nornyx.governance as governance_api
from nornyx.governance import (
    GovernanceError,
    GovernanceRegistry,
    Rule,
    compose_governance,
    load_pack_bytes,
)
from nornyx.governance.approvals import (
    compose_effective_approval,
    normalize_approval,
    trusted_effective_approval,
    trusted_normalized_approval,
)
from nornyx.governance.models import immutable_mapping
from nornyx.governance.runtime import evaluate_document_governance
from nornyx.governance.rules import evaluate_rule
from nornyx.governance.schemas import canonical_pack_hash, validate_payload


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


@pytest.mark.parametrize("authority", [7, True, {}, [], "", "   "])
def test_aud003_accountable_authority_requires_a_nonempty_source_string(
    authority: object,
) -> None:
    normalized = normalize_approval(
        _ordinary_approval(accountable_authority=authority),
        shape="ordinary_approval",
        path="approvals[0]",
        fallback_id="approval-0",
    )

    assert normalized.resolution == "invalid"
    assert "APPROVAL_ACCOUNTABLE_AUTHORITY_INVALID" in {
        item.code for item in normalized.diagnostics
    }


def _pack_with_authority(authority: str) -> dict[str, Any]:
    payload = yaml.safe_load(
        (
            ROOT
            / "tests"
            / "fixtures"
            / "governance_extension"
            / "valid_module_v1.yaml"
        ).read_text(encoding="utf-8")
    )
    payload["approval_requirements"] = [
        {
            "id": "human_gate",
            "required_roles": ["reviewer"],
            "eligible_roles": ["reviewer"],
            "denied_actor_types": ["ai_tool"],
            "required_evidence": ["review_record"],
            "actions": ["merge"],
            "timing": "before_merge",
            "accountable_authority": authority,
        }
    ]
    payload["integrity"]["content_hash"] = canonical_pack_hash(payload)
    return payload


def test_aud003_source_pack_loading_rejects_non_human_authority() -> None:
    payload = _pack_with_authority("ai_tool")

    with pytest.raises(GovernanceError) as captured:
        load_pack_bytes(
            yaml.safe_dump(payload, sort_keys=False).encode("utf-8"),
            source_path="bad-authority.yaml",
            source_tier="project",
        )

    assert "APPROVAL_NON_HUMAN_AUTHORITY" in {
        item.code for item in captured.value.diagnostics
    }


def test_aud003_composition_rejects_programmatic_non_human_authority() -> None:
    builtin = GovernanceRegistry.builtins().resolve_module("human_approval")
    source = deepcopy(dict(builtin.approval_requirements[0]))
    source["accountable_authority"] = "tool:approval_bot"
    bad = replace(
        builtin,
        id="org.example.bad_authority",
        name="bad_authority",
        dependencies=(),
        approval_requirements=(immutable_mapping(source),),
        provenance=replace(
            builtin.provenance,
            source_tier="project",
            source_path="bad-authority.yaml",
        ),
    )
    registry = GovernanceRegistry()
    registry.register_module(bad)

    with pytest.raises(GovernanceError) as captured:
        compose_governance(
            registry,
            profile_identity=None,
            module_ids=[bad.id],
        )

    assert "APPROVAL_NON_HUMAN_AUTHORITY" in {
        item.code for item in captured.value.diagnostics
    }


def test_aud003_document_evaluation_preserves_specific_authority_failure() -> None:
    document = _document()
    document["project"]["modules"] = ["human_approval"]
    document["approvals"][0]["accountable_authority"] = "service:approval_bot"

    assert "APPROVAL_NON_HUMAN_AUTHORITY" in _codes(document)


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
    ).to_verifiable_dict()


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


def _bind_source(source: dict[str, Any]) -> None:
    unsigned = {key: value for key, value in source.items() if key != "binding"}
    encoded = json.dumps(
        unsigned,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    source["binding"] = "sha256:" + hashlib.sha256(encoded).hexdigest()


def test_aud004_missing_identity_uses_one_path_derived_fallback() -> None:
    raw = {
        "eligible_roles": ["reviewer"],
        "required_evidence": ["review_record"],
    }
    first = normalize_approval(
        raw,
        shape="ordinary_approval",
        path="approvals[4]",
        fallback_id="human_gate",
    ).to_verifiable_dict()
    second = normalize_approval(
        raw,
        shape="ordinary_approval",
        path="approvals[4]",
        fallback_id="release_owner",
    ).to_verifiable_dict()

    assert first == second
    assert first["id"] == first["source"]["fallback_id"]
    forged = deepcopy(first)
    forged["id"] = "release_owner"
    forged["source"]["fallback_id"] = "release_owner"
    _bind_source(forged["source"])
    assert trusted_normalized_approval(forged) is None


def test_aud004_legacy_serializer_and_schema_remain_base_compatible() -> None:
    source = _ordinary_approval()
    source["revision_binding"]["scope_hash"] = "sha256:" + "0" * 64
    normalized = normalize_approval(
        source,
        shape="ordinary_approval",
        path="approvals[0]",
        fallback_id="approval-0",
    )
    payload = normalized.to_dict()

    validate_payload(payload, "governance_approval_model_v1.schema.json")
    assert payload["schema"] == "nornyx.normalized_approval.v1"
    assert "exact_revision_required" not in payload
    assert "expires_after" not in payload
    assert "scope_hash" not in payload["revision_binding"]
    assert normalized.to_verifiable_dict()["revision_binding"]["scope_hash"] == (
        "sha256:" + "0" * 64
    )
    assert trusted_normalized_approval(payload) is not None


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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("eligible_roles", [7]),
        ("required_evidence", [{"id": "review_record"}]),
        ("actions_requiring_approval", [True]),
    ],
)
def test_aud005_adjacent_approval_authority_values_never_coerce(
    field: str,
    value: list[object],
) -> None:
    normalized = normalize_approval(
        _ordinary_approval(**{field: value}),
        shape="ordinary_approval",
        path="approvals[0]",
        fallback_id="approval-0",
    )

    assert normalized.resolution == "invalid"
    assert "APPROVAL_VALUE_TYPE_INVALID" in {
        item.code for item in normalized.diagnostics
    }


def test_aud005_subject_revision_and_exception_authority_never_coerce() -> None:
    document = _document()
    document["project"]["modules"].append("exception_management")
    document["governance_evidence"]["subject_revision"] = 7
    document["exceptions"]["entries"][0]["approving_authority"] = {
        "role": "exception_approver"
    }

    codes = _codes(document)
    assert "APPROVAL_GOVERNED_REVISION_INVALID" in codes
    assert "EXCEPTION_AUTHORITY_INVALID" in codes


def test_aud006_standalone_approval_must_match_governed_revision() -> None:
    document = _document()
    document["project"]["modules"] = ["human_approval"]
    document.pop("changes", None)
    document.pop("exceptions", None)
    document.pop("separation_of_duties", None)
    document["approvals"][0]["revision_binding"]["revision"] = "git:WRONG"

    assert "APPROVAL_REVISION_MISMATCH" in _codes(document)


def _human_only_document() -> dict[str, Any]:
    document = _document()
    document["project"]["modules"] = ["human_approval"]
    document.pop("changes", None)
    document.pop("exceptions", None)
    document.pop("separation_of_duties", None)
    return document


def test_aud006_matching_standalone_revision_is_accepted() -> None:
    document = _human_only_document()

    assert "APPROVAL_REVISION_MISMATCH" not in _codes(document)
    assert "APPROVAL_GOVERNED_REVISION_CONFLICT" not in _codes(document)


def test_aud006_missing_governed_revision_fails_closed() -> None:
    document = _human_only_document()
    document["governance_evidence"].pop("subject_revision")

    assert "APPROVAL_GOVERNED_REVISION_MISSING" in _codes(document)


def test_aud006_conflicting_evidence_revision_fails_closed() -> None:
    document = _human_only_document()
    document["governance_evidence"]["records"][0]["subject_revision"] = "git:WRONG"

    assert "APPROVAL_GOVERNED_REVISION_CONFLICT" in _codes(document)


def test_aud006_multiple_approvals_cannot_span_governed_revisions() -> None:
    document = _human_only_document()
    second = deepcopy(document["approvals"][0])
    second["name"] = "OtherRevisionGate"
    second["revision_binding"]["revision"] = "git:OTHER"
    document["approvals"].append(second)

    assert "APPROVAL_REVISION_MISMATCH" in _codes(document)


def test_aud006_change_scope_hash_must_match_same_approval() -> None:
    document = _document()
    document["approvals"][0]["revision_binding"]["scope_hash"] = "sha256:" + "0" * 64

    assert "APPROVAL_STALE_FOR_SCOPE" in _codes(document)


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


@pytest.mark.parametrize(
    ("roles", "expected"),
    [
        (["security_reviewer"], "CHANGE_APPROVER_ROLE_UNAUTHORIZED"),
        (["reviewer", "reviewer"], "CHANGE_APPROVER_ROLE_INVALID"),
        (["reviewer", 7], "CHANGE_APPROVER_ROLE_INVALID"),
        (["reviewer", {"role": "owner"}], "CHANGE_APPROVER_ROLE_INVALID"),
        ([" reviewer"], "CHANGE_APPROVER_ROLE_INVALID"),
    ],
)
def test_aud007_required_duplicate_and_malformed_change_roles_fail(
    roles: list[object],
    expected: str,
) -> None:
    document = _document()
    document["changes"][0]["approver_roles"] = roles

    assert expected in _codes(document)


def test_aud007_irreversible_authority_must_be_eligible() -> None:
    document = _document()
    change = document["changes"][0]
    change["approver_roles"] = ["reviewer", "untrusted_role"]
    change["reversibility"] = "irreversible"
    change["irreversible_authority"] = "untrusted_role"
    change["rollback_required"] = True
    change["rollback_plan_artifact"] = "artifact:rollback-plan"

    codes = _codes(document)
    assert "CHANGE_APPROVER_ROLE_UNAUTHORIZED" in codes
    assert "CHANGE_IRREVERSIBLE_AUTHORITY_UNAUTHORIZED" in codes


def test_aud007_valid_human_high_risk_authority_remains_accepted() -> None:
    document = _document()
    change = document["changes"][0]
    change["reversibility"] = "irreversible"
    change["irreversible_authority"] = "reviewer"
    change["rollback_required"] = True
    change["rollback_plan_artifact"] = "artifact:rollback-plan"

    codes = _codes(document)
    assert "CHANGE_APPROVER_ROLE_UNAUTHORIZED" not in codes
    assert "CHANGE_NON_HUMAN_AUTHORITY" not in codes
    assert "CHANGE_IRREVERSIBLE_AUTHORITY_UNAUTHORIZED" not in codes


def test_aud012_effective_approvals_are_independently_verifiable() -> None:
    verifier = getattr(governance_api, "trusted_effective_approval", None)
    assert callable(verifier), "effective approvals require a dedicated public verifier"
    composition = compose_governance(
        GovernanceRegistry.builtins(),
        profile_identity="architecture_governance",
    )
    effective_output = composition.to_effective_dict()
    validate_payload(effective_output, "effective_governance_v2.schema.json")
    payloads = effective_output["approval_requirements"]
    assert payloads
    for approval, payload in zip(
        composition.approval_requirements,
        payloads,
        strict=True,
    ):
        assert approval.effective_approval is not None
        assert approval.effective_approval.to_dict() == payload
        assert verifier(payload) is not None
        tampered = deepcopy(payload)
        tampered["eligible_roles"] = ["untrusted_role"]
        assert verifier(tampered) is None


def test_aud012_nonbuiltin_effective_approval_requires_its_registry() -> None:
    pack = load_pack_bytes(
        yaml.safe_dump(
            _pack_with_authority("owner"),
            sort_keys=False,
        ).encode("utf-8"),
        source_path="project-module.yaml",
        source_tier="project",
    )
    registry = GovernanceRegistry()
    registry.register_module(pack)
    output = compose_governance(
        registry,
        profile_identity=None,
        module_ids=[pack.id],
    ).to_effective_dict()
    effective = output["approval_requirements"][0]

    assert trusted_effective_approval(effective) is None
    assert trusted_effective_approval(effective, registry=registry) is not None


def test_aud012_forged_builtin_lineage_is_not_self_authenticating() -> None:
    genuine = compose_governance(
        GovernanceRegistry.builtins(),
        profile_identity="architecture_governance",
    ).to_effective_dict()["approval_requirements"][0]
    source_record = genuine["sources"][0]
    provenance = deepcopy(source_record["provenance"])
    forged_raw = deepcopy(source_record["approval"]["source"]["raw"])
    forged_raw["required_evidence"] = [
        *forged_raw.get("required_evidence", []),
        "forged_evidence",
    ]
    forged_leaf = normalize_approval(
        forged_raw,
        shape="generated_profile_approval",
        path=provenance["approval_path"],
        fallback_id="ignored-by-v2",
    )
    forged = compose_effective_approval([(forged_leaf, provenance)]).to_dict()

    assert trusted_effective_approval(forged) is None


def test_aud012_document_rules_reject_effective_reporting_artifacts() -> None:
    effective = compose_governance(
        GovernanceRegistry.builtins(),
        profile_identity="architecture_governance",
    ).to_effective_dict()["approval_requirements"][0]
    rule = Rule.from_dict(
        {
            "id": "AUD-012",
            "description": "Effective reporting artifacts need registry context.",
            "require": [{"path": "approvals", "references_role": "architecture_owner"}],
            "severity": "error",
            "message": "untrusted effective approval",
        },
        source_id="test.audit",
    )

    diagnostics = evaluate_rule({"approvals": [effective]}, rule)
    assert [item.code for item in diagnostics] == ["RULE_REFERENCE_TYPE_ERROR"]


def test_aud012_public_verifiers_fail_closed_on_excessive_depth() -> None:
    nested: dict[str, Any] = {}
    for _ in range(10_000):
        nested = {"next": nested}

    assert trusted_normalized_approval(
        {"schema": "nornyx.normalized_approval.v2", "nested": nested}
    ) is None
    assert trusted_effective_approval(
        {"schema": "nornyx.effective_approval.v1", "nested": nested}
    ) is None


@pytest.mark.parametrize(
    "mutation",
    [
        "source_raw",
        "source_hash",
        "source_path",
        "source_order",
        "operation",
        "decisions",
        "result",
        "duplicate_source",
    ],
)
def test_aud012_effective_approval_mutation_matrix(mutation: str) -> None:
    payload = next(
        item
        for item in compose_governance(
            GovernanceRegistry.builtins(),
            profile_identity="architecture_governance",
        ).to_effective_dict()["approval_requirements"]
        if item["id"] == "architecture_authority"
    )
    assert len(payload["sources"]) == 2
    mutated = deepcopy(payload)
    if mutation == "source_raw":
        mutated["sources"][0]["approval"]["source"]["raw"]["required_roles"] = []
    elif mutation == "source_hash":
        mutated["sources"][0]["hash"] = "sha256:" + "0" * 64
    elif mutation == "source_path":
        mutated["sources"][0]["provenance"]["approval_path"] = "forged[0]"
    elif mutation == "source_order":
        mutated["sources"].reverse()
    elif mutation == "operation":
        mutated["operation"] = "union"
    elif mutation == "decisions":
        mutated["decisions"]["eligible_roles"] = "union"
    elif mutation == "result":
        mutated["required_evidence"] = []
    else:
        duplicate = deepcopy(mutated["sources"][0])
        duplicate["position"] = len(mutated["sources"])
        mutated["sources"].append(duplicate)
        mutated["decisions"]["source_order"].append(
            duplicate["provenance"]["approval_path"]
        )

    assert trusted_effective_approval(mutated) is None


def _effective_source(
    index: int,
    eligible_roles: list[str],
    *,
    required_roles: list[str] | None = None,
) -> tuple[Any, dict[str, Any]]:
    source_id = f"org.example.layer{index}"
    path = f"{source_id}.approval_requirements[0]"
    normalized = normalize_approval(
        {
            "id": "shared_gate",
            "required_roles": required_roles or [],
            "eligible_roles": eligible_roles,
            "required_evidence": [f"evidence_{index}"],
            "actions": ["merge"],
            "accountable_authority": "user:owner",
            "exact_revision_required": index == 0,
            "invalidation_conditions": ["revision_changed"],
            "expires_after": "PT24H",
        },
        shape="generated_profile_approval",
        path=path,
        fallback_id="shared_gate",
    )
    provenance = {
        "source_id": source_id,
        "source_kind": "module",
        "source_version": "1.0.0",
        "source_tier": "project",
        "source_path": f"{source_id}.yaml",
        "approval_path": path,
        "source_index": 0,
        "content_hash": "sha256:" + f"{index + 1:064x}",
    }
    return normalized, provenance


def test_aud012_provenance_id_index_and_path_must_agree() -> None:
    normalized, provenance = _effective_source(0, ["reviewer"])
    provenance["source_id"] = "org.example.claimed"

    with pytest.raises(GovernanceError) as captured:
        compose_effective_approval([(normalized, provenance)])

    assert "PACK_APPROVAL_PROVENANCE_INVALID" in {
        item.code for item in captured.value.diagnostics
    }


def test_aud012_composer_rejects_duplicate_source_leaves() -> None:
    source = _effective_source(0, ["reviewer"])

    with pytest.raises(GovernanceError) as captured:
        compose_effective_approval([source, source])

    assert "PACK_APPROVAL_PROVENANCE_INVALID" in {
        item.code for item in captured.value.diagnostics
    }


def test_aud012_one_pack_index_cannot_claim_two_different_leaves() -> None:
    first, provenance = _effective_source(0, ["reviewer"])
    second_raw = deepcopy(first.source_raw)
    second_raw["required_evidence"] = ["different_evidence"]
    second = normalize_approval(
        second_raw,
        shape=first.source_shape,
        path=first.source_path,
        fallback_id="shared_gate",
    )

    with pytest.raises(GovernanceError) as captured:
        compose_effective_approval(
            [(first, provenance), (second, deepcopy(provenance))]
        )

    assert "PACK_APPROVAL_PROVENANCE_INVALID" in {
        item.code for item in captured.value.diagnostics
    }


def test_aud012_source_limit_stops_consuming_the_generator() -> None:
    yielded: list[int] = []

    def sources() -> Any:
        for index in range(100):
            yielded.append(index)
            yield _effective_source(index, ["reviewer"])

    with pytest.raises(GovernanceError) as captured:
        compose_effective_approval(sources())

    assert yielded == list(range(33))
    assert "PACK_APPROVAL_SOURCE_LIMIT_EXCEEDED" in {
        item.code for item in captured.value.diagnostics
    }


def test_aud012_three_layer_composition_is_deterministic_and_monotonic() -> None:
    sources = [
        _effective_source(0, ["reviewer", "security", "owner"], required_roles=["reviewer"]),
        _effective_source(1, ["reviewer", "security"]),
        _effective_source(2, ["reviewer", "auditor"]),
    ]

    payloads = {
        yaml.safe_dump(
            compose_effective_approval(order).to_dict(),
            sort_keys=True,
        )
        for order in permutations(sources)
    }

    assert len(payloads) == 1
    effective = compose_effective_approval(sources)
    assert effective.eligible_roles == ("reviewer",)
    assert effective.required_roles == ("reviewer",)
    assert effective.exact_revision_required is True
    assert effective.expires_after == "PT24H"
    assert trusted_effective_approval(effective.to_dict()) is None


def test_aud012_empty_eligibility_never_broadens_a_restriction() -> None:
    restricted = _effective_source(0, ["reviewer", "security"])
    empty = _effective_source(1, [])

    effective = compose_effective_approval([empty, restricted])

    assert effective.eligible_roles == ("reviewer", "security")


def test_aud012_disjoint_nonempty_sets_fail_even_with_an_empty_layer() -> None:
    sources = [
        _effective_source(0, ["reviewer"]),
        _effective_source(1, []),
        _effective_source(2, ["security"]),
    ]

    with pytest.raises(GovernanceError) as captured:
        compose_effective_approval(sources)

    assert "PACK_MONOTONICITY_APPROVAL" in {
        item.code for item in captured.value.diagnostics
    }


def test_aud012_required_role_excluded_by_another_layer_fails() -> None:
    sources = [
        _effective_source(0, ["reviewer", "security"], required_roles=["security"]),
        _effective_source(1, ["reviewer"]),
    ]

    with pytest.raises(GovernanceError, match="excluded by another layer"):
        compose_effective_approval(sources)
