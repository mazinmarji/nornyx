"""Unknown / inert policy-rule diagnostic (M5-A-4).

`policies.deny` accepts free text, but the policy matcher only ever considers
names containing one of a small set of tokens. A name outside that set is
stored, rendered, reviewed -- and evaluated by nothing. These tests pin the
diagnostic that surfaces it, and pin the boundary of what the diagnostic is
allowed to claim.

The boundary matters as much as the diagnostic. Being *in* the vocabulary makes
a rule eligible for matching, not certain to match: that still depends on the
declared flow's step text. A diagnostic that implied otherwise would reproduce,
inside the linter, exactly the overclaim the linter exists to prevent.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from nornyx.checker import check_document, has_errors
from nornyx.policy_runtime import (
    EVALUATED_DENY_RULE_NAME_TOKENS,
    _matches_deny_rule,
    is_evaluated_deny_rule_name,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

UNKNOWN_RULES = ["prefer_small_prs", "clear_commit_messages", "be_concise"]
KNOWN_RULES = [
    "secret_to_llm",
    "production_deploy",
    "destructive_change",
    "connector_access",
    "self_modification",
]


def _doc(deny: list[str]) -> dict:
    return {
        "nornyx": "0.2",
        "project": {"name": "PolicyVocabularyFixture"},
        "policies": [{"name": "SamplePolicy", "deny": list(deny)}],
    }


def _unknown_rule_diagnostics(deny: list[str]) -> list:
    return [
        item
        for item in check_document(_doc(deny))
        if item.code == "UNKNOWN_POLICY_RULE"
    ]


# ---------------------------------------------------------------------------
# Vocabulary helper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rule", UNKNOWN_RULES)
def test_unknown_names_are_not_in_the_evaluated_vocabulary(rule: str) -> None:
    assert is_evaluated_deny_rule_name(rule) is False


@pytest.mark.parametrize("rule", KNOWN_RULES)
def test_known_family_names_are_in_the_evaluated_vocabulary(rule: str) -> None:
    """Recognized as eligible for evaluation.

    Deliberately NOT an assertion that these rules fire: that depends on the
    declared flow, which this vocabulary check never inspects.
    """
    assert is_evaluated_deny_rule_name(rule) is True


def test_vocabulary_matches_the_names_the_matcher_actually_checks() -> None:
    """Drift guard between the declared vocabulary and the matcher.

    The matcher keeps its own inline conditions so its behavior is untouched by
    this feature. If a token family is added or renamed there without updating
    the vocabulary, the diagnostic would start reporting a real family as
    unknown. This fails first instead.
    """
    source = Path(_matches_deny_rule.__code__.co_filename).read_text(encoding="utf-8")
    body = source.split("def _matches_deny_rule", 1)[1].split("\ndef ", 1)[0]
    for token in EVALUATED_DENY_RULE_NAME_TOKENS:
        assert f'"{token}"' in body, (
            f"{token!r} is declared in the vocabulary but not checked by the matcher"
        )


# ---------------------------------------------------------------------------
# Diagnostic emission
# ---------------------------------------------------------------------------


def test_unknown_rule_produces_a_warning_not_an_error() -> None:
    diagnostics = check_document(_doc(["prefer_small_prs"]))
    unknown = [item for item in diagnostics if item.code == "UNKNOWN_POLICY_RULE"]
    assert len(unknown) == 1
    assert unknown[0].level == "warning"
    # Non-breaking by default: a document whose only issue is an unknown rule
    # name must still be considered error-free.
    assert has_errors(diagnostics) is False


def test_diagnostic_names_the_unknown_rule() -> None:
    message = _unknown_rule_diagnostics(["prefer_small_prs"])[0].message
    assert "prefer_small_prs" in message


def test_diagnostic_points_at_the_declaring_policy() -> None:
    assert _unknown_rule_diagnostics(["be_concise"])[0].path == "policies.SamplePolicy.deny"


@pytest.mark.parametrize("rule", KNOWN_RULES)
def test_known_family_names_do_not_warn(rule: str) -> None:
    assert _unknown_rule_diagnostics([rule]) == []


def test_every_unknown_rule_is_reported_individually() -> None:
    reported = _unknown_rule_diagnostics(UNKNOWN_RULES)
    assert len(reported) == len(UNKNOWN_RULES)


def test_mixed_policy_reports_only_the_unknown_names() -> None:
    reported = _unknown_rule_diagnostics(["secret_to_llm", "prefer_small_prs"])
    assert len(reported) == 1
    assert "prefer_small_prs" in reported[0].message


def test_shorthand_rules_form_is_also_checked() -> None:
    """`rules: - deny x` normalizes to the same place as `deny: [x]`."""
    doc = {
        "nornyx": "0.2",
        "project": {"name": "PolicyVocabularyFixture"},
        "policies": [{"name": "SamplePolicy", "rules": ["deny prefer_small_prs"]}],
    }
    reported = [i for i in check_document(doc) if i.code == "UNKNOWN_POLICY_RULE"]
    assert len(reported) == 1


# ---------------------------------------------------------------------------
# The claim boundary
# ---------------------------------------------------------------------------


def test_diagnostic_makes_no_flow_outcome_claim() -> None:
    """The message must describe vocabulary, never matching behavior.

    An in-vocabulary rule is eligible, not effective. Saying a rule "will fire",
    "is enforced", or "blocks" anything would overclaim in exactly the way this
    whole track exists to prevent.
    """
    diagnostic = _unknown_rule_diagnostics(["prefer_small_prs"])[0]
    text = f"{diagnostic.message} {diagnostic.hint or ''}".lower()
    for forbidden in (
        "will fire",
        "will never fire",
        "is enforced",
        "blocks the behavior",
        "guarantees",
        "prevents",
        "runtime dlp",
    ):
        assert forbidden not in text, f"diagnostic overclaims: {forbidden!r}"


def test_diagnostic_uses_vocabulary_language() -> None:
    diagnostic = _unknown_rule_diagnostics(["prefer_small_prs"])[0]
    assert "outside the evaluated policy-rule vocabulary" in diagnostic.message
    assert "--strict" in (diagnostic.hint or "")


# ---------------------------------------------------------------------------
# CLI behavior: default is non-breaking, strict is opt-in
# ---------------------------------------------------------------------------


def _write_contract(tmp_path: Path, deny_extra: list[str]) -> Path:
    source = (
        REPO_ROOT
        / "examples"
        / "agents_migration_example"
        / "agents_migration_example.nyx"
    ).read_text(encoding="utf-8")
    injected = "\n".join(f"      - {rule}" for rule in deny_extra)
    source = source.replace(
        "      - self_modification\n",
        f"      - self_modification\n{injected}\n",
        1,
    )
    target = tmp_path / "contract.nyx"
    target.write_text(source, encoding="utf-8")
    return target


def _check(path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "nornyx.cli", "check", str(path), *extra],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_default_check_warns_but_passes(tmp_path: Path) -> None:
    result = _check(_write_contract(tmp_path, ["prefer_small_prs"]))
    assert result.returncode == 0, result.stdout
    assert "UNKNOWN_POLICY_RULE" in result.stdout
    assert "prefer_small_prs" in result.stdout
    assert "Nornyx check passed" in result.stdout


def test_strict_check_fails_on_unknown_rule(tmp_path: Path) -> None:
    result = _check(_write_contract(tmp_path, ["prefer_small_prs"]), "--strict")
    assert result.returncode != 0
    assert "UNKNOWN_POLICY_RULE" in result.stdout
    assert "Nornyx check passed" not in result.stdout


def test_strict_check_passes_a_clean_contract() -> None:
    """Strict must not fail the repository's own example.

    If it did, --strict would be unusable and would quietly be dropped from any
    pipeline that adopted it.
    """
    contract = (
        REPO_ROOT
        / "examples"
        / "agents_migration_example"
        / "agents_migration_example.nyx"
    )
    result = _check(contract, "--strict")
    assert result.returncode == 0, result.stdout


def test_default_check_still_passes_the_shipped_examples() -> None:
    """Compatibility: the new warning must not break existing valid contracts."""
    for name in ("nornyx_roadmap_goals.nyx", "governance_foundations.nyx"):
        result = _check(REPO_ROOT / "examples" / name)
        assert result.returncode == 0, f"{name}:\n{result.stdout}"
