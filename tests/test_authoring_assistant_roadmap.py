from __future__ import annotations

from pathlib import Path

import yaml

from nornyx.authoring_assistant import (
    authoring_summary,
    should_start_with_cli_wizard,
    validate_authoring_roadmap,
)


ROOT = Path(__file__).resolve().parents[1]


def valid_roadmap() -> dict:
    return {
        "schema_version": "1.0",
        "status": "roadmap",
        "name": "Nornyx Authoring Assistant Roadmap",
        "purpose": "Make .nyx easy to create.",
        "capabilities": [
            {"id": "cli_wizard", "status": "roadmap", "description": "Guided CLI .nyx authoring.", "priority": "high", "safe_now": True},
            {"id": "llm_authoring_pack", "status": "roadmap", "description": "Mini-spec and examples for LLM drafting.", "priority": "high", "safe_now": True},
            {"id": "formatted_preview", "status": "roadmap", "description": "Readable preview for human approval.", "priority": "high", "safe_now": True},
            {"id": "repair_loop", "status": "roadmap", "description": "Use checker errors to repair drafts.", "priority": "high", "safe_now": True},
        ],
        "authority_rules": [
            "LLM may draft .nyx.",
            "Nornyx checker validates .nyx.",
            "Human approves authoritative .nyx.",
            "Unknowns must become open questions.",
        ],
        "promotion_gates": [
            "Checker diagnostics are stable enough.",
            "Human approval remains required.",
            "Capability design exists before live integrations.",
            "Evidence is recorded for drafts and approvals.",
        ],
        "blocked_actions": [
            "live_llm_calls",
            "fine_tuning_pipeline",
            "model_hosting",
            "portal_implementation",
            "automatic_approval",
            "automatic_repo_writes",
            "production_config_writes",
            "external_tool_calls_by_default",
            "checker_bypass",
        ],
        "non_goals": [
            "live LLM integration now",
            "fine-tuning pipeline now",
            "model hosting now",
            "portal implementation now",
            "automatic approval",
            "automatic production writes",
        ],
        "next_focus": ["Keep as roadmap"],
    }


def test_valid_roadmap_has_no_errors() -> None:
    issues = validate_authoring_roadmap(valid_roadmap())
    assert not any(issue.severity == "error" for issue in issues)


def test_duplicate_capability_is_error() -> None:
    data = valid_roadmap()
    data["capabilities"].append(dict(data["capabilities"][0]))
    issues = validate_authoring_roadmap(data)
    assert any("duplicate capability" in issue.message for issue in issues)


def test_real_roadmap_has_no_errors() -> None:
    path = ROOT / "docs" / "backlog" / "nornyx-authoring-assistant-roadmap.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    issues = validate_authoring_roadmap(data)
    assert not [issue.message for issue in issues if issue.severity == "error"]


def test_authority_rules_warn_if_missing_human() -> None:
    data = valid_roadmap()
    data["authority_rules"] = ["LLM may draft.", "Checker validates."]
    issues = validate_authoring_roadmap(data)
    assert any(issue.severity == "warning" and "human" in issue.message for issue in issues)


def test_roadmap_blocks_premature_promotion() -> None:
    data = valid_roadmap()
    data["status"] = "stable"
    data["capabilities"][0]["status"] = "candidate"
    issues = validate_authoring_roadmap(data)
    messages = [issue.message for issue in issues if issue.severity == "error"]

    assert any("status=roadmap" in message for message in messages)
    assert any("separately promoted" in message for message in messages)


def test_roadmap_requires_explicit_blocked_actions() -> None:
    data = valid_roadmap()
    data["blocked_actions"].remove("checker_bypass")
    issues = validate_authoring_roadmap(data)
    assert any("blocked_actions missing" in issue.message for issue in issues)


def test_unsafe_future_capabilities_cannot_be_safe_now() -> None:
    data = valid_roadmap()
    data["capabilities"].append(
        {
            "id": "specialized_small_model",
            "status": "research",
            "description": "Optional future model.",
            "priority": "medium",
            "safe_now": True,
        }
    )
    issues = validate_authoring_roadmap(data)
    assert any("specialized_small_model cannot be safe_now" in issue.message for issue in issues)


def test_should_start_with_cli_wizard() -> None:
    assert should_start_with_cli_wizard(valid_roadmap()) is True


def test_authoring_summary() -> None:
    summary = authoring_summary(valid_roadmap())
    assert "capabilities=4" in summary
    assert "safe_now=4" in summary
