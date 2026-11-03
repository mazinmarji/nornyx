"""Shipped examples under `nornyx check --strict`.

`--strict` turns every warning into a failure, including `UNKNOWN_POLICY_RULE`
(a `policies.deny` name the policy matcher never evaluates). An example that
fails `--strict` teaches users that the flag is unusable, so the examples that
can be clean must stay clean.

A few contracts and scaffolds still carry unevaluated deny names on purpose;
the migration guide lists them and says why. The last test pins that list to
what the checker actually reports, in both directions, so the documentation
cannot drift from the code.
"""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import re
import subprocess

import pytest

from nornyx.checker import check_document
from nornyx.cli import main
from nornyx.parser import load_nyx
from nornyx.profiles import PROFILE_NAMES

ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-07-17T00:00:00Z"
GUIDE = ROOT / "docs" / "67_M5_A2B_MIGRATION_GUIDE_AGENTS_POLICIES_EVALS.md"
GUIDE_SECTION = "### Contracts that still warn under `--strict`"
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
# Tracked contracts that intentionally keep unevaluated deny names, and which.
DOCUMENTED_REMAINING = {
    "examples/agentic_network.nyx": AGENTIC_STARTER_NAMES,
    "examples/agentic_network_support/support_network.nyx": AGENTIC_STARTER_NAMES
    | {"customer_pii_exposure"},
    "examples/crewai_governance_benchmark/contract/remediation_network.nyx": (
        AGENTIC_STARTER_NAMES | {"customer_pii_exposure"}
    ),
    CONFORMANCE_FIXTURE: AGENTIC_STARTER_NAMES,
}
# Scaffold commands whose output intentionally keeps unevaluated deny names.
INIT_AGENTIC = "nornyx init --profile agentic_network"
ADOPT_INIT_LITE = "nornyx adopt init-lite"
DOCUMENTED_SCAFFOLDS = {
    INIT_AGENTIC: AGENTIC_STARTER_NAMES,
    ADOPT_INIT_LITE: {"scope_expansion_without_triage"},
}


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


def _tracked_contracts() -> list[str]:
    """Every tracked `.nyx` outside `tests/`.

    `tests/` holds goldens and before/after migration snapshots, which keep old
    content on purpose. Untracked files are never scanned.
    """
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.nyx"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    paths = [item for item in result.stdout.decode("utf-8").split("\0") if item]
    assert paths, "git ls-files found no tracked .nyx files"
    return sorted(path for path in paths if not path.startswith("tests/"))


def _guide_rows(guide: str) -> dict[str, set[str]]:
    """Parse the disclosure table: column-1 identifier -> column-2 names."""
    parts = guide.replace("\r\n", "\n").split(GUIDE_SECTION, 1)
    assert len(parts) == 2, "migration guide lost its strict-mode disclosure"
    section = parts[1].split("\n---\n", 1)[0].split("\n## ", 1)[0]
    rows: dict[str, set[str]] = {}
    for line in section.splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0] == "Contract":
            continue
        assert len(cells) == 3, line
        identifiers = re.findall(r"`([^`]+)`", cells[0])
        assert len(identifiers) == 1, line
        key = identifiers[0]
        assert key not in rows, f"duplicate row for {key}"
        rows[key] = set(re.findall(r"`([^`]+)`", cells[1]))
        assert rows[key], line
    return rows


def test_packaged_examples_are_listed() -> None:
    assert "nornyx/examples/org_policies.nyx" in PACKAGED_EXAMPLES
    assert "nornyx/examples/governed_service.nyx" in PACKAGED_EXAMPLES


@pytest.mark.parametrize(
    "example", PACKAGED_EXAMPLES + REPO_EXAMPLES_MADE_STRICT_CLEAN
)
def test_shipped_example_passes_check_strict(example: str) -> None:
    exit_code, out = _run(["check", str(ROOT / example), "--as-of", AS_OF, "--strict"])

    assert "UNKNOWN_POLICY_RULE" not in out, out
    assert exit_code == 0, out
    assert "Nornyx check passed" in out


def test_documented_strict_warnings_are_exactly_the_ones_that_remain(
    tmp_path: Path,
) -> None:
    contracts = _tracked_contracts()
    assert CONFORMANCE_FIXTURE in contracts
    assert set(PACKAGED_EXAMPLES) <= set(contracts)
    observed: dict[str, set[str]] = {}
    for contract in contracts:
        names = _unknown_rule_names(ROOT / contract)
        if names:
            observed[contract] = names
    assert observed == DOCUMENTED_REMAINING

    observed_scaffolds: dict[str, set[str]] = {}
    for profile in PROFILE_NAMES:
        target = tmp_path / f"{profile}.nyx"
        exit_code, out = _run(
            ["init", "--profile", profile, "--name", "DemoProject", "--out", str(target)]
        )
        assert exit_code == 0, out
        names = _unknown_rule_names(target)
        if names:
            observed_scaffolds[f"nornyx init --profile {profile}"] = names
    lite_repo = tmp_path / "lite_repo"
    lite_repo.mkdir()
    lite = tmp_path / "lite.nyx"
    exit_code, out = _run(
        [
            "adopt",
            "init-lite",
            "--project",
            "DemoProject",
            "--repo",
            str(lite_repo),
            "--out",
            str(lite),
        ]
    )
    assert exit_code == 0, out
    names = _unknown_rule_names(lite)
    if names:
        observed_scaffolds[ADOPT_INIT_LITE] = names
    assert observed_scaffolds == DOCUMENTED_SCAFFOLDS

    # The guide's table must list exactly these rows, each with its own names.
    rows = _guide_rows(GUIDE.read_text(encoding="utf-8"))
    assert rows == {**DOCUMENTED_REMAINING, **DOCUMENTED_SCAFFOLDS}
