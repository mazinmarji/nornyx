from __future__ import annotations

import json
from pathlib import Path

from nornyx import __version__


def load_manifest() -> dict:
    return json.loads(Path("manifest.json").read_text(encoding="utf-8"))


def test_manifest_current_validation_is_fresh() -> None:
    manifest = load_manifest()
    validation = manifest["current_validation"]

    assert manifest["version"] == __version__ == "1.9.0"
    assert manifest["language_version"] == "1.0.0"
    assert manifest["updated_for"] == f"{__version__}-release-candidate"
    assert validation["goal"] == f"{__version__}-release-candidate"
    assert validation["date"] == "2026-07-30"
    assert validation["test_command"] == "python -m pytest -q"
    assert validation["package_publication"] == "1.8.0"
    assert validation["release_check"]["blocked"] == 0
    assert validation["stable_language_check"]["blocked"] == 0

    test_result = validation["test_result"]
    for marker in (
        "1566 passed",
        "48 skipped",
        "CPython 3.10-3.13",
        "core build",
        "installed-wheel",
        "adapter",
    ):
        assert marker in test_result

    current_validation = json.dumps(validation, sort_keys=True)
    assert "1.7.0-release" not in current_validation
    assert "1.7.0-agentic-network-release" not in current_validation
    assert validation["package_publication"] != "1.7.0"
    assert "Pending final" not in current_validation


def test_manifest_has_no_build_provenance() -> None:
    # The manifest carries only current metadata; internal build-provenance
    # blocks must not be present.
    manifest = load_manifest()
    for key in ("historical_zip_verification", "verification", "final_recheck"):
        assert key not in manifest
