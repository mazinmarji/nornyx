#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nornyx.requirement_triage import triage_summary, validate_triage_matrix  # noqa: E402


def main() -> int:
    path = ROOT / "docs" / "backlog" / "nornyx-requirement-triage-matrix.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    print(triage_summary(data))
    issues = validate_triage_matrix(data)
    for issue in issues:
        print(f"{issue.severity.upper()}: {issue.message}")
    return 1 if any(issue.severity == "error" for issue in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
