from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "docs" / "pmo" / "status" / "current_status.json"


def load_status() -> dict:
    return json.loads(STATUS_PATH.read_text(encoding="utf-8"))


def test_pmo_summary_stays_concise_and_current() -> None:
    data = load_status()
    summary = data["summary"]

    assert summary["overall_status"] == "graph_demo_expansion_completed"
    assert "GOAL-064" in summary["next_recommended_goal"]
    assert "Adoption Readiness Friction Audit" in summary["next_recommended_goal"]
    assert "model level medium" in summary["next_recommended_goal"].lower()
    assert len(summary["roadmap_note"]) <= 220
    assert "GOAL-049" not in summary["roadmap_note"]
    assert "GOAL-055" not in summary["roadmap_note"]


def test_pmo_readability_guidance_preserves_history_boundary() -> None:
    data = load_status()
    readability = data["summary"]["pmo_readability"]

    assert readability["latest_completed_goal"] == "GOAL-063 Nornyx Graph Demo Expansion"
    assert "Preserve completed goal blocks" in readability["history_policy"]
    assert "goal ledger" in readability["portal_guidance"].lower()
    assert any(block["id"] == "goal_055_manifest_metadata_freshness_cleanup" for block in data["blocks"])
    assert any(block["id"] == "goal_056_pmo_summary_noise_reduction" for block in data["blocks"])
    assert any(block["id"] == "goal_057_manifest_validation_baseline_refresh" for block in data["blocks"])
    assert any(block["id"] == "goal_058_readme_v101_hygiene_index_refresh" for block in data["blocks"])
    assert any(block["id"] == "goal_059_pmo_next_goal_label_refinement" for block in data["blocks"])
    assert any(block["id"] == "goal_060_readme_pmo_label_guidance_link_refresh" for block in data["blocks"])
    assert any(block["id"] == "goal_061_status_date_rollover_refresh" for block in data["blocks"])
    assert any(block["id"] == "goal_062_define_next_strategic_track_after_v101_hygiene" for block in data["blocks"])
    assert any(block["id"] == "goal_063_nornyx_graph_demo_expansion" for block in data["blocks"])


def test_goal_100_remains_locked_after_summary_cleanup() -> None:
    data = load_status()
    goal_100 = next(block for block in data["blocks"] if block["id"] == "goal_100_future_regulated_extensions")

    assert goal_100["status"] == "locked"
    assert goal_100["completion_pct"] == 0
