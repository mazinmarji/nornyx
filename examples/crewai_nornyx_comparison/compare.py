"""Run both variants and emit the A/B comparison artifacts.

Usage::

    python examples/crewai_nornyx_comparison/compare.py --out demo_out

Produces, under ``--out``: ``comparison.json``, ``comparison.md``,
``plain_results.json``, ``governed_results.json``, ``nornyx_runtime_events.json``,
``nornyx_evidence_report.json``, and ``environment.json``.

Exit code is **0 only if the full expected-result contract holds** (see
``verify_contract``): every scenario present with the expected outcome and
diagnostic code, denied side-effect counters zero, evidence validated and
digest-bound, drift/approval/identity/bypass results as declared. Otherwise the
process prints the failures and exits non-zero.

Everything runs offline under a loopback-only guard: no API key, no external
model, no DNS, no external socket, no subprocess, no shell.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import common  # noqa: E402
from common import capture_environment, no_external_io  # noqa: E402
from governed_crewai import GovernedSupportNetwork  # noqa: E402
from plain_crewai import PlainSupportNetwork  # noqa: E402
from scenarios import (  # noqa: E402
    RUNTIME_ALLOWED,
    RUNTIME_DENIED,
    SCENARIO_IDS,
    build_metrics,
    build_rows,
)

from nornyx.agentic_artifacts import (  # noqa: E402
    build_agentic_network_lock,
    write_agentic_network_lock,
)
from nornyx.governance import GovernanceRegistry, compose_governance  # noqa: E402
from nornyx.parser import load_nyx  # noqa: E402
from nornyx_agentic_adapters.crewai_adapter import CrewAIGovernanceAdapter  # noqa: E402
from nornyx_agentic_adapters.governance_kernel import (  # noqa: E402
    DeterministicClock,
    GovernanceKernel,
    GovernanceViolation,
)

EXPECTED = json.loads(
    (Path(_HERE) / "expected_results.json").read_text(encoding="utf-8")
)

LIMITATIONS = [
    "Nornyx governs declared authority and supplied evidence; it does not operate "
    "CrewAI, execute the model, or authenticate agents.",
    "Enforcement is cooperative: code that bypasses the adapter is not intercepted "
    "(scenario S14).",
    "Evidence validation proves content binding to the exact contract and lock, not "
    "that an emitted event is truthful.",
    "The CrewAI adapter is unpackaged in Nornyx 1.7.0; it lives under integrations/.",
    "Runtime denials are proved by a side-effect ledger; S12 is an initialization "
    "check and S14 is a negative control, reported separately.",
    "Timing figures are a local microbenchmark, not a production performance claim.",
]


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        return 0.0
    mid = n // 2
    return ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0


def _microbenchmark(out_dir: Path, samples: int = 200, init_samples: int = 10) -> dict:
    """A local microbenchmark: setup time and per-call governance overhead."""

    registry = GovernanceRegistry.builtins()
    document = load_nyx(common.CONTRACT)
    composition = compose_governance(registry, profile_identity="agentic_network")
    lock_payload = build_agentic_network_lock(document, composition)
    lock_path = write_agentic_network_lock(
        lock_payload, out_dir / "bench.agentic_network.lock"
    )

    init_times: list[float] = []
    for _ in range(init_samples):
        start = time.perf_counter()
        GovernanceKernel.from_local_controls(
            common.CONTRACT, lock_path, framework="crewai", as_of=common.AS_OF
        )
        init_times.append(time.perf_counter() - start)

    kernel = GovernanceKernel.from_local_controls(
        common.CONTRACT, lock_path, framework="crewai", as_of=common.AS_OF,
        clock=DeterministicClock(),
    )
    adapter = CrewAIGovernanceAdapter(kernel)

    class _Agent:
        role = common.ROLE_COORDINATOR

    agent = _Agent()
    allowed: list[float] = []
    for _ in range(samples):
        guarded = adapter.guarded_task(
            agent, "classify_support_request", lambda: "x", mission_id=common.MISSION
        )
        start = time.perf_counter()
        guarded()
        allowed.append(time.perf_counter() - start)

    denied: list[float] = []
    for _ in range(samples):
        guarded = adapter.guarded_task(
            agent, "escalate_high_value_refund", lambda: "x", mission_id=common.MISSION
        )
        start = time.perf_counter()
        try:
            guarded()
        except GovernanceViolation:
            pass
        denied.append(time.perf_counter() - start)

    return {
        "label": "local microbenchmark (not a production performance claim)",
        "sample_count_per_call_type": samples,
        "init_sample_count": init_samples,
        "median_governance_init_seconds": round(_median(init_times), 6),
        "median_allowed_call_overhead_seconds": round(_median(allowed), 8),
        "median_denied_call_overhead_seconds": round(_median(denied), 8),
    }


def verify_contract(comparison: dict) -> list[str]:
    """Return a list of contract failures; empty means the full contract holds."""

    failures: list[str] = []
    rows = {row["scenario"]: row for row in comparison["rows"]}
    metrics = comparison["metrics"]
    expected = EXPECTED["scenarios"]

    for sid, want in expected.items():
        if sid not in rows:
            failures.append(f"{sid}: missing from comparison rows")
            continue
        row = rows[sid]
        checks = {
            "baseline_outcome": want["baseline_outcome"],
            "governed_outcome": want["governed_outcome"],
            "baseline_protected_work_executed": want["baseline_work_executed"],
            "governed_protected_work_executed": want["governed_work_executed"],
            "nornyx_diagnostic_code": want["diagnostic_code"],
            "emitted_event_types": want["emitted_event_types"],
        }
        for key, expected_value in checks.items():
            if row.get(key) != expected_value:
                failures.append(
                    f"{sid}.{key}: got {row.get(key)!r}, expected {expected_value!r}"
                )
        # A denied runtime scenario must have zero side-effect counter and events
        # that bind to the exact digests.
        if row["emitted_event_types"] and row["contract_digest_bound"] is not True:
            failures.append(f"{sid}: emitted events not all contract-digest bound")
        if row["emitted_event_types"] and row["lock_digest_bound"] is not True:
            failures.append(f"{sid}: emitted events not all lock-digest bound")

    checks = {
        "runtime_business_callables_executed_in_baseline": len(RUNTIME_DENIED),
        "runtime_business_callables_prevented_by_nornyx": len(RUNTIME_DENIED),
        "false_denials_of_allowed_actions": 0,
        "runtime_allowed_completed": len(RUNTIME_ALLOWED),
        "evidence_validation_status": "pass",
        "governed_events_emitted": EXPECTED["governed_events_emitted"],
        "ai_approval_rejection": "AN_ADAPTER_APPROVAL_NON_HUMAN",
        "identity_binding_enforcement": "AN_ADAPTER_IDENTITY_UNKNOWN",
        "stale_lock_detection": "AN_ADAPTER_LOCK_STALE",
    }
    for key, expected_value in checks.items():
        if metrics.get(key) != expected_value:
            failures.append(
                f"metric {key}: got {metrics.get(key)!r}, expected {expected_value!r}"
            )
    if metrics["events_bound_to_contract_digest"] != metrics["governed_events_emitted"]:
        failures.append("not all events bound to the contract digest")
    if metrics["events_bound_to_network_lock_digest"] != metrics["governed_events_emitted"]:
        failures.append("not all events bound to the network-lock digest")
    if metrics["human_approval_enforcement"]["allowed_with_human_approval"] is not True:
        failures.append("human approval was not accepted")
    if metrics["human_approval_enforcement"]["denied_without_approval"] != (
        "AN_ADAPTER_CROSSING_APPROVAL_REQUIRED"
    ):
        failures.append("high-risk action without approval was not denied")
    if metrics["deliberate_bypass_executed_in_both"] is not True:
        failures.append("bypass negative control did not execute in both variants")
    if comparison["workflow"]["outputs_equivalent"] is not True:
        failures.append("workflow outputs not equivalent")
    if metrics["allowed_output_equivalence"] is not True:
        failures.append("allowed outputs not equivalent")
    return failures


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )


def _markdown(comparison: dict) -> str:
    m = comparison["metrics"]
    lines = [
        "# CrewAI x Nornyx 1.7.0 - A/B comparison",
        "",
        f"- Contract digest: `{comparison['contract_digest']}`",
        f"- Network-lock digest: `{comparison['network_lock_digest']}`",
        f"- Evidence validation: **{m['evidence_validation_status']}** "
        f"({m['evidence_records_validated']} events)",
        f"- Allowed-output equivalence (A == B): **{m['allowed_output_equivalence']}**",
        f"- Runtime business callables executed in baseline: "
        f"**{m['runtime_business_callables_executed_in_baseline']}**",
        f"- Runtime business callables prevented by Nornyx (ledger-proven): "
        f"**{m['runtime_business_callables_prevented_by_nornyx']}**",
        f"- Prevention by category: {m['runtime_prevention_by_category']}",
        f"- False denials of allowed actions: "
        f"**{m['false_denials_of_allowed_actions']}**",
        f"- Initialization failure (S12): `{m['initialization_failure']}` · "
        f"bypass executed in both (S14): **{m['deliberate_bypass_executed_in_both']}**",
        "",
        "## Scenario matrix",
        "",
        "| # | Scenario | Kind | Baseline | Governed | Work ran (A/B) | Diagnostic | "
        "Events |",
        "|---|----------|------|----------|----------|----------------|------------|"
        "--------|",
    ]
    for row in comparison["rows"]:
        events = ", ".join(row["emitted_event_types"]) or "-"
        code = row["nornyx_diagnostic_code"] or "-"
        work = (
            f"{'Y' if row['baseline_protected_work_executed'] else 'N'}/"
            f"{'Y' if row['governed_protected_work_executed'] else 'N'}"
        )
        lines.append(
            f"| {row['scenario']} | {row['title']} | {row['kind']} | "
            f"{row['baseline_outcome']} | {row['governed_outcome']} | {work} | "
            f"`{code}` | {events} |"
        )
    lines += [
        "",
        "## Aggregate metrics",
        "",
        "```json",
        json.dumps(m, indent=2),
        "```",
        "",
        "## Limitations",
        "",
    ]
    lines += [f"- {item}" for item in comparison["limitations"]]
    lines.append("")
    return "\n".join(lines)


def run(out_dir: Path, *, benchmark: bool = True) -> dict:
    """Execute both variants and assemble the comparison (already offline-guarded)."""

    plain = PlainSupportNetwork()
    plain_wf = plain.run_workflow()
    plain_scn = plain.run_scenarios()

    governed = GovernedSupportNetwork(out_dir)
    governed_wf = governed.run_workflow()
    governed_scn = governed.run_scenarios()

    events_path = governed.write_events(out_dir / "nornyx_runtime_events.json")
    evidence_report = governed.evidence_report()
    events = governed.kernel.events_payload()["events"]

    allowed_equivalence = (
        plain.allowed_outputs == governed.allowed_outputs
        and plain_wf["output"] == governed_wf["output"]
    )

    rows = build_rows(plain_scn, governed_scn)
    metrics = build_metrics(
        plain_scn, governed_scn,
        allowed_equivalence=allowed_equivalence,
        evidence_report=evidence_report,
        contract_digest=governed.kernel.contract_digest,
        lock_digest=governed.kernel.lock_digest,
        events=events,
    )

    bench = _microbenchmark(out_dir) if benchmark else None
    comparison = {
        "schema": "nornyx.crewai_ab_comparison.v1",
        "network_id": governed.kernel.network_id,
        "subject_revision": governed.kernel.subject_revision,
        "contract_digest": governed.kernel.contract_digest,
        "network_lock_digest": governed.kernel.lock_digest,
        "workflow": {
            "baseline_output": plain_wf["output"],
            "governed_output": governed_wf["output"],
            "outputs_equivalent": plain_wf["output"] == governed_wf["output"],
            "governed_event_types": governed_wf["event_types"],
            "governed_evidence_status": governed_wf["evidence_status"],
        },
        "metrics": metrics,
        "rows": rows,
        "event_artifact_bytes": events_path.stat().st_size,
        "microbenchmark": bench,
        "safety": {
            "note": "Enforced by a loopback-only guard during the run; the guard "
            "raised no violation. External writes are not independently "
            "instrumented and are confined to the --out directory by construction.",
            "ran_under_no_external_io_guard": True,
            "guard_raised_violation": False,
            "api_keys_used": False,
            "external_model_called": False,
        },
        "limitations": LIMITATIONS,
        "environment": capture_environment(),
    }
    contract_failures = verify_contract(comparison)
    comparison["contract_verified"] = not contract_failures
    comparison["contract_failures"] = contract_failures

    _write_json(out_dir / "comparison.json", comparison)
    (out_dir / "comparison.md").write_text(
        _markdown(comparison), encoding="utf-8", newline="\n"
    )
    _write_json(
        out_dir / "plain_results.json",
        {"variant": "plain_crewai", "workflow": plain_wf, "scenarios": plain_scn,
         "ledger": plain.ledger.snapshot()},
    )
    _write_json(
        out_dir / "governed_results.json",
        {"variant": "governed_crewai", "workflow": governed_wf,
         "scenarios": governed_scn, "ledger": governed.ledger.snapshot(),
         "contract_digest": governed.kernel.contract_digest,
         "network_lock_digest": governed.kernel.lock_digest},
    )
    _write_json(out_dir / "nornyx_evidence_report.json", evidence_report)
    _write_json(out_dir / "environment.json", capture_environment())
    return comparison


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(common.EXAMPLE_DIR / "demo_out"))
    parser.add_argument("--no-benchmark", action="store_true")
    args = parser.parse_args(argv)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with no_external_io():
        comparison = run(out_dir, benchmark=not args.no_benchmark)

    ok = comparison["contract_verified"]
    print(
        json.dumps(
            {
                "status": "pass" if ok else "fail",
                "out": str(out_dir),
                "scenarios": len(SCENARIO_IDS),
                "runtime_prevented": comparison["metrics"][
                    "runtime_business_callables_prevented_by_nornyx"
                ],
                "governed_events": comparison["metrics"]["governed_events_emitted"],
                "contract_failures": comparison["contract_failures"],
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
