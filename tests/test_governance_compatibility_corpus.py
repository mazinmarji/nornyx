from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
from typing import Any

from nornyx import __version__
from nornyx.cli import main
from nornyx.governance import (
    GovernanceRegistry,
    compose_governance,
    lock_for_packs,
    project_profile_to_v03,
)
from nornyx.profiles import PROFILE_NAMES


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "governance_compatibility" / "manifest.json"


def _manifest() -> dict[str, Any]:
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_lf(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sanitize(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(ROOT.as_posix(), "<ROOT>")
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items()}
    return value


def test_compatibility_corpus_declares_every_required_class() -> None:
    manifest = _manifest()

    assert manifest["schema"] == "nornyx.governance_compatibility_corpus.v1"
    assert manifest["baseline"]["package_version"] == __version__ == "1.5.2"
    assert set(manifest["classes"]) == {
        "byte_identical",
        "canonical_lf_identical",
        "semantically_equivalent",
        "intentional_migration_requiring_approval",
    }
    assert {
        "profile_starters",
        "nyx_examples",
        "governed_package_examples",
        "generated_artifacts_and_manifests",
        "legacy_profile_api",
        "locks",
        "cli",
        "intentional_migrations",
    } <= set(manifest)


def test_compatibility_corpus_pins_all_example_and_generated_bytes() -> None:
    manifest = _manifest()
    categories = (
        "nyx_examples",
        "governed_package_examples",
        "generated_artifacts_and_manifests",
    )
    for category in categories:
        for entry in manifest[category]["files"]:
            raw = (ROOT / entry["path"]).read_bytes()
            if manifest[category]["classification"] == "canonical_lf_identical":
                raw = _canonical_lf(raw)
            assert _sha256(raw) == entry["sha256"]

    recorded_examples = {
        item["path"] for item in manifest["nyx_examples"]["files"]
    }
    recorded_packages = {
        item["path"] for item in manifest["governed_package_examples"]["files"]
    }
    assert recorded_examples == {
        path.relative_to(ROOT).as_posix() for path in (ROOT / "examples").glob("*.nyx")
    }
    assert recorded_packages == {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "examples" / "governed_package").glob("*.nyx")
    }


def test_compatibility_corpus_delegates_all_starters_to_the_existing_goldens() -> None:
    manifest = _manifest()
    starter_manifest = json.loads(
        (ROOT / manifest["profile_starters"]["manifest"]).read_text(encoding="utf-8")
    )

    assert starter_manifest["profile_order"] == PROFILE_NAMES
    assert len(starter_manifest["profiles"]) == len(PROFILE_NAMES)
    assert manifest["profile_starters"]["legacy_profiles_unchanged"] == 11
    assert manifest["profile_starters"]["additive_profiles"] == [
        "architecture_governance"
    ]


def test_compatibility_corpus_pins_legacy_projection_and_lock_shapes() -> None:
    manifest = _manifest()
    registry = GovernanceRegistry.builtins()
    projection = project_profile_to_v03(registry.resolve_profile("ai_coding"))
    assert _sha256(_canonical_json(projection.legacy_dict())) == (
        manifest["legacy_profile_api"]["ai_coding_projection_sha256"]
    )
    assert _sha256(_canonical_json(projection.report.to_dict())) == (
        manifest["legacy_profile_api"]["ai_coding_projection_report_sha256"]
    )

    composition = compose_governance(registry, profile_identity="minimal")
    lock = lock_for_packs([*composition.modules, composition.profile])
    canonical_lock = _canonical_json(lock.to_dict()) + b"\n"
    assert _sha256(canonical_lock) == manifest["locks"]["minimal_profile_lock_sha256"]


def test_compatibility_corpus_pins_cli_stdout_and_exit_codes() -> None:
    for case in _manifest()["cli"]["cases"]:
        output = StringIO()
        with redirect_stdout(output):
            exit_code = main(case["argv"])
        payload = json.loads(output.getvalue())
        observed = _sha256(_canonical_json(_sanitize(payload)))
        assert exit_code == case["exit"], case["id"]
        assert observed == case["sha256"], case["id"]


def test_every_intentional_migration_has_the_required_approval_record() -> None:
    for migration in _manifest()["intentional_migrations"]:
        assert migration["classification"] == "intentional_migration_requiring_approval"
        assert "old_hash" in migration and migration["new_hash"]
        assert migration["reason"]
        assert migration["approval"]
        assert migration["changelog"]
        if migration["surface"] == "architecture_governance starter":
            starter = (
                ROOT
                / "tests"
                / "fixtures"
                / "governance_extension"
                / "starter_golden"
                / "architecture_governance.nyx"
            )
            assert migration["new_hash"] == "sha256:" + _sha256(starter.read_bytes())
