"""Structural tests for the first-wave standards mapping (issue #47).

A standards mapping is read as an assertion of coverage. The control that keeps
it honest is the non-coverage table, so these tests check that both halves are
present -- exactly as the migration example's tests check both the contract and
its residual list.

Deliberately structural. They do not pin row counts, framework wording, or the
presence of any particular mapping, because a test that did would break on the
next wave and get deleted, taking the control with it.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MAPPING = REPO_ROOT / "docs" / "68_STANDARDS_MAPPING_FIRST_WAVE.md"

#: Surface labels a mapped row may carry. Flattening these into one generic
#: "control" label is what turns a mapping into marketing.
SURFACE_LABELS = {
    "authorization-spi",
    "harness-policy",
    "evidence",
    "approval",
    "eval-threshold",
    "lock-drift-conformance",
    "docs-guidance",
    "example-only",
}

#: Qualified claim types. Unqualified "covered" is deliberately absent.
CLAIM_TYPES = {
    "implemented",
    "checked",
    "evidence-bound",
    "declared",
    "example-only",
    "documentation-only",
}

#: Phrases that would turn this document into a compliance claim.
FORBIDDEN_PHRASES = (
    "fully covered",
    "complete coverage",
    "proves compliance",
    "guarantees governance",
    "guarantees prevention",
    "meets iso",
    "meets nist",
    "enterprise-ready",
)


@pytest.fixture(scope="module")
def text() -> str:
    return MAPPING.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def prose(text: str) -> str:
    """Lowercased text with markdown emphasis removed.

    Phrase assertions run against this so that emphasising a word -- writing
    `**not** a certification` rather than `not a certification` -- cannot
    silently defeat a check. The claim is what matters, not its formatting.
    """
    return re.sub(r"[*_`]+", "", text).lower()


@pytest.fixture(scope="module")
def mapping_ids(text: str) -> list[str]:
    return re.findall(r"\|\s*(MAP-\d+)\s*\|", text)


@pytest.fixture(scope="module")
def noncoverage_ids(text: str) -> list[str]:
    return re.findall(r"\|\s*(NC-\d+)\s*\|", text)


def test_mapping_document_exists() -> None:
    assert MAPPING.is_file(), f"missing standards mapping at {MAPPING}"


def test_document_has_a_mapped_control_table(mapping_ids: list[str]) -> None:
    assert mapping_ids, "no MAP- rows found; the mapped-control table is missing"


def test_document_has_an_explicit_non_coverage_table(noncoverage_ids: list[str]) -> None:
    assert noncoverage_ids, "no NC- rows found; the non-coverage table is missing"


def test_non_coverage_table_is_not_empty(noncoverage_ids: list[str]) -> None:
    """The control that keeps a mapping from reading as a coverage claim.

    Not a row-count assertion -- only that the unmapped half exists at all.
    """
    assert len(set(noncoverage_ids)) >= 1


def test_every_mapped_row_is_labelled_by_surface(text: str, mapping_ids: list[str]) -> None:
    """No row may be flattened into a generic control label."""
    # A mapping id appears in both the summary table and the evidence table.
    # At least one of its rows must carry a surface label.
    unlabelled: list[str] = []
    for identifier in sorted(set(mapping_ids)):
        rows = [
            line
            for line in text.splitlines()
            if re.match(rf"\|\s*{identifier}\s*\|", line)
        ]
        if not any(any(f"`{label}`" in row for label in SURFACE_LABELS) for row in rows):
            unlabelled.append(identifier)
    assert unlabelled == [], f"these mapped rows carry no surface label: {unlabelled}"


def test_surface_labels_are_declared_in_the_document(text: str) -> None:
    """The label vocabulary must be defined, not implied by usage."""
    used = {label for label in SURFACE_LABELS if f"`{label}`" in text}
    assert len(used) >= 4, f"too few surface labels declared/used: {sorted(used)}"


def test_every_mapped_row_carries_a_qualified_claim_type(
    text: str, mapping_ids: list[str]
) -> None:
    missing: list[str] = []
    for identifier in sorted(set(mapping_ids)):
        rows = [
            line
            for line in text.splitlines()
            if re.match(rf"\|\s*{identifier}\s*\|", line)
        ]
        if not any(any(f"`{claim}`" in row for claim in CLAIM_TYPES) for row in rows):
            missing.append(identifier)
    assert missing == [], f"these mapped rows carry no qualified claim type: {missing}"


def test_unqualified_covered_is_not_used_as_a_claim_type(text: str) -> None:
    """`covered` alone hides the difference between declared and enforced."""
    assert "`covered`" not in text.lower()


def test_document_states_it_is_not_a_certification(prose: str) -> None:
    assert "not a certification" in prose
    assert "not an attestation" in prose


def test_document_states_the_governing_claim_boundary(prose: str) -> None:
    """policies.deny must not be presented as runtime enforcement."""
    assert "closes the rule-name gap, not the flow-outcome gap" in prose
    assert "not runtime interception" in prose


def test_external_adoption_is_explicitly_not_claimed(prose: str) -> None:
    assert "does not prove external adoption" in prose


def test_no_unnegated_overclaim_phrases(text: str) -> None:
    """Any risky phrase must be negated in the same sentence.

    Checked per sentence rather than per document so a negation elsewhere
    cannot launder a claim made here.
    """
    offenders: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
        lowered = sentence.lower()
        for phrase in FORBIDDEN_PHRASES:
            if phrase not in lowered:
                continue
            if not re.search(r"\b(no|not|never|without|cannot|non-goal)\b", lowered):
                offenders.append(sentence.strip()[:160])
    assert offenders == [], offenders


def test_first_wave_frameworks_come_from_the_backlog(text: str) -> None:
    """Scope must follow the repo's backlog, not be chosen in the document."""
    backlog = (REPO_ROOT / "docs" / "backlog" / "nornyx-standards-mapping-roadmap.yaml").read_text(
        encoding="utf-8"
    )
    for framework in ("NIST AI RMF", "ISO/IEC 42001"):
        assert framework in backlog
        assert framework in text
