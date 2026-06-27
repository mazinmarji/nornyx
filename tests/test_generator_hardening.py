from __future__ import annotations

import json
from pathlib import Path

from nornyx.cli import main
from nornyx.generation_drift import DriftCase, check_generated_drift
from nornyx.generator import generate_artifacts
from nornyx.parser import load_nyx


def test_generation_manifest_is_deterministic_and_hashed(tmp_path: Path) -> None:
    doc = load_nyx(Path("examples/nornyx_roadmap_goals.nyx"))

    first_paths = generate_artifacts(doc, tmp_path / "first")
    second_paths = generate_artifacts(doc, tmp_path / "second")

    first_manifest = json.loads((tmp_path / "first" / "nornyx_generation_manifest.json").read_text())
    second_manifest = json.loads((tmp_path / "second" / "nornyx_generation_manifest.json").read_text())

    assert [path.relative_to(tmp_path / "first").as_posix() for path in first_paths] == [
        path.relative_to(tmp_path / "second").as_posix() for path in second_paths
    ]
    assert first_manifest["schema"] == "nornyx.generation_manifest.v0.1"
    assert first_manifest["artifacts"] == second_manifest["artifacts"]
    assert first_manifest["artifact_hashes"] == second_manifest["artifact_hashes"]
    assert first_manifest["artifact_count"] == len(first_manifest["artifacts"])
    assert all(entry["sha256"] for entry in first_manifest["artifact_hashes"])


def test_generator_writes_goal_task_packets(tmp_path: Path) -> None:
    doc = load_nyx(Path("examples/nornyx_roadmap_goals.nyx"))
    generate_artifacts(doc, tmp_path)

    task_packet = tmp_path / "task_packets" / "GOAL-003.md"
    text = task_packet.read_text(encoding="utf-8")

    assert task_packet.exists()
    assert "Artifact generator hardening" in text
    assert "Validation" in text
    assert "Evidence" in text
    assert "Stop Rules" in text


def test_goal_plan_cli_writes_expected_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "goal_plan"

    assert main(["goal-plan", "examples/nornyx_roadmap_goals.nyx", "--out", str(out)]) == 0

    assert (out / "goals.yaml").exists()
    assert (out / "GOAL_PLAN.md").exists()


def test_generated_drift_gate_matches_committed_baselines() -> None:
    report = check_generated_drift(Path("."))

    assert report["status"] == "pass"
    assert report["case_count"] == 2
    assert {item["status"] for item in report["results"]} == {"pass"}


def test_generated_drift_gate_detects_changed_baseline(tmp_path: Path) -> None:
    baseline_path = tmp_path / "governed_delivery_control_plane.json"
    case = DriftCase(
        label="governed_delivery_control_plane",
        source="examples/governed_delivery_control_plane.nyx",
        baseline=str(baseline_path),
    )

    update_report = check_generated_drift(Path("."), cases=(case,), update_baseline=True)
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline["generator_manifest"]["artifact_hashes"][0]["sha256"] = "intentional-drift"
    baseline_path.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = check_generated_drift(Path("."), cases=(case,))

    assert update_report["status"] == "updated"
    assert report["status"] == "fail"
    assert report["results"][0]["status"] == "drift"
    assert "generated manifest differs" in report["results"][0]["issues"][0]
