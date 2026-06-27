#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nornyx.kpi_metrics import build_kpi_result, kpi_summary, validate_kpi_result  # noqa: E402


def main() -> int:
    result = build_kpi_result(ROOT, evidence_dir=ROOT / "docs" / "qa" / "evidence" / "GOAL-031")
    print(kpi_summary(result))

    issues = validate_kpi_result(result)
    for issue in issues:
        print(f"{issue.severity.upper()}: {issue.message}")

    return 1 if any(issue.severity == "error" for issue in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
