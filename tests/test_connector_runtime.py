from __future__ import annotations

import json
from pathlib import Path

from nornyx.cli import main
from nornyx.connector_runtime import build_connector_report


def _connector(report: dict, name: str) -> dict:
    return next(item for item in report["connectors"] if item["name"] == name)


def _decision(connector: dict, code: str) -> dict:
    return next(item for item in connector["decisions"] if item["code"] == code)


def test_connector_report_plans_mcp_manifest_without_execution() -> None:
    doc = {
        "nornyx": "0.1",
        "project": {"name": "ConnectorFixture"},
        "connectors": [
            {
                "name": "GitHub",
                "protocol": "MCP",
                "capabilities": ["read_repo", "create_pr"],
                "deny": ["delete_repo"],
                "security": {"requires_approval": True, "default_mode": "read_only"},
            }
        ],
    }

    report = build_connector_report(doc)
    connector = _connector(report, "GitHub")

    assert report["status"] == "requires_human_approval"
    assert report["safety"]["connectors_enabled"] is False
    assert report["safety"]["network_used"] is False
    assert connector["execution"] == "not_executed"
    assert _decision(connector, "CONNECTOR_PROTOCOL_SUPPORTED")["status"] == "ready"
    assert _decision(connector, "CONNECTOR_APPROVAL_REQUIRED")["status"] == "requires_human_approval"


def test_connector_report_blocks_live_target_and_unsafe_mode() -> None:
    doc = {
        "nornyx": "0.1",
        "project": {"name": "ConnectorFixture"},
        "connectors": [
            {
                "name": "Unsafe",
                "protocol": "MCP",
                "capabilities": ["write_repo"],
                "endpoint": "https://example.invalid/mcp",
                "security": {"requires_approval": False, "default_mode": "live"},
            }
        ],
    }

    report = build_connector_report(doc)
    connector = _connector(report, "Unsafe")

    assert report["status"] == "blocked"
    assert _decision(connector, "CONNECTOR_DEFAULT_MODE_UNSAFE")["status"] == "blocked"
    assert _decision(connector, "CONNECTOR_LIVE_TARGET_DECLARED")["status"] == "blocked"


def test_connector_report_blocks_harness_connector_without_manifest() -> None:
    doc = {
        "nornyx": "0.1",
        "project": {"name": "ConnectorFixture"},
        "harnesses": [
            {
                "name": "Dev",
                "flow": [{"connector": "GitHub", "action": "read_repo"}],
            }
        ],
    }

    report = build_connector_report(doc)

    assert report["status"] == "blocked"
    assert report["summary"]["harness_connector_refs"] == 1
    assert report["harness_references"][0]["code"] == "CONNECTOR_MANIFEST_NOT_DECLARED"


def test_connector_report_supports_experimental_plugin_connectors() -> None:
    doc = {
        "nornyx": "0.1",
        "project": {"name": "ConnectorFixture"},
        "experimental": {
            "plugins": [
                {
                    "name": "repo-tools",
                    "version": "0.1",
                    "status": "candidate",
                    "provides": ["connector_manifest"],
                    "conformance": ["schemas/connector_manifest.schema.json"],
                    "connectors": [
                        {
                            "name": "AuditPeer",
                            "protocol": "A2A",
                            "capabilities": ["share_evidence_digest"],
                            "share": ["evidence_digest"],
                            "never_share": ["secrets", "credentials", "tokens", "private_memory"],
                            "security": {
                                "requires_approval": True,
                                "default_mode": "contract_only",
                            },
                        }
                    ],
                }
            ]
        },
    }

    report = build_connector_report(doc)

    assert report["summary"]["plugins"] == 1
    assert report["summary"]["connectors"] == 1
    assert _connector(report, "AuditPeer")["protocol"] == "a2a"
    assert report["summary"]["blocked"] == 0


def test_connector_plan_cli_writes_report(tmp_path: Path, capsys) -> None:
    source = tmp_path / "connector.nyx"
    source.write_text(
        """
nornyx: "0.1"
project:
  name: ConnectorFixture
connectors:
  - name: GitHub
    protocol: MCP
    capabilities: [read_repo]
    security:
      requires_approval: true
      default_mode: read_only
""".strip(),
        encoding="utf-8",
    )
    out_path = tmp_path / "connector_report.json"

    assert main(["connector-plan", str(source), "--out", str(out_path)]) == 0

    out = capsys.readouterr().out
    report = json.loads(out_path.read_text(encoding="utf-8"))

    assert "Connector report written" in out
    assert report["schema"] == "nornyx.connector_report.v0.1"
    assert report["summary"]["connectors"] == 1
