from __future__ import annotations

from nornyx.patterns import can_promote, summarize_pattern, validate_pattern_lifecycle


def valid_pattern() -> dict:
    return {
        "id": "context_authority_order",
        "name": "Context Authority Order",
        "type": "context",
        "status": "candidate",
        "problem": "Agents may use low-authority context as instruction.",
        "solution": "Declare explicit authority order.",
        "applicability": ["repos with multiple context sources"],
        "non_goals": ["guarantee all docs are correct"],
        "validation": ["nornyx check", "context authority conflict test"],
        "evidence": ["docs/qa/evidence/GOAL-005/"],
        "risks": ["stale authoritative docs"],
        "failure_modes": ["authority declared but not enforced"],
        "promotion_criteria": ["eval pass", "human review"],
    }


def test_valid_candidate_pattern_has_no_errors() -> None:
    issues = validate_pattern_lifecycle(valid_pattern())
    assert not any(issue.severity == "error" for issue in issues)
    assert can_promote(valid_pattern()) is True


def test_missing_evidence_is_error() -> None:
    pattern = valid_pattern()
    pattern["evidence"] = []
    issues = validate_pattern_lifecycle(pattern)
    assert any("evidence" in issue.message for issue in issues)


def test_invalid_type_is_error() -> None:
    pattern = valid_pattern()
    pattern["type"] = "youtube_trick"
    issues = validate_pattern_lifecycle(pattern)
    assert any("type must be" in issue.message for issue in issues)


def test_stable_without_human_review_warns() -> None:
    pattern = valid_pattern()
    pattern["status"] = "stable"
    pattern["promotion_criteria"] = ["eval pass", "evidence pack"]
    issues = validate_pattern_lifecycle(pattern)
    assert any(issue.severity == "warning" for issue in issues)


def test_summarize_pattern() -> None:
    assert summarize_pattern(valid_pattern()).startswith("context_authority_order [context/candidate]")
