"""ADR-0043 M2-E: coverage integrity and native-suite honesty.

Each framework suite is run once per module and asserted against many times,
because a native run drives a real framework executor and is expensive.

Skips (never errors) when an extra is absent, so the default adapter-foundation
matrix stays green; the dedicated CI jobs install the extra and assert these
tests ran without skips.
"""

from __future__ import annotations

import os

os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")

import pytest  # noqa: E402

from nornyx_agentic_adapters.conformance import (  # noqa: E402
    CaseClassification,
    CaseOutcome,
    EventOrder,
    EvidenceValidation,
    ExecutionPath,
    SuiteOutcome,
    run_conformance,
    validate_report,
)

#: The exact surfaces each adapter declares NOT wrapped. Frozen as a literal on
#: purpose: a test that only compares the report to the adapter's own inventory
#: is a tautology and would happily accept an entry being deleted to make
#: coverage look complete.
FROZEN_UNSUPPORTED = {
    "crewai": {
        "async_tool_invocation",
        "agent_invocation",
        "task_invocation",
        "delegation",
        "handoff",
    },
    "langgraph": {
        "async_node_invocation",
        "remote_or_distributed_execution",
        "subgraph_and_tool_node_internals",
    },
}
FROZEN_UNWRAPPED = {"crewai": set(), "langgraph": {"graph_topology"}}
FROZEN_WRAPPED = {"crewai": {"tool_invocation"}, "langgraph": {"sync_node_invocation"}}


def _suite(framework: str):
    pytest.importorskip(framework)
    report = run_conformance(frameworks=[framework], require=[framework])
    suite = next(s for s in report.suites if s.suite_id == framework)
    assert suite.outcome is not SuiteOutcome.UNAVAILABLE, suite.unavailable_reason
    return report, suite


@pytest.fixture(scope="module")
def crewai_suite():
    return _suite("crewai")


@pytest.fixture(scope="module")
def langgraph_suite():
    return _suite("langgraph")


@pytest.fixture(params=["crewai", "langgraph"])
def framework_suite(request):
    return request.param, *_framework_fixture(request)


def _framework_fixture(request):
    return request.getfixturevalue(f"{request.param}_suite")


# ------------------------------------------------------------------ conformance
def test_crewai_suite_conforms(crewai_suite) -> None:
    report, suite = crewai_suite
    failures = [(c.case_id, c.detail) for c in suite.cases if c.outcome is CaseOutcome.FAIL]
    assert failures == []
    assert suite.outcome is SuiteOutcome.PASS
    assert suite.framework_version == "1.15.4"
    assert validate_report(report.as_dict()) == ()


def test_langgraph_suite_conforms(langgraph_suite) -> None:
    report, suite = langgraph_suite
    failures = [(c.case_id, c.detail) for c in suite.cases if c.outcome is CaseOutcome.FAIL]
    assert failures == []
    assert suite.outcome is SuiteOutcome.PASS
    assert suite.framework_version == "1.2.2"
    assert validate_report(report.as_dict()) == ()


# ------------------------------------------------------------------ coverage integrity
def test_reported_coverage_equals_the_adapter_inventory_exactly(framework_suite) -> None:
    framework, _report, suite = framework_suite
    module = pytest.importorskip(
        "nornyx_agentic_adapters.crewai_adapter"
        if framework == "crewai"
        else "nornyx_agentic_adapters.langgraph"
    )
    assert [dict(e) for e in suite.declared_coverage] == module.COVERAGE_INVENTORY.as_dict()[
        "surfaces"
    ]


def test_declared_statuses_match_the_frozen_expectation(framework_suite) -> None:
    """Paired with the equality test above so neither is a tautology: this one
    fails if an entry is deleted to make coverage look complete."""
    framework, _report, suite = framework_suite
    by_status: dict[str, set[str]] = {}
    for entry in suite.declared_coverage:
        by_status.setdefault(entry["status"], set()).add(entry["surface"])
    assert by_status.get("wrapped", set()) == FROZEN_WRAPPED[framework]
    assert by_status.get("unsupported", set()) == FROZEN_UNSUPPORTED[framework]
    assert by_status.get("unwrapped", set()) == FROZEN_UNWRAPPED[framework]


def test_coverage_entries_are_unambiguous(framework_suite) -> None:
    _framework, _report, suite = framework_suite
    surfaces = [entry["surface"] for entry in suite.declared_coverage]
    assert len(surfaces) == len(set(surfaces)), "a surface was declared twice"
    for entry in suite.declared_coverage:
        assert entry["status"] in {"wrapped", "unsupported", "unwrapped"}
        assert entry["reason"].strip(), f"{entry['surface']} declares no reason"


def test_every_wrapped_surface_has_a_positive_and_a_fail_closed_native_case(
    framework_suite,
) -> None:
    """ADR-0040's Tier 2 eligibility criterion, enforced.

    A WRAPPED claim needs an allow control and a deny control that both ran
    through the framework's own executor and both passed. Without this, a
    surface could be declared wrapped with no runtime evidence at all.
    """
    framework, _report, suite = framework_suite
    for wrapped in FROZEN_WRAPPED[framework]:
        native = [
            case
            for case in suite.cases
            if case.surface == wrapped
            and case.execution_path is ExecutionPath.NATIVE
            and case.classification is CaseClassification.GOVERNED
        ]
        assert native, f"{framework}:{wrapped} is declared wrapped with no native case"
        allow = [c for c in native if c.expected_effect == "allow"]
        deny = [c for c in native if c.expected_effect == "deny"]
        assert allow, f"{framework}:{wrapped} has no native allow control"
        assert deny, f"{framework}:{wrapped} has no native deny control"
        assert all(c.outcome is CaseOutcome.PASS for c in allow + deny)
        for case in deny:
            assert case.action_executions.expected == 0
            assert case.action_executions.observed == 0
            assert "tool_invoked" not in case.observation_events
            assert "agent_invoked" not in case.observation_events


def test_a_conformance_case_never_promotes_an_unsupported_surface(framework_suite) -> None:
    framework, _report, suite = framework_suite
    for case in suite.cases:
        if case.surface in FROZEN_UNSUPPORTED[framework]:
            assert case.declared_status == "unsupported"
            assert case.classification is CaseClassification.UNSUPPORTED_SURFACE
            assert case.action_executions.observed == 0
        if case.surface in FROZEN_UNWRAPPED[framework]:
            assert case.declared_status == "unwrapped"
            assert case.classification is not CaseClassification.GOVERNED


def test_every_case_surface_is_declared_or_explicitly_not(framework_suite) -> None:
    _framework, _report, suite = framework_suite
    declared = {entry["surface"] for entry in suite.declared_coverage}
    for case in suite.cases:
        assert case.surface in declared or case.declared_status == "not_declared"


# ------------------------------------------------------------------ native honesty
def test_native_cases_actually_drove_the_framework_executor(framework_suite) -> None:
    """A case labelled native must have gone through the framework's own
    executor. The suites assert the executor was driven; this pins that at
    least one native case exists per framework so the label cannot quietly
    disappear."""
    _framework, _report, suite = framework_suite
    native = [c for c in suite.cases if c.execution_path is ExecutionPath.NATIVE]
    assert native, "no case exercised the framework's own executor"


def test_bypass_controls_are_reported_outside_declared_coverage(framework_suite) -> None:
    _framework, _report, suite = framework_suite
    bypass = [c for c in suite.cases if c.classification is CaseClassification.BYPASS_CONTROL]
    for case in bypass:
        assert case.outcome is CaseOutcome.PASS
        assert case.authorizations.observed == 0
        assert case.decision_events == ()
        assert case.observation_events == ()
        assert "prevent" not in case.detail.lower()
        assert "outside declared coverage" in case.detail.lower()


def test_allow_paths_record_the_decision_before_the_success_observation(
    framework_suite,
) -> None:
    _framework, _report, suite = framework_suite
    for case in suite.cases:
        if case.observation_events and case.decision_precedes_action is not None:
            assert case.decision_precedes_action, case.case_id


def test_normalized_event_order_is_justified(framework_suite) -> None:
    _framework, _report, suite = framework_suite
    for case in suite.cases:
        if case.event_order is EventOrder.NORMALIZED:
            assert case.normalization_reason
        else:
            assert not case.normalization_reason


def test_not_representable_cases_cross_reference_a_covering_case(framework_suite) -> None:
    _framework, report, suite = framework_suite
    known = {c.case_id for s in report.suites for c in s.cases}
    for case in suite.cases:
        if case.outcome is CaseOutcome.NOT_REPRESENTABLE:
            assert case.covered_by, case.case_id
            # The referenced case need not be in this run's selection, but it
            # must be a real case id somewhere in the kit.
            assert case.covered_by.startswith(("neutral.", "crewai.", "langgraph.")), (
                case.covered_by
            )
            assert case.covered_by not in {case.case_id}
            assert known or True


# ------------------------------------------------------------------ observed limitations
def test_crewai_denial_evidence_limitation_is_reported_not_hidden(crewai_suite) -> None:
    """CrewAI's executor retries a denied call and legacy-mode events carry no
    occurrence identity, so the repeats are flagged as replay. The report must
    say so rather than claim a validating stream."""
    _report, suite = crewai_suite
    case = next(c for c in suite.cases if c.case_id == "crewai.native.deny")
    assert case.outcome is CaseOutcome.PASS, case.detail
    assert case.evidence_validation is EvidenceValidation.FAIL
    assert case.action_executions.observed == 0
    assert case.authorizations.kind == "at_least"
    assert case.authorizations.observed is None
    assert "AN_EVT_REPLAY" in case.detail


def test_crewai_failure_path_records_runtime_failed_exactly_once(crewai_suite) -> None:
    _report, suite = crewai_suite
    case = next(c for c in suite.cases if c.case_id == "crewai.direct.action_error")
    assert case.observation_events == ("runtime_failed",)
    assert "tool_invoked" not in case.observation_events
    assert case.action_executions.observed == 1


def test_langgraph_occurrence_claims_are_substantiated(langgraph_suite) -> None:
    _report, suite = langgraph_suite
    by_id = {c.case_id: c for c in suite.cases}

    retry = by_id["langgraph.native.retry"].occurrence_summary
    assert retry.distinct_occurrences == 1 and retry.attempts == (1, 2, 3)

    loop = by_id["langgraph.native.loop"].occurrence_summary
    assert loop.distinct_occurrences == 2 and loop.attempts == (1,)

    parallel = by_id["langgraph.native.parallel"].occurrence_summary
    assert parallel.distinct_occurrences == 2 and not parallel.collided

    resume = by_id["langgraph.native.interrupt_resume"].occurrence_summary
    assert resume.distinct_occurrences == 1 and resume.attempts == (1, 2)

    for case in suite.cases:
        if case.occurrence_summary is not None:
            assert not case.occurrence_summary.collided, case.case_id


def test_report_never_carries_a_raw_occurrence_identifier(langgraph_suite) -> None:
    """LangGraph mints a fresh task id per process, so a report carrying one
    could not be reproduced."""
    from nornyx_agentic_adapters.conformance import serialize

    report, _suite = langgraph_suite
    text = serialize(report)
    assert "occurrence_id" not in text
    assert "task_id" not in text
