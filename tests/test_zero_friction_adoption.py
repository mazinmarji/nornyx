from __future__ import annotations

from pathlib import Path

import yaml

from nornyx.adoption import (
    adoption_summary,
    adoption_status,
    detect_repo_signals,
    render_lite_nyx,
    slug_project_name,
    validate_adoption_pack,
    write_lite_nyx,
)
from nornyx.checker import check_document, has_errors
from nornyx.dev_quality import safe_quality_commands


ROOT = Path(__file__).resolve().parents[1]


def test_slug_project_name() -> None:
    assert slug_project_name("My Repo!") == "MyRepo"
    assert slug_project_name("   ") == "NornyxProject"


def test_detect_repo_signals_python(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    signals = detect_repo_signals(tmp_path)
    assert "python" in signals["languages"]
    assert "python -m pytest -q" in signals["test_commands"]
    assert signals["recommended_level"] == "lite"


def test_render_lite_nyx_passes_current_checker(tmp_path) -> None:
    (tmp_path / "tests").mkdir()
    text = render_lite_nyx("Demo Project", repo_root=tmp_path)
    data = yaml.safe_load(text)
    diagnostics = check_document(data)
    assert not has_errors(diagnostics)
    assert data["project"]["name"] == "DemoProject"
    assert data["experimental"]["adoption"]["level"] == "lite"


def test_write_lite_nyx_does_not_overwrite_without_force(tmp_path) -> None:
    out = tmp_path / "nornyx.project.nyx"
    write_lite_nyx("Demo", out, repo_root=tmp_path)
    try:
        write_lite_nyx("Demo", out, repo_root=tmp_path)
    except FileExistsError:
        pass
    else:
        raise AssertionError("Expected FileExistsError")


def test_adoption_status_recommends_init_lite(tmp_path) -> None:
    status = adoption_status(tmp_path)
    assert status["next_action"] == "init-lite"
    assert "init-lite" in status["recommended_command"]
    assert "adoption_level=lite" in adoption_summary(status)


def test_validate_adoption_pack() -> None:
    data = {
        "status": "candidate",
        "adoption_levels": ["observe", "lite", "standard"],
        "capabilities": [
            {"id": "repo_status", "status": "candidate", "safe_now": True},
            {"id": "init_lite", "status": "candidate", "safe_now": True},
            {"id": "fast_quality_hint", "status": "candidate", "safe_now": True},
        ],
        "non_goals": [
            "live LLM calls",
            "portal wizard implementation",
            "fine-tuned model pipeline",
            "automatic remote Git writes",
            "automatic approval",
            "production enforcement",
        ],
        "first_commands": [
            "python -m nornyx.cli adopt status --repo .",
            "python -m nornyx.cli adopt init-lite --project MyRepo --out nornyx.project.nyx",
        ],
    }
    issues = validate_adoption_pack(data)
    assert not any(issue.severity == "error" for issue in issues)


def test_real_adoption_pack_has_no_errors() -> None:
    data = yaml.safe_load((ROOT / "docs" / "backlog" / "nornyx-zero-friction-adoption-pack.yaml").read_text(encoding="utf-8"))
    issues = validate_adoption_pack(data)
    assert not [issue.message for issue in issues if issue.severity == "error"]


def test_lite_adoption_validates_on_clean_downstream_repo(tmp_path) -> None:
    (tmp_path / "README.md").write_text("# Downstream Demo\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_demo.py").write_text("def test_demo(): assert True\n", encoding="utf-8")

    out = write_lite_nyx("Downstream Demo", tmp_path / "nornyx.project.nyx", repo_root=tmp_path)
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    diagnostics = check_document(data)

    assert not has_errors(diagnostics)
    assert adoption_status(tmp_path)["next_action"] == "check"


def test_standard_quality_includes_adoption_check(tmp_path) -> None:
    (tmp_path / "scripts" / "dev").mkdir(parents=True)
    (tmp_path / "scripts" / "dev" / "check_adoption_pack.py").write_text("# adoption\n", encoding="utf-8")

    assert ["python", "scripts/dev/check_adoption_pack.py"] in safe_quality_commands(tmp_path, profile="standard")
