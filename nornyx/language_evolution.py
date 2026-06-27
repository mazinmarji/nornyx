"""Research-only language evolution helpers for Nornyx.

This module produces local research metadata only. It does not change parser
or checker behavior, add execution backends, enable connectors, call networks,
load secrets, or approve public syntax.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .checker import CORE_TOP_LEVEL_BLOCKS, EXTENSION_TOP_LEVEL_BLOCKS


RESEARCH_STATUS = "research_only_pending_approval"

MANDATORY_BOUNDARIES = [
    "v0.1 remains a YAML-compatible AI engineering control-plane language",
    "future syntax stays proposal-only until a dedicated goal and approval",
    "no production deployment behavior",
    "no arbitrary command execution",
    "no secret handling",
    "no dependency addition",
    "no connector enablement",
    "no security-model change without explicit approval",
]

APPROVAL_REQUIRED_BEFORE = [
    "public syntax change",
    "parser or checker semantic change",
    "runtime execution expansion",
    "native backend implementation",
    "dependency addition",
    "connector enablement",
    "security-model change",
    "release, tag, or public announcement",
]

LANGUAGE_EVOLUTION_TRACKS = [
    {
        "id": "semantic_core",
        "title": "Semantic core and typed block model",
        "research_question": (
            "How should existing control-plane blocks become more precise without "
            "breaking v0.1 YAML-compatible documents?"
        ),
        "candidate_constructs": [
            "typed block schemas",
            "named reference kinds",
            "contract signatures for agents, skills, policies, harnesses, and evals",
            "schema migration metadata",
        ],
        "promotion_gate": "RFC plus checker tests proving v0.1 compatibility",
        "status": "research",
    },
    {
        "id": "type_effect_system",
        "title": "Type and effect system",
        "research_question": (
            "Which capability, evidence, approval, taint, budget, and connector effects "
            "must be checkable before any runtime action is planned?"
        ),
        "candidate_constructs": [
            "capability effects",
            "approval effects",
            "evidence obligations",
            "context taint labels",
            "budget effects",
            "connector boundary effects",
        ],
        "promotion_gate": "formal effect table plus negative tests for unsafe plans",
        "status": "research",
    },
    {
        "id": "workflow_constructs",
        "title": "Workflow programming constructs",
        "research_question": (
            "Which harness-level control-flow constructs are native to governed "
            "human-AI engineering without becoming a general-purpose runtime?"
        ),
        "candidate_constructs": [
            "bounded retry blocks",
            "repair loops with attempt limits",
            "approval branches",
            "evidence checkpoints",
            "failure handlers",
            "eval gates",
        ],
        "promotion_gate": "harness semantics spec plus trace/evidence compatibility tests",
        "status": "research",
    },
    {
        "id": "native_backends",
        "title": "Native backend research",
        "research_question": (
            "Which backends should Nornyx generate or target while preserving existing "
            "tools as the execution surface?"
        ),
        "candidate_constructs": [
            "JSON schema export",
            "LSP and Tree-sitter metadata",
            "OpenTelemetry-compatible trace export",
            "MCP/A2A connector manifests",
            "policy/eval/evidence reports",
            "optional domain-specific runners after approval",
        ],
        "promotion_gate": "backend decision record plus local-only adapter safety tests",
        "status": "research",
    },
]


def _track_ids(tracks: list[dict[str, Any]]) -> set[str]:
    return {str(track.get("id", "")) for track in tracks}


def validate_language_evolution_report(report: dict[str, Any]) -> list[dict[str, str]]:
    """Return blocking research-contract issues for a language evolution report."""
    issues: list[dict[str, str]] = []
    required = {"semantic_core", "type_effect_system", "workflow_constructs", "native_backends"}
    missing = sorted(required - _track_ids(report.get("tracks", []) or []))
    if missing:
        issues.append(
            {
                "severity": "error",
                "message": f"missing required research tracks: {missing}",
            }
        )

    for track in report.get("tracks", []) or []:
        if track.get("status") != "research":
            issues.append(
                {
                    "severity": "error",
                    "message": f"{track.get('id', '<unknown>')} must remain research status",
                }
            )
        if not track.get("promotion_gate"):
            issues.append(
                {
                    "severity": "error",
                    "message": f"{track.get('id', '<unknown>')} is missing a promotion gate",
                }
            )

    safety = report.get("safety", {})
    for flag, value in safety.items():
        if flag.startswith("requires_"):
            continue
        if value is not False:
            issues.append(
                {
                    "severity": "error",
                    "message": f"safety flag {flag} must be false for research-only output",
                }
            )

    if report.get("status") != RESEARCH_STATUS:
        issues.append({"severity": "error", "message": "report status must remain research-only"})

    return issues


def build_language_evolution_report(repo_root: str | Path = ".") -> dict[str, Any]:
    repo = Path(repo_root)
    docs = [
        "docs/01_LANGUAGE_SPEC_v0_1.md",
        "docs/16_FINAL_LANGUAGE_TARGET.md",
        "docs/23_DISTINCT_LANGUAGE_STRATEGY.md",
        "docs/RFCs/RFC-0003-full-language-evolution-research.md",
        "docs/goals/goal-013-full-language-evolution-research.md",
    ]
    missing_docs = [path for path in docs if not (repo / path).exists()]
    report = {
        "schema": "nornyx.language_evolution_research.v0.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": RESEARCH_STATUS,
        "current_language_version": "0.1",
        "current_surface": {
            "syntax": "yaml-compatible",
            "core_top_level_blocks": CORE_TOP_LEVEL_BLOCKS,
            "deferred_extension_blocks": EXTENSION_TOP_LEVEL_BLOCKS,
        },
        "tracks": copy.deepcopy(LANGUAGE_EVOLUTION_TRACKS),
        "mandatory_boundaries": MANDATORY_BOUNDARIES,
        "approval_required_before": APPROVAL_REQUIRED_BEFORE,
        "references": docs,
        "missing_references": missing_docs,
        "safety": {
            "parser_changed": False,
            "checker_semantics_changed": False,
            "runtime_execution_added": False,
            "native_backend_implemented": False,
            "public_syntax_changed": False,
            "dependencies_added": False,
            "connectors_enabled": False,
            "network_used": False,
            "production_deploy_behavior": False,
            "requires_human_approval_for_promotion": True,
        },
        "recommended_next_goal": "GOAL-014 - Distinct language developer experience",
    }
    report["issues"] = validate_language_evolution_report(report)
    report["summary"] = {
        "track_count": len(report["tracks"]),
        "blocking_issues": sum(1 for issue in report["issues"] if issue["severity"] == "error"),
        "missing_references": len(missing_docs),
        "approval_gates": len(APPROVAL_REQUIRED_BEFORE),
    }
    return report


def write_language_evolution_report(report: dict[str, Any], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return output
