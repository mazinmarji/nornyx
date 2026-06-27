from __future__ import annotations

import json
from pathlib import Path

import yaml

from nornyx.regulated_controls import (
    ALLOWED_QUALITY_FLAGS,
    decision_boundary_summary,
    evidence_quality_summary,
    regulated_control_pack_summary,
    validate_decision_boundary,
    validate_evidence_quality,
    validate_regulated_control_pack,
)


def valid_boundary() -> dict:
    return {
        "name": "ShipmentDisposition",
        "ai_allowed": ["propose_risk_score", "explain_anomaly"],
        "ai_denied": ["approve_disposal", "release_blocked_shipment"],
        "human_owner": "ComplianceOwner",
        "approval_required": True,
        "evidence_required": ["ai_recommendation", "human_approval", "timestamp"],
    }


def valid_evidence_quality() -> dict:
    return {
        "name": "ColdGuardAuditEvidence",
        "required": ["telemetry_snapshot", "human_approval"],
        "quality": [
            "immutable_timestamp",
            "source_hash",
            "approver_identity",
            "retention_policy",
            "decision_reason",
        ],
        "retention": "2 years",
        "export": {"formats": ["json", "pdf"], "redaction_required": True},
    }


def test_valid_decision_boundary_has_no_errors() -> None:
    issues = validate_decision_boundary(valid_boundary())
    assert not any(issue.severity == "error" for issue in issues)


def test_decision_boundary_rejects_allowed_denied_overlap() -> None:
    data = valid_boundary()
    data["ai_denied"] = ["propose_risk_score"]
    issues = validate_decision_boundary(data)
    assert any("both allowed and denied" in issue.message for issue in issues)


def test_decision_boundary_requires_evidence_when_approval_required() -> None:
    data = valid_boundary()
    data["evidence_required"] = []
    issues = validate_decision_boundary(data)
    assert any("requires evidence_required" in issue.message for issue in issues)


def test_valid_evidence_quality_has_no_errors() -> None:
    issues = validate_evidence_quality(valid_evidence_quality())
    assert not any(issue.severity == "error" for issue in issues)


def test_evidence_quality_requires_retention_when_flagged() -> None:
    data = valid_evidence_quality()
    data["retention"] = ""
    issues = validate_evidence_quality(data)
    assert any("requires retention" in issue.message for issue in issues)


def test_evidence_quality_warns_when_audit_flags_missing() -> None:
    data = valid_evidence_quality()
    data["quality"] = ["decision_reason"]
    issues = validate_evidence_quality(data)
    assert any(issue.severity == "warning" for issue in issues)


def test_summaries() -> None:
    assert "ShipmentDisposition" in decision_boundary_summary(valid_boundary())
    assert "ColdGuardAuditEvidence" in evidence_quality_summary(valid_evidence_quality())


def test_regulated_control_pack_links_decision_evidence_to_quality_contract() -> None:
    pack = {
        "decision_boundaries": [valid_boundary()],
        "evidence_quality": [
            {
                **valid_evidence_quality(),
                "required": ["ai_recommendation", "human_approval", "timestamp"],
            }
        ],
        "safety": {
            "automatic_approval": False,
            "connector_calls": False,
            "llm_calls": False,
            "deployment_actions": False,
            "production_writes": False,
        },
    }

    issues = validate_regulated_control_pack(pack)

    assert not any(issue.severity == "error" for issue in issues)


def test_regulated_control_pack_blocks_missing_evidence_quality_coverage() -> None:
    pack = {
        "decision_boundaries": [valid_boundary()],
        "evidence_quality": [{**valid_evidence_quality(), "required": ["telemetry_snapshot"]}],
    }

    issues = validate_regulated_control_pack(pack)

    assert any("not covered" in issue.message for issue in issues)


def test_regulated_control_pack_blocks_unsafe_safety_flags() -> None:
    pack = {
        "decision_boundaries": [valid_boundary()],
        "evidence_quality": [
            {
                **valid_evidence_quality(),
                "required": ["ai_recommendation", "human_approval", "timestamp"],
            }
        ],
        "safety": {"automatic_approval": True},
    }

    issues = validate_regulated_control_pack(pack)

    assert any("automatic_approval" in issue.message for issue in issues)


def test_backlog_regulated_control_yaml_is_valid() -> None:
    data = yaml.safe_load(
        Path("docs/backlog/nornyx-decision-boundary-evidence-quality.yaml").read_text()
    )

    issues = validate_regulated_control_pack(data)

    assert not any(issue.severity == "error" for issue in issues)
    assert data["safety"]["automatic_approval"] is False
    assert data["safety"]["production_writes"] is False
    assert data["promotion"]["decision_boundary"] == "regulated_enterprise_candidate"
    assert "decision_boundaries=1" in regulated_control_pack_summary(data)


def test_schema_quality_flags_match_validator_constants() -> None:
    schema = json.loads(Path("schemas/evidence_quality.schema.json").read_text())

    assert set(schema["properties"]["quality"]["items"]["enum"]) == ALLOWED_QUALITY_FLAGS
