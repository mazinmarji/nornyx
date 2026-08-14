"""Public-boundary scanner.

Three detection layers, all deterministic and offline:

1. Synthetic neutral markers (``PUBLIC_BOUNDARY_MARKERS``) that stand in for
   private names in fixtures and must never reach public content.
2. Optional untracked local term files (``LOCAL_TERM_FILES``) holding real
   private names. These files are gitignored and absent in CI, so they can
   never be the only protection for a concept.
3. Tracked strategy-shape rules (``STRATEGY_LEAK_RULES``) that describe the
   *shape* of private product-strategy language. They run everywhere,
   including CI. Each rule is written so this source file never contains a
   flagged compound as contiguous text, and diagnostics never echo matched
   content — findings report a rule id and remediation hint only.

Layer 3 exists because layers 1 and 2 cannot, by design, carry real private
terms into CI; a strategy phrase that is not a synthetic marker previously
passed the public scan unchallenged.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path


PUBLIC_BOUNDARY_MARKERS = [
    "PRIVATE_DOWNSTREAM_PLATFORM",
    "PRIVATE_REPO_MARKER",
    "PRIVATE_PRODUCT_MARKER",
    "INTERNAL_LAB_MARKER",
    "DOWNSTREAM_SYSTEM_MARKER",
    "INTERNAL_CODEBASE_MARKER",
]

# Separators tolerated inside a flagged compound: whitespace, punctuation used
# in module/file paths, and zero-width/BOM characters that could hide a join.
_SEP = r"[\s_./\\\u200b-\u200d\ufeff-]"

# Rule ids are stable identifiers for diagnostics and tests. Hints must stay
# public-safe: they explain the violated boundary without quoting any flagged
# phrase.
STRATEGY_LEAK_RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "nonpublic-product-edition",
        re.compile(
            r"\bnornyx" + _SEP + r"{0,3}enterprises?\b",
            re.IGNORECASE,
        ),
        "references a non-public product edition of Nornyx; public content "
        "must stay vendor-neutral (docs/public-boundary-policy.md)",
    ),
    (
        "product-edition-shape",
        re.compile(
            r"\b(?:enterprise|commercial)\s+(?:edition|tier|sku)s?\b",
            re.IGNORECASE,
        ),
        "product-edition strategy language; the public repository does not "
        "define paid or private editions",
    ),
    (
        # Deliberately case-sensitive: the capitalized word is the edition
        # signal, while lowercase generic usage (industry scale, audience,
        # deployment style) must keep passing.
        "product-edition-counterpart",
        re.compile(
            r"\b(?:versus|vs)\b\.?" + _SEP + r"{1,3}" + r"Enterprise\b"
            + r"|\bEnterprise" + _SEP + r"{1,3}" + r"(?:versus|vs)\b"
            + r"|\bEnterprise" + _SEP + r"{0,3}"
            + r"(?i:boundar(?:y|ies)|deployments?|hostings?)\b",
        ),
        "capitalizes a product-edition counterpart of this repository; use "
        "lowercase generic wording or describe the public Core boundary "
        "instead",
    ),
    (
        "commercial-open-source-boundary",
        re.compile(
            r"\bcommercial\s*(?:[/\\-]|\bvs\.?\s|\bversus\s)\s*open[\s-]*source\b"
            r"|\bopen[\s-]*source\s*(?:[/\\-]|\bvs\.?\s|\bversus\s)\s*commercial\b",
            re.IGNORECASE,
        ),
        "frames a commercial-versus-open-source product split; describe the "
        "public Core boundary instead",
    ),
    (
        "commercial-boundary",
        re.compile(
            r"\bcommercial[\s-]+boundar(?:y|ies)\b",
            re.IGNORECASE,
        ),
        "names a commercial boundary; describe the public Core boundary "
        "instead",
    ),
]

LOCAL_TERM_FILES = [
    ".private-boundary-terms.txt",
    ".private-boundary-terms",
    "private-boundary-terms.txt",
]

SKIP_DIR_NAMES = {
    ".claude",
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
    Path("tests/test_public_boundary.py"),
    Path("scripts/check-public-boundary.py"),
}
LOCAL_TERM_PATHS = {Path(filename) for filename in LOCAL_TERM_FILES}


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
        if rel in LOCAL_TERM_PATHS:
            continue
        if rel in ALLOWED_SYNTHETIC_MARKER_FILES:
            continue
        if any(part in SKIP_DIR_NAMES or part.endswith(".egg-info") for part in rel.parts):
            continue
        files.append(path)
    return sorted(files)


def _term_finding(rel: str, line_number: int, term: str, scope: str) -> dict[str, object]:
    return {
        "path": rel,
        "line": line_number,
        "scope": scope,
        "term_fingerprint": _fingerprint(term),
    }


def _rule_finding(rel: str, line_number: int, rule_id: str, hint: str, scope: str) -> dict[str, object]:
    return {
        "path": rel,
        "line": line_number,
        "scope": scope,
        "rule": rule_id,
        "hint": hint,
    }


def _scan_text_line(rel: str, line_number: int, line: str, terms: list[str]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for term in terms:
        if term in line:
            findings.append(_term_finding(rel, line_number, term, "content"))
    for rule_id, pattern, hint in STRATEGY_LEAK_RULES:
        if pattern.search(line):
            findings.append(_rule_finding(rel, line_number, rule_id, hint, "content"))
    return findings


def _scan_wrapped_lines(rel: str, lines: list[str]) -> list[dict[str, object]]:
    """Catch a flagged compound split across a soft line wrap.

    Adjacent lines are joined with a single space; a match counts only when it
    spans the join, so single-line findings are never duplicated.
    """
    findings: list[dict[str, object]] = []
    for index in range(len(lines) - 1):
        first = lines[index]
        joined = first + " " + lines[index + 1]
        boundary = len(first)
        for rule_id, pattern, hint in STRATEGY_LEAK_RULES:
            for match in pattern.finditer(joined):
                if match.start() < boundary < match.end():
                    findings.append(
                        _rule_finding(rel, index + 1, rule_id, hint, "content")
                    )
                    break
    return findings


def _scan_path(rel: str, terms: list[str]) -> list[dict[str, object]]:
    """Flag private names or strategy shapes carried by the file path itself."""
    findings: list[dict[str, object]] = []
    for term in terms:
        if term in rel:
            findings.append(_term_finding(rel, 0, term, "path"))
    for rule_id, pattern, hint in STRATEGY_LEAK_RULES:
        if pattern.search(rel):
            findings.append(_rule_finding(rel, 0, rule_id, hint, "path"))
    return findings


def check_public_boundary(repo: str | Path) -> list[dict[str, object]]:
    root = Path(repo)
    terms = _load_terms(root)
    findings: list[dict[str, object]] = []
    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        file_findings = _scan_path(rel, terms)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = None
        if lines is not None:
            for line_number, line in enumerate(lines, start=1):
                file_findings.extend(_scan_text_line(rel, line_number, line, terms))
            file_findings.extend(_scan_wrapped_lines(rel, lines))
        file_findings.sort(
            key=lambda finding: (
                finding["line"],
                str(finding.get("rule", "")),
                str(finding.get("term_fingerprint", "")),
            )
        )
        findings.extend(file_findings)
    return findings


def _render(finding: dict[str, object]) -> str:
    location = f"{finding['path']}:{finding['line']}"
    scope = f" scope={finding['scope']}" if finding.get("scope") == "path" else ""
    if "rule" in finding:
        return f"{location}: rule={finding['rule']}{scope} hint={finding['hint']}"
    return f"{location}: term_fingerprint={finding['term_fingerprint']}{scope}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check public-boundary leakage: synthetic markers, untracked "
            "local terms, and tracked strategy-shape rules."
        )
    )
    parser.add_argument("--repo", default=".", help="Repository root to scan.")
    args = parser.parse_args(argv)

    findings = check_public_boundary(args.repo)
    if not findings:
        print("public boundary check passed")
        return 0
    print("public boundary check failed")
    for finding in findings:
        print(_render(finding))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
