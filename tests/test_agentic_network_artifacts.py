"""AN-003 tests: deterministic agentic-network artifacts and network lock."""

from __future__ import annotations

import builtins
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import socket
import subprocess
from typing import Any

import pytest
import yaml

from nornyx.agentic_artifacts import (
    ARTIFACT_NAMES,
    GENERATION_MANIFEST_NAME,
    AgenticArtifactError,
    agentic_network_lock_digest,
    build_agentic_network_artifacts,
    build_agentic_network_lock,
    contract_digest,
    load_agentic_network_lock,
    render_agentic_network_artifacts,
    verify_agentic_network_lock,
    write_agentic_network_artifacts,
    write_agentic_network_lock,
)
from nornyx.cli import main as cli_main
from nornyx.governance import GovernanceError, GovernanceRegistry, compose_governance
from symlink_support import create_symlink_or_skip


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "agentic_network.nyx"
AS_OF = "2026-07-17T00:00:00Z"
REGISTRY = GovernanceRegistry.builtins()
COMPOSITION = compose_governance(REGISTRY, profile_identity="agentic_network")

# Golden binding for the bundled example contract at the AN-003 baseline.
# A change here is a deliberate, reviewed migration, never a test refresh.
GOLDEN_EXAMPLE_LOCK_DIGEST = (
    "sha256:7fb7987edb2e12226b3a21e3ddf89ffbf38ba46ffcd8bb18e80e7909b12109ca"
)


def _document() -> dict[str, Any]:
    return yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))


def _cli(argv: list[str]) -> tuple[int, dict[str, Any]]:
    out = StringIO()
    with redirect_stdout(out):
        code = cli_main(argv)
    return code, json.loads(out.getvalue())


def test_generation_is_byte_identical_across_repeated_runs() -> None:
    document = _document()
    first = render_agentic_network_artifacts(document, COMPOSITION)
    second = render_agentic_network_artifacts(deepcopy(document), COMPOSITION)
    assert first == second
    assert set(first) == set(ARTIFACT_NAMES) | {GENERATION_MANIFEST_NAME}


def test_generation_is_stable_under_source_permutations() -> None:
    document = _document()
    baseline = render_agentic_network_artifacts(document, COMPOSITION)

    permuted = _document()
    network = permuted["agentic_network"]
    network["trust_zones"] = list(reversed(network["trust_zones"]))
    network["memberships"] = list(reversed(network["memberships"]))
    network["network_gates"] = list(reversed(network["network_gates"]))
    permuted["agent_identities"] = list(reversed(permuted["agent_identities"]))
    permuted["capabilities"] = list(reversed(permuted["capabilities"]))
    shuffled = render_agentic_network_artifacts(permuted, COMPOSITION)

    assert shuffled == baseline
    assert contract_digest(permuted) == contract_digest(document)


def test_formatting_only_changes_keep_the_source_digest() -> None:
    parsed = _document()
    reformatted = yaml.safe_dump(parsed, sort_keys=True, indent=4, width=60)
    reparsed = yaml.safe_load(reformatted)
    assert contract_digest(parsed) == contract_digest(reparsed)
    assert (
        render_agentic_network_artifacts(parsed, COMPOSITION)
        == render_agentic_network_artifacts(reparsed, COMPOSITION)
    )


def test_semantic_mutation_changes_expected_hashes() -> None:
    document = _document()
    baseline = render_agentic_network_artifacts(document, COMPOSITION)
    mutated_doc = _document()
    mutated_doc["capabilities"][0]["risk"] = "medium"
    mutated = render_agentic_network_artifacts(mutated_doc, COMPOSITION)
    assert mutated["capability_matrix.json"] != baseline["capability_matrix.json"]
    assert (
        mutated[GENERATION_MANIFEST_NAME] != baseline[GENERATION_MANIFEST_NAME]
    )
    assert contract_digest(mutated_doc) != contract_digest(document)


def test_generation_manifest_hashes_are_accurate() -> None:
    rendered = render_agentic_network_artifacts(_document(), COMPOSITION)
    manifest = json.loads(rendered[GENERATION_MANIFEST_NAME])
    listed = {item["path"]: item["sha256"] for item in manifest["artifacts"]}
    assert set(listed) == set(ARTIFACT_NAMES)
    for name in ARTIFACT_NAMES:
        assert listed[name] == hashlib.sha256(rendered[name]).hexdigest()


def test_protocol_declarations_are_contract_only() -> None:
    artifacts = build_agentic_network_artifacts(_document(), COMPOSITION)
    for name in ("a2a_declaration.json", "mcp_capability_declaration.json"):
        declaration = artifacts[name]
        assert declaration["execution_mode"] == "contract_only"
        assert declaration["live_connector_execution"] is False
        assert "runtime" not in declaration["compatibility"].split()[0]
        assert declaration["denied_sensitive_categories"] == [
            "credentials",
            "private_memory",
            "secrets",
            "tokens",
        ]
    a2a = artifacts["a2a_declaration.json"]
    assert [item["id"] for item in a2a["declared_targets"]] == [
        "protocol.external_reviewer"
    ]
    assert artifacts["mcp_capability_declaration.json"]["declared_targets"] == []


def test_generated_payloads_reject_urls_and_transport_values() -> None:
    document = _document()
    document["agentic_network"]["delegations"] = []
    document["agentic_network"]["handoffs"] = []
    document["agentic_network"]["relations"] = [
        {
            "id": "relation.bad",
            "type": "observed_by",
            "source": {"kind": "agent_identity", "ref": "identity.researcher.local"},
            "target": {"kind": "human_role", "ref": "network_governance_owner"},
            "description": "report to https://collector.example/events",
        }
    ]
    with pytest.raises(GovernanceError) as excinfo:
        build_agentic_network_artifacts(document, COMPOSITION)
    assert any(
        item.code == "AN_ARTIFACT_FORBIDDEN_VALUE"
        for item in excinfo.value.diagnostics
    )


def test_generated_payloads_reject_ip_addresses() -> None:
    document = _document()
    document["agentic_network"]["relations"] = [
        {
            "id": "relation.bad",
            "type": "observed_by",
            "source": {"kind": "agent_identity", "ref": "identity.researcher.local"},
            "target": {"kind": "human_role", "ref": "network_governance_owner"},
            "description": "10.0.0.1",
        }
    ]
    with pytest.raises(GovernanceError) as excinfo:
        build_agentic_network_artifacts(document, COMPOSITION)
    assert any(
        item.code == "AN_ARTIFACT_FORBIDDEN_VALUE"
        for item in excinfo.value.diagnostics
    )


def test_schema_identifier_names_stay_permitted() -> None:
    artifacts = build_agentic_network_artifacts(_document(), COMPOSITION)
    schema_ids = {
        item["schema_id"] for item in artifacts["network_manifest.json"]["block_schemas"]
    }
    assert (
        "https://nornyx.dev/schemas/agentic_network_v1.schema.json" in schema_ids
    )


def test_lock_round_trip_and_golden_digest(tmp_path: Path) -> None:
    document = _document()
    payload = build_agentic_network_lock(document, COMPOSITION)
    assert agentic_network_lock_digest(payload) == GOLDEN_EXAMPLE_LOCK_DIGEST

    lock_path = tmp_path / "nornyx.agentic_network.lock"
    write_agentic_network_lock(payload, lock_path)
    loaded = load_agentic_network_lock(lock_path)
    assert loaded == payload
    assert verify_agentic_network_lock(loaded, document, COMPOSITION) == ()


def test_lock_detects_stale_source_and_changed_records() -> None:
    document = _document()
    payload = build_agentic_network_lock(document, COMPOSITION)
    mutated = _document()
    mutated["capabilities"][0]["risk"] = "medium"
    codes = {
        item.code
        for item in verify_agentic_network_lock(payload, mutated, COMPOSITION)
    }
    assert "AN_LOCK_SOURCE_STALE" in codes
    assert "AN_LOCK_RECORD_MISMATCH" in codes
    assert "AN_LOCK_ARTIFACT_MISMATCH" in codes


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda lock: lock["profile"].update({"content_hash": "sha256:" + "0" * 64}),
            "AN_LOCK_PROFILE_MISMATCH",
        ),
        (
            lambda lock: lock["modules"][0].update(
                {"content_hash": "sha256:" + "0" * 64}
            ),
            "AN_LOCK_MODULE_MISMATCH",
        ),
        (
            lambda lock: lock["block_schemas"].pop(),
            "AN_LOCK_SCHEMA_MISMATCH",
        ),
        (
            lambda lock: lock.update({"structural_checks": ["human_approval.v1"]}),
            "AN_LOCK_CHECKS_MISMATCH",
        ),
        (
            lambda lock: lock.update({"network_id": "network.other"}),
            "AN_LOCK_NETWORK_MISMATCH",
        ),
        (
            lambda lock: lock.update({"subject_revision": "git:" + "9" * 40}),
            "AN_LOCK_REVISION_MISMATCH",
        ),
        (
            lambda lock: lock["records"]["capabilities"][0].update(
                {"digest": "sha256:" + "0" * 64}
            ),
            "AN_LOCK_RECORD_MISMATCH",
        ),
        (
            lambda lock: lock["artifacts"][0].update({"sha256": "0" * 64}),
            "AN_LOCK_ARTIFACT_MISMATCH",
        ),
    ],
)
def test_lock_hash_substitution_matrix(mutate, expected) -> None:
    document = _document()
    payload = json.loads(
        json.dumps(build_agentic_network_lock(document, COMPOSITION))
    )
    mutate(payload)
    codes = {
        item.code
        for item in verify_agentic_network_lock(payload, document, COMPOSITION)
    }
    assert expected in codes


def test_mutable_subject_revision_is_rejected() -> None:
    document = _document()
    document["agentic_network"]["subject_revision"] = "refs/heads/main"
    with pytest.raises(GovernanceError) as excinfo:
        build_agentic_network_lock(document, COMPOSITION)
    assert any(
        item.code == "AN_LOCK_REVISION_MUTABLE"
        for item in excinfo.value.diagnostics
    )


def test_lock_check_flags_disk_drift(tmp_path: Path) -> None:
    document = _document()
    out_dir = tmp_path / "artifacts"
    write_agentic_network_artifacts(document, COMPOSITION, out_dir)
    payload = build_agentic_network_lock(document, COMPOSITION)
    assert (
        verify_agentic_network_lock(
            payload, document, COMPOSITION, artifacts_dir=out_dir
        )
        == ()
    )

    (out_dir / "identity_manifest.json").write_text("tampered", encoding="utf-8")
    (out_dir / "network_manifest.json").unlink()
    (out_dir / "stray_artifact.json").write_text("{}", encoding="utf-8")
    codes = {
        item.code
        for item in verify_agentic_network_lock(
            payload, document, COMPOSITION, artifacts_dir=out_dir
        )
    }
    assert {
        "AN_LOCK_ARTIFACT_MISMATCH",
        "AN_LOCK_ARTIFACT_MISSING",
        "AN_LOCK_ARTIFACT_UNEXPECTED",
    } <= codes


def test_symlinked_artifact_is_not_a_regular_file(tmp_path: Path) -> None:
    document = _document()
    out_dir = tmp_path / "artifacts"
    write_agentic_network_artifacts(document, COMPOSITION, out_dir)
    payload = build_agentic_network_lock(document, COMPOSITION)
    original = out_dir / "identity_manifest.json"
    moved = tmp_path / "identity_manifest.real.json"
    moved.write_bytes(original.read_bytes())
    original.unlink()
    create_symlink_or_skip(original, moved)
    codes = {
        item.code
        for item in verify_agentic_network_lock(
            payload, document, COMPOSITION, artifacts_dir=out_dir
        )
    }
    assert "AN_LOCK_ARTIFACT_MISMATCH" in codes


def test_writer_refuses_symlinked_artifact_targets(tmp_path: Path) -> None:
    # AN3-AUD-001: a pre-planted symlink named like a governed artifact must
    # never redirect the write outside the output directory.
    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()
    victim = tmp_path / "victim.json"
    victim.write_text("untouched", encoding="utf-8")
    create_symlink_or_skip(out_dir / "identity_manifest.json", victim)
    with pytest.raises(GovernanceError) as excinfo:
        write_agentic_network_artifacts(_document(), COMPOSITION, out_dir)
    assert any(
        item.code == "AN_ARTIFACT_OUTPUT_INVALID"
        for item in excinfo.value.diagnostics
    )
    assert victim.read_text(encoding="utf-8") == "untouched"


def test_remote_and_device_paths_are_rejected(tmp_path: Path) -> None:
    document = _document()
    with pytest.raises(GovernanceError):
        write_agentic_network_artifacts(
            document, COMPOSITION, "//attacker/share/out"
        )
    with pytest.raises(GovernanceError):
        load_agentic_network_lock("//attacker/share/nornyx.agentic_network.lock")


def test_malformed_lock_fails_closed(tmp_path: Path) -> None:
    target = tmp_path / "broken.lock"
    target.write_text("{\"schema\": \"nornyx.agentic_network_lock.v1\"", encoding="utf-8")
    with pytest.raises(GovernanceError) as excinfo:
        load_agentic_network_lock(target)
    assert any(
        item.code == "AN_LOCK_MALFORMED" for item in excinfo.value.diagnostics
    )

    duplicate = tmp_path / "duplicate.lock"
    duplicate.write_text(
        "{\"schema\": \"nornyx.agentic_network_lock.v1\", \"schema\": \"x\"}",
        encoding="utf-8",
    )
    with pytest.raises(GovernanceError):
        load_agentic_network_lock(duplicate)


def test_missing_network_block_fails_generation() -> None:
    document = _document()
    del document["agentic_network"]
    with pytest.raises(GovernanceError) as excinfo:
        build_agentic_network_artifacts(document, COMPOSITION)
    assert any(
        item.code == "AN_ARTIFACT_NETWORK_MISSING"
        for item in excinfo.value.diagnostics
    )


def test_cli_generate_lock_and_lock_check_flow(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    lock_path = tmp_path / "nornyx.agentic_network.lock"

    code, payload = _cli(
        [
            "agentic-network",
            "generate",
            str(EXAMPLE),
            "--out",
            str(artifacts_dir),
            "--as-of",
            AS_OF,
        ]
    )
    assert code == 0 and payload["status"] == "pass"
    assert payload["artifact_count"] == 10

    code, payload = _cli(
        [
            "agentic-network",
            "lock",
            str(EXAMPLE),
            "--artifacts",
            str(artifacts_dir),
            "--out",
            str(lock_path),
            "--as-of",
            AS_OF,
        ]
    )
    assert code == 0 and payload["status"] == "pass"
    assert payload["lock_digest"] == GOLDEN_EXAMPLE_LOCK_DIGEST

    code, payload = _cli(
        [
            "agentic-network",
            "lock-check",
            str(EXAMPLE),
            "--lock",
            str(lock_path),
            "--artifacts",
            str(artifacts_dir),
            "--as-of",
            AS_OF,
        ]
    )
    assert code == 0 and payload["status"] == "pass"
    assert payload["diagnostics"] == []


def test_cli_lock_check_fails_on_contract_drift(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    lock_path = tmp_path / "nornyx.agentic_network.lock"
    document = _document()
    write_agentic_network_artifacts(document, COMPOSITION, artifacts_dir)
    write_agentic_network_lock(
        build_agentic_network_lock(document, COMPOSITION), lock_path
    )

    import shutil

    shutil.copytree(
        EXAMPLE.parent / "governance_evidence", tmp_path / "governance_evidence"
    )
    drifted = tmp_path / "drifted.nyx"
    document["capabilities"][0]["risk"] = "medium"
    drifted.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    code, payload = _cli(
        [
            "agentic-network",
            "lock-check",
            str(drifted),
            "--lock",
            str(lock_path),
            "--artifacts",
            str(artifacts_dir),
            "--as-of",
            AS_OF,
        ]
    )
    assert code == 1 and payload["status"] == "fail"
    codes = {item["code"] for item in payload["diagnostics"]}
    assert "AN_LOCK_SOURCE_STALE" in codes


def test_cli_generate_refuses_invalid_contracts(tmp_path: Path) -> None:
    document = _document()
    document["agent_identities"][0]["capability_refs"].append("missing_capability")
    invalid = tmp_path / "invalid.nyx"
    invalid.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    out = StringIO()
    with redirect_stdout(out):
        code = cli_main(
            [
                "agentic-network",
                "generate",
                str(invalid),
                "--out",
                str(tmp_path / "artifacts"),
                "--as-of",
                AS_OF,
            ]
        )
    assert code == 1
    assert "AN_CAPABILITY_UNKNOWN" in out.getvalue()
    assert not (tmp_path / "artifacts").exists()


def test_agentic_artifact_error_is_a_governance_error() -> None:
    assert issubclass(AgenticArtifactError, GovernanceError)


def test_failures_raise_the_module_error_type(tmp_path: Path) -> None:
    # AN-CLOSE-AUD-001: generation and lock failures must raise the module's
    # own AgenticArtifactError so narrow handlers observe them, not only the
    # GovernanceError base.
    smuggled = _document()
    smuggled["agentic_network"]["trust_zones"][0]["endpoint_url"] = (
        "https://collector.example/events"
    )
    with pytest.raises(AgenticArtifactError) as excinfo:
        build_agentic_network_artifacts(smuggled, COMPOSITION)
    assert any(
        item.code == "AN_ARTIFACT_FORBIDDEN_FIELD"
        for item in excinfo.value.diagnostics
    )

    broken = tmp_path / "broken.lock"
    broken.write_text(
        "{\"schema\": \"nornyx.agentic_network_lock.v1\"", encoding="utf-8"
    )
    with pytest.raises(AgenticArtifactError) as excinfo:
        load_agentic_network_lock(broken)
    assert any(
        item.code == "AN_LOCK_MALFORMED" for item in excinfo.value.diagnostics
    )

    mutable = _document()
    mutable["agentic_network"]["subject_revision"] = "draft-1"
    with pytest.raises(AgenticArtifactError):
        build_agentic_network_lock(mutable, COMPOSITION)


def test_generation_uses_no_network_or_processes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("artifact generation attempted an external operation")

    original_import = builtins.__import__

    def guarded_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.split(".", 1)[0] in {"crewai", "langgraph"}:
            raise AssertionError("artifact generation constructed a framework")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)

    document = _document()
    write_agentic_network_artifacts(document, COMPOSITION, tmp_path / "artifacts")
    payload = build_agentic_network_lock(document, COMPOSITION)
    assert (
        verify_agentic_network_lock(
            payload, document, COMPOSITION, artifacts_dir=tmp_path / "artifacts"
        )
        == ()
    )
