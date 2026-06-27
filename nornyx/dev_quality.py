"""Safe developer-quality helpers for Nornyx.

This module contains pure/local utilities only. It does not call LLMs,
connectors, networks, shells, or production systems.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any


@dataclass(frozen=True)
class PmoIssue:
    severity: str
    block_id: str
    message: str


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} root must be a JSON object")
    return data


def audit_pmo_status(data: dict[str, Any]) -> list[PmoIssue]:
    """Return consistency issues in a PMO status document."""
    issues: list[PmoIssue] = []
    blocks = data.get("blocks", [])
    if not isinstance(blocks, list):
        return [PmoIssue("error", "<root>", "blocks must be a list")]

    for block in blocks:
        if not isinstance(block, dict):
            issues.append(PmoIssue("error", "<unknown>", "block must be an object"))
            continue

        block_id = str(block.get("id", "<missing-id>"))
        title = str(block.get("title", ""))
        status = str(block.get("status", ""))
        pct = int(block.get("completion_pct", 0) or 0)
        completed = block.get("completed", []) or []
        pending = block.get("pending", []) or []

        if not title:
            issues.append(PmoIssue("error", block_id, "title is required"))

        if title.startswith("GOAL-") and "—" not in title:
            issues.append(PmoIssue("warning", block_id, "goal title should use 'GOAL-XXX — Name' format"))

        if status == "completed" and pending:
            issues.append(PmoIssue("error", block_id, "completed block cannot have pending items"))

        if status == "completed" and pct != 100:
            issues.append(PmoIssue("error", block_id, "completed block must have completion_pct 100"))

        if status != "completed" and pct == 100:
            issues.append(PmoIssue("error", block_id, "non-completed block cannot have completion_pct 100"))

        if status == "not_started" and (pct > 0 or completed):
            issues.append(PmoIssue("error", block_id, "not_started block cannot have progress or completed items"))

        if status == "locked" and pct >= 100:
            issues.append(PmoIssue("error", block_id, "locked block cannot be 100% complete"))

        if pct < 0 or pct > 100:
            issues.append(PmoIssue("error", block_id, "completion_pct must be between 0 and 100"))

    return issues


def status_summary(data: dict[str, Any]) -> str:
    blocks = data.get("blocks", [])
    completed = sum(1 for b in blocks if isinstance(b, dict) and b.get("status") == "completed")
    partial = sum(1 for b in blocks if isinstance(b, dict) and b.get("status") == "partial")
    locked = sum(1 for b in blocks if isinstance(b, dict) and b.get("status") == "locked")
    return f"blocks={len(blocks)} completed={completed} partial={partial} locked={locked}"


def repo_file_exists(repo_root: Path, rel_path: str) -> bool:
    return (repo_root / rel_path).exists()


QUALITY_PROFILES = {"fast", "standard", "release", "regulated"}


def _script_command(repo_root: Path, rel_path: str, *args: str) -> list[str] | None:
    if repo_file_exists(repo_root, rel_path):
        return ["python", rel_path, *args]
    return None


def safe_quality_commands(repo_root: Path, profile: str = "standard") -> list[list[str]]:
    """Return safe local commands that can be run by scripts/dev/run_quality.py.

    Profiles:
    - fast: pytest only.
    - standard: pytest plus core local status/triage checks when present.
    - release: standard plus drift/KPI smoke checks when present.
    - regulated: release plus the same local checks under the strictest profile name.

    The function intentionally returns an allowlist of local commands only.
    It does not call networks, LLMs, connectors, deploys, or secrets.
    """
    if profile not in QUALITY_PROFILES:
        raise ValueError(f"Unknown quality profile: {profile}")

    commands: list[list[str]] = [["python", "-m", "pytest", "-q"]]

    if profile == "fast":
        return commands

    optional_standard = [
        ("scripts/dev/audit_pmo_status.py",),
        ("scripts/dev/check_requirement_triage.py",),
        ("scripts/dev/check_triage_candidates.py",),
        ("scripts/dev/check_evergreen_assurance.py",),
        ("scripts/dev/check_kpi_measurement.py",),
        ("scripts/dev/check_adoption_pack.py",),
        ("scripts/dev/check_authoring_assistant_roadmap.py",),
        ("scripts/dev/check_product_lifecycle.py",),
        ("scripts/dev/check_handover_controls.py",),
        ("scripts/dev/check_regulated_controls.py",),
        ("scripts/release/check_release_readiness.py",),
        ("scripts/release/check_rc_stabilization.py",),
        ("scripts/release/check_stable_language.py",),
    ]
    for item in optional_standard:
        command = _script_command(repo_root, item[0], *item[1:])
        if command:
            commands.append(command)

    if profile in {"release", "regulated"}:
        optional_release = [
            ("scripts/dev/check_generated_drift.py",),
            ("scripts/dev/run_kpi_benchmark.py", "--no-write"),
        ]
        for item in optional_release:
            command = _script_command(repo_root, item[0], *item[1:])
            if command:
                commands.append(command)

    return commands
