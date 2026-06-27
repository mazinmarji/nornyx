from __future__ import annotations

import json
from pathlib import Path

from nornyx.cli import main
from nornyx.harness_runtime import normalize_repairs, run_harness
from nornyx.parser import load_nyx


def test_harness_runtime_writes_safe_manifest(tmp_path: Path) -> None:
    doc = load_nyx(Path("examples/governed_delivery_control_plane.nyx"))
    manifest = run_harness(doc, Path("."), tmp_path, harness_name="DevHarness")

    assert manifest["schema"] == "nornyx.harness_run.v0.1"
    assert manifest["harness"] == "DevHarness"
    assert manifest["status"] == "planned_with_policy_blocks"
    assert manifest["policy_summary"]["blocked"] == 1
    assert manifest["eval_summary"]["pending_metrics"] == 3
    assert manifest["connector_summary"]["connectors"] == 0
    assert manifest["safety"]["tools_executed"] is False
    assert manifest["safety"]["arbitrary_commands_allowed"] is False
    assert manifest["safety"]["connectors_enabled"] is False
    assert manifest["safety"]["default_capability_mode"] == "deny_unless_declared"
    assert any(
        gate["status"] == "requires_human_approval"
        for gate in manifest["gates"]
    )
    assert (tmp_path / "run_manifest.json").exists()
    assert (tmp_path / "context_pack.json").exists()
    assert (tmp_path / "trace_bundle.json").exists()
    assert (tmp_path / "trace_digest.json").exists()
    assert (tmp_path / "approval_log.json").exists()
    assert (tmp_path / "policy_report.json").exists()
    assert (tmp_path / "eval_report.json").exists()
    assert (tmp_path / "connector_report.json").exists()
    assert (tmp_path / "evidence" / "evidence_manifest.json").exists()


def test_harness_runtime_bounds_repair_attempts() -> None:
    repairs = normalize_repairs({"repair": [{"on": "test_failure", "max_attempts": 99}]})

    assert repairs[0]["max_attempts"] == 3
    assert repairs[0]["requested_max_attempts"] == 99
    assert repairs[0]["execution"] == "not_executed"


def test_harness_run_cli_creates_manifest(tmp_path: Path, capsys) -> None:
    assert (
        main(
            [
                "harness-run",
                "examples/governed_delivery_control_plane.nyx",
                "--harness",
                "DevHarness",
                "--out",
                str(tmp_path),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    manifest = json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8"))

    assert "Harness run manifest written" in out
    assert manifest["mode"] == "safe_local_manifest"
    assert manifest["policy_summary"]["blocked"] == 1
    assert manifest["eval_summary"]["pending_metrics"] == 3
    assert manifest["connector_summary"]["connectors"] == 0
    assert manifest["flow"][0]["execution"] == "not_executed"
