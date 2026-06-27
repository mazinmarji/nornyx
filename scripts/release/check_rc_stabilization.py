#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nornyx.release_readiness import build_release_candidate_stabilization_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local Nornyx v0.9 RC stabilization.")
    parser.add_argument("--target-version", default="1.0.0")
    parser.add_argument("--approved", action="store_true", help="Record human release approval")
    parser.add_argument("--strict", action="store_true", help="Return non-zero on blocking errors")
    args = parser.parse_args()

    report = build_release_candidate_stabilization_report(
        ROOT,
        target_version=args.target_version,
        approved=args.approved,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "target_version": report["target_version"],
                "summary": report["summary"],
            },
            indent=2,
        )
    )
    if args.strict and report["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
