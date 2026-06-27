"""Evergreen Assurance helpers for Nornyx.

This module is local/read-only validation only. It does not call LLMs,
networks, connectors, GitHub, shells, or production systems.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


STABLE_KERNEL_BLOCKS = {
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

ALLOWED_EXTENSION_STATUSES = {"experimental", "candidate", "stable", "deprecated"}

MATURITY_LEVELS = {
    0: "ad_hoc",
    1: "generated_instructions",
    2: "checked_contracts",
    3: "harness_runtime",
    4: "governed_connectors",
    5: "controlled_self_improvement",
}


@dataclass(frozen=True)
class EvergreenIssue:
    severity: str
    message: str


def _string_list(value: Any) -> bool:
    """Return True for a list whose items are non-empty strings.

    Empty lists are allowed by this helper for optional compatibility fields.
    Use _non_empty_string_list for required capability/conformance fields.
    """
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


def _non_empty_string_list(value: Any) -> bool:
    return _string_list(value) and len(value) > 0


def validate_evergreen_assurance(data: dict[str, Any]) -> list[EvergreenIssue]:
    issues: list[EvergreenIssue] = []

    if not isinstance(data.get("nornyx_version"), str) or not data.get("nornyx_version", "").strip():
        issues.append(EvergreenIssue("error", "nornyx_version is required"))

    kernel = data.get("kernel")
    if not isinstance(kernel, dict):
        issues.append(EvergreenIssue("error", "kernel must be an object"))
    else:
        stable_blocks = kernel.get("stable_blocks")
        if not _non_empty_string_list(stable_blocks):
            issues.append(EvergreenIssue("error", "kernel.stable_blocks must be a non-empty string list"))
        else:
            missing = sorted(STABLE_KERNEL_BLOCKS - set(stable_blocks))
            if missing:
                issues.append(EvergreenIssue("warning", f"stable kernel is missing recommended blocks: {missing}"))

    extensions = data.get("extensions")
    if not isinstance(extensions, list):
        issues.append(EvergreenIssue("error", "extensions must be a list"))
    else:
        seen: set[str] = set()
        for index, ext in enumerate(extensions):
            if not isinstance(ext, dict):
                issues.append(EvergreenIssue("error", f"extensions[{index}] must be an object"))
                continue

            name = ext.get("name")
            if not isinstance(name, str) or not name.strip():
                issues.append(EvergreenIssue("error", f"extensions[{index}].name is required"))
                continue

            if name in seen:
                issues.append(EvergreenIssue("error", f"duplicate extension: {name}"))
            seen.add(name)

            if ext.get("status") not in ALLOWED_EXTENSION_STATUSES:
                issues.append(EvergreenIssue("error", f"extension {name} has invalid status"))

            if not _non_empty_string_list(ext.get("provides")):
                issues.append(EvergreenIssue("error", f"extension {name} must provide at least one capability"))

            # Candidate and stable extensions must prove compatibility through at
            # least one conformance entry. Empty lists are invalid here.
            if ext.get("status") in {"candidate", "stable"} and not _non_empty_string_list(ext.get("conformance")):
                issues.append(EvergreenIssue("error", f"extension {name} requires conformance entries"))

    compatibility = data.get("compatibility")
    if not isinstance(compatibility, dict):
        issues.append(EvergreenIssue("error", "compatibility must be an object"))
    else:
        profiles = compatibility.get("profiles", [])
        if profiles and not _string_list(profiles):
            issues.append(EvergreenIssue("error", "compatibility.profiles must be a string list"))

        python_versions = compatibility.get("python", [])
        if python_versions and not _string_list(python_versions):
            issues.append(EvergreenIssue("error", "compatibility.python must be a string list"))

        operating_systems = compatibility.get("operating_systems", [])
        if operating_systems and not _string_list(operating_systems):
            issues.append(EvergreenIssue("error", "compatibility.operating_systems must be a string list"))

    maturity = data.get("maturity")
    if not isinstance(maturity, dict):
        issues.append(EvergreenIssue("error", "maturity must be an object"))
    else:
        level = maturity.get("level")
        if level not in MATURITY_LEVELS:
            issues.append(EvergreenIssue("error", "maturity.level must be between 0 and 5"))

        expected_name = MATURITY_LEVELS.get(level)
        name = maturity.get("name")
        if expected_name and name and name != expected_name:
            issues.append(EvergreenIssue("warning", f"maturity.name should be {expected_name!r} for level {level}"))

    return issues


def evergreen_summary(data: dict[str, Any]) -> str:
    extensions = data.get("extensions", [])
    maturity = data.get("maturity", {})
    level = maturity.get("level", "?") if isinstance(maturity, dict) else "?"
    level_name = MATURITY_LEVELS.get(level, "unknown")
    return (
        f"Nornyx {data.get('nornyx_version', 'unknown')} | "
        f"extensions={len(extensions) if isinstance(extensions, list) else 0} | "
        f"maturity=L{level}:{level_name}"
    )


def is_enterprise_ready(data: dict[str, Any]) -> bool:
    """Enterprise-ready means no validation errors and maturity level >= 2."""
    issues = validate_evergreen_assurance(data)
    if any(issue.severity == "error" for issue in issues):
        return False
    maturity = data.get("maturity", {})
    return isinstance(maturity, dict) and int(maturity.get("level", 0)) >= 2
