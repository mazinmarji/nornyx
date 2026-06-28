from __future__ import annotations

from pathlib import Path

from nornyx.generator import generate_artifacts
from nornyx.parser import load_nyx
from nornyx.repo_drift import check_repo_drift

CONTRACT = """\
nornyx: "0.1"
project:
  name: DriftProbe
policies:
  - name: SafeDeliveryPolicy
    rules:
      - deny secrets_to_llm
      - require tests_if_code_changed
agents:
  - name: Builder
    role: build
    policy: SafeDeliveryPolicy
"""


def _write_contract(tmp_path: Path) -> Path:
    contract = tmp_path / "probe.nyx"
    contract.write_text(CONTRACT, encoding="utf-8")
    return contract


def test_repo_drift_pass_when_in_sync(tmp_path):
    contract = _write_contract(tmp_path)
    out = tmp_path / "gen"
    generate_artifacts(load_nyx(contract), out)
    report = check_repo_drift(contract, out)
    assert report["status"] == "pass", report


def test_repo_drift_detects_policy_change(tmp_path):
    """The key regression: a policy.yaml change is caught even though AGENTS.md
    is unaffected (the AGENTS.md-only gate missed this)."""
    contract = _write_contract(tmp_path)
    out = tmp_path / "gen"
    generate_artifacts(load_nyx(contract), out)

    # Mutate only policy.yaml in the committed dir.
    policy = out / "policy.yaml"
    policy.write_text(policy.read_text(encoding="utf-8") + "\n# stale edit\n", encoding="utf-8")

    report = check_repo_drift(contract, out)
    assert report["status"] == "drift"
    changed = {a["path"]: a["status"] for a in report["artifacts"]}
    assert changed.get("policy.yaml") == "changed"
    assert changed.get("AGENTS.md") == "ok"  # AGENTS.md alone would have passed


def test_repo_drift_detects_missing_and_stray(tmp_path):
    contract = _write_contract(tmp_path)
    out = tmp_path / "gen"
    generate_artifacts(load_nyx(contract), out)
    (out / "policy.yaml").unlink()           # missing
    (out / "leftover.txt").write_text("x", encoding="utf-8")  # stray

    report = check_repo_drift(contract, out)
    statuses = {a["path"]: a["status"] for a in report["artifacts"]}
    assert statuses.get("policy.yaml") == "missing"
    assert statuses.get("leftover.txt") == "stray"
    assert report["status"] == "drift"


def test_repo_drift_reports_contract_error(tmp_path):
    bad = tmp_path / "bad.nyx"
    bad.write_text('nornyx: "0.1"\n', encoding="utf-8")  # no project -> checker error
    report = check_repo_drift(bad, tmp_path / "gen")
    assert report["status"] == "error"
