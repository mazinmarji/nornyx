from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_schemas_are_bundled_in_package() -> None:
    bundled = ROOT / "nornyx" / "schemas"
    for name in ("nornyx_v0_1.schema.json", "nornyx_v0_2.schema.json", "nornyx_v1_0.schema.json"):
        assert (bundled / name).is_file(), f"missing bundled schema: {name}"


def test_schema_command_loads_each_version() -> None:
    for version in ("0.2", "1.0"):
        result = subprocess.run(
            [sys.executable, "-m", "nornyx.cli", "schema", "--version", version],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        json.loads(result.stdout)  # output is valid JSON schema summary
