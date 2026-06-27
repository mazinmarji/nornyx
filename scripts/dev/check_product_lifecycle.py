#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nornyx.product_lifecycle import lifecycle_summary, validate_lifecycle_extension  # noqa: E402


def main() -> int:
    path = ROOT / "docs" / "backlog" / "nornyx-product-to-ops-lifecycle.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    issues = validate_lifecycle_extension(data)
    print(lifecycle_summary(data))
    for issue in issues:
        print(f"{issue.severity.upper()}: {issue.message}")
    return 1 if any(issue.severity == "error" for issue in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
