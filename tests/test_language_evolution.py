from __future__ import annotations

import json
from pathlib import Path

from nornyx.cli import main
from nornyx.language_evolution import (
    build_language_evolution_report,
    validate_language_evolution_report,
)


def test_language_evolution_report_is_research_only() -> None:
    report = build_language_evolution_report(Path("."))

    assert report["schema"] == "nornyx.language_evolution_research.v0.1"
    assert report["status"] == "research_only_pending_approval"
    assert report["summary"]["blocking_issues"] == 0
    assert report["summary"]["track_count"] == 4
    assert report["summary"]["missing_references"] == 0
    assert report["current_surface"]["syntax"] == "yaml-compatible"
    assert report["safety"]["parser_changed"] is False
    assert report["safety"]["checker_semantics_changed"] is False
    assert report["safety"]["runtime_execution_added"] is False
    assert report["safety"]["native_backend_implemented"] is False
    assert report["safety"]["requires_human_approval_for_promotion"] is True


def test_language_evolution_report_contains_required_tracks() -> None:
    report = build_language_evolution_report(Path("."))
    track_ids = {track["id"] for track in report["tracks"]}

    assert {
        "semantic_core",
        "type_effect_system",
        "workflow_constructs",
        "native_backends",
    } <= track_ids
    assert all(track["status"] == "research" for track in report["tracks"])
    assert all(track["promotion_gate"] for track in report["tracks"])


def test_language_evolution_validation_blocks_premature_promotion() -> None:
    report = build_language_evolution_report(Path("."))
    report["tracks"][0] = {**report["tracks"][0], "status": "approved"}
    report["safety"] = {**report["safety"], "public_syntax_changed": True}

    issues = validate_language_evolution_report(report)

    assert any("must remain research status" in issue["message"] for issue in issues)
    assert any("public_syntax_changed" in issue["message"] for issue in issues)


def test_language_evolution_cli_writes_report(tmp_path: Path, capsys) -> None:
    out_path = tmp_path / "language_evolution.json"

    assert main(["language-evolution", "--out", str(out_path), "--strict"]) == 0

    output = capsys.readouterr().out
    report = json.loads(out_path.read_text(encoding="utf-8"))

    assert "Language evolution report written" in output
    assert report["status"] == "research_only_pending_approval"
    assert report["summary"]["blocking_issues"] == 0
