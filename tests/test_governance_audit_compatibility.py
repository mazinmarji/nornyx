from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from nornyx.governance.models import (
    CompositionResult,
    GovernanceModule,
    NormalizedApproval,
    PackProvenance,
)
from nornyx.governed_package import validate_governed_package
from nornyx.parser import load_nyx


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "governance_compatibility"


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


def test_aud017_current_docs_are_marked_superseded_during_remediation() -> None:
    paths = [
        ROOT / "docs" / "planning" / "governance-extension" / name
        for name in (
            "19_COMPATIBILITY_REPORT.md",
            "20_SECURITY_ASSURANCE_REPORT.md",
            "21_PROGRAM_CLOSURE_REPORT.md",
            "22_FINAL_INDEPENDENT_AUDIT.md",
        )
    ] + [ROOT / "docs" / "releases" / "RELEASE_CANDIDATE_GOVERNANCE_PROGRAM.md"]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "superseded" in text.lower(), path
        assert "35ee69359599af7887f6b9b58ae0a4cd06a48d25" in text, path
    candidate = paths[-1].read_text(encoding="utf-8")
    assert "PR remains draft" in candidate
    assert "unauthorized" in candidate


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def test_aud020_migration_record_is_mechanically_bound_to_artifacts() -> None:
    manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    migration = next(
        item
        for item in manifest["intentional_migrations"]
        if item["surface"] == "governance_explain normalized approval requirements"
    )
    for key in ("before_artifact", "after_artifact", "expected_diff_artifact"):
        assert migration.get(key), key
        assert (ROOT / migration[key]).is_file(), key

    before = (ROOT / migration["before_artifact"]).read_bytes()
    after = (ROOT / migration["after_artifact"]).read_bytes()
    assert _sha256(before) == migration["old_hash"]
    assert _sha256(after) == migration["new_hash"]

    expected_diff = json.loads(
        (ROOT / migration["expected_diff_artifact"]).read_text(encoding="utf-8")
    )
    before_payload = json.loads(before)
    after_payload = json.loads(after)
    observed = {
        "before_only": sorted(set(before_payload) - set(after_payload)),
        "after_only": sorted(set(after_payload) - set(before_payload)),
        "changed": sorted(
            key
            for key in set(before_payload) & set(after_payload)
            if before_payload[key] != after_payload[key]
        ),
    }
    assert observed == expected_diff
    assert migration["reason"] and migration["approval"] and migration["changelog"]
