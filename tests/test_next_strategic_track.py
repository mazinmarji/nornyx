from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "docs" / "pmo" / "status" / "current_status.json"


def load_status() -> dict:
    return json.loads(STATUS_PATH.read_text(encoding="utf-8"))


def test_v101_hygiene_loop_is_closed() -> None:
    data = load_status()
    summary = data["summary"]

    assert summary["pmo_readability"]["current_focus"] == "post-v1.0.1 strategic track"
    assert "v1.0.1 hygiene is closed" in summary["roadmap_model"]["v1.0"]
    assert "Next v1.0.1 hygiene follow-up" not in summary["next_recommended_goal"]
    assert "GOAL-064" in summary["next_recommended_goal"]


def test_named_strategic_tracks_are_present() -> None:
    data = load_status()
    tracks = {track["id"]: track for track in data["summary"]["strategic_next_tracks"]}

    assert tracks["graph_demo_expansion"]["first_goal"] == "GOAL-063"
    assert tracks["graph_demo_expansion"]["model_level"] == "high"
    assert tracks["adoption_readiness"]["first_goal"] == "GOAL-064"
    assert tracks["profile_conformance"]["first_goal"] == "GOAL-065"
