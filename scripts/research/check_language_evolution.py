#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nornyx.language_evolution import build_language_evolution_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local Nornyx language evolution research.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero on research-contract issues")
    args = parser.parse_args()

    report = build_language_evolution_report(ROOT)
    print(
        json.dumps(
            {
                "status": report["status"],
                "summary": report["summary"],
                "recommended_next_goal": report["recommended_next_goal"],
            },
            indent=2,
        )
    )
    if args.strict and report["summary"]["blocking_issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
