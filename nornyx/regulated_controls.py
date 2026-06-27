"""Regulated-system controls for Nornyx.

This module validates decision boundaries and evidence-quality contracts.
It is local/read-only and does not enforce runtime policy, call LLMs,
connect to external systems, or perform operational actions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


RECOMMENDED_AUDIT_QUALITY = {
    "immutable_timestamp",
    "source_hash",
    "approver_identity",
}

ALLOWED_QUALITY_FLAGS = {
    "immutable_timestamp",
    "source_hash",
    "source_provenance",
    "approver_identity",
    "tenant_id",
    "exportable_report",
    "tamper_resistant_storage",
    "retention_policy",
    "decision_reason",
}


@dataclass(frozen=True)
class RegulatedControlIssue:
    severity: str
    message: str


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and all(_non_empty_string(item) for item in value)


def _non_empty_string_list(value: Any) -> bool:
    return _string_list(value) and len(value) > 0


def validate_decision_boundary(data: dict[str, Any]) -> list[RegulatedControlIssue]:
    issues: list[RegulatedControlIssue] = []

    if not _non_empty_string(data.get("name")):
        issues.append(RegulatedControlIssue("error", "name is required"))

    if not _string_list(data.get("ai_allowed", [])):
        issues.append(RegulatedControlIssue("error", "ai_allowed must be a string list"))

    if not _non_empty_string_list(data.get("ai_denied")):
        issues.append(RegulatedControlIssue("error", "ai_denied must be a non-empty string list"))

    allowed = set(data.get("ai_allowed", []) or [])
    denied = set(data.get("ai_denied", []) or [])
    overlap = sorted(allowed.intersection(denied))
    if overlap:
        issues.append(RegulatedControlIssue("error", f"actions cannot be both allowed and denied: {overlap}"))

    if not _non_empty_string(data.get("human_owner")):
        issues.append(RegulatedControlIssue("error", "human_owner is required"))

    if not isinstance(data.get("approval_required"), bool):
        issues.append(RegulatedControlIssue("error", "approval_required must be boolean"))

    evidence_required = data.get("evidence_required", [])
    if data.get("approval_required") is True and not _non_empty_string_list(evidence_required):
        issues.append(RegulatedControlIssue("error", "approval_required=True requires evidence_required"))

    if data.get("approval_required") is False and denied:
        issues.append(RegulatedControlIssue("warning", "boundary denies AI actions but approval_required is false"))

    return issues


def validate_evidence_quality(data: dict[str, Any]) -> list[RegulatedControlIssue]:
    issues: list[RegulatedControlIssue] = []

    if not _non_empty_string(data.get("name")):
        issues.append(RegulatedControlIssue("error", "name is required"))

    if not _non_empty_string_list(data.get("required")):
        issues.append(RegulatedControlIssue("error", "required must be a non-empty string list"))

    quality = data.get("quality")
    if not _non_empty_string_list(quality):
        issues.append(RegulatedControlIssue("error", "quality must be a non-empty string list"))
        return issues

    invalid = sorted(set(quality) - ALLOWED_QUALITY_FLAGS)
    if invalid:
        issues.append(RegulatedControlIssue("error", f"invalid quality flags: {invalid}"))

    missing_recommended = sorted(RECOMMENDED_AUDIT_QUALITY - set(quality))
    if missing_recommended:
        issues.append(RegulatedControlIssue("warning", f"audit-grade evidence should include: {missing_recommended}"))

    if "retention_policy" in quality and not _non_empty_string(data.get("retention")):
        issues.append(RegulatedControlIssue("error", "retention_policy quality requires retention"))

    export = data.get("export")
    if export is not None and not isinstance(export, dict):
        issues.append(RegulatedControlIssue("error", "export must be an object"))

    return issues


def validate_regulated_control_pack(data: dict[str, Any]) -> list[RegulatedControlIssue]:
    """Validate a local pack of decision boundaries and evidence-quality contracts."""
    issues: list[RegulatedControlIssue] = []
    boundaries = data.get("decision_boundaries")
    evidence_contracts = data.get("evidence_quality")

    if not isinstance(boundaries, list) or not boundaries:
        issues.append(RegulatedControlIssue("error", "decision_boundaries must be a non-empty list"))
        boundaries = []

    if not isinstance(evidence_contracts, list) or not evidence_contracts:
        issues.append(RegulatedControlIssue("error", "evidence_quality must be a non-empty list"))
        evidence_contracts = []

    boundary_names: set[str] = set()
    required_evidence: set[str] = set()
    for index, boundary in enumerate(boundaries):
        if not isinstance(boundary, dict):
            issues.append(RegulatedControlIssue("error", f"decision_boundaries[{index}] must be an object"))
            continue
        issues.extend(validate_decision_boundary(boundary))
        name = str(boundary.get("name", ""))
        if name in boundary_names:
            issues.append(RegulatedControlIssue("error", f"duplicate decision boundary name: {name}"))
        if name:
            boundary_names.add(name)
        if boundary.get("approval_required") is True:
            required_evidence.update(str(item) for item in boundary.get("evidence_required", []) or [])

    evidence_names: set[str] = set()
    covered_evidence: set[str] = set()
    for index, contract in enumerate(evidence_contracts):
        if not isinstance(contract, dict):
            issues.append(RegulatedControlIssue("error", f"evidence_quality[{index}] must be an object"))
            continue
        issues.extend(validate_evidence_quality(contract))
        name = str(contract.get("name", ""))
        if name in evidence_names:
            issues.append(RegulatedControlIssue("error", f"duplicate evidence quality name: {name}"))
        if name:
            evidence_names.add(name)
        covered_evidence.update(str(item) for item in contract.get("required", []) or [])

    missing_coverage = sorted(required_evidence - covered_evidence)
    if missing_coverage:
        issues.append(
            RegulatedControlIssue(
                "error",
                f"approval-required evidence is not covered by evidence_quality.required: {missing_coverage}",
            )
        )

    safety = data.get("safety", {})
    if isinstance(safety, dict):
        for flag in [
            "automatic_approval",
            "connector_calls",
            "llm_calls",
            "deployment_actions",
            "production_writes",
        ]:
            if safety.get(flag) is not False:
                issues.append(RegulatedControlIssue("error", f"safety.{flag} must be false"))

    return issues


def decision_boundary_summary(data: dict[str, Any]) -> str:
    return (
        f"{data.get('name', '<decision_boundary>')} | "
        f"allowed={len(data.get('ai_allowed', []) or [])} | "
        f"denied={len(data.get('ai_denied', []) or [])} | "
        f"owner={data.get('human_owner', '<missing>')}"
    )


def evidence_quality_summary(data: dict[str, Any]) -> str:
    return (
        f"{data.get('name', '<evidence_quality>')} | "
        f"required={len(data.get('required', []) or [])} | "
        f"quality={len(data.get('quality', []) or [])}"
    )


def regulated_control_pack_summary(data: dict[str, Any]) -> str:
    boundaries = data.get("decision_boundaries", [])
    evidence_contracts = data.get("evidence_quality", [])
    return (
        f"{data.get('name', 'RegulatedControlPack')} | "
        f"decision_boundaries={len(boundaries) if isinstance(boundaries, list) else 0} | "
        f"evidence_quality={len(evidence_contracts) if isinstance(evidence_contracts, list) else 0}"
    )
