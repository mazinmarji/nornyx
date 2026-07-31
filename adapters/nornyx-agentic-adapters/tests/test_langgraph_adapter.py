"""Native LangGraph 1.2.2 M2-C occurrence-semantics corpus."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import pytest
import yaml

pytest.importorskip("langgraph")

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import ExecutionInfo, Runtime
from langgraph.types import Command, RetryPolicy, interrupt

from nornyx.agentic import (
    SPI_VERSION,
    Authorizer,
    EvaluationContext,
    EvidenceRecorder,
    GovernanceRegistry,
    build_agentic_network_lock,
    compose_document_governance,
)
from nornyx_agentic_adapters import AdapterConfigurationError, AdapterDenied, SurfaceBinding
from nornyx_agentic_adapters._compat import SUPPORTED_SPI_MAJOR, check_spi_version
from nornyx_agentic_adapters.langgraph import (
    COVERAGE_INVENTORY,
    FRAMEWORK,
    METADATA,
    make_governed_node,
    resolve_identity,
)


ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture()
def governed_runtime() -> tuple[Authorizer, EvaluationContext, EvidenceRecorder]:
    document = yaml.safe_load(
        (ROOT / "examples" / "agentic_network.nyx").read_text(encoding="utf-8")
    )
    composition = compose_document_governance(
        document, registry=GovernanceRegistry.builtins()
    )
    authorizer = Authorizer(
        document, composition, build_agentic_network_lock(document, composition)
    )
    context = EvaluationContext(
        "2026-07-17T10:00:00Z", authorizer.subject_revision
    )
    recorder = EvidenceRecorder.for_occurrences(
        authorizer, context, producer_id="langgraph-tests"
    )
    return authorizer, context, recorder


def _node(governed_runtime, *, surface="node.read", action=lambda state: state):
    authorizer, context, recorder = governed_runtime
    return make_governed_node(
        binding=SurfaceBinding(
            surface,
            "identity.researcher.local",
            "read_governed_context",
        ),
        authorizer=authorizer,
        context=context,
        recorder=recorder,
        mission_id="GOAL-001",
        action=action,
    )


def _compile_single(node, *, retry_policy=None, checkpointer=None):
    builder = StateGraph(dict)
    builder.add_node("read", node, retry_policy=retry_policy)
    builder.add_edge(START, "read")
    builder.add_edge("read", END)
    return builder.compile(checkpointer=checkpointer)


def test_metadata_and_coverage_are_closed() -> None:
    assert FRAMEWORK == "langgraph"
    assert METADATA.adapter_version == "0.2.0"
    # docs/COMPATIBILITY.md declares adapter 0.2.x compatible with SPI *major* 1,
    # not with one exact minor: every additive SPI minor is compatible under
    # ADR-0039's minor-compatibility rule. Pinning an exact minor here would
    # contradict that matrix and fail on a core minor the adapter does support.
    assert METADATA.spi_version == SPI_VERSION
    assert int(METADATA.spi_version.partition(".")[0]) == SUPPORTED_SPI_MAJOR
    check_spi_version(METADATA.spi_version)
    assert METADATA.framework_version_range == "==1.2.2"
    assert METADATA.nornyx_version_range == ">=1.10,<2"
    assert [item.surface for item in COVERAGE_INVENTORY.wrapped()] == [
        "sync_node_invocation"
    ]


def test_node_requires_explicit_recorder(governed_runtime) -> None:
    authorizer, context, _recorder = governed_runtime
    legacy = EvidenceRecorder(authorizer, context, producer_id="legacy")
    with pytest.raises(AdapterConfigurationError, match="occurrence-aware"):
        make_governed_node(
            binding=SurfaceBinding(
                "node.read",
                "identity.researcher.local",
                "read_governed_context",
            ),
            authorizer=authorizer,
            context=context,
            recorder=legacy,
            mission_id="GOAL-001",
            action=lambda state: state,
        )


def test_missing_execution_info_fails_before_action(governed_runtime) -> None:
    called = []
    node = _node(governed_runtime, action=lambda state: called.append(state))
    with pytest.raises(AdapterConfigurationError, match="execution_info"):
        node({}, Runtime())
    assert called == []


def test_sync_node_success_uses_public_task_identity(governed_runtime) -> None:
    _authorizer, _context, recorder = governed_runtime
    node = _node(governed_runtime, action=lambda state: {"value": 1})
    runtime = Runtime(
        execution_info=ExecutionInfo(
            checkpoint_id="checkpoint-1",
            checkpoint_ns="",
            task_id="task-with-hyphens",
            node_attempt=1,
        )
    )
    assert node({}, runtime) == {"value": 1}
    assert {
        event["occurrence"]["occurrence_id"]
        for event in recorder.stream()["events"]
    } == {"task-with-hyphens"}
    assert recorder.validate()["status"] == "pass"


def test_policy_denial_never_calls_action(governed_runtime) -> None:
    authorizer, context, recorder = governed_runtime
    called = []
    node = make_governed_node(
        binding=SurfaceBinding(
            "node.denied",
            "identity.reviewer.local",
            "propose_research_finding",
        ),
        authorizer=authorizer,
        context=context,
        recorder=recorder,
        mission_id="GOAL-001",
        action=lambda state: called.append(state),
    )
    runtime = Runtime(
        execution_info=ExecutionInfo("checkpoint-1", "", "task-denied", node_attempt=1)
    )
    with pytest.raises(AdapterDenied):
        node({}, runtime)
    assert called == []
    assert recorder.validate()["status"] == "pass"


def test_native_retry_maps_to_one_occurrence_and_three_attempts(governed_runtime) -> None:
    _authorizer, _context, recorder = governed_runtime
    calls = 0

    def action(_state):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ValueError("retry")
        return {"value": calls}

    graph = _compile_single(
        _node(governed_runtime, action=action),
        retry_policy=RetryPolicy(
            max_attempts=3, retry_on=ValueError, initial_interval=0
        ),
    )
    assert graph.invoke({}) == {"value": 3}
    occurrences = [event["occurrence"] for event in recorder.stream()["events"]]
    assert len({item["occurrence_id"] for item in occurrences}) == 1
    assert {item["attempt"] for item in occurrences} == {1, 2, 3}
    assert recorder.validate()["status"] == "pass"


class LoopState(TypedDict):
    count: int


def test_native_loop_creates_distinct_occurrences(governed_runtime) -> None:
    _authorizer, _context, recorder = governed_runtime
    node = _node(
        governed_runtime,
        surface="node.loop",
        action=lambda state: {"count": state["count"] + 1},
    )
    builder = StateGraph(LoopState)
    builder.add_node("loop", node)
    builder.add_edge(START, "loop")
    builder.add_conditional_edges(
        "loop", lambda state: "loop" if state["count"] < 2 else END
    )
    assert builder.compile().invoke({"count": 0})["count"] == 2
    terminal = [
        event
        for event in recorder.stream()["events"]
        if event["event_type"] == "agent_invoked"
    ]
    assert len(terminal) == 2
    assert len({event["occurrence"]["occurrence_id"] for event in terminal}) == 2
    assert {event["occurrence"]["attempt"] for event in terminal} == {1}
    assert recorder.validate()["status"] == "pass"


class ParallelState(TypedDict, total=False):
    left: int
    right: int


def test_native_parallel_branches_have_distinct_occurrences(governed_runtime) -> None:
    _authorizer, _context, recorder = governed_runtime
    builder = StateGraph(ParallelState)
    builder.add_node(
        "left",
        _node(
            governed_runtime,
            surface="node.left",
            action=lambda _state: {"left": 1},
        ),
    )
    builder.add_node(
        "right",
        _node(
            governed_runtime,
            surface="node.right",
            action=lambda _state: {"right": 1},
        ),
    )
    builder.add_edge(START, "left")
    builder.add_edge(START, "right")
    builder.add_edge("left", END)
    builder.add_edge("right", END)
    assert builder.compile().invoke({}) == {"left": 1, "right": 1}
    terminal = [
        event
        for event in recorder.stream()["events"]
        if event["event_type"] == "agent_invoked"
    ]
    assert len({event["occurrence"]["occurrence_id"] for event in terminal}) == 2
    assert recorder.validate()["status"] == "pass"


def test_interrupt_resume_offsets_reset_node_attempt(governed_runtime) -> None:
    _authorizer, _context, recorder = governed_runtime

    def action(_state):
        return {"answer": interrupt("approve")}

    graph = _compile_single(
        _node(governed_runtime, action=action), checkpointer=InMemorySaver()
    )
    config = {"configurable": {"thread_id": "thread-1"}}
    interrupted = graph.invoke({}, config)
    assert interrupted["__interrupt__"]
    assert not any(
        event["event_type"] == "runtime_failed"
        for event in recorder.stream()["events"]
    )
    assert graph.invoke(Command(resume="yes"), config) == {"answer": "yes"}
    events = recorder.stream()["events"]
    occurrence_ids = {event["occurrence"]["occurrence_id"] for event in events}
    assert len(occurrence_ids) == 1
    assert {event["occurrence"]["attempt"] for event in events} == {1, 2}
    assert recorder.validate()["status"] == "pass"


def test_declared_langgraph_identity_resolution() -> None:
    document = yaml.safe_load(
        (
            ROOT
            / "examples"
            / "agentic_network_support"
            / "support_network.nyx"
        ).read_text(encoding="utf-8")
    )
    composition = compose_document_governance(
        document, registry=GovernanceRegistry.builtins()
    )
    authorizer = Authorizer(
        document, composition, build_agentic_network_lock(document, composition)
    )
    assert resolve_identity(authorizer, "support_coordinator") == (
        "identity.support_coordinator"
    )
