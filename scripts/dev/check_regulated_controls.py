#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nornyx.regulated_controls import (  # noqa: E402
    regulated_control_pack_summary,
    validate_regulated_control_pack,
)


def main() -> int:
    path = ROOT / "docs" / "backlog" / "nornyx-decision-boundary-evidence-quality.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    issues = validate_regulated_control_pack(data)
    print(regulated_control_pack_summary(data))
    for issue in issues:
        print(f"{issue.severity.upper()}: {issue.message}")
    return 1 if any(issue.severity == "error" for issue in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
