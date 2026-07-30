"""ADR-0039 M2-B: CrewAI adapter behavior against real crewai==1.15.4 objects.

Mirrors the root repository's own ``tests/test_agentic_crewai_native.py``
pattern (deterministic offline LLM, real ``Agent``/``Task``/``Crew`` objects,
socket/subprocess forbidden) but exercises this package's own
``crewai_adapter`` module built on the core SPI's ``Authorizer``/
``EvidenceRecorder``/``enforce()`` rather than the legacy reference kernel.

Skips (never errors) when crewai is not installed, so the default
``adapter-foundation`` CI matrix (no framework extras) stays green; a
dedicated CI job installs the ``crewai`` extra and asserts these tests ran
without skips.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import os

# Telemetry must be off before the first `crewai` import in this process.
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

crewai = pytest.importorskip("crewai")

# Imports that must follow the telemetry env setup / importorskip above; the
# E402 exception here matches the repository's established native-CrewAI test
# convention (see tests/test_agentic_crewai_native.py at the monorepo root).
import nornyx.agentic as A  # noqa: E402
from crewai import Agent, BaseLLM, Crew, Process, Task  # noqa: E402
from nornyx.agentic import (  # noqa: E402
    Authorizer,
    EvaluationContext,
    EvidenceRecorder,
    IdentityResolutionCode,
    IdentityResolutionError,
)
from nornyx.agentic_artifacts import build_agentic_network_lock  # noqa: E402
from nornyx.governance import GovernanceRegistry  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from nornyx_agentic_adapters import (  # noqa: E402
    AdapterConfigurationError,
    AdapterDenied,
    SurfaceBinding,
)
from nornyx_agentic_adapters.coverage import SurfaceStatus  # noqa: E402
from nornyx_agentic_adapters.crewai_adapter import (  # noqa: E402
    COVERAGE_INVENTORY,
    FRAMEWORK,
    METADATA,
    agent_identity_key,
    make_governed_tool,
    resolve_identity,
)
from nornyx_agentic_adapters.crewai_adapter import (  # noqa: E402
    _check_crewai_version,
    _installed_crewai_version,
    _REQUIRED_CREWAI_VERSION,
)

# This test file lives at adapters/nornyx-agentic-adapters/tests/; the shared
# example contract fixture lives at the monorepo root. Read-only reuse of an
# existing, already-validated fixture for integration testing only — the
# adapter package's own distributed wheel never depends on this file.
ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "examples" / "agentic_network.nyx"
AS_OF = "2026-07-17T10:00:00Z"
REVISION = "git:0123456789abcdef0123456789abcdef01234567"
MISSION_ID = "GOAL-001"


def _document() -> dict[str, Any]:
    document = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    for identity, key in (
        (document["agent_identities"][0], "researcher"),
        (document["agent_identities"][1], "reviewer"),
    ):
        identity["framework_bindings"].append({"framework": "crewai", "agent_key": key})
    return document


def _authorizer(document: dict[str, Any]) -> Authorizer:
    composition = A.compose_document_governance(document, registry=GovernanceRegistry.builtins())
    lock = build_agentic_network_lock(document, composition)
    return Authorizer(document, composition, lock)


def _delegated_document() -> dict[str, Any]:
    """The example contract plus an active delegation of a capability.

    ``identity.reviewer.local`` does NOT hold ``propose_research_finding``
    directly; here it receives it by bounded delegation, which is the only way
    the ALLOW decision's basis carries ``kind="delegation"``.
    """
    document = _document()
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
    return document


@pytest.fixture()
def authorizer() -> Authorizer:
    return _authorizer(_document())


@pytest.fixture()
def delegating_authorizer() -> Authorizer:
    return _authorizer(_delegated_document())


def _context() -> EvaluationContext:
    return EvaluationContext(decision_at=AS_OF, observed_subject_revision=REVISION)


def _recorder(authorizer: Authorizer) -> EvidenceRecorder:
    return EvidenceRecorder(
        authorizer, _context(), producer_id="test-crewai-adapter", producer_type="synthetic_harness"
    )


class DeterministicLLM(BaseLLM):
    """Scripted offline LLM driving CrewAI's native ReAct executor.

    The first call of a task emits an ``Action:`` step for the configured
    governed tool; every later call emits a ``Final Answer:``. Never touches
    a network, an API key, or an external model.
    """

    def __init__(self, tool_name: str | None, final_answer: str, action_input: str = "{}"):
        super().__init__(model="nornyx-deterministic-offline")
        self._tool_name = tool_name
        self._final_answer = final_answer
        self._action_input = action_input
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
                f"Action Input: {self._action_input}"
            )
        return f"Thought: I now can give a great answer\nFinal Answer: {self._final_answer}"

    def supports_function_calling(self) -> bool:
        return False

    def supports_stop_words(self) -> bool:
        return False

    def get_context_window_size(self) -> int:
        return 8192


def _agent(role: str, llm: DeterministicLLM) -> Agent:
    return Agent(
        role=role,
        goal="Demonstrate governed deterministic offline behavior.",
        backstory="Deterministic local fixture agent.",
        allow_delegation=False,
        verbose=False,
        llm=llm,
    )


# --------------------------------------------------------------- metadata + coverage
def test_metadata_declares_framework_and_pinned_version() -> None:
    assert METADATA.framework_name == FRAMEWORK == "crewai"
    assert METADATA.framework_version_range == "==1.15.4"
    assert METADATA.nornyx_version_range == ">=1.10,<2"


def test_coverage_inventory_declares_only_tool_invocation_wrapped() -> None:
    wrapped = {entry.surface for entry in COVERAGE_INVENTORY.wrapped()}
    assert wrapped == {"tool_invocation"}
    unsupported = {
        entry.surface
        for entry in COVERAGE_INVENTORY.entries
        if entry.status is SurfaceStatus.UNSUPPORTED
    }
    assert unsupported == {
        "async_tool_invocation",
        "agent_invocation",
        "task_invocation",
        "delegation",
        "handoff",
    }
    # Every unsupported entry names a reason; the inventory never hides a gap.
    for entry in COVERAGE_INVENTORY.entries:
        if entry.status is SurfaceStatus.UNSUPPORTED:
            assert entry.reason.strip()


# --------------------------------------------------------------- identity resolution
def test_agent_identity_key_extracts_role() -> None:
    agent = _agent("researcher", DeterministicLLM(None, "unused"))
    assert agent_identity_key(agent) == "researcher"


def test_agent_identity_key_fails_closed_on_blank_role() -> None:
    class _NoRole:
        role = "   "

    with pytest.raises(AdapterConfigurationError):
        agent_identity_key(_NoRole())


def test_resolve_identity_maps_a_declared_crewai_role(authorizer: Authorizer) -> None:
    agent = _agent("researcher", DeterministicLLM(None, "unused"))
    assert resolve_identity(authorizer, agent) == "identity.researcher.local"


def test_resolve_identity_fails_closed_on_unknown_role(authorizer: Authorizer) -> None:
    agent = _agent("unmapped-role", DeterministicLLM(None, "unused"))
    with pytest.raises(IdentityResolutionError) as excinfo:
        resolve_identity(authorizer, agent)
    assert excinfo.value.code is IdentityResolutionCode.IDENTITY_UNKNOWN


# --------------------------------------------------------------- direct tool enforcement
def test_governed_tool_allow_runs_action_exactly_once_and_records_tool_invoked(
    authorizer: Authorizer,
) -> None:
    recorder = _recorder(authorizer)
    calls: list[Any] = []

    def action() -> str:
        calls.append(1)
        return "sanitized governed context"

    binding = SurfaceBinding(
        surface="tool:governed_reader",
        identity_ref="identity.researcher.local",
        capability_ref="read_governed_context",
    )
    tool = make_governed_tool(
        name="governed_reader",
        description="Read governed context.",
        binding=binding,
        authorizer=authorizer,
        context=_context(),
        recorder=recorder,
        mission_id=MISSION_ID,
        action=action,
    )

    result = tool.run()

    assert result == "sanitized governed context"
    assert len(calls) == 1
    events = recorder.stream()["events"]
    assert [event["event_type"] for event in events] == [
        "capability_requested",
        "capability_allowed",
        "tool_invoked",
    ]
    report = recorder.validate()
    assert report["status"] == "pass"


def test_governed_tool_deny_never_runs_action_and_raises_adapter_denied(
    authorizer: Authorizer,
) -> None:
    recorder = _recorder(authorizer)
    calls: list[Any] = []

    def action() -> str:
        calls.append(1)
        return "should never happen"

    # The reviewer identity does not hold propose_research_finding.
    binding = SurfaceBinding(
        surface="tool:proposer",
        identity_ref="identity.reviewer.local",
        capability_ref="propose_research_finding",
    )
    tool = make_governed_tool(
        name="proposer",
        description="Propose a research finding.",
        binding=binding,
        authorizer=authorizer,
        context=_context(),
        recorder=recorder,
        mission_id=MISSION_ID,
        action=action,
    )

    with pytest.raises(AdapterDenied) as excinfo:
        tool.run()

    assert calls == []  # the wrapped side effect never ran
    assert not excinfo.value.decision.allowed
    events = recorder.stream()["events"]
    assert [event["event_type"] for event in events] == [
        "capability_requested",
        "capability_denied",
    ]


def test_delegated_capability_observation_carries_the_authorizing_delegation(
    delegating_authorizer: Authorizer,
) -> None:
    """A capability held only by delegation must produce a validating stream.

    The ALLOW is correct and ``capability_allowed`` already carries the
    delegation. Without the same reference on ``tool_invoked``, the validator's
    possession check fails closed and reports a capability the actor does not
    hold — so delegation and validatable evidence were mutually exclusive.
    """
    recorder = _recorder(delegating_authorizer)
    calls: list[Any] = []

    def action() -> str:
        calls.append(1)
        return "proposed finding"

    binding = SurfaceBinding(
        surface="tool:proposer",
        identity_ref="identity.reviewer.local",
        capability_ref="propose_research_finding",
    )
    tool = make_governed_tool(
        name="proposer",
        description="Propose a research finding.",
        binding=binding,
        authorizer=delegating_authorizer,
        context=_context(),
        recorder=recorder,
        mission_id=MISSION_ID,
        action=action,
    )

    assert tool.run() == "proposed finding"
    assert calls == [1]  # exactly once

    events = recorder.stream()["events"]
    assert [event["event_type"] for event in events] == [
        "capability_requested",
        "capability_allowed",
        "tool_invoked",
    ]
    allowed = events[1]
    invoked = events[2]
    assert allowed["delegation_ref"] == "delegation.research"
    assert invoked["delegation_ref"] == "delegation.research"

    report = recorder.validate()
    assert report["status"] == "pass", report["diagnostics"]
    assert report["diagnostics"] == []


def test_directly_held_capability_observation_omits_delegation_ref(
    authorizer: Authorizer,
) -> None:
    """A capability held by membership records no delegation — the field is absent."""
    recorder = _recorder(authorizer)
    binding = SurfaceBinding(
        surface="tool:governed_reader",
        identity_ref="identity.researcher.local",
        capability_ref="read_governed_context",
    )
    tool = make_governed_tool(
        name="governed_reader",
        description="Read governed context.",
        binding=binding,
        authorizer=authorizer,
        context=_context(),
        recorder=recorder,
        mission_id=MISSION_ID,
        action=lambda: "ok",
    )
    assert tool.run() == "ok"
    invoked = recorder.stream()["events"][-1]
    assert invoked["event_type"] == "tool_invoked"
    assert "delegation_ref" not in invoked
    assert recorder.validate()["status"] == "pass"


def test_delegation_ref_is_not_taken_from_tool_arguments(
    delegating_authorizer: Authorizer,
) -> None:
    """Caller-supplied arguments must never determine the recorded delegation."""

    class Injected(BaseModel):
        delegation_ref: str = "delegation.forged"

    recorder = _recorder(delegating_authorizer)
    tool = make_governed_tool(
        name="proposer",
        description="Propose a research finding.",
        binding=SurfaceBinding(
            surface="tool:proposer",
            identity_ref="identity.reviewer.local",
            capability_ref="propose_research_finding",
        ),
        authorizer=delegating_authorizer,
        context=_context(),
        recorder=recorder,
        mission_id=MISSION_ID,
        action=lambda **kwargs: "proposed finding",
        args_schema=Injected,
    )

    assert tool._run(delegation_ref="delegation.forged") == "proposed finding"
    invoked = recorder.stream()["events"][-1]
    assert invoked["delegation_ref"] == "delegation.research"


def test_expired_delegation_denies_and_records_no_tool_invoked() -> None:
    """A delegation outside its validity window grants nothing, and observes nothing.

    The decision hook only ever reads an authorizing delegation off an ALLOW, so
    a lapsed delegation cannot produce a ``tool_invoked`` observation at all.
    """
    document = _delegated_document()
    document["agentic_network"]["delegations"][0]["expires_at"] = "2026-07-17T09:00:00Z"
    authorizer = _authorizer(document)
    recorder = _recorder(authorizer)
    calls: list[Any] = []

    tool = make_governed_tool(
        name="proposer",
        description="Propose a research finding.",
        binding=SurfaceBinding(
            surface="tool:proposer",
            identity_ref="identity.reviewer.local",
            capability_ref="propose_research_finding",
        ),
        authorizer=authorizer,
        context=_context(),
        recorder=recorder,
        mission_id=MISSION_ID,
        action=lambda: calls.append(1),
    )
    with pytest.raises(AdapterDenied) as excinfo:
        tool.run()
    assert calls == []
    assert excinfo.value.decision.code.value == "CAPABILITY_DENIED"
    events = recorder.stream()["events"]
    assert [e["event_type"] for e in events] == [
        "capability_requested",
        "capability_denied",
    ]
    assert all("delegation_ref" not in e for e in events)


def test_make_governed_tool_fails_closed_on_blank_binding_field(authorizer: Authorizer) -> None:
    recorder = _recorder(authorizer)
    binding = SurfaceBinding(surface="tool:x", identity_ref="", capability_ref="read_governed_context")
    with pytest.raises(AdapterConfigurationError):
        make_governed_tool(
            name="x",
            description="x",
            binding=binding,
            authorizer=authorizer,
            context=_context(),
            recorder=recorder,
            mission_id=MISSION_ID,
            action=lambda: "never",
        )


# --------------------------------------------------------------- cooperative-boundary bypass
def test_bypass_calling_the_raw_action_directly_skips_enforcement_entirely(
    authorizer: Authorizer,
) -> None:
    """ADR-0040 cooperative Tier 2: bypassing the adapter bypasses enforcement.

    Nothing in this package prevents an integrator from invoking the
    underlying work callable directly, without ever constructing a governed
    tool or evaluating a Decision. This test makes that boundary explicit
    rather than implicit.
    """
    calls: list[Any] = []

    def action() -> str:
        calls.append(1)
        return "ran with no authorization check whatsoever"

    # The reviewer identity does not hold this capability — if this ran
    # through make_governed_tool it would be denied. Called directly, it just
    # runs, because nothing enforces anything outside the governed wrapper.
    result = action()
    assert result == "ran with no authorization check whatsoever"
    assert calls == [1]


# --------------------------------------------------------------- full Crew.kickoff() lifecycle
def test_native_crew_kickoff_allowed_capability_end_to_end(
    authorizer: Authorizer, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("native crewai flow attempted an external operation")

    real_connect = socket.socket.connect

    def loopback_only_connect(sock: socket.socket, address: Any) -> Any:
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(sock, address)
        raise AssertionError(f"native crewai flow attempted an external connection: {address!r}")

    monkeypatch.setattr(socket.socket, "connect", loopback_only_connect)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)

    recorder = _recorder(authorizer)
    llm = DeterministicLLM("governed_reader", "governed research complete")
    agent = _agent("researcher", llm)
    assert resolve_identity(authorizer, agent) == "identity.researcher.local"

    binding = SurfaceBinding(
        surface="tool:governed_reader",
        identity_ref="identity.researcher.local",
        capability_ref="read_governed_context",
    )
    tool = make_governed_tool(
        name="governed_reader",
        description="Read governed context.",
        binding=binding,
        authorizer=authorizer,
        context=_context(),
        recorder=recorder,
        mission_id=MISSION_ID,
        action=lambda: "sanitized governed context",
    )
    task = Task(
        description="Read the governed context with the governed tool.",
        expected_output="A short governed answer.",
        agent=agent,
        tools=[tool],
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
    result = crew.kickoff()

    assert "governed research complete" in str(result)
    assert llm._call_count >= 2, "the native executor must drive the LLM"
    events = recorder.stream()["events"]
    assert [event["event_type"] for event in events] == [
        "capability_requested",
        "capability_allowed",
        "tool_invoked",
    ]
    report = recorder.validate()
    assert report["status"] == "pass"


def test_native_crew_kickoff_denied_capability_side_effect_never_runs(
    authorizer: Authorizer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same native lifecycle, but the governed tool wraps a capability the
    agent does not hold. CrewAI's executor observes a tool error, but the
    wrapped side effect must never have run."""

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("native crewai flow attempted an external operation")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)

    recorder = _recorder(authorizer)
    llm = DeterministicLLM("proposer", "should never be reached")
    # reviewer holds only read_governed_context, not propose_research_finding.
    agent = _agent("reviewer", llm)

    calls: list[Any] = []

    def action() -> str:
        calls.append(1)
        return "should never happen"

    binding = SurfaceBinding(
        surface="tool:proposer",
        identity_ref="identity.reviewer.local",
        capability_ref="propose_research_finding",
    )
    tool = make_governed_tool(
        name="proposer",
        description="Propose a research finding.",
        binding=binding,
        authorizer=authorizer,
        context=_context(),
        recorder=recorder,
        mission_id=MISSION_ID,
        action=action,
    )
    task = Task(
        description="Propose a finding with the governed tool.",
        expected_output="A proposal.",
        agent=agent,
        tools=[tool],
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
    crew.kickoff()

    assert calls == []  # the wrapped side effect never ran, regardless of how CrewAI reports the error
    # CrewAI's own executor may retry a failed tool call internally (an
    # implementation detail this adapter does not control), so assert the
    # fail-closed invariant rather than one exact retry count: every recorded
    # event is a decision intent, denial happened at least once, and
    # tool_invoked — recorded only after a successful action() — never appears.
    events = recorder.stream()["events"]
    event_types = [event["event_type"] for event in events]
    assert event_types, "expected at least one recorded decision-intent event"
    assert set(event_types) <= {"capability_requested", "capability_denied"}
    assert "capability_denied" in event_types
    assert "tool_invoked" not in event_types


# --------------------------------------------------------------- F2: async tool invocation unsupported
def test_coverage_inventory_declares_async_tool_invocation_unsupported() -> None:
    entry = next(
        e for e in COVERAGE_INVENTORY.entries if e.surface == "async_tool_invocation"
    )
    assert entry.status is SurfaceStatus.UNSUPPORTED
    # The reason states the concrete mechanism: no _arun override; async fails closed.
    assert "_arun" in entry.reason
    assert "NotImplementedError" in entry.reason
    # Async is never presented as a wrapped/governed surface.
    wrapped = {e.surface for e in COVERAGE_INVENTORY.wrapped()}
    assert "async_tool_invocation" not in wrapped
    assert wrapped == {"tool_invocation"}


def test_async_tool_invocation_reason_is_deterministic() -> None:
    reasons = [
        e.reason
        for e in COVERAGE_INVENTORY.entries
        if e.surface == "async_tool_invocation"
    ]
    # Exactly one async entry, with a stable non-empty reason; the deterministic
    # as_dict() serialization exposes the same reason string.
    assert len(reasons) == 1
    reason = reasons[0]
    assert reason.strip()
    serialized = {
        s["surface"]: s["reason"] for s in COVERAGE_INVENTORY.as_dict()["surfaces"]
    }
    assert serialized["async_tool_invocation"] == reason


def test_async_arun_fails_closed_and_records_nothing(authorizer: Authorizer) -> None:
    recorder = _recorder(authorizer)
    calls: list[Any] = []
    binding = SurfaceBinding(
        surface="tool:governed_reader",
        identity_ref="identity.researcher.local",
        capability_ref="read_governed_context",
    )
    tool = make_governed_tool(
        name="governed_reader",
        description="Read governed context.",
        binding=binding,
        authorizer=authorizer,
        context=_context(),
        recorder=recorder,
        mission_id=MISSION_ID,
        action=lambda: calls.append(1),
    )
    # The inherited BaseTool._arun raises; the wrapped action never runs and the
    # governed _run (hence enforce/record) is never reached.
    with pytest.raises(NotImplementedError):
        asyncio.run(tool.arun())
    assert calls == []  # the wrapped side effect never ran
    event_types = [e["event_type"] for e in recorder.stream()["events"]]
    assert "tool_invoked" not in event_types
    assert event_types == []  # no decision recorded either


# --------------------------------------------------------------- F3: structured args_schema
class _TopicInput(BaseModel):
    topic: str


class _MultiInput(BaseModel):
    topic: str
    limit: int = Field(default=5, description="max results")


def _researcher_read_binding() -> SurfaceBinding:
    return SurfaceBinding(
        surface="tool:reader",
        identity_ref="identity.researcher.local",
        capability_ref="read_governed_context",
    )


def test_structured_scalar_arg_exposed_and_allowed_runs_once(authorizer: Authorizer) -> None:
    recorder = _recorder(authorizer)
    seen: list[Any] = []

    def action(topic: str) -> str:
        seen.append(topic)
        return f"read:{topic}"

    tool = make_governed_tool(
        name="reader",
        description="Read a topic.",
        binding=_researcher_read_binding(),
        authorizer=authorizer,
        context=_context(),
        recorder=recorder,
        mission_id=MISSION_ID,
        action=action,
        args_schema=_TopicInput,
    )
    # CrewAI sees the caller-supplied schema (not an empty auto-generated one).
    assert "topic" in tool.args_schema.model_fields
    result = tool.run(topic="alpha")
    assert result == "read:alpha"
    assert seen == ["alpha"]
    event_types = [e["event_type"] for e in recorder.stream()["events"]]
    assert event_types == ["capability_requested", "capability_allowed", "tool_invoked"]


def test_structured_multiple_required_and_optional_fields(authorizer: Authorizer) -> None:
    recorder = _recorder(authorizer)
    got: dict[str, Any] = {}

    def action(topic: str, limit: int = 5) -> str:
        got["topic"] = topic
        got["limit"] = limit
        return "ok"

    tool = make_governed_tool(
        name="reader",
        description="Read a topic with a limit.",
        binding=_researcher_read_binding(),
        authorizer=authorizer,
        context=_context(),
        recorder=recorder,
        mission_id=MISSION_ID,
        action=action,
        args_schema=_MultiInput,
    )
    assert tool.run(topic="a") == "ok"  # optional defaults via the schema
    assert got == {"topic": "a", "limit": 5}
    assert tool.run(topic="b", limit=9) == "ok"
    assert got == {"topic": "b", "limit": 9}


def test_structured_invalid_input_rejected_before_side_effect(authorizer: Authorizer) -> None:
    recorder = _recorder(authorizer)
    side: list[Any] = []

    def action(topic: str) -> str:
        side.append(topic)
        return "x"

    tool = make_governed_tool(
        name="reader",
        description="Read a topic.",
        binding=_researcher_read_binding(),
        authorizer=authorizer,
        context=_context(),
        recorder=recorder,
        mission_id=MISSION_ID,
        action=action,
        args_schema=_TopicInput,
    )
    # Missing the required 'topic' field: CrewAI rejects before _run/enforce.
    with pytest.raises(ValueError):
        tool.run(not_topic="x")
    assert side == []
    assert recorder.stream()["events"] == []


def test_structured_denied_executes_zero_times(authorizer: Authorizer) -> None:
    recorder = _recorder(authorizer)
    side: list[Any] = []

    def action(topic: str) -> str:
        side.append(topic)
        return "x"

    # reviewer does not hold propose_research_finding: DENY despite valid input.
    tool = make_governed_tool(
        name="proposer",
        description="Propose with a topic.",
        binding=SurfaceBinding(
            surface="tool:proposer",
            identity_ref="identity.reviewer.local",
            capability_ref="propose_research_finding",
        ),
        authorizer=authorizer,
        context=_context(),
        recorder=recorder,
        mission_id=MISSION_ID,
        action=action,
        args_schema=_TopicInput,
    )
    with pytest.raises(AdapterDenied):
        tool.run(topic="alpha")
    assert side == []
    event_types = [e["event_type"] for e in recorder.stream()["events"]]
    assert "tool_invoked" not in event_types


def test_make_governed_tool_rejects_non_model_args_schema(authorizer: Authorizer) -> None:
    recorder = _recorder(authorizer)

    def build(schema: Any) -> Any:
        return make_governed_tool(
            name="reader",
            description="d",
            binding=_researcher_read_binding(),
            authorizer=authorizer,
            context=_context(),
            recorder=recorder,
            mission_id=MISSION_ID,
            action=lambda: "ok",
            args_schema=schema,
        )

    with pytest.raises(AdapterConfigurationError):
        build(dict)  # a type, but not a pydantic BaseModel subclass
    with pytest.raises(AdapterConfigurationError):
        build(object())  # not even a type


def test_structured_schema_does_not_serialize_governance_state(authorizer: Authorizer) -> None:
    recorder = _recorder(authorizer)
    tool = make_governed_tool(
        name="reader",
        description="Read a topic.",
        binding=_researcher_read_binding(),
        authorizer=authorizer,
        context=_context(),
        recorder=recorder,
        mission_id=MISSION_ID,
        action=lambda topic: f"read:{topic}",
        args_schema=_TopicInput,
    )
    # The exposed schema carries tool inputs only — never authorizer/recorder/binding.
    assert set(tool.args_schema.model_fields) == {"topic"}
    dumped = tool.model_dump()
    assert not any(k.startswith("_nornyx") for k in dumped)


def test_native_crew_kickoff_structured_tool_allowed_end_to_end(
    authorizer: Authorizer, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("native crewai flow attempted an external operation")

    real_connect = socket.socket.connect

    def loopback_only_connect(sock: socket.socket, address: Any) -> Any:
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(sock, address)
        raise AssertionError(f"native crewai flow attempted an external connection: {address!r}")

    monkeypatch.setattr(socket.socket, "connect", loopback_only_connect)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)

    recorder = _recorder(authorizer)
    llm = DeterministicLLM("governed_reader", "structured research complete", action_input='{"topic": "alpha"}')
    agent = _agent("researcher", llm)
    seen: list[Any] = []

    def action(topic: str) -> str:
        seen.append(topic)
        return f"sanitized:{topic}"

    tool = make_governed_tool(
        name="governed_reader",
        description="Read governed context for a topic.",
        binding=SurfaceBinding(
            surface="tool:governed_reader",
            identity_ref="identity.researcher.local",
            capability_ref="read_governed_context",
        ),
        authorizer=authorizer,
        context=_context(),
        recorder=recorder,
        mission_id=MISSION_ID,
        action=action,
        args_schema=_TopicInput,
    )
    task = Task(
        description="Read the governed context for topic alpha with the governed tool.",
        expected_output="A short governed answer.",
        agent=agent,
        tools=[tool],
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
    result = crew.kickoff()

    assert "structured research complete" in str(result)
    assert seen == ["alpha"], "the governed action received the structured argument"
    event_types = [e["event_type"] for e in recorder.stream()["events"]]
    assert event_types == ["capability_requested", "capability_allowed", "tool_invoked"]
    report = recorder.validate()
    assert report["status"] == "pass"


# --------------------------------------------------------------- F4: CrewAI version enforcement
def test_installed_crewai_version_is_the_supported_exact_version() -> None:
    # Real environment: the [crewai] extra pins crewai==1.15.4.
    assert _REQUIRED_CREWAI_VERSION == "1.15.4"
    assert _installed_crewai_version() == _REQUIRED_CREWAI_VERSION
    assert crewai.__version__ == _REQUIRED_CREWAI_VERSION
    # The supported version passes the compatibility check without raising.
    _check_crewai_version(_REQUIRED_CREWAI_VERSION)


def test_check_crewai_version_rejects_unsupported_version() -> None:
    with pytest.raises(AdapterConfigurationError) as excinfo:
        _check_crewai_version("1.14.0")
    message = str(excinfo.value)
    assert "1.14.0" in message
    assert _REQUIRED_CREWAI_VERSION in message


def test_installed_crewai_version_fails_closed_on_missing_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError("crewai")

    monkeypatch.setattr(importlib.metadata, "version", _raise)
    with pytest.raises(AdapterConfigurationError):
        _installed_crewai_version()


def test_installed_crewai_version_fails_closed_on_malformed_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(importlib.metadata, "version", lambda _name: "   ")
    with pytest.raises(AdapterConfigurationError):
        _installed_crewai_version()
