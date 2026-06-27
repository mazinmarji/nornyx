from __future__ import annotations

import json
from pathlib import Path

import yaml

from nornyx.product_lifecycle import (
    ALLOWED_EXTENSION_STATUSES,
    ALLOWED_PLACEMENTS,
    lifecycle_summary,
    should_promote_handover_first,
    validate_lifecycle_extension,
)


def valid_extension() -> dict:
    concepts = [
        ("intake", "Capture product problem and constraints", "roadmap"),
        ("persona", "Capture user roles and needs", "roadmap"),
        ("journey", "Capture user journey", "roadmap"),
        ("prototype", "Capture mockup and UX handover", "roadmap"),
        ("assumption", "Capture assumptions explicitly", "near_term_design"),
        ("open_question", "Capture unresolved questions", "near_term_design"),
        ("decision_needed", "Capture owner-bound decision", "near_term_design"),
        ("handover", "Connect lifecycle phases", "candidate"),
        ("operations", "Capture runbook and monitoring readiness", "roadmap"),
        ("product_eval", "Capture product/business outcome validation", "roadmap"),
        ("lifecycle_state", "Track product/service stage", "roadmap"),
    ]
    return {
        "name": "ProductToOperationsLifecycle",
        "status": "roadmap",
        "concepts": [
            {"name": name, "purpose": purpose, "placement": placement}
            for name, purpose, placement in concepts
        ],
        "promotion_order": ["handover", "assumption", "open_question", "decision_needed", "intake", "prototype", "operations", "product_eval", "lifecycle_state"],
        "non_goals": ["product management suite", "operations console"],
    }


def test_valid_lifecycle_extension_has_no_errors() -> None:
    issues = validate_lifecycle_extension(valid_extension())
    assert not any(issue.severity == "error" for issue in issues)


def test_missing_handover_warns() -> None:
    data = valid_extension()
    data["promotion_order"] = ["intake"]
    issues = validate_lifecycle_extension(data)
    assert any("handover" in issue.message for issue in issues)


def test_duplicate_concept_is_error() -> None:
    data = valid_extension()
    data["concepts"].append(dict(data["concepts"][0]))
    issues = validate_lifecycle_extension(data)
    assert any("duplicate concept" in issue.message for issue in issues)


def test_should_promote_handover_first() -> None:
    assert should_promote_handover_first(valid_extension()) is True


def test_lifecycle_summary() -> None:
    summary = lifecycle_summary(valid_extension())
    assert "ProductToOperationsLifecycle" in summary
    assert "concepts=11" in summary


def test_backlog_lifecycle_yaml_is_valid() -> None:
    data = yaml.safe_load(Path("docs/backlog/nornyx-product-to-ops-lifecycle.yaml").read_text())

    issues = validate_lifecycle_extension(data)

    assert not any(issue.severity == "error" for issue in issues)
    assert should_promote_handover_first(data) is True
    placements = {concept["name"]: concept["placement"] for concept in data["concepts"]}
    assert placements["handover"] == "candidate"
    assert all(placement != "core" for placement in placements.values())


def test_schema_enums_match_validator_constants() -> None:
    schema = json.loads(Path("schemas/product_lifecycle_extension.schema.json").read_text())

    assert set(schema["properties"]["status"]["enum"]) == ALLOWED_EXTENSION_STATUSES
    assert set(schema["properties"]["concepts"]["items"]["properties"]["placement"]["enum"]) == (
        ALLOWED_PLACEMENTS
    )
