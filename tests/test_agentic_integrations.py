"""AN-005 tests: CrewAI and LangGraph reference adapters over one contract."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from typing import Any

import pytest
import yaml

from nornyx.agentic_artifacts import (
    build_agentic_network_lock,
    write_agentic_network_lock,
)
from nornyx.agentic_evidence import validate_runtime_events
from nornyx.governance import GovernanceRegistry, compose_governance


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "agentic_network.nyx"
INTEGRATIONS = ROOT / "integrations"
if str(INTEGRATIONS) not in sys.path:
    sys.path.insert(0, str(INTEGRATIONS))

from nornyx_agentic_adapters.governance_kernel import (  # noqa: E402
    DeterministicClock,
    GovernanceKernel,
    GovernanceViolation,
)
from nornyx_agentic_adapters.crewai_adapter import (  # noqa: E402
    CrewAIGovernanceAdapter,
    crewai_available,
)
from nornyx_agentic_adapters.langgraph_adapter import (  # noqa: E402
    LangGraphGovernanceAdapter,
    langgraph_available,
)
from nornyx_agentic_adapters.local_harness import (  # noqa: E402
    DuckAgent,
    FakeModel,
    InertTool,
)


AS_OF = "2026-07-17T00:00:00Z"
REGISTRY = GovernanceRegistry.builtins()
COMPOSITION = compose_governance(REGISTRY, profile_identity="agentic_network")


def _document() -> dict[str, Any]:
    document = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    for identity, key in (
        (document["agent_identities"][0], "researcher"),
        (document["agent_identities"][1], "reviewer"),
    ):
        identity["framework_bindings"].extend(
            [
                {"framework": "crewai", "agent_key": key},
                {"framework": "langgraph", "agent_key": key},
            ]
        )
    document["capabilities"][1]["delegable"] = True
    document["capabilities"][1]["max_delegation_depth"] = 2
    document["agentic_network"]["delegations"] = [
        {
            "id": "delegation.research",
            "delegator_ref": "identity.researcher.local",
            "delegate_ref": "identity.reviewer.local",
            "capability_ref": "propose_research_finding",
            "purpose": "Bounded review-cycle finding proposals",
            "actions": ["propose_finding"],
            "scope_refs": ["GovernedNetworkContext"],
            "status": "active",
            "valid_from": "2026-01-01T00:00:00Z",
            "expires_at": "2026-08-01T00:00:00Z",
            "max_depth": 2,
            "current_depth": 0,
            "onward_delegation": "allowed_with_policy",
            "source_zone_ref": "zone.local_governed",
            "target_zone_ref": "zone.local_governed",
            "required_gate_refs": [],
            "required_policy_refs": [],
            "required_approval_refs": [],
            "required_evidence_refs": [],
            "revocation_refs": [],
        }
    ]
    document["agentic_network"]["handoffs"] = [
        {
            "id": "handoff.review",
            "from_identity_ref": "identity.researcher.local",
            "to_identity_ref": "identity.reviewer.local",
            "purpose": "Transfer finding-review responsibility",
            "mission_ref": "GOAL-001",
            "from_zone_ref": "zone.local_governed",
            "to_zone_ref": "zone.local_governed",
            "required_capability_refs": ["read_governed_context"],
            "delegation_refs": [],
            "shared_context": ["finding_summary"],
            "never_share": ["secrets", "credentials", "tokens", "private_memory"],
            "status": "initiated",
            "valid_from": "2026-01-01T00:00:00Z",
            "expires_at": "2026-08-01T00:00:00Z",
            "required_gate_refs": [],
            "required_approval_refs": [],
            "required_evidence_refs": [],
            "revocation_refs": [],
        }
    ]
    return document


@pytest.fixture(scope="module")
def controls(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("an005-controls")
    shutil.copytree(
        EXAMPLE.parent / "governance_evidence", root / "governance_evidence"
    )
    document = _document()
    contract = root / "contract.nyx"
    contract.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    lock_path = root / "nornyx.agentic_network.lock"
    write_agentic_network_lock(
        build_agentic_network_lock(document, COMPOSITION), lock_path
    )
    return {
        "root": root,
        "document": document,
        "contract": contract,
        "lock": lock_path,
    }


def _kernel(controls: dict[str, Any], framework: str) -> GovernanceKernel:
    return GovernanceKernel.from_local_controls(
        controls["contract"],
        controls["lock"],
        framework=framework,
        as_of=AS_OF,
        clock=DeterministicClock(),
    )


def test_one_contract_governs_both_frameworks(controls: dict[str, Any]) -> None:
    crewai_kernel = _kernel(controls, "crewai")
    langgraph_kernel = _kernel(controls, "langgraph")
    assert crewai_kernel.contract_digest == langgraph_kernel.contract_digest
    assert crewai_kernel.lock_digest == langgraph_kernel.lock_digest
    assert (
        crewai_kernel.resolve_identity("researcher")
        == langgraph_kernel.resolve_identity("researcher")
        == "identity.researcher.local"
    )


def test_crewai_identity_mapping_and_guarded_task(controls: dict[str, Any]) -> None:
    kernel = _kernel(controls, "crewai")
    adapter = CrewAIGovernanceAdapter(kernel)
    agent = DuckAgent(role="researcher")
    assert adapter.resolve_identity(agent) == "identity.researcher.local"

    model = FakeModel({"classify": "governed-response"})
    tool = InertTool("reader", "sanitized text")
    task = adapter.guarded_task(
        agent,
        "read_governed_context",
        lambda: model.complete("classify") + ":" + tool.run(document="request-1"),
        mission_id="mission.crewai",
    )
    assert task() == "governed-response:sanitized text"
    types = [event["event_type"] for event in kernel.events_payload()["events"]]
    assert types == ["capability_requested", "capability_allowed", "tool_invoked"]


def test_capability_denial_is_fail_closed(controls: dict[str, Any]) -> None:
    kernel = _kernel(controls, "crewai")
    adapter = CrewAIGovernanceAdapter(kernel)
    reviewer = DuckAgent(role="reviewer")
    # `propose_research_finding` is reachable only through the declared
    # delegation, so it is allowed; an unassigned capability must deny.
    blocked = adapter.guarded_task(
        reviewer,
        "propose_research_finding",
        lambda: "delegated work",
        mission_id="mission.delegated",
    )
    assert blocked() == "delegated work"
    delegated_event = kernel.events_payload()["events"][1]
    assert delegated_event["event_type"] == "capability_allowed"
    assert delegated_event["delegation_ref"] == "delegation.research"

    kernel = _kernel(controls, "crewai")
    adapter = CrewAIGovernanceAdapter(kernel)
    researcher = DuckAgent(role="researcher")
    with pytest.raises(GovernanceViolation) as excinfo:
        adapter.guarded_task(
            researcher,
            "undeclared_capability",
            lambda: "never",
            mission_id="mission.denied",
        )()
    assert excinfo.value.code == "AN_ADAPTER_CAPABILITY_UNKNOWN"

    stripped = _document()
    stripped["agentic_network"]["delegations"] = []
    bare = GovernanceKernel(
        stripped,
        COMPOSITION,
        build_agentic_network_lock(stripped, COMPOSITION),
        framework="crewai",
    )
    with pytest.raises(GovernanceViolation) as excinfo:
        bare.check_capability(
            "identity.reviewer.local",
            "propose_research_finding",
            mission_id="mission.denied",
        )
    assert excinfo.value.code == "AN_ADAPTER_CAPABILITY_DENIED"
    types = [event["event_type"] for event in bare.events_payload()["events"]]
    assert types == ["capability_requested", "capability_denied"]


def test_delegation_requests_validate_against_declarations(
    controls: dict[str, Any],
) -> None:
    kernel = _kernel(controls, "crewai")
    kernel.request_delegation("delegation.research", mission_id="mission.delegate")
    types = [event["event_type"] for event in kernel.events_payload()["events"]]
    assert types == ["delegation_requested", "delegation_accepted"]

    with pytest.raises(GovernanceViolation) as excinfo:
        kernel.request_delegation("delegation.unknown", mission_id="mission.delegate")
    assert excinfo.value.code == "AN_ADAPTER_DELEGATION_UNKNOWN"

    suspended = _document()
    suspended["agentic_network"]["delegations"][0]["status"] = "suspended"
    inactive = GovernanceKernel(
        suspended,
        COMPOSITION,
        build_agentic_network_lock(suspended, COMPOSITION),
        framework="crewai",
    )
    with pytest.raises(GovernanceViolation) as excinfo:
        inactive.request_delegation(
            "delegation.research", mission_id="mission.delegate"
        )
    assert excinfo.value.code == "AN_ADAPTER_DELEGATION_INACTIVE"


def test_handoff_transfers_responsibility_not_authority(
    controls: dict[str, Any],
) -> None:
    kernel = _kernel(controls, "crewai")
    kernel.request_handoff("handoff.review", mission_id="mission.handoff")
    kernel.complete_handoff("handoff.review", mission_id="mission.handoff")
    types = [event["event_type"] for event in kernel.events_payload()["events"]]
    assert types == ["handoff_initiated", "handoff_completed"]

    with pytest.raises(GovernanceViolation) as excinfo:
        kernel.request_handoff("handoff.unknown", mission_id="mission.handoff")
    assert excinfo.value.code == "AN_ADAPTER_HANDOFF_UNKNOWN"

    escalating = _document()
    escalating["agentic_network"]["delegations"] = []
    escalating["agentic_network"]["handoffs"][0]["required_capability_refs"] = [
        "propose_research_finding"
    ]
    bare = GovernanceKernel(
        escalating,
        COMPOSITION,
        build_agentic_network_lock(escalating, COMPOSITION),
        framework="crewai",
    )
    with pytest.raises(GovernanceViolation) as excinfo:
        bare.request_handoff("handoff.review", mission_id="mission.handoff")
    assert excinfo.value.code == "AN_ADAPTER_HANDOFF_AUTHORITY"


def test_missing_enforcement_hook_fails_closed() -> None:
    with pytest.raises(GovernanceViolation) as excinfo:
        CrewAIGovernanceAdapter(None)
    assert excinfo.value.code == "AN_ADAPTER_HOOK_MISSING"
    with pytest.raises(GovernanceViolation) as excinfo:
        LangGraphGovernanceAdapter(None)
    assert excinfo.value.code == "AN_ADAPTER_HOOK_MISSING"


def test_framework_and_identity_mismatches(controls: dict[str, Any]) -> None:
    langgraph_kernel = _kernel(controls, "langgraph")
    with pytest.raises(GovernanceViolation) as excinfo:
        CrewAIGovernanceAdapter(langgraph_kernel)
    assert excinfo.value.code == "AN_ADAPTER_FRAMEWORK_MISMATCH"

    with pytest.raises(GovernanceViolation) as excinfo:
        langgraph_kernel.resolve_identity("unbound-agent")
    assert excinfo.value.code == "AN_ADAPTER_IDENTITY_UNKNOWN"


def test_stale_controls_and_wrong_digest_fail_closed(
    controls: dict[str, Any], tmp_path: Path
) -> None:
    shutil.copytree(
        EXAMPLE.parent / "governance_evidence", tmp_path / "governance_evidence"
    )
    document = _document()
    contract = tmp_path / "contract.nyx"
    contract.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    lock_path = tmp_path / "nornyx.agentic_network.lock"
    write_agentic_network_lock(
        build_agentic_network_lock(document, COMPOSITION), lock_path
    )

    document["capabilities"][0]["risk"] = "medium"
    contract.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    with pytest.raises(GovernanceViolation) as excinfo:
        GovernanceKernel.from_local_controls(
            contract, lock_path, framework="crewai", as_of=AS_OF
        )
    assert excinfo.value.code == "AN_ADAPTER_LOCK_STALE"

    other = _document()
    other["agentic_network"]["id"] = "network.other"
    wrong_lock = tmp_path / "wrong.lock"
    write_agentic_network_lock(
        build_agentic_network_lock(other, COMPOSITION), wrong_lock
    )
    with pytest.raises(GovernanceViolation) as excinfo:
        GovernanceKernel.from_local_controls(
            controls["contract"], wrong_lock, framework="crewai", as_of=AS_OF
        )
    assert excinfo.value.code == "AN_ADAPTER_LOCK_STALE"


def test_invalid_contract_cannot_load(controls: dict[str, Any], tmp_path: Path) -> None:
    shutil.copytree(
        EXAMPLE.parent / "governance_evidence", tmp_path / "governance_evidence"
    )
    document = _document()
    document["agent_identities"][0]["capability_refs"].append("missing_capability")
    contract = tmp_path / "invalid.nyx"
    contract.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    with pytest.raises(GovernanceViolation) as excinfo:
        GovernanceKernel.from_local_controls(
            contract, controls["lock"], framework="crewai", as_of=AS_OF
        )
    assert excinfo.value.code == "AN_ADAPTER_CONTRACT_INVALID"


def test_human_approval_is_required_and_ai_approval_rejected(
    controls: dict[str, Any],
) -> None:
    kernel = _kernel(controls, "crewai")
    kernel.require_human_approval(
        {"role": "network_governance_owner", "actor_type": "human", "granted": True},
        mission_id="mission.approval",
        actor_ref="identity.researcher.local",
    )
    types = [event["event_type"] for event in kernel.events_payload()["events"]]
    assert types == ["approval_requested", "approval_granted"]

    for record, expected in (
        (
            {"role": "network_governance_owner", "actor_type": "model", "granted": True},
            "AN_ADAPTER_APPROVAL_NON_HUMAN",
        ),
        (
            {"role": "unlisted_role", "actor_type": "human", "granted": True},
            "AN_ADAPTER_APPROVAL_ROLE_INVALID",
        ),
        (
            {"role": "network_governance_owner", "actor_type": "human", "granted": False},
            "AN_ADAPTER_APPROVAL_NOT_GRANTED",
        ),
    ):
        kernel = _kernel(controls, "crewai")
        with pytest.raises(GovernanceViolation) as excinfo:
            kernel.require_human_approval(
                record,
                mission_id="mission.approval",
                actor_ref="identity.researcher.local",
            )
        assert excinfo.value.code == expected


def test_zone_and_sensitive_sharing_enforcement(controls: dict[str, Any]) -> None:
    kernel = _kernel(controls, "crewai")
    kernel.record_zone_crossing(
        "identity.reviewer.local",
        "zone.local_governed",
        "zone.external_contract",
        mission_id="mission.zone",
        approval_ref="agentic_network_authority",
    )
    with pytest.raises(GovernanceViolation) as excinfo:
        kernel.record_zone_crossing(
            "identity.reviewer.local",
            "zone.external_contract",
            "zone.local_governed",
            mission_id="mission.zone",
        )
    assert excinfo.value.code == "AN_ADAPTER_ZONE_CROSSING_DENIED"

    # AN5-AUD-001: an external-classified destination without an approval
    # reference fails fast at the adapter, not only at evidence validation.
    with pytest.raises(GovernanceViolation) as excinfo:
        kernel.record_zone_crossing(
            "identity.reviewer.local",
            "zone.local_governed",
            "zone.external_contract",
            mission_id="mission.zone",
        )
    assert excinfo.value.code == "AN_ADAPTER_CROSSING_APPROVAL_REQUIRED"

    with pytest.raises(GovernanceViolation) as excinfo:
        kernel.record_data_shared(
            "identity.researcher.local",
            "identity.reviewer.local",
            ["finding_summary", "secrets"],
            mission_id="mission.zone",
            source_zone="zone.local_governed",
            target_zone="zone.local_governed",
        )
    assert excinfo.value.code == "AN_ADAPTER_SENSITIVE_SHARING"

    with pytest.raises(GovernanceViolation) as excinfo:
        kernel.record_data_shared(
            "identity.researcher.local",
            "identity.reviewer.local",
            ["undeclared_category"],
            mission_id="mission.zone",
            source_zone="zone.local_governed",
            target_zone="zone.local_governed",
        )
    assert excinfo.value.code == "AN_ADAPTER_SHARE_NOT_ALLOWED"


def _run_governed_scenario(kernel: GovernanceKernel) -> None:
    mission = "GOAL-001"
    researcher = kernel.resolve_identity("researcher")
    reviewer = kernel.resolve_identity("reviewer")
    kernel.invoke_tool(researcher, "read_governed_context", mission_id=mission)
    kernel.request_delegation("delegation.research", mission_id=mission)
    kernel.check_capability(
        reviewer, "propose_research_finding", mission_id=mission
    )
    kernel.request_handoff("handoff.review", mission_id=mission)
    kernel.complete_handoff("handoff.review", mission_id=mission)
    kernel.require_human_approval(
        {"role": "network_governance_owner", "actor_type": "human", "granted": True},
        mission_id=mission,
        actor_ref=researcher,
    )
    kernel.record_data_shared(
        researcher,
        reviewer,
        ["finding_summary"],
        mission_id=mission,
        source_zone="zone.local_governed",
        target_zone="zone.local_governed",
    )


def test_emitted_evidence_validates_against_the_lock(
    controls: dict[str, Any],
) -> None:
    for framework in ("crewai", "langgraph"):
        kernel = _kernel(controls, framework)
        _run_governed_scenario(kernel)
        report = validate_runtime_events(
            controls["document"],
            COMPOSITION,
            kernel.lock_payload,
            kernel.events_payload(),
        )
        assert report["status"] == "pass", (framework, report["diagnostics"])
        assert report["event_count"] == 12


def test_evidence_emission_is_deterministic(controls: dict[str, Any]) -> None:
    first = _kernel(controls, "crewai")
    second = _kernel(controls, "crewai")
    _run_governed_scenario(first)
    _run_governed_scenario(second)
    assert first.events_payload() == second.events_payload()


def test_no_credentials_endpoints_or_network_in_evidence(
    controls: dict[str, Any],
) -> None:
    from nornyx.agentic_artifacts import _scan_forbidden

    kernel = _kernel(controls, "crewai")
    _run_governed_scenario(kernel)
    _scan_forbidden(
        {
            key: value
            for key, value in kernel.events_payload().items()
            if key != "events"
        },
        path="events_file",
    )
    for index, event in enumerate(kernel.events_payload()["events"]):
        filtered = {
            key: value
            for key, value in event.items()
            if key not in {"share_categories", "never_share"}
        }
        _scan_forbidden(filtered, path=f"events[{index}]")


def test_full_adapter_flow_uses_no_network_or_processes(
    controls: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("adapter flow attempted an external operation")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)

    kernel = _kernel(controls, "crewai")
    _run_governed_scenario(kernel)
    report = validate_runtime_events(
        controls["document"],
        COMPOSITION,
        kernel.lock_payload,
        kernel.events_payload(),
    )
    assert report["status"] == "pass"


@pytest.mark.skipif(not langgraph_available(), reason="langgraph is not installed")
def test_langgraph_native_state_graph_is_governed(controls: dict[str, Any]) -> None:
    from typing_extensions import TypedDict

    class State(TypedDict, total=False):
        request: str
        reading: str
        proposal: str

    kernel = _kernel(controls, "langgraph")
    adapter = LangGraphGovernanceAdapter(kernel)
    model = FakeModel({"propose": "bounded proposal"})

    graph = adapter.build_governed_graph(
        {
            "read": (
                "researcher",
                "read_governed_context",
                lambda state: {"reading": f"sanitized:{state['request']}"},
            ),
            "propose": (
                "reviewer",
                "propose_research_finding",
                lambda state: {"proposal": model.complete("propose")},
            ),
        },
        [("START", "read"), ("read", "propose"), ("propose", "END")],
        mission_id="GOAL-001",
        state_schema=State,
    )
    result = graph.invoke({"request": "customer question"})
    assert result["reading"] == "sanitized:customer question"
    assert result["proposal"] == "bounded proposal"
    events = kernel.events_payload()["events"]
    assert [event["event_type"] for event in events] == [
        "capability_requested",
        "capability_allowed",
        "tool_invoked",
        "capability_requested",
        "capability_allowed",
        "tool_invoked",
    ]
    assert events[4]["delegation_ref"] == "delegation.research"
    report = validate_runtime_events(
        controls["document"],
        COMPOSITION,
        kernel.lock_payload,
        kernel.events_payload(),
    )
    assert report["status"] == "pass"


@pytest.mark.skipif(not langgraph_available(), reason="langgraph is not installed")
def test_langgraph_denied_node_fails_closed(controls: dict[str, Any]) -> None:
    stripped = _document()
    stripped["agentic_network"]["delegations"] = []
    kernel = GovernanceKernel(
        stripped,
        COMPOSITION,
        build_agentic_network_lock(stripped, COMPOSITION),
        framework="langgraph",
    )
    adapter = LangGraphGovernanceAdapter(kernel)
    graph = adapter.build_governed_graph(
        {
            "propose": (
                "reviewer",
                "propose_research_finding",
                lambda state: {"proposal": "never"},
            ),
        },
        [("START", "propose"), ("propose", "END")],
        mission_id="GOAL-001",
    )
    with pytest.raises(GovernanceViolation) as excinfo:
        graph.invoke({})
    assert excinfo.value.code == "AN_ADAPTER_CAPABILITY_DENIED"


@pytest.mark.skipif(not crewai_available(), reason="crewai is not installed")
def test_crewai_native_agent_objects_are_governed(controls: dict[str, Any]) -> None:
    from crewai import Agent

    kernel = _kernel(controls, "crewai")
    adapter = CrewAIGovernanceAdapter(kernel)
    agent = Agent(
        role="researcher",
        goal="governed local demonstration",
        backstory="deterministic fixture",
        allow_delegation=False,
    )
    assert adapter.resolve_identity(agent) == "identity.researcher.local"
    task = adapter.guarded_task(
        agent,
        "read_governed_context",
        lambda: "sanitized",
        mission_id="GOAL-001",
    )
    assert task() == "sanitized"


def test_default_install_does_not_package_integrations() -> None:
    import nornyx

    package_root = Path(nornyx.__file__).resolve().parent
    assert not (package_root / "integrations").exists()
    assert not (package_root / "nornyx_agentic_adapters").exists()
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'include = ["nornyx*"]' in pyproject
    assert "crewai" not in pyproject
    assert "langgraph" not in pyproject


def test_kernel_never_writes_outside_requested_paths(
    controls: dict[str, Any], tmp_path: Path
) -> None:
    kernel = _kernel(controls, "crewai")
    _run_governed_scenario(kernel)
    target = tmp_path / "evidence" / "events.json"
    kernel.write_events(target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["schema"] == "nornyx.agentic_runtime_events.v1"
    assert len(payload["events"]) == 12
