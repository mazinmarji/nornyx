from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "docs" / "pmo" / "status" / "current_status.json"


def test_dev_pmo_status_json_contract() -> None:
    assert STATUS.exists(), "PMO status JSON must exist"
    payload = json.loads(STATUS.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["project"] == "Nornyx"
    assert isinstance(payload.get("blocks"), list)
    assert payload["blocks"], "PMO status must include goal blocks"

    required = {
        "id",
        "title",
        "phase",
        "status",
        "completion_pct",
        "completed",
        "pending",
        "risks",
        "evidence",
        "next_goal",
    }
    for block in payload["blocks"]:
        assert required.issubset(block), f"Missing keys in {block.get('id')}: {required - set(block)}"
        assert 0 <= int(block["completion_pct"]) <= 100
        assert block["status"] in {"completed", "partial", "not_started", "locked", "blocked"}


def test_portal_static_files_exist() -> None:
    portal = ROOT / "apps" / "nornyx-dev-pmo-portal"
    for name in ["index.html", "app.js", "styles.css", "server.py", "README.md"]:
        assert (portal / name).exists(), name
