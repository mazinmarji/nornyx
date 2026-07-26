#!/usr/bin/env python3
"""Run the Nornyx governance A/B benchmark and emit every artifact.

    python examples/crewai_governance_benchmark/benchmark.py --out benchmark_out

Exits non-zero unless every clause of the benchmark contract holds **and** the
complete runtime-event stream validates. The contract is asserted here; the
metrics it is asserted against are computed in ``metrics.py`` from actual
execution, never read back from the expectations.

The verdict is ``GO`` or ``NO_GO``. There is no conditional verdict and no
allow-list of tolerated evidence diagnostics: the authoritative evidence claim is
the status of the full stream, never a filtered or reduced one.

``--scenario`` reproduces selected rows and asserts the same per-scenario clauses
the full run does, so a focused spot-check also exits non-zero on a mismatch.
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
from crewai_governance_benchmark.manifest import build_manifest, candidate_digest  # noqa: E402
from crewai_governance_benchmark.metrics import build_metrics  # noqa: E402
from crewai_governance_benchmark.report import (  # noqa: E402
    heat_rows,
    render_dashboard,
    render_json,
    render_markdown,
    terminal_summary,
)
from crewai_governance_benchmark.scenarios import BY_ID, SCENARIOS  # noqa: E402


def _scenario_checks(scenario: Any, governed: dict) -> list[dict[str, Any]]:
    """The per-scenario clauses of the contract: side effects, code, exactly-once.

    Shared by the full run and by ``--scenario``, so a focused run is held to
    exactly the same expectations as the row it reproduces — a focused run that
    printed its outcome without asserting it would let a reviewer "confirm" a
    scenario that had in fact changed behavior.
    """
    g = governed[scenario.id]
    completed = int(g["business_side_effects_completed"])
    checks: list[dict[str, Any]] = [
        {
            "check": f"side_effects[{scenario.id}]",
            "passed": completed == scenario.expected_governed_side_effects,
            "detail": (
                f"expected {scenario.expected_governed_side_effects} completed "
                f"side effect(s), got {completed}."
            ),
        },
        {
            "check": f"diagnostic[{scenario.id}]",
            "passed": (g.get("diagnostic_code") or "") == scenario.expected_code,
            "detail": f"expected {scenario.expected_code!r}, got {g.get('diagnostic_code')!r}.",
        },
    ]
    if scenario.expected_governed_side_effects == 1:
        checks.append(
            {
                "check": f"exactly_once[{scenario.id}]",
                "passed": int(g["business_callable_attempts"]) == 1 and completed == 1,
                "detail": (
                    f"ALLOW must execute the callable exactly once; attempts="
                    f"{g['business_callable_attempts']}, completions={completed}."
                ),
            }
        )
    return checks


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
        checks.extend(_scenario_checks(scenario, governed))

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
    # The authoritative evidence claim: the FULL stream, with nothing filtered,
    # excluded, or reduced. There is no allow-list of tolerated diagnostics.
    check(
        "full_evidence_stream_validates",
        e["validation_status"] == "pass",
        f"full-stream validation status is {e['validation_status']!r}.",
    )
    diagnostic_codes = sorted({d["code"] for d in e["diagnostics"]})
    check(
        "no_evidence_diagnostics",
        not diagnostic_codes,
        f"evidence diagnostics: {diagnostic_codes or 'none'}.",
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
    """``GO`` only when every contract check passes and the full stream validates.

    There is no conditional verdict. A verdict that normalizes a known defect
    reads as a pass to everyone who does not also read the footnote, so the two
    ways this benchmark can be untrustworthy — a failed contract clause, or an
    evidence stream that does not validate in full — both produce ``NO_GO``.
    """
    failed = [c for c in checks if not c["passed"]]
    evidence_ok = metrics["evidence"]["validation_status"] == "pass"
    blocking = [f"{c['check']}: {c['detail']}" for c in failed]
    if not evidence_ok and not any(
        c["check"] == "full_evidence_stream_validates" for c in failed
    ):  # pragma: no cover - defence in depth if the check is ever removed
        blocking.append(
            "full_evidence_stream_validates: full-stream validation status is "
            f"{metrics['evidence']['validation_status']!r}."
        )
    if blocking:
        reasons = []
        if failed:
            reasons.append(f"{len(failed)} benchmark-contract check(s) failed")
        if not evidence_ok:
            codes = sorted({d["code"] for d in metrics["evidence"]["diagnostics"]})
            reasons.append(
                "the full evidence stream does not validate ("
                + (", ".join(codes) or "no diagnostic reported")
                + ")"
            )
        return {
            "verdict": "NO_GO",
            "summary": (
                " and ".join(reasons)
                + "; the A/B result is not trustworthy as reported."
            ),
            "blocking": blocking,
        }
    return {
        "verdict": "GO",
        "summary": (
            "Every benchmark-contract check passed and the full evidence stream validates "
            "against the exact contract and lock revision, with zero diagnostics."
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

    # A focused run reproduces selected rows and is held to their contract; it
    # emits no artifacts, so the timing probes and report rendering are skipped.
    if only:
        return _print_focus(only, plain, governed)

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

    adapter = variant_governed.adapter_surface()
    env = capture_environment()
    metrics = build_metrics(
        plain,
        governed,
        evidence_report=evidence_report,
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
        # Binds this result to the exact candidate tree that produced it: the
        # governance inputs plus every benchmark source file. Reproducible on any
        # machine, so a reviewer can tell in one comparison whether a committed
        # result and their own run come from the same code and contract.
        "candidate_digest": candidate_digest(),
        "results_are_a_snapshot": (
            "This file is a snapshot of one run. It is not continuously verified and can go "
            "stale the moment the candidate changes; compare candidate_digest, and rerun "
            "the benchmark rather than trusting this snapshot."
        ),
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

    digest = payload["candidate_digest"]
    (out_dir / "benchmark.json").write_text(render_json(payload), encoding="utf-8")
    (out_dir / "benchmark.md").write_text(
        render_markdown(metrics, rows, env, adapter, verdict, digest), encoding="utf-8"
    )
    (out_dir / "dashboard.html").write_text(
        render_dashboard(metrics, rows, env, adapter, verdict, digest), encoding="utf-8"
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
    # Non-zero on anything short of GO: a failed contract clause, or a full
    # evidence stream that does not validate.
    return 0 if (not failed and verdict["verdict"] == "GO") else 1


def _print_focus(only: tuple[str, ...], plain: dict, governed: dict) -> int:
    """Print the selected scenarios and return non-zero if any differs from its contract."""
    failed: list[dict[str, Any]] = []
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
        checks = _scenario_checks(s, governed)
        for c in checks:
            print(f"  {'ok  ' if c['passed'] else 'FAIL'} {c['check']}: {c['detail']}")
        failed.extend(c for c in checks if not c["passed"])
    print()
    if failed:
        print(f"  {len(failed)} focused contract check(s) failed")
        print()
        return 1
    return 0


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
