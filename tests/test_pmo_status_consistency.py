from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "docs" / "pmo" / "status" / "current_status.json"


def load_status() -> dict:
    return json.loads(STATUS_PATH.read_text(encoding="utf-8"))


def test_completed_blocks_have_no_pending_items_and_are_100_percent() -> None:
    data = load_status()
    offenders = []
    for block in data.get("blocks", []):
        if block.get("status") == "completed":
            if block.get("pending") or block.get("completion_pct") != 100:
                offenders.append((block.get("id"), block.get("title"), block.get("completion_pct"), block.get("pending")))
    assert offenders == []


def test_no_block_with_pending_items_claims_100_percent() -> None:
    data = load_status()
    offenders = []
    for block in data.get("blocks", []):
        if block.get("pending") and block.get("completion_pct") == 100:
            offenders.append((block.get("id"), block.get("title")))
    assert offenders == []


def test_not_started_blocks_have_no_completed_work_or_positive_progress() -> None:
    data = load_status()
    offenders = []
    for block in data.get("blocks", []):
        if block.get("status") == "not_started":
            if block.get("completed") or block.get("completion_pct", 0) > 0:
                offenders.append((block.get("id"), block.get("title"), block.get("completion_pct"), block.get("completed")))
    assert offenders == []


def test_goal_blocks_have_goal_prefix_in_title() -> None:
    data = load_status()
    offenders = []
    for block in data.get("blocks", []):
        title = block.get("title", "")
        block_id = block.get("id", "")
        if block_id.startswith("goal_") and not title.startswith("GOAL-"):
            offenders.append((block_id, title))
    assert offenders == []


def test_goal_014_is_completed_after_dx_loop_is_stable() -> None:
    data = load_status()
    goal_014 = next(block for block in data.get("blocks", []) if block.get("id") == "goal_014_distinct_language_dx")
    assert goal_014["title"].startswith("GOAL-014")
    assert goal_014["status"] == "completed"
    assert goal_014["completion_pct"] == 100
    assert goal_014["pending"] == []


def test_locked_goals_are_not_completed() -> None:
    data = load_status()
    offenders = []
    for block in data.get("blocks", []):
        if block.get("status") == "locked" and block.get("completion_pct") == 100:
            offenders.append((block.get("id"), block.get("title")))
    assert offenders == []
