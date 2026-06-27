from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
GOALS_FILE = ROOT / "examples" / "nornyx_roadmap_goals.nyx"
OUT = ROOT / "docs" / "pmo" / "status" / "current_status.json"


def load_goals() -> list[dict[str, Any]]:
    data = yaml.safe_load(GOALS_FILE.read_text(encoding="utf-8"))
    return list(data.get("goals", []))


def status_for(goal_id: str, phase: str) -> tuple[str, int]:
    if goal_id == "GOAL-000":
        return "completed", 100
    if goal_id in {"GOAL-001", "GOAL-002", "GOAL-003", "GOAL-005"}:
        return "partial", {"GOAL-001": 70, "GOAL-002": 55, "GOAL-003": 65, "GOAL-005": 35}[goal_id]
    if phase in {"v0.7", "v1.0"}:
        return "locked", 10 if phase == "v0.7" else 5
    return "not_started", 20 if phase == "v0.2" else 15


def block_from_goal(goal: dict[str, Any]) -> dict[str, Any]:
    goal_id = goal["id"]
    status, pct = status_for(goal_id, str(goal.get("phase", "future")))
    return {
        "id": goal_id.lower().replace("-", "_"),
        "title": f"{goal_id} — {goal.get('title', goal_id)}",
        "phase": goal.get("phase", "future"),
        "status": status,
        "completion_pct": pct,
        "completed": ["Defined in Nornyx roadmap goal ledger."],
        "pending": [goal.get("goal", "Complete goal work.")],
        "risks": goal.get("stop_rules", []),
        "evidence": [goal.get("evidence", f"docs/qa/evidence/{goal_id}/")],
        "related_prs": [],
        "next_goal": "Advance according to docs/19_NORNYX_DEVELOPMENT_GOAL_LEDGER.md",
    }


def main() -> int:
    goals = load_goals()
    payload = {
        "schema_version": "1.0",
        "project": "Nornyx",
        "report_id": f"NORNYX-PMO-STATUS-{date.today().isoformat()}",
        "source_of_truth": {
            "repository": "nornyx",
            "branch": "local-dev",
            "last_review_commit": "local",
            "update_workflow": "Generated from examples/nornyx_roadmap_goals.nyx via scripts/pmo/generate_nornyx_pmo_status.py",
        },
        "summary": {
            "overall_status": "goal_led_development",
            "next_recommended_goal": "GOAL-001: Core block spec freeze",
            "current_operating_model": "Every phase is handled as a governed goal.",
        },
        "legend": {
            "completed": "Implemented or sufficiently scaffolded.",
            "partial": "Partly implemented or documented.",
            "not_started": "Future target architecture only.",
            "locked": "Requires approval or prerequisite gates.",
            "blocked": "Cannot proceed without human decision or prerequisite.",
        },
        "blocks": [block_from_goal(goal) for goal in goals],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
