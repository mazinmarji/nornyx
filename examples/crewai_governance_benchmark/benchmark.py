#!/usr/bin/env python3
"""Run the Nornyx governance A/B benchmark and emit every artifact.

    python examples/crewai_governance_benchmark/benchmark.py --out benchmark_out

Exits non-zero unless every clause of the benchmark contract holds. The contract
is asserted here; the metrics it is asserted against are computed in
``metrics.py`` from actual execution, never read back from the expectations.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

# Run-as-a-script bootstrap. Every module in this benchmark is imported under the
# ``crewai_governance_benchmark`` package name so its generic module names
# (config, scenarios, runtime, report…) never become importable top-level modules
# for the rest of a test session — those names collide with
# examples/crewai_nornyx_comparison. Executing this file directly puts *this*
# directory on sys.path rather than its parent, so add the parent here.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crewai_governance_benchmark import config  # noqa: E402
from crewai_governance_benchmark.config import (  # noqa: E402
    capture_environment,
    no_external_io,
)
from crewai_governance_benchmark.manifest import build_manifest  # noqa: E402
from crewai_governance_benchmark.metrics import build_metrics  # noqa: E402
from crewai_governance_benchmark.report import (  # noqa: E402
    heat_rows,
    render_dashboard,
    render_json,
    render_markdown,
    terminal_summary,
)
from crewai_governance_benchmark.scenarios import BY_ID, SCENARIOS  # noqa: E402

# Evidence diagnostics attributable to defects in the audited packages rather
# than to this benchmark. They are disclosed in FINDINGS.md, reported in full,
# and never removed from the headline validation status. The contract requires
# that *no other* diagnostic appears — a new code fails the run.
KNOWN_UPSTREAM_DEFECT_CODES = frozenset(
    {"AN_EVT_APPROVAL_NON_HUMAN", "AN_EVT_CAPABILITY_NOT_HELD"}
)


def _affected_event_indices(report: dict[str, Any]) -> set[int]:
    """Indices of events carrying a known-upstream-defect diagnostic."""
    indices: set[int] = set()
    for diagnostic in report.get("diagnostics", []):
        if diagnostic.get("code") not in KNOWN_UPSTREAM_DEFECT_CODES:
            continue
        path = str(diagnostic.get("path", ""))
        if path.startswith("events[") and "]" in path:
            try:
                indices.add(int(path[len("events[") : path.index("]")]))
            except ValueError:  # pragma: no cover - defensive
                continue
    return indices


def _checks(metrics: dict, plain: dict, governed: dict) -> list[dict[str, Any]]:
    """The benchmark contract, evaluated against measured results."""
    a, p, e, b = (
        metrics["allowed_path"],
        metrics["prevention"],
        metrics["evidence"],
        metrics["boundary"],
    )
    x = metrics["execution_integrity"]
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(ok), "detail": detail})

    check(
        "allowed_path_output_equivalence",
        a["business_output_equivalence"],
        "Both variants produce identical business and crew output on every allowed path.",
    )
    check(
        "no_false_denials",
        a["false_denials_of_valid_actions"] == 0,
        f"{a['false_denials_of_valid_actions']} valid action(s) wrongly refused.",
    )
    check(
        "no_false_allows",
        p["false_allows_on_governed_path"] == 0,
        f"{p['false_allows_on_governed_path']} prohibited callable(s) still executed under governance.",
    )
    check(
        "baseline_executes_prohibited_actions",
        p["prohibited_callables_executed_in_baseline"] > 0,
        f"The baseline executed {p['prohibited_callables_executed_in_baseline']} prohibited callable(s).",
    )
    check(
        "governance_prevents_every_prohibited_action",
        p["prohibited_callables_prevented_by_nornyx"]
        == p["prohibited_callables_executed_in_baseline"],
        f"{p['prohibited_callables_prevented_by_nornyx']} prevented of "
        f"{p['prohibited_callables_executed_in_baseline']} executed in the baseline.",
    )

    # Per-scenario mechanical proof.
    for scenario in SCENARIOS:
        g = governed[scenario.id]
        completed = int(g["business_side_effects_completed"])
        check(
            f"side_effects[{scenario.id}]",
            completed == scenario.expected_governed_side_effects,
            f"expected {scenario.expected_governed_side_effects} completed side effect(s), got {completed}.",
        )
        check(
            f"diagnostic[{scenario.id}]",
            (g.get("diagnostic_code") or "") == scenario.expected_code,
            f"expected {scenario.expected_code!r}, got {g.get('diagnostic_code')!r}.",
        )
        if scenario.expected_governed_side_effects == 1:
            check(
                f"exactly_once[{scenario.id}]",
                int(g["business_callable_attempts"]) == 1 and completed == 1,
                f"ALLOW must execute the callable exactly once; attempts="
                f"{g['business_callable_attempts']}, completions={completed}.",
            )

    check(
        "decisions_recorded_before_execution",
        not x["ordering_violations"],
        f"ordering violations: {x['ordering_violations'] or 'none'}.",
    )
    check(
        "retries_reenter_governance",
        int(governed["S14"]["business_callable_attempts"])
        <= int(governed["S14"]["decisions_recorded"]),
        f"S14 entered the callable {governed['S14']['business_callable_attempts']} time(s) "
        f"with {governed['S14']['decisions_recorded']} recorded decision(s); every entry "
        f"must have its own authorization.",
    )
    check(
        "no_success_observation_without_success",
        x["observations_match_completed_side_effects"],
        f"{x['post_success_observations_recorded']} tool_invoked observation(s) vs "
        f"{x['completed_side_effects_on_governed_surfaces']} governed-surface completion(s).",
    )
    check(
        "all_events_bound_to_contract_digest",
        e["all_events_bound_to_contract_digest"],
        f"{e['events_bound_to_contract_digest']}/{e['events_emitted']} bound.",
    )
    check(
        "all_events_bound_to_lock_digest",
        e["all_events_bound_to_lock_digest"],
        f"{e['events_bound_to_lock_digest']}/{e['events_emitted']} bound.",
    )
    unexpected = sorted(
        {d["code"] for d in e["diagnostics"] if d["code"] not in KNOWN_UPSTREAM_DEFECT_CODES}
    )
    check(
        "no_unexpected_evidence_diagnostics",
        not unexpected,
        f"unexpected diagnostics: {unexpected or 'none'}.",
    )
    check(
        "bypass_control_visible_and_uncounted",
        b["bypass_visible_and_uncounted"],
        "The unwrapped tool executes in both variants and is not counted as prevented.",
    )
    check(
        "application_rule_refused_in_both",
        b["application_rule_refused_in_both"],
        "The application's own business rule refused identically in both variants.",
    )
    check(
        "unsupported_surfaces_disclosed",
        len(b["unsupported_or_unwrapped_surfaces"]) > 0,
        f"{len(b['unsupported_or_unwrapped_surfaces'])} surface(s) declared unsupported.",
    )
    return checks


def _verdict(checks: list[dict], metrics: dict) -> dict[str, Any]:
    failed = [c for c in checks if not c["passed"]]
    evidence_ok = metrics["evidence"]["validation_status"] == "pass"
    if failed:
        return {
            "verdict": "NO_GO",
            "summary": (
                f"{len(failed)} benchmark-contract check(s) failed; the A/B result is not "
                f"trustworthy as reported."
            ),
            "blocking": [f"{c['check']}: {c['detail']}" for c in failed],
        }
    if not evidence_ok:
        codes = sorted({d["code"] for d in metrics["evidence"]["diagnostics"]})
        return {
            "verdict": "CONDITIONAL_GO",
            "summary": (
                "Every A/B and side-effect claim in this report is mechanically verified: "
                "valid actions were allowed with identical output, every prohibited callable "
                "the baseline executed was prevented with zero side effects, and every event "
                "binds the exact contract and lock digest. The full evidence stream does not "
                "validate, because two mandatory scenarios each reproduce a real defect in "
                f"the audited packages ({', '.join(codes)}). Those defects block a clean "
                "evidence claim until fixed upstream; they do not affect any enforcement result."
            ),
            "blocking": [],
        }
    return {
        "verdict": "GO",
        "summary": (
            "Every benchmark-contract check passed and the full evidence stream validates "
            "against the exact contract and lock revision."
        ),
        "blocking": [],
    }


def run(out_dir: Path, only: tuple[str, ...] | None = None) -> int:
    from crewai_governance_benchmark import variant_governed
    from crewai_governance_benchmark import variant_plain

    out_dir.mkdir(parents=True, exist_ok=True)
    timing: dict[str, float] = {}

    with no_external_io():
        start = time.perf_counter()
        plain, plain_ledger = variant_plain.run(only=only)
        timing["plain_variant_seconds"] = time.perf_counter() - start

        start = time.perf_counter()
        governed, governed_ledger, recorder, authorizer = variant_governed.run(out_dir, only=only)
        timing["governed_variant_seconds"] = time.perf_counter() - start

    stream = recorder.stream()
    events = stream["events"]

    start = time.perf_counter()
    evidence_report = recorder.validate()
    timing["evidence_validation_seconds"] = time.perf_counter() - start

    # Separate the one-time control-plane cost (loading and lock-verifying the
    # contract) from the per-decision cost, because reporting only the variant
    # totals would attribute a startup cost to every governed call.
    from nornyx.agentic import CapabilityRequest, EvaluationContext

    start = time.perf_counter()
    variant_governed.load()
    timing["authorizer_load_seconds"] = time.perf_counter() - start

    probe_ctx = EvaluationContext(config.AS_OF, authorizer.subject_revision)
    probe_req = CapabilityRequest("identity.intake_agent", "read_customer_case")
    iterations = 1000
    start = time.perf_counter()
    for _ in range(iterations):
        authorizer.evaluate(probe_req, context=probe_ctx)
    elapsed = time.perf_counter() - start
    timing["mean_evaluate_milliseconds"] = (elapsed / iterations) * 1000.0

    # Re-validate with only the events affected by disclosed upstream defects
    # removed. Reported as a diagnostic aid, never as the headline status.
    affected = _affected_event_indices(evidence_report)
    if affected:
        from nornyx.agentic import validate_runtime_events
        from nornyx.agentic.authz import _thaw

        reduced = dict(stream)
        reduced["events"] = [e for i, e in enumerate(events) if i not in affected]
        reduced_report = validate_runtime_events(
            _thaw(authorizer._document),
            authorizer._composition,
            _thaw(authorizer._lock_payload),
            reduced,
        )
    else:
        reduced_report = evidence_report

    if only:
        _print_focus(only, plain, governed)
        return 0

    adapter = variant_governed.adapter_surface()
    env = capture_environment()
    metrics = build_metrics(
        plain,
        governed,
        evidence_report=evidence_report,
        evidence_report_excluding_known_defects=reduced_report,
        events=events,
        contract_digest=authorizer.contract_digest,
        lock_digest=authorizer.network_lock_digest,
        adapter_surface=adapter,
        timing=timing,
    )
    checks = _checks(metrics, plain, governed)
    verdict = _verdict(checks, metrics)
    rows = heat_rows(plain, governed, metrics)

    payload = {
        "benchmark": "nornyx.crewai_governance_ab.v1",
        "verdict": verdict,
        "environment": env,
        "adapter_surface": adapter,
        "metrics": metrics,
        "contract_checks": checks,
        "scenarios": [
            {
                "id": s.id,
                "title": s.title,
                "stage": s.stage,
                "category": s.category,
                "risk": s.risk,
                "crewai_role": s.role,
                "capability_ref": s.capability_ref,
                "expected_effect": s.expected_effect,
                "expected_code": s.expected_code,
                "interpretation": s.interpretation,
                "caveat": s.caveat,
                "baseline": plain[s.id],
                "governed": governed[s.id],
            }
            for s in SCENARIOS
        ],
        "heat_map": rows,
    }

    (out_dir / "benchmark.json").write_text(render_json(payload), encoding="utf-8")
    (out_dir / "benchmark.md").write_text(
        render_markdown(metrics, rows, env, adapter, verdict), encoding="utf-8"
    )
    (out_dir / "dashboard.html").write_text(
        render_dashboard(metrics, rows, env, adapter, verdict), encoding="utf-8"
    )
    (out_dir / "environment.json").write_text(render_json(env), encoding="utf-8")
    (out_dir / "plain_results.json").write_text(
        render_json({"results": plain, "ledger": plain_ledger.timeline()}), encoding="utf-8"
    )
    (out_dir / "governed_results.json").write_text(
        render_json({"results": governed, "ledger": governed_ledger.timeline()}), encoding="utf-8"
    )
    (out_dir / "nornyx_runtime_events.json").write_text(render_json(stream), encoding="utf-8")
    (out_dir / "nornyx_evidence_report.json").write_text(
        render_json(evidence_report), encoding="utf-8"
    )
    (out_dir / "validation_manifest.json").write_text(
        render_json(
            build_manifest(
                out_dir,
                contract_digest=authorizer.contract_digest,
                lock_digest=authorizer.network_lock_digest,
            )
        ),
        encoding="utf-8",
    )

    print(terminal_summary(metrics, rows, env))
    failed = [c for c in checks if not c["passed"]]
    if failed:
        print("  BENCHMARK CONTRACT FAILED\n" + "  " + "-" * 74)
        for c in failed:
            print(f"  x {c['check']}: {c['detail']}")
        print()
    else:
        print(f"  benchmark contract: {len(checks)} checks, all passed")
    print(f"  verdict: {verdict['verdict']}")
    print(f"  artifacts: {out_dir}\n")
    return 1 if failed else 0


def _print_focus(only: tuple[str, ...], plain: dict, governed: dict) -> None:
    for sid in only:
        s = BY_ID[sid]
        print(f"\n=== {s.id} — {s.title} ({s.stage}/{s.category}) ===")
        print(f"  expected: {s.expected_effect} / {s.expected_code}, "
              f"{s.expected_governed_side_effects} governed side effect(s)")
        for label, row in (("baseline", plain[sid]), ("governed", governed[sid])):
            print(f"  {label:<9} outcome={row['outcome']} "
                  f"attempts={row['business_callable_attempts']} "
                  f"completed={row['business_side_effects_completed']} "
                  f"diagnostic={row.get('diagnostic_code')}")
            print(f"            output={row['business_output']!r}")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="benchmark_out", help="artifact output directory")
    parser.add_argument(
        "--scenario",
        action="append",
        metavar="ID",
        help="run only these scenarios (repeatable), e.g. --scenario S03",
    )
    args = parser.parse_args(argv)
    only = tuple(args.scenario) if args.scenario else None
    if only:
        unknown = [sid for sid in only if sid not in BY_ID]
        if unknown:
            parser.error(f"unknown scenario id(s): {', '.join(unknown)}")
    return run(Path(args.out).resolve(), only)


if __name__ == "__main__":
    sys.exit(main())
