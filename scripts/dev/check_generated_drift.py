#!/usr/bin/env python3
"""Check that generated Nornyx artifacts match committed drift baselines.

This gate is local and deterministic. It writes only when
`--update-baseline` is passed explicitly.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nornyx.generation_drift import check_generated_drift, format_drift_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Check generated Nornyx artifact drift.")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Regenerate committed drift baselines intentionally.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    report = check_generated_drift(ROOT, update_baseline=args.update_baseline)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_drift_report(report))
        if not args.update_baseline and report["status"] != "pass":
            print("\nRun with --update-baseline only when generated output changes intentionally.")

    return 0 if report["status"] in {"pass", "updated"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
