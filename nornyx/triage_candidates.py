"""Triage candidate validation for agent-discovered requirements.

This module is local/read-only validation. It does not call LLMs,
connectors, networks, GitHub, shells, or production systems.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

from .requirement_triage import classify_concept

try:
    import yaml
except Exception:  # pragma: no cover - fallback only
    yaml = None  # type: ignore[assignment]


CLASSIFICATIONS = {
    "core_now",
    "near_core_candidate",
    "extension_backlog",
    "profile_specific",
    "outside_nornyx",
    "rejected",
}

DISCOVERED_BY = {"codex", "claude", "human", "other"}
RISK_LEVELS = {"low", "medium", "high"}
STATUSES = {"proposed", "accepted", "rejected", "deferred"}


@dataclass(frozen=True)
class CandidateIssue:
    severity: str
    candidate_id: str
    message: str


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _non_empty_string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_non_empty_string(item) for item in value)


def validate_triage_candidate(candidate: dict[str, Any]) -> list[CandidateIssue]:
    candidate_id = str(candidate.get("id", "<missing-id>"))
    issues: list[CandidateIssue] = []

    for field in [
        "id",
        "title",
        "concept",
        "source_task",
        "description",
        "rationale",
        "recommended_action",
        "owner",
    ]:
        if not _non_empty_string(candidate.get(field)):
            issues.append(CandidateIssue("error", candidate_id, f"{field} is required"))

    if not str(candidate.get("id", "")).startswith("TC-"):
        issues.append(CandidateIssue("error", candidate_id, "id must start with TC-"))

    if candidate.get("discovered_by") not in DISCOVERED_BY:
        issues.append(CandidateIssue("error", candidate_id, f"discovered_by must be one of {sorted(DISCOVERED_BY)}"))

    if candidate.get("classification") not in CLASSIFICATIONS:
        issues.append(CandidateIssue("error", candidate_id, f"classification must be one of {sorted(CLASSIFICATIONS)}"))

    if not isinstance(candidate.get("blocks_current_goal"), bool):
        issues.append(CandidateIssue("error", candidate_id, "blocks_current_goal must be boolean"))

    if candidate.get("risk") not in RISK_LEVELS:
        issues.append(CandidateIssue("error", candidate_id, f"risk must be one of {sorted(RISK_LEVELS)}"))

    if candidate.get("status") not in STATUSES:
        issues.append(CandidateIssue("error", candidate_id, f"status must be one of {sorted(STATUSES)}"))

    if not _non_empty_string_list(candidate.get("evidence")):
        issues.append(CandidateIssue("error", candidate_id, "evidence must be a non-empty string list"))

    if candidate.get("blocks_current_goal") is True:
        action = str(candidate.get("recommended_action", "")).lower()
        if "stop" not in action and "human" not in action and "decision" not in action:
            issues.append(
                CandidateIssue(
                    "warning",
                    candidate_id,
                    "blocking candidates should recommend stop/escalation/human decision",
                )
            )

    if candidate.get("classification") in {"outside_nornyx", "rejected"} and candidate.get("blocks_current_goal") is True:
        issues.append(
            CandidateIssue(
                "warning",
                candidate_id,
                "outside/rejected candidates usually should not block the current goal unless acceptance depends on them",
            )
        )

    return issues


def validate_candidate_against_matrix(
    candidate: dict[str, Any],
    matrix: dict[str, Any],
) -> list[CandidateIssue]:
    candidate_id = str(candidate.get("id", "<missing-id>"))
    issues: list[CandidateIssue] = []
    concept = str(candidate.get("concept", "")).strip()
    if not concept:
        return issues

    expected = classify_concept(matrix, concept)
    if expected is None:
        issues.append(
            CandidateIssue(
                "warning",
                candidate_id,
                "concept is not in the requirement triage matrix and requires human review",
            )
        )
        return issues

    if candidate.get("classification") != expected:
        issues.append(
            CandidateIssue(
                "error",
                candidate_id,
                f"classification {candidate.get('classification')!r} does not match matrix category {expected!r}",
            )
        )
    return issues


def load_candidate(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        if yaml is None:
            raise RuntimeError("PyYAML is required for YAML triage candidates")
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path} root must be an object")
    return data


def find_candidate_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.iterdir()
        if path.is_file() and path.suffix.lower() in {".yaml", ".yml", ".json"}
    )


def validate_candidate_directory(
    root: Path,
    matrix: dict[str, Any] | None = None,
) -> list[CandidateIssue]:
    issues: list[CandidateIssue] = []
    seen_ids: set[str] = set()

    for path in find_candidate_files(root):
        try:
            candidate = load_candidate(path)
        except Exception as exc:  # noqa: BLE001 - validation should report path-level failure
            issues.append(CandidateIssue("error", path.name, f"failed to load candidate: {exc}"))
            continue

        candidate_id = str(candidate.get("id", path.name))
        if candidate_id in seen_ids:
            issues.append(CandidateIssue("error", candidate_id, "duplicate candidate id"))
        seen_ids.add(candidate_id)

        issues.extend(validate_triage_candidate(candidate))
        if matrix is not None:
            issues.extend(validate_candidate_against_matrix(candidate, matrix))

    return issues


def candidate_summary(candidate: dict[str, Any]) -> str:
    return (
        f"{candidate.get('id', '<missing-id>')} | "
        f"{candidate.get('concept', '<concept>')} | "
        f"{candidate.get('classification', '<classification>')} | "
        f"blocks={candidate.get('blocks_current_goal', '<unknown>')} | "
        f"{candidate.get('title', '<title>')}"
    )
