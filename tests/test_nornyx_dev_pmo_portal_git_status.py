from __future__ import annotations

import importlib.util
from pathlib import Path


def load_server_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "apps" / "nornyx-dev-pmo-portal" / "server.py"
    spec = importlib.util.spec_from_file_location("nornyx_dev_pmo_server", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_normalize_github_web_url_for_ssh() -> None:
    module = load_server_module()
    assert (
        module.normalize_github_web_url("git@github.com:mazinmarji/nornyx.git")
        == "https://github.com/mazinmarji/nornyx"
    )


def test_normalize_github_web_url_for_https() -> None:
    module = load_server_module()
    assert (
        module.normalize_github_web_url("https://github.com/mazinmarji/nornyx.git")
        == "https://github.com/mazinmarji/nornyx"
    )


def test_count_worktree_changes() -> None:
    module = load_server_module()
    counts = module.count_worktree_changes(" M file.py\nA  added.py\n?? new.txt\n")
    assert counts["dirty"] is True
    assert counts["modified_count"] == 1
    assert counts["staged_count"] == 1
    assert counts["untracked_count"] == 1
    assert counts["total_changed"] == 3


def test_remote_status_from_counts() -> None:
    module = load_server_module()
    assert module.remote_status_from_counts("abc", "abc", 0, 0) == "up_to_date"
    assert module.remote_status_from_counts("abc", "", 1, 0) == "local_ahead"
    assert module.remote_status_from_counts("abc", "", 0, 1) == "local_behind"
    assert module.remote_status_from_counts("abc", "", 1, 1) == "diverged"


def test_compact_sha() -> None:
    module = load_server_module()
    assert module.compact_sha("1234567890abcdef") == "12345678"
    assert module.compact_sha("") == ""


def test_goal_packet_metadata_reads_title_and_phase() -> None:
    module = load_server_module()
    root = Path(__file__).resolve().parents[1]
    path = root / "docs" / "goals" / "goal-011-lsp-and-editor-tooling.md"

    metadata = module.goal_packet_metadata(path)

    assert metadata["id"] == "GOAL-011"
    assert metadata["title"] == "GOAL-011: LSP and editor tooling"
    assert metadata["phase"] == "v0.8"
    assert Path(metadata["path"]).name == "goal-011-lsp-and-editor-tooling.md"


def test_collect_pmo_status_includes_goal_packet_files() -> None:
    module = load_server_module()
    status = module.collect_pmo_status()

    assert status["blocks"], "curated PMO blocks should remain present"
    assert len(status["goals"]) >= len(status["blocks"])
    assert any(goal["id"] == "GOAL-012" for goal in status["goals"])
    assert "vision_map" in status
    assert "source_of_truth" in status


def test_collect_portal_kpis_is_read_only_local_metrics() -> None:
    module = load_server_module()
    kpis = module.collect_portal_kpis()

    assert kpis["schema_version"] == "1.0"
    assert kpis["repo_kpis"]["agentic_dev_readiness_score"] >= 85
    assert kpis["current_goal_evidence"]["evidence_dir"].endswith("GOAL-029")
    assert kpis["safety"]["mode"] == "read_only_local_metrics"
    assert kpis["safety"]["writes"] == "disabled"


def test_remote_status_success_payload_has_status_fields() -> None:
    module = load_server_module()
    payload = module.remote_status_from_counts("abc", "def", 0, 0)
    assert payload == "different_head"
