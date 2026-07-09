from __future__ import annotations

import json
import re
from pathlib import Path

from nornyx.checker import check_document, has_errors
from nornyx.governed_package import (
    generate_governed_package,
    radar_governed_packages,
    register_existing_package,
    validate_governed_package_source,
    verify_package_lock,
)
from nornyx.parser import load_nyx


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "governed_package"


def _codes(path: Path) -> set[str]:
    diagnostics = validate_governed_package_source(path)
    return {item.code for item in diagnostics}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _banned_terms() -> list[str]:
    return [
        "Mission " + "Control OS",
        "M" + "CO",
        "Ops" + "Guard",
        "Agentic " + "Dev OS",
        "Agentic" + "Networks",
        "mco-realistic-external-" + "lab",
        "mission-control-" + "os",
    ]


def test_parses_valid_governed_package_example() -> None:
    doc = load_nyx(EXAMPLES / "basic.nyx")

    assert doc["governed_package"]["profile"] == "governed_package"
    assert doc["governed_package"]["package_id"] == "gp-example-001"


def test_basic_example_validates() -> None:
    assert validate_governed_package_source(EXAMPLES / "basic.nyx") == []


def test_software_change_example_validates() -> None:
    assert validate_governed_package_source(EXAMPLES / "software_change.nyx") == []


def test_nornyx_check_accepts_valid_governed_package_block() -> None:
    diagnostics = check_document(load_nyx(EXAMPLES / "basic.nyx"))

    assert not has_errors(diagnostics), [item.to_dict() for item in diagnostics]


def test_rejects_execution_surface_as_approver() -> None:
    codes = _codes(EXAMPLES / "invalid_ai_tool_approver.nyx")

    assert "INVALID_APPROVER_EXECUTION_SURFACE" in codes


def test_rejects_unsafe_installation_policy() -> None:
    codes = _codes(EXAMPLES / "invalid_unsafe_flags.nyx")

    assert "UNSAFE_INSTALLATION_POLICY_INSTALLED" in codes
    assert "UNSAFE_INSTALLATION_POLICY_EXECUTABLE_BY_DEFAULT" in codes


def test_rejects_unsafe_safety_flags() -> None:
    codes = _codes(EXAMPLES / "invalid_unsafe_flags.nyx")

    assert "UNSAFE_SAFETY_BOUNDARY_SECRETS_ALLOWED" in codes
    assert "UNSAFE_SAFETY_BOUNDARY_DEPLOYMENT_ALLOWED" in codes


def test_generate_mode_creates_inert_package_manifest_and_lock(tmp_path: Path) -> None:
    generate_governed_package(EXAMPLES / "basic.nyx", tmp_path)
    manifest = _read_json(tmp_path / "package_manifest.json")
    lock = _read_json(tmp_path / "package_lock.json")

    assert manifest["profile"] == "governed_package"
    assert manifest["installation_policy"]["installed"] is False
    assert manifest["installation_policy"]["executable_by_default"] is False
    assert manifest["safety_boundary"]["deployment_allowed"] is False
    assert lock["profile"] == "governed_package"
    assert lock["artifact_hashes"]
    assert not verify_package_lock(tmp_path)


def test_detects_modified_generated_artifact_hash_mismatch(tmp_path: Path) -> None:
    generate_governed_package(EXAMPLES / "basic.nyx", tmp_path)
    (tmp_path / "AGENTS.md").write_text("modified\n", encoding="utf-8")

    diagnostics = verify_package_lock(tmp_path)

    assert any(item.code == "PACKAGE_LOCK_ARTIFACT_HASH_MISMATCH" for item in diagnostics)


def test_register_existing_mode_locks_existing_artifact_directory(tmp_path: Path) -> None:
    source = tmp_path / "existing"
    (source / "docs").mkdir(parents=True)
    (source / "README.md").write_text("# Existing\n", encoding="utf-8")
    (source / "docs" / "summary.md").write_text("# Summary\n", encoding="utf-8")
    out = tmp_path / "registered"

    register_existing_package(source, out, contract=EXAMPLES / "register_existing.nyx")
    manifest = _read_json(out / "package_manifest.json")

    assert manifest["registration_mode"] == "existing"
    assert all(item["sha256"] for item in manifest["artifacts"])
    assert not validate_governed_package_source(out)


def test_register_existing_mode_rejects_unsafe_manifest(tmp_path: Path) -> None:
    out = tmp_path / "unsafe"
    generate_governed_package(EXAMPLES / "basic.nyx", out)
    manifest_path = out / "package_manifest.json"
    manifest = _read_json(manifest_path)
    manifest["installation_policy"]["installed"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    codes = _codes(manifest_path)

    assert "UNSAFE_INSTALLATION_POLICY_INSTALLED" in codes


def test_radar_mode_detects_candidate_package_from_sample_repo(tmp_path: Path) -> None:
    report = radar_governed_packages(EXAMPLES / "radar_sample_repo", tmp_path / "radar_report.json")

    assert report["proposal_only"] is True
    assert report["candidate_packages"]
    assert report["candidate_packages"][0]["artifacts"]
    assert report["inferred_risk_tier"] == "medium"


def test_radar_mode_is_proposal_only_and_inert(tmp_path: Path) -> None:
    report = radar_governed_packages(EXAMPLES / "radar_sample_repo", tmp_path / "radar_report.json")

    assert report["proposal_only"] is True
    assert report["installed"] is False
    assert report["executable_by_default"] is False
    assert report["installation_policy"]["installed"] is False
    assert report["installation_policy"]["executable_by_default"] is False
    assert report["suggested_approval_gates"][0]["eligible_approver_roles"] == ["reviewer"]


def test_radar_mode_does_not_copy_secret_like_values(tmp_path: Path) -> None:
    report_path = tmp_path / "radar_report.json"
    radar_governed_packages(EXAMPLES / "radar_sample_repo", report_path)
    text = report_path.read_text(encoding="utf-8")

    assert "replace-me" not in text
    assert "possible_secret" in text


def test_radar_suggest_contract_writes_contract_and_report(tmp_path: Path) -> None:
    contract_path = tmp_path / "radar_suggested.nyx"
    report = radar_governed_packages(
        EXAMPLES / "radar_sample_repo",
        contract_path,
        suggest_contract=True,
    )

    assert contract_path.exists()
    assert Path(report["report_path"]).exists()
    assert report["suggested_contract_ref"] == contract_path.as_posix()


def test_all_three_modes_produce_provenance_and_remain_inert(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    registered_source = tmp_path / "registered-source"
    registered_source.mkdir()
    (registered_source / "README.md").write_text("# Existing\n", encoding="utf-8")
    registered = tmp_path / "registered"
    radar_path = tmp_path / "radar.json"

    generate_governed_package(EXAMPLES / "basic.nyx", generated)
    register_existing_package(registered_source, registered, contract=EXAMPLES / "register_existing.nyx")
    radar = radar_governed_packages(EXAMPLES / "radar_sample_repo", radar_path)

    for manifest_path in [generated / "package_manifest.json", registered / "package_manifest.json"]:
        manifest = _read_json(manifest_path)
        assert manifest["provenance"]["source_sha256"]
        assert manifest["installation_policy"]["installed"] is False
        assert manifest["installation_policy"]["executable_by_default"] is False
    assert radar["provenance"]["source_sha256"]
    assert radar["installation_policy"]["installed"] is False
    assert radar["installation_policy"]["executable_by_default"] is False


def test_all_three_modes_reject_or_avoid_execution_surface_approvers(tmp_path: Path) -> None:
    generated_codes = _codes(EXAMPLES / "invalid_ai_tool_approver.nyx")
    assert "INVALID_APPROVER_EXECUTION_SURFACE" in generated_codes

    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("# Existing\n", encoding="utf-8")
    out = tmp_path / "registered-invalid"
    try:
        register_existing_package(source, out, contract=EXAMPLES / "invalid_ai_tool_approver.nyx")
    except ValueError as exc:
        assert "execution surfaces and AI tools cannot be eligible approvers" in str(exc)
    else:
        raise AssertionError("register existing accepted an execution surface approver")

    radar = radar_governed_packages(EXAMPLES / "radar_sample_repo", tmp_path / "radar.json")
    assert radar["suggested_approval_gates"][0]["eligible_approver_roles"] == ["reviewer"]


def test_generated_package_artifacts_do_not_contain_private_names(tmp_path: Path) -> None:
    generate_governed_package(EXAMPLES / "basic.nyx", tmp_path)
    pattern = re.compile("|".join(re.escape(term) for term in _banned_terms()))

    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert not pattern.search(path.read_text(encoding="utf-8"))


def test_governed_package_docs_examples_source_and_tests_do_not_contain_private_names() -> None:
    roots = [
        ROOT / "docs" / "governed-package-profile.md",
        ROOT / "examples" / "governed_package",
        ROOT / "nornyx" / "governed_package.py",
        ROOT / "nornyx" / "schemas" / "governed_package.schema.json",
        Path(__file__),
    ]
    pattern = re.compile("|".join(re.escape(term) for term in _banned_terms()))

    for root in roots:
        paths = [root] if root.is_file() else [item for item in root.rglob("*") if item.is_file()]
        for path in paths:
            assert not pattern.search(path.read_text(encoding="utf-8"))
