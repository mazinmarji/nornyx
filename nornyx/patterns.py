"""AI Pattern Lifecycle helpers for Nornyx.

This module is pure/local validation only. It does not call LLMs, external
tools, networks, shells, or production systems.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ALLOWED_PATTERN_TYPES = {
    "prompt",
    "context",
    "agent_workflow",
    "harness",
    "eval",
    "evidence",
    "tool_integration",
    "portal_renderer",
    "security_guardrail",
}

ALLOWED_PATTERN_STATUSES = {
    "experimental",
    "evaluated",
    "candidate",
    "stable",
    "deprecated",
}


@dataclass(frozen=True)
class PatternIssue:
    severity: str
    message: str


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _non_empty_string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_non_empty_string(item) for item in value)


def validate_pattern_lifecycle(pattern: dict[str, Any]) -> list[PatternIssue]:
    issues: list[PatternIssue] = []

    for field in ["id", "name", "problem", "solution"]:
        if not _non_empty_string(pattern.get(field)):
            issues.append(PatternIssue("error", f"{field} is required"))

    if pattern.get("type") not in ALLOWED_PATTERN_TYPES:
        issues.append(PatternIssue("error", f"type must be one of {sorted(ALLOWED_PATTERN_TYPES)}"))

    if pattern.get("status") not in ALLOWED_PATTERN_STATUSES:
        issues.append(PatternIssue("error", f"status must be one of {sorted(ALLOWED_PATTERN_STATUSES)}"))

    for field in [
        "applicability",
        "validation",
        "evidence",
        "risks",
        "failure_modes",
        "promotion_criteria",
    ]:
        if not _non_empty_string_list(pattern.get(field)):
            issues.append(PatternIssue("error", f"{field} must be a non-empty list of strings"))

    status = pattern.get("status")
    if status in {"candidate", "stable"}:
        if len(pattern.get("evidence", []) or []) < 1:
            issues.append(PatternIssue("error", "candidate/stable patterns require evidence"))
        if len(pattern.get("validation", []) or []) < 1:
            issues.append(PatternIssue("error", "candidate/stable patterns require validation"))

    if status == "stable":
        criteria = pattern.get("promotion_criteria", []) or []
        criteria_text = " ".join(criteria).lower()
        if "human" not in criteria_text and "approval" not in criteria_text:
            issues.append(PatternIssue("warning", "stable patterns should include human approval/review criteria"))

    return issues


def can_promote(pattern: dict[str, Any]) -> bool:
    """Return True only when a pattern has no validation errors."""
    return not any(issue.severity == "error" for issue in validate_pattern_lifecycle(pattern))


def summarize_pattern(pattern: dict[str, Any]) -> str:
    return (
        f"{pattern.get('id', '<missing>')} "
        f"[{pattern.get('type', 'unknown')}/{pattern.get('status', 'unknown')}]: "
        f"{pattern.get('name', '<unnamed>')}"
    )
