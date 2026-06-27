from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .connector_runtime import build_connector_report, write_connector_report
from .context_builder import build_context_pack, write_context_pack
from .eval_runtime import evaluate_document_evals, write_eval_report
from .evidence import create_evidence_pack
from .policy_runtime import evaluate_harness_policy, write_policy_report
from .trace_runtime import (
    make_trace_event,
    make_trace_id,
    write_trace_bundle,
    write_trace_digest,
)

MAX_REPAIR_ATTEMPTS = 3


class HarnessRuntimeError(Exception):
    pass


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _project_name(doc: dict[str, Any]) -> str:
    project = doc.get("project")
    if isinstance(project, dict) and project.get("name"):
        return str(project["name"])
    return "UnnamedProject"


def _harnesses(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in _as_list(doc.get("harnesses")) if isinstance(item, dict)]


def select_harness(doc: dict[str, Any], name: str | None = None) -> dict[str, Any]:
    harnesses = _harnesses(doc)
    if not harnesses:
        raise HarnessRuntimeError("No harnesses are defined in the .nyx document")
    if name is None:
        return harnesses[0]
    for harness in harnesses:
        if harness.get("name") == name:
            return harness
    raise HarnessRuntimeError(f"Harness {name!r} is not defined")


def _step_kind(step: dict[str, Any]) -> tuple[str, str | None]:
    for key in ["agent", "tool", "connector", "model", "eval", "evidence"]:
        if key in step:
            return key, str(step.get(key))
    return "unknown", None


def normalize_flow(harness: dict[str, Any]) -> list[dict[str, Any]]:
    flow = []
    for index, step in enumerate(_as_list(harness.get("flow")), start=1):
        if not isinstance(step, dict):
            flow.append(
                {
                    "index": index,
                    "kind": "invalid",
                    "ref": None,
                    "action": None,
                    "status": "blocked",
                    "reason": "flow step must be a mapping",
                }
            )
            continue
        kind, ref = _step_kind(step)
        flow.append(
            {
                "index": index,
                "kind": kind,
                "ref": ref,
                "action": step.get("action"),
                "status": "planned",
                "execution": "not_executed",
            }
        )
    return flow


def _eval_refs(flow: list[dict[str, Any]]) -> list[str]:
    refs = []
    for step in flow:
        if step.get("kind") == "eval" and step.get("ref"):
            refs.append(str(step["ref"]))
    return refs


def normalize_gates(harness: dict[str, Any]) -> list[dict[str, Any]]:
    raw_gates = _as_list(harness.get("gate")) + _as_list(harness.get("gates"))
    gates = []
    for index, gate in enumerate(raw_gates, start=1):
        if isinstance(gate, dict):
            requirement = gate.get("require")
        else:
            requirement = gate
        requirement_text = str(requirement or "").strip()
        if not requirement_text:
            status = "blocked"
            reason = "gate requirement is empty"
        elif "approval" in requirement_text:
            status = "requires_human_approval"
            reason = "approval gates cannot be auto-satisfied by the harness runtime"
        else:
            status = "pending_evidence"
            reason = "gate requires external evidence before completion"
        gates.append(
            {
                "index": index,
                "require": requirement_text,
                "status": status,
                "reason": reason,
            }
        )
    return gates


def normalize_repairs(harness: dict[str, Any]) -> list[dict[str, Any]]:
    repairs = []
    for index, repair in enumerate(_as_list(harness.get("repair")), start=1):
        if not isinstance(repair, dict):
            repairs.append(
                {
                    "index": index,
                    "status": "blocked",
                    "reason": "repair entry must be a mapping",
                    "max_attempts": 0,
                }
            )
            continue
        requested = repair.get("max_attempts", 0)
        try:
            requested_attempts = int(requested)
        except (TypeError, ValueError):
            requested_attempts = 0
        bounded_attempts = max(0, min(requested_attempts, MAX_REPAIR_ATTEMPTS))
        repairs.append(
            {
                "index": index,
                "on": repair.get("on"),
                "agent": repair.get("agent"),
                "action": repair.get("action"),
                "max_attempts": bounded_attempts,
                "requested_max_attempts": requested,
                "status": "not_started",
                "execution": "not_executed",
            }
        )
    return repairs


def _approval_log(gates: list[dict[str, Any]]) -> dict[str, Any]:
    required = [
        {"gate": gate["require"], "status": "pending"}
        for gate in gates
        if gate["status"] == "requires_human_approval"
    ]
    return {
        "schema": "nornyx.approval_log.v0.1",
        "approvals": required,
        "note": "Harness runtime MVP records approval requirements; it does not grant approvals.",
    }


def _trace_events(
    trace_id: str,
    harness_name: str,
    flow: list[dict[str, Any]],
    gates: list[dict[str, Any]],
    policy_report: dict[str, Any] | None = None,
    eval_report: dict[str, Any] | None = None,
    connector_report: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    events = [
        make_trace_event(
            trace_id,
            "harness.run_planned",
            attributes={
                "nornyx.harness": harness_name,
                "nornyx.tools_executed": False,
                "nornyx.runtime_mode": "safe_local_manifest",
            },
        )
    ]
    events.extend(
        make_trace_event(
            trace_id,
            "harness.step_planned",
            attributes={
                "nornyx.step_index": step["index"],
                "nornyx.step_kind": step["kind"],
                "nornyx.step_ref": step["ref"],
                "nornyx.step_action": step["action"],
            },
        )
        for step in flow
    )
    if policy_report:
        summary = policy_report.get("summary", {})
        events.append(
            make_trace_event(
                trace_id,
                "harness.policy_evaluated",
                attributes={
                    "nornyx.policy.blocked": summary.get("blocked", 0),
                    "nornyx.policy.allowed": summary.get("allowed", 0),
                    "nornyx.policy.pending_evidence": summary.get("pending_evidence", 0),
                    "nornyx.policy.requires_human_approval": summary.get(
                        "requires_human_approval", 0
                    ),
                    "nornyx.policy.default_capability_mode": policy_report.get(
                        "default_capability_mode"
                    ),
                },
            )
        )
    if eval_report:
        summary = eval_report.get("summary", {})
        events.append(
            make_trace_event(
                trace_id,
                "harness.evals_recorded",
                attributes={
                    "nornyx.evals.status": eval_report.get("status"),
                    "nornyx.evals.count": summary.get("evals", 0),
                    "nornyx.evals.pending_metrics": summary.get("pending_metrics", 0),
                    "nornyx.evals.integrity_warnings": summary.get(
                        "integrity_warnings", 0
                    ),
                    "nornyx.evals.integrity_blockers": summary.get(
                        "integrity_blockers", 0
                    ),
                },
            )
        )
    if connector_report:
        summary = connector_report.get("summary", {})
        events.append(
            make_trace_event(
                trace_id,
                "harness.connectors_planned",
                attributes={
                    "nornyx.connectors.status": connector_report.get("status"),
                    "nornyx.connectors.count": summary.get("connectors", 0),
                    "nornyx.connectors.plugins": summary.get("plugins", 0),
                    "nornyx.connectors.blocked": summary.get("blocked", 0),
                    "nornyx.connectors.requires_human_approval": summary.get(
                        "requires_human_approval", 0
                    ),
                    "nornyx.connectors.enabled": False,
                },
            )
        )
    events.extend(
        make_trace_event(
            trace_id,
            "harness.gate_recorded",
            attributes={
                "nornyx.gate_index": gate["index"],
                "nornyx.gate_requirement": gate["require"],
                "nornyx.gate_status": gate["status"],
            },
        )
        for gate in gates
    )
    return events


def run_harness(
    doc: dict[str, Any],
    repo: str | Path,
    out_dir: str | Path,
    *,
    harness_name: str | None = None,
    include_content: bool = False,
) -> dict[str, Any]:
    harness = select_harness(doc, harness_name)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    context_pack = build_context_pack(doc, repo, include_content=include_content)
    context_path = write_context_pack(context_pack, out / "context_pack.json")
    flow = normalize_flow(harness)
    gates = normalize_gates(harness)
    repairs = normalize_repairs(harness)
    harness_name_value = str(harness.get("name", "UnnamedHarness"))
    policy_report = evaluate_harness_policy(doc, harness_name_value)
    policy_path = write_policy_report(policy_report, out / "policy_report.json")
    eval_names = _eval_refs(flow)
    eval_report = evaluate_document_evals(doc, eval_names=eval_names)
    eval_path = write_eval_report(eval_report, out / "eval_report.json")
    connector_report = build_connector_report(doc)
    connector_path = write_connector_report(connector_report, out / "connector_report.json")
    run_status = (
        "planned_with_policy_blocks"
        if policy_report["summary"]["blocked"]
        else "planned"
    )
    trace_id = make_trace_id(
        {
            "project": _project_name(doc),
            "harness": harness_name_value,
            "context_entries": context_pack["count"],
        }
    )
    approval_path = out / "approval_log.json"
    approval_path.write_text(
        json.dumps(_approval_log(gates), indent=2),
        encoding="utf-8",
    )
    trace_bundle = write_trace_bundle(
        _trace_events(
            trace_id,
            harness_name_value,
            flow,
            gates,
            policy_report,
            eval_report,
            connector_report,
        ),
        out / "trace_bundle.json",
    )
    trace_digest = write_trace_digest(trace_bundle, out / "trace_digest.json")
    evidence_paths = create_evidence_pack(
        out / "evidence",
        status=run_status,
        trace_digest=trace_digest,
        runtime_artifacts=[
            context_path,
            approval_path,
            policy_path,
            eval_path,
            connector_path,
            out / "trace_bundle.json",
            out / "trace_digest.json",
        ],
    )
    manifest = {
        "schema": "nornyx.harness_run.v0.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project": _project_name(doc),
        "harness": harness_name_value,
        "mode": "safe_local_manifest",
        "status": run_status,
        "safety": {
            "tools_executed": False,
            "agents_executed": False,
            "repairs_executed": False,
            "external_connectors_used": False,
            "arbitrary_commands_allowed": False,
            "default_capability_mode": policy_report["default_capability_mode"],
            "connectors_enabled": connector_report["safety"]["connectors_enabled"],
        },
        "context_pack": str(context_path),
        "context_entries": context_pack["count"],
        "policy_report": str(policy_path),
        "policy_summary": policy_report["summary"],
        "eval_report": str(eval_path),
        "eval_summary": eval_report["summary"],
        "connector_report": str(connector_path),
        "connector_summary": connector_report["summary"],
        "trace_bundle": str(out / "trace_bundle.json"),
        "trace_digest": trace_digest,
        "flow": flow,
        "gates": gates,
        "repair": repairs,
        "evidence": [str(path) for path in evidence_paths],
    }
    (out / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    return manifest
