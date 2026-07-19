from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
import re
from typing import Any

import pytest
from jsonschema import Draft202012Validator

import nornyx.governance as governance
from nornyx.governance.models import (
    CompositionResult,
    GovernanceDiagnostic,
    GovernanceModule,
    NormalizedApproval,
    PackProvenance,
)
from nornyx.governed_package import validate_governed_package
from nornyx.governance.schemas import validate_governance_block
from nornyx.parser import load_nyx


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "governance_compatibility"
LEGACY_CHANGE_SCHEMA = {
    "type": "object",
    "required": ["id", "type"],
    "properties": {
        "id": {"type": "string"},
        "type": {"type": "string"},
        "expected_artifacts": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "additionalProperties": True,
}
BASE_PUBLIC_GOVERNANCE_EXPORTS = {
    "CompositionResult",
    "GovernanceDiagnostic",
    "GovernanceError",
    "GovernanceModule",
    "GovernanceRegistry",
    "LockEntry",
    "NormalizedApproval",
    "ProfileLock",
    "ProfilePack",
    "ProjectionResult",
    "Rule",
    "StarterFragment",
    "compose_document_governance",
    "compose_governance",
    "evaluate_document_governance",
    "evaluate_rule",
    "evaluate_rules",
    "load_local_pack",
    "load_lock",
    "load_pack_bytes",
    "lock_for_packs",
    "normalize_approval",
    "project_profile_to_v03",
    "registry_for_contract",
    "registry_for_directory",
    "verify_lock",
    "write_lock",
}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "change with spaces"),
        ("type", "schema migration"),
        ("id", "_legacy_change"),
        ("id", "évolution"),
        ("type", "migration/phase one"),
    ],
)
def test_aud015_governed_package_legacy_change_strings_remain_valid(
    field: str,
    value: str,
) -> None:
    package = load_nyx(ROOT / "examples" / "governed_package" / "basic.nyx")[
        "governed_package"
    ]
    package["changes"][0][field] = value

    assert "INVALID_GOVERNED_PACKAGE_CHANGE" not in {
        item.code for item in validate_governed_package(package) if item.level == "error"
    }


@pytest.mark.parametrize(
    "value",
    [
        "",
        " ",
        "\t",
        "-leading",
        ".leading",
        "évolution",
        "变化",
        "🔒",
        "with embedded\nnewline",
        "x" * 2049,
    ],
)
@pytest.mark.parametrize("field", ["id", "type"])
def test_aud015_head_matches_base_string_domain(field: str, value: str) -> None:
    change = {
        "id": "legacy-id",
        "type": "legacy-type",
        "expected_artifacts": ["", "artifact with spaces", "产物"],
        "schema": "nornyx.change.v1",
        "status": {"legacy_extension": True},
        "scope": "legacy free-form extension",
    }
    change[field] = value
    assert Draft202012Validator(LEGACY_CHANGE_SCHEMA).is_valid(change)

    package = deepcopy(
        load_nyx(ROOT / "examples" / "governed_package" / "basic.nyx")[
            "governed_package"
        ]
    )
    package["changes"] = [change]
    errors = {
        item.code for item in validate_governed_package(package) if item.level == "error"
    }
    assert "INVALID_GOVERNED_PACKAGE_CHANGE" not in errors


@pytest.mark.parametrize(
    "change",
    [
        {},
        {"id": "only-id"},
        {"type": "only-type"},
        {"id": 1, "type": "change"},
        {"id": True, "type": "change"},
        {"id": [], "type": "change"},
        {"id": {}, "type": "change"},
        {"id": "change", "type": 1},
        {"id": "change", "type": "type", "expected_artifacts": "artifact"},
        {"id": "change", "type": "type", "expected_artifacts": [1]},
        [],
        True,
    ],
)
def test_aud015_head_matches_base_rejection_domain(change: Any) -> None:
    assert not Draft202012Validator(LEGACY_CHANGE_SCHEMA).is_valid(change)
    package = deepcopy(
        load_nyx(ROOT / "examples" / "governed_package" / "basic.nyx")[
            "governed_package"
        ]
    )
    package["changes"] = [change]
    assert "INVALID_GOVERNED_PACKAGE_CHANGE" in {
        item.code for item in validate_governed_package(package) if item.level == "error"
    }


def test_aud015_seeded_base_vs_head_string_differential() -> None:
    rng = random.Random(1502)
    alphabet = "abZ09 _-./:@\té变化🔒"
    template = load_nyx(ROOT / "examples" / "governed_package" / "basic.nyx")[
        "governed_package"
    ]
    validator = Draft202012Validator(LEGACY_CHANGE_SCHEMA)

    for _ in range(250):
        value = "".join(rng.choice(alphabet) for _ in range(rng.randrange(0, 300)))
        for field in ("id", "type"):
            change = {
                "id": "legacy-id",
                "type": "legacy-type",
                "expected_artifacts": ["", value],
                "arbitrary_extension": {"retained": [True, None, 7]},
            }
            change[field] = value
            assert validator.is_valid(change)
            package = deepcopy(template)
            package["changes"] = [change]
            assert "INVALID_GOVERNED_PACKAGE_CHANGE" not in {
                item.code
                for item in validate_governed_package(package)
                if item.level == "error"
            }


def test_aud015_generalized_change_schema_remains_strict_when_selected() -> None:
    diagnostics = validate_governance_block(
        "changes",
        [{"id": "legacy id", "type": "schema migration"}],
        "https://nornyx.dev/schemas/change_v1.schema.json",
        source_id="test.change_control",
    )
    assert {item.code for item in diagnostics} == {"GOVERNANCE_BLOCK_SCHEMA_INVALID"}


def test_aud015_governed_package_schema_mirrors_pin_the_base_oracle() -> None:
    for path in (
        ROOT / "schemas" / "governed_package.schema.json",
        ROOT / "nornyx" / "schemas" / "governed_package.schema.json",
    ):
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["properties"]["changes"]["items"] == LEGACY_CHANGE_SCHEMA


def _base_module() -> GovernanceModule:
    return GovernanceModule(
        id="org.example.module",
        name="module",
        version="1.0.0",
        compatible_core=">=1.0,<2.0",
        dependencies=(),
        conflicts=(),
        required_blocks=(),
        policies=(),
        evidence_requirements=(),
        approval_requirements=(),
        evaluations=(),
        rules=(),
        non_goals=(),
        provenance=PackProvenance("human", "project", "git:base", "module.yaml"),
        content_hash="sha256:" + "0" * 64,
        raw={},
    )


def _base_approval() -> NormalizedApproval:
    return NormalizedApproval(
        id="HumanGate",
        required_roles=("reviewer",),
        eligible_roles=("reviewer",),
        denied_actor_types=("ai_tool",),
        denied_execution_surfaces=("execution_surface",),
        required_evidence=("review",),
        actions_requiring_approval=("merge",),
        timing="before_merge",
        accountable_authority="user:owner",
        revision_binding=None,
        invalidation_conditions=("revision_changed",),
        expires_at=None,
        resolution="complete",
        diagnostics=(),
        source_shape="ordinary_approval",
        source_path="approvals[0]",
        source_raw={"name": "HumanGate"},
        role_field="eligible_roles",
    )


def _base_composition() -> CompositionResult:
    return CompositionResult(
        profile=None,
        modules=(),
        required_blocks=(),
        policies=(),
        evidence_requirements=(),
        approval_requirements=(),
        evaluations=(),
        rules=(),
        non_goals=(),
        starter_fragments=(),
        provenance=(),
    )


@pytest.mark.parametrize(
    "factory",
    [_base_module, _base_approval, _base_composition],
)
def test_aud016_base_public_dataclass_constructors_remain_valid(
    factory: Any,
) -> None:
    assert factory() is not None


def test_aud016_base_serialization_shapes_remain_available() -> None:
    approval_keys = set(_base_approval().to_dict())
    assert "exact_revision_required" not in approval_keys
    assert "expires_after" not in approval_keys

    composition_keys = set(_base_composition().to_dict())
    assert "block_schemas" not in composition_keys
    assert "structural_checks" not in composition_keys


def test_aud016_base_positional_constructor_prefixes_remain_valid() -> None:
    module = GovernanceModule(
        "org.example.module",
        "module",
        "1.0.0",
        ">=1.0,<2.0",
        (),
        (),
        (),
        (),
        (),
        (),
        (),
        (),
        (),
        PackProvenance("human", "project", "git:base", "module.yaml"),
        "sha256:" + "0" * 64,
        {},
    )
    approval = NormalizedApproval(
        "HumanGate",
        ("reviewer",),
        ("reviewer",),
        ("ai_tool",),
        ("execution_surface",),
        ("review",),
        ("merge",),
        "before_merge",
        "user:owner",
        None,
        ("revision_changed",),
        None,
        "complete",
        (),
        "ordinary_approval",
        "approvals[0]",
        {"name": "HumanGate"},
        "eligible_roles",
    )
    composition = CompositionResult(
        None,
        (module,),
        (),
        (),
        (),
        (approval,),
        (),
        (),
        (),
        (),
        (),
    )

    assert module.block_schemas == () and module.structural_checks == ()
    assert approval.exact_revision_required is None and approval.expires_after is None
    assert composition.block_schemas is None and composition.structural_checks is None


def test_aud016_base_serialized_payloads_are_exactly_preserved() -> None:
    assert _base_approval().to_dict() == {
        "schema": "nornyx.normalized_approval.v1",
        "id": "HumanGate",
        "required_roles": ["reviewer"],
        "eligible_roles": ["reviewer"],
        "denied_actor_types": ["ai_tool"],
        "denied_execution_surfaces": ["execution_surface"],
        "required_evidence": ["review"],
        "actions_requiring_approval": ["merge"],
        "timing": "before_merge",
        "accountable_authority": "user:owner",
        "revision_binding": None,
        "invalidation_conditions": ["revision_changed"],
        "expires_at": None,
        "resolution": "complete",
        "normalization_diagnostics": [],
        "source": {
            "shape": "ordinary_approval",
            "path": "approvals[0]",
            "raw": {"name": "HumanGate"},
            "role_field": "eligible_roles",
        },
    }
    assert _base_composition().to_dict() == {
        "schema": "nornyx.effective_governance.v1",
        "profile": None,
        "modules": [],
        "required_blocks": [],
        "policies": [],
        "evidence_requirements": [],
        "approval_requirements": [],
        "evaluations": [],
        "rules": [],
        "non_goals": [],
        "starter_fragments": [],
        "provenance": [],
        "diagnostics": [],
    }


def test_aud016_base_nested_values_and_diagnostics_are_preserved() -> None:
    revision_binding = {
        "kind": "git",
        "revision": "base-revision",
        "exact": True,
        "scope_hash": "sha256:" + "a" * 64,
        "consumer_extension": {"retained": [1, True, None]},
    }
    approval = replace(
        _base_approval(),
        revision_binding=revision_binding,
        diagnostics=(
            GovernanceDiagnostic(
                "warning",
                "APPROVAL_BASE_CONSUMER_WARNING",
                "retained diagnostic",
                "approvals[0]",
                "consumer",
            ),
        ),
        source_raw={"name": "HumanGate", "nested": {"retained": ["value"]}},
    )

    payload = approval.to_dict()
    assert payload["revision_binding"] == revision_binding
    assert payload["normalization_diagnostics"] == [
        {
            "level": "warning",
            "code": "APPROVAL_BASE_CONSUMER_WARNING",
            "message": "retained diagnostic",
        }
    ]
    assert payload["source"]["raw"] == {
        "name": "HumanGate",
        "nested": {"retained": ["value"]},
    }

    extended = replace(approval, exact_revision_required=True)
    assert "scope_hash" not in extended.to_dict()["revision_binding"]
    assert extended.to_verifiable_dict()["revision_binding"]["scope_hash"] == (
        revision_binding["scope_hash"]
    )


def test_aud016_base_public_exports_are_not_removed() -> None:
    assert BASE_PUBLIC_GOVERNANCE_EXPORTS <= set(governance.__all__)


def test_aud017_current_docs_state_exact_evidence_and_authorization_boundary() -> None:
    markdown_paths = [
        ROOT / "docs" / "planning" / "governance-extension" / name
        for name in (
            "12_IMPLEMENTATION_ROADMAP.md",
            "15_CURRENT_IMPLEMENTATION_INVENTORY.md",
            "19_COMPATIBILITY_REPORT.md",
            "20_SECURITY_ASSURANCE_REPORT.md",
            "21_PROGRAM_CLOSURE_REPORT.md",
            "22_FINAL_INDEPENDENT_AUDIT.md",
        )
    ] + [ROOT / "docs" / "releases" / "RELEASE_CANDIDATE_GOVERNANCE_PROGRAM.md"]

    audited_base = "95952226999327458c6fea81cb32d82539bcae5b"
    original_candidate = "35ee69359599af7887f6b9b58ae0a4cd06a48d25"
    implementation_anchor = "81899aaac5e54781dfe9c8002f557a874854c8b8"
    historical_ci_candidate = "3a0e840c3229dbf58959df1e3a161318bffd94ac"
    residual_code_commit = "1319613697b0e94d177ebe2c879f73107c366c7e"
    reopened_ids = ("AUD-011-R1", "AUD-017-R1", "AUD-021-R1", "PRMETA-001")
    forbidden_current_state_claims = (
        "remote head remains the failing candidate",
        "still at the old remote head",
        "not been pushed",
        "pending authorized push",
        "no hosted linux ci result exists",
        "no current-head hosted ci result is claimed",
        "old ci is the latest result",
        "ready for a fresh independent read-only audit",
        "final local candidate",
        "29273126271",
    )
    forbidden_current_state_patterns = (
        r"\bremote\s+(?:pr\s+)?head[\s\S]{0,80}\b(?:remains|is|still\s+at)\b"
        r"[\s\S]{0,80}\b35ee693",
        r"\b(?:branch|remediation|candidate|head)\b[\s\S]{0,80}"
        r"\b(?:unpush(?:ed)?|not\s+(?:been\s+)?pushed)\b",
        r"\b(?:no\s+)?(?:current-head\s+)?hosted(?:\s+linux)?"
        r"(?:\s+ci|\s+run|\s+result)?[\s\S]{0,80}"
        r"\b(?:does\s+not\s+exist|has\s+not\s+(?:been\s+)?run|"
        r"is\s+unavailable|not\s+available|pending\s+authorized\s+push)\b",
        r"\bcurrent(?:-state|-head)?(?:\s+audit)?\s+verdict\s*"
        r"(?::|=|\bis\b)\s*[`*]*GO\b",
        r"(?m)^\s*status\s*:\s*(?:\*\*)?\s*GO\b",
        r"\bold\s+(?:hosted\s+)?ci[\s\S]{0,50}\b(?:latest|current)\b",
    )

    for path in markdown_paths:
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        assert "## Audit Evidence History" in text, path
        prefix, history_tail = text.split("## Audit Evidence History", 1)
        history, separator, remainder = history_tail.partition("\n## ")
        assert separator, path
        current_state_text = prefix + separator + remainder
        assert "conclusion `success`" in history, path
        assert "returned historical `NO-GO`" in history, path
        assert audited_base in text, path
        assert original_candidate in text, path
        assert implementation_anchor in text, path
        assert historical_ci_candidate in text, path
        assert residual_code_commit in text, path
        assert "29373272295" in text, path
        assert "913 passed, 45 skipped" in text, path
        assert "958 passed, zero skipped" in text, path
        assert "network_attempts=[]" in text and "network_used=false" in text, path
        assert all(reopened_id in text for reopened_id in reopened_ids), path
        assert "not the final approved" in lowered, path
        assert "external final-head verification" in lowered, path
        assert "containing commit" in lowered, path
        assert "human authorization is not granted" in lowered, path
        assert all(claim not in lowered for claim in forbidden_current_state_claims), path
        assert all(
            re.search(pattern, current_state_text, re.IGNORECASE) is None
            for pattern in forbidden_current_state_patterns
        ), path

    ledger_path = (
        ROOT
        / "docs"
        / "planning"
        / "governance-extension"
        / "AUDIT_REMEDIATION_LEDGER.json"
    )
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert ledger["schema"] == "nornyx.audit_remediation_ledger.v2"
    audit = ledger["audit"]
    assert audit["audited_base"] == audited_base
    assert audit["original_no_go_candidate"] == original_candidate
    assert audit["main_remediation_implementation_anchor"] == implementation_anchor
    historical_ci = audit["historical_exact_head_ci"]
    assert historical_ci["candidate"] == historical_ci_candidate
    assert historical_ci["is_final_approved_candidate"] is False
    assert historical_ci["run_id"] == 29373272295
    assert historical_ci["conclusion"] == "success"
    assert historical_ci["windows"] == {
        "source": "local_windows",
        "passed": 913,
        "skipped": 45,
        "lineage_anchor": implementation_anchor,
    }
    assert historical_ci["linux"] == {
        "source": "hosted_linux_ci",
        "run_id": 29373272295,
        "passed": 958,
        "skipped": 0,
    }
    assert historical_ci["wheel"] == {
        "source": "hosted_linux_ci",
        "run_id": 29373272295,
        "profiles": 12,
        "modules": 6,
        "network_attempts": [],
        "network_used": False,
    }
    assert audit["later_reopening_audit"]["reopened_findings"] == list(reopened_ids)
    assert audit["residual_remediation"]["code_commit"] == residual_code_commit
    documentation_commit = audit["residual_remediation"]["documentation_commit"]
    assert documentation_commit == {
        "kind": "containing_commit",
        "sha": None,
        "self_embedding_avoided": True,
    }
    assert audit["external_final_head_verification"] == {
        "resolve_candidate_from": "git_and_github",
        "hosted_ci": "required_for_resolved_exact_head",
        "independent_audit": "required_after_green_exact_head_ci",
    }
    assert set(ledger["authorization"]) == {
        "approve",
        "mark_ready",
        "auto_merge",
        "merge",
        "release",
        "tag",
        "publish",
        "deploy",
    }
    assert all(value is False for value in ledger["authorization"].values())

    candidate = markdown_paths[-1].read_text(encoding="utf-8")
    assert "PR state: draft" in candidate
    assert "## Prepared PR Description" in candidate
    assert candidate.count("```markdown") == 1
    prepared_body = candidate.split("```markdown", 1)[1].split("```", 1)[0]
    required_body_facts = (
        audited_base,
        implementation_anchor,
        "AUD-001 through AUD-022",
        "now closed on the final exact head",
        *reopened_ids,
        "{{FINAL_HEAD}}",
        "{{FINAL_CI_RUN_ID}}",
        "{{FINAL_WINDOWS_RESULT}}",
        "{{FINAL_LINUX_RESULT}}",
        "{{FINAL_AUDIT_VERDICT}}",
        "Candidate-aware diff",
        "Source and wheel builds: passed",
        "Twine checks: passed",
        "12 profiles",
        "6 modules",
        "network_attempts=[]",
        "network_used=false",
        "five verified migrations",
        "separately\nrecorded additive architecture starter",
        "PR #30 remains draft",
        "does not\nauthorize merge",
        "auto-merge",
        "release",
        "tagging",
        "publication",
        "deployment",
    )
    assert all(fact in prepared_body for fact in required_body_facts)
    assert "29373272295" not in prepared_body
    assert "913 passed" not in prepared_body
    assert "958 passed" not in prepared_body


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def test_aud020_migration_record_is_mechanically_bound_to_artifacts() -> None:
    from scripts.check_compatibility_migrations import verify_manifest

    manifest = verify_manifest(CORPUS / "manifest.json")
    # 7 pre-AN migrations plus the AN-002 module evolution
    # (migration:modules-agentic-network-governance-v2).
    assert len(manifest["intentional_migrations"]) == 8
