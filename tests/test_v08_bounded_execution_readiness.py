from __future__ import annotations

import json
from pathlib import Path

from nornyx.bounded_execution import (
    build_bounded_execution_readiness_report,
    write_bounded_execution_readiness_report,
)
from nornyx.parser import load_nyx

EXAMPLE = Path("examples/nornyx_v04_adapter_contracts.nyx")


def _codes(report: dict) -> set[str]:
    return {decision["code"] for decision in report["decisions"]}


def test_v08_bounded_execution_readiness_is_static_and_approval_gated() -> None:
    report = build_bounded_execution_readiness_report(load_nyx(EXAMPLE), harness_name="AdapterContractHarness")

    assert report["schema"] == "nornyx.bounded_execution_readiness.v0.8"
    assert report["mode"] == "static_bounded_execution_readiness"
    assert report["status"] == "requires_human_approval"
    assert report["summary"]["blocked"] == 0
    assert report["summary"]["requires_human_approval"] > 0
    assert report["sandbox"] == {
        "filesystem": "workspace_only",
        "network": "disabled",
        "credentials": "disabled",
        "production": "disabled",
        "shell": "disabled",
        "approval_required": True,
        "trace_required": True,
        "evidence_required": True,
    }
    assert report["safety"] == {
        "execution_enabled": False,
        "tools_executed": False,
        "agents_executed": False,
        "connectors_enabled": False,
        "models_called": False,
        "network_used": False,
        "credentials_loaded": False,
        "production_deployments": False,
        "approvals_granted": False,
        "self_modification": False,
        "arbitrary_commands_allowed": False,
    }
    assert {
        "SANDBOX_NETWORK_SAFE",
        "SANDBOX_CREDENTIALS_SAFE",
        "SANDBOX_PRODUCTION_SAFE",
        "SANDBOX_SHELL_SAFE",
        "APPROVAL_BEFORE_ACTION_REQUIRED",
        "ACTIVE_CAPABILITY_STEPS_REQUIRE_APPROVAL",
        "REPAIR_ATTEMPTS_BOUNDED",
        "POLICY_BLOCKS_ABSENT",
        "ADAPTER_CONFORMANCE_BLOCKS_ABSENT",
    } <= _codes(report)


def test_v08_bounded_execution_readiness_blocks_unsafe_sandbox() -> None:
    doc = {
        "nornyx": "0.2",
        "project": {"name": "UnsafeBoundedExecution"},
        "experimental": {
            "bounded_execution": {
                "sandbox": {
                    "filesystem": "full_access",
                    "network": "enabled",
                    "credentials": "enabled",
                    "production": "enabled",
                    "shell": "execute",
                    "approval_required": False,
                    "trace_required": False,
                    "evidence_required": False,
                }
            }
        },
        "policies": [{"name": "SafePolicy"}],
        "agents": [{"name": "Builder", "policy": "SafePolicy"}],
        "harnesses": [{"name": "UnsafeHarness", "flow": [{"agent": "Builder", "action": "plan"}]}],
        "evidence": {"required": ["bounded_execution_readiness_report.json"]},
    }

    report = build_bounded_execution_readiness_report(doc, harness_name="UnsafeHarness")

    assert report["status"] == "blocked"
    assert report["summary"]["blocked"] > 0
    assert {
        "SANDBOX_NETWORK_UNSAFE",
        "SANDBOX_CREDENTIALS_UNSAFE",
        "SANDBOX_PRODUCTION_UNSAFE",
        "SANDBOX_SHELL_UNSAFE",
        "SANDBOX_APPROVAL_REQUIRED_MISSING",
        "SANDBOX_TRACE_REQUIRED_MISSING",
        "SANDBOX_EVIDENCE_REQUIRED_MISSING",
        "APPROVAL_BEFORE_ACTION_GATE_MISSING",
    } <= _codes(report)
    assert report["safety"]["execution_enabled"] is False
    assert report["safety"]["network_used"] is False
    assert report["safety"]["credentials_loaded"] is False


def test_v08_bounded_execution_readiness_report_can_be_written(tmp_path: Path) -> None:
    report = build_bounded_execution_readiness_report(load_nyx(EXAMPLE), harness_name="AdapterContractHarness")
    out = write_bounded_execution_readiness_report(report, tmp_path / "bounded_execution_readiness.json")

    payload = json.loads(out.read_text(encoding="utf-8"))

    assert payload["schema"] == "nornyx.bounded_execution_readiness.v0.8"
    assert payload["safety"]["execution_enabled"] is False


def test_v08_bounded_execution_readiness_schema_is_non_executing() -> None:
    schema = json.loads(Path("schemas/bounded_execution_readiness.schema.json").read_text(encoding="utf-8"))
    safety = schema["properties"]["safety"]["properties"]
    sandbox = schema["properties"]["sandbox"]["properties"]

    assert safety["execution_enabled"]["const"] is False
    assert safety["connectors_enabled"]["const"] is False
    assert safety["network_used"]["const"] is False
    assert safety["credentials_loaded"]["const"] is False
    assert safety["approvals_granted"]["const"] is False
    assert sandbox["network"]["const"] == "disabled"
    assert sandbox["credentials"]["const"] == "disabled"
    assert sandbox["approval_required"]["const"] is True
