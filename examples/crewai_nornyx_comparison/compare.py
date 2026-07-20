"""Run both variants and emit the A/B comparison artifacts.

Usage::

    python examples/crewai_nornyx_comparison/compare.py --out demo_out

Produces, under ``--out``:

* ``comparison.json``          full machine-readable comparison
* ``comparison.md``            human-readable comparison report
* ``plain_results.json``       Variant A per-scenario results
* ``governed_results.json``    Variant B per-scenario results
* ``nornyx_runtime_events.json`` the governed evidence stream
* ``nornyx_evidence_report.json`` Nornyx validation of that stream
* ``environment.json``         the exact runtime

Everything runs offline under a loopback-only network guard: no API key, no
external model, no DNS, no external socket, no subprocess, no shell.
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
from scenarios import SCENARIO_IDS, build_metrics, build_rows  # noqa: E402

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

LIMITATIONS = [
    "Nornyx governs declared authority and supplied evidence; it does not operate "
    "CrewAI, execute the model, or authenticate agents.",
    "Enforcement is cooperative: code that bypasses the adapter is not intercepted "
    "(scenario S14).",
    "Evidence validation proves content binding to the exact contract and lock, not "
    "that an emitted event is truthful.",
    "The CrewAI adapter is unpackaged in Nornyx 1.7.0; it lives under integrations/.",
    "Timing figures are a local microbenchmark, not a production performance claim.",
]


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _microbenchmark(out_dir: Path, samples: int = 200, init_samples: int = 10) -> dict:
    """A local microbenchmark: setup time and per-call governance overhead.

    Setup (kernel load) and per-call overhead are measured separately. These are
    kernel-level operations, not Crew.kickoff() timings, and are labelled as a
    local microbenchmark only.
    """

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


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _markdown(comparison: dict) -> str:
    metrics = comparison["metrics"]
    lines = [
        "# CrewAI x Nornyx 1.7.0 — A/B comparison",
        "",
        f"- Contract digest: `{comparison['contract_digest']}`",
        f"- Network-lock digest: `{comparison['network_lock_digest']}`",
        f"- Evidence validation: **{metrics['evidence_validation_status']}** "
        f"({metrics['evidence_records_validated']} events)",
        f"- Allowed-output equivalence (A == B): "
        f"**{metrics['allowed_output_equivalence']}**",
        f"- Unauthorized actions executed in baseline: "
        f"**{metrics['unauthorized_actions_executed_in_baseline']}**",
        f"- Unauthorized actions prevented by Nornyx: "
        f"**{metrics['unauthorized_actions_prevented_by_nornyx']}**",
        f"- False denials of allowed actions: "
        f"**{metrics['false_denials_of_allowed_actions']}**",
        "",
        "## Scenario matrix",
        "",
        "| # | Scenario | Baseline | Governed | Work ran (A/B) | Diagnostic | "
        "Events | Interpretation |",
        "|---|----------|----------|----------|----------------|------------|"
        "--------|----------------|",
    ]
    for row in comparison["rows"]:
        events = ", ".join(row["emitted_event_types"]) or "—"
        code = row["nornyx_diagnostic_code"] or "—"
        work = (
            f"{'Y' if row['baseline_protected_work_executed'] else 'N'}/"
            f"{'Y' if row['governed_protected_work_executed'] else 'N'}"
        )
        lines.append(
            f"| {row['scenario']} | {row['title']} | {row['baseline_outcome']} | "
            f"{row['governed_outcome']} | {work} | `{code}` | {events} | "
            f"{row['interpretation']} |"
        )
    lines += [
        "",
        "## Aggregate metrics",
        "",
        "```json",
        json.dumps(metrics, indent=2),
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
        plain_scn,
        governed_scn,
        allowed_equivalence=allowed_equivalence,
        evidence_report=evidence_report,
        contract_digest=governed.kernel.contract_digest,
        lock_digest=governed.kernel.lock_digest,
        events=events,
    )

    environment = capture_environment()
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
            "api_keys_used": False,
            "external_model_called": False,
            "network_used": False,
            "subprocess_used": False,
            "external_writes_outside_out_dir": False,
            "real_customer_data": False,
        },
        "limitations": LIMITATIONS,
    }

    _write_json(out_dir / "comparison.json", comparison)
    (out_dir / "comparison.md").write_text(_markdown(comparison), encoding="utf-8",
                                           newline="\n")
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
    _write_json(out_dir / "environment.json", environment)
    return comparison


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(common.EXAMPLE_DIR / "demo_out"))
    parser.add_argument(
        "--no-benchmark", action="store_true", help="skip the local microbenchmark"
    )
    args = parser.parse_args(argv)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with no_external_io():
        comparison = run(out_dir, benchmark=not args.no_benchmark)

    metrics = comparison["metrics"]
    print(
        json.dumps(
            {
                "status": "pass"
                if (
                    metrics["evidence_validation_status"] == "pass"
                    and metrics["false_denials_of_allowed_actions"] == 0
                    and metrics["allowed_output_equivalence"] is True
                )
                else "review",
                "out": str(out_dir),
                "scenarios": len(SCENARIO_IDS),
                "unauthorized_executed_in_baseline": metrics[
                    "unauthorized_actions_executed_in_baseline"
                ],
                "unauthorized_prevented_by_nornyx": metrics[
                    "unauthorized_actions_prevented_by_nornyx"
                ],
                "governed_events": metrics["governed_events_emitted"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
