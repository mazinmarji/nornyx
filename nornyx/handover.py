"""Handover and ambiguity-control validators for Nornyx.

This module is local/read-only validation only. It does not call LLMs,
connectors, shell commands, networks, GitHub, or production systems.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ALLOWED_AMBIGUITY_KINDS = {"assumption", "open_question", "decision_needed"}
ALLOWED_RISKS = {"low", "medium", "high"}


@dataclass(frozen=True)
class HandoverIssue:
    severity: str
    message: str


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _non_empty_string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_non_empty_string(item) for item in value)


def validate_handover_contract(data: dict[str, Any]) -> list[HandoverIssue]:
    issues: list[HandoverIssue] = []

    for field in ["name", "from_state", "to_state", "approval", "evidence"]:
        if not _non_empty_string(data.get(field)):
            issues.append(HandoverIssue("error", f"{field} is required"))

    if data.get("from_state") == data.get("to_state"):
        issues.append(HandoverIssue("error", "from_state and to_state must differ"))

    if not _non_empty_string_list(data.get("required")):
        issues.append(HandoverIssue("error", "required must be a non-empty list of strings"))

    acceptance = data.get("acceptance", [])
    if acceptance and not isinstance(acceptance, list):
        issues.append(HandoverIssue("error", "acceptance must be a list"))
    elif isinstance(acceptance, list) and not all(_non_empty_string(item) for item in acceptance):
        issues.append(HandoverIssue("error", "acceptance items must be non-empty strings"))

    blocking_questions = data.get("blocking_open_questions", [])
    if blocking_questions and not isinstance(blocking_questions, list):
        issues.append(HandoverIssue("error", "blocking_open_questions must be a list"))
    elif isinstance(blocking_questions, list) and not all(_non_empty_string(item) for item in blocking_questions):
        issues.append(HandoverIssue("error", "blocking_open_questions items must be non-empty strings"))

    return issues


def validate_ambiguity_control(data: dict[str, Any]) -> list[HandoverIssue]:
    issues: list[HandoverIssue] = []

    kind = data.get("kind")
    if kind not in ALLOWED_AMBIGUITY_KINDS:
        issues.append(HandoverIssue("error", f"kind must be one of {sorted(ALLOWED_AMBIGUITY_KINDS)}"))

    for field in ["id", "text", "owner"]:
        if not _non_empty_string(data.get(field)):
            issues.append(HandoverIssue("error", f"{field} is required"))

    risk = data.get("risk")
    if risk is not None and risk not in ALLOWED_RISKS:
        issues.append(HandoverIssue("error", f"risk must be one of {sorted(ALLOWED_RISKS)}"))

    if kind == "assumption" and "can_proceed" not in data:
        issues.append(HandoverIssue("error", "assumption must declare can_proceed"))

    if kind == "open_question":
        blocks = data.get("blocks", [])
        if blocks and not isinstance(blocks, list):
            issues.append(HandoverIssue("error", "open_question.blocks must be a list"))
        elif isinstance(blocks, list) and not all(_non_empty_string(item) for item in blocks):
            issues.append(HandoverIssue("error", "open_question.blocks items must be non-empty strings"))

    if kind == "decision_needed":
        required_before = data.get("required_before", [])
        if not _non_empty_string_list(required_before):
            issues.append(HandoverIssue("error", "decision_needed requires non-empty required_before list"))

    return issues


def validate_handover_pack(data: dict[str, Any]) -> list[HandoverIssue]:
    """Validate a local handover/ambiguity pack.

    The pack shape is intentionally simple:
    - handovers: list of handover contracts
    - ambiguity_controls: list of assumption/open_question/decision_needed items
    """
    issues: list[HandoverIssue] = []
    handovers = data.get("handovers")
    controls = data.get("ambiguity_controls")

    if not isinstance(handovers, list) or not handovers:
        issues.append(HandoverIssue("error", "handovers must be a non-empty list"))
        handovers = []

    if not isinstance(controls, list) or not controls:
        issues.append(HandoverIssue("error", "ambiguity_controls must be a non-empty list"))
        controls = []

    open_questions: set[str] = set()
    control_ids: set[str] = set()
    for index, control in enumerate(controls):
        if not isinstance(control, dict):
            issues.append(HandoverIssue("error", f"ambiguity_controls[{index}] must be an object"))
            continue
        issues.extend(validate_ambiguity_control(control))
        control_id = str(control.get("id", ""))
        if control_id in control_ids:
            issues.append(HandoverIssue("error", f"duplicate ambiguity control id: {control_id}"))
        if control_id:
            control_ids.add(control_id)
        if control.get("kind") == "open_question" and control_id:
            open_questions.add(control_id)

    handover_names: set[str] = set()
    for index, handover in enumerate(handovers):
        if not isinstance(handover, dict):
            issues.append(HandoverIssue("error", f"handovers[{index}] must be an object"))
            continue
        issues.extend(validate_handover_contract(handover))
        name = str(handover.get("name", ""))
        if name in handover_names:
            issues.append(HandoverIssue("error", f"duplicate handover name: {name}"))
        if name:
            handover_names.add(name)
        blockers = set(str(item) for item in handover.get("blocking_open_questions", []) or [])
        missing_blockers = sorted(blockers - open_questions)
        if missing_blockers:
            issues.append(
                HandoverIssue(
                    "error",
                    f"handover {name or index} references unknown blocking open questions: {missing_blockers}",
                )
            )

    return issues


def handover_ready(handover: dict[str, Any], artifacts_present: set[str], unresolved_questions: set[str]) -> bool:
    """Return True when a handover can proceed.

    This is a pure check. The caller supplies artifact/question state.
    """
    if any(issue.severity == "error" for issue in validate_handover_contract(handover)):
        return False

    required = set(str(item) for item in handover.get("required", []))
    if not required.issubset(artifacts_present):
        return False

    blockers = set(str(item) for item in handover.get("blocking_open_questions", []))
    if blockers.intersection(unresolved_questions):
        return False

    return True


def handover_summary(handover: dict[str, Any]) -> str:
    return (
        f"{handover.get('name', '<handover>')}: "
        f"{handover.get('from_state', '?')} -> {handover.get('to_state', '?')} | "
        f"required={len(handover.get('required', []) or [])}"
    )


def handover_pack_summary(data: dict[str, Any]) -> str:
    handovers = data.get("handovers", [])
    controls = data.get("ambiguity_controls", [])
    return (
        f"{data.get('name', 'HandoverPack')} | "
        f"handovers={len(handovers) if isinstance(handovers, list) else 0} | "
        f"ambiguity_controls={len(controls) if isinstance(controls, list) else 0}"
    )
