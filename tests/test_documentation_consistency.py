"""M0 product-state consistency: version, dependency, and status statements.

These assertions turn the repository's own source-of-truth claims into checked
facts, so documentation cannot silently drift from the package — the exact
failure mode Nornyx exists to prevent. Pure stdlib and repository reads; no
``tomllib`` so the test runs on the full supported Python range (3.10+).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    assert match, "pyproject.toml has no top-level version"
    return match.group(1)


def _pyproject_dependency_names() -> set[str]:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"(?ms)^dependencies\s*=\s*\[(.*?)\]", text)
    assert block, "pyproject.toml has no dependencies array"
    names: set[str] = set()
    for raw in re.findall(r'"([^"]+)"', block.group(1)):
        # Strip any version specifier / extras to leave the distribution name.
        name = re.split(r"[<>=!~\[; ]", raw, maxsplit=1)[0].strip()
        if name:
            names.add(name)
    return names


def test_package_version_is_consistent_across_all_locations() -> None:
    version = _pyproject_version()

    init_text = (ROOT / "nornyx" / "__init__.py").read_text(encoding="utf-8")
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    assert init_match, "nornyx/__init__.py has no __version__"
    assert init_match.group(1) == version, (
        f"nornyx/__init__.py {init_match.group(1)} != pyproject {version}"
    )

    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest.get("version") == version, (
        f"manifest.json {manifest.get('version')!r} != pyproject {version}"
    )

    versioning = (ROOT / "docs" / "VERSIONING.md").read_text(encoding="utf-8")
    assert f"`{version}`" in versioning, (
        f"docs/VERSIONING.md does not record the current package version {version}"
    )


def test_readme_lists_the_actual_runtime_dependencies() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in _pyproject_dependency_names():
        assert name in readme, (
            f"README.md does not mention runtime dependency {name!r} "
            "(pyproject dependencies changed without updating the README)"
        )


def test_source_of_truth_docs_have_no_stale_product_state() -> None:
    # Specific stale claims reconciled in M0; reintroducing any of them is a
    # regression that this test must catch.
    forbidden = [
        "@v1.1.1",  # README install pin to a deleted-era tag
        "the only runtime dependency is pyyaml",
        "does not publish a python package",
        "pending human review",
    ]
    sources = [
        ROOT / "README.md",
        ROOT / "docs" / "02_ARCHITECTURE.md",
        ROOT / "docs" / "48_NORNYX_POSITIONING.md",
        ROOT / "docs" / "planning" / "agentic-network" / "02_AN_COMPLETION_PROGRAM.md",
    ]
    for source in sources:
        text = source.read_text(encoding="utf-8").casefold()
        for phrase in forbidden:
            assert phrase.casefold() not in text, (source.name, phrase)


def test_an_completion_record_is_a_closure_not_a_pending_record() -> None:
    record = (
        ROOT / "docs" / "planning" / "agentic-network" / "02_AN_COMPLETION_PROGRAM.md"
    ).read_text(encoding="utf-8")
    assert "merged and closed" in record.casefold(), (
        "AN completion record must read as a permanent closure record"
    )
    # The permanent record cites the merge commit as the closure marker.
    assert "e4fb39e0" in record, "AN completion record must cite the merge commit"
