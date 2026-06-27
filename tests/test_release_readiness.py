from __future__ import annotations

import json
from pathlib import Path

from nornyx.cli import main
from nornyx.release_readiness import (
    build_release_candidate_stabilization_report,
    build_release_readiness_report,
    build_stable_language_report,
)


def test_release_readiness_reports_candidate_pending_approval() -> None:
    report = build_release_readiness_report(Path("."), target_version="1.0.0")

    assert report["schema"] == "nornyx.release_readiness.v0.1"
    assert report["status"] == "release_candidate_ready_pending_approval"
    assert report["summary"]["blocked"] == 0
    assert report["summary"]["requires_human_approval"] == 1
    assert report["safety"]["published"] is False
    assert report["safety"]["pushed_to_remote"] is False
    assert report["safety"]["package_version_changed"] is False


def test_release_readiness_detects_approval_as_ready_for_release() -> None:
    report = build_release_readiness_report(Path("."), target_version="1.0.0", approved=True)

    assert report["status"] == "ready_for_release"
    assert report["summary"]["requires_human_approval"] == 0


def test_release_readiness_blocks_missing_docs(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")
    package = tmp_path / "nornyx"
    package.mkdir()
    (package / "__init__.py").write_text('__version__ = "0.1.0"\n', encoding="utf-8")

    report = build_release_readiness_report(tmp_path)

    assert report["status"] == "blocked"
    assert any(check["id"] == "release_docs_present" and check["status"] == "blocked" for check in report["checks"])


def test_release_check_cli_writes_report(tmp_path: Path, capsys) -> None:
    out_path = tmp_path / "release_readiness.json"

    assert main(["release-check", "--out", str(out_path)]) == 0

    output = capsys.readouterr().out
    report = json.loads(out_path.read_text(encoding="utf-8"))

    assert "Release readiness report written" in output
    assert report["schema"] == "nornyx.release_readiness.v0.1"
    assert report["status"] == "release_candidate_ready_pending_approval"


def test_release_candidate_stabilization_reports_pending_approval() -> None:
    report = build_release_candidate_stabilization_report(Path("."), target_version="1.0.0")

    assert report["schema"] == "nornyx.release_candidate_stabilization.v0.9"
    assert report["status"] == "release_candidate_stabilized_pending_approval"
    assert report["summary"]["blocked"] == 0
    assert report["summary"]["requires_human_approval"] >= 1
    assert report["safety"]["published"] is False
    assert report["safety"]["tag_created"] is False
    assert report["safety"]["pushed_to_remote"] is False
    assert report["safety"]["package_version_changed"] is False
    assert report["safety"]["release_claim_made"] is False
    assert isinstance(report["safety"]["goal_042_completed_local"], bool)
    assert report["safety"]["goal_100_unlocked"] is False
    assert any(
        check["id"] == "strategic_maturity_goals_completed" and check["status"] == "passed"
        for check in report["checks"]
    )
    assert any(
        check["id"] == "strategic_maturity_evidence_present" and check["status"] == "passed"
        for check in report["checks"]
    )
    assert any(check["id"] == "release_boundary_preserved" and check["status"] == "passed" for check in report["checks"])


def test_release_candidate_stabilization_detects_approval() -> None:
    report = build_release_candidate_stabilization_report(Path("."), target_version="1.0.0", approved=True)

    assert report["status"] == "release_candidate_stabilized_approved"
    assert report["summary"]["requires_human_approval"] == 0


def test_release_candidate_stabilization_schema_is_no_publish() -> None:
    schema = json.loads(Path("schemas/release_candidate_stabilization.schema.json").read_text(encoding="utf-8"))
    safety = schema["properties"]["safety"]["properties"]

    assert safety["published"]["const"] is False
    assert safety["tag_created"]["const"] is False
    assert safety["pushed_to_remote"]["const"] is False
    assert safety["package_version_changed"]["const"] is False
    assert safety["release_claim_made"]["const"] is False


def test_stable_language_reports_local_completion_pending_release_approval() -> None:
    report = build_stable_language_report(Path("."), target_version="1.0.0")

    assert report["schema"] == "nornyx.stable_language.v1.0"
    assert report["status"] == "stable_language_completed_local_pending_release_approval"
    assert report["summary"]["blocked"] == 0
    assert report["summary"]["requires_human_approval"] >= 1
    assert "Graph" in report["stable_core_concepts"]
    assert "full autonomous runtime" in report["stable_v1_non_goals"]
    assert report["safety"]["published"] is False
    assert report["safety"]["tag_created"] is False
    assert report["safety"]["pushed_to_remote"] is False
    assert report["safety"]["package_version_changed"] is False
    assert report["safety"]["production_deployment"] is False
    assert report["safety"]["general_purpose_language_claim"] is False
    assert report["safety"]["full_autonomous_runtime_claim"] is False
    assert report["safety"]["unrestricted_connector_runtime_claim"] is False
    assert report["safety"]["goal_042_completed_local"] is True
    assert report["safety"]["goal_100_unlocked"] is False
    assert any(check["id"] == "v1_stable_goals_completed" and check["status"] == "passed" for check in report["checks"])
    assert any(check["id"] == "goal_100_remains_locked" and check["status"] == "passed" for check in report["checks"])


def test_stable_language_detects_approval_as_local_approved() -> None:
    report = build_stable_language_report(Path("."), target_version="1.0.0", approved=True)

    assert report["status"] == "stable_language_approved_local"
    assert report["summary"]["requires_human_approval"] == 0


def test_stable_language_check_cli_writes_report(tmp_path: Path, capsys) -> None:
    out_path = tmp_path / "stable_language.json"

    assert main(["stable-language-check", "--out", str(out_path)]) == 0

    output = capsys.readouterr().out
    report = json.loads(out_path.read_text(encoding="utf-8"))

    assert "Stable language report written" in output
    assert report["schema"] == "nornyx.stable_language.v1.0"
    assert report["status"] == "stable_language_completed_local_pending_release_approval"


def test_stable_language_schema_is_no_publish() -> None:
    schema = json.loads(Path("schemas/stable_language_report.schema.json").read_text(encoding="utf-8"))
    safety = schema["properties"]["safety"]["properties"]

    assert safety["published"]["const"] is False
    assert safety["tag_created"]["const"] is False
    assert safety["pushed_to_remote"]["const"] is False
    assert safety["package_version_changed"]["const"] is False
    assert safety["production_deployment"]["const"] is False
    assert safety["general_purpose_language_claim"]["const"] is False
    assert safety["full_autonomous_runtime_claim"]["const"] is False
    assert safety["unrestricted_connector_runtime_claim"]["const"] is False
    assert safety["goal_100_unlocked"]["const"] is False
