from __future__ import annotations

from pathlib import Path
import json
import yaml

from nornyx.dev_quality import audit_pmo_status, status_summary
from nornyx.goal_templates import make_goal_packet, slugify, render_handoff


def test_slugify_goal_title() -> None:
    assert slugify("Development Acceleration Tooling!") == "development-acceleration-tooling"


def test_make_goal_packet_paths() -> None:
    packet = make_goal_packet("GOAL-016", "Development acceleration tooling", Path("/repo"))
    assert packet.goal_path.as_posix().endswith("docs/goals/goal-016-development-acceleration-tooling.md")
    assert packet.evidence_path.as_posix().endswith("docs/qa/evidence/GOAL-016/README.md")
    assert "GOAL-016" in packet.content


def test_pmo_audit_flags_completed_with_pending() -> None:
    data = {
        "blocks": [
            {
                "id": "goal_999",
                "title": "GOAL-999 — Bad status",
                "status": "completed",
                "completion_pct": 100,
                "completed": ["x"],
                "pending": ["y"],
            }
        ]
    }
    issues = audit_pmo_status(data)
    assert any(issue.severity == "error" for issue in issues)


def test_pmo_audit_accepts_partial_goal() -> None:
    data = {
        "blocks": [
            {
                "id": "goal_016",
                "title": "GOAL-016 — Safe Development Acceleration Tooling",
                "status": "partial",
                "completion_pct": 60,
                "completed": ["x"],
                "pending": ["y"],
            }
        ]
    }
    issues = audit_pmo_status(data)
    assert not any(issue.severity == "error" for issue in issues)


def test_status_summary_counts() -> None:
    data = {
        "blocks": [
            {"status": "completed"},
            {"status": "partial"},
            {"status": "locked"},
        ]
    }
    assert status_summary(data) == "blocks=3 completed=1 partial=1 locked=1"


def test_render_handoff() -> None:
    text = render_handoff("Nornyx", "blocks=3", "GOAL-016")
    assert "# Handoff — Nornyx" in text
    assert "GOAL-016" in text


def test_safe_dev_quality_workflow_is_manual_only() -> None:
    path = Path(".github/workflows/nornyx-safe-dev-quality.yml")
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert "workflow_dispatch" in workflow[True]
    assert "push" not in workflow[True]
    assert "pull_request" not in workflow[True]
    assert workflow["permissions"]["contents"] == "read"
    commands = "\n".join(
        step.get("run", "")
        for step in workflow["jobs"]["local-quality"]["steps"]
        if isinstance(step, dict)
    )
    assert "pytest" in commands
    assert "audit_pmo_status.py" in commands
    assert "--dry-run" in commands


def test_vscode_tasks_are_local_safe_commands() -> None:
    path = Path(".vscode/tasks.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    tasks = data["tasks"]

    assert {task["label"] for task in tasks} >= {
        "Nornyx: quality fast",
        "Nornyx: audit PMO status",
        "Nornyx: check mission example",
        "Nornyx: scaffold goal dry-run",
    }
    for task in tasks:
        assert task["type"] == "shell"
        assert task["command"] == "python"
        joined = " ".join(task["args"])
        assert "git push" not in joined
        assert "deploy" not in joined
        assert "secrets" not in joined
