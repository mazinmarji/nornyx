from __future__ import annotations

import json
from pathlib import Path

from nornyx import __version__


def load_manifest() -> dict:
    return json.loads(Path("manifest.json").read_text(encoding="utf-8"))


def test_manifest_current_validation_is_fresh() -> None:
    manifest = load_manifest()
    validation = manifest["current_validation"]

    assert manifest["version"] == __version__
    assert manifest["language_version"] == "1.0.0"
    assert manifest["updated_for"] == "1.7.0-agentic-network-release"
    assert validation["goal"] == "1.7.0-release"
    assert validation["date"] == "2026-07-20"
    assert "merged" in validation["test_result"]
    assert validation["release_check"]["blocked"] == 0
    assert validation["stable_language_check"]["blocked"] == 0
    assert "AN-006" in validation["pmo_audit"]


def test_manifest_has_no_build_provenance() -> None:
    # The manifest carries only current metadata; internal build-provenance
    # blocks must not be present.
    manifest = load_manifest()
    for key in ("historical_zip_verification", "verification", "final_recheck"):
        assert key not in manifest
