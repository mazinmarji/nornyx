from __future__ import annotations

import json
from pathlib import Path

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "interop"
    / "dogwood_temporal_cross_step_v1.json"
)


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _comparison_by_semantic(data: dict[str, object]) -> dict[str, dict[str, object]]:
    rows = data["semantic_comparison"]
    assert isinstance(rows, list)
    return {
        row["semantic"]: row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("semantic"), str)
    }


def test_cross_step_fixture_pins_sources_and_closed_classification_vocabulary() -> None:
    data = _fixture()

    assert data["schema"] == "nornyx.interop.temporal_cross_step_fixture.v1"
    assert data["status"] == "specification_conformance_fixture"
    assert data["classification_vocabulary"] == [
        "EQUIVALENT",
        "COMPOSITE",
        "UNSUPPORTED",
    ]

    target = data["external_target"]
    assert isinstance(target, dict)
    assert target["dogwood_commit"] == "c6237c88099b3f492ecc5fcee42df06a19224b97"
    assert target["source_observed_at"] == "2026-08-24"

    baseline = data["nornyx_baseline"]
    assert isinstance(baseline, dict)
    assert baseline["commit"] == "8729b5bdf1740e656c2cd0c3a8a0a99454ed973a"


def test_cross_step_intent_is_composite_not_silently_equivalent() -> None:
    data = _fixture()
    scenario = data["scenario"]
    assert isinstance(scenario, dict)
    assert scenario["overall_classification"] == "COMPOSITE"
    assert scenario["authority_source"] == "nornyx_contract"
    assert (
        scenario["external_policy_role"]
        == "projection_and_enforcement_surface_not_independent_authority"
    )

    comparison = _comparison_by_semantic(data)
    assert comparison["recent_successful_run_tests"]["classification"] == "EQUIVALENT"
    assert comparison["human_approval_integrity"]["classification"] == "COMPOSITE"
    assert (
        comparison["nornyx_revision_and_evidence_binding"]["classification"]
        == "UNSUPPORTED"
    )


def test_plain_cedar_cannot_be_called_equivalent_without_temporal_monitor() -> None:
    data = _fixture()
    projection = data["plain_cedar_projection"]
    assert isinstance(projection, dict)

    assert projection["classification"] == "UNSUPPORTED"
    assert (
        projection["forbidden_claim"]
        == "plain_cedar_is_semantically_equivalent_to_full_temporal_policy"
    )


def test_cross_step_cases_pin_each_surface_decision_and_combined_outcome() -> None:
    data = _fixture()
    cases = data["decision_cases"]
    assert isinstance(cases, list)
    assert len(cases) == 5

    expected_cases = {
        "missing_tests_and_approval": {
            "fresh_successful_tests": False,
            "valid_revision_bound_human_approval": False,
            "external_temporal_decision": "DENY",
            "nornyx_decision": "APPROVAL_REQUIRED",
            "combined_decision": "DENY",
        },
        "fresh_tests_missing_approval": {
            "fresh_successful_tests": True,
            "valid_revision_bound_human_approval": False,
            "external_temporal_decision": "ALLOW",
            "nornyx_decision": "APPROVAL_REQUIRED",
            "combined_decision": "DENY",
        },
        "stale_tests_valid_approval": {
            "fresh_successful_tests": False,
            "valid_revision_bound_human_approval": True,
            "external_temporal_decision": "DENY",
            "nornyx_decision": "ALLOW",
            "combined_decision": "DENY",
        },
        "fresh_tests_wrong_revision_approval": {
            "fresh_successful_tests": True,
            "valid_revision_bound_human_approval": False,
            "approval_failure": "revision_mismatch",
            "external_temporal_decision": "ALLOW",
            "nornyx_decision": "DENY",
            "combined_decision": "DENY",
        },
        "fresh_tests_valid_exact_revision_approval": {
            "fresh_successful_tests": True,
            "valid_revision_bound_human_approval": True,
            "external_temporal_decision": "ALLOW",
            "nornyx_decision": "ALLOW",
            "combined_decision": "ALLOW",
        },
    }

    observed_ids = set()
    for case in cases:
        assert isinstance(case, dict)
        case_id = case["id"]
        assert isinstance(case_id, str)
        assert case_id in expected_cases
        assert case_id not in observed_ids
        observed_ids.add(case_id)

        expected = expected_cases[case_id]
        for field, expected_value in expected.items():
            assert case[field] == expected_value

        external_allows = case["external_temporal_decision"] == "ALLOW"
        nornyx_allows = case["nornyx_decision"] == "ALLOW"
        combined = "ALLOW" if external_allows and nornyx_allows else "DENY"
        assert case["combined_decision"] == combined

    assert observed_ids == set(expected_cases)


def test_fixture_cannot_overclaim_runtime_execution_or_event_truth() -> None:
    data = _fixture()
    boundaries = data["claim_boundaries"]
    assert isinstance(boundaries, dict)

    for key in (
        "runtime_executed",
        "agentcore_called",
        "dogwood_dependency_added",
        "proves_agentcore_runtime_enforcement",
        "proves_external_event_truth",
        "nornyx_runtime_policy_engine_added",
    ):
        assert boundaries[key] is False
