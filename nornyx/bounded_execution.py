from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .connector_runtime import build_adapter_conformance_report
from .harness_runtime import MAX_REPAIR_ATTEMPTS, normalize_flow, normalize_gates, normalize_repairs, select_harness
from .policy_runtime import evaluate_harness_policy, normalize_capabilities


REQUIRED_SANDBOX_FIELDS = {
    "filesystem",
    "network",
    "credentials",
    "production",
    "shell",
    "approval_required",
    "trace_required",
    "evidence_required",
}
SAFE_SANDBOX_VALUES = {
    "filesystem": {"read_only", "workspace_only", "disabled"},
    "network": {"disabled"},
    "credentials": {"disabled"},
    "production": {"disabled"},
    "shell": {"disabled", "allowlisted"},
}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


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


def _experimental(doc: dict[str, Any]) -> dict[str, Any]:
    experimental = doc.get("experimental")
    return experimental if isinstance(experimental, dict) else {}


def _bounded_execution_config(doc: dict[str, Any]) -> dict[str, Any]:
    raw = doc.get("bounded_execution")
    if not isinstance(raw, dict):
        raw = _experimental(doc).get("bounded_execution")
    return raw if isinstance(raw, dict) else {}


def sandbox_contract(doc: dict[str, Any]) -> dict[str, Any]:
    config = _bounded_execution_config(doc)
    sandbox = config.get("sandbox") if isinstance(config.get("sandbox"), dict) else {}
    return {
        "filesystem": str(sandbox.get("filesystem") or "workspace_only").strip().lower(),
        "network": str(sandbox.get("network") or "disabled").strip().lower(),
        "credentials": str(sandbox.get("credentials") or "disabled").strip().lower(),
        "production": str(sandbox.get("production") or "disabled").strip().lower(),
        "shell": str(sandbox.get("shell") or "disabled").strip().lower(),
        "approval_required": _bool_value(sandbox.get("approval_required"), default=True),
        "trace_required": _bool_value(sandbox.get("trace_required"), default=True),
        "evidence_required": _bool_value(sandbox.get("evidence_required"), default=True),
    }


def _decision(status: str, code: str, reason: str, **extra: Any) -> dict[str, Any]:
    return {"status": status, "code": code, "reason": reason, **extra}


def _sandbox_decisions(contract: dict[str, Any]) -> list[dict[str, Any]]:
    decisions = []
    for field in sorted(REQUIRED_SANDBOX_FIELDS):
        if field not in contract:
            decisions.append(_decision("blocked", "SANDBOX_FIELD_MISSING", f"Sandbox field {field} is required.", field=field))
    for field, safe_values in SAFE_SANDBOX_VALUES.items():
        value = contract.get(field)
        if value in safe_values:
            decisions.append(_decision("ready", f"SANDBOX_{field.upper()}_SAFE", f"Sandbox {field} is {value!r}."))
        else:
            decisions.append(_decision("blocked", f"SANDBOX_{field.upper()}_UNSAFE", f"Sandbox {field} must be one of {sorted(safe_values)}.", value=value))
    for field in ["approval_required", "trace_required", "evidence_required"]:
        if contract.get(field) is True:
            decisions.append(_decision("ready", f"SANDBOX_{field.upper()}", f"Sandbox requires {field.replace('_', ' ')}."))
        else:
            decisions.append(_decision("blocked", f"SANDBOX_{field.upper()}_MISSING", f"Sandbox must require {field.replace('_', ' ')}."))
    return decisions


def _capability_decisions(doc: dict[str, Any]) -> list[dict[str, Any]]:
    decisions = []
    capabilities = normalize_capabilities(doc)
    if not capabilities:
        decisions.append(_decision("ready", "CAPABILITY_DEFAULT_DENY", "No capabilities are declared; default deny remains active."))
        return decisions
    for capability in capabilities:
        if capability["approval_required"]:
            decisions.append(_decision("requires_human_approval", "CAPABILITY_APPROVAL_REQUIRED", "Capability requires human approval before use.", capability=capability["id"]))
        else:
            decisions.append(_decision("warning", "CAPABILITY_APPROVAL_NOT_REQUIRED", "Capability does not require approval; bounded execution readiness should review it.", capability=capability["id"]))
    return decisions


def _readiness_status(decisions: list[dict[str, Any]]) -> str:
    statuses = {decision["status"] for decision in decisions}
    if "blocked" in statuses:
        return "blocked"
    if "requires_human_approval" in statuses:
        return "requires_human_approval"
    if "warning" in statuses:
        return "ready_with_warnings"
    return "ready"


def _count_decisions(decisions: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"blocked": 0, "requires_human_approval": 0, "warnings": 0, "ready": 0}
    for decision in decisions:
        status = decision["status"]
        if status == "warning":
            counts["warnings"] += 1
        elif status in counts:
            counts[status] += 1
    return counts


def build_bounded_execution_readiness_report(
    doc: dict[str, Any],
    *,
    harness_name: str | None = None,
) -> dict[str, Any]:
    harness = select_harness(doc, harness_name)
    selected_harness_name = str(harness.get("name", "UnnamedHarness"))
    flow = normalize_flow(harness)
    gates = normalize_gates(harness)
    repairs = normalize_repairs(harness)
    policy_report = evaluate_harness_policy(doc, selected_harness_name)
    adapter_report = build_adapter_conformance_report(doc)
    sandbox = sandbox_contract(doc)

    decisions: list[dict[str, Any]] = []
    decisions.extend(_sandbox_decisions(sandbox))
    decisions.extend(_capability_decisions(doc))
    if any(gate["status"] == "requires_human_approval" for gate in gates):
        decisions.append(_decision("requires_human_approval", "APPROVAL_BEFORE_ACTION_REQUIRED", "Harness declares approval gates that cannot be auto-satisfied."))
    else:
        decisions.append(_decision("blocked", "APPROVAL_BEFORE_ACTION_GATE_MISSING", "Harness must declare an approval-before-action gate."))
    if any(step["kind"] in {"tool", "connector", "model"} for step in flow):
        decisions.append(_decision("requires_human_approval", "ACTIVE_CAPABILITY_STEPS_REQUIRE_APPROVAL", "Tool, connector, or model steps require explicit approval before execution."))
    else:
        decisions.append(_decision("ready", "NO_ACTIVE_CAPABILITY_STEPS", "Harness has no tool, connector, or model steps."))
    if any(repair["max_attempts"] > MAX_REPAIR_ATTEMPTS for repair in repairs):
        decisions.append(_decision("blocked", "REPAIR_ATTEMPTS_UNBOUNDED", "Repair attempts exceed the configured maximum."))
    else:
        decisions.append(_decision("ready", "REPAIR_ATTEMPTS_BOUNDED", "Repair attempts are bounded."))
    if policy_report["summary"]["blocked"]:
        decisions.append(_decision("blocked", "POLICY_BLOCKS_PRESENT", "Policy report has blocked decisions.", blocked=policy_report["summary"]["blocked"]))
    else:
        decisions.append(_decision("ready", "POLICY_BLOCKS_ABSENT", "Policy report has no blocked decisions."))
    if adapter_report["summary"]["blocked"]:
        decisions.append(_decision("blocked", "ADAPTER_CONFORMANCE_BLOCKS_PRESENT", "Adapter conformance has blocked decisions.", blocked=adapter_report["summary"]["blocked"]))
    else:
        decisions.append(_decision("ready", "ADAPTER_CONFORMANCE_BLOCKS_ABSENT", "Adapter conformance has no blocked decisions."))

    summary = _count_decisions(decisions)
    return {
        "schema": "nornyx.bounded_execution_readiness.v0.8",
        "mode": "static_bounded_execution_readiness",
        "status": _readiness_status(decisions),
        "harness": selected_harness_name,
        "summary": summary,
        "sandbox": sandbox,
        "flow": flow,
        "gates": gates,
        "repair": repairs,
        "policy_summary": policy_report["summary"],
        "adapter_conformance_summary": adapter_report["summary"],
        "safety": {
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
        },
        "decisions": decisions,
    }


def write_bounded_execution_readiness_report(report: dict[str, Any], path: str | Path) -> Path:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path
