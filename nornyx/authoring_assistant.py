"""Authoring Assistant roadmap validation for Nornyx.

This module validates the authoring-assistant roadmap. It does not call LLMs,
host models, run a portal, write .nyx, call connectors, or approve drafts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REQUIRED_AUTHORITY_RULE_SNIPPETS = ["llm", "checker", "human", "unknown"]
REQUIRED_CAPABILITIES = {"cli_wizard", "llm_authoring_pack", "formatted_preview", "repair_loop"}
ALLOWED_ROADMAP_CAPABILITY_STATUSES = {"roadmap", "research"}
REQUIRED_NON_GOAL_SNIPPETS = [
    "live llm",
    "fine-tuning",
    "model hosting",
    "portal implementation",
    "automatic approval",
    "automatic production writes",
]
REQUIRED_PROMOTION_GATE_SNIPPETS = ["checker", "human approval", "capability", "evidence"]
REQUIRED_BLOCKED_ACTIONS = {
    "live_llm_calls",
    "fine_tuning_pipeline",
    "model_hosting",
    "portal_implementation",
    "automatic_approval",
    "automatic_repo_writes",
    "production_config_writes",
    "external_tool_calls_by_default",
    "checker_bypass",
}
UNSAFE_SAFE_NOW_CAPABILITIES = {"ui_authoring_portal", "specialized_small_model"}


@dataclass(frozen=True)
class AuthoringIssue:
    severity: str
    message: str


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _non_empty_string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_non_empty_string(item) for item in value)


def validate_authoring_roadmap(data: dict[str, Any]) -> list[AuthoringIssue]:
    issues: list[AuthoringIssue] = []

    for field in ["schema_version", "status", "name", "purpose"]:
        if not _non_empty_string(data.get(field)):
            issues.append(AuthoringIssue("error", f"{field} is required"))

    if data.get("status") != "roadmap":
        issues.append(AuthoringIssue("error", "authoring assistant pack must remain status=roadmap"))

    capabilities = data.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        issues.append(AuthoringIssue("error", "capabilities must be a non-empty list"))
    else:
        seen: set[str] = set()
        for index, cap in enumerate(capabilities):
            if not isinstance(cap, dict):
                issues.append(AuthoringIssue("error", f"capabilities[{index}] must be an object"))
                continue

            cap_id = cap.get("id")
            if not _non_empty_string(cap_id):
                issues.append(AuthoringIssue("error", f"capabilities[{index}].id is required"))
                continue

            if cap_id in seen:
                issues.append(AuthoringIssue("error", f"duplicate capability: {cap_id}"))
            seen.add(str(cap_id))

            if cap.get("status") not in ALLOWED_ROADMAP_CAPABILITY_STATUSES:
                issues.append(
                    AuthoringIssue(
                        "error",
                        f"capability {cap_id} must remain roadmap or research until separately promoted",
                    )
                )

            if cap.get("priority") not in {"low", "medium", "high"}:
                issues.append(AuthoringIssue("error", f"capability {cap_id} has invalid priority"))

            if not isinstance(cap.get("safe_now"), bool):
                issues.append(AuthoringIssue("error", f"capability {cap_id}.safe_now must be boolean"))
            elif cap["safe_now"] is True and cap_id in UNSAFE_SAFE_NOW_CAPABILITIES:
                issues.append(AuthoringIssue("error", f"capability {cap_id} cannot be safe_now"))

            if not _non_empty_string(cap.get("description")):
                issues.append(AuthoringIssue("error", f"capability {cap_id}.description is required"))

        missing = sorted(REQUIRED_CAPABILITIES - seen)
        if missing:
            issues.append(AuthoringIssue("warning", f"recommended capabilities missing: {missing}"))

    authority_rules = data.get("authority_rules")
    if not _non_empty_string_list(authority_rules):
        issues.append(AuthoringIssue("error", "authority_rules must be a non-empty string list"))
    else:
        authority_text = " ".join(authority_rules).lower()
        for snippet in REQUIRED_AUTHORITY_RULE_SNIPPETS:
            if snippet not in authority_text:
                issues.append(AuthoringIssue("warning", f"authority_rules should mention {snippet!r}"))
        if "approve" not in authority_text and "approval" not in authority_text:
            issues.append(AuthoringIssue("warning", "authority_rules should mention approval"))

    non_goals = data.get("non_goals")
    if not _non_empty_string_list(non_goals):
        issues.append(AuthoringIssue("error", "non_goals must be a non-empty string list"))
    else:
        non_goal_text = " ".join(non_goals).lower()
        for snippet in REQUIRED_NON_GOAL_SNIPPETS:
            if snippet not in non_goal_text:
                issues.append(AuthoringIssue("error", f"non_goals must block {snippet!r}"))

    promotion_gates = data.get("promotion_gates")
    if not _non_empty_string_list(promotion_gates):
        issues.append(AuthoringIssue("error", "promotion_gates must be a non-empty string list"))
    else:
        gate_text = " ".join(promotion_gates).lower()
        for snippet in REQUIRED_PROMOTION_GATE_SNIPPETS:
            if snippet not in gate_text:
                issues.append(AuthoringIssue("error", f"promotion_gates must mention {snippet!r}"))

    blocked_actions = data.get("blocked_actions")
    if not _non_empty_string_list(blocked_actions):
        issues.append(AuthoringIssue("error", "blocked_actions must be a non-empty string list"))
    else:
        missing_actions = sorted(REQUIRED_BLOCKED_ACTIONS - set(blocked_actions))
        if missing_actions:
            issues.append(AuthoringIssue("error", f"blocked_actions missing: {missing_actions}"))

    for field in ["next_focus"]:
        value = data.get(field, [])
        if value and not _non_empty_string_list(value):
            issues.append(AuthoringIssue("error", f"{field} must be a string list"))

    return issues


def authoring_summary(data: dict[str, Any]) -> str:
    caps = data.get("capabilities", [])
    safe_now = 0
    if isinstance(caps, list):
        safe_now = sum(1 for cap in caps if isinstance(cap, dict) and cap.get("safe_now") is True)
    return (
        f"{data.get('name', 'AuthoringAssistant')} | "
        f"status={data.get('status', 'unknown')} | "
        f"capabilities={len(caps) if isinstance(caps, list) else 0} | "
        f"safe_now={safe_now}"
    )


def should_start_with_cli_wizard(data: dict[str, Any]) -> bool:
    caps = data.get("capabilities", [])
    if not isinstance(caps, list):
        return False
    for cap in caps:
        if isinstance(cap, dict) and cap.get("id") == "cli_wizard":
            return cap.get("priority") == "high" and cap.get("safe_now") is True
    return False
