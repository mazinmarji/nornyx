"""Public-boundary scanner.

Three detection layers, all deterministic and offline:

1. Synthetic neutral markers (``PUBLIC_BOUNDARY_MARKERS``) that stand in for
   private names in fixtures and must never reach public content. Files listed
   in ``ALLOWED_SYNTHETIC_MARKER_FILES`` are exempt from this layer only:
   they are still scanned for local private terms and strategy shapes, and
   their paths are still checked.
2. Optional untracked local term files (``LOCAL_TERM_FILES``) holding real
   private names. These files are gitignored and absent in CI, so they can
   never be the only protection for a concept. Local terms are compared in a
   canonical form (``_canonical_term_text``): casefolded, with targeted
   zero-width characters removed, read via ``utf-8-sig`` so a BOM cannot
   defeat a match. Term fingerprints are taken over the canonical form.
3. Tracked strategy-shape rules (``STRATEGY_LEAK_RULES``) that describe the
   *shape* of private product-strategy language. They run everywhere,
   including CI, and share one bounded separator model. Each rule is written
   so this source file never contains a flagged compound as contiguous text,
   and diagnostics never echo matched content — findings report a rule id and
   remediation hint only.

Confidentiality boundary: when a file's *path* matches a private term or a
strategy rule, the raw path does not leave ``check_public_boundary`` at all —
every finding for that file carries ``path: "<redacted>"`` plus a
deterministic SHA-256 path fingerprint, so ``repr``/JSON of the findings stays
safe. The fingerprint is deterministic redaction for correlation, not
cryptographic secrecy. Findings for cleanly named paths keep normal
``path:line`` metadata.
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

REDACTED_PATH = "<redacted>"

# Characters an author can use to visually hide a join inside a flagged
# compound: ZERO WIDTH SPACE, ZERO WIDTH NON-JOINER, ZERO WIDTH JOINER, and
# ZERO WIDTH NO-BREAK SPACE / BOM. They are removed before matching only;
# file content is never modified.
_ZERO_WIDTH_CHARS = ("\u200b", "\u200c", "\u200d", "\ufeff")

# Bounded separator that can join the tokens of a flagged compound in prose,
# identifiers, or paths: up to three spaced characters (whitespace, hyphen,
# colon, slash, backslash), or a single unspaced dot/underscore. A dot
# followed by whitespace is deliberately NOT a join, so ordinary sentence
# boundaries ("... uses Nornyx. Enterprise teams ...") stay legal. The whole
# group is optional so a join hidden entirely behind zero-width characters
# (stripped before matching) is still caught.
_JOIN = r"(?:[\s/:\\-]{1,3}|[._])?"

# Connector between the two halves of the split shape: a spaced or unspaced
# slash/backslash/hyphen, an identifier-style dot or underscore, or a spaced
# "vs"/"versus".
_CONTRAST = r"(?:\s{0,2}[/\\-]\s{0,2}|[._]|\s+(?:vs\.?|versus)\s+)"

# Connector around the contrast word when a public-side term is set against an
# enterprise-side counterpart. Dot and underscore are excluded here so that
# sentence boundaries and snake_case identifiers do not read as contrasts.
_VS = r"[\s/:\\-]{0,3}(?:versus|vs\.?)[\s/:\\-]{0,3}"

# Rule ids are stable identifiers for diagnostics and tests. Ids and hints
# must stay public-safe AND must not themselves match any rule, because these
# files are rule-scanned like every other file.
STRATEGY_LEAK_RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "nonpublic-product-edition",
        re.compile(r"\bnornyx" + _JOIN + r"enterprises?\b", re.IGNORECASE),
        "references a non-public product edition of Nornyx; public content "
        "must stay vendor-neutral (docs/public-boundary-policy.md)",
    ),
    (
        "product-edition-shape",
        re.compile(
            r"\b(?:enterprise|commercial)" + _JOIN + r"(?:edition|tier|sku)s?\b",
            re.IGNORECASE,
        ),
        "product-edition strategy language; the public repository does not "
        "define paid or private editions",
    ),
    (
        "commercial-oss-split",
        re.compile(
            r"\bcommercial" + _CONTRAST + r"open" + _JOIN + r"source\b"
            r"|\bopen" + _JOIN + r"source" + _CONTRAST + r"commercial\b",
            re.IGNORECASE,
        ),
        "frames a split between commercial and open-source product lines; "
        "describe the public Core boundary instead",
    ),
    (
        "commercial-scope-phrase",
        re.compile(r"\bcommercial" + _JOIN + r"boundar(?:y|ies)\b", re.IGNORECASE),
        "names a commercial-positioning scope line; describe the public Core "
        "boundary instead",
    ),
    (
        "enterprise-counterpart-contrast",
        re.compile(
            r"\b(?:public(?:" + _JOIN + r"core)?|core|open" + _JOIN + r"source)"
            + _VS
            + r"enterprise\b"
            r"|\benterprise"
            + _VS
            + r"(?:public(?:" + _JOIN + r"core)?|core|open" + _JOIN + r"source)\b",
            re.IGNORECASE,
        ),
        "contrasts the public Core with an enterprise counterpart; describe "
        "the public Core scope boundary instead",
    ),
]

LOCAL_TERM_FILES = [
    ".private-boundary-terms.txt",
    ".private-boundary-terms",
    "private-boundary-terms.txt",
]

# Directory names that hold local agent/worktree state only when they sit at
# the repository root. A nested directory with the same name can carry
# tracked public configuration and MUST be scanned.
ROOT_LOCAL_DIR_NAMES = {".claude"}

# Cache/build directory names skipped at any depth. The tracked tree contains
# no public files under these names (verified against `git ls-files`).
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

# Exempt from the synthetic-marker layer ONLY. All other layers still apply.
ALLOWED_SYNTHETIC_MARKER_FILES = {
    Path("tests/test_governed_package_profile.py"),
    Path("tests/test_public_boundary.py"),
    Path("scripts/check-public-boundary.py"),
}
LOCAL_TERM_PATHS = {Path(filename) for filename in LOCAL_TERM_FILES}


def _fingerprint(term: str) -> str:
    return hashlib.sha256(term.encode("utf-8")).hexdigest()[:12]


def _strip_zero_width(text: str) -> str:
    for character in _ZERO_WIDTH_CHARS:
        if character in text:
            text = text.replace(character, "")
    return text


def _canonical_term_text(text: str) -> str:
    """Canonical comparison form for local private-term matching."""
    return _strip_zero_width(text).casefold()


def _load_local_terms(repo: Path) -> list[str]:
    terms: list[str] = []
    for filename in LOCAL_TERM_FILES:
        path = repo / filename
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            term = line.strip()
            if term and not term.startswith("#"):
                canonical = _canonical_term_text(term)
                if canonical and canonical not in terms:
                    terms.append(canonical)
    return terms


def _iter_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(repo)
        if rel in LOCAL_TERM_PATHS:
            continue
        if rel.parts and rel.parts[0] in ROOT_LOCAL_DIR_NAMES:
            continue
        if any(part in SKIP_DIR_NAMES or part.endswith(".egg-info") for part in rel.parts):
            continue
        files.append(path)
    return sorted(files)


def _term_finding(line_number: int, term_fingerprint: str, scope: str) -> dict[str, object]:
    return {
        "path": None,
        "line": line_number,
        "scope": scope,
        "term_fingerprint": term_fingerprint,
    }


def _rule_finding(line_number: int, rule_id: str, hint: str, scope: str) -> dict[str, object]:
    return {
        "path": None,
        "line": line_number,
        "scope": scope,
        "rule": rule_id,
        "hint": hint,
    }


def _scan_text_line(
    line_number: int,
    stripped_line: str,
    local_terms: list[str],
    marker_exempt: bool,
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    if not marker_exempt:
        for marker in PUBLIC_BOUNDARY_MARKERS:
            if marker in stripped_line:
                findings.append(_term_finding(line_number, _fingerprint(marker), "content"))
    if local_terms:
        canonical_line = stripped_line.casefold()
        for term in local_terms:
            if term in canonical_line:
                findings.append(_term_finding(line_number, _fingerprint(term), "content"))
    for rule_id, pattern, hint in STRATEGY_LEAK_RULES:
        if pattern.search(stripped_line):
            findings.append(_rule_finding(line_number, rule_id, hint, "content"))
    return findings


def _scan_line_windows(stripped_lines: list[str]) -> list[dict[str, object]]:
    """Catch a flagged compound split across up to three soft-wrapped lines.

    Windows of two and three adjacent lines are joined with single spaces. A
    match counts only when it starts in the first line of the window and ends
    in the last, so same-line and shorter-window findings are never
    duplicated. Windows containing a blank line are skipped: a paragraph
    break is not a soft wrap.
    """
    findings: list[dict[str, object]] = []
    seen: set[tuple[int, str]] = set()
    for size in (2, 3):
        for start in range(len(stripped_lines) - size + 1):
            segments = stripped_lines[start : start + size]
            if any(not segment.strip() for segment in segments):
                continue
            joined = " ".join(segments)
            first_length = len(segments[0])
            last_start = len(joined) - len(segments[-1])
            for rule_id, pattern, hint in STRATEGY_LEAK_RULES:
                for match in pattern.finditer(joined):
                    if match.start() < first_length and match.end() > last_start:
                        key = (start + 1, rule_id)
                        if key not in seen:
                            seen.add(key)
                            findings.append(
                                _rule_finding(start + 1, rule_id, hint, "content")
                            )
                        break
    return findings


def _scan_path(
    stripped_rel: str,
    local_terms: list[str],
    marker_exempt: bool,
) -> list[dict[str, object]]:
    """Flag private names or strategy shapes carried by the file path itself."""
    findings: list[dict[str, object]] = []
    if not marker_exempt:
        for marker in PUBLIC_BOUNDARY_MARKERS:
            if marker in stripped_rel:
                findings.append(_term_finding(0, _fingerprint(marker), "path"))
    if local_terms:
        canonical_rel = stripped_rel.casefold()
        for term in local_terms:
            if term in canonical_rel:
                findings.append(_term_finding(0, _fingerprint(term), "path"))
    for rule_id, pattern, hint in STRATEGY_LEAK_RULES:
        if pattern.search(stripped_rel):
            findings.append(_rule_finding(0, rule_id, hint, "path"))
    return findings


def check_public_boundary(repo: str | Path) -> list[dict[str, object]]:
    root = Path(repo)
    local_terms = _load_local_terms(root)
    findings: list[dict[str, object]] = []
    for path in _iter_files(root):
        rel_path = path.relative_to(root)
        rel = rel_path.as_posix()
        marker_exempt = rel_path in ALLOWED_SYNTHETIC_MARKER_FILES
        file_findings = _scan_path(_strip_zero_width(rel), local_terms, marker_exempt)
        path_is_sensitive = bool(file_findings)
        try:
            raw_lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            raw_lines = None
        if raw_lines is not None:
            stripped_lines = [_strip_zero_width(line) for line in raw_lines]
            for line_number, stripped_line in enumerate(stripped_lines, start=1):
                file_findings.extend(
                    _scan_text_line(line_number, stripped_line, local_terms, marker_exempt)
                )
            file_findings.extend(_scan_line_windows(stripped_lines))
        # Confidentiality boundary: the raw path is attached only when the
        # path itself is clean; a sensitive path never leaves this function.
        safe_path = REDACTED_PATH if path_is_sensitive else rel
        for finding in file_findings:
            finding["path"] = safe_path
            if path_is_sensitive:
                finding["path_fingerprint"] = _fingerprint(rel)
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
    detail = (
        f"rule={finding['rule']} hint={finding['hint']}"
        if "rule" in finding
        else f"term_fingerprint={finding['term_fingerprint']}"
    )
    if "path_fingerprint" in finding:
        return (
            f"path_fingerprint={finding['path_fingerprint']} "
            f"line={finding['line']} scope={finding['scope']} {detail}"
        )
    return f"{finding['path']}:{finding['line']}: {detail}"


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
