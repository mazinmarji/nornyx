"""KPI measurement and evidence scoring helpers for Nornyx.

These helpers are local/read-only. They do not call LLMs, connectors,
networks, GitHub, deployment tools, or production systems.
"""
from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any
import json
import time


@dataclass(frozen=True)
class EvidenceRule:
    pattern: str
    points: int
    description: str


@dataclass(frozen=True)
class KpiIssue:
    severity: str
    message: str


DEFAULT_EVIDENCE_RULES: tuple[EvidenceRule, ...] = (
    EvidenceRule("patch.diff", 20, "Patch/diff is present"),
    EvidenceRule("changed_files.txt", 15, "Changed files list is present"),
    EvidenceRule("test_output.txt", 20, "Test output is present"),
    EvidenceRule("risk_note.md", 15, "Risk note is present"),
    EvidenceRule("handoff.md", 10, "Handoff note is present"),
    EvidenceRule("README.md", 10, "Evidence README is present"),
    EvidenceRule("*.json", 10, "Machine-readable report is present"),
)
REQUIRED_REPO_KPI_FIELDS = {
    "goals_count",
    "evidence_goal_dirs_count",
    "triage_candidate_count",
    "nyx_example_count",
    "test_file_count",
    "dev_check_script_count",
    "has_run_quality",
    "agentic_dev_readiness_score",
    "agentic_dev_readiness_max",
    "agentic_dev_readiness_status",
}
REQUIRED_EVIDENCE_FIELDS = {
    "evidence_dir",
    "exists",
    "score",
    "max_score",
    "percent",
    "status",
    "files",
    "present",
    "missing",
}


def _relative_files(root: Path) -> list[str]:
    if not root.exists() or not root.is_dir():
        return []
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    )


def score_evidence_dir(evidence_dir: Path, rules: tuple[EvidenceRule, ...] = DEFAULT_EVIDENCE_RULES) -> dict[str, Any]:
    """Score an evidence directory against a small deterministic checklist."""
    files = _relative_files(evidence_dir)
    present: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    score = 0
    max_score = sum(rule.points for rule in rules)

    for rule in rules:
        matched = any(fnmatch(path, rule.pattern) or fnmatch(Path(path).name, rule.pattern) for path in files)
        entry = {
            "pattern": rule.pattern,
            "points": rule.points,
            "description": rule.description,
        }
        if matched:
            score += rule.points
            present.append(entry)
        else:
            missing.append(entry)

    percent = round((score / max_score) * 100, 2) if max_score else 100.0
    if percent >= 90:
        status = "complete"
    elif percent >= 75:
        status = "reviewable"
    elif percent >= 50:
        status = "weak"
    else:
        status = "incomplete"

    return {
        "evidence_dir": str(evidence_dir),
        "exists": evidence_dir.exists(),
        "score": score,
        "max_score": max_score,
        "percent": percent,
        "status": status,
        "files": files,
        "present": present,
        "missing": missing,
    }


def _count_glob(root: Path, pattern: str) -> int:
    return sum(1 for path in root.glob(pattern) if path.is_file())


def _count_dirs(root: Path, pattern: str) -> int:
    return sum(1 for path in root.glob(pattern) if path.is_dir())


def collect_repo_kpis(repo_root: Path) -> dict[str, Any]:
    """Collect local repo-health KPIs useful for agentic development."""
    docs_goals = repo_root / "docs" / "goals"
    evidence_root = repo_root / "docs" / "qa" / "evidence"
    triage_root = repo_root / "docs" / "backlog" / "triage-candidates"
    scripts_dev = repo_root / "scripts" / "dev"

    metrics = {
        "goals_count": _count_glob(docs_goals, "*.md") if docs_goals.exists() else 0,
        "evidence_goal_dirs_count": _count_dirs(evidence_root, "GOAL-*") if evidence_root.exists() else 0,
        "triage_candidate_count": (
            _count_glob(triage_root, "*.yaml")
            + _count_glob(triage_root, "*.yml")
            + _count_glob(triage_root, "*.json")
            if triage_root.exists()
            else 0
        ),
        "nyx_example_count": _count_glob(repo_root / "examples", "*.nyx") if (repo_root / "examples").exists() else 0,
        "test_file_count": _count_glob(repo_root / "tests", "test_*.py") if (repo_root / "tests").exists() else 0,
        "dev_check_script_count": _count_glob(scripts_dev, "check_*.py") if scripts_dev.exists() else 0,
        "has_run_quality": (scripts_dev / "run_quality.py").exists(),
    }

    readiness_score = 0
    readiness_score += 15 if metrics["goals_count"] > 0 else 0
    readiness_score += 15 if metrics["evidence_goal_dirs_count"] > 0 else 0
    readiness_score += 10 if triage_root.exists() else 0
    readiness_score += 15 if metrics["nyx_example_count"] > 0 else 0
    readiness_score += 20 if metrics["test_file_count"] > 0 else 0
    readiness_score += 10 if metrics["dev_check_script_count"] > 0 else 0
    readiness_score += 15 if metrics["has_run_quality"] else 0

    metrics["agentic_dev_readiness_score"] = readiness_score
    metrics["agentic_dev_readiness_max"] = 100
    if readiness_score >= 85:
        metrics["agentic_dev_readiness_status"] = "strong"
    elif readiness_score >= 65:
        metrics["agentic_dev_readiness_status"] = "usable"
    elif readiness_score >= 40:
        metrics["agentic_dev_readiness_status"] = "weak"
    else:
        metrics["agentic_dev_readiness_status"] = "immature"

    return metrics


def build_kpi_result(repo_root: Path, *, evidence_dir: Path | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at_epoch": int(time.time()),
        "repo_root": str(repo_root),
        "repo_kpis": collect_repo_kpis(repo_root),
    }
    if evidence_dir is not None:
        result["evidence_score"] = score_evidence_dir(evidence_dir)
    return result


def validate_kpi_result(
    result: dict[str, Any],
    *,
    min_readiness_score: int = 85,
    min_evidence_percent: float = 75.0,
) -> list[KpiIssue]:
    """Validate that a KPI result is reviewable enough to guide local work."""
    issues: list[KpiIssue] = []

    if result.get("schema_version") != "1.0":
        issues.append(KpiIssue("error", "schema_version must be 1.0"))

    repo_kpis = result.get("repo_kpis")
    if not isinstance(repo_kpis, dict):
        issues.append(KpiIssue("error", "repo_kpis must be an object"))
    else:
        missing = sorted(REQUIRED_REPO_KPI_FIELDS - set(repo_kpis))
        if missing:
            issues.append(KpiIssue("error", f"repo_kpis missing fields: {missing}"))

        score = repo_kpis.get("agentic_dev_readiness_score")
        max_score = repo_kpis.get("agentic_dev_readiness_max")
        if not isinstance(score, int) or not isinstance(max_score, int):
            issues.append(KpiIssue("error", "readiness score and max must be integers"))
        elif score < min_readiness_score:
            issues.append(KpiIssue("error", f"readiness score {score}/{max_score} is below {min_readiness_score}"))

    evidence = result.get("evidence_score")
    if evidence is None:
        issues.append(KpiIssue("warning", "evidence_score is not present"))
    elif not isinstance(evidence, dict):
        issues.append(KpiIssue("error", "evidence_score must be an object"))
    else:
        missing = sorted(REQUIRED_EVIDENCE_FIELDS - set(evidence))
        if missing:
            issues.append(KpiIssue("error", f"evidence_score missing fields: {missing}"))

        if evidence.get("exists") is not True:
            issues.append(KpiIssue("error", "evidence directory must exist"))

        percent = evidence.get("percent")
        if not isinstance(percent, int | float):
            issues.append(KpiIssue("error", "evidence percent must be numeric"))
        elif float(percent) < min_evidence_percent:
            issues.append(KpiIssue("error", f"evidence score {percent}% is below {min_evidence_percent}%"))

    return issues


def kpi_summary(result: dict[str, Any]) -> str:
    repo_kpis = result.get("repo_kpis", {})
    evidence = result.get("evidence_score", {})
    readiness = "unknown"
    evidence_status = "not_scored"
    if isinstance(repo_kpis, dict):
        readiness = (
            f"{repo_kpis.get('agentic_dev_readiness_score', '?')}/"
            f"{repo_kpis.get('agentic_dev_readiness_max', '?')}"
            f" {repo_kpis.get('agentic_dev_readiness_status', 'unknown')}"
        )
    if isinstance(evidence, dict):
        evidence_status = f"{evidence.get('percent', '?')}% {evidence.get('status', 'unknown')}"
    return f"repo_readiness={readiness} | evidence={evidence_status}"


def write_kpi_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
