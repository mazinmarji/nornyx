#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nornyx.triage_candidates import (  # noqa: E402
    candidate_summary,
    find_candidate_files,
    load_candidate,
    validate_candidate_directory,
)


def main() -> int:
    root = ROOT / "docs" / "backlog" / "triage-candidates"
    matrix_path = ROOT / "docs" / "backlog" / "nornyx-requirement-triage-matrix.yaml"
    matrix = load_candidate(matrix_path)
    files = find_candidate_files(root)
    print(f"triage_candidates={len(files)}")

    for path in files:
        try:
            print(candidate_summary(load_candidate(path)))
        except Exception as exc:  # noqa: BLE001
            print(f"{path.name} | failed_to_load | {exc}")

    issues = validate_candidate_directory(root, matrix=matrix)
    for issue in issues:
        print(f"{issue.severity.upper()}: {issue.candidate_id}: {issue.message}")

    return 1 if any(issue.severity == "error" for issue in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
