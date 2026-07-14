from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
BASE = "95952226999327458c6fea81cb32d82539bcae5b"
RAW_HASH_GLOBS = (
    "examples/governance_evidence/*.json",
    "examples/architecture_reports/*.json",
    "tests/fixtures/governance_compatibility/*.json",
    "tests/fixtures/generated_drift/*.json",
    "tests/fixtures/governance_extension/starter_golden/*.nyx",
)


def test_aud014_hash_bound_artifacts_are_checkout_stable() -> None:
    attributes = {
        line.strip()
        for line in (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "examples/governance_evidence/*.json -text" in attributes
    assert "examples/architecture_reports/*.json -text" in attributes
    assert "tests/fixtures/governance_compatibility/*.json -text" in attributes
    assert "tests/fixtures/generated_drift/*.json -text" in attributes


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"command failed ({result.returncode}): {' '.join(command)}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return result


def test_aud014_fresh_autocrlf_checkout_preserves_hash_bound_behavior() -> None:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert status.returncode == 0, status.stderr

    # Keep the clone beneath the resolved workspace parent. Windows may expose
    # the system temp directory through an 8.3 alias, which would create an
    # unrelated lexical-root mismatch in the path hardening checks.
    with tempfile.TemporaryDirectory(
        prefix="nornyx-autocrlf-",
        dir=ROOT.parent,
    ) as raw_tmp:
        clone_root = Path(raw_tmp).resolve()
        candidate_root = ROOT
        if status.stdout:
            untracked = [
                line
                for line in status.stdout.splitlines()
                if line.startswith(b"?? ")
            ]
            assert not untracked, (
                "fresh-checkout proof cannot omit untracked candidate files: "
                + ", ".join(line[3:].decode(errors="replace") for line in untracked)
            )
            candidate_root = clone_root / "candidate"
            _run(
                [
                    "git",
                    "-c",
                    "core.autocrlf=false",
                    "clone",
                    "--no-hardlinks",
                    str(ROOT),
                    str(candidate_root),
                ],
                cwd=clone_root,
            )
            patch = subprocess.run(
                ["git", "diff", "--binary", "HEAD"],
                cwd=ROOT,
                capture_output=True,
                check=False,
            )
            assert patch.returncode == 0, patch.stderr.decode(errors="replace")
            applied = subprocess.run(
                ["git", "apply", "--binary", "-"],
                cwd=candidate_root,
                input=patch.stdout,
                capture_output=True,
                check=False,
            )
            assert applied.returncode == 0, applied.stderr.decode(errors="replace")
            _run(["git", "add", "-A"], cwd=candidate_root)
            _run(
                [
                    "git",
                    "-c",
                    "user.name=Nornyx Test",
                    "-c",
                    "user.email=nornyx-test@example.invalid",
                    "-c",
                    "commit.gpgsign=false",
                    "commit",
                    "-m",
                    "test candidate snapshot",
                ],
                cwd=candidate_root,
            )

        checkout = clone_root / "checkout"
        _run(
            [
                "git",
                "-c",
                "core.autocrlf=true",
                "clone",
                "--no-hardlinks",
                str(candidate_root),
                str(checkout),
            ],
            cwd=clone_root,
        )

        matched: list[Path] = []
        for pattern in RAW_HASH_GLOBS:
            paths = sorted(candidate_root.glob(pattern))
            assert paths, pattern
            matched.extend(paths)
        for source in matched:
            relative = source.relative_to(candidate_root)
            blob = subprocess.run(
                ["git", "show", f"HEAD:{relative.as_posix()}"],
                cwd=candidate_root,
                capture_output=True,
                check=False,
            )
            assert blob.returncode == 0, blob.stderr.decode(errors="replace")
            assert (checkout / relative).read_bytes() == blob.stdout, relative

        for example in (
            "examples/governance_foundations.nyx",
            "examples/architecture_governance.nyx",
        ):
            _run([sys.executable, "-m", "nornyx.cli", "check", example], cwd=checkout)

        for command in ("resolve", "explain", "matrix"):
            _run(
                [
                    sys.executable,
                    "-m",
                    "nornyx.cli",
                    "governance",
                    command,
                    "examples/governance_foundations.nyx",
                    "--as-of",
                    "2026-06-01T00:00:00Z",
                    "--json",
                ],
                cwd=checkout,
            )

        _run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_governance_compatibility_corpus.py",
            ],
            cwd=checkout,
        )


def test_aud021_wheel_smoke_enforces_observed_no_network() -> None:
    source = (ROOT / "scripts" / "test_wheel_install.py").read_text(encoding="utf-8")
    assert '"--no-index"' in source
    assert "socket" in source
    assert '"network_used": False' not in source
    assert "network_attempts" in source


def test_aud022_candidate_diff_is_clean() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "git diff --check" in workflow
    result = subprocess.run(
        ["git", "diff", "--check", f"{BASE}...HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
