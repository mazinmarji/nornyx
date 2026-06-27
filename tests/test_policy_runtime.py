from __future__ import annotations

import json
from pathlib import Path

from nornyx.cli import main
from nornyx.parser import load_nyx
from nornyx.policy_runtime import evaluate_harness_policy, normalize_policy_rules


def _decision(report: dict, kind: str, ref: str) -> dict:
    return next(
        item
        for item in report["decisions"]
        if item["kind"] == kind and item["ref"] == ref
    )


def test_policy_rules_normalize_legacy_and_explicit_forms() -> None:
    rules = normalize_policy_rules(
        {
            "rules": ["deny secrets_to_llm", "require tests_if_code_changed"],
            "deny": ["destructive_commands"],
            "require": ["evidence_if_goal_completed"],
        }
    )

    assert rules == {
        "deny": ["destructive_commands", "secrets_to_llm"],
        "require": ["evidence_if_goal_completed", "tests_if_code_changed"],
    }


def test_policy_runtime_default_denies_undeclared_tool_capability() -> None:
    doc = load_nyx(Path("examples/governed_delivery_control_plane.nyx"))
    report = evaluate_harness_policy(doc, harness_name="DevHarness")
    tool = _decision(report, "tool", "tests")

    assert report["default_capability_mode"] == "deny_unless_declared"
    assert tool["status"] == "blocked"
    assert tool["code"] == "CAPABILITY_NOT_DECLARED"
    assert report["summary"]["blocked"] == 1
    assert report["safety"]["tools_executed"] is False


def test_policy_runtime_allows_explicit_tool_capability_without_execution() -> None:
    doc = {
        "nornyx": "0.1",
        "project": {"name": "PolicyFixture"},
        "policies": [
            {
                "name": "SafeEdit",
                "deny": ["production_write_without_approval"],
                "require": ["tests_if_code_changed"],
            }
        ],
        "agents": [{"name": "Builder", "policy": "SafeEdit"}],
        "capabilities": [
            {
                "name": "tests",
                "kind": "tool",
                "allow": ["run"],
                "approval_required": False,
            }
        ],
        "harnesses": [
            {
                "name": "Dev",
                "flow": [
                    {"agent": "Builder", "action": "implement"},
                    {"tool": "tests", "action": "run"},
                    {"evidence": "DevEvidence", "action": "pack"},
                ],
            }
        ],
    }

    report = evaluate_harness_policy(doc, harness_name="Dev")
    tool = _decision(report, "tool", "tests")
    agent = _decision(report, "agent", "Builder")

    assert tool["status"] == "allowed"
    assert tool["code"] == "CAPABILITY_ALLOWED"
    assert agent["pending_requirements"] == [
        {"rule": "tests_if_code_changed", "status": "pending_evidence"}
    ]
    assert report["summary"]["blocked"] == 0


def test_policy_runtime_blocks_external_model_without_guardrail() -> None:
    doc = {
        "nornyx": "0.1",
        "project": {"name": "PolicyFixture"},
        "capabilities": [
            {
                "name": "review_model",
                "kind": "model",
                "allow": ["call"],
                "approval_required": False,
            }
        ],
        "harnesses": [
            {
                "name": "Dev",
                "flow": [{"model": "review_model", "action": "call"}],
            }
        ],
    }

    report = evaluate_harness_policy(doc, harness_name="Dev")
    model = _decision(report, "model", "review_model")

    assert model["status"] == "blocked"
    assert model["code"] == "GUARDRAIL_REQUIRED_FOR_EXTERNAL_USE"


def test_policy_check_cli_writes_report(tmp_path: Path, capsys) -> None:
    out_path = tmp_path / "policy_report.json"

    assert (
        main(
            [
                "policy-check",
                "examples/governed_delivery_control_plane.nyx",
                "--harness",
                "DevHarness",
                "--out",
                str(out_path),
            ]
        )
        == 0
    )

    out = capsys.readouterr().out
    report = json.loads(out_path.read_text(encoding="utf-8"))

    assert "Policy report written" in out
    assert report["schema"] == "nornyx.policy_report.v0.1"
    assert report["summary"]["blocked"] == 1
