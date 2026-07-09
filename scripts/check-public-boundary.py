from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


PUBLIC_BOUNDARY_MARKERS = [
    "PRIVATE_DOWNSTREAM_PLATFORM",
    "PRIVATE_REPO_MARKER",
    "PRIVATE_PRODUCT_MARKER",
    "INTERNAL_LAB_MARKER",
    "DOWNSTREAM_SYSTEM_MARKER",
    "INTERNAL_CODEBASE_MARKER",
]

LOCAL_TERM_FILES = [
    ".private-boundary-terms.txt",
    ".private-boundary-terms",
    "private-boundary-terms.txt",
]

SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}

ALLOWED_SYNTHETIC_MARKER_FILES = {
    Path("tests/test_governed_package_profile.py"),
    Path("scripts/check-public-boundary.py"),
}


def _fingerprint(term: str) -> str:
    return hashlib.sha256(term.encode("utf-8")).hexdigest()[:12]


def _load_terms(repo: Path) -> list[str]:
    terms = list(PUBLIC_BOUNDARY_MARKERS)
    for filename in LOCAL_TERM_FILES:
        path = repo / filename
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            term = line.strip()
            if term and not term.startswith("#"):
                terms.append(term)
    return terms


def _iter_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(repo)
        if rel in ALLOWED_SYNTHETIC_MARKER_FILES:
            continue
        if any(part in SKIP_DIR_NAMES or part.endswith(".egg-info") for part in rel.parts):
            continue
        files.append(path)
    return files


def check_public_boundary(repo: str | Path) -> list[dict[str, object]]:
    root = Path(repo)
    terms = _load_terms(root)
    findings: list[dict[str, object]] = []
    for path in _iter_files(root):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(root).as_posix()
        for line_number, line in enumerate(lines, start=1):
            for term in terms:
                if term in line:
                    findings.append(
                        {
                            "path": rel,
                            "line": line_number,
                            "term_fingerprint": _fingerprint(term),
                        }
                    )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check public-boundary marker leakage.")
    parser.add_argument("--repo", default=".", help="Repository root to scan.")
    args = parser.parse_args(argv)

    findings = check_public_boundary(args.repo)
    if not findings:
        print("public boundary check passed")
        return 0
    print("public boundary check failed")
    for finding in findings:
        print(
            f"{finding['path']}:{finding['line']}: "
            f"term_fingerprint={finding['term_fingerprint']}"
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
