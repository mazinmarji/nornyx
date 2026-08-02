"""LangGraph runtime conformance against the exact pinned framework version.

The declared wrapped surface is synchronous ``StateGraph`` node execution. Every
governed case here runs a real compiled graph through ``graph.invoke()``, so the
occurrence identities under test are the ones LangGraph's own scheduler minted —
including under native retry, looping, parallel branches, interrupt, and
checkpoint resume.

Raw occurrence ids never reach the report: LangGraph mints a fresh ``task_id``
per process, so only the determinism-safe facts derived from them are recorded.
"""

from __future__ import annotations

import importlib.metadata
from typing import Any, Callable, TypedDict

from nornyx.agentic import EvidenceRecorder

from ..._compat import require_extra

# Imported through require_extra rather than module-level `import langgraph`,
# matching this package's established pattern: the base package's import
# boundary forbids a module-level framework import anywhere in its source, and
# a missing extra should yield an actionable MissingOptionalDependencyError
# rather than a bare ImportError.
InMemorySaver = require_extra("langgraph.checkpoint.memory", extra="langgraph").InMemorySaver
_graph = require_extra("langgraph.graph", extra="langgraph")
END, START, StateGraph = _graph.END, _graph.START, _graph.StateGraph
Runtime = require_extra("langgraph.runtime", extra="langgraph").Runtime
_types = require_extra("langgraph.types", extra="langgraph")
Command, RetryPolicy, interrupt = _types.Command, _types.RetryPolicy, _types.interrupt

from ...binding import SurfaceBinding  # noqa: E402
from ...coverage import SurfaceStatus  # noqa: E402
from ...errors import AdapterConfigurationError, AdapterDenied  # noqa: E402
from ...langgraph import (  # noqa: E402
    COVERAGE_INVENTORY,
    FRAMEWORK,
    METADATA,
    _check_langgraph_version,
    make_governed_node,
    resolve_identity,
)
from .. import harness as H  # noqa: E402
from ..model import (  # noqa: E402
    CaseClassification,
    CaseOutcome,
    CaseResult,
    CountCheck,
    EvidenceValidation,
    ExecutionPath,
    SuiteOutcome,
    SuiteResult,
)

SUITE_ID = "langgraph"
WRAPPED_SURFACE = "sync_node_invocation"
_DETAIL_LIMIT = 240


def _bounded(text: str) -> str:
    return " ".join(str(text).split())[:_DETAIL_LIMIT]


def _declared_status(surface: str) -> str:
    for entry in COVERAGE_INVENTORY.entries:
        if entry.surface == surface:
            return entry.status.value
    return "not_declared"


class _Ctx:
    """One authorizer/context/recorder triple plus its instrumentation."""

    def __init__(self, *, occurrences: bool = True) -> None:
        self.authorizer = H.build_authorizer()
        self.context = H.build_context(self.authorizer)
        self.recorder: EvidenceRecorder = (
            H.build_occurrence_recorder(self.authorizer, self.context)
            if occurrences
            else H.build_recorder(self.authorizer, self.context)
        )
        self.counting = H.CountingAuthorizer(self.authorizer)
        self.counter = H.ExecutionCounter()

    def node(
        self,
        action: Callable[[Any], Any],
        *,
        surface: str = "node.read",
        identity: str = H.RESEARCHER,
        capability: str = H.READ_CAPABILITY,
    ) -> Callable[[Any, Runtime], Any]:
        return make_governed_node(
            binding=SurfaceBinding(surface, identity, capability),
            authorizer=self.counting,
            context=self.context,
            recorder=self.recorder,
            mission_id=H.MISSION_ID,
            action=action,
        )


def _single_graph(node: Any, *, retry_policy: Any = None, checkpointer: Any = None) -> Any:
    builder = StateGraph(dict)
    builder.add_node("read", node, retry_policy=retry_policy)
    builder.add_edge(START, "read")
    builder.add_edge("read", END)
    return builder.compile(checkpointer=checkpointer)


def _result(
    case_id: str,
    *,
    surface: str,
    classification: CaseClassification,
    execution_path: ExecutionPath,
    problems: list[str],
    executions: CountCheck,
    authorizations: CountCheck,
    ctx: _Ctx | None = None,
    expect_evidence: EvidenceValidation = EvidenceValidation.PASS,
    expected_effect: str | None = None,
    observed_effect: str | None = None,
    expected_code: str | None = None,
    observed_code: str | None = None,
    note: str = "",
) -> CaseResult:
    recorder = ctx.recorder if ctx is not None else None
    evidence = (
        H.validate_evidence(recorder)
        if recorder is not None
        else EvidenceValidation.NOT_APPLICABLE
    )
    if evidence is not expect_evidence:
        problems.append(
            f"evidence validation {evidence.value!r}, expected {expect_evidence.value!r}"
        )
    if not executions.satisfied:
        problems.append(
            f"action executions {executions.observed}, expected {executions.expected}"
        )
    if not authorizations.satisfied:
        problems.append(
            f"authorizations {authorizations.observed}, expected {authorizations.expected}"
        )
    summary = H.summarize_occurrences(recorder) if recorder is not None else None
    if summary is not None and summary.collided:
        problems.append("two logical operations shared one occurrence identity")

    outcome = CaseOutcome.FAIL if problems else CaseOutcome.PASS
    return CaseResult(
        case_id=case_id,
        framework=FRAMEWORK,
        surface=surface,
        declared_status=_declared_status(surface),
        classification=classification,
        outcome=outcome,
        execution_path=execution_path,
        action_executions=executions,
        authorizations=authorizations,
        decision_events=H.decision_event_types(recorder) if recorder else (),
        observation_events=H.observation_event_types(recorder) if recorder else (),
        expected_effect=expected_effect,
        observed_effect=observed_effect,
        expected_code=expected_code,
        observed_code=observed_code,
        decision_precedes_action=(
            H.decision_precedes_observations(recorder) if recorder else None
        ),
        evidence_validation=evidence,
        occurrence_summary=summary,
        detail=_bounded("; ".join(problems) if problems else note),
    )


# ------------------------------------------------------------------ governed cases
def _case_allow() -> CaseResult:
    ctx = _Ctx()
    problems: list[str] = []
    if resolve_identity(ctx.counting, "researcher") != H.RESEARCHER:
        problems.append("resolve_identity did not map the LangGraph node key")
    graph = _single_graph(ctx.node(lambda state: ctx.counter.run({"value": 1})))
    if graph.invoke({}) != {"value": 1}:
        problems.append("the graph did not return the node's result unchanged")
    if H.decision_event_types(ctx.recorder) != ("capability_requested", "capability_allowed"):
        problems.append("unexpected decision-event order on ALLOW")
    if H.observation_event_types(ctx.recorder) != ("agent_invoked",):
        problems.append("expected exactly one agent_invoked observation")
    if not H.decision_precedes_observations(ctx.recorder):
        problems.append("the success observation preceded the authorizing decision")
    summary = H.summarize_occurrences(ctx.recorder)
    if summary.distinct_occurrences != 1 or summary.attempts != (1,):
        problems.append(f"expected one occurrence at attempt 1, got {summary.as_dict()}")

    return _result(
        "langgraph.native.allow",
        surface=WRAPPED_SURFACE,
        classification=CaseClassification.GOVERNED,
        execution_path=ExecutionPath.NATIVE,
        problems=problems,
        executions=CountCheck("exact", 1, ctx.counter.count),
        authorizations=CountCheck("exact", 1, ctx.counting.evaluations),
        ctx=ctx,
        expected_effect="allow",
        observed_effect="allow",
        expected_code="ALLOWED",
        observed_code="ALLOWED",
    )


def _case_deny() -> CaseResult:
    ctx = _Ctx()
    problems: list[str] = []
    observed_code: str | None = None
    node = ctx.node(
        lambda state: ctx.counter.run("must not run"),
        surface="node.denied",
        identity=H.REVIEWER,
        capability=H.PROPOSE_CAPABILITY,
    )
    try:
        _single_graph(node).invoke({})
        problems.append("the graph completed instead of raising AdapterDenied")
    except AdapterDenied as denied:
        observed_code = denied.decision.code.value
    except Exception as exc:  # noqa: BLE001
        problems.append(f"raised {type(exc).__name__} instead of AdapterDenied")

    if H.observation_event_types(ctx.recorder):
        problems.append("a success observation was recorded on denial")
    if H.decision_event_types(ctx.recorder) != ("capability_requested", "capability_denied"):
        problems.append("unexpected decision-event order on denial")

    return _result(
        "langgraph.native.deny",
        surface=WRAPPED_SURFACE,
        classification=CaseClassification.GOVERNED,
        execution_path=ExecutionPath.NATIVE,
        problems=problems,
        executions=CountCheck("exact", 0, ctx.counter.count),
        authorizations=CountCheck("exact", 1, ctx.counting.evaluations),
        ctx=ctx,
        expected_effect="deny",
        observed_effect="deny",
        expected_code="CAPABILITY_DENIED",
        observed_code=observed_code,
    )


def _case_action_error() -> CaseResult:
    ctx = _Ctx()
    problems: list[str] = []

    def boom(_state: Any) -> Any:
        return ctx.counter.run(raises=ValueError("node action failed"))

    try:
        _single_graph(ctx.node(boom)).invoke({})
        problems.append("the node failure did not propagate")
    except ValueError:
        pass
    except Exception as exc:  # noqa: BLE001
        problems.append(f"propagated {type(exc).__name__}, expected ValueError")

    observations = H.observation_event_types(ctx.recorder)
    if observations != ("runtime_failed",):
        problems.append(f"observations {list(observations)}, expected one runtime_failed")

    return _result(
        "langgraph.native.action_error",
        surface=WRAPPED_SURFACE,
        classification=CaseClassification.GOVERNED,
        execution_path=ExecutionPath.NATIVE,
        problems=problems,
        executions=CountCheck("exact", 1, ctx.counter.count),
        authorizations=CountCheck("exact", 1, ctx.counting.evaluations),
        ctx=ctx,
        expected_effect="allow",
        observed_effect="allow",
    )


def _case_retry() -> CaseResult:
    """Native retry is one occurrence with successive attempts, not repeats."""
    ctx = _Ctx()
    problems: list[str] = []

    def flaky(_state: Any) -> Any:
        ctx.counter.count += 1
        if ctx.counter.count < 3:
            raise ValueError("retry")
        return {"value": ctx.counter.count}

    graph = _single_graph(
        ctx.node(flaky),
        retry_policy=RetryPolicy(max_attempts=3, retry_on=ValueError, initial_interval=0),
    )
    if graph.invoke({}) != {"value": 3}:
        problems.append("the retried node did not converge to its third attempt")
    summary = H.summarize_occurrences(ctx.recorder)
    if summary.distinct_occurrences != 1:
        problems.append(f"retry produced {summary.distinct_occurrences} occurrences, expected 1")
    if summary.attempts != (1, 2, 3):
        problems.append(f"attempts {list(summary.attempts)}, expected 1, 2, 3")
    observations = H.observation_event_types(ctx.recorder)
    if observations.count("runtime_failed") != 2:
        problems.append(f"expected two runtime_failed, got {list(observations)}")
    if observations.count("agent_invoked") != 1:
        problems.append("expected exactly one successful observation across retries")

    return _result(
        "langgraph.native.retry",
        surface=WRAPPED_SURFACE,
        classification=CaseClassification.GOVERNED,
        execution_path=ExecutionPath.NATIVE,
        problems=problems,
        executions=CountCheck("exact", 3, ctx.counter.count),
        authorizations=CountCheck("exact", 3, ctx.counting.evaluations),
        ctx=ctx,
    )


class _LoopState(TypedDict):
    count: int


def _case_loop() -> CaseResult:
    """Repeat visits are distinct occurrences, each at attempt 1."""
    ctx = _Ctx()
    problems: list[str] = []
    node = ctx.node(
        lambda state: ctx.counter.run({"count": state["count"] + 1}), surface="node.loop"
    )
    builder = StateGraph(_LoopState)
    builder.add_node("loop", node)
    builder.add_edge(START, "loop")
    builder.add_conditional_edges("loop", lambda s: "loop" if s["count"] < 2 else END)
    if builder.compile().invoke({"count": 0})["count"] != 2:
        problems.append("the loop did not run twice")
    summary = H.summarize_occurrences(ctx.recorder)
    if summary.distinct_occurrences != 2:
        problems.append(f"loop produced {summary.distinct_occurrences} occurrences, expected 2")
    if summary.attempts != (1,):
        problems.append(f"attempts {list(summary.attempts)}, expected every visit at attempt 1")

    return _result(
        "langgraph.native.loop",
        surface=WRAPPED_SURFACE,
        classification=CaseClassification.GOVERNED,
        execution_path=ExecutionPath.NATIVE,
        problems=problems,
        executions=CountCheck("exact", 2, ctx.counter.count),
        authorizations=CountCheck("exact", 2, ctx.counting.evaluations),
        ctx=ctx,
    )


class _ParallelState(TypedDict, total=False):
    left: int
    right: int


def _case_parallel() -> CaseResult:
    """Parallel branches must not collide on one occurrence identity."""
    ctx = _Ctx()
    problems: list[str] = []
    builder = StateGraph(_ParallelState)
    builder.add_node(
        "left", ctx.node(lambda _s: ctx.counter.run({"left": 1}), surface="node.left")
    )
    builder.add_node(
        "right", ctx.node(lambda _s: ctx.counter.run({"right": 1}), surface="node.right")
    )
    builder.add_edge(START, "left")
    builder.add_edge(START, "right")
    builder.add_edge("left", END)
    builder.add_edge("right", END)
    if builder.compile().invoke({}) != {"left": 1, "right": 1}:
        problems.append("both parallel branches did not complete")
    summary = H.summarize_occurrences(ctx.recorder)
    if summary.distinct_occurrences != 2:
        problems.append(f"parallel produced {summary.distinct_occurrences} occurrences, expected 2")

    return _result(
        "langgraph.native.parallel",
        surface=WRAPPED_SURFACE,
        classification=CaseClassification.GOVERNED,
        execution_path=ExecutionPath.NATIVE,
        problems=problems,
        executions=CountCheck("exact", 2, ctx.counter.count),
        authorizations=CountCheck("exact", 2, ctx.counting.evaluations),
        ctx=ctx,
    )


def _case_interrupt_and_resume() -> CaseResult:
    """An interrupted attempt is control flow, not a runtime failure, and the
    resumed attempt must not collide with the incomplete prefix."""
    ctx = _Ctx()
    problems: list[str] = []
    graph = _single_graph(
        ctx.node(lambda _s: {"answer": interrupt("approve")}), checkpointer=InMemorySaver()
    )
    config = {"configurable": {"thread_id": "conformance-thread"}}
    interrupted = graph.invoke({}, config)
    if not interrupted.get("__interrupt__"):
        problems.append("the graph did not interrupt")
    if "runtime_failed" in H.observation_event_types(ctx.recorder):
        problems.append("an interrupt was recorded as a runtime failure")
    if graph.invoke(Command(resume="yes"), config) != {"answer": "yes"}:
        problems.append("the resumed graph did not return the resumed value")

    summary = H.summarize_occurrences(ctx.recorder)
    if summary.distinct_occurrences != 1:
        problems.append(
            f"resume produced {summary.distinct_occurrences} occurrences, expected 1"
        )
    if summary.attempts != (1, 2):
        problems.append(
            f"attempts {list(summary.attempts)}, expected the resumed attempt to follow the first"
        )

    return _result(
        "langgraph.native.interrupt_resume",
        surface=WRAPPED_SURFACE,
        classification=CaseClassification.GOVERNED,
        execution_path=ExecutionPath.NATIVE,
        problems=problems,
        executions=CountCheck("exact", 0, 0),
        authorizations=CountCheck("exact", 2, ctx.counting.evaluations),
        ctx=ctx,
        note=(
            "Interrupt is control flow: no runtime_failed was recorded for the "
            "incomplete attempt, and the resumed attempt offset from the "
            "validated prefix rather than colliding with it."
        ),
    )


# --------------------------------------------------- fail-closed / unsupported
def _case_missing_execution_info() -> CaseResult:
    ctx = _Ctx()
    problems: list[str] = []
    node = ctx.node(lambda state: ctx.counter.run("must not run"))
    try:
        node({}, Runtime())
        problems.append("a node without execution metadata executed anyway")
    except AdapterConfigurationError:
        pass
    except Exception as exc:  # noqa: BLE001
        problems.append(f"raised {type(exc).__name__}, expected AdapterConfigurationError")
    if H.event_types(ctx.recorder):
        problems.append("events were recorded for malformed execution metadata")

    return _result(
        "langgraph.malformed.missing_execution_info",
        surface=WRAPPED_SURFACE,
        classification=CaseClassification.GOVERNED,
        execution_path=ExecutionPath.DIRECT,
        problems=problems,
        executions=CountCheck("exact", 0, ctx.counter.count),
        authorizations=CountCheck("exact", 0, ctx.counting.evaluations),
        ctx=ctx,
    )


def _case_async_node_unsupported() -> CaseResult:
    ctx = _Ctx()
    problems: list[str] = []

    async def async_action(_state: Any) -> Any:  # pragma: no cover - never awaited
        return {"value": 1}

    try:
        ctx.node(async_action)
        problems.append("an asynchronous node action was accepted")
    except AdapterConfigurationError:
        pass
    except Exception as exc:  # noqa: BLE001
        problems.append(f"raised {type(exc).__name__}, expected AdapterConfigurationError")
    if _declared_status("async_node_invocation") != SurfaceStatus.UNSUPPORTED.value:
        problems.append("async_node_invocation is no longer declared unsupported")

    return _result(
        "langgraph.unsupported.async_node",
        surface="async_node_invocation",
        classification=CaseClassification.UNSUPPORTED_SURFACE,
        execution_path=ExecutionPath.DIRECT,
        problems=problems,
        executions=CountCheck("exact", 0, 0),
        authorizations=CountCheck("exact", 0, 0),
        ctx=ctx,
    )


def _case_legacy_recorder_rejected() -> CaseResult:
    """Occurrence-aware enforcement requires an explicit occurrence recorder."""
    ctx = _Ctx(occurrences=False)
    problems: list[str] = []
    try:
        ctx.node(lambda state: state)
        problems.append("a legacy-mode recorder was accepted for occurrence-aware nodes")
    except AdapterConfigurationError:
        pass
    except Exception as exc:  # noqa: BLE001
        problems.append(f"raised {type(exc).__name__}, expected AdapterConfigurationError")

    return _result(
        "langgraph.malformed.legacy_recorder_rejected",
        surface=WRAPPED_SURFACE,
        classification=CaseClassification.GOVERNED,
        execution_path=ExecutionPath.DIRECT,
        problems=problems,
        executions=CountCheck("exact", 0, 0),
        authorizations=CountCheck("exact", 0, 0),
        ctx=ctx,
    )


def _case_unwrapped_topology() -> CaseResult:
    """Graph topology is declared unwrapped: the caller owns construction, and
    an unwrapped node is simply not governed."""
    ctx = _Ctx()
    problems: list[str] = []
    if _declared_status("graph_topology") != SurfaceStatus.UNWRAPPED.value:
        problems.append("graph_topology is no longer declared unwrapped")
    builder = StateGraph(dict)
    builder.add_node("ungoverned", lambda state: ctx.counter.run({"value": 1}))
    builder.add_edge(START, "ungoverned")
    builder.add_edge("ungoverned", END)
    builder.compile().invoke({})
    if ctx.counter.count != 1:
        problems.append("the ungoverned node did not run")
    if H.event_types(ctx.recorder):
        problems.append("an unwrapped node produced governance evidence")

    return _result(
        "langgraph.unwrapped.graph_topology",
        surface="graph_topology",
        classification=CaseClassification.BYPASS_CONTROL,
        execution_path=ExecutionPath.NATIVE,
        problems=problems,
        executions=CountCheck("exact", 1, ctx.counter.count),
        authorizations=CountCheck("exact", 0, ctx.counting.evaluations),
        ctx=ctx,
        note=(
            "A node the caller never wrapped executes with no decision and no "
            "evidence. Outside declared coverage, exactly as the inventory says."
        ),
    )


def _case_version_guard() -> CaseResult:
    problems: list[str] = []
    installed = importlib.metadata.version("langgraph")
    expected = METADATA.framework_version_range.removeprefix("==")
    if installed != expected:
        problems.append(f"installed langgraph {installed!r}, adapter declares {expected!r}")
    try:
        _check_langgraph_version("0.0.0-not-a-supported-version")
        problems.append("an unsupported LangGraph version was accepted")
    except AdapterConfigurationError:
        pass

    return _result(
        "langgraph.boundary.version_pin_enforced",
        surface=WRAPPED_SURFACE,
        classification=CaseClassification.DISTRIBUTION_BOUNDARY,
        execution_path=ExecutionPath.BOUNDARY,
        problems=problems,
        executions=CountCheck("exact", 0, 0),
        authorizations=CountCheck("exact", 0, 0),
        expect_evidence=EvidenceValidation.NOT_APPLICABLE,
        note="The exact LangGraph pin is enforced at import time, not merely declared.",
    )


_CASES: tuple[Callable[[], CaseResult], ...] = (
    _case_allow,
    _case_deny,
    _case_action_error,
    _case_retry,
    _case_loop,
    _case_parallel,
    _case_interrupt_and_resume,
    _case_missing_execution_info,
    _case_async_node_unsupported,
    _case_legacy_recorder_rejected,
    _case_unwrapped_topology,
    _case_version_guard,
)


def run(case_ids: frozenset[str] | None = None) -> SuiteResult:
    cases: list[CaseResult] = []
    for factory in _CASES:
        result = factory()
        if case_ids is not None and result.case_id not in case_ids:
            continue
        cases.append(result)
    cases.sort(key=lambda case: case.case_id)
    outcome = (
        SuiteOutcome.FAIL
        if any(case.outcome is CaseOutcome.FAIL for case in cases)
        else SuiteOutcome.PASS
    )
    return SuiteResult(
        suite_id=SUITE_ID,
        framework=FRAMEWORK,
        outcome=outcome,
        cases=tuple(cases),
        framework_version=importlib.metadata.version("langgraph"),
        declared_coverage=tuple(COVERAGE_INVENTORY.as_dict()["surfaces"]),
    )


__all__ = ["SUITE_ID", "run"]
