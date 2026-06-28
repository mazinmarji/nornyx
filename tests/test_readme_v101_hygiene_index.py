from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def test_readme_links_product_docs() -> None:
    text = README.read_text(encoding="utf-8")

    expected_links = [
        "docs/48_NORNYX_POSITIONING.md",
        "docs/49_NORNYX_5_MINUTE_ADOPTION.md",
        "docs/50_NORNYX_GRAPH_DEMO.md",
        "docs/52_SCHEMA_TARGETS_AND_EXAMPLES.md",
        "docs/03_ROADMAP_TO_v1_AND_BEYOND.md",
    ]

    for link in expected_links:
        assert link in text


def test_readme_preserves_runtime_safety_boundary() -> None:
    text = README.read_text(encoding="utf-8")

    # The README must state the non-runtime safety boundary.
    assert "autonomous system modification" in text
    assert "production deployment" in text
    assert "credential handling" in text
    assert "arbitrary command execution" in text
