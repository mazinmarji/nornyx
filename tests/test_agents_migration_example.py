"""Tests for the bounded AGENTS.md migration example (M5-A-3).

Both halves of the example are checked. The `.nyx` contract must validate, and
the residual list must exist with the required structure -- because a suite
that validated only the mapped contract would, over time, teach maintainers
that only the mapped controls matter. That is precisely the erosion the
migration guide warns about.

Deliberately structural. These tests assert that residual entries exist and
carry their four declared fields; they do not pin the row count, the exact
source text, or the presence of any particular instruction. A test that
required specific rows would break on unrelated AGENTS.md edits, and a brittle
control is one that eventually gets deleted -- taking the control with it.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = REPO_ROOT / "examples" / "agents_migration_example"
CONTRACT = EXAMPLE_DIR / "agents_migration_example.nyx"
RESIDUAL = EXAMPLE_DIR / "residual_guidance.yaml"
README = EXAMPLE_DIR / "README.md"

#: Every residual entry must declare all four. The set is the contract between
#: this test and the migration guide's residual-list template.
REQUIRED_FIELDS = {
    "source_instruction",
    "reason_not_migrated",
    "where_it_remains",
    "future_option",
}

#: Policy rule name fragments the policy runtime actually evaluates. A deny
#: rule outside these is accepted by the checker and matches nothing.
EVALUATED_RULE_TOKENS = (
    "production",
    "secret",
    "destructive",
    "connector",
    "self_modification",
)


@pytest.fixture(scope="module")
def residual() -> list[dict]:
    document = yaml.safe_load(RESIDUAL.read_text(encoding="utf-8"))
    assert isinstance(document, dict), "residual list must be a mapping at the top level"
    entries = document.get("residual_guidance")
    assert isinstance(entries, list), "residual_guidance must be a list"
    return entries


# ---------------------------------------------------------------------------
# The mapped half
# ---------------------------------------------------------------------------


def test_contract_exists() -> None:
    assert CONTRACT.is_file(), f"missing migration contract at {CONTRACT}"


def test_contract_passes_nornyx_check() -> None:
    """The mapped half must be a real contract, not illustrative YAML."""
    result = subprocess.run(
        [sys.executable, "-m", "nornyx.cli", "check", str(CONTRACT)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"nornyx check failed for {CONTRACT.name}:\n{result.stdout}\n{result.stderr}"
    )


def test_contract_declares_no_inert_policy_rules() -> None:
    """Every deny rule must sit inside an evaluated token family.

    This is the example's own guard against the trap the migration guide leads
    with: a rule name the checker accepts and the policy runtime never matches.
    """
    document = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    inert: list[str] = []
    for policy in document.get("policies", []):
        for rule in policy.get("deny", []) or []:
            if not any(token in str(rule).lower() for token in EVALUATED_RULE_TOKENS):
                inert.append(f"{policy.get('name')}: {rule}")
    assert inert == [], (
        "these deny rules fall outside every evaluated token family and would "
        f"be accepted while matching nothing: {inert}"
    )


# ---------------------------------------------------------------------------
# The unmapped half -- equally checked
# ---------------------------------------------------------------------------


def test_residual_list_exists() -> None:
    assert RESIDUAL.is_file(), f"missing residual list at {RESIDUAL}"


def test_residual_list_is_not_empty(residual: list[dict]) -> None:
    """An empty residual list is the signal that a migration over-mapped."""
    assert residual, (
        "the residual list is empty. A migration with no residual guidance is "
        "suspicious: it may have encoded guidance as controls that evaluate nothing."
    )


def test_every_residual_entry_has_the_required_structure(residual: list[dict]) -> None:
    problems: list[str] = []
    for index, entry in enumerate(residual):
        if not isinstance(entry, dict):
            problems.append(f"entry {index} is not a mapping")
            continue
        missing = REQUIRED_FIELDS - set(entry)
        if missing:
            problems.append(f"entry {index} is missing {sorted(missing)}")
        for field in REQUIRED_FIELDS & set(entry):
            value = entry[field]
            if not isinstance(value, str) or not value.strip():
                problems.append(f"entry {index} field {field!r} is empty")
    assert problems == [], problems


def test_residual_entries_name_where_guidance_remains(residual: list[dict]) -> None:
    """`where_it_remains` must point somewhere, not restate the omission.

    Structural, not content-pinned: any non-trivial destination passes. The
    point is that a reader can find the guidance, not that it lives in one
    particular file.
    """
    vague = {"n/a", "none", "-", "nowhere", "tbd"}
    offenders = [
        entry["source_instruction"]
        for entry in residual
        if entry.get("where_it_remains", "").strip().lower() in vague
    ]
    assert offenders == [], (
        f"these residual entries do not say where the guidance remains: {offenders}"
    )


def test_readme_states_this_is_not_a_full_conversion() -> None:
    readme = README.read_text(encoding="utf-8")
    assert "not a full AGENTS.md conversion" in readme
    assert "residual" in readme.lower()
