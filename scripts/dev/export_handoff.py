#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nornyx.dev_quality import load_json, status_summary  # noqa: E402
from nornyx.goal_templates import render_handoff  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a concise handoff from PMO status.")
    parser.add_argument("--out", default="docs/handoff/NORNYX_HANDOFF.md")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    status_path = ROOT / "docs" / "pmo" / "status" / "current_status.json"
    if status_path.exists():
        data = load_json(status_path)
        project = str(data.get("project", "Nornyx"))
        summary = status_summary(data)
        next_goal = str((data.get("summary") or {}).get("next_recommended_goal", "Not defined"))
    else:
        project = "Nornyx"
        summary = "No PMO status file found."
        next_goal = "Create or update docs/pmo/status/current_status.json"

    content = render_handoff(project, summary, next_goal)

    if args.dry_run:
        print(content)
        return 0

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    print(out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
