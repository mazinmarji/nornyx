from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "docs" / "pmo" / "status" / "current_status.json"


def load_status() -> dict:
    return json.loads(STATUS_PATH.read_text(encoding="utf-8"))


def test_pmo_status_current_fields_match_latest_rollover() -> None:
    # Rollover pins follow the docs/60 procedure: the current date and the
    # numbered-goal ledger tail move together with the status file.
    data = load_status()

    assert data["updated_at"] == "2026-08-14"
    assert (
        data["summary"]["pmo_readability"]["latest_completed_goal"]
        == "GOAL-063 Nornyx Graph Demo Expansion"
    )

