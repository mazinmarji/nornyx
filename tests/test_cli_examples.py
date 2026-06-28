from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_examples_are_bundled_in_package() -> None:
    pkg_examples = ROOT / "nornyx" / "examples"
    files = sorted(p.name for p in pkg_examples.glob("*.nyx"))
    assert len(files) >= 2
    assert "governed_delivery_control_plane.nyx" in files


def test_examples_command_writes_files(tmp_path) -> None:
    out = tmp_path / "examples"
    result = subprocess.run(
        [sys.executable, "-m", "nornyx.cli", "examples", "--out", str(out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (out / "governed_delivery_control_plane.nyx").is_file()
