"""Product-to-Operations lifecycle extension helpers.

This is roadmap/backlog validation only. It does not implement product
management, design tooling, operations automation, connectors, or runtime actions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ALLOWED_EXTENSION_STATUSES = {"roadmap", "experimental", "candidate", "stable"}
ALLOWED_PLACEMENTS = {"roadmap", "near_term_design", "candidate", "core"}
RECOMMENDED_CONCEPTS = {
    "intake",
    "persona",
    "journey",
    "prototype",
    "assumption",
    "open_question",
    "decision_needed",
    "handover",
    "operations",
    "product_eval",
    "lifecycle_state",
}


@dataclass(frozen=True)
class LifecycleIssue:
    severity: str
    message: str


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_lifecycle_extension(data: dict[str, Any]) -> list[LifecycleIssue]:
    issues: list[LifecycleIssue] = []

    if not _non_empty_string(data.get("name")):
        issues.append(LifecycleIssue("error", "name is required"))

    if data.get("status") not in ALLOWED_EXTENSION_STATUSES:
        issues.append(LifecycleIssue("error", f"status must be one of {sorted(ALLOWED_EXTENSION_STATUSES)}"))

    concepts = data.get("concepts")
    if not isinstance(concepts, list) or not concepts:
        issues.append(LifecycleIssue("error", "concepts must be a non-empty list"))
    else:
        seen: set[str] = set()
        for index, concept in enumerate(concepts):
            if not isinstance(concept, dict):
                issues.append(LifecycleIssue("error", f"concepts[{index}] must be an object"))
                continue
            name = concept.get("name")
            if not _non_empty_string(name):
                issues.append(LifecycleIssue("error", f"concepts[{index}].name is required"))
                continue
            if name in seen:
                issues.append(LifecycleIssue("error", f"duplicate concept: {name}"))
            seen.add(str(name))

            if not _non_empty_string(concept.get("purpose")):
                issues.append(LifecycleIssue("error", f"concept {name} requires purpose"))

            if concept.get("placement") not in ALLOWED_PLACEMENTS:
                issues.append(LifecycleIssue("error", f"concept {name} has invalid placement"))

        missing = sorted(RECOMMENDED_CONCEPTS - seen)
        if missing:
            issues.append(LifecycleIssue("warning", f"recommended lifecycle concepts missing: {missing}"))

    promotion_order = data.get("promotion_order")
    if not isinstance(promotion_order, list) or not all(_non_empty_string(item) for item in promotion_order):
        issues.append(LifecycleIssue("error", "promotion_order must be a string list"))

    if isinstance(promotion_order, list) and "handover" not in promotion_order:
        issues.append(LifecycleIssue("warning", "handover should appear in promotion_order"))

    return issues


def lifecycle_summary(data: dict[str, Any]) -> str:
    concepts = data.get("concepts", [])
    status = data.get("status", "unknown")
    return f"{data.get('name', 'LifecycleExtension')} | status={status} | concepts={len(concepts) if isinstance(concepts, list) else 0}"


def should_promote_handover_first(data: dict[str, Any]) -> bool:
    order = data.get("promotion_order", [])
    return isinstance(order, list) and bool(order) and order[0] == "handover"
