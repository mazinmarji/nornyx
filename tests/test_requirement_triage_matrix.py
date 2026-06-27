from __future__ import annotations

import json
from pathlib import Path

import yaml

from nornyx.requirement_triage import (
    EXPECTED_CATEGORY_ACTIONS,
    REQUIRED_CATEGORIES,
    classify_concept,
    should_create_diff_for_category,
    triage_summary,
    validate_triage_matrix,
)


def valid_matrix() -> dict:
    return {
        "schema_version": "1.0",
        "status": "proposed",
        "purpose": "Classify concepts.",
        "categories": {
            "core_now": {
                "action": "implement_or_harden",
                "concepts": [
                    "project",
                    "goal",
                    "intent",
                    "context",
                    "agent",
                    "policy",
                    "harness",
                    "eval",
                    "evidence",
                    "approval",
                    "trace",
                    "budget",
                    "delivery_state",
                ],
            },
            "near_core_candidate": {
                "action": "docs_schema_local_validator_only",
                "concepts": ["handover", "decision_boundary"],
            },
            "extension_backlog": {
                "action": "roadmap_backlog",
                "concepts": ["operations", "product_eval"],
            },
            "profile_specific": {
                "action": "future_profile",
                "concepts": ["telecom_ops_profile"],
            },
            "outside_nornyx": {
                "action": "define_contract_only",
                "concepts": ["identity_provider"],
            },
            "rejected": {
                "action": "do_not_add",
                "concepts": ["prompt_trick_catalog"],
            },
        },
        "next_focus": ["GOAL-001 Core block spec freeze"],
    }


def test_valid_triage_matrix_has_no_errors() -> None:
    issues = validate_triage_matrix(valid_matrix())
    assert not any(issue.severity == "error" for issue in issues)


def test_duplicate_concepts_are_rejected() -> None:
    data = valid_matrix()
    data["categories"]["extension_backlog"]["concepts"].append("handover")
    issues = validate_triage_matrix(data)
    assert any("multiple categories" in issue.message for issue in issues)


def test_category_actions_are_locked() -> None:
    data = valid_matrix()
    data["categories"]["extension_backlog"]["action"] = "implement_or_harden"
    issues = validate_triage_matrix(data)
    assert any("extension_backlog.action" in issue.message for issue in issues)


def test_core_must_have_required_concepts() -> None:
    data = valid_matrix()
    data["categories"]["core_now"]["concepts"].remove("goal")
    issues = validate_triage_matrix(data)
    assert any("core_now missing" in issue.message for issue in issues)


def test_classify_concept() -> None:
    data = valid_matrix()
    assert classify_concept(data, "handover") == "near_core_candidate"
    assert classify_concept(data, "identity_provider") == "outside_nornyx"
    assert classify_concept(data, "unknown") is None


def test_should_create_diff_for_category() -> None:
    assert should_create_diff_for_category("core_now") is True
    assert should_create_diff_for_category("near_core_candidate") is True
    assert should_create_diff_for_category("extension_backlog") is False
    assert should_create_diff_for_category("outside_nornyx") is False


def test_triage_summary() -> None:
    summary = triage_summary(valid_matrix())
    assert "core_now=13" in summary
    assert "near_core_candidate=2" in summary


def test_real_triage_matrix_is_valid_and_keeps_backlog_out_of_core() -> None:
    data = yaml.safe_load(Path("docs/backlog/nornyx-requirement-triage-matrix.yaml").read_text())

    issues = validate_triage_matrix(data)

    assert not any(issue.severity == "error" for issue in issues)
    assert classify_concept(data, "handover") == "near_core_candidate"
    assert classify_concept(data, "operations") == "extension_backlog"
    assert classify_concept(data, "identity_provider") == "outside_nornyx"
    assert classify_concept(data, "automatic_github_writes") == "rejected"
    assert "GOAL-001 Core block spec freeze" in data["next_focus"]


def test_schema_categories_match_validator_categories() -> None:
    schema = json.loads(Path("schemas/requirement_triage_matrix.schema.json").read_text())
    categories = schema["properties"]["categories"]

    assert set(categories["required"]) == REQUIRED_CATEGORIES
    assert set(categories["properties"]) == REQUIRED_CATEGORIES


def test_real_matrix_actions_match_locked_actions() -> None:
    data = yaml.safe_load(Path("docs/backlog/nornyx-requirement-triage-matrix.yaml").read_text())

    actions = {
        category: section["action"]
        for category, section in data["categories"].items()
    }

    assert actions == EXPECTED_CATEGORY_ACTIONS
