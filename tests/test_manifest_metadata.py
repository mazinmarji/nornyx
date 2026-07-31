from __future__ import annotations

import json
import re
from pathlib import Path

from nornyx import __version__


def load_manifest() -> dict:
    return json.loads(Path("manifest.json").read_text(encoding="utf-8"))


def load_validation() -> dict:
    return load_manifest()["current_validation"]


def test_manifest_current_validation_is_fresh() -> None:
    manifest = load_manifest()
    validation = manifest["current_validation"]

    assert manifest["version"] == __version__ == "1.11.0"
    assert manifest["language_version"] == "1.0.0"
    assert manifest["updated_for"] == f"{__version__}-release-candidate"
    assert validation["goal"] == f"{__version__}-release-candidate"
    assert validation["date"] == "2026-08-01"
    assert validation["test_command"] == "python -m pytest -q"
    assert validation["package_publication"] == "1.10.0"
    assert validation["release_check"]["blocked"] == 0
    assert validation["release_check"]["warning"] == 1
    assert validation["stable_language_check"]["blocked"] == 0
    assert validation["stable_language_check"]["warning"] == 1

    test_result = validation["test_result"]
    for marker in (
        "Authorizer.state",
        "AuthorizerState",
        "SPI 1.2",
        "runtime-events schema 1.1",
        "focused release-consistency checks",
        "core build",
        "installed-wheel verification",
    ):
        assert marker in test_result

    current_validation = json.dumps(validation, sort_keys=True)
    assert "1.7.0-release" not in current_validation
    assert "1.7.0-agentic-network-release" not in current_validation
    assert validation["package_publication"] != "1.7.0"
    assert "Pending final" not in current_validation


def test_manifest_records_canonical_test_environment() -> None:
    # The recorded counts are only meaningful against a named environment:
    # the pass/skip split moves when optional framework extras are present.
    environment = load_validation()["test_environment"]

    assert re.fullmatch(r"3\.\d+\.\d+", environment["python"])
    assert environment["install"] == "pip install -e .[dev]"
    assert environment["optional_framework_extras"] is False
    assert environment["platform"] == "windows-short-path"


def test_manifest_test_summary_is_internally_coherent() -> None:
    summary = load_validation()["test_summary"]

    for key in (
        "collected_items",
        "module_level_import_skips",
        "passed",
        "skipped",
        "total_outcomes",
    ):
        value = summary[key]
        # bool is an int subclass; an exact-type check keeps True out of counts.
        assert type(value) is int
        assert value >= 0

    assert summary["passed"] + summary["skipped"] == summary["total_outcomes"]
    # Modules skipped by a module-level importorskip never become collected
    # items, but pytest still reports each one as a skipped outcome.
    assert (
        summary["collected_items"] + summary["module_level_import_skips"]
        == summary["total_outcomes"]
    )


def test_manifest_test_result_prose_matches_structured_summary() -> None:
    # The structured block is the source of truth; the prose must not drift
    # away from it.
    validation = load_validation()
    summary = validation["test_summary"]
    environment = validation["test_environment"]
    test_result = validation["test_result"]

    assert f"{summary['passed']} passed" in test_result
    assert f"{summary['skipped']} skipped" in test_result
    assert f"{summary['total_outcomes']} total outcomes" in test_result
    assert environment["python"] in test_result
    assert "no optional framework extras" in test_result


def test_manifest_has_no_build_provenance() -> None:
    # The manifest carries only current metadata; internal build-provenance
    # blocks must not be present.
    manifest = load_manifest()
    for key in ("historical_zip_verification", "verification", "final_recheck"):
        assert key not in manifest
