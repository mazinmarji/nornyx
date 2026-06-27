from __future__ import annotations

import json
from pathlib import Path

from nornyx.checker import EXTENSION_TOP_LEVEL_BLOCKS, check_document, has_errors
from nornyx.connector_runtime import build_connector_report
from nornyx.parser import load_nyx
from nornyx.schema_model import FORMAL_GRAMMAR_V0_1, load_v01_schema, schema_model_summary

EXAMPLE = Path("examples/nornyx_v04_adapter_contracts.nyx")
EXPECTED_ADAPTER_KINDS = {
    "governed_delivery_control_plane",
    "agentic_development_harness",
    "governance_adapter",
    "telecom_ops",
    "business_ops",
}
REQUIRED_NON_GOALS = {
    "live connector execution",
    "production deployment",
    "unrestricted adapter execution",
    "credential loading",
    "network calls",
    "automatic approvals",
}


def _doc() -> dict:
    return load_nyx(EXAMPLE)


def _names(items: list[dict]) -> set[str]:
    return {item["name"] for item in items}


def test_v04_adapter_contract_example_is_checkable() -> None:
    doc = _doc()
    diagnostics = check_document(doc)

    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics]
    assert doc["nornyx"] == "0.2"
    assert "adapters" in EXTENSION_TOP_LEVEL_BLOCKS


def test_v04_adapter_contract_schema_is_contract_only() -> None:
    schema = json.loads(Path("schemas/adapter_contract.schema.json").read_text(encoding="utf-8"))

    assert schema["title"] == "Nornyx v0.4 Adapter Contract"
    assert schema["properties"]["execution_mode"]["const"] == "contract_only"
    assert schema["properties"]["live_connector_execution"]["const"] is False
    assert "credential loading" in schema["properties"]["non_goals"]["items"]["enum"]
    assert "network calls" in schema["properties"]["non_goals"]["items"]["enum"]


def test_v04_adapter_extension_surface_is_in_compatibility_schema() -> None:
    schema = load_v01_schema()
    summary = schema_model_summary()

    assert "adapters" in schema["properties"]
    assert schema["properties"]["adapters"]["items"]["$ref"] == "#/$defs/adapter"
    assert "adapter_block" in FORMAL_GRAMMAR_V0_1
    assert summary["v0_4_adapter_surface"]["adapters"].startswith("Contract-only")


def test_v04_adapter_contracts_cover_required_ecosystem_bridges() -> None:
    adapters = _doc()["adapters"]

    assert {adapter["kind"] for adapter in adapters} == EXPECTED_ADAPTER_KINDS
    assert {adapter["execution_mode"] for adapter in adapters} == {"contract_only"}
    assert {adapter["live_connector_execution"] for adapter in adapters} == {False}
    for adapter in adapters:
        assert set(adapter["non_goals"]) == REQUIRED_NON_GOALS
        assert adapter["connector_conformance"]["approval_required"] is True
        assert adapter["connector_conformance"]["default_mode"] == "contract_only"


def test_v04_adapter_references_bind_to_policy_eval_evidence_and_connectors() -> None:
    doc = _doc()
    policy_names = _names(doc["policies"])
    eval_names = _names(doc["evals"])
    connector_names = _names(doc["connectors"])
    evidence_required = set(doc["evidence"]["required"])

    for adapter in doc["adapters"]:
        assert set(adapter["policy_refs"]) <= policy_names
        assert set(adapter["eval_refs"]) <= eval_names
        assert set(adapter["connector_refs"]) <= connector_names
        assert set(adapter["evidence_refs"]) <= evidence_required


def test_v04_connector_conformance_remains_safe_and_non_executing() -> None:
    report = build_connector_report(_doc())

    assert report["status"] == "requires_human_approval"
    assert report["summary"]["connectors"] == 2
    assert report["summary"]["harness_connector_refs"] == 2
    assert report["summary"]["blocked"] == 0
    assert report["safety"] == {
        "connectors_enabled": False,
        "adapters_executed": False,
        "network_used": False,
        "commands_executed": False,
        "credentials_loaded": False,
        "default_execution_mode": "disabled",
    }
    for connector in report["connectors"]:
        assert connector["execution"] == "not_executed"
        assert connector["default_mode"] == "contract_only"
        assert connector["approval_required"] is True
        assert connector["has_endpoint"] is False
        assert connector["has_command"] is False
