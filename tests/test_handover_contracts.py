from __future__ import annotations

import json
from pathlib import Path

import yaml

from nornyx.handover import (
    ALLOWED_AMBIGUITY_KINDS,
    ALLOWED_RISKS,
    handover_ready,
    handover_pack_summary,
    handover_summary,
    validate_ambiguity_control,
    validate_handover_contract,
    validate_handover_pack,
)


def valid_handover() -> dict:
    return {
        "name": "ProductToNornyx",
        "from_state": "product_discovery",
        "to_state": "governed_development",
        "required": ["problem_statement", "personas", "acceptance_criteria"],
        "acceptance": ["all required artifacts present"],
        "approval": "ProductOwner",
        "evidence": "docs/qa/evidence/GOAL-023/",
        "blocking_open_questions": ["CitizenPhoneNumber"],
    }


def test_valid_handover_has_no_errors() -> None:
    issues = validate_handover_contract(valid_handover())
    assert not any(issue.severity == "error" for issue in issues)


def test_handover_requires_different_states() -> None:
    data = valid_handover()
    data["to_state"] = "product_discovery"
    issues = validate_handover_contract(data)
    assert any("must differ" in issue.message for issue in issues)


def test_handover_ready_requires_artifacts_and_resolved_questions() -> None:
    data = valid_handover()
    assert handover_ready(
        data,
        artifacts_present={"problem_statement", "personas", "acceptance_criteria"},
        unresolved_questions=set(),
    )

    assert not handover_ready(
        data,
        artifacts_present={"problem_statement"},
        unresolved_questions=set(),
    )

    assert not handover_ready(
        data,
        artifacts_present={"problem_statement", "personas", "acceptance_criteria"},
        unresolved_questions={"CitizenPhoneNumber"},
    )


def test_assumption_requires_can_proceed() -> None:
    issues = validate_ambiguity_control(
        {
            "kind": "assumption",
            "id": "WebFirstMVP",
            "text": "MVP supports web app only.",
            "owner": "ProductOwner",
        }
    )
    assert any("can_proceed" in issue.message for issue in issues)


def test_decision_needed_requires_required_before() -> None:
    issues = validate_ambiguity_control(
        {
            "kind": "decision_needed",
            "id": "AIVisibility",
            "text": "Should AI suggestions be external?",
            "owner": "ProductOwner",
        }
    )
    assert any("required_before" in issue.message for issue in issues)


def test_handover_summary() -> None:
    summary = handover_summary(valid_handover())
    assert "ProductToNornyx" in summary
    assert "product_discovery -> governed_development" in summary


def test_handover_pack_validates_cross_references() -> None:
    pack = {
        "handovers": [valid_handover()],
        "ambiguity_controls": [
            {
                "kind": "open_question",
                "id": "CitizenPhoneNumber",
                "text": "Should phone number be mandatory?",
                "owner": "ProductOwner",
            }
        ],
    }

    issues = validate_handover_pack(pack)

    assert not any(issue.severity == "error" for issue in issues)


def test_handover_pack_blocks_unknown_open_question_references() -> None:
    pack = {
        "handovers": [valid_handover()],
        "ambiguity_controls": [
            {
                "kind": "open_question",
                "id": "OtherQuestion",
                "text": "Different question.",
                "owner": "ProductOwner",
            }
        ],
    }

    issues = validate_handover_pack(pack)

    assert any("unknown blocking open questions" in issue.message for issue in issues)


def test_backlog_handover_yaml_is_valid() -> None:
    data = yaml.safe_load(Path("docs/backlog/nornyx-handover-and-ambiguity-controls.yaml").read_text())

    issues = validate_handover_pack(data)

    assert not any(issue.severity == "error" for issue in issues)
    assert data["safety"]["automatic_approval"] is False
    assert data["safety"]["connector_calls"] is False
    assert data["promotion"]["handover"] == "candidate_after_core_checker_maturity"
    assert "handovers=1" in handover_pack_summary(data)


def test_schema_enums_match_validator_constants() -> None:
    schema = json.loads(Path("schemas/ambiguity_control.schema.json").read_text())

    assert set(schema["properties"]["kind"]["enum"]) == ALLOWED_AMBIGUITY_KINDS
    assert set(schema["properties"]["risk"]["enum"]) == ALLOWED_RISKS
