from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import sys

import pytest
import yaml

from nornyx.cli import main
from nornyx.governed_package import (
    verify_package_lock,
    verify_registered_artifact_hashes,
)
from nornyx.governance import GovernanceError
from nornyx.governance.architecture import import_architecture_evidence
from nornyx.governance.evidence_validation import validate_governance_evidence_file
from nornyx.governance.loader import (
    _load_bundled_pack,
    load_local_pack,
    load_pack_bytes,
    read_local_file_bytes,
)
from nornyx.governance.locks import load_lock, lock_for_packs, write_lock
from nornyx.governance.registry import GovernanceRegistry
from nornyx.governance.runtime import registry_for_contract, registry_for_directory
from nornyx.governance.schemas import canonical_pack_hash
from nornyx.parser import NornyxParseError, load_nyx
from nornyx.workspace import WorkspaceError, check_workspace


FIXTURES = Path(__file__).parent / "fixtures" / "governance_extension"


def _codes(exc: GovernanceError) -> set[str]:
    return {item.code for item in exc.diagnostics}


def _payload(name: str) -> dict[str, object]:
    return yaml.safe_load((FIXTURES / name).read_text(encoding="utf-8"))


def _write_pack(path: Path, payload: dict[str, object]) -> None:
    material = deepcopy(payload)
    integrity = material["integrity"]
    assert isinstance(integrity, dict)
    integrity["content_hash"] = canonical_pack_hash(material)
    path.write_text(
        yaml.safe_dump(material, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )


def _directory_symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        if sys.platform.startswith("linux"):
            pytest.fail(f"real Linux symlink creation failed: {exc}")
        pytest.skip(f"symlink creation is unavailable: {exc}")


@pytest.mark.parametrize("api", ["registry", "loader"])
def test_aud009_exported_api_rejects_symlink_ancestor(
    tmp_path: Path,
    api: str,
) -> None:
    real = tmp_path / "real"
    project = real / "project"
    profiles = project / ".nornyx" / "profiles"
    profiles.mkdir(parents=True)
    _write_pack(profiles / "profile.yaml", _payload("valid_profile_v1.yaml"))
    alias = tmp_path / "alias"
    _directory_symlink_or_skip(alias, real)
    aliased_project = alias / "project"

    with pytest.raises(GovernanceError) as caught:
        if api == "registry":
            registry_for_directory(aliased_project)
        else:
            load_local_pack(
                aliased_project / ".nornyx" / "profiles" / "profile.yaml",
                allowed_root=aliased_project / ".nornyx" / "profiles",
            )
    assert _codes(caught.value) == {"PACK_SYMLINK_REJECTED"}


@pytest.mark.parametrize(
    "api",
    ["registry", "register_path", "register_directory", "reader", "evidence"],
)
def test_aud009_caller_supplied_weak_trust_root_cannot_hide_symlink(
    tmp_path: Path,
    api: str,
) -> None:
    real = tmp_path / "real"
    project = real / "project"
    profiles = project / ".nornyx" / "profiles"
    profiles.mkdir(parents=True)
    pack_path = profiles / "profile.yaml"
    _write_pack(pack_path, _payload("valid_profile_v1.yaml"))
    evidence_path = project / "evidence.yaml"
    evidence_path.write_text("subject_revision: rev\nrecords: []\n", encoding="utf-8")
    alias = tmp_path / "alias"
    _directory_symlink_or_skip(alias, real)
    aliased_project = alias / "project"
    aliased_profiles = aliased_project / ".nornyx" / "profiles"
    aliased_pack = aliased_profiles / "profile.yaml"

    with pytest.raises(GovernanceError) as caught:
        if api == "registry":
            registry_for_directory(aliased_project, trust_root=aliased_project)
        elif api == "register_path":
            GovernanceRegistry().register_path(
                aliased_pack,
                allowed_root=aliased_profiles,
                trust_root=aliased_profiles,
                source_tier="project",
            )
        elif api == "register_directory":
            GovernanceRegistry().register_directory(
                aliased_profiles,
                trust_root=aliased_profiles,
                source_tier="project",
            )
        elif api == "reader":
            read_local_file_bytes(
                aliased_pack,
                allowed_root=aliased_profiles,
                trust_root=aliased_profiles,
                code_prefix="PACK",
                noun="Pack",
            )
        else:
            validate_governance_evidence_file(
                alias / "project" / "evidence.yaml",
                allowed_root=aliased_project,
                trust_root=aliased_project,
            )
    assert _codes(caught.value) in (
        {"PACK_SYMLINK_REJECTED"},
        {"EVIDENCE_SYMLINK_REJECTED"},
    )


def test_aud009_safe_explicit_trust_root_remains_supported(tmp_path: Path) -> None:
    path = tmp_path / "profile.yaml"
    _write_pack(path, _payload("valid_profile_v1.yaml"))
    pack = load_local_pack(
        path,
        allowed_root=tmp_path,
        trust_root=tmp_path,
        source_tier="project",
    )
    assert pack.id == "org.example.delivery_profile"


def test_aud009_trust_root_must_contain_permitted_root(tmp_path: Path) -> None:
    path = tmp_path / "profile.yaml"
    _write_pack(path, _payload("valid_profile_v1.yaml"))
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    with pytest.raises(GovernanceError) as caught:
        load_local_pack(
            path,
            allowed_root=tmp_path,
            trust_root=unrelated,
            source_tier="project",
        )
    assert _codes(caught.value) == {"PACK_PATH_OUTSIDE_ROOT"}


def _valid_lock_bytes() -> bytes:
    registry = GovernanceRegistry.builtins()
    lock = lock_for_packs([registry.resolve_profile("minimal")])
    return (json.dumps(lock.to_dict(), indent=2) + "\n").encode("utf-8")


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("symlink", "PACK_SYMLINK_REJECTED"),
        ("dangling_symlink", "PACK_SYMLINK_REJECTED"),
        ("duplicate_key", "PACK_LOCK_DUPLICATE_KEY"),
        ("oversized", "PACK_LIMIT_EXCEEDED"),
        ("malformed_utf8", "PACK_ENCODING_INVALID"),
    ],
)
def test_aud010_lock_loader_rejects_unsafe_inputs(
    tmp_path: Path,
    case: str,
    expected: str,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    lock_path = project / "nornyx.profiles.lock"
    if case == "symlink":
        outside = tmp_path / "outside.lock"
        outside.write_bytes(_valid_lock_bytes())
        try:
            lock_path.symlink_to(outside)
        except (NotImplementedError, OSError) as exc:
            pytest.skip(f"symlink creation is unavailable: {exc}")
    elif case == "dangling_symlink":
        try:
            lock_path.symlink_to(tmp_path / "missing.lock")
        except (NotImplementedError, OSError) as exc:
            pytest.skip(f"symlink creation is unavailable: {exc}")
    elif case == "duplicate_key":
        lock_path.write_bytes(
            b'{"schema":"nornyx.profiles_lock.v1",'
            b'"schema":"nornyx.profiles_lock.v1","resolved":[]}\n'
        )
    elif case == "oversized":
        lock_path.write_bytes(b" " * (512 * 1024 + 1))
    else:
        lock_path.write_bytes(b"\xff")

    with pytest.raises(GovernanceError) as caught:
        load_lock(lock_path)
    assert expected in _codes(caught.value)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"[]\n", "PACK_LOCK_INVALID"),
        (b'{"schema":"nornyx.profiles_lock.v1","resolved":[],"x":NaN}\n', "PACK_LOCK_INVALID"),
        (b'{"schema":"wrong","resolved":[]}\n', "PACK_SCHEMA_INVALID"),
        (
            b'{"schema":"nornyx.profiles_lock.v1","resolved":[],"meta":{"x":1,"x":2}}\n',
            "PACK_LOCK_DUPLICATE_KEY",
        ),
    ],
)
def test_aud010_lock_json_is_strict_and_schema_validated(
    tmp_path: Path,
    raw: bytes,
    expected: str,
) -> None:
    path = tmp_path / "nornyx.profiles.lock"
    path.write_bytes(raw)
    with pytest.raises(GovernanceError) as caught:
        load_lock(path)
    assert expected in _codes(caught.value)


def test_aud010_lock_path_must_remain_in_explicit_project_root(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.lock"
    outside.write_bytes(_valid_lock_bytes())
    with pytest.raises(GovernanceError) as caught:
        load_lock(outside, allowed_root=project)
    assert _codes(caught.value) == {"PACK_PATH_OUTSIDE_ROOT"}


def test_aud010_lock_directory_is_not_treated_as_absent(tmp_path: Path) -> None:
    lock_path = tmp_path / "nornyx.profiles.lock"
    lock_path.mkdir()
    with pytest.raises(GovernanceError) as caught:
        load_lock(lock_path)
    assert _codes(caught.value) == {"PACK_PATH_TYPE_INVALID"}


def test_aud010_absent_lock_remains_an_optional_positive_case(
    tmp_path: Path,
) -> None:
    from nornyx.governance.loader import inspect_local_file

    assert (
        inspect_local_file(
            tmp_path / "nornyx.profiles.lock",
            allowed_root=tmp_path,
            code_prefix="PACK",
            noun="Profile lock",
            allow_missing=True,
        )
        is None
    )


def test_aud010_write_lock_refuses_existing_symlink(tmp_path: Path) -> None:
    outside = tmp_path / "outside.lock"
    outside.write_text("unchanged\n", encoding="utf-8")
    target = tmp_path / "nornyx.profiles.lock"
    try:
        target.symlink_to(outside)
    except (NotImplementedError, OSError) as exc:
        if sys.platform.startswith("linux"):
            pytest.fail(f"real Linux symlink creation failed: {exc}")
        pytest.skip(f"symlink creation is unavailable: {exc}")
    registry = GovernanceRegistry.builtins()
    lock = lock_for_packs([registry.resolve_profile("minimal")])
    with pytest.raises(GovernanceError) as caught:
        write_lock(target, lock)
    assert _codes(caught.value) == {"PACK_SYMLINK_REJECTED"}
    assert outside.read_text(encoding="utf-8") == "unchanged\n"


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission-bit compatibility")
def test_aud010_atomic_lock_write_preserves_posix_modes(tmp_path: Path) -> None:
    registry = GovernanceRegistry.builtins()
    lock = lock_for_packs([registry.resolve_profile("minimal")])
    control = tmp_path / "control.lock"
    control.write_text("control\n", encoding="utf-8")

    new_target = tmp_path / "new.lock"
    write_lock(new_target, lock)
    assert (new_target.stat().st_mode & 0o777) == (control.stat().st_mode & 0o777)

    existing_target = tmp_path / "existing.lock"
    existing_target.write_text("old\n", encoding="utf-8")
    existing_target.chmod(0o640)
    write_lock(existing_target, lock)
    assert existing_target.stat().st_mode & 0o777 == 0o640


@pytest.mark.parametrize(
    ("argv_prefix", "expected_exit"),
    [
        (("check",), 1),
        (("governance", "resolve"), 2),
        (("governance", "explain"), 2),
        (("governance", "matrix"), 2),
    ],
)
def test_aud010_cli_lock_symlink_fails_all_governance_consumers(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    argv_prefix: tuple[str, ...],
    expected_exit: int,
) -> None:
    contract = tmp_path / "contract.nyx"
    contract.write_text(
        "nornyx: '0.1'\nproject:\n  name: Audit\n  profile: minimal\n",
        encoding="utf-8",
    )
    outside = tmp_path / "outside.lock"
    outside.write_bytes(_valid_lock_bytes())
    try:
        (tmp_path / "nornyx.profiles.lock").symlink_to(outside)
    except (NotImplementedError, OSError) as exc:
        if sys.platform.startswith("linux"):
            pytest.fail(f"real Linux symlink creation failed: {exc}")
        pytest.skip(f"symlink creation is unavailable: {exc}")
    argv = [*argv_prefix, str(contract)]
    if argv_prefix[0] == "governance":
        argv.extend(["--as-of", "2026-07-14T00:00:00Z", "--json"])
    assert main(argv) == expected_exit
    assert "PACK_SYMLINK_REJECTED" in capsys.readouterr().out


@pytest.mark.parametrize(
    "remote_path",
    [
        r"\\server\share\pack.yaml",
        "//server/share/pack.yaml",
        r"\\?\UNC\server\share\pack.yaml",
        r"\\?\C:\project\pack.yaml",
        r"\\.\PhysicalDrive0",
        r"\??\C:\project\pack.yaml",
        r"\Device\HarddiskVolume1\pack.yaml",
        r"\GLOBAL??\C:\project\pack.yaml",
        "smb://server/share/pack.yaml",
        "nfs://server/share/pack.yaml",
        "file://server/share/pack.yaml",
        "NUL",
        r"C:\project\COM1.txt",
    ],
)
def test_aud011_windows_remote_paths_are_rejected_before_filesystem_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    remote_path: str,
) -> None:
    def unexpected_filesystem_call(*args: object, **kwargs: object) -> os.stat_result:
        raise AssertionError("filesystem inspection ran before lexical path rejection")

    monkeypatch.setattr(os, "lstat", unexpected_filesystem_call)
    with pytest.raises(GovernanceError) as caught:
        read_local_file_bytes(
            remote_path,
            allowed_root=tmp_path,
            code_prefix="PACK",
            noun="Pack",
        )
    assert _codes(caught.value) == {"PACK_REMOTE_SOURCE_REJECTED"}


@pytest.mark.parametrize("boundary", ["path", "allowed_root", "trust_root"])
def test_aud011_every_loader_boundary_is_lexically_screened_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    unsafe = r"\\server\share\pack.yaml"
    values: dict[str, str | Path | None] = {
        "path": tmp_path / "pack.yaml",
        "allowed_root": tmp_path,
        "trust_root": None,
    }
    values[boundary] = unsafe

    def unexpected_filesystem_call(*args: object, **kwargs: object) -> os.stat_result:
        raise AssertionError("filesystem inspection ran before lexical path rejection")

    monkeypatch.setattr(os, "lstat", unexpected_filesystem_call)
    with pytest.raises(GovernanceError) as caught:
        read_local_file_bytes(
            values["path"],  # type: ignore[arg-type]
            allowed_root=values["allowed_root"],  # type: ignore[arg-type]
            trust_root=values["trust_root"],  # type: ignore[arg-type]
            code_prefix="PACK",
            noun="Pack",
        )
    assert _codes(caught.value) == {"PACK_REMOTE_SOURCE_REJECTED"}


@pytest.mark.parametrize(
    ("api", "expected"),
    [
        ("registry_contract", "PACK_REMOTE_SOURCE_REJECTED"),
        ("registry_directory", "PACK_REMOTE_SOURCE_REJECTED"),
        ("lock", "PACK_REMOTE_SOURCE_REJECTED"),
        ("evidence", "EVIDENCE_REMOTE_SOURCE_REJECTED"),
        ("architecture", "ARCH_REPORT_REMOTE_SOURCE_REJECTED"),
    ],
)
def test_aud011_public_governance_path_apis_reject_before_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    api: str,
    expected: str,
) -> None:
    unsafe = r"\\server\share\input.yaml"

    def unexpected_filesystem_call(*args: object, **kwargs: object) -> os.stat_result:
        raise AssertionError("filesystem inspection ran before lexical path rejection")

    monkeypatch.setattr(os, "lstat", unexpected_filesystem_call)
    with pytest.raises(GovernanceError) as caught:
        if api == "registry_contract":
            registry_for_contract(unsafe)
        elif api == "registry_directory":
            registry_for_directory(unsafe)
        elif api == "lock":
            load_lock(unsafe)
        elif api == "evidence":
            validate_governance_evidence_file(unsafe, allowed_root=tmp_path)
        else:
            import_architecture_evidence(unsafe, allowed_root=tmp_path)
    assert _codes(caught.value) == {expected}


def test_aud011_direct_contract_parser_rejects_before_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unsafe = r"\\server\share\contract.nyx"

    def unexpected_filesystem_call(*args: object, **kwargs: object) -> bool:
        raise AssertionError("filesystem inspection ran before lexical path rejection")

    monkeypatch.setattr(Path, "exists", unexpected_filesystem_call)
    with pytest.raises(NornyxParseError, match="remote or device-backed"):
        load_nyx(unsafe)


@pytest.mark.parametrize(
    "argv",
    [
        ["profiles", "validate", r"\\server\share\profile.yaml"],
        ["modules", "validate", r"\\server\share\module.yaml"],
        ["evidence", "validate", r"\\server\share\evidence.yaml"],
    ],
)
def test_aud011_validation_clis_reject_before_probe(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
) -> None:
    def unexpected_filesystem_call(*args: object, **kwargs: object) -> os.stat_result:
        raise AssertionError("filesystem inspection ran before lexical path rejection")

    monkeypatch.setattr(os, "lstat", unexpected_filesystem_call)
    assert main(argv) != 0
    assert "REMOTE_SOURCE_REJECTED" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("fixture", "kind"),
    [
        ("valid_profile_v1.yaml", "profile"),
        ("valid_module_v1.yaml", "module"),
    ],
)
@pytest.mark.parametrize("reserved_id", ["nornyx.builtin", "nornyx.builtin.forged"])
@pytest.mark.parametrize("source_tier", ["project", "org", "explicit_path"])
def test_aud018_reserved_namespace_root_is_rejected(
    tmp_path: Path,
    fixture: str,
    kind: str,
    reserved_id: str,
    source_tier: str,
) -> None:
    payload = _payload(fixture)
    payload["id"] = reserved_id
    path = tmp_path / f"{kind}.yaml"
    _write_pack(path, payload)

    with pytest.raises(GovernanceError) as caught:
        load_local_pack(
            path,
            allowed_root=tmp_path,
            source_tier=source_tier,  # type: ignore[arg-type]
        )
    assert _codes(caught.value) == {"PACK_RESERVED_NAMESPACE"}


def test_aud018_local_loader_cannot_claim_builtin_tier(tmp_path: Path) -> None:
    path = tmp_path / "profile.yaml"
    payload = _payload("valid_profile_v1.yaml")
    payload["id"] = "nornyx.builtin.forged"
    _write_pack(path, payload)
    with pytest.raises(GovernanceError) as caught:
        load_local_pack(path, allowed_root=tmp_path, source_tier="builtin")
    assert _codes(caught.value) == {"PACK_SOURCE_TIER_INVALID"}


def test_aud018_public_bytes_loader_cannot_claim_builtin_tier() -> None:
    raw = (FIXTURES / "valid_profile_v1.yaml").read_bytes()
    with pytest.raises(GovernanceError) as caught:
        load_pack_bytes(raw, source_path="forged.yaml", source_tier="builtin")
    assert _codes(caught.value) == {"PACK_SOURCE_TIER_INVALID"}


def test_aud018_programmatic_nonbuiltin_pack_is_defensively_rejected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "profile.yaml"
    _write_pack(path, _payload("valid_profile_v1.yaml"))
    profile = load_local_pack(path, allowed_root=tmp_path, source_tier="project")
    forged = replace(profile, id="nornyx.builtin")
    with pytest.raises(GovernanceError) as caught:
        GovernanceRegistry().register_profile(forged)  # type: ignore[arg-type]
    assert _codes(caught.value) == {"PACK_RESERVED_NAMESPACE"}


def test_aud018_programmatic_builtin_tier_claim_is_rejected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "profile.yaml"
    _write_pack(path, _payload("valid_profile_v1.yaml"))
    profile = load_local_pack(path, allowed_root=tmp_path, source_tier="project")
    forged = replace(
        profile,
        id="nornyx.builtin.forged",
        provenance=replace(profile.provenance, source_tier="builtin"),
    )
    with pytest.raises(GovernanceError) as caught:
        GovernanceRegistry().register_profile(forged)  # type: ignore[arg-type]
    assert _codes(caught.value) == {"PACK_SOURCE_TIER_INVALID"}


def test_aud018_private_bundled_loader_requires_catalog_capability() -> None:
    with pytest.raises(GovernanceError) as caught:
        _load_bundled_pack(object(), capability=object())  # type: ignore[arg-type]
    assert _codes(caught.value) == {"PACK_SOURCE_TIER_INVALID"}


def test_aud018_authentic_packaged_builtin_remains_publicly_registerable() -> None:
    packaged = GovernanceRegistry.builtins().resolve_profile("minimal")
    registry = GovernanceRegistry()
    registry.register_profile(packaged)
    assert registry.resolve_profile("minimal") == packaged


@pytest.mark.parametrize("command", ["resolve", "explain", "matrix"])
@pytest.mark.parametrize("as_json", [False, True])
def test_aud019_invalid_lock_uses_documented_exit_code(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    command: str,
    as_json: bool,
) -> None:
    contract = tmp_path / "contract.nyx"
    contract.write_text(
        "nornyx: '0.1'\nproject:\n  name: Audit\n  profile: minimal\n",
        encoding="utf-8",
        newline="\n",
    )
    (tmp_path / "nornyx.profiles.lock").write_text(
        "{}\n",
        encoding="utf-8",
        newline="\n",
    )
    argv = [
        "governance",
        command,
        str(contract),
        "--as-of",
        "2026-07-14T00:00:00Z",
    ]
    if as_json:
        argv.append("--json")

    assert main(argv) == 2
    assert "PACK_SCHEMA_INVALID" in capsys.readouterr().out


@pytest.mark.parametrize("command", ["resolve", "explain", "matrix"])
@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize(
    ("lock_bytes", "expected_code"),
    [
        (b"{}\n", "PACK_SCHEMA_INVALID"),
        (
            b'{"schema":"nornyx.profiles_lock.v1",'
            b'"schema":"nornyx.profiles_lock.v1","resolved":[]}\n',
            "PACK_LOCK_DUPLICATE_KEY",
        ),
        (b"\xff\n", "PACK_ENCODING_INVALID"),
        (
            b'{"schema":"nornyx.profiles_lock.v1","resolved":[]}\n',
            "PACK_LOCK_SET_MISMATCH",
        ),
    ],
)
def test_aud019_all_invalid_lock_classes_use_exit_two(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    command: str,
    as_json: bool,
    lock_bytes: bytes,
    expected_code: str,
) -> None:
    contract = tmp_path / "contract.nyx"
    contract.write_text(
        "nornyx: '0.1'\nproject:\n  name: Audit\n  profile: minimal\n",
        encoding="utf-8",
        newline="\n",
    )
    (tmp_path / "nornyx.profiles.lock").write_bytes(lock_bytes)
    argv = [
        "governance",
        command,
        str(contract),
        "--as-of",
        "2026-07-14T00:00:00Z",
    ]
    if as_json:
        argv.append("--json")

    assert main(argv) == 2
    output = capsys.readouterr().out
    assert expected_code in output
    if as_json:
        payload = json.loads(output)
        assert expected_code in {item["code"] for item in payload["diagnostics"]}


@pytest.mark.parametrize("command", ["resolve", "explain", "matrix"])
def test_aud019_invalid_lock_path_type_uses_exit_two(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    contract = tmp_path / "contract.nyx"
    contract.write_text(
        "nornyx: '0.1'\nproject:\n  name: Audit\n  profile: minimal\n",
        encoding="utf-8",
        newline="\n",
    )
    (tmp_path / "nornyx.profiles.lock").mkdir()

    assert main(
        [
            "governance",
            command,
            str(contract),
            "--as-of",
            "2026-07-14T00:00:00Z",
            "--json",
        ]
    ) == 2
    assert "PACK_PATH_TYPE_INVALID" in capsys.readouterr().out


@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize(
    ("lock_bytes", "expected_code"),
    [
        (b"{}\n", "PACK_SCHEMA_INVALID"),
        (
            b'{"schema":"nornyx.profiles_lock.v1",'
            b'"schema":"nornyx.profiles_lock.v1","resolved":[]}\n',
            "PACK_LOCK_DUPLICATE_KEY",
        ),
        (b"\xff\n", "PACK_ENCODING_INVALID"),
        (
            b'{"schema":"nornyx.profiles_lock.v1","resolved":[]}\n',
            "PACK_LOCK_SET_MISMATCH",
        ),
    ],
)
def test_aud019_profiles_resolve_uses_the_same_lock_exit_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    as_json: bool,
    lock_bytes: bytes,
    expected_code: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "nornyx.profiles.lock").write_bytes(lock_bytes)
    argv = ["profiles", "resolve", "minimal"]
    if as_json:
        argv.append("--json")

    assert main(argv) == 2
    output = capsys.readouterr().out
    assert expected_code in output
    if as_json:
        payload = json.loads(output)
        assert expected_code in {item["code"] for item in payload["diagnostics"]}


def test_aud019_schema_invalid_pack_remains_exit_one(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pack = tmp_path / "not-a-lock.yaml"
    payload = _payload("valid_profile_v1.yaml")
    payload.pop("name")
    _write_pack(pack, payload)

    assert main(["profiles", "validate", str(pack), "--json"]) == 1
    assert "PACK_SCHEMA_INVALID" in capsys.readouterr().out


@pytest.mark.parametrize("command", ["resolve", "explain", "matrix"])
def test_safe_contained_parent_component_keeps_canonical_contract_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    contract = tmp_path / "contract.nyx"
    contract.write_text(
        "nornyx: '0.1'\nproject:\n  name: Audit\n  profile: minimal\n",
        encoding="utf-8",
    )
    (tmp_path / "subdir").mkdir()
    supplied = tmp_path / "subdir" / ".." / "contract.nyx"
    assert main(
        [
            "governance",
            command,
            str(supplied),
            "--as-of",
            "2026-07-14T00:00:00Z",
            "--json",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["contract"] == contract.resolve().as_posix()


def test_adjacent_workspace_member_parent_traversal_is_rejected(
    tmp_path: Path,
) -> None:
    project = tmp_path / "workspace"
    project.mkdir()
    outside = tmp_path / "outside.nyx"
    outside.write_text(
        "nornyx: '0.1'\npolicies:\n- name: OrgPolicy\n  rules:\n  - deny external_write\n",
        encoding="utf-8",
    )
    manifest = project / "nornyx.workspace.yaml"
    manifest.write_text(
        "workspace: Audit\n"
        "policies:\n  OrgPolicy:\n  - deny external_write\n"
        "members:\n- ../outside.nyx\n",
        encoding="utf-8",
    )
    with pytest.raises(WorkspaceError, match="WORKSPACE_PATH_OUTSIDE_ROOT"):
        check_workspace(manifest, write=True)
    assert outside.read_text(encoding="utf-8").startswith("nornyx: '0.1'")


def test_adjacent_governed_package_lock_artifact_cannot_traverse_parent(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    manifest = package / "package_manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    lock = {
        "manifest_sha256": "sha256:ignored",
        "artifact_hashes": [
            {"path": "../outside.txt", "sha256": "sha256:forged"}
        ],
    }
    (package / "package_lock.json").write_text(
        json.dumps(lock),
        encoding="utf-8",
    )
    diagnostics = verify_package_lock(package)
    assert any(item.code == "UNSAFE_PACKAGE_LOCK_ARTIFACT" for item in diagnostics)


def test_adjacent_governed_package_missing_artifact_diagnostic_is_compatible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    package = Path("package")
    package.mkdir()
    manifest = package / "package_manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    (package / "package_lock.json").write_text(
        json.dumps(
            {
                "manifest_sha256": "mismatch",
                "artifact_hashes": [
                    {"path": "missing.txt", "sha256": "sha256:missing"}
                ],
            }
        ),
        encoding="utf-8",
    )
    diagnostic = next(
        item
        for item in verify_package_lock(package)
        if item.code == "PACKAGE_LOCK_ARTIFACT_MISSING"
    )
    assert diagnostic.message == "locked artifact missing: missing.txt"
    assert diagnostic.path == "package/missing.txt"


def test_adjacent_registered_missing_artifact_diagnostic_is_compatible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    source = Path("source")
    source.mkdir()
    package = {
        "registration_mode": "existing",
        "source_path": "source",
        "artifacts": [
            {"path": "missing.txt", "sha256": "sha256:missing"}
        ],
    }
    diagnostic = verify_registered_artifact_hashes(package, Path("package"))[0]
    assert diagnostic.code == "REGISTERED_ARTIFACT_MISSING"
    assert diagnostic.message == "registered artifact missing from source: missing.txt"
    assert diagnostic.path == "source/missing.txt"


def test_adjacent_governed_package_hash_mismatch_paths_remain_lexical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    package_dir = Path("package")
    package_dir.mkdir()
    (package_dir / "package_manifest.json").write_text("{}\n", encoding="utf-8")
    (package_dir / "artifact.txt").write_text("actual\n", encoding="utf-8")
    (package_dir / "package_lock.json").write_text(
        json.dumps(
            {
                "manifest_sha256": "mismatch",
                "artifact_hashes": [
                    {"path": "artifact.txt", "sha256": "sha256:wrong"}
                ],
            }
        ),
        encoding="utf-8",
    )
    package_diagnostic = next(
        item
        for item in verify_package_lock(package_dir)
        if item.code == "PACKAGE_LOCK_ARTIFACT_HASH_MISMATCH"
    )
    assert package_diagnostic.path == "package/artifact.txt"

    source = Path("source")
    source.mkdir()
    (source / "artifact.txt").write_text("actual\n", encoding="utf-8")
    registered_diagnostic = verify_registered_artifact_hashes(
        {
            "registration_mode": "existing",
            "source_path": "source",
            "artifacts": [
                {"path": "artifact.txt", "sha256": "sha256:wrong"}
            ],
        },
        package_dir,
    )[0]
    assert registered_diagnostic.code == "REGISTERED_ARTIFACT_HASH_MISMATCH"
    assert registered_diagnostic.path == "source/artifact.txt"


@pytest.mark.parametrize(
    ("kind", "message"),
    [
        ("missing", "Architecture report is missing, unreadable, or outside the permitted root."),
        ("directory", "Architecture report must be a regular local file."),
    ],
)
def test_adjacent_architecture_unavailable_diagnostic_remains_compatible(
    tmp_path: Path,
    kind: str,
    message: str,
) -> None:
    report = tmp_path / "report.json"
    if kind == "directory":
        report.mkdir()
    with pytest.raises(GovernanceError) as caught:
        import_architecture_evidence(report, allowed_root=tmp_path)
    assert _codes(caught.value) == {"ARCH_REPORT_UNAVAILABLE"}
    assert caught.value.diagnostics[0].message == message
