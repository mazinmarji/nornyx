"""CrewAI runtime conformance against the exact pinned framework version.

The declared wrapped surface is synchronous tool execution via a
``crewai.tools.BaseTool._run`` override. Two cases here drive CrewAI's *own*
ReAct executor through ``Crew.kickoff()`` and prove they did so, because a case
that quietly calls the wrapper directly would substantiate nothing about the
framework path it names.

Everything runs offline against a scripted local model. No API key, no network,
and no external model service or endpoint — but a model abstraction really is
instantiated and driven, which is what makes a native run deterministic. The
report says so rather than claiming no model was called at all.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import os
from typing import Any, Callable

# Telemetry must be disabled before the first crewai import in this process.
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")

from ..._compat import require_extra  # noqa: E402

# Imported through require_extra rather than a module-level `import crewai`,
# matching this package's established pattern: the base package's import
# boundary forbids a module-level framework import anywhere in its source, and
# a missing extra should yield an actionable MissingOptionalDependencyError
# rather than a bare ImportError.
_crewai = require_extra("crewai", extra="crewai")
Agent = _crewai.Agent
BaseLLM = _crewai.BaseLLM
Crew = _crewai.Crew
Process = _crewai.Process
Task = _crewai.Task

# The crewai extra guarantees pydantic; import it only after require_extra has
# confirmed the framework is present.
BaseModel = require_extra("pydantic", extra="crewai").BaseModel

from ...binding import SurfaceBinding  # noqa: E402
from ...coverage import SurfaceStatus  # noqa: E402
from ...crewai_adapter import (  # noqa: E402
    COVERAGE_INVENTORY,
    FRAMEWORK,
    METADATA,
    _check_crewai_version,
    make_governed_tool,
    resolve_identity,
)
from ...errors import AdapterConfigurationError  # noqa: E402
from .. import harness as H  # noqa: E402
from ..model import (  # noqa: E402
    CaseClassification,
    CaseOutcome,
    CaseResult,
    CountCheck,
    EventOrder,
    EvidenceValidation,
    ExecutionPath,
    SuiteOutcome,
    SuiteResult,
)

SUITE_ID = "crewai"

#: Calls made to the scripted, offline, in-process model during the last
#: :func:`run`. Read by the runner so the report's
#: ``scripted_in_process_model_called`` is observed rather than declared.
_SCRIPTED_MODEL_CALLS = 0


def scripted_model_calls() -> int:
    """How many times this suite's scripted in-process model was driven."""
    return _SCRIPTED_MODEL_CALLS

WRAPPED_SURFACE = "tool_invocation"
_DETAIL_LIMIT = 240

#: CrewAI's ReAct executor owns its own error-recovery loop and may re-issue a
#: failed tool call an undeclared number of times. Any count on that path is
#: framework-controlled, not an adapter guarantee.
_RETRY_REASON = (
    "CrewAI's ReAct executor may internally retry a failed tool call, so the "
    "repetition count on this path is framework-controlled, not an adapter "
    "guarantee."
)


def _bounded(text: str) -> str:
    return " ".join(str(text).split())[:_DETAIL_LIMIT]


class _DeterministicLLM(BaseLLM):
    """A scripted offline LLM that drives CrewAI's native ReAct executor.

    The first call of a task emits an ``Action:`` step naming the governed
    tool; every later call emits a ``Final Answer:``. ``calls`` is what proves
    a native case actually went through the executor rather than calling the
    wrapper directly — a direct call would leave it at zero.
    """

    def __init__(self, tool_name: str | None, final_answer: str, action_input: str = "{}") -> None:
        super().__init__(model="nornyx-deterministic-offline")
        self._tool_name = tool_name
        self._final_answer = final_answer
        self._action_input = action_input
        self.calls = 0

    def call(
        self,
        messages: Any,
        tools: Any = None,
        callbacks: Any = None,
        available_functions: Any = None,
        **kwargs: Any,
    ) -> str:
        global _SCRIPTED_MODEL_CALLS
        _SCRIPTED_MODEL_CALLS += 1
        self.calls += 1
        if self._tool_name is not None and self.calls == 1:
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


class _TopicInput(BaseModel):
    topic: str


def _declared_status(surface: str) -> str:
    for entry in COVERAGE_INVENTORY.entries:
        if entry.surface == surface:
            return entry.status.value
    return "not_declared"


def _agent(role: str, llm: _DeterministicLLM) -> Agent:
    return Agent(
        role=role,
        goal="Demonstrate governed deterministic offline behavior.",
        backstory="Deterministic local conformance fixture agent.",
        allow_delegation=False,
        verbose=False,
        llm=llm,
    )


def _result(
    case_id: str,
    *,
    surface: str,
    classification: CaseClassification,
    execution_path: ExecutionPath,
    problems: list[str],
    executions: CountCheck,
    authorizations: CountCheck,
    recorder: Any = None,
    expect_evidence: EvidenceValidation = EvidenceValidation.PASS,
    expect_diagnostics: tuple[str, ...] | None = None,
    event_order: EventOrder = EventOrder.RECORDED,
    normalization_reason: str = "",
    expected_effect: str | None = None,
    observed_effect: str | None = None,
    expected_code: str | None = None,
    observed_code: str | None = None,
    covered_by: str | None = None,
    note: str = "",
) -> CaseResult:
    """Assemble a case result, with evidence validity as a pass criterion.

    ``expect_evidence`` is asserted in both directions: a case expecting a
    validating stream fails if validation regresses, and a case documenting a
    known non-validating path fails if that path silently starts validating.
    Either way the report states what was observed, not what was hoped for.
    """
    decision_events = H.decision_event_types(recorder) if recorder is not None else ()
    observation_events = H.observation_event_types(recorder) if recorder is not None else ()
    if event_order is EventOrder.NORMALIZED:
        decision_events = H.normalized(decision_events)
        observation_events = H.normalized(observation_events)

    evidence = (
        H.validate_evidence(recorder)
        if recorder is not None
        else EvidenceValidation.NOT_APPLICABLE
    )
    diagnostics = (
        H.evidence_diagnostics(recorder)
        if recorder is not None and evidence is EvidenceValidation.FAIL
        else ()
    )
    if expect_diagnostics is not None and diagnostics != tuple(expect_diagnostics):
        problems.append(
            f"evidence diagnostics {list(diagnostics)}, expected {list(expect_diagnostics)}"
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

    outcome = CaseOutcome.FAIL if problems else CaseOutcome.PASS
    detail = "; ".join(problems) if problems else note
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
        decision_events=decision_events,
        observation_events=observation_events,
        event_order=event_order,
        normalization_reason=normalization_reason,
        expected_effect=expected_effect,
        observed_effect=observed_effect,
        expected_code=expected_code,
        observed_code=observed_code,
        decision_precedes_observation=(
            H.decision_precedes_observations(recorder) if recorder is not None else None
        ),
        evidence_validation=evidence,
        evidence_diagnostics=diagnostics,
        covered_by=covered_by,
        detail=_bounded(detail),
    )


def _governed_tool(
    authorizer: Any,
    context: Any,
    recorder: Any,
    action: Callable[..., Any],
    *,
    name: str = "governed_reader",
    identity: str = H.RESEARCHER,
    capability: str = H.READ_CAPABILITY,
    args_schema: type | None = None,
) -> Any:
    return make_governed_tool(
        name=name,
        description="Read governed context.",
        binding=SurfaceBinding(f"tool:{name}", identity, capability),
        authorizer=authorizer,
        context=context,
        recorder=recorder,
        mission_id=H.MISSION_ID,
        action=action,
        args_schema=args_schema,
    )


def _kickoff(agent: Agent, tool: Any) -> Any:
    task = Task(
        description="Use the governed tool as instructed.",
        expected_output="A short governed answer.",
        agent=agent,
        tools=[tool],
    )
    return Crew(agents=[agent], tasks=[task], process=Process.sequential).kickoff()


# ------------------------------------------------------------------ native cases
def _case_native_allow() -> CaseResult:
    authorizer = H.build_authorizer()
    context = H.build_context(authorizer)
    recorder = H.build_recorder(authorizer, context)
    counting = H.CountingAuthorizer(authorizer)
    counter = H.ExecutionCounter()
    llm = _DeterministicLLM("governed_reader", "governed research complete")
    agent = _agent("researcher", llm)

    problems: list[str] = []
    # No guard here: the runner installs one around every executing suite, and
    # a nested guard would capture attempts into its own counter where the
    # run-level report could not see them.
    # Identity resolution through the adapter's own public path.
    if resolve_identity(counting, agent) != H.RESEARCHER:
        problems.append("resolve_identity did not map the CrewAI role to its identity")
    tool = _governed_tool(
        counting, context, recorder, lambda: counter.run("sanitized governed context")
    )
    result = _kickoff(agent, tool)

    if "governed research complete" not in str(result):
        problems.append("the native executor did not return the scripted final answer")
    if llm.calls < 2:
        problems.append(
            f"the ReAct executor drove the LLM {llm.calls} times; a native run needs at least 2"
        )
    if counter.count != 1:
        problems.append(f"action executed {counter.count} times, expected exactly 1")
    if H.decision_event_types(recorder) != ("capability_requested", "capability_allowed"):
        problems.append("unexpected decision-event order on ALLOW")
    if H.observation_event_types(recorder) != ("tool_invoked",):
        problems.append("expected exactly one tool_invoked observation")
    if H.decision_precedes_observations(recorder) is False:
        problems.append("tool_invoked was recorded before the authorizing decision")

    return _result(
        "crewai.native.allow",
        surface=WRAPPED_SURFACE,
        classification=CaseClassification.GOVERNED,
        execution_path=ExecutionPath.NATIVE,
        problems=problems,
        executions=CountCheck("exact", 1, counter.count),
        authorizations=CountCheck("exact", 1, counting.evaluations),
        recorder=recorder,
        expected_effect="allow",
        observed_effect="allow",
        expected_code="ALLOWED",
        observed_code="ALLOWED",
    )


def _case_native_deny() -> CaseResult:
    """The agent holds no such capability. CrewAI observes a tool error and may
    retry it; the wrapped side effect must still never run."""
    authorizer = H.build_authorizer()
    context = H.build_context(authorizer)
    recorder = H.build_recorder(authorizer, context)
    counting = H.CountingAuthorizer(authorizer)
    counter = H.ExecutionCounter()
    llm = _DeterministicLLM("proposer", "should never be reached")
    agent = _agent("reviewer", llm)

    problems: list[str] = []
    tool = _governed_tool(
        counting,
        context,
        recorder,
        lambda: counter.run("must not run"),
        name="proposer",
        identity=H.REVIEWER,
        capability=H.PROPOSE_CAPABILITY,
    )
    _kickoff(agent, tool)

    recorded = H.decision_event_types(recorder)
    observations = H.observation_event_types(recorder)
    if counter.count != 0:
        problems.append(f"the wrapped action ran {counter.count} times on a denied capability")
    if observations:
        problems.append(f"a success observation was recorded on denial: {list(observations)}")
    if "capability_denied" not in recorded:
        problems.append("no capability_denied event was recorded")
    if set(recorded) - {"capability_requested", "capability_denied"}:
        problems.append(f"unexpected decision events on denial: {sorted(set(recorded))}")
    # Retry-safe, and strictly stronger than a bare membership check: the
    # recorder commits a decision's intents as one atomic batch, so however many
    # times CrewAI retried, requests and denials must pair up exactly.
    if recorded.count("capability_requested") != recorded.count("capability_denied"):
        problems.append("capability_requested and capability_denied events did not pair up")
    if counting.evaluations < 1:
        problems.append("no authorization was evaluated")

    return _result(
        "crewai.native.deny",
        surface=WRAPPED_SURFACE,
        classification=CaseClassification.GOVERNED,
        execution_path=ExecutionPath.NATIVE,
        problems=problems,
        executions=CountCheck("exact", 0, counter.count),
        authorizations=CountCheck("at_least", 1, reason=_RETRY_REASON),
        recorder=recorder,
        # An observed limitation, reported rather than hidden: because CrewAI's
        # executor retries the denied call and legacy-mode evidence carries no
        # occurrence identity, the repeated identical decision batches are
        # flagged AN_EVT_REPLAY.
        #
        # The exact diagnostic code is asserted, not merely "it failed".
        # Without that, any future evidence regression on this path -- a broken
        # contract digest, a stale lock, a schema-invalid event -- would produce
        # the same bare failure and the same reassuring prose, and would be
        # structurally invisible on the deny control of a wrapped surface.
        expect_evidence=EvidenceValidation.FAIL,
        expect_diagnostics=("AN_EVT_REPLAY",),
        event_order=EventOrder.NORMALIZED,
        normalization_reason=_RETRY_REASON,
        expected_effect="deny",
        observed_effect="deny",
        expected_code="CAPABILITY_DENIED",
        note=(
            "Fail-closed held: zero executions, paired requested/denied events. "
            "Evidence does not validate: CrewAI retried the denied call and "
            "legacy-mode events carry no occurrence identity, so the repeats "
            "are flagged AN_EVT_REPLAY."
        ),
    )


def _case_native_structured_args() -> CaseResult:
    authorizer = H.build_authorizer()
    context = H.build_context(authorizer)
    recorder = H.build_recorder(authorizer, context)
    counting = H.CountingAuthorizer(authorizer)
    seen: list[str] = []
    llm = _DeterministicLLM(
        "governed_reader", "structured research complete", action_input='{"topic": "alpha"}'
    )
    agent = _agent("researcher", llm)

    def action(topic: str) -> str:
        seen.append(topic)
        return f"read:{topic}"

    problems: list[str] = []
    tool = _governed_tool(counting, context, recorder, action, args_schema=_TopicInput)
    _kickoff(agent, tool)

    if seen != ["alpha"]:
        problems.append(f"validated arguments did not reach the action: {seen}")
    if llm.calls < 2:
        problems.append(f"the ReAct executor drove the LLM {llm.calls} times, expected 2+")
    if H.observation_event_types(recorder) != ("tool_invoked",):
        problems.append("expected exactly one tool_invoked observation")
    if H.decision_precedes_observations(recorder) is False:
        problems.append("tool_invoked was recorded before the authorizing decision")

    return _result(
        "crewai.native.structured_args",
        surface=WRAPPED_SURFACE,
        classification=CaseClassification.GOVERNED,
        execution_path=ExecutionPath.NATIVE,
        problems=problems,
        executions=CountCheck("exact", 1, len(seen)),
        authorizations=CountCheck("exact", 1, counting.evaluations),
        recorder=recorder,
        expected_effect="allow",
        observed_effect="allow",
    )


# ------------------------------------------------------------------ direct cases
def _case_action_error() -> CaseResult:
    """An authorized action that fails records ``runtime_failed`` exactly once
    and never ``tool_invoked``."""
    authorizer = H.build_authorizer()
    context = H.build_context(authorizer)
    recorder = H.build_recorder(authorizer, context)
    counting = H.CountingAuthorizer(authorizer)
    counter = H.ExecutionCounter()

    problems: list[str] = []
    tool = _governed_tool(
        counting, context, recorder, lambda: counter.run(raises=RuntimeError("action failed"))
    )
    try:
        tool.run()
        problems.append("the action's failure did not propagate")
    except Exception:  # noqa: BLE001 - CrewAI may wrap the underlying error
        pass

    observations = H.observation_event_types(recorder)
    if counter.count != 1:
        problems.append(f"action executed {counter.count} times, expected exactly 1")
    if observations != ("runtime_failed",):
        problems.append(f"observations {list(observations)}, expected exactly one runtime_failed")
    if "tool_invoked" in observations:
        problems.append("tool_invoked was recorded for an action that failed")

    return _result(
        "crewai.direct.action_error",
        surface=WRAPPED_SURFACE,
        classification=CaseClassification.GOVERNED,
        execution_path=ExecutionPath.DIRECT,
        problems=problems,
        executions=CountCheck("exact", 1, counter.count),
        authorizations=CountCheck("exact", 1, counting.evaluations),
        recorder=recorder,
        expected_effect="allow",
        observed_effect="allow",
    )


def _case_invalid_args() -> CaseResult:
    """Invalid structured input is rejected by CrewAI before ``_run``, so no
    authorization is evaluated at all — a pre-authorization rejection, not a
    denial, and the report must not conflate the two."""
    authorizer = H.build_authorizer()
    context = H.build_context(authorizer)
    recorder = H.build_recorder(authorizer, context)
    counting = H.CountingAuthorizer(authorizer)
    counter = H.ExecutionCounter()

    problems: list[str] = []
    tool = _governed_tool(
        counting,
        context,
        recorder,
        lambda topic: counter.run(topic),
        args_schema=_TopicInput,
    )
    try:
        tool.run(not_topic="x")
        problems.append("invalid structured input was accepted")
    except Exception:  # noqa: BLE001
        pass

    if counter.count != 0:
        problems.append(f"the action ran {counter.count} times on invalid input")
    if H.event_types(recorder):
        problems.append("events were recorded for input rejected before authorization")

    return _result(
        "crewai.direct.invalid_args_rejected",
        surface=WRAPPED_SURFACE,
        classification=CaseClassification.GOVERNED,
        execution_path=ExecutionPath.DIRECT,
        problems=problems,
        executions=CountCheck("exact", 0, counter.count),
        authorizations=CountCheck("exact", 0, counting.evaluations),
        # Rejected before any authorization, so nothing is recorded. There is
        # no evidence to validate, and 'pass' would be a positive claim about
        # an empty stream.
        expect_evidence=EvidenceValidation.NOT_APPLICABLE,
        recorder=recorder,
    )


# ------------------------------------------------- unsupported / bypass controls
def _case_async_unsupported() -> CaseResult:
    """The async tool path is declared unsupported and must stay that way: the
    inherited ``_arun`` raises, so nothing executes and nothing is recorded."""
    authorizer = H.build_authorizer()
    context = H.build_context(authorizer)
    recorder = H.build_recorder(authorizer, context)
    counting = H.CountingAuthorizer(authorizer)
    counter = H.ExecutionCounter()

    problems: list[str] = []
    tool = _governed_tool(counting, context, recorder, lambda: counter.run("must not run"))
    try:
        asyncio.run(tool.arun())
        problems.append("the async path executed instead of failing closed")
    except NotImplementedError:
        pass
    except Exception as exc:  # noqa: BLE001
        problems.append(f"async path raised {type(exc).__name__}, expected NotImplementedError")

    if counter.count != 0:
        problems.append(f"the wrapped action ran {counter.count} times on the async path")
    if H.event_types(recorder):
        problems.append("events were recorded for an unsupported surface")
    if _declared_status("async_tool_invocation") != SurfaceStatus.UNSUPPORTED.value:
        problems.append("async_tool_invocation is no longer declared unsupported")

    return _result(
        "crewai.unsupported.async_tool_invocation",
        surface="async_tool_invocation",
        classification=CaseClassification.UNSUPPORTED_SURFACE,
        execution_path=ExecutionPath.DIRECT,
        problems=problems,
        executions=CountCheck("exact", 0, counter.count),
        authorizations=CountCheck("exact", 0, counting.evaluations),
        recorder=recorder,
        # The inherited _arun raises before the governed _run is reached, so
        # nothing is recorded and there is no evidence to validate.
        expect_evidence=EvidenceValidation.NOT_APPLICABLE,
    )


def _case_approval_required_not_representable() -> CaseResult:
    """APPROVAL_REQUIRED cannot occur on this surface, and saying so is the
    honest result.

    The governed tool issues a ``CapabilityRequest``, and in this core an
    APPROVAL_REQUIRED effect is reachable only from a zone-crossing request.
    No contract or fixture can make a real CrewAI tool observe one. Faking it
    with a stub authorizer would prove only that ``enforce()`` fails closed,
    which the framework-neutral case already proves — so this case names that
    case instead of inventing evidence.
    """
    return CaseResult(
        case_id="crewai.unsupported.approval_required",
        framework=FRAMEWORK,
        surface=WRAPPED_SURFACE,
        declared_status=_declared_status(WRAPPED_SURFACE),
        classification=CaseClassification.UNSUPPORTED_SURFACE,
        outcome=CaseOutcome.NOT_REPRESENTABLE,
        execution_path=ExecutionPath.DIRECT,
        action_executions=CountCheck("exact", 0, 0),
        authorizations=CountCheck("exact", 0, 0),
        covered_by="neutral.enforce.approval_required",
        detail=(
            "The CrewAI tool surface issues CapabilityRequest only; an "
            "APPROVAL_REQUIRED effect is reachable in this core exclusively via "
            "a zone-crossing request to an external-classification zone."
        ),
    )


def _case_bypass() -> CaseResult:
    """Calling the underlying work callable directly bypasses the adapter
    entirely. Nothing here prevents that — which is what cooperative Tier 2
    means, and why this is reported as outside declared coverage rather than
    as a governed path.

    A real governed tool is constructed first, and the action it wraps is then
    invoked directly, so the control demonstrates bypass of an actually-built
    wrapper rather than of nothing at all.
    """
    authorizer = H.build_authorizer()
    context = H.build_context(authorizer)
    recorder = H.build_recorder(authorizer, context)
    counting = H.CountingAuthorizer(authorizer)
    counter = H.ExecutionCounter()
    problems: list[str] = []

    action = lambda: counter.run("ran with no authorization check whatsoever")  # noqa: E731
    # The reviewer identity does not hold this capability: through the governed
    # tool this would be denied.
    _governed_tool(
        counting,
        context,
        recorder,
        action,
        name="proposer",
        identity=H.REVIEWER,
        capability=H.PROPOSE_CAPABILITY,
    )

    result = action()
    if result != "ran with no authorization check whatsoever" or counter.count != 1:
        problems.append("the bypassed action did not execute")
    if counting.evaluations != 0:
        problems.append("a decision was evaluated on a bypassed call")
    if H.event_types(recorder):
        problems.append("a bypassed call produced governance evidence")

    return _result(
        "crewai.bypass.direct_action",
        surface=WRAPPED_SURFACE,
        classification=CaseClassification.BYPASS_CONTROL,
        execution_path=ExecutionPath.DIRECT,
        problems=problems,
        executions=CountCheck("exact", 1, counter.count),
        authorizations=CountCheck("exact", 0, counting.evaluations),
        recorder=recorder,
        expect_evidence=EvidenceValidation.NOT_APPLICABLE,
        note=(
            "Bypassing the adapter bypasses enforcement: a governed tool was "
            "built, its underlying action was called directly, no decision was "
            "evaluated and no evidence was produced. Outside declared coverage."
        ),
    )


def _case_version_guard() -> CaseResult:
    """The exact framework pin is enforced, not merely declared."""
    problems: list[str] = []
    installed = importlib.metadata.version("crewai")
    expected = METADATA.framework_version_range.removeprefix("==")
    if installed != expected:
        problems.append(f"installed crewai {installed!r}, adapter declares {expected!r}")
    try:
        _check_crewai_version("0.0.0-not-a-supported-version")
        problems.append("an unsupported CrewAI version was accepted")
    except AdapterConfigurationError:
        pass

    return _result(
        "crewai.boundary.version_pin_enforced",
        surface="distribution",
        classification=CaseClassification.DISTRIBUTION_BOUNDARY,
        execution_path=ExecutionPath.BOUNDARY,
        problems=problems,
        executions=CountCheck("exact", 0, 0),
        authorizations=CountCheck("exact", 0, 0),
        expect_evidence=EvidenceValidation.NOT_APPLICABLE,
        note="The exact CrewAI pin is enforced at import time, not merely declared.",
    )


_CASES: tuple[Callable[[], CaseResult], ...] = (
    _case_native_allow,
    _case_native_deny,
    _case_native_structured_args,
    _case_action_error,
    _case_invalid_args,
    _case_async_unsupported,
    _case_approval_required_not_representable,
    _case_bypass,
    _case_version_guard,
)


def run(case_ids: frozenset[str] | None = None) -> SuiteResult:
    global _SCRIPTED_MODEL_CALLS
    _SCRIPTED_MODEL_CALLS = 0
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
        framework_version=importlib.metadata.version("crewai"),
        declared_coverage=tuple(COVERAGE_INVENTORY.as_dict()["surfaces"]),
    )


__all__ = ["SUITE_ID", "run"]
