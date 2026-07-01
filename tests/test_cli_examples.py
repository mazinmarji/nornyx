from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from nornyx.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_examples_are_bundled_in_package() -> None:
    pkg_examples = ROOT / "nornyx" / "examples"
    files = sorted(p.name for p in pkg_examples.glob("*.nyx"))
    assert len(files) >= 5
    assert "email_triage.nyx" in files
    assert "governed_delivery_control_plane.nyx" in files
    assert "release_guardrails.nyx" in files
    assert "org_policies.nyx" in files
    assert "governed_service.nyx" in files


def test_examples_command_writes_files(tmp_path) -> None:
    out = tmp_path / "examples"
    result = subprocess.run(
        [sys.executable, "-m", "nornyx.cli", "examples", "--out", str(out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Wrote 5 example(s)" in result.stdout
    assert len(list(out.glob("*.nyx"))) == 5
    assert (out / "governed_delivery_control_plane.nyx").is_file()


def test_bundled_examples_check_cleanly() -> None:
    pkg_examples = ROOT / "nornyx" / "examples"
    for example in sorted(pkg_examples.glob("*.nyx")):
        assert main(["check", str(example)]) == 0
