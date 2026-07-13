from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from nornyx.cli import main
from nornyx.governance import GovernanceRegistry, compose_governance
from nornyx.governance.locks import lock_for_packs, write_lock
from nornyx.governance.schemas import canonical_pack_hash
from nornyx.profiles import profile_document


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "governance_extension"
AS_OF = "2026-06-01T00:00:00Z"
MODULE_NAMES = {
    "evidence_integrity",
    "human_approval",
    "separation_of_duties",
    "exception_management",
    "change_control",
    "architecture_conformance",
}


def _fixture(name: str) -> dict[str, Any]:
    return yaml.safe_load((FIXTURES / name).read_text(encoding="utf-8"))


def _write_pack(path: Path, payload: dict[str, Any]) -> None:
    payload = deepcopy(payload)
    payload["integrity"]["content_hash"] = canonical_pack_hash(payload)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_evidence(root: Path, *, content_hash: str | None = None) -> Path:
    artifact = root / "evidence-manifest.json"
    artifact.write_text('{"status":"pass"}\n', encoding="utf-8")
    observed = "sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest()
    payload = {
        "schema": "nornyx.governance_evidence.v1",
        "subject_revision": "git:test-revision",
        "records": [
            {
                "id": "evidence_manifest",
                "type": "evidence_manifest",
                "schema_id": "nornyx.governance_evidence.v1",
                "producer": {"id": "test_tool", "type": "tool"},
                "artifact": artifact.name,
                "content_hash": content_hash or observed,
                "subject_revision": "git:test-revision",
                "tool": {"name": "test_tool", "version": "1.0.0"},
                "generated_at": "2026-05-01T00:00:00Z",
                "expires_at": "2027-05-01T00:00:00Z",
                "status": "pass",
                "dependencies": [],
            }
        ],
    }
    path = root / "governance-evidence.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def test_modules_cli_lists_inspects_and_discovers_project_modules(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    module_dir = tmp_path / ".nornyx" / "modules"
    module_dir.mkdir(parents=True)
    _write_pack(module_dir / "fixture.yaml", _fixture("valid_module_v1.yaml"))
    monkeypatch.chdir(tmp_path)

    assert main(["modules", "list", "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    names = {item["name"] for item in listed["modules"]}
    assert MODULE_NAMES | {"fixture_evidence_integrity"} <= names
    fixture = next(
        item for item in listed["modules"] if item["name"] == "fixture_evidence_integrity"
    )
    assert fixture["source_tier"] == "project"
    assert fixture["content_hash"].startswith("sha256:")

    assert main(["modules", "inspect", "change_control", "--json"]) == 0
    inspected = json.loads(capsys.readouterr().out)["module"]
    assert inspected["dependencies"] == ["nornyx.builtin.module.exception_management"]
    assert inspected["structural_checks"] == ["change_control.v1"]
    assert inspected["resolved_provenance"]["source_tier"] == "builtin"


def test_modules_validate_requires_a_module_pack(
    tmp_path: Path,
    capsys,
) -> None:
    module_path = tmp_path / "module.yaml"
    _write_pack(module_path, _fixture("valid_module_v1.yaml"))
    assert main(["modules", "validate", str(module_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["kind"] == "module"

    profile_path = tmp_path / "profile.yaml"
    _write_pack(profile_path, _fixture("valid_profile_v1.yaml"))
    assert main(["modules", "validate", str(profile_path), "--json"]) == 1
    rejected = json.loads(capsys.readouterr().out)
    assert rejected["diagnostics"][0]["code"] == "PACK_KIND_MISMATCH"


@pytest.mark.parametrize("command", ["resolve", "explain", "matrix"])
def test_governance_cli_reports_effective_contract_controls(
    command: str,
    capsys,
) -> None:
    path = ROOT / "examples" / "governance_foundations.nyx"
    assert main(
        ["governance", command, str(path), "--as-of", AS_OF, "--json"]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "pass"
    assert payload["lock"]["status"] == "absent"
    if command == "resolve":
        assert "evidence_integrity.v1" in payload["active_controls"]["structural_checks"]
        assert payload["required_evidence"]
        assert payload["approval_requirements"]
        assert payload["exception_status"]["by_status"] == {"active": 1}
    elif command == "explain":
        assert payload["active_controls"]["rules"]
        assert payload["exception_status"]["declared"] == 1
    else:
        names = {row["name"] for row in payload["matrix"]}
        assert {
            "evidence_integrity",
            "human_approval",
            "separation_of_duties",
            "exception_management",
        } <= names
        assert all("provenance" in row for row in payload["matrix"])


def test_governance_resolve_verifies_and_rejects_lock_substitution(
    tmp_path: Path,
    capsys,
) -> None:
    contract = tmp_path / "contract.nyx"
    contract.write_text(
        yaml.safe_dump(profile_document("minimal", "LockDemo"), sort_keys=False),
        encoding="utf-8",
    )
    registry = GovernanceRegistry.builtins()
    composition = compose_governance(registry, profile_identity="minimal")
    lock_path = write_lock(
        tmp_path / "nornyx.profiles.lock",
        lock_for_packs([*composition.modules, composition.profile]),
    )

    assert main(
        ["governance", "resolve", str(contract), "--as-of", AS_OF, "--json"]
    ) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["lock"]["status"] == "verified"

    lock_payload = json.loads(lock_path.read_text(encoding="utf-8"))
    lock_payload["resolved"][0]["content_hash"] = "sha256:" + "0" * 64
    lock_path.write_text(json.dumps(lock_payload, indent=2) + "\n", encoding="utf-8")
    assert main(
        ["governance", "resolve", str(contract), "--as-of", AS_OF, "--json"]
    ) == 2
    rejected = json.loads(capsys.readouterr().out)
    assert rejected["diagnostics"][0]["code"] == "PACK_LOCK_MISMATCH"


def test_governance_resolve_preserves_legacy_unknown_profile_warning(
    tmp_path: Path,
    capsys,
) -> None:
    contract = tmp_path / "legacy.nyx"
    contract.write_text(
        yaml.safe_dump(
            {
                "nornyx": "0.2",
                "project": {"name": "Legacy", "profile": "org_legacy_profile"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "nornyx.profiles.lock").write_text("{}\n", encoding="utf-8")

    assert main(
        ["governance", "resolve", str(contract), "--as-of", AS_OF, "--json"]
    ) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "not_selected"
    assert report["lock"]["status"] == "not_applicable"
    assert report["diagnostics"][0]["code"] == "PACK_NOT_RESOLVED"


def test_evidence_validate_checks_schema_hash_freshness_and_text_output(
    tmp_path: Path,
    capsys,
) -> None:
    evidence_path = _write_evidence(tmp_path)
    assert main(
        ["evidence", "validate", str(evidence_path), "--as-of", AS_OF, "--json"]
    ) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "pass"
    assert report["diagnostics"] == []

    assert main(
        ["evidence", "validate", str(evidence_path), "--as-of", AS_OF]
    ) == 0
    assert "Valid governance evidence" in capsys.readouterr().out

    bad_path = _write_evidence(tmp_path, content_hash="sha256:" + "0" * 64)
    assert main(
        ["evidence", "validate", str(bad_path), "--as-of", AS_OF, "--json"]
    ) == 1
    failed = json.loads(capsys.readouterr().out)
    assert failed["status"] == "fail"
    assert "EVIDENCE_ARTIFACT_HASH_MISMATCH" in {
        item["code"] for item in failed["diagnostics"]
    }


def test_evidence_validate_rejects_parent_and_symlink_traversal(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    evidence_path = _write_evidence(outside)
    trusted = tmp_path / "trusted"
    trusted.mkdir()
    monkeypatch.chdir(trusted)

    assert main(
        [
            "evidence",
            "validate",
            "../outside/governance-evidence.yaml",
            "--as-of",
            AS_OF,
            "--json",
        ]
    ) == 1
    traversal = json.loads(capsys.readouterr().out)
    assert traversal["diagnostics"][0]["code"] == "EVIDENCE_PATH_OUTSIDE_ROOT"

    link = trusted / "evidence-link.yaml"
    try:
        link.symlink_to(evidence_path)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")
    assert main(
        ["evidence", "validate", str(link), "--as-of", AS_OF, "--json"]
    ) == 1
    symlink = json.loads(capsys.readouterr().out)
    assert symlink["diagnostics"][0]["code"] == "EVIDENCE_SYMLINK_REJECTED"


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("remote", "EVIDENCE_REMOTE_SOURCE_REJECTED"),
        ("oversized", "EVIDENCE_LIMIT_EXCEEDED"),
        ("aliases", "EVIDENCE_LIMIT_EXCEEDED"),
        ("malformed", "EVIDENCE_YAML_INVALID"),
    ],
)
def test_evidence_validate_rejects_remote_and_resource_abuse(
    kind: str,
    expected: str,
    tmp_path: Path,
    capsys,
) -> None:
    if kind == "remote":
        source = "https://example.invalid/evidence.yaml"
    else:
        path = tmp_path / f"{kind}.yaml"
        if kind == "oversized":
            path.write_bytes(b"x" * (512 * 1024 + 1))
        elif kind == "aliases":
            aliases = ", ".join("*item" for _ in range(51))
            path.write_text(f"base: &item value\nitems: [{aliases}]\n", encoding="utf-8")
        else:
            path.write_text("records: [unterminated\n", encoding="utf-8")
        source = str(path)

    assert main(
        ["evidence", "validate", source, "--as-of", AS_OF, "--json"]
    ) == 1
    rejected = json.loads(capsys.readouterr().out)
    assert rejected["diagnostics"][0]["code"] == expected


def test_modules_validate_rejects_remote_sources(capsys) -> None:
    assert main(
        ["modules", "validate", "https://example.invalid/module.yaml", "--json"]
    ) == 1
    rejected = json.loads(capsys.readouterr().out)
    assert rejected["diagnostics"][0]["code"] == "PACK_REMOTE_SOURCE_REJECTED"


def test_governance_cli_and_public_api_contract_is_documented() -> None:
    guide = (ROOT / "docs" / "GOVERNANCE_CLI_AND_API.md").read_text(encoding="utf-8")
    for marker in (
        "nornyx modules list",
        "nornyx governance resolve",
        "nornyx governance explain",
        "nornyx governance matrix",
        "nornyx evidence validate",
        "validate_governance_evidence_file",
        "at least two package",
        "does not exist",
    ):
        assert marker in guide
