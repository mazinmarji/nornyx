"""Native CrewAI x Nornyx 1.7.0 A/B comparison tests.

Exercises real ``Agent``/``Task``/``Crew`` objects and ``Crew.kickoff()`` in
both variants against the canonical support contract with a deterministic
offline model. No API key, no external model, no network, no subprocess: the
whole comparison runs under a loopback-only guard. The module skips (never
errors) when ``crewai`` is not installed, matching the repository's native
CrewAI suite; the hosted native-frameworks job installs CrewAI and runs it
without skips.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "crewai_nornyx_comparison"
if str(EXAMPLE) not in sys.path:
    sys.path.insert(0, str(EXAMPLE))

import common  # noqa: F401,E402  (imported first to set the telemetry kill switches)

crewai = pytest.importorskip("crewai")

import compare  # noqa: E402
from common import no_external_io  # noqa: E402
from governed_crewai import GovernedSupportNetwork  # noqa: E402
from plain_crewai import PlainSupportNetwork  # noqa: E402
from scenarios import SCENARIO_META  # noqa: E402

EXPECTED = json.loads((EXAMPLE / "expected_results.json").read_text(encoding="utf-8"))
PREVENTION = [
    sid
    for sid, meta in SCENARIO_META.items()
    if meta["klass"] in ("prevention", "identity")
]


@pytest.fixture(scope="module")
def comparison(tmp_path_factory: pytest.TempPathFactory) -> dict:
    out = tmp_path_factory.mktemp("crewai-ab")
    with no_external_io():
        return compare.run(out, benchmark=False)


# ---------------------------------------------------------------- digests
def test_events_bind_to_exact_contract_and_lock_digests(comparison: dict) -> None:
    assert comparison["contract_digest"] == EXPECTED["contract_digest"]
    assert comparison["network_lock_digest"] == EXPECTED["network_lock_digest"]
    metrics = comparison["metrics"]
    assert metrics["events_bound_to_contract_digest"] == metrics[
        "governed_events_emitted"
    ]
    assert metrics["events_bound_to_network_lock_digest"] == metrics[
        "governed_events_emitted"
    ]


# ------------------------------------------------------- evidence validation
def test_runtime_event_evidence_validates(comparison: dict) -> None:
    metrics = comparison["metrics"]
    assert metrics["evidence_validation_status"] == "pass"
    assert metrics["evidence_records_validated"] == EXPECTED["governed_events_emitted"]
    assert metrics["governed_events_emitted"] == EXPECTED["governed_events_emitted"]


# ------------------------------------------------- allowed-path equivalence
def test_identical_allowed_business_output_and_no_false_denials(
    comparison: dict,
) -> None:
    metrics = comparison["metrics"]
    assert metrics["allowed_output_equivalence"] is True
    assert comparison["workflow"]["outputs_equivalent"] is True
    assert metrics["false_denials_of_allowed_actions"] == 0
    assert metrics["allowed_scenarios_completed"] == metrics["allowed_scenarios_total"]


# --------------------------------------------------------- scenario matrix
def test_scenario_matrix_matches_expected(comparison: dict) -> None:
    rows = {row["scenario"]: row for row in comparison["rows"]}
    for sid, want in EXPECTED["scenarios"].items():
        row = rows[sid]
        assert row["baseline_outcome"] == want["baseline_outcome"], sid
        assert row["governed_outcome"] == want["governed_outcome"], sid
        assert row["baseline_protected_work_executed"] == want[
            "baseline_work_executed"
        ], sid
        assert row["governed_protected_work_executed"] == want[
            "governed_work_executed"
        ], sid
        assert row["nornyx_diagnostic_code"] == want["diagnostic_code"], sid
        assert row["emitted_event_types"] == want["emitted_event_types"], sid


def test_unauthorized_work_never_runs_under_nornyx(comparison: dict) -> None:
    rows = {row["scenario"]: row for row in comparison["rows"]}
    for sid in PREVENTION:
        # CrewAI alone executes the unauthorized work ...
        assert rows[sid]["baseline_protected_work_executed"] is True, sid
        # ... and Nornyx prevents it before the work callable runs.
        assert rows[sid]["governed_protected_work_executed"] is False, sid
        assert rows[sid]["governed_outcome"] in ("denied", "refused_init"), sid
    metrics = comparison["metrics"]
    assert metrics["unauthorized_actions_executed_in_baseline"] == len(PREVENTION)
    assert metrics["unauthorized_actions_prevented_by_nornyx"] == len(PREVENTION)


# -------------------------------------------------- specific enforcement points
def test_named_enforcement_codes(comparison: dict) -> None:
    rows = {row["scenario"]: row for row in comparison["rows"]}
    assert rows["S2"]["nornyx_diagnostic_code"] == "AN_ADAPTER_CAPABILITY_UNKNOWN"
    assert rows["S3"]["nornyx_diagnostic_code"] == "AN_ADAPTER_CAPABILITY_DENIED"
    assert rows["S5"]["nornyx_diagnostic_code"] == "AN_ADAPTER_CAPABILITY_DENIED"
    assert rows["S6"]["emitted_event_types"][:2] == [
        "handoff_initiated",
        "handoff_completed",
    ]
    assert rows["S6"]["nornyx_diagnostic_code"] == "AN_ADAPTER_CAPABILITY_DENIED"
    assert rows["S7"]["nornyx_diagnostic_code"] == "AN_ADAPTER_CROSSING_APPROVAL_REQUIRED"
    assert rows["S8"]["governed_outcome"] == "allowed"
    assert "approval_granted" in rows["S8"]["emitted_event_types"]
    assert rows["S9"]["nornyx_diagnostic_code"] == "AN_ADAPTER_APPROVAL_NON_HUMAN"
    assert rows["S10"]["nornyx_diagnostic_code"] == "AN_ADAPTER_SENSITIVE_SHARING"
    assert rows["S11"]["nornyx_diagnostic_code"] == "AN_ADAPTER_ZONE_CROSSING_DENIED"
    assert rows["S12"]["nornyx_diagnostic_code"] == "AN_ADAPTER_LOCK_STALE"
    assert rows["S13"]["nornyx_diagnostic_code"] == "AN_ADAPTER_IDENTITY_UNKNOWN"


def test_deliberate_bypass_is_documented_not_prevented(comparison: dict) -> None:
    rows = {row["scenario"]: row for row in comparison["rows"]}
    s14 = rows["S14"]
    # The negative control: bypassing the adapter runs the code in both variants.
    assert s14["baseline_protected_work_executed"] is True
    assert s14["governed_protected_work_executed"] is True
    assert s14["nornyx_diagnostic_code"] is None
    assert "boundary" in s14["caveat"].lower()
    assert comparison["metrics"]["deliberate_bypass_result"][
        "governed_protected_work_executed"
    ] is True


# ----------------------------------------------- native Crew.kickoff() both
def test_native_crew_kickoff_in_both_variants_matches() -> None:
    with no_external_io():
        plain = PlainSupportNetwork()
        plain_wf = plain.run_workflow()
        governed = GovernedSupportNetwork(_tmp())
        governed_wf = governed.run_workflow()
    assert plain_wf["output"] == governed_wf["output"]
    assert plain_wf["output"].strip() != ""
    assert governed_wf["evidence_status"] == "pass"
    # Both variants really drove the native ReAct executor (>=2 LLM calls/task).
    assert governed_wf["event_count"] >= 6


def _tmp() -> Path:
    import tempfile

    return Path(tempfile.mkdtemp(prefix="crewai-ab-kickoff-"))


# ---------------------------------------------------------------- determinism
def test_deterministic_repeated_results(tmp_path: Path) -> None:
    with no_external_io():
        first = compare.run(tmp_path / "a", benchmark=False)
        second = compare.run(tmp_path / "b", benchmark=False)
    assert first["rows"] == second["rows"]
    events_a = (tmp_path / "a" / "nornyx_runtime_events.json").read_text(
        encoding="utf-8"
    )
    events_b = (tmp_path / "b" / "nornyx_runtime_events.json").read_text(
        encoding="utf-8"
    )
    assert events_a == events_b


# ---------------------------------------------------- no external operations
def test_guard_blocks_network_and_subprocess() -> None:
    with no_external_io():
        with pytest.raises(AssertionError):
            socket.create_connection(("example.com", 443))
        with pytest.raises(AssertionError):
            socket.getaddrinfo("example.com", 443)
        with pytest.raises(AssertionError):
            subprocess.run(["echo", "nope"])  # noqa: S603,S607
        # A full governed workflow completes under the same guard, proving the
        # demonstration needs no external network, subprocess, or shell.
        governed = GovernedSupportNetwork(_tmp())
        result = governed.run_workflow()
    assert result["evidence_status"] == "pass"
