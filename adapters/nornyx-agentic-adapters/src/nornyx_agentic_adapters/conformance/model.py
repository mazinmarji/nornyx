"""The typed, deterministic result model for runtime adapter conformance.

Every value here is chosen so the serialized report is byte-identical across
repeated runs on one platform. Two framework behaviors make that non-trivial
and are handled explicitly rather than papered over:

* LangGraph mints a fresh ``task_id`` per process, so raw occurrence ids are
  never carried into a result — only the determinism-safe facts derived from
  them (:class:`OccurrenceSummary`).
* CrewAI's native executor may retry a failed tool call internally, so the
  number of authorization evaluations on that path is framework-controlled.
  :class:`CountCheck` records which kind of assertion was actually made, and
  omits an observed value it cannot promise to reproduce.

Nothing in this module claims a recorded event is true. It records what was
observed at a declared boundary, under exactly the versions the report names.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

CONFORMANCE_SCHEMA_ID = "nornyx.agentic_runtime_conformance.v1"
CONFORMANCE_SCHEMA_VERSION = "1.0"

#: ADR-0040 assurance tier. This kit never establishes any other tier.
ASSURANCE_TIER = "tier_2_cooperative"

#: Stated on every report. Deliberately phrased as limits, not reassurances.
LIMITATIONS: tuple[str, ...] = (
    "Cooperative Tier 2, declared wrapped surfaces only.",
    "Conformance is behavior observed under exactly the adapter, framework, "
    "Nornyx, SPI, and Python versions named in this report.",
    "Conformance does not authenticate agents or approvers.",
    "Conformance does not prove that a recorded runtime event is true; it "
    "establishes only whether the event stream is schema-valid and consistently "
    "bound. See each case's evidence_validation.",
    "Conformance does not prevent bypass. Bypassing an adapter bypasses "
    "enforcement; bypass is reported as a negative control outside declared "
    "coverage, never as a prevented path.",
    "Conformance does not imply whole-application coverage.",
    "Conformance enables no live connector, network, model, or external "
    "execution.",
    "Conformance establishes no Tier 3 independent runtime assurance.",
)

#: What this report is explicitly not.
NON_GOALS: tuple[str, ...] = (
    "Not an attestation of runtime truth.",
    "Not a security guarantee.",
    "Not a statement about any surface the adapter declares unsupported or "
    "unwrapped.",
    "Not a statement about any framework version other than the one named.",
)


class CaseClassification(Enum):
    """What kind of claim a single conformance case is making."""

    #: A declared WRAPPED surface exercised through its real supported path.
    GOVERNED = "governed"
    #: A declared UNSUPPORTED/UNWRAPPED surface, exercised only to show it
    #: fails closed. Passing here never promotes the surface to wrapped.
    UNSUPPORTED_SURFACE = "unsupported_surface"
    #: A deliberate bypass of the adapter, proving Tier 2 bypassability.
    BYPASS_CONTROL = "bypass_control"
    #: An installation, import, or packaging boundary rather than a runtime
    #: authorization path.
    DISTRIBUTION_BOUNDARY = "distribution_boundary"


class CaseOutcome(Enum):
    PASS = "pass"
    FAIL = "fail"
    #: The case cannot exist on this surface at all — not a skip, not a pass.
    #: Used where a supported surface structurally cannot reach a decision
    #: outcome (see ``covered_by`` for where the behavior *is* proven).
    NOT_REPRESENTABLE = "not_representable"


class RunOutcome(Enum):
    """Whole-run outcome. Distinct from :class:`CaseOutcome`: a run is only
    ever conformant or not."""

    PASS = "pass"
    FAIL = "fail"


class ExecutionPath(Enum):
    """How the case reached the adapter — the difference between exercising a
    framework's own executor and calling the wrapper directly."""

    #: Driven through the framework's real executor (``Crew.kickoff()``,
    #: ``graph.invoke()``). The only path that can substantiate a native claim.
    NATIVE = "native"
    #: The adapter's public wrapper invoked directly, without the framework
    #: executor in the loop.
    DIRECT = "direct"
    #: No framework involved — the framework-neutral boundary, or a
    #: packaging/import boundary.
    BOUNDARY = "boundary"


class EventOrder(Enum):
    #: Event lists are in exactly the order the adapter's recorder committed
    #: them. The default, and required for any ordering claim.
    RECORDED = "recorded"
    #: Sorted and de-duplicated because a framework executor — not the
    #: adapter — controls how many times the governed call repeats. Used only
    #: where a raw order would make the report non-reproducible.
    NORMALIZED = "normalized"


class SuiteOutcome(Enum):
    PASS = "pass"
    FAIL = "fail"
    #: The suite's framework extra is not installed. Distinct from PASS so a
    #: CI job that requires the extra can fail on it rather than read a silent
    #: skip as success.
    UNAVAILABLE = "unavailable"


class EvidenceValidation(Enum):
    PASS = "pass"
    FAIL = "fail"
    #: The case records no runtime evidence (for example a pure import
    #: boundary), so there is nothing to validate.
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class CountCheck:
    """One counted observation and the assertion actually made about it.

    ``kind`` is ``"exact"`` when the count is fully adapter-controlled and
    reproducible, or ``"at_least"`` when a framework's own executor controls
    repetition. For ``"at_least"``, ``observed`` is ``None`` and ``reason``
    states why: reporting a framework-controlled number as though it were a
    stable adapter guarantee would overstate the claim.
    """

    kind: str
    expected: int
    observed: int | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.kind not in ("exact", "at_least"):
            raise ValueError(f"CountCheck.kind must be 'exact' or 'at_least'; got {self.kind!r}")
        if not isinstance(self.expected, int) or isinstance(self.expected, bool) or self.expected < 0:
            raise ValueError("CountCheck.expected must be a non-negative int")
        if self.kind == "exact":
            if self.observed is None:
                raise ValueError("an 'exact' CountCheck must record its observed value")
            if self.reason:
                raise ValueError("an 'exact' CountCheck states no omission reason")
        else:
            if self.observed is not None:
                raise ValueError(
                    "an 'at_least' CountCheck omits the observed value; it is "
                    "framework-controlled and not reproducible"
                )
            if not self.reason:
                raise ValueError("an 'at_least' CountCheck must state why the value is omitted")

    @property
    def satisfied(self) -> bool:
        if self.kind == "exact":
            return self.observed == self.expected
        return True

    def as_dict(self) -> dict:
        payload: dict = {"kind": self.kind, "expected": self.expected}
        if self.kind == "exact":
            payload["observed"] = self.observed
        else:
            payload["reason"] = self.reason
        return payload


@dataclass(frozen=True)
class OccurrenceSummary:
    """Determinism-safe facts about an occurrence-aware evidence stream.

    Deliberately excludes the raw occurrence ids: LangGraph mints a new
    ``task_id`` per process, so the ids themselves are not reproducible even
    though the structure they produce is.
    """

    distinct_occurrences: int
    attempts: tuple[int, ...]
    collided: bool

    def as_dict(self) -> dict:
        return {
            "distinct_occurrences": self.distinct_occurrences,
            "attempts": list(self.attempts),
            "collided": self.collided,
        }


@dataclass(frozen=True)
class CaseResult:
    """The observed result of one conformance case.

    ``declared_status`` is read from the adapter's own exported
    ``CoverageInventory`` — never restated by the case — so a case can never
    quietly upgrade a surface it exercises.
    """

    case_id: str
    framework: str
    surface: str
    declared_status: str
    classification: CaseClassification
    outcome: CaseOutcome
    action_executions: CountCheck
    authorizations: CountCheck
    execution_path: ExecutionPath = ExecutionPath.BOUNDARY
    decision_events: tuple[str, ...] = ()
    observation_events: tuple[str, ...] = ()
    event_order: EventOrder = EventOrder.RECORDED
    normalization_reason: str = ""
    expected_effect: str | None = None
    observed_effect: str | None = None
    expected_code: str | None = None
    observed_code: str | None = None
    decision_precedes_observation: bool | None = None
    evidence_validation: EvidenceValidation = EvidenceValidation.NOT_APPLICABLE
    evidence_diagnostics: tuple[str, ...] = ()
    occurrence_summary: OccurrenceSummary | None = None
    covered_by: str | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        if self.event_order is EventOrder.NORMALIZED and not self.normalization_reason:
            raise ValueError(
                "a normalized event order must state why the recorded order is "
                "not reproducible"
            )
        if self.event_order is EventOrder.RECORDED and self.normalization_reason:
            raise ValueError("a recorded event order states no normalization reason")
        if self.outcome is CaseOutcome.NOT_REPRESENTABLE and not self.covered_by:
            raise ValueError(
                "a not-representable case must name the case that does prove "
                "the behavior, so the gap is cross-referenced rather than hidden"
            )

    def as_dict(self) -> dict:
        payload: dict = {
            "case_id": self.case_id,
            "framework": self.framework,
            "surface": self.surface,
            "declared_status": self.declared_status,
            "classification": self.classification.value,
            "outcome": self.outcome.value,
            "execution_path": self.execution_path.value,
            "action_executions": self.action_executions.as_dict(),
            "authorizations": self.authorizations.as_dict(),
            "decision_events": list(self.decision_events),
            "observation_events": list(self.observation_events),
            "event_order": self.event_order.value,
            "evidence_validation": self.evidence_validation.value,
            "evidence_diagnostics": list(self.evidence_diagnostics),
            "detail": self.detail,
        }
        if self.event_order is EventOrder.NORMALIZED:
            payload["normalization_reason"] = self.normalization_reason
        for key, value in (
            ("expected_effect", self.expected_effect),
            ("observed_effect", self.observed_effect),
            ("expected_code", self.expected_code),
            ("observed_code", self.observed_code),
            ("covered_by", self.covered_by),
        ):
            if value is not None:
                payload[key] = value
        if self.decision_precedes_observation is not None:
            payload["decision_precedes_observation"] = self.decision_precedes_observation
        if self.occurrence_summary is not None:
            payload["occurrence_summary"] = self.occurrence_summary.as_dict()
        return payload


@dataclass(frozen=True)
class SuiteResult:
    """One framework's (or the neutral boundary's) conformance results.

    ``declared_coverage`` is the adapter's exported inventory verbatim. The
    report states declared coverage and observed behavior side by side rather
    than merging them, so a reader can always tell a claim from an observation.
    """

    suite_id: str
    framework: str
    outcome: SuiteOutcome
    cases: tuple[CaseResult, ...] = ()
    framework_version: str | None = None
    declared_coverage: tuple[dict, ...] = ()
    unavailable_reason: str = ""

    def as_dict(self) -> dict:
        payload: dict = {
            "suite_id": self.suite_id,
            "framework": self.framework,
            "outcome": self.outcome.value,
            "declared_coverage": [dict(entry) for entry in self.declared_coverage],
            "cases": [case.as_dict() for case in self.cases],
        }
        if self.framework_version is not None:
            payload["framework_version"] = self.framework_version
        if self.outcome is SuiteOutcome.UNAVAILABLE:
            payload["unavailable_reason"] = self.unavailable_reason
        return payload


@dataclass(frozen=True)
class RunSafety:
    """What this conformance run actually did.

    Deliberately *not* the core evidence validator's ``safety`` block. That one
    describes the validator, which executes nothing. This kit really does
    invoke governed actions and really does drive framework executors, so
    copying the validator's block would assert ``tools_executed: false``
    immediately after executing a tool. Stating it separately, and truthfully,
    is the point.
    """

    adapter_actions_executed: bool
    frameworks_executed: tuple[str, ...]
    #: Which suites actually ran under the outbound guard. Named rather than a
    #: bare boolean so a reader can tell exactly what was covered.
    guarded_suites: tuple[str, ...] = ()
    #: Observed count of outbound calls the guard blocked. Reported as what it
    #: is. A blocked attempt means the network was *not* reached, so this is
    #: deliberately not restated as a "network was used" flag.
    blocked_outbound_attempts: int = 0
    #: No *external* model is called. The framework suites do drive a scripted,
    #: offline, in-process LLM, which is what makes a native run deterministic;
    #: nothing leaves the process.
    models_called: bool = False
    #: Structural properties of the kit's design, not measurements: it executes
    #: no connector and loads no credentials.
    external_connectors_used: bool = False
    credentials_loaded: bool = False

    def as_dict(self) -> dict:
        return {
            "adapter_actions_executed": self.adapter_actions_executed,
            "frameworks_executed": list(self.frameworks_executed),
            "guarded_suites": list(self.guarded_suites),
            "blocked_outbound_attempts": self.blocked_outbound_attempts,
            "models_called": self.models_called,
            "external_connectors_used": self.external_connectors_used,
            "credentials_loaded": self.credentials_loaded,
        }


@dataclass(frozen=True)
class ConformanceReport:
    """The complete, deterministic runtime adapter-conformance report."""

    adapter_name: str
    adapter_version: str
    nornyx_version: str
    spi_version: str
    python_version: str
    suites: tuple[SuiteResult, ...]
    outcome: RunOutcome
    safety: RunSafety
    schema: str = CONFORMANCE_SCHEMA_ID
    schema_version: str = CONFORMANCE_SCHEMA_VERSION
    assurance_tier: str = ASSURANCE_TIER
    limitations: tuple[str, ...] = LIMITATIONS
    non_goals: tuple[str, ...] = NON_GOALS

    def as_dict(self) -> dict:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "nornyx_version": self.nornyx_version,
            "spi_version": self.spi_version,
            "python_version": self.python_version,
            "assurance_tier": self.assurance_tier,
            "outcome": self.outcome.value,
            "safety": self.safety.as_dict(),
            "suites": [suite.as_dict() for suite in self.suites],
            "limitations": list(self.limitations),
            "non_goals": list(self.non_goals),
        }

    def cases(self) -> tuple[CaseResult, ...]:
        return tuple(case for suite in self.suites for case in suite.cases)

    def failures(self) -> tuple[CaseResult, ...]:
        return tuple(
            case for case in self.cases() if case.outcome is CaseOutcome.FAIL
        )


__all__ = [
    "ASSURANCE_TIER",
    "CONFORMANCE_SCHEMA_ID",
    "CONFORMANCE_SCHEMA_VERSION",
    "LIMITATIONS",
    "NON_GOALS",
    "CaseClassification",
    "CaseOutcome",
    "CaseResult",
    "ConformanceReport",
    "CountCheck",
    "EventOrder",
    "EvidenceValidation",
    "ExecutionPath",
    "OccurrenceSummary",
    "RunOutcome",
    "RunSafety",
    "SuiteOutcome",
    "SuiteResult",
]
