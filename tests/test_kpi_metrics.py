from __future__ import annotations

from pathlib import Path

from nornyx.dev_quality import safe_quality_commands
from nornyx.kpi_metrics import build_kpi_result, collect_repo_kpis, kpi_summary, score_evidence_dir, validate_kpi_result


ROOT = Path(__file__).resolve().parents[1]


def test_score_complete_evidence_fixture() -> None:
    root = Path(__file__).resolve().parent / "fixtures" / "kpi" / "evidence_complete"
    result = score_evidence_dir(root)
    assert result["percent"] == 100.0
    assert result["status"] == "complete"
    assert not result["missing"]


def test_score_incomplete_evidence_fixture() -> None:
    root = Path(__file__).resolve().parent / "fixtures" / "kpi" / "evidence_incomplete"
    result = score_evidence_dir(root)
    assert result["percent"] < 75
    assert result["status"] in {"weak", "incomplete"}
    assert result["missing"]


def test_collect_repo_kpis_on_minimal_repo(tmp_path: Path) -> None:
    (tmp_path / "docs" / "goals").mkdir(parents=True)
    (tmp_path / "docs" / "goals" / "goal-001.md").write_text("# Goal\n", encoding="utf-8")
    (tmp_path / "docs" / "qa" / "evidence" / "GOAL-001").mkdir(parents=True)
    (tmp_path / "docs" / "backlog" / "triage-candidates").mkdir(parents=True)
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "demo.nyx").write_text("project Demo:\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_demo.py").write_text("def test_demo(): assert True\n", encoding="utf-8")
    (tmp_path / "scripts" / "dev").mkdir(parents=True)
    (tmp_path / "scripts" / "dev" / "run_quality.py").write_text("# run\n", encoding="utf-8")
    (tmp_path / "scripts" / "dev" / "check_demo.py").write_text("# check\n", encoding="utf-8")

    result = collect_repo_kpis(tmp_path)
    assert result["goals_count"] == 1
    assert result["nyx_example_count"] == 1
    assert result["test_file_count"] == 1
    assert result["agentic_dev_readiness_score"] >= 85


def test_real_goal_031_kpi_result_is_reviewable() -> None:
    result = build_kpi_result(ROOT, evidence_dir=ROOT / "docs" / "qa" / "evidence" / "GOAL-031")
    issues = validate_kpi_result(result)

    assert not [issue.message for issue in issues if issue.severity == "error"]
    assert result["evidence_score"]["status"] in {"reviewable", "complete"}
    assert "repo_readiness=" in kpi_summary(result)


def test_kpi_validation_blocks_weak_evidence(tmp_path: Path) -> None:
    (tmp_path / "docs" / "goals").mkdir(parents=True)
    (tmp_path / "docs" / "goals" / "goal-001.md").write_text("# Goal\n", encoding="utf-8")
    (tmp_path / "docs" / "qa" / "evidence" / "GOAL-001").mkdir(parents=True)
    (tmp_path / "docs" / "backlog" / "triage-candidates").mkdir(parents=True)
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "demo.nyx").write_text("project Demo:\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_demo.py").write_text("def test_demo(): assert True\n", encoding="utf-8")
    (tmp_path / "scripts" / "dev").mkdir(parents=True)
    (tmp_path / "scripts" / "dev" / "run_quality.py").write_text("# run\n", encoding="utf-8")
    (tmp_path / "scripts" / "dev" / "check_demo.py").write_text("# check\n", encoding="utf-8")
    weak_evidence = tmp_path / "docs" / "qa" / "evidence" / "GOAL-999"
    weak_evidence.mkdir(parents=True)
    (weak_evidence / "README.md").write_text("# Evidence\n", encoding="utf-8")

    result = build_kpi_result(tmp_path, evidence_dir=weak_evidence)
    issues = validate_kpi_result(result)

    assert any("evidence score" in issue.message for issue in issues)


def test_quality_profiles_are_safe_and_progressive(tmp_path: Path) -> None:
    (tmp_path / "scripts" / "dev").mkdir(parents=True)
    (tmp_path / "scripts" / "dev" / "audit_pmo_status.py").write_text("# audit\n", encoding="utf-8")
    (tmp_path / "scripts" / "dev" / "check_kpi_measurement.py").write_text("# kpi check\n", encoding="utf-8")
    (tmp_path / "scripts" / "dev" / "run_kpi_benchmark.py").write_text("# kpi\n", encoding="utf-8")

    fast = safe_quality_commands(tmp_path, profile="fast")
    standard = safe_quality_commands(tmp_path, profile="standard")
    release = safe_quality_commands(tmp_path, profile="release")

    assert fast == [["python", "-m", "pytest", "-q"]]
    assert len(standard) >= len(fast)
    assert len(release) >= len(standard)
    assert all(command[0] == "python" for command in release)
    assert ["python", "scripts/dev/check_kpi_measurement.py"] in standard
