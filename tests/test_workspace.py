from __future__ import annotations

from pathlib import Path

import pytest

from nornyx.workspace import WorkspaceError, check_workspace

MANIFEST = """\
workspace: TestOrg
policies:
  SafeDeliveryPolicy:
    - deny secrets_to_llm
    - require tests_if_code_changed
    - require human_approval_before_merge
members:
  - path: a/a.nyx
  - path: b/b.nyx
"""

MEMBER = """\
nornyx: "0.1"
project:
  name: {name}
policies:
  - name: SafeDeliveryPolicy
    rules:
{rules}
"""

ALIGNED = "      - deny secrets_to_llm\n      - require tests_if_code_changed\n      - require human_approval_before_merge\n"


def _member(tmp_path: Path, sub: str, name: str, rules: str) -> None:
    d = tmp_path / sub
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{sub}.nyx").write_text(MEMBER.format(name=name, rules=rules), encoding="utf-8")


def _manifest(tmp_path: Path) -> Path:
    m = tmp_path / "nornyx.workspace.yaml"
    m.write_text(MANIFEST, encoding="utf-8")
    return m


def test_workspace_pass_when_all_aligned(tmp_path):
    _member(tmp_path, "a", "A", ALIGNED)
    _member(tmp_path, "b", "B", ALIGNED)
    report = check_workspace(_manifest(tmp_path))
    assert report["status"] == "pass", report


def test_workspace_detects_divergent_member(tmp_path):
    _member(tmp_path, "a", "A", ALIGNED)
    # b is missing a rule and adds an extra one
    _member(
        tmp_path,
        "b",
        "B",
        "      - deny secrets_to_llm\n      - require tests_if_code_changed\n      - require extra_rule\n",
    )
    report = check_workspace(_manifest(tmp_path))
    assert report["status"] == "drift"
    b = next(m for m in report["members"] if m["path"] == "b/b.nyx")
    pol = b["policies"][0]
    assert "require human_approval_before_merge" in pol["missing"]
    assert "require extra_rule" in pol["extra"]


def test_workspace_detects_missing_policy(tmp_path):
    _member(tmp_path, "a", "A", ALIGNED)
    d = tmp_path / "b"
    d.mkdir()
    (d / "b.nyx").write_text('nornyx: "0.1"\nproject:\n  name: B\n', encoding="utf-8")
    report = check_workspace(_manifest(tmp_path))
    assert report["status"] == "drift"
    b = next(m for m in report["members"] if m["path"] == "b/b.nyx")
    assert b["policies"][0]["status"] == "missing"


def test_workspace_detects_missing_contract(tmp_path):
    _member(tmp_path, "a", "A", ALIGNED)
    # no b/ at all
    report = check_workspace(_manifest(tmp_path))
    assert report["status"] == "drift"
    b = next(m for m in report["members"] if m["path"] == "b/b.nyx")
    assert b["policies"][0]["status"] == "contract_missing"


def test_workspace_rejects_malformed_manifest(tmp_path):
    m = tmp_path / "bad.yaml"
    m.write_text("workspace: X\nmembers: []\n", encoding="utf-8")  # no policies
    with pytest.raises(WorkspaceError):
        check_workspace(m)


# --- sync mode (write=True) -------------------------------------------------

COMMENTED_MEMBER = """\
nornyx: "0.1"
project:
  name: A
policies:
  # keep this comment
  - name: SafeDeliveryPolicy
    rules:
      - deny secrets_to_llm
      - require extra_local_rule

agents:
  - name: Builder
    role: build
    policy: SafeDeliveryPolicy
"""


def test_workspace_write_syncs_divergent_member(tmp_path):
    from nornyx.parser import load_nyx

    _member(tmp_path, "a", "A", ALIGNED)
    d = tmp_path / "b"
    d.mkdir()
    (d / "b.nyx").write_text(COMMENTED_MEMBER, encoding="utf-8")

    report = check_workspace(_manifest(tmp_path), write=True)
    assert report["status"] == "synced"
    b = next(m for m in report["members"] if m["path"] == "b/b.nyx")
    assert b["policies"][0]["status"] == "synced"

    # File now matches the canonical set, keeps its comment, and is still valid.
    text = (d / "b.nyx").read_text(encoding="utf-8")
    assert "# keep this comment" in text
    assert "extra_local_rule" not in text
    assert "require human_approval_before_merge" in text
    doc = load_nyx(d / "b.nyx")
    assert doc["project"]["name"] == "A"  # untouched

    # Idempotent: a second pass is a clean pass.
    again = check_workspace(_manifest(tmp_path))
    assert again["status"] == "pass"


def test_workspace_write_does_not_invent_missing_policy(tmp_path):
    _member(tmp_path, "a", "A", ALIGNED)
    d = tmp_path / "b"
    d.mkdir()
    (d / "b.nyx").write_text('nornyx: "0.1"\nproject:\n  name: B\n', encoding="utf-8")
    report = check_workspace(_manifest(tmp_path), write=True)
    # Missing policy is left for a human; sync edits existing blocks only.
    assert report["status"] == "drift"
    b = next(m for m in report["members"] if m["path"] == "b/b.nyx")
    assert b["policies"][0]["status"] == "missing"
