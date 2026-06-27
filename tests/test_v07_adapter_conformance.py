from __future__ import annotations

import json
from pathlib import Path

from nornyx.connector_runtime import (
    REQUIRED_ADAPTER_NON_GOALS,
    build_adapter_conformance_report,
    write_adapter_conformance_report,
)
from nornyx.parser import load_nyx

EXAMPLE = Path("examples/nornyx_v04_adapter_contracts.nyx")


def _decision_codes(adapter: dict) -> set[str]:
    return {decision["code"] for decision in adapter["decisions"]}


def test_v07_adapter_conformance_report_is_static_and_approval_gated() -> None:
    report = build_adapter_conformance_report(load_nyx(EXAMPLE))

    assert report["schema"] == "nornyx.adapter_conformance.v0.7"
    assert report["mode"] == "static_adapter_connector_contract_conformance"
    assert report["status"] == "requires_human_approval"
    assert report["summary"]["adapters"] == 5
    assert report["summary"]["connectors"] == 2
    assert report["summary"]["blocked"] == 0
    assert report["summary"]["warnings"] == 0
    assert report["safety"]["connectors_enabled"] is False
    assert report["safety"]["adapters_executed"] is False
    assert report["safety"]["adapter_contracts_executed"] is False
    assert report["safety"]["live_connector_execution_allowed"] is False

    for adapter in report["adapters"]:
        assert adapter["execution"] == "not_executed"
        assert adapter["execution_mode"] == "contract_only"
        assert adapter["live_connector_execution"] is False
        assert REQUIRED_ADAPTER_NON_GOALS <= set(adapter["non_goals"])
        assert {
            "ADAPTER_EXECUTION_MODE_CONTRACT_ONLY",
            "ADAPTER_LIVE_EXECUTION_DISABLED",
            "ADAPTER_CONNECTOR_REFS_DECLARED",
            "ADAPTER_POLICY_REFS_DECLARED",
            "ADAPTER_EVAL_REFS_DECLARED",
            "ADAPTER_EVIDENCE_REFS_DECLARED",
            "ADAPTER_CONNECTOR_PROTOCOLS_SUPPORTED",
            "ADAPTER_CONNECTOR_DEFAULT_MODE_SAFE",
            "ADAPTER_CONNECTOR_APPROVAL_REQUIRED",
            "ADAPTER_NON_GOALS_COMPLETE",
        } <= _decision_codes(adapter)


def test_v07_adapter_conformance_blocks_unsafe_adapter_contracts() -> None:
    doc = {
        "nornyx": "0.2",
        "project": {"name": "UnsafeAdapterFixture"},
        "policies": [{"name": "AdapterPolicy"}],
        "evals": [{"name": "AdapterEval"}],
        "evidence": {"required": ["adapter_conformance_report.json"]},
        "connectors": [
            {
                "name": "UnsafeConnector",
                "protocol": "MCP",
                "capabilities": ["write_remote"],
                "endpoint": "https://example.invalid/mcp",
                "security": {"requires_approval": False, "default_mode": "live"},
            }
        ],
        "adapters": [
            {
                "name": "UnsafeAdapter",
                "kind": "governed_delivery_control_plane",
                "target_profile": "ai_coding",
                "execution_mode": "execute",
                "live_connector_execution": True,
                "connector_refs": ["MissingConnector"],
                "policy_refs": ["MissingPolicy"],
                "eval_refs": ["MissingEval"],
                "evidence_refs": ["missing.json"],
                "connector_conformance": {
                    "protocols": ["mcp", "custom"],
                    "default_mode": "live",
                    "approval_required": False,
                },
                "non_goals": ["production deployment"],
            }
        ],
    }

    report = build_adapter_conformance_report(doc)
    adapter = report["adapters"][0]
    codes = _decision_codes(adapter)

    assert report["status"] == "blocked"
    assert report["summary"]["blocked"] > 0
    assert {
        "ADAPTER_EXECUTION_MODE_UNSAFE",
        "ADAPTER_LIVE_EXECUTION_ENABLED",
        "ADAPTER_CONNECTOR_REFS_UNKNOWN",
        "ADAPTER_POLICY_REFS_UNKNOWN",
        "ADAPTER_EVAL_REFS_UNKNOWN",
        "ADAPTER_EVIDENCE_REFS_UNKNOWN",
        "ADAPTER_CONNECTOR_PROTOCOLS_UNSUPPORTED",
        "ADAPTER_CONNECTOR_DEFAULT_MODE_UNSAFE",
        "ADAPTER_CONNECTOR_APPROVAL_NOT_REQUIRED",
        "ADAPTER_NON_GOALS_INCOMPLETE",
    } <= codes
    assert report["safety"]["connectors_enabled"] is False
    assert report["safety"]["network_used"] is False
    assert report["safety"]["credentials_loaded"] is False


def test_v07_adapter_conformance_report_can_be_written(tmp_path: Path) -> None:
    report = build_adapter_conformance_report(load_nyx(EXAMPLE))
    out = write_adapter_conformance_report(report, tmp_path / "adapter_conformance_report.json")

    payload = json.loads(out.read_text(encoding="utf-8"))

    assert payload["schema"] == "nornyx.adapter_conformance.v0.7"
    assert payload["summary"]["adapters"] == 5


def test_v07_adapter_and_connector_conformance_schemas_are_contract_only() -> None:
    adapter_schema = json.loads(Path("schemas/adapter_conformance_report.schema.json").read_text(encoding="utf-8"))
    connector_schema = json.loads(Path("schemas/connector_contract_conformance.schema.json").read_text(encoding="utf-8"))

    assert adapter_schema["properties"]["safety"]["properties"]["connectors_enabled"]["const"] is False
    assert adapter_schema["properties"]["safety"]["properties"]["adapter_contracts_executed"]["const"] is False
    assert adapter_schema["properties"]["safety"]["properties"]["live_connector_execution_allowed"]["const"] is False
    assert connector_schema["properties"]["approval_required"]["const"] is True
    assert connector_schema["properties"]["live_targets_allowed"]["const"] is False
    assert connector_schema["properties"]["sensitive_sharing_allowed"]["const"] is False
