from __future__ import annotations

import json

from nornyx.renderers import normalize_blocks, render_delivery_state, render_json, render_markdown, render_shell


def sample_status() -> dict:
    return {
        "project": "Nornyx",
        "summary": {
            "overall_status": "baseline_partial",
            "next_recommended_goal": "GOAL-001",
        },
        "blocks": [
            {
                "id": "goal_014",
                "title": "GOAL-014 — Distinct Language Developer Experience",
                "status": "partial",
                "completion_pct": 75,
                "completed": ["CLI", "docs"],
                "pending": ["LSP"],
                "evidence": ["docs/23.md"],
                "next_goal": "GOAL-014A",
            }
        ],
    }


def test_normalize_blocks() -> None:
    blocks = normalize_blocks(sample_status())
    assert len(blocks) == 1
    assert blocks[0].title.startswith("GOAL-014")
    assert blocks[0].completed_count == 2
    assert blocks[0].pending_count == 1


def test_render_shell_contains_goal_state() -> None:
    text = render_shell(sample_status())
    assert "Nornyx — baseline_partial" in text
    assert "GOAL-014" in text
    assert "completion: 75%" in text


def test_render_markdown_table() -> None:
    text = render_markdown(sample_status())
    assert "# Nornyx Delivery State" in text
    assert "| Block | Status | Completion" in text
    assert "GOAL-014" in text


def test_render_json_normalized() -> None:
    text = render_json(sample_status())
    data = json.loads(text)
    assert data["project"] == "Nornyx"
    assert data["blocks"][0]["evidence_count"] == 1


def test_render_delivery_state_rejects_unknown_format() -> None:
    try:
        render_delivery_state(sample_status(), "portal")
    except ValueError as exc:
        assert "Unsupported" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
