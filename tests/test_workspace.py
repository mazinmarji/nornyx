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


def _sync_one(tmp_path, src: str, canon: list[str]):
    from nornyx.parser import load_nyx
    from nornyx.workspace import _member_ruleset, sync_policy_in_contract

    f = tmp_path / "c.nyx"
    f.write_text(src, encoding="utf-8")
    assert sync_policy_in_contract(f, "P", canon) is True
    load_nyx(f)  # still valid
    return f, _member_ruleset(f, "P")


CANON = ["deny secrets_to_llm", "require tests_if_code_changed", "require human_approval_before_merge"]
WANT = set(CANON)


def test_sync_handles_flow_style_rules(tmp_path):
    src = 'nornyx: "0.1"\nproject:\n  name: F\npolicies:\n  - name: P\n    rules: [deny secrets_to_llm, require old_rule]\n'
    _, rules = _sync_one(tmp_path, src, CANON)
    assert rules == WANT


def test_sync_handles_deny_require_form(tmp_path):
    src = (
        'nornyx: "0.1"\nproject:\n  name: D\npolicies:\n  - name: P\n'
        "    deny:\n      - secrets_to_llm\n    require:\n      - old_rule\n"
    )
    _, rules = _sync_one(tmp_path, src, CANON)
    assert rules == WANT


def test_sync_only_touches_named_policy(tmp_path):
    from nornyx.workspace import _member_ruleset

    src = (
        'nornyx: "0.1"\nproject:\n  name: M\npolicies:\n'
        "  - name: Other\n    rules:\n      - require keep_me\n"
        "  - name: P\n    rules:\n      - require old_rule\n"
        "  - name: Another\n    rules:\n      - deny keep_me_too\n"
    )
    f, rules = _sync_one(tmp_path, src, CANON)
    assert rules == WANT
    assert _member_ruleset(f, "Other") == {"require keep_me"}
    assert _member_ruleset(f, "Another") == {"deny keep_me_too"}


def test_workspace_check_nudges_to_write_on_syncable_drift(tmp_path):
    from nornyx.workspace import format_workspace

    _member(tmp_path, "a", "A", ALIGNED)
    _member(
        tmp_path, "b", "B",
        "      - deny secrets_to_llm\n      - require tests_if_code_changed\n",  # missing one rule
    )
    report = check_workspace(_manifest(tmp_path))
    assert "--write" in format_workspace(report)


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
