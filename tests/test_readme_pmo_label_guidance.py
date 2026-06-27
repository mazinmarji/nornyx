from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def test_readme_links_pmo_label_guidance() -> None:
    text = README.read_text(encoding="utf-8")

    assert "PMO next-goal label refinement" in text
    assert "docs/58_PMO_NEXT_GOAL_LABEL_REFINEMENT.md" in text


def test_readme_links_current_hygiene_link_refresh_note() -> None:
    text = README.read_text(encoding="utf-8")

    assert "README PMO label guidance link refresh" in text
    assert "docs/59_README_PMO_LABEL_GUIDANCE_LINK_REFRESH.md" in text
