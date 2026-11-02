"""Shipped examples under `nornyx check --strict`.

`--strict` turns every warning into a failure, including `UNKNOWN_POLICY_RULE`
(a `policies.deny` name the policy matcher never evaluates). An example that
fails `--strict` teaches users that the flag is unusable, so the examples that
can be clean must stay clean.

A few contracts still carry unevaluated deny names on purpose; the migration
guide lists them and says why. The second test pins that list to what the
checker actually reports, so the documentation cannot drift from the code.
"""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import re

import pytest

from nornyx.checker import check_document
from nornyx.cli import main
from nornyx.parser import load_nyx
from nornyx.profiles import PROFILE_NAMES

ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-07-17T00:00:00Z"
GUIDE = ROOT / "docs" / "67_M5_A2B_MIGRATION_GUIDE_AGENTS_POLICIES_EVALS.md"
CONFORMANCE_FIXTURE = (
    "adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/"
    "conformance/fixtures/conformance_network.nyx"
)

PACKAGED_EXAMPLES = sorted(
    path.relative_to(ROOT).as_posix()
    for path in (ROOT / "nornyx" / "examples").glob("*.nyx")
)
REPO_EXAMPLES_MADE_STRICT_CLEAN = [
    "examples/nornyx_distinct_language_showcase.nyx",
    "examples/nornyx_graph_demo.nyx",
    "examples/nornyx_graph_demo_expanded.nyx",
    "examples/nornyx_v04_adapter_contracts.nyx",
]

AGENTIC_STARTER_NAMES = {
    "autonomous_approval",
    "undeclared_capability_use",
    "undeclared_cross_zone_transition",
}
# Contracts that intentionally keep unevaluated deny names, and exactly which.
DOCUMENTED_REMAINING = {
    "examples/agentic_network.nyx": AGENTIC_STARTER_NAMES,
    "examples/agentic_network_support/support_network.nyx": AGENTIC_STARTER_NAMES
    | {"customer_pii_exposure"},
    "examples/crewai_governance_benchmark/contract/remediation_network.nyx": (
        AGENTIC_STARTER_NAMES | {"customer_pii_exposure"}
    ),
    CONFORMANCE_FIXTURE: AGENTIC_STARTER_NAMES,
}
DOCUMENTED_REMAINING_PROFILES = {"agentic_network": AGENTIC_STARTER_NAMES}


def _run(argv: list[str]) -> tuple[int, str]:
    output = StringIO()
    with redirect_stdout(output):
        exit_code = main(argv)
    return exit_code, output.getvalue()


def _unknown_rule_names(path: Path) -> set[str]:
    names = set()
    for diagnostic in check_document(load_nyx(path)):
        if diagnostic.code != "UNKNOWN_POLICY_RULE":
            continue
        match = re.match(r"`([^`]+)`", diagnostic.message)
        assert match, diagnostic.message
        names.add(match.group(1))
    return names


def test_packaged_examples_are_listed() -> None:
    assert "nornyx/examples/org_policies.nyx" in PACKAGED_EXAMPLES
    assert "nornyx/examples/governed_service.nyx" in PACKAGED_EXAMPLES


@pytest.mark.parametrize(
    "example", PACKAGED_EXAMPLES + REPO_EXAMPLES_MADE_STRICT_CLEAN
)
def test_shipped_example_passes_check_strict(example: str) -> None:
    exit_code, out = _run(["check", example, "--as-of", AS_OF, "--strict"])

    assert "UNKNOWN_POLICY_RULE" not in out, out
    assert exit_code == 0, out
    assert "Nornyx check passed" in out


def test_documented_strict_warnings_are_exactly_the_ones_that_remain(
    tmp_path: Path,
) -> None:
    observed: dict[str, set[str]] = {}
    contracts = sorted(
        {path.relative_to(ROOT).as_posix() for path in (ROOT / "examples").rglob("*.nyx")}
        | set(PACKAGED_EXAMPLES)
        | {CONFORMANCE_FIXTURE}
    )
    for contract in contracts:
        names = _unknown_rule_names(ROOT / contract)
        if names:
            observed[contract] = names
    assert observed == DOCUMENTED_REMAINING

    observed_profiles: dict[str, set[str]] = {}
    for profile in PROFILE_NAMES:
        target = tmp_path / f"{profile}.nyx"
        exit_code, out = _run(
            ["init", "--profile", profile, "--name", "DemoProject", "--out", str(target)]
        )
        assert exit_code == 0, out
        names = _unknown_rule_names(target)
        if names:
            observed_profiles[profile] = names
    assert observed_profiles == DOCUMENTED_REMAINING_PROFILES

    guide = GUIDE.read_text(encoding="utf-8")
    section = guide.split("### Contracts that still warn under `--strict`", 1)
    assert len(section) == 2, "migration guide lost its strict-mode disclosure"
    disclosure = section[1].split("\n## ", 1)[0]
    conformance_name = Path(CONFORMANCE_FIXTURE).name
    for contract in DOCUMENTED_REMAINING:
        expected = conformance_name if contract == CONFORMANCE_FIXTURE else contract
        assert f"`{expected}`" in disclosure, contract
    assert "`nornyx init --profile agentic_network`" in disclosure
    for name in set().union(*DOCUMENTED_REMAINING.values()):
        assert f"`{name}`" in disclosure, name
