"""CI: machine-check the generated A/B comparison artifacts (not just exit codes).

Usage::

    python examples/crewai_nornyx_comparison/ci_check_artifacts.py <out_dir>

Exits non-zero with a description if any expected guarantee is missing from the
generated ``comparison.json``, ``nornyx_evidence_report.json``, or
``governed_results.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Runtime scenarios whose governed business callable must never run.
DENIED = ("S2", "S3", "S5", "S6", "S7", "S9", "S10", "S11", "S13")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: ci_check_artifacts.py <out_dir>")
        return 2
    out = Path(argv[0])
    comparison = json.loads((out / "comparison.json").read_text(encoding="utf-8"))
    report = json.loads((out / "nornyx_evidence_report.json").read_text(encoding="utf-8"))
    governed = json.loads((out / "governed_results.json").read_text(encoding="utf-8"))
    metrics = comparison["metrics"]

    problems: list[object] = []
    if not comparison.get("contract_verified"):
        problems.append({"contract_failures": comparison.get("contract_failures")})
    if report.get("status") != "pass":
        problems.append({"evidence_report_status": report.get("status")})
    if metrics["evidence_validation_status"] != "pass":
        problems.append("evidence metric not pass")
    total = metrics["governed_events_emitted"]
    if metrics["events_bound_to_contract_digest"] != total:
        problems.append("not all events bound to contract digest")
    if metrics["events_bound_to_network_lock_digest"] != total:
        problems.append("not all events bound to lock digest")
    if metrics["runtime_business_callables_prevented_by_nornyx"] < 1:
        problems.append("no runtime prevention recorded")
    if metrics["false_denials_of_allowed_actions"] != 0:
        problems.append("false denials present")
    if metrics["allowed_output_equivalence"] is not True:
        problems.append("allowed outputs not equivalent")

    ledger = governed.get("ledger", {})
    for sid in DENIED:
        if sid in ledger:  # a denied scenario's business callable ran under Nornyx
            problems.append({sid: "governed business work executed"})

    if problems:
        print("ARTIFACT CHECK FAILED:")
        print(json.dumps(problems, indent=2, sort_keys=True))
        return 1
    print(
        "ARTIFACT CHECK OK: contract_verified, evidence pass, "
        f"{total} events digest-bound, "
        f"{metrics['runtime_business_callables_prevented_by_nornyx']} runtime "
        "denials ledger-zero."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
