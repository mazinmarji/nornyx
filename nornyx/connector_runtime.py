from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any


class ConnectorRuntimeError(Exception):
    pass


SUPPORTED_PROTOCOLS = {"mcp", "a2a"}
PLUGIN_STATUSES = {"experimental", "candidate", "stable", "deprecated"}
SAFE_DEFAULT_MODES = {
    "disabled",
    "read_only",
    "read-only",
    "metadata_only",
    "manifest_only",
    "contract_only",
}
UNSAFE_DEFAULT_MODES = {"enabled", "live", "write", "execute", "full_access", "admin"}
SENSITIVE_SHARE_TOKENS = {"secrets", "credentials", "tokens", "private_memory", "private-memory"}
REQUIRED_ADAPTER_NON_GOALS = {
    "live connector execution",
    "production deployment",
    "unrestricted adapter execution",
    "credential loading",
    "network calls",
    "automatic approvals",
}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _text_list(value: Any) -> list[str]:
    items = []
    for item in _as_list(value):
        if isinstance(item, dict):
            name = item.get("name") or item.get("id") or item.get("capability")
            if name:
                items.append(str(name).strip())
        else:
            items.append(str(item).strip())
    return [item for item in items if item]


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _bool_value(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1", "required"}:
            return True
        if lowered in {"false", "no", "0", "not_required"}:
            return False
    return bool(value)


def _mapping_items(value: Any, *, default_name_prefix: str) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        items = []
        for name, raw in value.items():
            item = dict(raw) if isinstance(raw, dict) else {"value": raw}
            item.setdefault("name", name)
            items.append(item)
        return items
    if value:
        return [{"name": default_name_prefix, "value": value}]
    return []


def _experimental(doc: dict[str, Any]) -> dict[str, Any]:
    experimental = doc.get("experimental")
    return experimental if isinstance(experimental, dict) else {}


def _top_level_or_experimental(doc: dict[str, Any], block: str) -> list[dict[str, Any]]:
    items = _mapping_items(doc.get(block), default_name_prefix=block)
    items.extend(_mapping_items(_experimental(doc).get(block), default_name_prefix=block))
    return items


def normalize_plugins(doc: dict[str, Any]) -> list[dict[str, Any]]:
    plugins = []
    raw_plugins = _top_level_or_experimental(doc, "plugins")
    raw_plugins.extend(_top_level_or_experimental(doc, "extensions"))
    for index, item in enumerate(raw_plugins, start=1):
        name = item.get("name") or item.get("id") or f"plugin_{index}"
        status = str(item.get("status") or "experimental").strip().lower()
        if status not in PLUGIN_STATUSES:
            status = "experimental"
        plugins.append(
            {
                "name": str(name),
                "version": str(item.get("version") or "unversioned"),
                "status": status,
                "provides": _text_list(item.get("provides") or item.get("capabilities")),
                "conformance": _text_list(item.get("conformance") or item.get("tests")),
                "source_index": index,
            }
        )
    return plugins


def _connector_sources(doc: dict[str, Any]) -> list[dict[str, Any]]:
    connectors = _top_level_or_experimental(doc, "connectors")
    for plugin in _top_level_or_experimental(doc, "plugins"):
        plugin_name = plugin.get("name") or plugin.get("id") or "plugin"
        for connector in _mapping_items(plugin.get("connectors"), default_name_prefix="connector"):
            connector = dict(connector)
            connector.setdefault("plugin", plugin_name)
            connectors.append(connector)
    return connectors


def normalize_connectors(doc: dict[str, Any]) -> list[dict[str, Any]]:
    connectors = []
    for index, item in enumerate(_connector_sources(doc), start=1):
        security = item.get("security") if isinstance(item.get("security"), dict) else {}
        name = item.get("name") or item.get("id") or item.get("connector") or f"connector_{index}"
        protocol = str(item.get("protocol") or item.get("adapter") or "").strip().lower()
        default_mode = str(
            item.get("default_mode") or security.get("default_mode") or "disabled"
        ).strip().lower()
        approval_required = _bool_value(
            item.get("approval_required", security.get("requires_approval")),
            default=True,
        )
        share = _text_list(item.get("share") or item.get("shares"))
        never_share = _text_list(
            item.get("never_share") or item.get("deny_share") or security.get("never_share")
        )
        capabilities = _text_list(
            item.get("capabilities") or item.get("provides") or item.get("actions")
        )
        connectors.append(
            {
                "name": str(name),
                "protocol": protocol,
                "version": str(item.get("version") or "unversioned"),
                "plugin": str(item.get("plugin")) if item.get("plugin") else None,
                "capabilities": _dedupe(capabilities),
                "deny": _dedupe(_text_list(item.get("deny") or item.get("blocked"))),
                "share": _dedupe(share),
                "never_share": _dedupe(never_share),
                "default_mode": default_mode,
                "approval_required": approval_required,
                "has_endpoint": bool(item.get("endpoint") or item.get("url") or item.get("server")),
                "has_command": bool(item.get("command") or item.get("exec")),
                "source_index": index,
            }
        )
    return connectors


def _connector_refs(doc: dict[str, Any]) -> list[dict[str, Any]]:
    refs = []
    for harness_index, harness in enumerate(_as_list(doc.get("harnesses")), start=1):
        if not isinstance(harness, dict):
            continue
        harness_name = str(harness.get("name") or f"harness_{harness_index}")
        for step_index, step in enumerate(_as_list(harness.get("flow")), start=1):
            if isinstance(step, dict) and step.get("connector"):
                refs.append(
                    {
                        "harness": harness_name,
                        "step_index": step_index,
                        "connector": str(step["connector"]),
                        "action": step.get("action"),
                    }
                )
    return refs


def _named_items(doc: dict[str, Any], block: str) -> dict[str, dict[str, Any]]:
    return {
        str(item["name"]): item
        for item in _mapping_items(doc.get(block), default_name_prefix=block)
        if isinstance(item, dict) and item.get("name")
    }


def _evidence_required(doc: dict[str, Any]) -> set[str]:
    evidence = doc.get("evidence")
    if not isinstance(evidence, dict):
        return set()
    return {
        str(item)
        for item in _as_list(evidence.get("required"))
        if str(item).strip()
    }


def normalize_adapters(doc: dict[str, Any]) -> list[dict[str, Any]]:
    adapters = []
    for index, item in enumerate(_top_level_or_experimental(doc, "adapters"), start=1):
        name = item.get("name") or item.get("id") or f"adapter_{index}"
        conformance = item.get("connector_conformance")
        if not isinstance(conformance, dict):
            conformance = {}
        adapters.append(
            {
                "name": str(name),
                "kind": str(item.get("kind") or "unspecified"),
                "target_profile": str(item.get("target_profile") or "unspecified"),
                "execution_mode": str(item.get("execution_mode") or "unspecified").strip().lower(),
                "live_connector_execution": _bool_value(
                    item.get("live_connector_execution"),
                    default=False,
                ),
                "connector_refs": _text_list(item.get("connector_refs")),
                "policy_refs": _text_list(item.get("policy_refs")),
                "eval_refs": _text_list(item.get("eval_refs")),
                "evidence_refs": _text_list(item.get("evidence_refs")),
                "connector_conformance": {
                    "protocols": [protocol.lower() for protocol in _text_list(conformance.get("protocols"))],
                    "default_mode": str(conformance.get("default_mode") or "").strip().lower(),
                    "approval_required": _bool_value(
                        conformance.get("approval_required"),
                        default=False,
                    ),
                },
                "non_goals": _text_list(item.get("non_goals")),
                "source_index": index,
            }
        )
    return adapters


def _connector_decisions(connector: dict[str, Any]) -> list[dict[str, Any]]:
    decisions = []
    protocol = connector["protocol"]
    if protocol in SUPPORTED_PROTOCOLS:
        decisions.append(
            {
                "status": "ready",
                "code": "CONNECTOR_PROTOCOL_SUPPORTED",
                "reason": f"{protocol.upper()} connector manifest is recognized.",
            }
        )
    else:
        decisions.append(
            {
                "status": "blocked",
                "code": "CONNECTOR_PROTOCOL_UNSUPPORTED",
                "reason": "Connector protocol must be MCP or A2A for this adapter scaffold.",
            }
        )

    if connector["capabilities"]:
        decisions.append(
            {
                "status": "ready",
                "code": "CONNECTOR_CAPABILITIES_DECLARED",
                "reason": "Connector declares at least one capability.",
            }
        )
    else:
        decisions.append(
            {
                "status": "blocked",
                "code": "CONNECTOR_CAPABILITIES_MISSING",
                "reason": "Connector manifests must declare capabilities.",
            }
        )

    mode = connector["default_mode"]
    if mode in UNSAFE_DEFAULT_MODES:
        decisions.append(
            {
                "status": "blocked",
                "code": "CONNECTOR_DEFAULT_MODE_UNSAFE",
                "reason": "Connector default mode must not enable live/write/execute access.",
            }
        )
    elif mode in SAFE_DEFAULT_MODES:
        decisions.append(
            {
                "status": "ready",
                "code": "CONNECTOR_DEFAULT_MODE_SAFE",
                "reason": "Connector default mode is safe for manifest planning.",
            }
        )
    else:
        decisions.append(
            {
                "status": "warning",
                "code": "CONNECTOR_DEFAULT_MODE_UNKNOWN",
                "reason": "Connector default mode is not recognized; execution remains disabled.",
            }
        )

    if connector["approval_required"]:
        decisions.append(
            {
                "status": "requires_human_approval",
                "code": "CONNECTOR_APPROVAL_REQUIRED",
                "reason": "Connector use requires human approval before any live enablement.",
            }
        )
    else:
        decisions.append(
            {
                "status": "warning",
                "code": "CONNECTOR_APPROVAL_NOT_REQUIRED",
                "reason": "Connector manifest does not require approval; live execution remains disabled.",
            }
        )

    if connector["has_endpoint"] or connector["has_command"]:
        decisions.append(
            {
                "status": "blocked",
                "code": "CONNECTOR_LIVE_TARGET_DECLARED",
                "reason": "Endpoint or command metadata is recorded but live adapter targets are disabled.",
            }
        )

    if connector["protocol"] == "a2a":
        share = {item.lower() for item in connector["share"]}
        never_share = {item.lower() for item in connector["never_share"]}
        sensitive_shared = sorted(share & SENSITIVE_SHARE_TOKENS)
        missing_never_share = sorted(SENSITIVE_SHARE_TOKENS - never_share)
        if sensitive_shared:
            decisions.append(
                {
                    "status": "blocked",
                    "code": "A2A_SENSITIVE_SHARE_BLOCKED",
                    "reason": f"A2A share list includes sensitive categories: {sensitive_shared}",
                }
            )
        if missing_never_share:
            decisions.append(
                {
                    "status": "warning",
                    "code": "A2A_NEVER_SHARE_INCOMPLETE",
                    "reason": "A2A connector should explicitly deny sensitive sharing categories.",
                    "missing": missing_never_share,
                }
            )

    decisions.append(
        {
            "status": "ready",
            "code": "CONNECTOR_EXECUTION_DISABLED",
            "reason": "Adapter planning is local only; no connector is executed.",
        }
    )
    return decisions


def _adapter_status(decisions: list[dict[str, Any]]) -> str:
    statuses = {decision["status"] for decision in decisions}
    if "blocked" in statuses:
        return "blocked"
    if "requires_human_approval" in statuses:
        return "requires_human_approval"
    if "warning" in statuses:
        return "manifest_ready_with_warnings"
    return "manifest_ready"


def _plugin_reports(plugins: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reports = []
    seen: set[str] = set()
    for plugin in plugins:
        decisions = []
        name = plugin["name"]
        if name.lower() in seen:
            decisions.append(
                {
                    "status": "blocked",
                    "code": "PLUGIN_DUPLICATE_NAME",
                    "reason": "Plugin names must be unique.",
                }
            )
        else:
            decisions.append(
                {
                    "status": "ready",
                    "code": "PLUGIN_NAME_UNIQUE",
                    "reason": "Plugin name is unique.",
                }
            )
        seen.add(name.lower())

        if plugin["provides"]:
            decisions.append(
                {
                    "status": "ready",
                    "code": "PLUGIN_PROVIDES_DECLARED",
                    "reason": "Plugin declares provided contracts.",
                }
            )
        else:
            decisions.append(
                {
                    "status": "warning",
                    "code": "PLUGIN_PROVIDES_MISSING",
                    "reason": "Plugin should declare provided contracts.",
                }
            )

        if plugin["status"] in {"candidate", "stable"} and not plugin["conformance"]:
            decisions.append(
                {
                    "status": "blocked",
                    "code": "PLUGIN_CONFORMANCE_REQUIRED",
                    "reason": "Candidate and stable plugins require conformance entries.",
                }
            )

        reports.append({**plugin, "status": _adapter_status(decisions), "decisions": decisions})
    return reports


def _adapter_reports(connectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reports = []
    seen: set[str] = set()
    for connector in connectors:
        decisions = _connector_decisions(connector)
        key = connector["name"].lower()
        if key in seen:
            decisions.append(
                {
                    "status": "blocked",
                    "code": "CONNECTOR_DUPLICATE_NAME",
                    "reason": "Connector names must be unique.",
                }
            )
        seen.add(key)
        reports.append(
            {
                **connector,
                "status": _adapter_status(decisions),
                "execution": "not_executed",
                "decisions": decisions,
            }
        )
    return reports


def _adapter_contract_decisions(
    adapter: dict[str, Any],
    *,
    connectors: dict[str, dict[str, Any]],
    policies: dict[str, dict[str, Any]],
    evals: dict[str, dict[str, Any]],
    evidence_required: set[str],
) -> list[dict[str, Any]]:
    decisions = []
    if adapter["execution_mode"] == "contract_only":
        decisions.append(
            {
                "status": "ready",
                "code": "ADAPTER_EXECUTION_MODE_CONTRACT_ONLY",
                "reason": "Adapter execution mode is contract-only.",
            }
        )
    else:
        decisions.append(
            {
                "status": "blocked",
                "code": "ADAPTER_EXECUTION_MODE_UNSAFE",
                "reason": "Adapter execution mode must remain contract_only.",
            }
        )

    if adapter["live_connector_execution"] is False:
        decisions.append(
            {
                "status": "ready",
                "code": "ADAPTER_LIVE_EXECUTION_DISABLED",
                "reason": "Adapter contract disables live connector execution.",
            }
        )
    else:
        decisions.append(
            {
                "status": "blocked",
                "code": "ADAPTER_LIVE_EXECUTION_ENABLED",
                "reason": "Adapter contracts must not enable live connector execution.",
            }
        )

    for field, declared in [
        ("connector_refs", connectors),
        ("policy_refs", policies),
        ("eval_refs", evals),
    ]:
        refs = adapter[field]
        if not refs:
            decisions.append(
                {
                    "status": "blocked",
                    "code": f"ADAPTER_{field.upper()}_MISSING",
                    "reason": f"Adapter must declare {field}.",
                }
            )
            continue
        unknown = sorted(set(refs) - set(declared))
        if unknown:
            decisions.append(
                {
                    "status": "blocked",
                    "code": f"ADAPTER_{field.upper()}_UNKNOWN",
                    "reason": f"Adapter references unknown {field}: {unknown}",
                    "unknown": unknown,
                }
            )
        else:
            decisions.append(
                {
                    "status": "ready",
                    "code": f"ADAPTER_{field.upper()}_DECLARED",
                    "reason": f"Adapter {field} resolve to declared blocks.",
                }
            )

    if not adapter["evidence_refs"]:
        decisions.append(
            {
                "status": "blocked",
                "code": "ADAPTER_EVIDENCE_REFS_MISSING",
                "reason": "Adapter must declare evidence_refs.",
            }
        )
    else:
        unknown_evidence = sorted(set(adapter["evidence_refs"]) - evidence_required)
        if unknown_evidence:
            decisions.append(
                {
                    "status": "blocked",
                    "code": "ADAPTER_EVIDENCE_REFS_UNKNOWN",
                    "reason": f"Adapter references evidence not declared in evidence.required: {unknown_evidence}",
                    "unknown": unknown_evidence,
                }
            )
        else:
            decisions.append(
                {
                    "status": "ready",
                    "code": "ADAPTER_EVIDENCE_REFS_DECLARED",
                    "reason": "Adapter evidence refs resolve to evidence.required.",
                }
            )

    conformance = adapter["connector_conformance"]
    protocols = set(conformance["protocols"])
    if protocols and protocols <= SUPPORTED_PROTOCOLS:
        decisions.append(
            {
                "status": "ready",
                "code": "ADAPTER_CONNECTOR_PROTOCOLS_SUPPORTED",
                "reason": "Adapter connector conformance uses supported MCP/A2A protocols.",
            }
        )
    else:
        decisions.append(
            {
                "status": "blocked",
                "code": "ADAPTER_CONNECTOR_PROTOCOLS_UNSUPPORTED",
                "reason": "Adapter connector conformance must declare only mcp/a2a protocols.",
            }
        )

    if conformance["default_mode"] in SAFE_DEFAULT_MODES:
        decisions.append(
            {
                "status": "ready",
                "code": "ADAPTER_CONNECTOR_DEFAULT_MODE_SAFE",
                "reason": "Adapter connector conformance default mode is safe.",
            }
        )
    else:
        decisions.append(
            {
                "status": "blocked",
                "code": "ADAPTER_CONNECTOR_DEFAULT_MODE_UNSAFE",
                "reason": "Adapter connector conformance must use a safe default mode.",
            }
        )

    if conformance["approval_required"]:
        decisions.append(
            {
                "status": "requires_human_approval",
                "code": "ADAPTER_CONNECTOR_APPROVAL_REQUIRED",
                "reason": "Adapter connector conformance requires human approval before live enablement.",
            }
        )
    else:
        decisions.append(
            {
                "status": "blocked",
                "code": "ADAPTER_CONNECTOR_APPROVAL_NOT_REQUIRED",
                "reason": "Adapter connector conformance must require approval.",
            }
        )

    missing_non_goals = sorted(REQUIRED_ADAPTER_NON_GOALS - set(adapter["non_goals"]))
    if missing_non_goals:
        decisions.append(
            {
                "status": "blocked",
                "code": "ADAPTER_NON_GOALS_INCOMPLETE",
                "reason": "Adapter non-goals must include the shared safety boundary.",
                "missing": missing_non_goals,
            }
        )
    else:
        decisions.append(
            {
                "status": "ready",
                "code": "ADAPTER_NON_GOALS_COMPLETE",
                "reason": "Adapter non-goals include the shared safety boundary.",
            }
        )

    return decisions


def _adapter_contract_reports(doc: dict[str, Any]) -> list[dict[str, Any]]:
    connectors = _named_items(doc, "connectors")
    policies = _named_items(doc, "policies")
    evals = _named_items(doc, "evals")
    evidence_required = _evidence_required(doc)
    reports = []
    seen: set[str] = set()
    for adapter in normalize_adapters(doc):
        decisions = _adapter_contract_decisions(
            adapter,
            connectors=connectors,
            policies=policies,
            evals=evals,
            evidence_required=evidence_required,
        )
        key = adapter["name"].lower()
        if key in seen:
            decisions.append(
                {
                    "status": "blocked",
                    "code": "ADAPTER_DUPLICATE_NAME",
                    "reason": "Adapter names must be unique.",
                }
            )
        seen.add(key)
        reports.append(
            {
                **adapter,
                "status": _adapter_status(decisions),
                "execution": "not_executed",
                "decisions": decisions,
            }
        )
    return reports


def _reference_reports(refs: list[dict[str, Any]], connectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    declared = {connector["name"] for connector in connectors}
    reports = []
    for ref in refs:
        declared_status = "ready" if ref["connector"] in declared else "blocked"
        reports.append(
            {
                **ref,
                "status": declared_status,
                "code": "CONNECTOR_MANIFEST_DECLARED"
                if declared_status == "ready"
                else "CONNECTOR_MANIFEST_NOT_DECLARED",
                "reason": "Harness connector step has a matching connector manifest."
                if declared_status == "ready"
                else "Harness connector step is denied until a matching connector manifest exists.",
            }
        )
    return reports


def _count_statuses(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"blocked": 0, "requires_human_approval": 0, "warnings": 0, "ready": 0}
    for item in items:
        for decision in item.get("decisions", [item]):
            status = decision.get("status")
            if status == "blocked":
                counts["blocked"] += 1
            elif status == "requires_human_approval":
                counts["requires_human_approval"] += 1
            elif status == "warning":
                counts["warnings"] += 1
            elif status == "ready":
                counts["ready"] += 1
    return counts


def build_connector_report(doc: dict[str, Any]) -> dict[str, Any]:
    plugins = _plugin_reports(normalize_plugins(doc))
    connectors = _adapter_reports(normalize_connectors(doc))
    references = _reference_reports(_connector_refs(doc), connectors)

    plugin_counts = _count_statuses(plugins)
    connector_counts = _count_statuses(connectors)
    reference_counts = _count_statuses(references)
    summary = {
        "plugins": len(plugins),
        "connectors": len(connectors),
        "harness_connector_refs": len(references),
        "blocked": plugin_counts["blocked"]
        + connector_counts["blocked"]
        + reference_counts["blocked"],
        "requires_human_approval": plugin_counts["requires_human_approval"]
        + connector_counts["requires_human_approval"]
        + reference_counts["requires_human_approval"],
        "warnings": plugin_counts["warnings"]
        + connector_counts["warnings"]
        + reference_counts["warnings"],
        "ready_decisions": plugin_counts["ready"]
        + connector_counts["ready"]
        + reference_counts["ready"],
    }
    status = "blocked" if summary["blocked"] else "manifest_ready"
    if status == "manifest_ready" and summary["requires_human_approval"]:
        status = "requires_human_approval"
    if status == "manifest_ready" and summary["warnings"]:
        status = "manifest_ready_with_warnings"

    return {
        "schema": "nornyx.connector_report.v0.1",
        "mode": "safe_local_connector_manifest",
        "status": status,
        "summary": summary,
        "safety": {
            "connectors_enabled": False,
            "adapters_executed": False,
            "network_used": False,
            "commands_executed": False,
            "credentials_loaded": False,
            "default_execution_mode": "disabled",
        },
        "plugins": plugins,
        "connectors": connectors,
        "harness_references": references,
    }


def build_adapter_conformance_report(doc: dict[str, Any]) -> dict[str, Any]:
    connector_report = build_connector_report(doc)
    adapters = _adapter_contract_reports(doc)
    adapter_counts = _count_statuses(adapters)
    summary = {
        "adapters": len(adapters),
        "connectors": connector_report["summary"]["connectors"],
        "harness_connector_refs": connector_report["summary"]["harness_connector_refs"],
        "blocked": adapter_counts["blocked"] + connector_report["summary"]["blocked"],
        "requires_human_approval": adapter_counts["requires_human_approval"]
        + connector_report["summary"]["requires_human_approval"],
        "warnings": adapter_counts["warnings"] + connector_report["summary"]["warnings"],
        "ready_decisions": adapter_counts["ready"] + connector_report["summary"]["ready_decisions"],
    }
    status = "blocked" if summary["blocked"] else "conformant"
    if status == "conformant" and summary["requires_human_approval"]:
        status = "requires_human_approval"
    if status == "conformant" and summary["warnings"]:
        status = "conformant_with_warnings"

    return {
        "schema": "nornyx.adapter_conformance.v0.7",
        "mode": "static_adapter_connector_contract_conformance",
        "status": status,
        "summary": summary,
        "safety": {
            **connector_report["safety"],
            "adapter_contracts_executed": False,
            "live_connector_execution_allowed": False,
        },
        "adapters": adapters,
        "connector_report": connector_report,
    }


def write_connector_report(report: dict[str, Any], path: str | Path) -> Path:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path


def write_adapter_conformance_report(report: dict[str, Any], path: str | Path) -> Path:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path
