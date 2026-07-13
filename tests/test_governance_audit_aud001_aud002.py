from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from nornyx.cli import main
from nornyx.governance import GovernanceError
from nornyx.governance.loader import load_local_pack
from nornyx.governance.locks import lock_for_packs, verify_lock
from nornyx.governance.registry import GovernanceRegistry
from nornyx.governance.schemas import canonical_pack_hash


FIXTURES = Path(__file__).parent / "fixtures" / "governance_extension"


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


def _colliding_packs(tmp_path: Path):
    profile_payload = _payload("valid_profile_v1.yaml")
    module_payload = _payload("valid_module_v1.yaml")
    module_payload["id"] = profile_payload["id"]
    module_payload["name"] = profile_payload["name"]
    profile_path = tmp_path / "profile.yaml"
    module_path = tmp_path / "module.yaml"
    _write_pack(profile_path, profile_payload)
    _write_pack(module_path, module_payload)
    return (
        load_local_pack(profile_path, allowed_root=tmp_path, source_tier="project"),
        load_local_pack(module_path, allowed_root=tmp_path, source_tier="org"),
    )


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
