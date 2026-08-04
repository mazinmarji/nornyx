"""Framework-neutral conformance for the ``enforce()`` boundary.

Every case here exercises the real :func:`nornyx_agentic_adapters.enforce`
against the real core SPI. No framework is imported, so this suite runs in the
base install with no extras.

The boundary's guarantee is narrow and worth stating exactly: evaluate, record
the decision's intents, then run the protected action only on ALLOW. Anything
that raises before the action is reached fails closed. ``enforce()`` records no
post-action observation of its own — observation semantics belong to the
framework wrapper — so a case here asserts the *absence* of a fabricated
success just as deliberately as it asserts a real one.
"""

from __future__ import annotations

from typing import Any, Callable

from nornyx.agentic import (
    CapabilityRequest,
    Decision,
    EvidenceRecorder,
    ZoneCrossingRequest,
)

from ...enforcement import enforce
from ...errors import AdapterDenied
from .. import harness as H
from ..model import (
    CaseClassification,
    CaseOutcome,
    CaseResult,
    CountCheck,
    EvidenceValidation,
    SuiteOutcome,
    SuiteResult,
)

SUITE_ID = "enforcement_boundary"
FRAMEWORK = "none"
SURFACE = "enforce"

_DETAIL_LIMIT = 240


def _bounded(text: str) -> str:
    """Bound a failure detail and keep it free of environment-specific noise."""
    collapsed = " ".join(str(text).split())
    return collapsed[:_DETAIL_LIMIT]


def _result(
    case_id: str,
    *,
    problems: list[str],
    executions: int,
    evaluations: int,
    recorder: EvidenceRecorder | None = None,
    expected_effect: str | None = None,
    observed_effect: str | None = None,
    expected_code: str | None = None,
    observed_code: str | None = None,
    expected_executions: int = 0,
) -> CaseResult:
    """Assemble a case result. Evidence validity is a pass criterion here too:
    every framework-neutral case that records anything must produce a stream
    that validates, so a regression cannot hide behind a green behavioral
    assertion."""
    evidence = (
        H.validate_evidence(recorder) if recorder else EvidenceValidation.NOT_APPLICABLE
    )
    # A stream that recorded nothing is NOT_APPLICABLE, not PASS: the
    # fail-closed cases legitimately record nothing, and "the evidence
    # validated" would be a positive statement about nothing.
    if evidence is EvidenceValidation.FAIL:
        problems.append("evidence validation failed")
    actions = CountCheck("exact", expected_executions, executions)
    authorizations = CountCheck("exact", 1, evaluations)
    if not actions.satisfied:
        problems.append(f"action executions {executions}, expected {expected_executions}")
    if not authorizations.satisfied:
        problems.append(f"authorizations {evaluations}, expected 1")
    outcome = CaseOutcome.FAIL if problems else CaseOutcome.PASS
    return CaseResult(
        case_id=case_id,
        framework=FRAMEWORK,
        surface=SURFACE,
        declared_status="not_declared",
        classification=CaseClassification.GOVERNED,
        outcome=outcome,
        action_executions=actions,
        authorizations=authorizations,
        decision_events=H.decision_event_types(recorder) if recorder else (),
        observation_events=H.observation_event_types(recorder) if recorder else (),
        expected_effect=expected_effect,
        observed_effect=observed_effect,
        expected_code=expected_code,
        observed_code=observed_code,
        decision_precedes_observation=(
            H.decision_precedes_observations(recorder) if recorder else None
        ),
        evidence_validation=evidence,
        evidence_diagnostics=(
            H.evidence_diagnostics(recorder)
            if recorder is not None and evidence is EvidenceValidation.FAIL
            else ()
        ),
        detail=_bounded("; ".join(problems)),
    )


class _ExplodingRecorder(EvidenceRecorder):
    """A recorder whose ``record_decision`` fails, to prove the boundary
    fails closed before the protected action is ever reached."""

    def record_decision(self, decision: Decision, *, mission_id: str) -> None:
        raise RuntimeError("recorder failure injected by conformance")


class _ExplodingAuthorizer:
    """An authorizer whose ``evaluate`` fails, to prove the same."""

    def __init__(self, authorizer: Any) -> None:
        self._authorizer = authorizer
        self.evaluations = 0

    def evaluate(self, request: Any, *, context: Any) -> Decision:
        self.evaluations += 1
        raise RuntimeError("evaluation failure injected by conformance")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._authorizer, name)


def _case_allow() -> CaseResult:
    authorizer = H.build_authorizer()
    context = H.build_context(authorizer)
    recorder = H.build_recorder(authorizer, context)
    counting = H.CountingAuthorizer(authorizer)
    counter = H.ExecutionCounter()
    sentinel = object()

    returned = enforce(
        counting,
        CapabilityRequest(H.RESEARCHER, H.READ_CAPABILITY),
        context=context,
        recorder=recorder,
        mission_id=H.MISSION_ID,
        action=lambda: counter.run(sentinel),
    )

    problems: list[str] = []
    if returned is not sentinel:
        problems.append("enforce did not return the action's result unchanged")
    if counter.count != 1:
        problems.append(f"action executed {counter.count} times, expected exactly 1")
    if counting.evaluations != 1:
        problems.append(f"{counting.evaluations} authorizations, expected exactly 1")
    observed = H.observation_event_types(recorder)
    if observed:
        problems.append(f"enforce fabricated a post-action observation: {observed}")
    recorded = H.decision_event_types(recorder)
    if recorded != ("capability_requested", "capability_allowed"):
        problems.append(f"decision events {list(recorded)}, expected request then allow")

    return _result(
        "neutral.enforce.allow",
        problems=problems,
        executions=counter.count,
        evaluations=counting.evaluations,
        recorder=recorder,
        expected_effect="allow",
        observed_effect="allow",
        expected_code="ALLOWED",
        observed_code="ALLOWED",
        expected_executions=1,
    )


def _denial_case(
    case_id: str,
    request: Any,
    *,
    expected_effect: str,
    expected_code: str,
    expected_decision_events: tuple[str, ...],
) -> CaseResult:
    """Shared shape for DENY and APPROVAL_REQUIRED: identical zero-execution
    guarantees, and neither collapsed into ALLOW or a generic exception.

    ``expected_decision_events`` is stated per case rather than assumed,
    because a denial does not always leave a trace: an undeclared identity is
    rejected as a malformed request carrying no event intents at all, so its
    recorded stream is legitimately empty. A kit that assumed every denial
    yields ``capability_denied`` would be wrong about that path, and reporting
    "denial recorded" for it would be false.
    """
    authorizer = H.build_authorizer()
    context = H.build_context(authorizer)
    recorder = H.build_recorder(authorizer, context)
    counting = H.CountingAuthorizer(authorizer)
    counter = H.ExecutionCounter()

    problems: list[str] = []
    observed_effect: str | None = None
    observed_code: str | None = None
    try:
        enforce(
            counting,
            request,
            context=context,
            recorder=recorder,
            mission_id=H.MISSION_ID,
            action=lambda: counter.run("must not run"),
        )
        problems.append("enforce returned instead of raising AdapterDenied")
    except AdapterDenied as denied:
        decision = denied.decision
        observed_effect = decision.effect.value
        observed_code = decision.code.value
        if decision.allowed:
            problems.append("AdapterDenied carried an allowed decision")
        if observed_effect != expected_effect:
            problems.append(f"effect {observed_effect!r}, expected {expected_effect!r}")
        if observed_code != expected_code:
            problems.append(f"code {observed_code!r}, expected {expected_code!r}")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"raised {type(exc).__name__} instead of AdapterDenied")

    if counter.count != 0:
        problems.append(f"action executed {counter.count} times on a non-ALLOW decision")
    if counting.evaluations != 1:
        problems.append(f"{counting.evaluations} authorizations, expected exactly 1")
    observations = H.observation_event_types(recorder)
    if observations:
        problems.append(f"success observation recorded on a non-ALLOW decision: {observations}")
    recorded = H.decision_event_types(recorder)
    if recorded != expected_decision_events:
        problems.append(
            f"decision events {list(recorded)}, expected {list(expected_decision_events)}"
        )

    return _result(
        case_id,
        problems=problems,
        executions=counter.count,
        evaluations=counting.evaluations,
        recorder=recorder,
        expected_effect=expected_effect,
        observed_effect=observed_effect,
        expected_code=expected_code,
        observed_code=observed_code,
    )


def _case_deny() -> CaseResult:
    return _denial_case(
        "neutral.enforce.deny",
        CapabilityRequest(H.REVIEWER, H.PROPOSE_CAPABILITY),
        expected_effect="deny",
        expected_code="CAPABILITY_DENIED",
        expected_decision_events=("capability_requested", "capability_denied"),
    )


def _case_deny_capability_unknown() -> CaseResult:
    """An undeclared capability denies with a single ``policy_violation`` and
    no ``capability_requested`` — a different recorded shape from an ordinary
    denial, and one the report must not misdescribe."""
    return _denial_case(
        "neutral.enforce.deny_capability_unknown",
        CapabilityRequest(H.RESEARCHER, "capability.not_declared"),
        expected_effect="deny",
        expected_code="CAPABILITY_UNKNOWN",
        expected_decision_events=("policy_violation",),
    )


def _case_deny_identity_unknown() -> CaseResult:
    """A denial that legitimately records nothing at all.

    An undeclared identity is rejected as a malformed request whose decision
    carries no event intents, so the recorder appends no events. The
    zero-execution guarantee still holds, and that is exactly what this case
    asserts — while reporting the empty stream honestly rather than implying a
    denial was evidenced.
    """
    return _denial_case(
        "neutral.enforce.deny_identity_unknown",
        CapabilityRequest("identity.not.declared", H.READ_CAPABILITY),
        expected_effect="deny",
        expected_code="REQUEST_MALFORMED",
        expected_decision_events=(),
    )


def _case_approval_required() -> CaseResult:
    # The only path in this core that yields APPROVAL_REQUIRED: an external
    # trust-zone crossing with no approval assertion supplied.
    return _denial_case(
        "neutral.enforce.approval_required",
        ZoneCrossingRequest(H.REVIEWER, H.LOCAL_ZONE, H.EXTERNAL_ZONE),
        expected_effect="approval_required",
        expected_code="CROSSING_APPROVAL_REQUIRED",
        expected_decision_events=("approval_requested",),
    )


def _fail_closed_case(
    case_id: str,
    *,
    build: Callable[[Any, Any, Any], tuple[Any, Any, Callable[[Decision], None] | None]],
) -> CaseResult:
    """An internal failure before the action must leave the action un-run."""
    authorizer = H.build_authorizer()
    context = H.build_context(authorizer)
    recorder = H.build_recorder(authorizer, context)
    counter = H.ExecutionCounter()
    used_authorizer, used_recorder, on_decision = build(authorizer, context, recorder)

    problems: list[str] = []
    try:
        enforce(
            used_authorizer,
            CapabilityRequest(H.RESEARCHER, H.READ_CAPABILITY),
            context=context,
            recorder=used_recorder,
            mission_id=H.MISSION_ID,
            action=lambda: counter.run("must not run"),
            on_decision=on_decision,
        )
        problems.append("the injected failure did not propagate")
    except RuntimeError:
        pass
    except Exception as exc:  # noqa: BLE001
        problems.append(f"propagated {type(exc).__name__}, expected RuntimeError")

    if counter.count != 0:
        problems.append(f"action executed {counter.count} times despite an internal failure")
    observations = H.observation_event_types(used_recorder)
    if observations:
        problems.append(f"success observation recorded despite failure: {observations}")

    # Read directly: a getattr fallback to the *expected* value would
    # manufacture agreement between expectation and observation.
    evaluations = used_authorizer.evaluations
    return _result(
        case_id,
        problems=problems,
        executions=counter.count,
        evaluations=evaluations,
        recorder=used_recorder,
    )


def _case_evaluate_error() -> CaseResult:
    return _fail_closed_case(
        "neutral.enforce.evaluate_error",
        build=lambda authorizer, context, recorder: (
            _ExplodingAuthorizer(authorizer),
            recorder,
            None,
        ),
    )


def _case_recorder_error() -> CaseResult:
    def build(authorizer: Any, context: Any, recorder: Any) -> tuple[Any, Any, None]:
        exploding = _ExplodingRecorder(
            authorizer,
            context,
            producer_id=H.PRODUCER_ID,
            producer_type=H.PRODUCER_TYPE,
        )
        return H.CountingAuthorizer(authorizer), exploding, None

    return _fail_closed_case("neutral.enforce.recorder_error", build=build)


def _case_on_decision_error() -> CaseResult:
    def raise_from_hook(_decision: Decision) -> None:
        raise RuntimeError("on_decision failure injected by conformance")

    return _fail_closed_case(
        "neutral.enforce.on_decision_error",
        build=lambda authorizer, context, recorder: (
            H.CountingAuthorizer(authorizer),
            recorder,
            raise_from_hook,
        ),
    )


def _case_action_error() -> CaseResult:
    """The action itself fails: it ran exactly once, and the generic boundary
    invents no framework-specific success on its behalf."""
    authorizer = H.build_authorizer()
    context = H.build_context(authorizer)
    recorder = H.build_recorder(authorizer, context)
    counting = H.CountingAuthorizer(authorizer)
    counter = H.ExecutionCounter()

    problems: list[str] = []
    try:
        enforce(
            counting,
            CapabilityRequest(H.RESEARCHER, H.READ_CAPABILITY),
            context=context,
            recorder=recorder,
            mission_id=H.MISSION_ID,
            action=lambda: counter.run(raises=RuntimeError("action failed")),
        )
        problems.append("the action's failure did not propagate")
    except RuntimeError:
        pass
    except Exception as exc:  # noqa: BLE001
        problems.append(f"propagated {type(exc).__name__}, expected RuntimeError")

    if counter.count != 1:
        problems.append(f"action executed {counter.count} times, expected exactly 1")
    observations = H.observation_event_types(recorder)
    if observations:
        problems.append(f"enforce fabricated an observation after failure: {observations}")

    return _result(
        "neutral.enforce.action_error",
        problems=problems,
        executions=counter.count,
        evaluations=counting.evaluations,
        recorder=recorder,
        expected_effect="allow",
        observed_effect="allow",
        expected_executions=1,
    )


_CASES: tuple[Callable[[], CaseResult], ...] = (
    _case_allow,
    _case_deny,
    _case_deny_capability_unknown,
    _case_deny_identity_unknown,
    _case_approval_required,
    _case_evaluate_error,
    _case_recorder_error,
    _case_on_decision_error,
    _case_action_error,
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
        framework_version=H.nornyx_version(),
        declared_coverage=(),
    )


__all__ = ["FRAMEWORK", "SUITE_ID", "run"]
