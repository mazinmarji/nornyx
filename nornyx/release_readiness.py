from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dev_quality import audit_pmo_status, load_json


REQUIRED_RELEASE_DOCS = [
    "README.md",
    "docs/01_LANGUAGE_SPEC_v0_1.md",
    "docs/05_SECURITY_MODEL.md",
    "docs/07_HARNESS_ENGINEERING.md",
    "docs/08_EVALS_AND_GUARDRAILS.md",
    "docs/10_EXTENSION_PROTOCOLS_MCP_A2A.md",
    "docs/11_OBSERVABILITY_EVIDENCE.md",
    "docs/tooling/26_TOOLING_ROADMAP_LSP_TREESITTER.md",
    "docs/releases/RELEASE_CANDIDATE_v1_0.md",
    "schemas/nornyx_v0_1.schema.json",
    "schemas/connector_manifest.schema.json",
    "examples/governed_delivery_control_plane.nyx",
    "examples/nornyx_roadmap_goals.nyx",
]
REQUIRED_RC_STABILIZATION_DOCS = [
    "docs/40_NORNYX_DOMAIN_PROFILES_v0_3.md",
    "docs/41_NORNYX_ADAPTER_CONTRACTS_v0_4.md",
    "docs/42_NORNYX_GRAPH_VALIDATION_v0_5.md",
    "docs/43_NORNYX_PROFILE_CONFORMANCE_v0_6.md",
    "docs/44_NORNYX_ADAPTER_CONFORMANCE_v0_7.md",
    "docs/45_NORNYX_BOUNDED_EXECUTION_READINESS_v0_8.md",
    "docs/46_NORNYX_RELEASE_CANDIDATE_STABILIZATION_v0_9.md",
]
REQUIRED_RC_SCHEMAS = [
    "schemas/domain_profile_pack.schema.json",
    "schemas/adapter_contract.schema.json",
    "schemas/adapter_conformance_report.schema.json",
    "schemas/connector_contract_conformance.schema.json",
    "schemas/bounded_execution_readiness.schema.json",
]
REQUIRED_RC_EXAMPLES = [
    "examples/nornyx_v04_adapter_contracts.nyx",
]
REQUIRED_V1_STABLE_DOCS = [
    *REQUIRED_RC_STABILIZATION_DOCS,
    "docs/47_NORNYX_STABLE_GENERALIZED_CONTRACT_LANGUAGE_v1_0.md",
    "docs/releases/RELEASE_CANDIDATE_v1_0.md",
]
REQUIRED_V1_STABLE_SCHEMAS = [
    *REQUIRED_RC_SCHEMAS,
    "schemas/release_candidate_stabilization.schema.json",
    "schemas/stable_language_report.schema.json",
]
REQUIRED_COMPLETED_GOALS = [f"GOAL-{index:03d}" for index in range(0, 12)]
REQUIRED_STRATEGIC_GOALS = [f"GOAL-{index:03d}" for index in range(33, 41)]
REQUIRED_V1_STABLE_GOALS = [f"GOAL-{index:03d}" for index in range(33, 43)]
REQUIRED_VALIDATION_COMMANDS = [
    "python -m pytest -q",
    "python -m nornyx.cli check examples/governed_delivery_control_plane.nyx",
    "python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx",
]
REQUIRED_RC_VALIDATION_COMMANDS = [
    *REQUIRED_VALIDATION_COMMANDS,
    "python -m nornyx.cli check examples/nornyx_v04_adapter_contracts.nyx",
    "python -m nornyx.cli release-check --out generated/release_readiness_v0_9.json",
    "python scripts/dev/audit_pmo_status.py",
]
REQUIRED_V1_STABLE_VALIDATION_COMMANDS = [
    *REQUIRED_RC_VALIDATION_COMMANDS,
    "python scripts/release/check_rc_stabilization.py",
    "python scripts/release/check_stable_language.py",
]
STABLE_CORE_CONCEPTS = [
    "Intent",
    "Agent",
    "Policy",
    "Eval",
    "Approval",
    "Evidence",
    "Context",
    "Artifact",
    "Graph",
    "Goal",
    "Budget",
    "Trace",
]
STABLE_V1_NON_GOALS = [
    "full autonomous runtime",
    "general-purpose programming language",
    "production execution engine",
    "unrestricted connector runtime",
    "automatic approvals",
    "self-modification",
    "regulated or enterprise GOAL-100 promotion",
]
NO_GO_CONDITIONS = [
    "failing tests",
    "inconsistent PMO status",
    "missing evidence",
    "unapproved release/tag/public announcement",
    "secret exposure",
    "live connector execution",
    "production deployment behavior",
]


def _version_from_pyproject(repo_root: Path) -> str:
    text = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*["\']([^"\']+)["\']', text)
    return match.group(1) if match else ""


def _version_from_init(repo_root: Path) -> str:
    text = (repo_root / "nornyx" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    return match.group(1) if match else ""


def _check(check_id: str, status: str, message: str, **extra: Any) -> dict[str, Any]:
    payload = {"id": check_id, "status": status, "message": message}
    payload.update(extra)
    return payload


def _goal_ids_from_status(status_doc: dict[str, Any]) -> set[str]:
    ids = set()
    for block in status_doc.get("blocks", []) or []:
        if not isinstance(block, dict):
            continue
        title = str(block.get("title", ""))
        match = re.search(r"GOAL-\d{3}", title)
        if match and block.get("status") == "completed":
            ids.add(match.group(0))
    return ids


def _block_by_goal_id(status_doc: dict[str, Any], goal_id: str) -> dict[str, Any] | None:
    for block in status_doc.get("blocks", []) or []:
        if not isinstance(block, dict):
            continue
        title = str(block.get("title", ""))
        if goal_id in title:
            return block
    return None


def _evidence_goal_ids(repo_root: Path) -> set[str]:
    evidence_root = repo_root / "docs" / "qa" / "evidence"
    if not evidence_root.exists():
        return set()
    return {path.name for path in evidence_root.glob("GOAL-*") if path.is_dir()}


def _summarize_checks(checks: list[dict[str, Any]]) -> dict[str, int]:
    statuses = {"passed": 0, "warning": 0, "blocked": 0, "requires_human_approval": 0}
    for check in checks:
        status = str(check.get("status", "warning"))
        if status in statuses:
            statuses[status] += 1
    return statuses


def build_release_readiness_report(
    repo_root: str | Path = ".",
    *,
    target_version: str = "1.0.0",
    approved: bool = False,
) -> dict[str, Any]:
    repo = Path(repo_root)
    checks: list[dict[str, Any]] = []

    pyproject_version = _version_from_pyproject(repo)
    init_version = _version_from_init(repo)
    checks.append(
        _check(
            "package_version_consistent",
            "passed" if pyproject_version and pyproject_version == init_version else "blocked",
            "Package versions match." if pyproject_version == init_version else "Package versions differ.",
            pyproject_version=pyproject_version,
            package_version=init_version,
        )
    )
    checks.append(
        _check(
            "target_version_recorded",
            "warning" if target_version != pyproject_version else "passed",
            "Target version is recorded for release-candidate review; package version is not changed without approval."
            if target_version != pyproject_version
            else "Target version matches current package version.",
            target_version=target_version,
            current_version=pyproject_version,
        )
    )

    missing_docs = [path for path in REQUIRED_RELEASE_DOCS if not (repo / path).exists()]
    checks.append(
        _check(
            "release_docs_present",
            "passed" if not missing_docs else "blocked",
            "Required release docs and examples are present."
            if not missing_docs
            else "Required release docs or examples are missing.",
            missing=missing_docs,
        )
    )

    status_path = repo / "docs" / "pmo" / "status" / "current_status.json"
    if status_path.exists():
        status_doc = load_json(status_path)
        pmo_errors = [issue for issue in audit_pmo_status(status_doc) if issue.severity == "error"]
        checks.append(
            _check(
                "pmo_status_consistent",
                "passed" if not pmo_errors else "blocked",
                "PMO status is internally consistent."
                if not pmo_errors
                else "PMO status has blocking consistency errors.",
                errors=[issue.__dict__ for issue in pmo_errors],
            )
        )
        completed = _goal_ids_from_status(status_doc)
    else:
        checks.append(
            _check(
                "pmo_status_consistent",
                "blocked",
                "PMO status file is missing.",
                path=str(status_path),
            )
        )
        completed = set()

    missing_completed = [goal_id for goal_id in REQUIRED_COMPLETED_GOALS if goal_id not in completed]
    checks.append(
        _check(
            "core_goal_sequence_completed",
            "passed" if not missing_completed else "blocked",
            "GOAL-000 through GOAL-011 are completed in PMO status."
            if not missing_completed
            else "Core release goal sequence is not fully completed in PMO status.",
            missing=missing_completed,
        )
    )

    evidence_ids = _evidence_goal_ids(repo)
    missing_evidence = [goal_id for goal_id in REQUIRED_COMPLETED_GOALS if goal_id not in evidence_ids]
    checks.append(
        _check(
            "core_goal_evidence_present",
            "passed" if not missing_evidence else "blocked",
            "GOAL-000 through GOAL-011 evidence directories are present."
            if not missing_evidence
            else "Core release goal evidence directories are missing.",
            missing=missing_evidence,
        )
    )

    checks.append(
        _check(
            "validation_commands_declared",
            "passed",
            "Release validation commands are declared for local execution.",
            commands=REQUIRED_VALIDATION_COMMANDS,
        )
    )
    checks.append(
        _check(
            "no_go_conditions_recorded",
            "passed",
            "Release no-go conditions are recorded.",
            conditions=NO_GO_CONDITIONS,
        )
    )
    checks.append(
        _check(
            "human_release_approval",
            "passed" if approved else "requires_human_approval",
            "Human release approval is recorded."
            if approved
            else "Release/tag/public announcement remains blocked until human approval.",
        )
    )

    summary = _summarize_checks(checks)
    if summary["blocked"]:
        status = "blocked"
    elif summary["requires_human_approval"]:
        status = "release_candidate_ready_pending_approval"
    else:
        status = "ready_for_release"

    return {
        "schema": "nornyx.release_readiness.v0.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target_version": target_version,
        "status": status,
        "summary": summary,
        "checks": checks,
        "required_validation": REQUIRED_VALIDATION_COMMANDS,
        "no_go_conditions": NO_GO_CONDITIONS,
        "safety": {
            "published": False,
            "tag_created": False,
            "pushed_to_remote": False,
            "package_version_changed": False,
            "connectors_enabled": False,
            "network_used": False,
            "requires_human_release_approval": not approved,
        },
    }


def build_release_candidate_stabilization_report(
    repo_root: str | Path = ".",
    *,
    target_version: str = "1.0.0",
    approved: bool = False,
) -> dict[str, Any]:
    repo = Path(repo_root)
    base_report = build_release_readiness_report(
        repo,
        target_version=target_version,
        approved=approved,
    )
    checks: list[dict[str, Any]] = []

    missing_docs = [
        path
        for path in [*REQUIRED_RC_STABILIZATION_DOCS, *REQUIRED_RC_SCHEMAS, *REQUIRED_RC_EXAMPLES]
        if not (repo / path).exists()
    ]
    checks.append(
        _check(
            "v09_docs_schemas_examples_present",
            "passed" if not missing_docs else "blocked",
            "v0.3-v0.8 stabilization docs, schemas, and examples are present."
            if not missing_docs
            else "v0.3-v0.8 stabilization docs, schemas, or examples are missing.",
            missing=missing_docs,
        )
    )

    status_path = repo / "docs" / "pmo" / "status" / "current_status.json"
    status_doc: dict[str, Any] = {}
    if status_path.exists():
        status_doc = load_json(status_path)
        completed = _goal_ids_from_status(status_doc)
    else:
        completed = set()

    missing_strategic = [goal_id for goal_id in REQUIRED_STRATEGIC_GOALS if goal_id not in completed]
    checks.append(
        _check(
            "strategic_maturity_goals_completed",
            "passed" if not missing_strategic else "blocked",
            "GOAL-033 through GOAL-040 are completed in PMO status."
            if not missing_strategic
            else "Strategic maturity goals are incomplete in PMO status.",
            missing=missing_strategic,
        )
    )

    evidence_ids = _evidence_goal_ids(repo)
    missing_evidence = [goal_id for goal_id in REQUIRED_STRATEGIC_GOALS if goal_id not in evidence_ids]
    checks.append(
        _check(
            "strategic_maturity_evidence_present",
            "passed" if not missing_evidence else "blocked",
            "GOAL-033 through GOAL-040 evidence directories are present."
            if not missing_evidence
            else "Strategic maturity evidence directories are missing.",
            missing=missing_evidence,
        )
    )

    goal_042 = _block_by_goal_id(status_doc, "GOAL-042")
    locked_100 = _block_by_goal_id(status_doc, "GOAL-100")
    goal_042_status = goal_042.get("status") if goal_042 else None
    goal_042_boundary_ok = goal_042_status == "locked" or (
        goal_042_status == "completed" and (repo / "docs" / "qa" / "evidence" / "GOAL-042").exists()
    )
    goal_100_locked = bool(locked_100 and locked_100.get("status") == "locked")
    checks.append(
        _check(
            "release_boundary_preserved",
            "passed" if goal_042_boundary_ok and goal_100_locked else "blocked",
            "GOAL-042 is either locked or locally completed with evidence, and GOAL-100 remains locked."
            if goal_042_boundary_ok and goal_100_locked
            else "Release boundary is not preserved.",
            goal_042_status=goal_042_status,
            goal_100_status=locked_100.get("status") if locked_100 else None,
        )
    )

    checks.append(
        _check(
            "rc_validation_commands_declared",
            "passed",
            "Release-candidate validation commands are declared.",
            commands=REQUIRED_RC_VALIDATION_COMMANDS,
        )
    )
    checks.append(
        _check(
            "rc_human_approval",
            "passed" if approved else "requires_human_approval",
            "Human release-candidate approval is recorded."
            if approved
            else "Release candidate remains pending human approval; no tag, publish, or announcement is allowed.",
        )
    )

    all_checks = [*base_report["checks"], *checks]
    summary = _summarize_checks(all_checks)
    if summary["blocked"]:
        status = "blocked"
    elif summary["requires_human_approval"]:
        status = "release_candidate_stabilized_pending_approval"
    else:
        status = "release_candidate_stabilized_approved"

    return {
        "schema": "nornyx.release_candidate_stabilization.v0.9",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target_version": target_version,
        "status": status,
        "summary": summary,
        "base_release_readiness": base_report,
        "checks": all_checks,
        "required_validation": REQUIRED_RC_VALIDATION_COMMANDS,
        "no_go_conditions": NO_GO_CONDITIONS,
        "safety": {
            "published": False,
            "tag_created": False,
            "pushed_to_remote": False,
            "package_version_changed": False,
            "connectors_enabled": False,
            "network_used": False,
            "release_claim_made": False,
            "goal_042_completed_local": goal_042_status == "completed",
            "goal_100_unlocked": False,
            "requires_human_release_approval": not approved,
        },
    }


def build_stable_language_report(
    repo_root: str | Path = ".",
    *,
    target_version: str = "1.0.0",
    approved: bool = False,
) -> dict[str, Any]:
    repo = Path(repo_root)
    base_report = build_release_candidate_stabilization_report(
        repo,
        target_version=target_version,
        approved=approved,
    )
    checks: list[dict[str, Any]] = []

    missing_docs = [path for path in REQUIRED_V1_STABLE_DOCS if not (repo / path).exists()]
    checks.append(
        _check(
            "v1_stable_docs_present",
            "passed" if not missing_docs else "blocked",
            "v1.0 stable-language docs are present."
            if not missing_docs
            else "v1.0 stable-language docs are missing.",
            missing=missing_docs,
        )
    )

    missing_schemas = [path for path in REQUIRED_V1_STABLE_SCHEMAS if not (repo / path).exists()]
    checks.append(
        _check(
            "v1_stable_schemas_present",
            "passed" if not missing_schemas else "blocked",
            "v1.0 stable-language schemas are present."
            if not missing_schemas
            else "v1.0 stable-language schemas are missing.",
            missing=missing_schemas,
        )
    )

    status_path = repo / "docs" / "pmo" / "status" / "current_status.json"
    status_doc: dict[str, Any] = {}
    if status_path.exists():
        status_doc = load_json(status_path)
        completed = _goal_ids_from_status(status_doc)
    else:
        completed = set()

    missing_goals = [goal_id for goal_id in REQUIRED_V1_STABLE_GOALS if goal_id not in completed]
    checks.append(
        _check(
            "v1_stable_goals_completed",
            "passed" if not missing_goals else "blocked",
            "GOAL-033 through GOAL-042 are completed in PMO status."
            if not missing_goals
            else "v1.0 stable-language goal sequence is incomplete in PMO status.",
            missing=missing_goals,
        )
    )

    evidence_ids = _evidence_goal_ids(repo)
    missing_evidence = [goal_id for goal_id in REQUIRED_V1_STABLE_GOALS if goal_id not in evidence_ids]
    checks.append(
        _check(
            "v1_stable_evidence_present",
            "passed" if not missing_evidence else "blocked",
            "GOAL-033 through GOAL-042 evidence directories are present."
            if not missing_evidence
            else "v1.0 stable-language evidence directories are missing.",
            missing=missing_evidence,
        )
    )

    goal_100 = _block_by_goal_id(status_doc, "GOAL-100")
    checks.append(
        _check(
            "goal_100_remains_locked",
            "passed" if goal_100 and goal_100.get("status") == "locked" else "blocked",
            "GOAL-100 remains locked; regulated and enterprise extensions are not promoted."
            if goal_100 and goal_100.get("status") == "locked"
            else "GOAL-100 is not locked.",
            goal_100_status=goal_100.get("status") if goal_100 else None,
        )
    )

    checks.append(
        _check(
            "stable_core_concepts_recorded",
            "passed",
            "Stable Nornyx core remains general around the contract-language concepts.",
            concepts=STABLE_CORE_CONCEPTS,
        )
    )
    checks.append(
        _check(
            "stable_v1_non_goals_recorded",
            "passed",
            "v1.0 non-goals preserve the boundary against runtime, deployment, and broad autonomy claims.",
            non_goals=STABLE_V1_NON_GOALS,
        )
    )
    checks.append(
        _check(
            "v1_validation_commands_declared",
            "passed",
            "v1.0 stable-language validation commands are declared.",
            commands=REQUIRED_V1_STABLE_VALIDATION_COMMANDS,
        )
    )
    checks.append(
        _check(
            "human_v1_release_approval",
            "passed" if approved else "requires_human_approval",
            "Human v1.0 release approval is recorded."
            if approved
            else "Local stable-language completion is recorded; public v1.0 release remains blocked until human approval.",
        )
    )

    all_checks = [*base_report["checks"], *checks]
    summary = _summarize_checks(all_checks)
    if summary["blocked"]:
        status = "blocked"
    elif summary["requires_human_approval"]:
        status = "stable_language_completed_local_pending_release_approval"
    else:
        status = "stable_language_approved_local"

    return {
        "schema": "nornyx.stable_language.v1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target_version": target_version,
        "status": status,
        "summary": summary,
        "base_release_candidate_stabilization": base_report,
        "checks": all_checks,
        "stable_core_concepts": STABLE_CORE_CONCEPTS,
        "stable_v1_non_goals": STABLE_V1_NON_GOALS,
        "required_validation": REQUIRED_V1_STABLE_VALIDATION_COMMANDS,
        "no_go_conditions": [*NO_GO_CONDITIONS, *STABLE_V1_NON_GOALS],
        "safety": {
            "published": False,
            "tag_created": False,
            "pushed_to_remote": False,
            "package_version_changed": False,
            "connectors_enabled": False,
            "network_used": False,
            "production_deployment": False,
            "general_purpose_language_claim": False,
            "full_autonomous_runtime_claim": False,
            "unrestricted_connector_runtime_claim": False,
            "goal_042_completed_local": "GOAL-042" in _goal_ids_from_status(status_doc),
            "goal_100_unlocked": False,
            "requires_human_release_approval": not approved,
        },
    }


def write_release_readiness_report(report: dict[str, Any], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return output
