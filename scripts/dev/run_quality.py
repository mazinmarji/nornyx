#!/usr/bin/env python3
"""Run safe local Nornyx quality gates.

This script runs an explicit allowlist of local quality commands.
It does not call LLMs, connectors, deploys, shells, secrets, or production systems.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nornyx.dev_quality import QUALITY_PROFILES, safe_quality_commands  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run safe local Nornyx quality gates.")
    parser.add_argument(
        "--profile",
        choices=sorted(QUALITY_PROFILES),
        default="standard",
        help="Quality profile to run. Use fast for tight loops, release before handoff.",
    )
    args = parser.parse_args()

    failed = 0
    commands = safe_quality_commands(ROOT, profile=args.profile)
    print(f"Quality profile: {args.profile}")
    print(f"Commands: {len(commands)}")

    for command in commands:
        print(f"\n$ {' '.join(command)}")
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode != 0:
            failed += 1
            print(f"FAILED: {' '.join(command)} -> {result.returncode}")

    if failed:
        print(f"\nQuality gates failed: {failed}")
        return 1

    print("\nQuality gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
