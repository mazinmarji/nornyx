from __future__ import annotations

from pathlib import Path


def app_source() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / "apps" / "nornyx-dev-pmo-portal" / "app.js").read_text(encoding="utf-8")


def test_portal_merges_pmo_blocks_with_packet_only_goals() -> None:
    source = app_source()

    assert "packetBlockFromGoal" in source
    assert "canonicalGoalId" in source
    assert "seenGoalIds" in source
    assert "if (id && seenGoalIds.has(id)) return false" in source
    assert "return [...fromBlocks, ...packetBlocks]" in source
    assert "if (fromBlocks.length) return fromBlocks" not in source


def test_portal_exposes_packet_only_filter_and_status_label() -> None:
    source = app_source()

    assert "packet_only: 'Packet only'" in source
    assert "'packet_only'" in source
    assert "Not yet tracked in PMO status ledger." in source


def test_portal_renders_read_only_kpi_panel() -> None:
    source = app_source()

    assert "renderKpiPanel" in source
    assert "/api/dev/kpi/status" in source
    assert "Agentic Development Readiness" in source
    assert "read-only metrics only" in source


def test_portal_renders_goal_numbering_audit() -> None:
    source = app_source()

    assert "renderGoalAudit" in source
    assert "Goal Ledger Clarity" in source
    assert "Skipped numbers" in source
    assert "Tracked packet files hidden" in source
