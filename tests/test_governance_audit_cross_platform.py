from __future__ import annotations

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BASE = "95952226999327458c6fea81cb32d82539bcae5b"


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
