#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nornyx.goal_templates import make_goal_packet  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a governed Nornyx goal packet.")
    parser.add_argument("goal_id", help="Example: GOAL-016")
    parser.add_argument("title", help="Human-readable goal title")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Print planned files without writing")
    mode.add_argument("--write", action="store_true", help="Write goal and evidence files")
    args = parser.parse_args()

    packet = make_goal_packet(args.goal_id, args.title, ROOT)

    if not args.write:
        print("DRY RUN")
        print(packet.goal_path.relative_to(ROOT))
        print(packet.evidence_path.relative_to(ROOT))
        return 0

    for path, content in [(packet.goal_path, packet.content), (packet.evidence_path, packet.evidence_content)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise SystemExit(f"Refusing to overwrite existing file: {path}")
        path.write_text(content, encoding="utf-8")
        print(path.relative_to(ROOT))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
