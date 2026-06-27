from pathlib import Path

from nornyx.parser import load_nyx
from nornyx.checker import check_document, has_errors
from nornyx.goals import extract_goals, write_goal_plan
from nornyx.generator import generate_artifacts


def test_roadmap_goals_check_clean():
    doc = load_nyx(Path("examples/nornyx_roadmap_goals.nyx"))
    diagnostics = check_document(doc)
    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics]
    assert len(extract_goals(doc)) >= 5


def test_goal_plan_generation(tmp_path):
    doc = load_nyx(Path("examples/nornyx_roadmap_goals.nyx"))
    paths = write_goal_plan(doc, tmp_path)
    assert (tmp_path / "goals.yaml").exists()
    assert (tmp_path / "GOAL_PLAN.md").exists()
    assert len(paths) == 2


def test_generator_writes_goal_ledger(tmp_path):
    doc = load_nyx(Path("examples/nornyx_roadmap_goals.nyx"))
    generate_artifacts(doc, tmp_path)
    assert (tmp_path / "goals.yaml").exists()
    assert (tmp_path / "goal_ledger.md").exists()
