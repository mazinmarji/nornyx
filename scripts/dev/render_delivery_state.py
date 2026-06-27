#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nornyx.renderers import render_delivery_state  # noqa: E402


def load_status(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Status file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Status file root must be a JSON object")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Nornyx delivery state.")
    parser.add_argument(
        "--format",
        choices=["shell", "markdown", "json", "json-compact"],
        default="shell",
    )
    parser.add_argument(
        "--status",
        default="docs/pmo/status/current_status.json",
        help="Path to PMO/delivery status JSON.",
    )
    parser.add_argument("--out", help="Optional output file.")
    args = parser.parse_args()

    status_path = ROOT / args.status
    if not status_path.exists() and args.status == "docs/pmo/status/current_status.json":
        fallback = ROOT / "docs" / "pmo" / "status" / "current_status.example.json"
        if fallback.exists():
            status_path = fallback

    rendered = render_delivery_state(load_status(status_path), args.format)

    if args.out:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
        print(out.relative_to(ROOT))
    else:
        print(rendered, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
