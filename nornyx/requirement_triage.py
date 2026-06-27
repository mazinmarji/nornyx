"""Requirement triage matrix helpers for Nornyx.

This module validates and summarizes the requirement triage matrix.
It is local/read-only and does not call LLMs, connectors, networks,
shell commands, GitHub, or production systems.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REQUIRED_CATEGORIES = {
    "core_now",
    "near_core_candidate",
    "extension_backlog",
    "profile_specific",
    "outside_nornyx",
    "rejected",
}

EXPECTED_CATEGORY_ACTIONS = {
    "core_now": "implement_or_harden",
    "near_core_candidate": "docs_schema_local_validator_only",
    "extension_backlog": "roadmap_backlog",
    "profile_specific": "future_profile",
    "outside_nornyx": "define_contract_only",
    "rejected": "do_not_add",
}

CORE_MUST_HAVE = {
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
}


@dataclass(frozen=True)
class TriageIssue:
    severity: str
    message: str


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)


def validate_triage_matrix(data: dict[str, Any]) -> list[TriageIssue]:
    issues: list[TriageIssue] = []

    if not isinstance(data.get("schema_version"), str) or not data["schema_version"].strip():
        issues.append(TriageIssue("error", "schema_version is required"))

    if data.get("status") not in {"proposed", "accepted", "deprecated"}:
        issues.append(TriageIssue("error", "status must be proposed, accepted, or deprecated"))

    categories = data.get("categories")
    if not isinstance(categories, dict):
        issues.append(TriageIssue("error", "categories must be an object"))
        return issues

    missing_categories = sorted(REQUIRED_CATEGORIES - set(categories))
    if missing_categories:
        issues.append(TriageIssue("error", f"missing categories: {missing_categories}"))

    all_concepts: dict[str, str] = {}
    duplicates: list[str] = []

    for category in sorted(REQUIRED_CATEGORIES.intersection(categories)):
        section = categories[category]
        if not isinstance(section, dict):
            issues.append(TriageIssue("error", f"{category} must be an object"))
            continue

        action = section.get("action")
        if not isinstance(action, str) or not action.strip():
            issues.append(TriageIssue("error", f"{category}.action is required"))
        elif action != EXPECTED_CATEGORY_ACTIONS[category]:
            issues.append(
                TriageIssue(
                    "error",
                    f"{category}.action must be {EXPECTED_CATEGORY_ACTIONS[category]!r}",
                )
            )

        concepts = section.get("concepts")
        if not _string_list(concepts):
            issues.append(TriageIssue("error", f"{category}.concepts must be a non-empty string list"))
            continue

        for concept in concepts:
            if concept in all_concepts:
                duplicates.append(concept)
            all_concepts[concept] = category

    if duplicates:
        issues.append(TriageIssue("error", f"concepts appear in multiple categories: {sorted(set(duplicates))}"))

    core = set(categories.get("core_now", {}).get("concepts", []) or [])
    missing_core = sorted(CORE_MUST_HAVE - core)
    if missing_core:
        issues.append(TriageIssue("error", f"core_now missing required concepts: {missing_core}"))

    next_focus = data.get("next_focus")
    if not _string_list(next_focus):
        issues.append(TriageIssue("error", "next_focus must be a non-empty string list"))

    return issues


def triage_summary(data: dict[str, Any]) -> str:
    categories = data.get("categories", {})
    parts = []
    if isinstance(categories, dict):
        for category in sorted(REQUIRED_CATEGORIES):
            section = categories.get(category, {})
            count = len(section.get("concepts", []) or []) if isinstance(section, dict) else 0
            parts.append(f"{category}={count}")
    return " | ".join(parts)


def classify_concept(data: dict[str, Any], concept: str) -> str | None:
    categories = data.get("categories", {})
    if not isinstance(categories, dict):
        return None
    for category, section in categories.items():
        if isinstance(section, dict) and concept in (section.get("concepts", []) or []):
            return str(category)
    return None


def should_create_diff_for_category(category: str) -> bool:
    """Return whether a concept category generally justifies a new diff."""
    return category in {"core_now", "near_core_candidate"}
