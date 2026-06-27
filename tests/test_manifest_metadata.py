from __future__ import annotations

import json
from pathlib import Path


def load_manifest() -> dict:
    return json.loads(Path("manifest.json").read_text(encoding="utf-8"))


def test_manifest_current_validation_is_fresh() -> None:
    manifest = load_manifest()
    validation = manifest["current_validation"]

    assert manifest["updated_for"] == "GOAL-063-nornyx-graph-demo-expansion"
    assert validation["goal"] == "GOAL-063"
    assert validation["date"] == "2026-06-04"
    assert validation["test_result"] == "253 passed"
    assert validation["release_check"]["blocked"] == 0
    assert validation["stable_language_check"]["blocked"] == 0
    assert validation["pmo_audit"] == "blocks=56 completed=55 partial=0 locked=1"


def test_manifest_has_no_zip_provenance() -> None:
    # ZIP build-provenance (uploaded ZIPs / /mnt/data) was removed for public release.
    manifest = load_manifest()
    assert "historical_zip_verification" not in manifest
    raw = Path("manifest.json").read_text(encoding="utf-8")
    assert "/mnt/data" not in raw
    assert "uploaded" not in raw.lower()
