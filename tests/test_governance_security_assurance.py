from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import subprocess
from typing import Any
import urllib.request

import pytest
import yaml

from nornyx.cli import main
from nornyx.governance import GovernanceError, validate_governance_evidence_file
from nornyx.governance.loader import load_local_pack
from nornyx.governance.runtime import registry_for_directory
from nornyx.governance.schemas import canonical_pack_hash
from nornyx.governed_package import validate_governed_package
from nornyx.parser import load_nyx


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "governance_extension"
AS_OF = "2026-06-01T00:00:00Z"


def _fixture(name: str) -> dict[str, Any]:
    return yaml.safe_load((FIXTURES / name).read_text(encoding="utf-8"))


def _write_pack(path: Path, payload: dict[str, Any]) -> None:
    payload = deepcopy(payload)
    payload["integrity"]["content_hash"] = canonical_pack_hash(payload)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _error_codes(exc: GovernanceError) -> set[str]:
    return {item.code for item in exc.diagnostics}


def _hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_confusable_pack_identities_fail_schema_validation(tmp_path: Path) -> None:
    module = _fixture("valid_module_v1.yaml")
    module["id"] = "org.example.modulе"
    module["name"] = "modulе"
    path = tmp_path / "confusable.yaml"
    _write_pack(path, module)

    with pytest.raises(GovernanceError) as caught:
        load_local_pack(path, allowed_root=tmp_path)
    assert _error_codes(caught.value) == {"PACK_SCHEMA_INVALID"}


@pytest.mark.parametrize(
    ("fixture", "field"),
    [
        ("valid_profile_v1.yaml", "remove_required_evidence"),
        ("valid_module_v1.yaml", "remove_approval_requirements"),
    ],
)
def test_packs_cannot_declare_governance_removal_operations(
    fixture: str,
    field: str,
    tmp_path: Path,
) -> None:
    payload = _fixture(fixture)
    payload[field] = ["target"]
    path = tmp_path / f"{field}.yaml"
    _write_pack(path, payload)

    with pytest.raises(GovernanceError) as caught:
        load_local_pack(path, allowed_root=tmp_path)
    assert _error_codes(caught.value) == {"PACK_SCHEMA_INVALID"}


def test_governed_package_cannot_approve_itself_through_its_execution_surface() -> None:
    package = deepcopy(
        load_nyx(ROOT / "examples" / "governed_package" / "basic.nyx")[
            "governed_package"
        ]
    )
    package["approval_gates"][0]["eligible_approver_roles"] = ["editor-local"]

    codes = {item.code for item in validate_governed_package(package)}
    assert "INVALID_APPROVER_EXECUTION_SURFACE" in codes


def test_release_evidence_for_the_wrong_revision_fails_closed(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    release = tmp_path / "release-report.json"
    manifest.write_text('{"type":"evidence_manifest"}\n', encoding="utf-8")
    release.write_text('{"type":"release_report"}\n', encoding="utf-8")
    common = {
        "schema_id": "nornyx.test_evidence.v1",
        "producer": {"id": "release_tool", "type": "tool"},
        "tool": {"name": "release_tool", "version": "1.0.0"},
        "generated_at": "2026-05-01T00:00:00Z",
        "expires_at": "2027-05-01T00:00:00Z",
        "status": "pass",
        "dependencies": [],
    }
    payload = {
        "schema": "nornyx.governance_evidence.v1",
        "subject_revision": "git:governed",
        "records": [
            {
                **common,
                "id": "evidence_manifest",
                "type": "evidence_manifest",
                "artifact": manifest.name,
                "content_hash": _hash(manifest),
                "subject_revision": "git:governed",
            },
            {
                **common,
                "id": "release_report",
                "type": "release_report",
                "artifact": release.name,
                "content_hash": _hash(release),
                "subject_revision": "git:other",
            },
        ],
    }
    evidence_path = tmp_path / "evidence.yaml"
    evidence_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    diagnostics = validate_governance_evidence_file(
        evidence_path,
        allowed_root=tmp_path,
        as_of=AS_OF,
    )
    assert "EVIDENCE_REVISION_MISMATCH" in {item.code for item in diagnostics}


def test_modules_validate_rejects_symlinked_module_paths(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    module = tmp_path / "module.yaml"
    _write_pack(module, _fixture("valid_module_v1.yaml"))
    link = tmp_path / "module-link.yaml"
    try:
        link.symlink_to(module)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")
    monkeypatch.chdir(tmp_path)

    assert main(["modules", "validate", link.name, "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["diagnostics"][0]["code"] == "PACK_SYMLINK_REJECTED"


def test_project_discovery_rejects_symlinked_nornyx_ancestor(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside_profiles = tmp_path / "outside" / ".nornyx" / "profiles"
    outside_profiles.mkdir(parents=True)
    _write_pack(outside_profiles / "profile.yaml", _fixture("valid_profile_v1.yaml"))
    try:
        (project / ".nornyx").symlink_to(
            outside_profiles.parent,
            target_is_directory=True,
        )
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")

    with pytest.raises(GovernanceError) as caught:
        registry_for_directory(project)
    assert _error_codes(caught.value) == {"PACK_SYMLINK_REJECTED"}


def test_check_rejects_symlinked_ancestor_above_project_root(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    project = tmp_path / "real_root" / "project"
    project.mkdir(parents=True)
    (project / "project.nyx").write_text(
        'nornyx: "0.1"\nproject:\n  name: SymlinkedProject\n  profile: minimal\n',
        encoding="utf-8",
    )
    link_root = tmp_path / "link_root"
    try:
        link_root.symlink_to(tmp_path / "real_root", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")

    monkeypatch.chdir(tmp_path)
    assert main(["check", "link_root/project/project.nyx"]) == 1
    assert "PACK_SYMLINK_REJECTED" in capsys.readouterr().out


def test_governance_inspection_rejects_symlinked_contract_ancestor(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    project = tmp_path / "real_root" / "project"
    project.mkdir(parents=True)
    (project / "project.nyx").write_text(
        'nornyx: "0.1"\nproject:\n  name: SymlinkedReport\n  profile: minimal\n',
        encoding="utf-8",
    )
    link_root = tmp_path / "link_root"
    try:
        link_root.symlink_to(tmp_path / "real_root", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")

    monkeypatch.chdir(tmp_path)
    assert main(
        [
            "governance",
            "explain",
            "link_root/project/project.nyx",
            "--json",
        ]
    ) == 1
    assert "PACK_SYMLINK_REJECTED" in capsys.readouterr().out


def test_malformed_evidence_diagnostics_are_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "malformed.yaml"
    path.write_text("records: [unterminated\n", encoding="utf-8")
    observed = []
    for _ in range(2):
        with pytest.raises(GovernanceError) as caught:
            validate_governance_evidence_file(
                path,
                allowed_root=tmp_path,
                as_of=AS_OF,
            )
        observed.append([item.to_dict() for item in caught.value.diagnostics])
    assert observed[0] == observed[1]
    assert observed[0][0]["code"] == "EVIDENCE_YAML_INVALID"


def test_governance_inspection_invokes_no_process_or_network_api(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    evidence = tmp_path / "evidence.json"
    artifact = tmp_path / "manifest.json"
    artifact.write_text('{"status":"pass"}\n', encoding="utf-8")
    evidence.write_text(
        json.dumps(
            {
                "schema": "nornyx.governance_evidence.v1",
                "subject_revision": "git:test",
                "records": [
                    {
                        "id": "evidence_manifest",
                        "type": "evidence_manifest",
                        "schema_id": "nornyx.test_evidence.v1",
                        "producer": {"id": "test_tool", "type": "tool"},
                        "artifact": artifact.name,
                        "content_hash": _hash(artifact),
                        "subject_revision": "git:test",
                        "tool": {"name": "test_tool", "version": "1.0.0"},
                        "generated_at": "2026-05-01T00:00:00Z",
                        "expires_at": "2027-05-01T00:00:00Z",
                        "status": "pass",
                        "dependencies": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
        del args, kwargs
        raise AssertionError("governance inspection attempted process or network access")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)

    assert main(["modules", "list", "--json"]) == 0
    capsys.readouterr()
    assert main(
        [
            "governance",
            "explain",
            str(ROOT / "examples" / "governance_foundations.nyx"),
            "--as-of",
            AS_OF,
            "--json",
        ]
    ) == 0
    capsys.readouterr()
    assert main(
        ["evidence", "validate", str(evidence), "--as-of", AS_OF, "--json"]
    ) == 0
    capsys.readouterr()
