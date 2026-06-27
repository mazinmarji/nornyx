from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def test_readme_links_v101_hygiene_docs() -> None:
    text = README.read_text(encoding="utf-8")

    expected_links = [
        "docs/53_README_COMMAND_CONSISTENCY_AUDIT.md",
        "docs/54_MANIFEST_METADATA_FRESHNESS.md",
        "docs/55_PMO_SUMMARY_NOISE_REDUCTION.md",
        "docs/56_MANIFEST_VALIDATION_BASELINE_REFRESH.md",
        "docs/57_README_V101_HYGIENE_INDEX_REFRESH.md",
        "docs/58_PMO_NEXT_GOAL_LABEL_REFINEMENT.md",
        "docs/59_README_PMO_LABEL_GUIDANCE_LINK_REFRESH.md",
        "docs/61_NEXT_STRATEGIC_TRACK_AFTER_V101.md",
        "docs/releases/RELEASE_RECORD_v1_0.md",
    ]

    for link in expected_links:
        assert link in text


def test_readme_preserves_runtime_safety_boundary() -> None:
    text = README.read_text(encoding="utf-8")

    assert "v1.0.0 does not mean package publication" in text
    assert "unrestricted connector runtime" in text
    assert "regulated/enterprise GOAL-100 promotion" in text
