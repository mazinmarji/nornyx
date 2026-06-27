from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml


def extract_goals(doc: dict[str, Any]) -> list[dict[str, Any]]:
    goals = doc.get("goals", []) or []
    if not isinstance(goals, list):
        return []
    return [g for g in goals if isinstance(g, dict)]


def write_goal_plan(doc: dict[str, Any], out_dir: str | Path) -> list[Path]:
    """Write a human-readable and machine-readable goal plan.

    Goal plans map Nornyx roadmap phases to implementation packets that Codex,
    Claude Code, Cursor, Copilot, or humans can execute safely.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    goals = extract_goals(doc)
    written: list[Path] = []

    plan = {
        "schema": "nornyx.goal_plan.v0.1",
        "project": (doc.get("project") or {}).get("name", "UnnamedProject")
        if isinstance(doc.get("project"), dict)
        else "UnnamedProject",
        "goals": goals,
    }
    yaml_path = out / "goals.yaml"
    yaml_path.write_text(yaml.safe_dump(plan, sort_keys=False), encoding="utf-8")
    written.append(yaml_path)

    lines = ["# Nornyx Goal Plan\n\n", "Generated from `.nyx` source.\n\n"]
    for goal in goals:
        gid = goal.get("id", "GOAL-UNKNOWN")
        title = goal.get("title", goal.get("goal", "Untitled goal"))
        lines.append(f"## {gid} — {title}\n\n")
        for key in ["phase", "goal", "scope", "non_goals", "validation", "evidence", "approval", "stop_rules"]:
            if key in goal:
                lines.append(f"### {key.replace('_', ' ').title()}\n\n")
                value = goal[key]
                if isinstance(value, list):
                    for item in value:
                        lines.append(f"- {item}\n")
                elif isinstance(value, dict):
                    lines.append("```yaml\n")
                    lines.append(yaml.safe_dump(value, sort_keys=False))
                    lines.append("```\n")
                else:
                    lines.append(f"{value}\n")
                lines.append("\n")
    md_path = out / "GOAL_PLAN.md"
    md_path.write_text("".join(lines), encoding="utf-8")
    written.append(md_path)
    return written
