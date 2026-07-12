from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from nornyx import __version__
from nornyx.profiles import PROFILE_NAMES, write_profile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "tests" / "fixtures" / "governance_extension" / "starter_golden"
PROJECT_NAME = "GovernanceGolden"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _assert_source_matches(source_commit: str) -> None:
    result = subprocess.run(
        ["git", "diff", "--quiet", source_commit, "--", "nornyx/profiles.py", "profiles"],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            "Current profile implementation differs from the requested source commit; "
            "capture from that commit before approving a new baseline."
        )


def _generate(profile: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="nornyx-profile-golden-") as tmp:
        target = Path(tmp) / f"{profile}.nyx"
        write_profile(target, profile, PROJECT_NAME)
        return target.read_bytes()


def capture(
    out_dir: Path,
    *,
    source_commit: str,
    approve_update: bool,
    approval_reason: str | None,
) -> None:
    if approve_update and not approval_reason:
        raise SystemExit("--approve-update requires --approval-reason")
    _assert_source_matches(source_commit)
    out_dir.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, str]] = []
    for profile in PROFILE_NAMES:
        generated = _generate(profile)
        target = out_dir / f"{profile}.nyx"
        if target.exists() and target.read_bytes() != generated:
            existing = target.read_bytes()
            if _canonical_lf(existing) == _canonical_lf(generated):
                generated = existing
            elif not approve_update:
                raise SystemExit(
                    f"Golden mismatch for {profile}; investigate it. "
                    "Use --approve-update with --approval-reason only after review."
                )
        if not target.exists() or (approve_update and target.read_bytes() != generated):
            target.write_bytes(generated)

        exact = target.read_bytes()
        entries.append(
            {
                "profile": profile,
                "project_name": PROJECT_NAME,
                "file": target.name,
                "source_commit": source_commit,
                "nornyx_version": __version__,
                "generation_command": (
                    "python -m nornyx.cli init "
                    f"--profile {profile} --name {PROJECT_NAME} "
                    f"--out tests/fixtures/governance_extension/starter_golden/{profile}.nyx"
                ),
                "sha256": _sha256(exact),
                "canonical_lf_sha256": _sha256(_canonical_lf(exact)),
                "compatibility_class": "semantic_equivalence_allowed",
                "allowed_normalization": "CRLF_to_LF_only",
            }
        )

    manifest = {
        "schema": "nornyx.profile_starter_golden.v1",
        "source_ref": "main",
        "source_commit": source_commit,
        "nornyx_version": __version__,
        "project_name": PROJECT_NAME,
        "profile_order": list(PROFILE_NAMES),
        "compatibility_classes": [
            "byte_identical",
            "semantic_equivalence_allowed",
            "intentional_migration_requires_approval",
        ],
        "default_class": "byte_identical",
        "normalization_exception": (
            "Current-main write_profile uses platform text translation. Existing starters are "
            "CRLF on Windows and LF on POSIX, so only line-ending normalization is allowed."
        ),
        "approval_reason": approval_reason if approve_update else None,
        "profiles": entries,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture or verify reviewed current-main profile starter baselines."
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--source-commit", default=_git("rev-parse", "main"))
    parser.add_argument("--approve-update", action="store_true")
    parser.add_argument("--approval-reason")
    args = parser.parse_args()
    capture(
        args.out,
        source_commit=args.source_commit,
        approve_update=args.approve_update,
        approval_reason=args.approval_reason,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
