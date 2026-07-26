"""Metric derivation. Every number here is computed from actual execution.

Nothing in this module reads an expected value. ``scenarios.py`` carries the
benchmark *contract* (what should happen); ``benchmark.py`` asserts the derived
metrics against it and exits non-zero on any mismatch. Keeping derivation and
assertion apart is what stops a metric from being quietly hardcoded to the
number that makes the report look good.

Counting rules, stated once so the report cannot drift from them:

* A **prevention** is counted only when the baseline actually executed the
  business callable and the governed run did not. A scenario the baseline never
  executed is not something Nornyx prevented.
* Runtime-stage and binding-stage preventions are reported separately and never
  summed into one headline number.
* The bypass negative control and the application-rule fairness control are
  excluded from every prevention metric by construction.
"""

from __future__ import annotations

from typing import Any

from crewai_governance_benchmark.scenarios import (
    APPLICATION,
    BINDING,
    BYPASS,
    EQUIVALENCE_IDS,
    LOAD,
    RUNTIME,
    SCENARIOS,
    BY_ID,
)


def _executed(row: dict[str, Any]) -> bool:
    return int(row.get("business_side_effects_completed", 0)) > 0


def build_metrics(
    plain: dict[str, dict[str, Any]],
    governed: dict[str, dict[str, Any]],
    *,
    evidence_report: dict[str, Any],
    evidence_report_excluding_known_defects: dict[str, Any],
    events: list[dict[str, Any]],
    contract_digest: str,
    lock_digest: str,
    adapter_surface: dict[str, Any],
    timing: dict[str, float],
) -> dict[str, Any]:
    # -- allowed-path equivalence -------------------------------------------
    equivalence_rows = []
    for sid in EQUIVALENCE_IDS:
        p, g = plain[sid], governed[sid]
        equivalence_rows.append(
            {
                "scenario": sid,
                "baseline_business_output": p["business_output"],
                "governed_business_output": g["business_output"],
                "business_output_equal": p["business_output"] == g["business_output"],
                "crew_output_equal": p["crew_output"] == g["crew_output"],
            }
        )
    equivalence = bool(equivalence_rows) and all(
        r["business_output_equal"] and r["crew_output_equal"] for r in equivalence_rows
    )

    # -- valid actions -------------------------------------------------------
    valid_ids = [s.id for s in SCENARIOS if s.id in EQUIVALENCE_IDS]
    valid_allowed = [sid for sid in valid_ids if governed[sid]["outcome"] == "allowed"]
    false_denials = [sid for sid in valid_ids if governed[sid]["outcome"] != "allowed"]

    # -- prevention ----------------------------------------------------------
    prohibited = [s for s in SCENARIOS if s.counts_as_prevention]
    baseline_executed = [s.id for s in prohibited if _executed(plain[s.id])]
    prevented = [
        s.id
        for s in prohibited
        if _executed(plain[s.id]) and not _executed(governed[s.id])
    ]
    false_allows = [s.id for s in prohibited if _executed(governed[s.id])]

    by_category: dict[str, int] = {}
    for sid in prevented:
        if BY_ID[sid].stage == RUNTIME:
            category = BY_ID[sid].category
            by_category[category] = by_category.get(category, 0) + 1

    runtime_prevented = [sid for sid in prevented if BY_ID[sid].stage == RUNTIME]
    binding_prevented = [sid for sid in prevented if BY_ID[sid].stage == BINDING]

    # -- ordering and observation integrity ----------------------------------
    ordering_checked = [
        sid for sid in governed if governed[sid]["decision_recorded_before_execution"] is not None
    ]
    ordering_ok = [
        sid for sid in ordering_checked if governed[sid]["decision_recorded_before_execution"]
    ]
    tool_invoked = sum(1 for e in events if e.get("event_type") == "tool_invoked")
    completed_side_effects = sum(
        int(governed[s.id]["business_side_effects_completed"]) for s in SCENARIOS
    )
    # The bypass control completes a side effect while emitting nothing — that is
    # its entire point. Observations can only be reconciled against work that
    # actually crossed the governed surface.
    completed_on_governed_surfaces = sum(
        int(governed[s.id]["business_side_effects_completed"])
        for s in SCENARIOS
        if s.stage != BYPASS
    )
    total_decisions = sum(int(governed[s.id]["decisions_recorded"]) for s in SCENARIOS)

    # -- evidence binding ----------------------------------------------------
    bound_contract = sum(1 for e in events if e.get("contract_digest") == contract_digest)
    bound_lock = sum(1 for e in events if e.get("network_lock_digest") == lock_digest)

    unsupported = [
        s for s in adapter_surface.get("surfaces", []) if s["status"] != "wrapped"
    ]
    wrapped = [s for s in adapter_surface.get("surfaces", []) if s["status"] == "wrapped"]

    return {
        "totals": {
            "scenarios": len(SCENARIOS),
            "runtime_stage": sum(1 for s in SCENARIOS if s.stage == RUNTIME),
            "binding_stage": sum(1 for s in SCENARIOS if s.stage == BINDING),
            "load_stage": sum(1 for s in SCENARIOS if s.stage == LOAD),
            "bypass_control": sum(1 for s in SCENARIOS if s.stage == BYPASS),
            "application_control": sum(1 for s in SCENARIOS if s.stage == APPLICATION),
        },
        "allowed_path": {
            "business_output_equivalence": equivalence,
            "valid_actions_total": len(valid_ids),
            "valid_actions_allowed": len(valid_allowed),
            "false_denials_of_valid_actions": len(false_denials),
            "false_denial_scenarios": false_denials,
            "comparisons": equivalence_rows,
        },
        "prevention": {
            "prohibited_callables_executed_in_baseline": len(baseline_executed),
            "prohibited_callables_prevented_by_nornyx": len(prevented),
            "runtime_stage_preventions": len(runtime_prevented),
            "runtime_stage_prevention_scenarios": runtime_prevented,
            "binding_stage_preventions": len(binding_prevented),
            "binding_stage_prevention_scenarios": binding_prevented,
            "false_allows_on_governed_path": len(false_allows),
            "false_allow_scenarios": false_allows,
            "runtime_prevention_by_category": dict(sorted(by_category.items())),
        },
        "side_effects": {
            "baseline_total": sum(
                int(plain[s.id]["business_side_effects_completed"]) for s in SCENARIOS
            ),
            "governed_total": completed_side_effects,
            "baseline_by_scenario": {
                s.id: int(plain[s.id]["business_side_effects_completed"]) for s in SCENARIOS
            },
            "governed_by_scenario": {
                s.id: int(governed[s.id]["business_side_effects_completed"]) for s in SCENARIOS
            },
        },
        "execution_integrity": {
            "total_decisions_recorded": total_decisions,
            "scenarios_with_ordering_checkable": len(ordering_checked),
            "scenarios_with_decision_before_execution": len(ordering_ok),
            "ordering_violations": [s for s in ordering_checked if s not in ordering_ok],
            "post_success_observations_recorded": tool_invoked,
            "completed_side_effects": completed_side_effects,
            "completed_side_effects_on_governed_surfaces": completed_on_governed_surfaces,
            "observations_match_completed_side_effects": (
                tool_invoked == completed_on_governed_surfaces
            ),
            "governed_tool_invocations": {
                s.id: int(governed[s.id].get("governed_tool_invocations", 0)) for s in SCENARIOS
            },
        },
        "evidence": {
            "events_emitted": len(events),
            "validation_status": evidence_report["status"],
            "records_validated": evidence_report.get("event_count"),
            "diagnostics": [
                {
                    "code": d.get("code"),
                    "path": d.get("path"),
                    "message": d.get("message"),
                }
                for d in evidence_report.get("diagnostics", [])
            ],
            "validation_status_excluding_known_upstream_defects": (
                evidence_report_excluding_known_defects["status"]
            ),
            "events_bound_to_contract_digest": bound_contract,
            "events_bound_to_lock_digest": bound_lock,
            "all_events_bound_to_contract_digest": bound_contract == len(events),
            "all_events_bound_to_lock_digest": bound_lock == len(events),
            "contract_digest": contract_digest,
            "network_lock_digest": lock_digest,
        },
        "boundary": {
            "bypass_executed_in_baseline": _executed(plain["S15"]),
            "bypass_executed_under_governance": _executed(governed["S15"]),
            "bypass_visible_and_uncounted": (
                _executed(plain["S15"])
                and _executed(governed["S15"])
                and "S15" not in prevented
            ),
            "application_rule_refused_in_both": (
                not _executed(plain["S18"]) and not _executed(governed["S18"])
            ),
            "wrapped_surfaces": [s["surface"] for s in wrapped],
            "unsupported_or_unwrapped_surfaces": [
                {"surface": s["surface"], "status": s["status"], "reason": s["reason"]}
                for s in unsupported
            ],
        },
        "timing_local_microbenchmark_only": {
            **timing,
            "disclaimer": (
                "Wall-clock seconds for this local, offline, single-process run. "
                "Not a production latency measurement and not a throughput claim."
            ),
        },
    }
