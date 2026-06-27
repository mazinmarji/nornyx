from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "docs" / "pmo" / "status" / "current_status.json"


def load_status() -> dict:
    return json.loads(STATUS_PATH.read_text(encoding="utf-8"))


def test_pmo_status_date_matches_goal_061_rollover() -> None:
    data = load_status()

    assert data["updated_at"] == "2026-06-04"
    assert (
        data["summary"]["pmo_readability"]["latest_completed_goal"]
        == "GOAL-063 Nornyx Graph Demo Expansion"
    )

