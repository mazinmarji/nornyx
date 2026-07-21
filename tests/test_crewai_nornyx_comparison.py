"""Native CrewAI x Nornyx 1.7.0 A/B comparison tests.

Every runtime scenario runs the same ``Agent``/``Task``/business tool through
``Crew.kickoff()`` in both variants; the governed variant inserts a Nornyx check
immediately before the shared, ledger-backed side effect. Denied runtime
scenarios are proved by the side-effect ledger staying at zero. No API key, no
external model, no network, no subprocess: the whole comparison runs under a
loopback-only guard. The module skips (never errors) when ``crewai`` is not
installed; the hosted native-frameworks job installs CrewAI and runs it without
skips.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
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
from scenarios import RUNTIME_DENIED  # noqa: E402

EXPECTED = json.loads((EXAMPLE / "expected_results.json").read_text(encoding="utf-8"))


def _tmp() -> Path:
    return Path(tempfile.mkdtemp(prefix="crewai-ab-"))


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
    total = metrics["governed_events_emitted"]
    assert metrics["events_bound_to_contract_digest"] == total
    assert metrics["events_bound_to_network_lock_digest"] == total
    # Per-row binding is computed from the actual events, not "are there events".
    for row in comparison["rows"]:
        if row["emitted_event_types"]:
            assert row["contract_digest_bound"] is True, row["scenario"]
            assert row["lock_digest_bound"] is True, row["scenario"]
        else:
            assert row["contract_digest_bound"] is None, row["scenario"]
            assert row["lock_digest_bound"] is None, row["scenario"]


def test_runtime_event_evidence_validates(comparison: dict) -> None:
    metrics = comparison["metrics"]
    assert metrics["evidence_validation_status"] == "pass"
    assert metrics["evidence_records_validated"] == EXPECTED["governed_events_emitted"]
    assert metrics["governed_events_emitted"] == EXPECTED["governed_events_emitted"]


def test_identical_allowed_business_output_and_no_false_denials(comparison: dict) -> None:
    metrics = comparison["metrics"]
    assert metrics["allowed_output_equivalence"] is True
    assert comparison["workflow"]["outputs_equivalent"] is True
    assert metrics["false_denials_of_allowed_actions"] == 0
    assert metrics["runtime_allowed_completed"] == metrics["runtime_allowed_total"]


# --------------------------------------------------------- scenario matrix
def test_scenario_matrix_matches_expected(comparison: dict) -> None:
    rows = {row["scenario"]: row for row in comparison["rows"]}
    for sid, want in EXPECTED["scenarios"].items():
        row = rows[sid]
        assert row["baseline_outcome"] == want["baseline_outcome"], sid
        assert row["governed_outcome"] == want["governed_outcome"], sid
        assert row["baseline_protected_work_executed"] == want["baseline_work_executed"], sid
        assert row["governed_protected_work_executed"] == want["governed_work_executed"], sid
        assert row["nornyx_diagnostic_code"] == want["diagnostic_code"], sid
        assert row["emitted_event_types"] == want["emitted_event_types"], sid
        assert row["kind"] == want["kind"], sid


def test_runtime_denials_are_ledger_proven_same_topology(comparison: dict) -> None:
    rows = {row["scenario"]: row for row in comparison["rows"]}
    for sid in RUNTIME_DENIED:
        row = rows[sid]
        assert row["kind"] == "runtime", sid
        # CrewAI alone runs the business callable through kickoff ...
        assert row["baseline_protected_work_executed"] is True, sid
        # ... and Nornyx prevents that same callable before it runs.
        assert row["governed_protected_work_executed"] is False, sid
        assert row["governed_outcome"] == "denied", sid
    metrics = comparison["metrics"]
    assert metrics["runtime_business_callables_executed_in_baseline"] == len(RUNTIME_DENIED)
    assert metrics["runtime_business_callables_prevented_by_nornyx"] == len(RUNTIME_DENIED)


def test_initialization_and_bypass_are_reported_separately(comparison: dict) -> None:
    rows = {row["scenario"]: row for row in comparison["rows"]}
    assert rows["S12"]["kind"] == "initialization"
    assert rows["S12"]["governed_outcome"] == "refused_init"
    assert comparison["metrics"]["initialization_failure"] == "AN_ADAPTER_LOCK_STALE"
    # S12 is not counted among runtime business callables prevented.
    assert "S12" not in RUNTIME_DENIED
    assert rows["S14"]["kind"] == "bypass"
    assert comparison["metrics"]["deliberate_bypass_executed_in_both"] is True


def test_named_enforcement_codes(comparison: dict) -> None:
    rows = {row["scenario"]: row for row in comparison["rows"]}
    assert rows["S2"]["nornyx_diagnostic_code"] == "AN_ADAPTER_CAPABILITY_UNKNOWN"
    assert rows["S3"]["nornyx_diagnostic_code"] == "AN_ADAPTER_CAPABILITY_DENIED"
    assert rows["S6"]["emitted_event_types"][:2] == ["handoff_initiated", "handoff_completed"]
    assert rows["S7"]["nornyx_diagnostic_code"] == "AN_ADAPTER_CROSSING_APPROVAL_REQUIRED"
    assert "approval_granted" in rows["S8"]["emitted_event_types"]
    assert rows["S9"]["nornyx_diagnostic_code"] == "AN_ADAPTER_APPROVAL_NON_HUMAN"
    assert rows["S10"]["nornyx_diagnostic_code"] == "AN_ADAPTER_SENSITIVE_SHARING"
    assert rows["S11"]["nornyx_diagnostic_code"] == "AN_ADAPTER_ZONE_CROSSING_DENIED"
    assert rows["S13"]["nornyx_diagnostic_code"] == "AN_ADAPTER_IDENTITY_UNKNOWN"


def test_deliberate_bypass_is_documented_not_prevented(comparison: dict) -> None:
    rows = {row["scenario"]: row for row in comparison["rows"]}
    s14 = rows["S14"]
    assert s14["baseline_protected_work_executed"] is True
    assert s14["governed_protected_work_executed"] is True
    assert s14["nornyx_diagnostic_code"] is None
    assert "boundary" in s14["caveat"].lower()


# --------------------------------------------------- contract self-verification
def test_compare_contract_holds(comparison: dict) -> None:
    assert comparison["contract_verified"] is True
    assert comparison["contract_failures"] == []


def test_contract_verification_catches_regressions(comparison: dict) -> None:
    import copy

    tampered = copy.deepcopy(comparison)
    # Simulate a lost denial guarantee: a denied scenario now "runs" the work.
    for row in tampered["rows"]:
        if row["scenario"] == "S2":
            row["governed_protected_work_executed"] = True
            row["governed_outcome"] = "executed"
    failures = compare.verify_contract(tampered)
    assert failures, "verify_contract must flag a lost denial guarantee"
    assert any("S2" in f for f in failures)


# ----------------------------------------------- native Crew.kickoff() both
def test_native_crew_kickoff_in_both_variants_matches() -> None:
    with no_external_io():
        plain_wf = PlainSupportNetwork().run_workflow()
        governed_wf = GovernedSupportNetwork(_tmp()).run_workflow()
    assert plain_wf["output"] == governed_wf["output"]
    assert plain_wf["output"].strip() != ""
    assert governed_wf["evidence_status"] == "pass"
    assert governed_wf["event_count"] >= 6


# ---------------------------------------------------------------- determinism
def test_deterministic_repeated_results(tmp_path: Path) -> None:
    with no_external_io():
        first = compare.run(tmp_path / "a", benchmark=False)
        second = compare.run(tmp_path / "b", benchmark=False)
    assert first["rows"] == second["rows"]
    events_a = (tmp_path / "a" / "nornyx_runtime_events.json").read_text(encoding="utf-8")
    events_b = (tmp_path / "b" / "nornyx_runtime_events.json").read_text(encoding="utf-8")
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
        result = GovernedSupportNetwork(_tmp()).run_workflow()
    assert result["evidence_status"] == "pass"
