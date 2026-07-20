"""AN-006 canonical demonstration: the Governed Customer Support Network.

Runs the same Nornyx contract through both reference adapters (CrewAI-shaped
and LangGraph) with a deterministic local harness: fake model, inert tools,
temporary local files only, no API keys, no sockets, no external writes, and
no production endpoints. Produces validated runtime evidence plus a
measurable, reproducible summary.

Usage:
    python examples/agentic_network_support/run_demo.py --out demo_out

Everything here is fake data. Nornyx validates declarations and supplied
evidence; it does not operate the network or attest runtime truth.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

EXAMPLE_DIR = Path(__file__).resolve().parent
ROOT = EXAMPLE_DIR.parents[1]
for entry in (str(ROOT), str(ROOT / "integrations")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from nornyx.agentic_artifacts import (  # noqa: E402
    build_agentic_network_lock,
    write_agentic_network_artifacts,
    write_agentic_network_lock,
    verify_agentic_network_lock,
)
from nornyx.agentic_evidence import validate_runtime_events  # noqa: E402
from nornyx.eval_import import convert_promptfoo_results  # noqa: E402
from nornyx.eval_runtime import evaluate_document_evals  # noqa: E402
from nornyx.governance import (  # noqa: E402
    GovernanceRegistry,
    compose_governance,
    evaluate_document_governance,
)
from nornyx.parser import load_nyx  # noqa: E402

from nornyx_agentic_adapters.governance_kernel import (  # noqa: E402
    DeterministicClock,
    GovernanceKernel,
    GovernanceViolation,
)
from nornyx_agentic_adapters.crewai_adapter import CrewAIGovernanceAdapter  # noqa: E402
from nornyx_agentic_adapters.langgraph_adapter import (  # noqa: E402
    LangGraphGovernanceAdapter,
    langgraph_available,
)
from nornyx_agentic_adapters.local_harness import (  # noqa: E402
    DuckAgent,
    FakeModel,
    InertTool,
)

CONTRACT = EXAMPLE_DIR / "support_network.nyx"
AS_OF = "2026-07-17T00:00:00Z"
MISSION = "GOAL-SUPPORT-001"
HUMAN_APPROVAL = {
    "role": "network_governance_owner",
    "actor_type": "human",
    "granted": True,
}
AI_APPROVAL = {"role": "network_governance_owner", "actor_type": "model", "granted": True}


def _blocked(summary: dict[str, Any], name: str, fn) -> None:
    try:
        fn()
    except GovernanceViolation as violation:
        summary["blocked_scenarios"][name] = violation.code
        return
    raise AssertionError(f"scenario {name!r} was expected to be blocked")


def _static_rejections(document: dict[str, Any], registry: Any) -> dict[str, str]:
    """Show fail-closed static diagnostics on deliberately broken variants."""

    import copy

    outcomes: dict[str, str] = {}

    def check(name: str, mutate, expected: str) -> None:
        variant = copy.deepcopy(document)
        mutate(variant)
        codes = {
            item.code
            for item in evaluate_document_governance(
                variant, registry=registry, as_of=AS_OF, document_root=EXAMPLE_DIR
            )
        }
        assert expected in codes, (name, expected, sorted(codes))
        outcomes[name] = expected

    check(
        "onward_delegation_denied",
        lambda doc: doc["agentic_network"]["delegations"].append(
            {
                **doc["agentic_network"]["delegations"][0],
                "id": "delegation.onward",
                "delegator_ref": "identity.refund_agent",
                "delegate_ref": "identity.policy_advisor",
                "parent_delegation_ref": "delegation.refund_proposal",
                "current_depth": 1,
            }
        ),
        "AN_ONWARD_DELEGATION_DENIED",
    )
    check(
        "capability_escalation",
        lambda doc: doc["agentic_network"]["memberships"][1]["capability_refs"].append(
            "escalate_high_value_refund"
        ),
        "AN_CAPABILITY_ESCALATION",
    )
    check(
        "ai_approval_rejected_statically",
        lambda doc: doc["governance_evidence"]["records"][2]["producer"].update(
            {"type": "ai_tool"}
        ),
        "AN_APPROVAL_HUMAN_REQUIRED",
    )
    check(
        "handoff_cannot_grant_authority",
        lambda doc: doc["agentic_network"]["handoffs"][0][
            "required_capability_refs"
        ].append("propose_refund_under_limit"),
        "AN_HANDOFF_AUTHORITY_ESCALATION",
    )
    check(
        "sensitive_delegation_scope",
        lambda doc: doc["agentic_network"]["delegations"][0]["scope_refs"].append(
            "secrets"
        ),
        "AN_DELEGATION_SENSITIVE_SHARING",
    )
    check(
        "stale_approval_on_revision_change",
        lambda doc: doc["agentic_network"].update(
            {"subject_revision": "git:" + "9" * 40}
        ),
        "AN_REVISION_MISMATCH",
    )
    return outcomes


def _run_crewai_scenario(kernel: GovernanceKernel) -> dict[str, Any]:
    adapter = CrewAIGovernanceAdapter(kernel)
    summary: dict[str, Any] = {"allowed_scenarios": {}, "blocked_scenarios": {}}
    model = FakeModel(
        {
            "classify": "refund_under_limit",
            "policy": "Refunds under $50 are auto-approvable by policy P-12.",
            "respond": "Your duplicate $12 charge is refunded. Reference: R-1001.",
        }
    )
    reader = InertTool("request_reader", '{"request": "duplicate $12 charge"}')

    coordinator = DuckAgent(role="support_coordinator")
    advisor = DuckAgent(role="policy_advisor")
    refund_agent = DuckAgent(role="refund_agent")

    read_task = adapter.guarded_task(
        coordinator,
        "read_sanitized_request",
        lambda: reader.run(case="case-1001"),
        mission_id=MISSION,
    )
    classify_task = adapter.guarded_task(
        coordinator,
        "classify_support_request",
        lambda: model.complete("classify"),
        mission_id=MISSION,
    )
    policy_task = adapter.guarded_task(
        advisor,
        "retrieve_declared_policy",
        lambda: model.complete("policy"),
        mission_id=MISSION,
    )
    summary["allowed_scenarios"]["read_sanitized_request"] = read_task()
    summary["allowed_scenarios"]["classify_support_request"] = classify_task()
    summary["allowed_scenarios"]["retrieve_declared_policy"] = policy_task()

    kernel.request_delegation("delegation.refund_proposal", mission_id=MISSION)
    refund_task = adapter.guarded_task(
        refund_agent,
        "propose_refund_under_limit",
        lambda: "propose refund of $12 (under limit)",
        mission_id=MISSION,
    )
    summary["allowed_scenarios"]["delegated_refund_proposal"] = refund_task()

    _blocked(
        summary,
        "refund_agent_capability_escalation",
        adapter.guarded_task(
            refund_agent,
            "escalate_high_value_refund",
            lambda: "never",
            mission_id=MISSION,
        ),
    )
    _blocked(
        summary,
        "undeclared_capability",
        adapter.guarded_task(
            coordinator,
            "delete_customer_records",
            lambda: "never",
            mission_id=MISSION,
        ),
    )

    kernel.request_handoff("handoff.high_value_escalation", mission_id=MISSION)
    kernel.complete_handoff("handoff.high_value_escalation", mission_id=MISSION)
    summary["allowed_scenarios"]["high_value_handoff"] = "responsibility transferred"

    escalation = kernel.resolve_identity("escalation_agent")
    kernel.check_capability(escalation, "request_human_approval", mission_id=MISSION)
    _blocked(
        summary,
        "ai_generated_approval",
        lambda: kernel.require_human_approval(
            AI_APPROVAL, mission_id=MISSION, actor_ref=escalation
        ),
    )
    kernel.require_human_approval(
        HUMAN_APPROVAL, mission_id=MISSION, actor_ref=escalation
    )
    summary["allowed_scenarios"]["human_approved_escalation"] = (
        "approval granted by network_governance_owner (human)"
    )
    kernel.check_capability(escalation, "escalate_high_value_refund", mission_id=MISSION)
    summary["allowed_scenarios"]["escalate_high_value_refund"] = "allowed"

    refund_identity = kernel.resolve_identity("refund_agent")
    respond_task = adapter.guarded_task(
        refund_agent,
        "produce_customer_safe_response",
        lambda: model.complete("respond"),
        mission_id=MISSION,
    )
    summary["allowed_scenarios"]["produce_customer_safe_response"] = respond_task()
    _blocked(
        summary,
        "sensitive_sharing",
        lambda: kernel.record_data_shared(
            refund_identity,
            kernel.resolve_identity("support_coordinator"),
            ["customer_response", "private_memory"],
            mission_id=MISSION,
            source_zone="zone.support_internal",
            target_zone="zone.support_internal",
        ),
    )
    _blocked(
        summary,
        "undeclared_zone_crossing",
        lambda: kernel.record_zone_crossing(
            refund_identity,
            "zone.customer_channel",
            "zone.support_internal",
            mission_id=MISSION,
        ),
    )
    kernel.record_zone_crossing(
        refund_identity,
        "zone.support_internal",
        "zone.customer_channel",
        mission_id=MISSION,
        approval_ref="agentic_network_authority",
    )
    kernel.record_data_shared(
        refund_identity,
        kernel.resolve_identity("support_coordinator"),
        ["customer_response"],
        mission_id=MISSION,
        source_zone="zone.support_internal",
        target_zone="zone.customer_channel",
    )
    summary["allowed_scenarios"]["governed_customer_response_share"] = "allowed"
    return summary


def _run_langgraph_scenario(kernel: GovernanceKernel) -> dict[str, Any]:
    adapter = LangGraphGovernanceAdapter(kernel)
    summary: dict[str, Any] = {"allowed_scenarios": {}, "blocked_scenarios": {}}
    model = FakeModel(
        {
            "classify": "refund_under_limit",
            "respond": "Your duplicate $12 charge is refunded. Reference: R-1001.",
        }
    )

    nodes = {
        "read": (
            "support_coordinator",
            "read_sanitized_request",
            lambda state: {"request": "duplicate $12 charge"},
        ),
        "classify": (
            "support_coordinator",
            "classify_support_request",
            lambda state: {"category": model.complete("classify")},
        ),
        "propose": (
            "refund_agent",
            "propose_refund_under_limit",
            lambda state: {"proposal": "refund $12"},
        ),
        "respond": (
            "refund_agent",
            "produce_customer_safe_response",
            lambda state: {"response": model.complete("respond")},
        ),
    }
    edges = [
        ("START", "read"),
        ("read", "classify"),
        ("classify", "propose"),
        ("propose", "respond"),
        ("respond", "END"),
    ]
    if langgraph_available():
        graph = adapter.build_governed_graph(nodes, edges, mission_id=MISSION)
        result = graph.invoke({})
        summary["allowed_scenarios"]["governed_state_graph"] = result["response"]
        summary["framework_native"] = True
    else:  # pragma: no cover - exercised only without langgraph installed
        for name, (agent_key, capability, work) in nodes.items():
            guarded = adapter.guard_node(
                agent_key, capability, work, mission_id=MISSION
            )
            summary["allowed_scenarios"][name] = str(guarded({}))
        summary["framework_native"] = False

    _blocked(
        summary,
        "policy_advisor_refund_attempt",
        lambda: adapter.guard_node(
            "policy_advisor",
            "propose_refund_under_limit",
            lambda state: state,
            mission_id=MISSION,
        )({}),
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(EXAMPLE_DIR / "demo_out"))
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    registry = GovernanceRegistry.builtins()
    document = load_nyx(CONTRACT)
    diagnostics = evaluate_document_governance(
        document, registry=registry, as_of=AS_OF, document_root=EXAMPLE_DIR
    )
    errors = [item for item in diagnostics if item.level == "error"]
    assert not errors, [item.to_dict() for item in errors]

    composition = compose_governance(registry, profile_identity="agentic_network")
    artifact_paths = write_agentic_network_artifacts(
        document, composition, out / "artifacts"
    )
    lock_payload = build_agentic_network_lock(document, composition)
    lock_path = write_agentic_network_lock(
        lock_payload, out / "nornyx.agentic_network.lock"
    )

    summary: dict[str, Any] = {
        "schema": "nornyx.agentic_support_demo_summary.v1",
        "contract": CONTRACT.name,
        "network_id": lock_payload["network_id"],
        "subject_revision": lock_payload["subject_revision"],
        "source_contract_digest": lock_payload["source_contract_digest"],
        "generated_artifacts": len(artifact_paths),
        "governed_identities": len(document["agent_identities"]),
        "capabilities": len(document["capabilities"]),
        "trust_zones": len(document["agentic_network"]["trust_zones"]),
        "frameworks": {},
        "static_rejections": {},
        "safety": {
            "api_keys_used": False,
            "sockets_opened": False,
            "external_writes": False,
            "production_endpoints": False,
            "real_customer_data": False,
        },
    }

    for framework, runner in (
        ("crewai", _run_crewai_scenario),
        ("langgraph", _run_langgraph_scenario),
    ):
        kernel = GovernanceKernel.from_local_controls(
            CONTRACT,
            lock_path,
            framework=framework,
            as_of=AS_OF,
            clock=DeterministicClock(),
        )
        framework_summary = runner(kernel)
        events_path = kernel.write_events(out / f"{framework}_events.json")
        report = validate_runtime_events(
            document,
            composition,
            lock_payload,
            kernel.events_payload(),
            events_root=events_path.parent,
        )
        assert report["status"] == "pass", report["diagnostics"]
        (out / f"{framework}_evidence_report.json").write_text(
            json.dumps(report, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        framework_summary["event_count"] = report["event_count"]
        framework_summary["evidence_validation"] = report["status"]
        summary["frameworks"][framework] = framework_summary

    summary["static_rejections"] = _static_rejections(dict(document), registry)

    drifted = json.loads(json.dumps(dict(document)))
    drifted["capabilities"][0]["risk"] = "medium"
    drift_codes = {
        item.code
        for item in verify_agentic_network_lock(lock_payload, drifted, composition)
    }
    assert "AN_LOCK_SOURCE_STALE" in drift_codes
    summary["contract_drift_detection"] = "AN_LOCK_SOURCE_STALE"
    summary["stale_lock_detection"] = "AN_LOCK_SOURCE_STALE"

    imported = convert_promptfoo_results(
        EXAMPLE_DIR / "eval" / "promptfoo_results.json",
        eval_name="support_response_quality",
        subject_revision=str(document["agentic_network"]["subject_revision"]),
    )
    eval_report = evaluate_document_evals(
        dict(document),
        results=imported,
        repo=EXAMPLE_DIR,
    )
    assert eval_report["status"] in {"passed", "passed_with_integrity_warnings"}, (
        eval_report["status"]
    )
    (out / "eval_report.json").write_text(
        json.dumps(eval_report, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    summary["external_eval"] = {
        "producer": "promptfoo (imported, not executed)",
        "report_sha256": imported["provenance"]["report_sha256"],
        "status": eval_report["status"],
        "metrics_passed": eval_report["summary"]["passed_metrics"],
    }

    summary_path = out / "demo_summary.json"
    summary_path.write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"status": "pass", "summary": str(summary_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
