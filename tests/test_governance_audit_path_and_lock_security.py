from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
import yaml

from nornyx.cli import main
from nornyx.governance import GovernanceError
from nornyx.governance.loader import load_local_pack, read_local_file_bytes
from nornyx.governance.locks import load_lock, lock_for_packs
from nornyx.governance.registry import GovernanceRegistry
from nornyx.governance.runtime import registry_for_directory
from nornyx.governance.schemas import canonical_pack_hash


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
    "remote_path",
    [
        r"\\server\share\pack.yaml",
        "//server/share/pack.yaml",
        r"\\?\UNC\server\share\pack.yaml",
        r"\\?\C:\project\pack.yaml",
        r"\\.\PhysicalDrive0",
    ],
)
def test_aud011_windows_remote_paths_are_rejected_before_filesystem_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    remote_path: str,
) -> None:
    def unexpected_filesystem_call(*args: object, **kwargs: object) -> bool:
        raise AssertionError("filesystem inspection ran before lexical path rejection")

    monkeypatch.setattr(Path, "is_symlink", unexpected_filesystem_call)
    with pytest.raises(GovernanceError) as caught:
        read_local_file_bytes(
            remote_path,
            allowed_root=tmp_path,
            code_prefix="PACK",
            noun="Pack",
        )
    assert _codes(caught.value) == {"PACK_REMOTE_SOURCE_REJECTED"}


@pytest.mark.parametrize(
    ("fixture", "kind"),
    [
        ("valid_profile_v1.yaml", "profile"),
        ("valid_module_v1.yaml", "module"),
    ],
)
def test_aud018_reserved_namespace_root_is_rejected(
    tmp_path: Path,
    fixture: str,
    kind: str,
) -> None:
    payload = _payload(fixture)
    payload["id"] = "nornyx.builtin"
    path = tmp_path / f"{kind}.yaml"
    _write_pack(path, payload)

    with pytest.raises(GovernanceError) as caught:
        load_local_pack(path, allowed_root=tmp_path, source_tier="project")
    assert _codes(caught.value) == {"PACK_RESERVED_NAMESPACE"}


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
