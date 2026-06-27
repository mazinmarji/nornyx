#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nornyx.kpi_metrics import score_evidence_dir  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a Nornyx evidence directory.")
    parser.add_argument("evidence_dir", help="Evidence directory, for example docs/qa/evidence/GOAL-031")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="Return non-zero if score percent is below this threshold.",
    )
    args = parser.parse_args()

    evidence_dir = (ROOT / args.evidence_dir).resolve() if not Path(args.evidence_dir).is_absolute() else Path(args.evidence_dir)
    result = score_evidence_dir(evidence_dir)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Evidence: {result['evidence_dir']}")
        print(f"Score: {result['score']}/{result['max_score']} ({result['percent']}%)")
        print(f"Status: {result['status']}")
        if result["missing"]:
            print("Missing:")
            for item in result["missing"]:
                print(f"  - {item['pattern']} ({item['points']}): {item['description']}")

    if args.fail_under is not None and result["percent"] < args.fail_under:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
