#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nornyx.kpi_metrics import build_kpi_result, write_kpi_result  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local Nornyx KPI benchmark.")
    parser.add_argument(
        "--evidence-dir",
        default="docs/qa/evidence/GOAL-031",
        help="Evidence directory to score.",
    )
    parser.add_argument(
        "--out",
        default="docs/metrics/results/latest-kpi-result.json",
        help="Output JSON path.",
    )
    parser.add_argument("--no-write", action="store_true", help="Print result but do not write output file.")
    args = parser.parse_args()

    evidence_dir = ROOT / args.evidence_dir
    result = build_kpi_result(ROOT, evidence_dir=evidence_dir)
    print(json.dumps(result, indent=2))

    if not args.no_write:
        write_kpi_result(ROOT / args.out, result)
        print(f"Wrote {args.out}")

    # This is an informational benchmark. It fails only if the repo is extremely immature.
    score = result["repo_kpis"]["agentic_dev_readiness_score"]
    return 0 if score >= 40 else 1


if __name__ == "__main__":
    raise SystemExit(main())
