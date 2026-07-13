from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace

import pytest
import yaml

from nornyx.cli import main
from nornyx.governance import GovernanceError
from nornyx.governance.loader import load_local_pack
from nornyx.governance.locks import lock_for_packs, verify_lock, write_lock
from nornyx.governance.models import LockEntry, ProfileLock
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


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        if sys.platform.startswith("linux"):
            pytest.fail(f"real Linux symlink creation failed: {exc}")
        pytest.skip(f"symlink creation is unavailable: {exc}")


@pytest.mark.parametrize("component", [".nornyx", "profiles", "modules"])
@pytest.mark.parametrize(
    "argv_prefix",
    [
        ("check",),
        ("governance", "resolve"),
        ("governance", "explain"),
        ("governance", "matrix"),
    ],
)
def test_aud001_dangling_project_governance_components_fail_all_commands(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    component: str,
    argv_prefix: tuple[str, ...],
) -> None:
    contract = tmp_path / "contract.nyx"
    contract.write_text(
        "nornyx: '0.1'\nproject:\n  name: Audit\n  profile: minimal\n",
        encoding="utf-8",
        newline="\n",
    )
    if component == ".nornyx":
        _symlink_or_skip(tmp_path / ".nornyx", tmp_path / "missing-governance-root")
    else:
        governance_root = tmp_path / ".nornyx"
        governance_root.mkdir()
        _symlink_or_skip(
            governance_root / component,
            tmp_path / f"missing-{component}",
        )

    argv = [*argv_prefix, str(contract)]
    if argv_prefix[0] == "governance":
        argv.extend(["--as-of", "2026-07-14T00:00:00Z", "--json"])
    exit_code = main(argv)
    output = capsys.readouterr().out

    assert exit_code != 0
    assert "PACK_SYMLINK_REJECTED" in output


def _colliding_packs(tmp_path: Path, collision: str = "both"):
    profile_payload = _payload("valid_profile_v1.yaml")
    module_payload = _payload("valid_module_v1.yaml")
    if collision in {"id", "both"}:
        module_payload["id"] = profile_payload["id"]
    if collision in {"name", "both"}:
        module_payload["name"] = profile_payload["name"]
    profile_path = tmp_path / "profile.yaml"
    module_path = tmp_path / "module.yaml"
    _write_pack(profile_path, profile_payload)
    _write_pack(module_path, module_payload)
    profile = load_local_pack(profile_path, allowed_root=tmp_path, source_tier="project")
    module = load_local_pack(module_path, allowed_root=tmp_path, source_tier="org")
    if collision == "cross_field":
        module = replace(module, id=profile.name)  # type: ignore[arg-type]
    return profile, module


@pytest.mark.parametrize("profile_first", [True, False])
def test_aud002_cross_kind_identity_is_globally_unique_and_locks_cannot_collapse(
    tmp_path: Path,
    profile_first: bool,
) -> None:
    profile, module = _colliding_packs(tmp_path)
    registry = GovernanceRegistry()
    first, second = (profile, module) if profile_first else (module, profile)
    if profile_first:
        registry.register_profile(first)  # type: ignore[arg-type]
        with pytest.raises(GovernanceError, match="PACK_DUPLICATE_IDENTITY"):
            registry.register_module(second)  # type: ignore[arg-type]
    else:
        registry.register_module(first)  # type: ignore[arg-type]
        with pytest.raises(GovernanceError, match="PACK_DUPLICATE_IDENTITY"):
            registry.register_profile(second)  # type: ignore[arg-type]


def test_aud002_lock_generation_rejects_cross_kind_duplicate_identity(
    tmp_path: Path,
) -> None:
    profile, module = _colliding_packs(tmp_path)
    with pytest.raises(GovernanceError, match="PACK_LOCK_DUPLICATE_ID"):
        lock_for_packs([module, profile])


def test_aud002_lock_verification_cannot_collapse_selected_packs(
    tmp_path: Path,
) -> None:
    profile, module = _colliding_packs(tmp_path)
    profile_lock = lock_for_packs([profile])
    with pytest.raises(GovernanceError, match="PACK_LOCK_DUPLICATE_ID"):
        verify_lock(profile_lock, [module, profile])


@pytest.mark.parametrize("collision", ["id", "name", "cross_field"])
def test_aud002_cross_kind_collision_diagnostic_is_order_independent(
    tmp_path: Path,
    collision: str,
) -> None:
    profile, module = _colliding_packs(tmp_path, collision)
    observed = []
    for profile_first in (True, False):
        registry = GovernanceRegistry()
        with pytest.raises(GovernanceError) as caught:
            if profile_first:
                registry.register_profile(profile)  # type: ignore[arg-type]
                registry.register_module(module)  # type: ignore[arg-type]
            else:
                registry.register_module(module)  # type: ignore[arg-type]
                registry.register_profile(profile)  # type: ignore[arg-type]
        observed.append([item.to_dict() for item in caught.value.diagnostics])
    assert observed[0] == observed[1]
    assert observed[0][0]["code"] == "PACK_DUPLICATE_IDENTITY"


@pytest.mark.parametrize("reverse", [False, True])
def test_aud002_lock_identity_collision_is_permutation_safe(
    tmp_path: Path,
    reverse: bool,
) -> None:
    profile, module = _colliding_packs(tmp_path, "name")
    selected = [module, profile] if reverse else [profile, module]
    with pytest.raises(GovernanceError) as caught:
        lock_for_packs(selected)
    assert _codes(caught.value) == {"PACK_DUPLICATE_IDENTITY"}


def test_aud002_forged_duplicate_lock_cannot_be_written(tmp_path: Path) -> None:
    registry = GovernanceRegistry.builtins()
    profile = registry.resolve_profile("minimal")
    entry = LockEntry(
        id=profile.id,
        version=profile.version,
        source_tier=profile.provenance.source_tier,
        content_hash=profile.content_hash,
        path_hint=profile.provenance.source_path,
    )
    with pytest.raises(GovernanceError) as caught:
        write_lock(tmp_path / "forged.lock", ProfileLock((entry, entry)))
    assert _codes(caught.value) == {"PACK_LOCK_DUPLICATE_ID"}


def test_aud002_generated_lock_always_verifies() -> None:
    registry = GovernanceRegistry.builtins()
    profile = registry.resolve_profile("minimal")
    modules = registry.dependency_order(profile)
    selected = (*modules, profile)
    verify_lock(lock_for_packs(selected), selected)


@pytest.mark.parametrize("component", [".nornyx", "profiles", "modules"])
@pytest.mark.parametrize("target_kind", ["file", "directory"])
def test_aud001_live_governance_symlink_targets_fail_closed(
    tmp_path: Path,
    component: str,
    target_kind: str,
) -> None:
    target = tmp_path / f"target-{component.strip('.')}-{target_kind}"
    if target_kind == "directory":
        target.mkdir()
    else:
        target.write_text("not a governance directory\n", encoding="utf-8")
    if component == ".nornyx":
        link = tmp_path / component
    else:
        (tmp_path / ".nornyx").mkdir()
        link = tmp_path / ".nornyx" / component
    try:
        link.symlink_to(target, target_is_directory=target_kind == "directory")
    except (NotImplementedError, OSError) as exc:
        if sys.platform.startswith("linux"):
            pytest.fail(f"real Linux symlink creation failed: {exc}")
        pytest.skip(f"symlink creation is unavailable: {exc}")

    with pytest.raises(GovernanceError) as caught:
        registry_for_directory(tmp_path)
    assert _codes(caught.value) == {"PACK_SYMLINK_REJECTED"}


@pytest.mark.parametrize("component", [".nornyx", "profiles", "modules"])
def test_aud001_non_directory_governance_components_fail_closed(
    tmp_path: Path,
    component: str,
) -> None:
    if component == ".nornyx":
        path = tmp_path / component
    else:
        (tmp_path / ".nornyx").mkdir()
        path = tmp_path / ".nornyx" / component
    path.write_text("not a directory\n", encoding="utf-8")

    with pytest.raises(GovernanceError) as caught:
        registry_for_directory(tmp_path)
    assert _codes(caught.value) == {"PACK_PATH_TYPE_INVALID"}


def test_aud001_project_components_are_inspected_before_bundled_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    governance_root = tmp_path / ".nornyx"
    governance_root.mkdir()
    original_lstat = os.lstat

    def simulated_link(path: str | Path) -> os.stat_result:
        if Path(path) == governance_root:
            return os.stat_result((stat.S_IFLNK | 0o777, 0, 0, 1, 0, 0, 0, 0, 0, 0))
        return original_lstat(path)

    def unexpected_bundled_discovery(cls: type[GovernanceRegistry]) -> GovernanceRegistry:
        raise AssertionError("bundled discovery ran before project inspection")

    monkeypatch.setattr(os, "lstat", simulated_link)
    monkeypatch.setattr(
        GovernanceRegistry,
        "builtins",
        classmethod(unexpected_bundled_discovery),
    )
    with pytest.raises(GovernanceError) as caught:
        registry_for_directory(tmp_path)
    assert _codes(caught.value) == {"PACK_SYMLINK_REJECTED"}


def test_aud001_inaccessible_governance_component_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    governance_root = tmp_path / ".nornyx"
    governance_root.mkdir()
    original_lstat = os.lstat

    def inaccessible(path: str | Path) -> os.stat_result:
        if Path(path) == governance_root:
            raise PermissionError("denied")
        return original_lstat(path)

    monkeypatch.setattr(os, "lstat", inaccessible)
    with pytest.raises(GovernanceError) as caught:
        registry_for_directory(tmp_path)
    assert _codes(caught.value) == {"PACK_PATH_INSPECTION_FAILED"}


def test_aud001_pack_directory_enumeration_error_is_normalized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profiles = tmp_path / ".nornyx" / "profiles"
    profiles.mkdir(parents=True)
    original_glob = Path.glob

    def denied_glob(path: Path, pattern: str):
        if path == profiles:
            raise PermissionError("denied")
        return original_glob(path, pattern)

    monkeypatch.setattr(Path, "glob", denied_glob)
    with pytest.raises(GovernanceError) as caught:
        registry_for_directory(tmp_path)
    assert _codes(caught.value) == {"PACK_PATH_INSPECTION_FAILED"}


def test_aud001_windows_reparse_component_is_rejected_without_real_junction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    governance_root = tmp_path / ".nornyx"
    governance_root.mkdir()
    original_lstat = os.lstat

    def simulated_reparse(path: str | Path):
        if Path(path) == governance_root:
            return SimpleNamespace(
                st_mode=stat.S_IFDIR | 0o755,
                st_file_attributes=0x400,
            )
        return original_lstat(path)

    monkeypatch.setattr(os, "lstat", simulated_reparse)
    with pytest.raises(GovernanceError) as caught:
        registry_for_directory(tmp_path)
    assert _codes(caught.value) == {"PACK_SYMLINK_REJECTED"}
