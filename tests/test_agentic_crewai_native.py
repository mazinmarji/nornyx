"""AN-005 P1 gate: framework-native CrewAI verification.

Exercises real CrewAI ``Agent``/``Task``/``Crew`` objects and the
``Crew.kickoff()`` lifecycle against the Nornyx governance kernel with a
deterministic offline LLM. No API key, no external model call, no network,
no subprocess: telemetry is disabled before ``crewai`` is imported and the
kickoff-path tests monkeypatch socket and process primitives to hard-fail.

The module skips (never errors) when ``crewai`` is not installed so the
default offline suite stays green; the hosted native-frameworks CI job
installs CrewAI and asserts these tests ran without skips.
"""

from __future__ import annotations

import os

# Telemetry must be off before the first `crewai` import in this process.
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

crewai = pytest.importorskip("crewai")

from crewai import Agent, BaseLLM, Crew, Process, Task  # noqa: E402
from crewai.tools import BaseTool  # noqa: E402

from nornyx.agentic_artifacts import (  # noqa: E402
    build_agentic_network_lock,
    write_agentic_network_lock,
)
from nornyx.agentic_evidence import validate_runtime_events  # noqa: E402
from nornyx.governance import GovernanceRegistry, compose_governance  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "agentic_network.nyx"
INTEGRATIONS = ROOT / "integrations"
if str(INTEGRATIONS) not in sys.path:
    sys.path.insert(0, str(INTEGRATIONS))

from nornyx_agentic_adapters.crewai_adapter import (  # noqa: E402
    CrewAIGovernanceAdapter,
)
from nornyx_agentic_adapters.governance_kernel import (  # noqa: E402
    DeterministicClock,
    GovernanceKernel,
    GovernanceViolation,
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
        identity["framework_bindings"].append(
            {"framework": "crewai", "agent_key": key}
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
    root = tmp_path_factory.mktemp("an005-crewai-native")
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


def _kernel(controls: dict[str, Any]) -> GovernanceKernel:
    return GovernanceKernel.from_local_controls(
        controls["contract"],
        controls["lock"],
        framework="crewai",
        as_of=AS_OF,
        clock=DeterministicClock(),
    )


class DeterministicLLM(BaseLLM):
    """Scripted offline LLM driving CrewAI's native ReAct executor.

    The first call of a task emits an ``Action:`` step for the configured
    governed tool; every later call emits a ``Final Answer:``. Never touches
    a network, an API key, or an external model.
    """

    def __init__(self, tool_name: str | None, final_answer: str):
        super().__init__(model="nornyx-deterministic-offline")
        self._tool_name = tool_name
        self._final_answer = final_answer
        self._call_count = 0

    def call(
        self,
        messages: Any,
        tools: Any = None,
        callbacks: Any = None,
        available_functions: Any = None,
        **kwargs: Any,
    ) -> str:
        self._call_count += 1
        if self._tool_name is not None and self._call_count == 1:
            return (
                "Thought: I must use the governed tool.\n"
                f"Action: {self._tool_name}\n"
                "Action Input: {}"
            )
        return (
            "Thought: I now can give a great answer\n"
            f"Final Answer: {self._final_answer}"
        )

    def supports_function_calling(self) -> bool:
        return False

    def supports_stop_words(self) -> bool:
        return False

    def get_context_window_size(self) -> int:
        return 8192


class GovernedTool(BaseTool):
    name: str = "governed_reader"
    description: str = "Execute one kernel-guarded unit of governed work."

    def _run(self) -> str:
        return self._guarded()  # type: ignore[attr-defined]


def _governed_tool(name: str, guarded: Any) -> GovernedTool:
    tool = GovernedTool()
    tool.name = name
    # The guarded callable stays outside the pydantic field model.
    object.__setattr__(tool, "_guarded", guarded)
    return tool


def _agent(role: str, llm: DeterministicLLM) -> Agent:
    return Agent(
        role=role,
        goal="Demonstrate governed deterministic offline behavior.",
        backstory="Deterministic local fixture agent.",
        allow_delegation=False,
        verbose=False,
        llm=llm,
    )


# (1)(2)(12)(13) identity mapping, allowed capability through a real
# Crew.kickoff() lifecycle, evidence emission, digest binding — with network
# and process primitives forbidden for the whole flow.
def test_native_crew_kickoff_allowed_capability_and_evidence(
    controls: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("native crewai flow attempted an external operation")

    # CrewAI's event bus creates an asyncio loop whose self-pipe is a
    # loopback socketpair; loopback stays permitted while name resolution,
    # external connects, and process primitives are forbidden.
    real_connect = socket.socket.connect

    def loopback_only_connect(sock: socket.socket, address: Any) -> Any:
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(sock, address)
        raise AssertionError(
            "native crewai flow attempted an external connection: "
            f"{address!r}"
        )

    monkeypatch.setattr(socket.socket, "connect", loopback_only_connect)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)

    kernel = _kernel(controls)
    adapter = CrewAIGovernanceAdapter(kernel)
    llm = DeterministicLLM("governed_reader", "governed research complete")
    agent = _agent("researcher", llm)

    # (1) the runtime CrewAI agent maps to the declared Nornyx identity
    assert adapter.resolve_identity(agent) == "identity.researcher.local"

    guarded = adapter.guarded_task(
        agent,
        "read_governed_context",
        lambda: "sanitized governed context",
        mission_id="GOAL-001",
    )
    task = Task(
        description="Read the governed context with the governed tool.",
        expected_output="A short governed answer.",
        agent=agent,
        tools=[_governed_tool("governed_reader", guarded)],
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
    result = crew.kickoff()

    # (2) the declared capability was allowed inside the native lifecycle
    assert "governed research complete" in str(result)
    assert llm._call_count >= 2, "the native executor must drive the LLM"
    events = kernel.events_payload()["events"]
    assert [event["event_type"] for event in events] == [
        "capability_requested",
        "capability_allowed",
        "tool_invoked",
    ]
    # (13) every event binds to the exact contract + lock digests
    for event in events:
        assert event["contract_digest"] == kernel.contract_digest
        assert event["network_lock_digest"] == kernel.lock_digest
    # (12) the emitted evidence validates against the same contract + lock
    report = validate_runtime_events(
        controls["document"],
        COMPOSITION,
        kernel.lock_payload,
        kernel.events_payload(),
    )
    assert report["status"] == "pass"


# (3) an undeclared capability is denied fail-closed for a real CrewAI agent
def test_native_agent_undeclared_capability_denied(controls: dict[str, Any]) -> None:
    kernel = _kernel(controls)
    adapter = CrewAIGovernanceAdapter(kernel)
    agent = _agent("researcher", DeterministicLLM(None, "unused"))
    with pytest.raises(GovernanceViolation) as excinfo:
        adapter.guarded_task(
            agent,
            "undeclared_capability",
            lambda: "never",
            mission_id="GOAL-001",
        )()
    assert excinfo.value.code == "AN_ADAPTER_CAPABILITY_UNKNOWN"
    types = [event["event_type"] for event in kernel.events_payload()["events"]]
    assert types == ["policy_violation"]


# (4) a declared delegation is accepted and the delegated execution rides a
# real Crew.kickoff() carrying the delegation reference in evidence
def test_native_delegated_crew_execution(controls: dict[str, Any]) -> None:
    kernel = _kernel(controls)
    adapter = CrewAIGovernanceAdapter(kernel)
    kernel.request_delegation("delegation.research", mission_id="GOAL-001")

    llm = DeterministicLLM("delegated_proposer", "delegated proposal recorded")
    reviewer = _agent("reviewer", llm)
    assert adapter.resolve_identity(reviewer) == "identity.reviewer.local"

    guarded = adapter.guarded_task(
        reviewer,
        "propose_research_finding",
        lambda: "bounded delegated finding",
        mission_id="GOAL-001",
    )
    task = Task(
        description="Propose the delegated finding with the governed tool.",
        expected_output="A delegated proposal.",
        agent=reviewer,
        tools=[_governed_tool("delegated_proposer", guarded)],
    )
    crew = Crew(agents=[reviewer], tasks=[task], process=Process.sequential)
    result = crew.kickoff()
    assert "delegated proposal recorded" in str(result)

    events = kernel.events_payload()["events"]
    assert [event["event_type"] for event in events] == [
        "delegation_requested",
        "delegation_accepted",
        "capability_requested",
        "capability_allowed",
        "tool_invoked",
    ]
    assert events[3]["delegation_ref"] == "delegation.research"
    assert events[4]["delegation_ref"] == "delegation.research"
    report = validate_runtime_events(
        controls["document"],
        COMPOSITION,
        kernel.lock_payload,
        kernel.events_payload(),
    )
    assert report["status"] == "pass"


# (5) capability escalation without a declared delegation is rejected
def test_native_capability_escalation_rejected(controls: dict[str, Any]) -> None:
    stripped = _document()
    stripped["agentic_network"]["delegations"] = []
    kernel = GovernanceKernel(
        stripped,
        COMPOSITION,
        build_agentic_network_lock(stripped, COMPOSITION),
        framework="crewai",
    )
    adapter = CrewAIGovernanceAdapter(kernel)
    reviewer = _agent("reviewer", DeterministicLLM(None, "unused"))
    with pytest.raises(GovernanceViolation) as excinfo:
        adapter.guarded_task(
            reviewer,
            "propose_research_finding",
            lambda: "escalated",
            mission_id="GOAL-001",
        )()
    assert excinfo.value.code == "AN_ADAPTER_CAPABILITY_DENIED"
    types = [event["event_type"] for event in kernel.events_payload()["events"]]
    assert types == ["capability_requested", "capability_denied"]


# (6)(7) a declared handoff succeeds; a handoff transfers responsibility,
# never authority
def test_native_handoff_success_and_no_authority_grant(
    controls: dict[str, Any],
) -> None:
    kernel = _kernel(controls)
    kernel.request_handoff("handoff.review", mission_id="GOAL-001")
    kernel.complete_handoff("handoff.review", mission_id="GOAL-001")
    types = [event["event_type"] for event in kernel.events_payload()["events"]]
    assert types == ["handoff_initiated", "handoff_completed"]

    # (7a) the completed handoff grants no capability: the reviewer still
    # cannot use an undelegated capability afterward
    stripped = _document()
    stripped["agentic_network"]["delegations"] = []
    bare = GovernanceKernel(
        stripped,
        COMPOSITION,
        build_agentic_network_lock(stripped, COMPOSITION),
        framework="crewai",
    )
    bare.request_handoff("handoff.review", mission_id="GOAL-001")
    bare.complete_handoff("handoff.review", mission_id="GOAL-001")
    with pytest.raises(GovernanceViolation) as excinfo:
        bare.check_capability(
            "identity.reviewer.local",
            "propose_research_finding",
            mission_id="GOAL-001",
        )
    assert excinfo.value.code == "AN_ADAPTER_CAPABILITY_DENIED"

    # (7b) a handoff whose target lacks a required capability is refused
    unqualified = _document()
    unqualified["agentic_network"]["handoffs"][0]["required_capability_refs"] = [
        "propose_research_finding"
    ]
    unqualified["agentic_network"]["delegations"] = []
    refused = GovernanceKernel(
        unqualified,
        COMPOSITION,
        build_agentic_network_lock(unqualified, COMPOSITION),
        framework="crewai",
    )
    with pytest.raises(GovernanceViolation) as excinfo:
        refused.request_handoff("handoff.review", mission_id="GOAL-001")
    assert excinfo.value.code == "AN_ADAPTER_HANDOFF_AUTHORITY"


# (8) human approval is required where declared (external trust-zone
# crossing) and a valid supplied human approval record is accepted
def test_native_human_approval_required_and_accepted(
    controls: dict[str, Any],
) -> None:
    kernel = _kernel(controls)
    with pytest.raises(GovernanceViolation) as excinfo:
        kernel.record_zone_crossing(
            "identity.researcher.local",
            "zone.local_governed",
            "zone.external_contract",
            mission_id="GOAL-001",
        )
    assert excinfo.value.code == "AN_ADAPTER_CROSSING_APPROVAL_REQUIRED"

    kernel.require_human_approval(
        {
            "actor_type": "human",
            "role": "network_governance_owner",
            "granted": True,
        },
        mission_id="GOAL-001",
        actor_ref="identity.researcher.local",
    )
    kernel.record_zone_crossing(
        "identity.researcher.local",
        "zone.local_governed",
        "zone.external_contract",
        mission_id="GOAL-001",
        approval_ref="agentic_network_authority",
    )
    types = [event["event_type"] for event in kernel.events_payload()["events"]]
    assert types == [
        "policy_violation",
        "approval_requested",
        "approval_granted",
        "trust_zone_crossed",
    ]


# (9) AI-generated approval is rejected and never becomes an approval outcome
def test_native_ai_generated_approval_rejected(controls: dict[str, Any]) -> None:
    kernel = _kernel(controls)
    for actor_type in ("model", "ai_tool", "autonomous_agent", "crewai_agent"):
        with pytest.raises(GovernanceViolation) as excinfo:
            kernel.require_human_approval(
                {
                    "actor_type": actor_type,
                    "role": "network_governance_owner",
                    "granted": True,
                },
                mission_id="GOAL-001",
                actor_ref="identity.researcher.local",
            )
        assert excinfo.value.code == "AN_ADAPTER_APPROVAL_NON_HUMAN"
    granted = [
        event
        for event in kernel.events_payload()["events"]
        if event["event_type"] == "approval_granted"
    ]
    assert granted == []


# (10) trust-zone restriction: an undeclared transition is denied
def test_native_trust_zone_restriction_enforced(controls: dict[str, Any]) -> None:
    kernel = _kernel(controls)
    with pytest.raises(GovernanceViolation) as excinfo:
        kernel.record_zone_crossing(
            "identity.researcher.local",
            "zone.external_contract",
            "zone.local_governed",
            mission_id="GOAL-001",
        )
    assert excinfo.value.code == "AN_ADAPTER_ZONE_CROSSING_DENIED"


# (11) sensitive sharing is rejected for every sensitive category
def test_native_sensitive_sharing_rejected(controls: dict[str, Any]) -> None:
    kernel = _kernel(controls)
    for category in ("secrets", "credentials", "tokens", "private_memory"):
        with pytest.raises(GovernanceViolation) as excinfo:
            kernel.record_data_shared(
                "identity.researcher.local",
                "identity.reviewer.local",
                [category],
                mission_id="GOAL-001",
                source_zone="zone.local_governed",
                target_zone="zone.local_governed",
            )
        assert excinfo.value.code == "AN_ADAPTER_SENSITIVE_SHARING"


# (14) stale generated controls fail closed before any crew can run: a
# valid contract paired with a lock generated from different governed
# content is refused at load, and mutated contract content is refused by
# the (earlier) revision-bound contract validation layer.
def test_native_stale_controls_fail_closed(
    controls: dict[str, Any], tmp_path: Path
) -> None:
    root = tmp_path / "stale"
    shutil.copytree(controls["root"], root)
    base_document = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    write_agentic_network_lock(
        build_agentic_network_lock(base_document, COMPOSITION),
        root / "nornyx.agentic_network.lock",
    )
    with pytest.raises(GovernanceViolation) as excinfo:
        GovernanceKernel.from_local_controls(
            root / "contract.nyx",
            root / "nornyx.agentic_network.lock",
            framework="crewai",
            as_of=AS_OF,
        )
    assert excinfo.value.code == "AN_ADAPTER_LOCK_STALE"

    tampered = tmp_path / "tampered"
    shutil.copytree(controls["root"], tampered)
    contract = tampered / "contract.nyx"
    document = yaml.safe_load(contract.read_text(encoding="utf-8"))
    document["capabilities"][0]["description"] = "tampered after locking"
    contract.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    with pytest.raises(GovernanceViolation) as excinfo:
        GovernanceKernel.from_local_controls(
            contract,
            tampered / "nornyx.agentic_network.lock",
            framework="crewai",
            as_of=AS_OF,
        )
    assert excinfo.value.code == "AN_ADAPTER_CONTRACT_INVALID"


# (15) a missing governance hook fails closed
def test_native_missing_hook_fails_closed() -> None:
    with pytest.raises(GovernanceViolation) as excinfo:
        CrewAIGovernanceAdapter(None)
    assert excinfo.value.code == "AN_ADAPTER_HOOK_MISSING"
