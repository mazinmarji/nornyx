from __future__ import annotations

import json
from pathlib import Path

import yaml

from nornyx.governance import GovernanceRegistry
from nornyx.profiles import PROFILE_NAMES


ROOT = Path(__file__).resolve().parents[1]
GSA_ROOT = ROOT / "docs" / "planning" / "governance-extension" / "gsa"
REQUIRED_KEYS = {
    "schema",
    "enforcement",
    "profile",
    "what_is_governed",
    "why",
    "owner",
    "who_may_act",
    "allowed",
    "denied",
    "approval_required",
    "evidence",
    "stale_or_false_detection",
    "drift_detection",
    "containment",
    "authority_expiry",
    "retirement",
    "required_modules",
    "recommended_modules",
}
LIST_KEYS = {
    "what_is_governed",
    "who_may_act",
    "allowed",
    "denied",
    "approval_required",
    "evidence",
    "stale_or_false_detection",
    "drift_detection",
    "containment",
}
FINAL_STATUSES = {
    "implemented_as_external_evidence_integration",
    "not_required_after_GSA",
    "superseded",
}


def _matrices() -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for path in sorted(GSA_ROOT.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict), path
        result[path.stem] = payload
    return result


def test_gsa_advisory_matrices_cover_the_profile_catalog() -> None:
    matrices = _matrices()
    catalog = json.loads(
        (ROOT / "nornyx" / "profiles_data" / "catalog.json").read_text(
            encoding="utf-8"
        )
    )
    module_names = set(catalog["modules"])

    assert set(matrices) == set(PROFILE_NAMES)
    for name, payload in matrices.items():
        assert set(payload) == REQUIRED_KEYS
        assert payload["schema"] == "nornyx.gsa_profile_matrix.v1"
        assert payload["enforcement"] == "advisory_document"
        assert payload["profile"] == name
        for key in LIST_KEYS:
            assert isinstance(payload[key], list) and payload[key], (name, key)
            assert all(isinstance(item, str) and item for item in payload[key])
        for key in ("required_modules", "recommended_modules"):
            assert isinstance(payload[key], list), (name, key)
            assert set(payload[key]) <= module_names
        for key in ("why", "owner", "authority_expiry", "retirement"):
            assert isinstance(payload[key], str) and payload[key]


def test_profile_mapping_preserves_legacy_requirements() -> None:
    matrices = _matrices()
    registry = GovernanceRegistry.builtins()

    for name in PROFILE_NAMES:
        profile = registry.resolve_profile(name)
        required_names = matrices[name]["required_modules"]
        assert isinstance(required_names, list)
        expected_ids = tuple(registry.resolve_module(item).id for item in required_names)
        assert profile.required_modules == expected_ids
        if name not in {"architecture_governance", "agentic_network"}:
            assert profile.required_modules == ()

    assert matrices["architecture_governance"]["required_modules"] == [
        "architecture_conformance"
    ]
    assert matrices["agentic_network"]["required_modules"] == [
        "agentic_network_governance"
    ]


def test_gsa_closes_candidates_without_runtime_tooling() -> None:
    adr = (
        ROOT
        / "docs"
        / "decisions"
        / "ADR-0031-specialist-governance-placement-after-gsa.md"
    ).read_text(encoding="utf-8")
    mapping = (
        ROOT / "docs" / "planning" / "governance-extension" / "17_PROFILE_MODULE_MAPPING.md"
    ).read_text(encoding="utf-8")

    for status in FINAL_STATUSES:
        assert f"`{status}`" in adr
    for candidate in (
        "Supply-chain governance",
        "Data-protection governance",
        "Lifecycle management",
        "Release control",
        "Incident response",
        "GSA runtime schema and CLI",
    ):
        assert candidate in adr
    for profile in PROFILE_NAMES:
        assert f"`{profile}`" in mapping

    assert not (ROOT / "schemas" / "gsa_report_v1.schema.json").exists()
    assert not (ROOT / "nornyx" / "schemas" / "gsa_report_v1.schema.json").exists()
    cli_source = (ROOT / "nornyx" / "cli.py").read_text(encoding="utf-8")
    assert 'add_parser("gsa"' not in cli_source
    assert 'add_parser("analyze"' not in cli_source
