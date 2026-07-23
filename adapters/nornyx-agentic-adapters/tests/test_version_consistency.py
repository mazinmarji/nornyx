"""Adapter-package-scoped version consistency (mirrors the root package's own
`test_documentation_consistency.py` check, but strictly local to this
sub-package — it never reads or writes the root `nornyx` version files)."""

from __future__ import annotations

import re
from pathlib import Path

import nornyx_agentic_adapters as naa

ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    assert match, "adapter pyproject.toml has no top-level version"
    return match.group(1)


def test_package_version_matches_pyproject() -> None:
    assert naa.__version__ == _pyproject_version()


def test_changelog_mentions_the_current_version_as_unreleased() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "[Unreleased]" in changelog
    assert "not yet released" in changelog.casefold()
