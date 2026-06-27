from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "docs" / "pmo" / "status" / "current_status.json"


def load_status() -> dict:
    return json.loads(STATUS_PATH.read_text(encoding="utf-8"))


def test_recent_next_goal_labels_are_concrete() -> None:
    data = load_status()
    by_id = {block["id"]: block for block in data["blocks"]}

    assert by_id["goal_056_pmo_summary_noise_reduction"]["next_goal"] == (
        "GOAL-057 \u2014 Manifest Validation Baseline Refresh"
    )
    assert by_id["goal_058_readme_v101_hygiene_index_refresh"]["next_goal"] == (
        "GOAL-059 \u2014 PMO Next-Goal Label Refinement"
    )
    assert by_id["goal_059_pmo_next_goal_label_refinement"]["next_goal"] == (
        "GOAL-060 \u2014 README PMO Label Guidance Link Refresh"
    )
    assert by_id["goal_060_readme_pmo_label_guidance_link_refresh"]["next_goal"] == (
        "GOAL-061 \u2014 Status Date Rollover Refresh"
    )
    assert by_id["goal_061_status_date_rollover_refresh"]["next_goal"] == (
        "GOAL-062 \u2014 Define Next Strategic Track After v1.0.1 Hygiene"
    )
    assert by_id["goal_062_define_next_strategic_track_after_v101_hygiene"]["next_goal"] == (
        "GOAL-063 \u2014 Nornyx Graph Demo Expansion Plan"
    )


def test_recent_next_goal_labels_do_not_use_generic_followup_text() -> None:
    data = load_status()
    recent_blocks = [
        block
        for block in data["blocks"]
        if block["id"]
        in {
            "goal_056_pmo_summary_noise_reduction",
            "goal_057_manifest_validation_baseline_refresh",
            "goal_058_readme_v101_hygiene_index_refresh",
            "goal_059_pmo_next_goal_label_refinement",
            "goal_060_readme_pmo_label_guidance_link_refresh",
            "goal_061_status_date_rollover_refresh",
            "goal_062_define_next_strategic_track_after_v101_hygiene",
            "goal_063_nornyx_graph_demo_expansion",
        }
    ]

    offenders = [
        block["id"]
        for block in recent_blocks[:-1]
        if "Next v1.0.1 hygiene follow-up" in block.get("next_goal", "")
    ]
    assert offenders == []
