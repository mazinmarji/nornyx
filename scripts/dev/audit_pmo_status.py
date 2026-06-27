#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nornyx.dev_quality import audit_pmo_status, load_json, status_summary  # noqa: E402


def main() -> int:
    path = ROOT / "docs" / "pmo" / "status" / "current_status.json"
    if not path.exists():
        print(f"SKIP: {path} not found")
        return 0

    data = load_json(path)
    issues = audit_pmo_status(data)
    print(status_summary(data))

    for issue in issues:
        print(f"{issue.severity.upper()}: {issue.block_id}: {issue.message}")

    return 1 if any(i.severity == "error" for i in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
