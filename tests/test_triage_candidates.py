from __future__ import annotations

from pathlib import Path

from nornyx.triage_candidates import (
    candidate_summary,
    find_candidate_files,
    validate_candidate_against_matrix,
    validate_candidate_directory,
    validate_triage_candidate,
)


def valid_candidate() -> dict:
    return {
        "id": "TC-20260601-001",
        "title": "Parser error recovery taxonomy",
        "concept": "error_taxonomy",
        "source_task": "GOAL-002",
        "discovered_by": "codex",
        "description": "Parser work revealed need for a formal error taxonomy.",
        "classification": "near_core_candidate",
        "rationale": "Improves checker diagnostics but can be handled after current parser slice.",
        "recommended_action": "Record for later review; continue assigned task.",
        "blocks_current_goal": False,
        "risk": "medium",
        "evidence": ["tests/test_parser.py"],
        "owner": "Architect",
        "status": "proposed",
    }


def test_valid_candidate_has_no_errors() -> None:
    issues = validate_triage_candidate(valid_candidate())
    assert not any(issue.severity == "error" for issue in issues)


def test_invalid_classification_is_error() -> None:
    data = valid_candidate()
    data["classification"] = "cool_future_idea"
    issues = validate_triage_candidate(data)
    assert any("classification" in issue.message for issue in issues)


def test_blocking_candidate_should_escalate() -> None:
    data = valid_candidate()
    data["blocks_current_goal"] = True
    data["recommended_action"] = "Record for later."
    issues = validate_triage_candidate(data)
    assert any(issue.severity == "warning" for issue in issues)


def test_candidate_summary() -> None:
    summary = candidate_summary(valid_candidate())
    assert "TC-20260601-001" in summary
    assert "error_taxonomy" in summary
    assert "near_core_candidate" in summary


def test_validate_candidate_directory(tmp_path: Path) -> None:
    candidate_file = tmp_path / "TC-20260601-001.yaml"
    candidate_file.write_text(
        """
id: TC-20260601-001
title: Parser error recovery taxonomy
concept: error_taxonomy
source_task: GOAL-002
discovered_by: codex
description: Parser work revealed need for a formal error taxonomy.
classification: near_core_candidate
rationale: Improves checker diagnostics but can be handled after current parser slice.
recommended_action: Record for later review; continue assigned task.
blocks_current_goal: false
risk: medium
evidence:
  - tests/test_parser.py
owner: Architect
status: proposed
""",
        encoding="utf-8",
    )
    assert find_candidate_files(tmp_path) == [candidate_file]
    issues = validate_candidate_directory(tmp_path)
    assert not any(issue.severity == "error" for issue in issues)


def test_duplicate_candidate_ids_are_errors(tmp_path: Path) -> None:
    body = """
id: TC-20260601-001
title: Parser error recovery taxonomy
concept: error_taxonomy
source_task: GOAL-002
discovered_by: codex
description: Parser work revealed need for a formal error taxonomy.
classification: near_core_candidate
rationale: Improves checker diagnostics but can be handled after current parser slice.
recommended_action: Record for later review; continue assigned task.
blocks_current_goal: false
risk: medium
evidence:
  - tests/test_parser.py
owner: Architect
status: proposed
"""
    (tmp_path / "a.yaml").write_text(body, encoding="utf-8")
    (tmp_path / "b.yaml").write_text(body, encoding="utf-8")
    issues = validate_candidate_directory(tmp_path)
    assert any("duplicate candidate id" in issue.message for issue in issues)


def test_candidate_classification_matches_matrix_when_concept_exists() -> None:
    candidate = {**valid_candidate(), "concept": "operations", "classification": "extension_backlog"}
    matrix = {
        "categories": {
            "extension_backlog": {"concepts": ["operations"]},
        }
    }

    issues = validate_candidate_against_matrix(candidate, matrix)

    assert not any(issue.severity == "error" for issue in issues)


def test_candidate_matrix_mismatch_is_error() -> None:
    candidate = {**valid_candidate(), "concept": "operations", "classification": "core_now"}
    matrix = {
        "categories": {
            "extension_backlog": {"concepts": ["operations"]},
        }
    }

    issues = validate_candidate_against_matrix(candidate, matrix)

    assert any("does not match matrix" in issue.message for issue in issues)


def test_unknown_candidate_concept_warns_for_human_review() -> None:
    candidate = valid_candidate()
    matrix = {"categories": {"near_core_candidate": {"concepts": ["handover"]}}}

    issues = validate_candidate_against_matrix(candidate, matrix)

    assert any("requires human review" in issue.message for issue in issues)


def test_real_candidate_directory_matches_real_triage_matrix() -> None:
    import yaml

    matrix = yaml.safe_load(Path("docs/backlog/nornyx-requirement-triage-matrix.yaml").read_text())
    issues = validate_candidate_directory(Path("docs/backlog/triage-candidates"), matrix=matrix)

    assert not any(issue.severity == "error" for issue in issues)
