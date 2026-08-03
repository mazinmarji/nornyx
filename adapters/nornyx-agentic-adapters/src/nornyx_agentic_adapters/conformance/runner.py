"""Suite discovery and the programmatic conformance runner.

Framework suites are imported lazily. A missing extra yields an ``unavailable``
suite rather than a skip, and an unavailable suite that the caller *required*
fails the run — a silent skip reading as success is exactly how a conformance
gate stops meaning anything.
"""

from __future__ import annotations

from typing import Any, Iterable

from .. import __version__ as ADAPTER_VERSION
from . import harness as H
from .model import (
    CaseOutcome,
    ConformanceReport,
    RunOutcome,
    RunSafety,
    SuiteOutcome,
    SuiteResult,
)
from .suites import distribution, neutral

#: Suite id -> (framework name, importer). Framework suites are imported only
#: when asked for, so the base package keeps importing no agent framework.
_FRAMEWORK_SUITES: dict[str, str] = {"crewai": "crewai_suite", "langgraph": "langgraph_suite"}

ADAPTER_NAME = "nornyx-agentic-adapters"


def available_suites() -> tuple[str, ...]:
    """Every suite id this build can run, in deterministic order."""
    return (distribution.SUITE_ID, neutral.SUITE_ID, *sorted(_FRAMEWORK_SUITES))


def _load_framework_suite(framework: str) -> Any:
    module_name = _FRAMEWORK_SUITES[framework]
    from importlib import import_module

    return import_module(f".suites.{module_name}", package=__package__)


def _unavailable(framework: str, reason: str) -> SuiteResult:
    return SuiteResult(
        suite_id=framework,
        framework=framework,
        outcome=SuiteOutcome.UNAVAILABLE,
        cases=(),
        framework_version=None,
        declared_coverage=(),
        unavailable_reason=reason,
    )


def run_conformance(
    *,
    frameworks: Iterable[str] | None = None,
    case_ids: Iterable[str] | None = None,
    require: Iterable[str] = (),
) -> ConformanceReport:
    """Run the conformance suites and assemble a deterministic report.

    ``frameworks`` selects suites by id (default: every available suite).
    ``case_ids`` narrows to specific cases. ``require`` names frameworks whose
    absence must fail the run rather than pass quietly.
    """
    selected = set(available_suites()) if frameworks is None else set(frameworks)
    unknown = selected - set(available_suites())
    if unknown:
        raise ValueError(
            f"unknown suite(s): {sorted(unknown)}; available: {list(available_suites())}"
        )
    required = set(require)
    unknown_required = required - set(_FRAMEWORK_SUITES)
    if unknown_required:
        raise ValueError(f"unknown required framework(s): {sorted(unknown_required)}")
    # Requiring a framework whose suite was never selected would be a silent
    # no-op — exactly the failure `require` exists to prevent. A CI edit that
    # adds `--suite` must not quietly disarm the gate.
    not_selected = required - selected
    if not_selected:
        raise ValueError(
            f"required framework(s) not selected to run: {sorted(not_selected)}"
        )

    wanted = frozenset(case_ids) if case_ids is not None else None
    suites: list[SuiteResult] = []
    executed_frameworks: list[str] = []

    # Resolve framework suite modules BEFORE the guard is installed. Importing
    # a framework is not a governed action, and some frameworks touch name
    # resolution at import time; guarding the import would misreport an
    # ordinary import as an outbound network attempt.
    loaded: list[tuple[str, Any]] = []
    for framework in sorted(_FRAMEWORK_SUITES):
        if framework not in selected:
            continue
        try:
            loaded.append((framework, _load_framework_suite(framework)))
        except ImportError as exc:
            suites.append(
                _unavailable(
                    framework,
                    f"the {framework!r} extra is not installed ({type(exc).__name__})",
                )
            )
        except Exception as exc:  # noqa: BLE001 - a broken suite is a real result
            suites.append(
                _unavailable(framework, f"the suite failed to load ({type(exc).__name__})")
            )

    # The distribution suite deliberately spawns a clean interpreter to check
    # the import boundary, so it runs outside the guard rather than being given
    # an escape hatch — a permitted child would be entirely unguarded, and a
    # count of attempts blocked in *this* process would say nothing about it.
    if distribution.SUITE_ID in selected:
        suites.append(distribution.run(wanted))

    # One guard around every executing suite, and only one: a nested guard
    # would record attempts into its own counter, so the run-level count could
    # not observe anything that happened inside it.
    guard = H.NetworkGuard()
    guarded: list[str] = []
    with guard.active():
        if neutral.SUITE_ID in selected:
            suites.append(neutral.run(wanted))
            guarded.append(neutral.SUITE_ID)
        for framework, module in loaded:
            suites.append(module.run(wanted))
            executed_frameworks.append(framework)
            guarded.append(framework)

    suites.sort(key=lambda suite: suite.suite_id)
    _validate_case_ids_unique(suites)

    produced = {case.case_id for suite in suites for case in suite.cases}
    if wanted is not None:
        # An unmatched case id must not yield a zero-case report that validates
        # and exits 0 — a typo would read as a passing run of that case. Ids
        # belonging to a suite that is unavailable are exempt: the case exists,
        # its extra does not, and that is already reported as unavailable.
        absent = tuple(
            f"{suite.framework}."
            for suite in suites
            if suite.outcome is SuiteOutcome.UNAVAILABLE
        )
        unmatched = sorted(
            case_id
            for case_id in wanted - produced
            # Unbound str.startswith: a subclass overriding startswith OR
            # __str__ could otherwise suppress this check.
            if not str.startswith(case_id, absent)
        )
        if unmatched:
            raise ValueError(f"no conformance case matches: {unmatched}")
        # Ids exempted because their suite is unavailable are not silently
        # dropped; the caller compares its own selection against the report's
        # cases to surface them. Nothing is stashed in module state to do it.

    failed_cases = any(
        case.outcome is CaseOutcome.FAIL for suite in suites for case in suite.cases
    )
    missing_required = [
        suite.suite_id
        for suite in suites
        if suite.outcome is SuiteOutcome.UNAVAILABLE and suite.framework in required
    ]
    # A run that produced no case verified nothing, so it cannot be a pass.
    # Otherwise selecting a framework whose extra is absent would report
    # `pass` with zero evidence behind it.
    #
    # A blocked outbound attempt fails the run outright. The guard raises into
    # the case that made the call, but a framework executor may swallow that
    # exception (CrewAI's ReAct loop treats a tool error as recoverable), so
    # the raise alone cannot be relied on to surface it. Reporting the count
    # without acting on it would make the observation decorative.
    outcome = (
        RunOutcome.FAIL
        if (failed_cases or missing_required or not produced or guard.attempts)
        else RunOutcome.PASS
    )

    return ConformanceReport(
        adapter_name=ADAPTER_NAME,
        adapter_version=ADAPTER_VERSION,
        nornyx_version=H.nornyx_version(),
        spi_version=H.spi_version(),
        python_version=H.python_version(),
        suites=tuple(suites),
        outcome=outcome,
        safety=RunSafety(
            adapter_actions_executed=True,
            frameworks_executed=tuple(sorted(executed_frameworks)),
            guarded_suites=tuple(guarded),
            blocked_outbound_attempts=guard.outbound_attempts,
            blocked_process_attempts=guard.process_attempts,
        ),
    )


def _validate_case_ids_unique(suites: Iterable[SuiteResult]) -> None:
    """A duplicate case id would let one result stand in for another."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for suite in suites:
        for case in suite.cases:
            if case.case_id in seen:
                duplicates.add(case.case_id)
            seen.add(case.case_id)
    if duplicates:
        raise ValueError(f"duplicate conformance case id(s): {sorted(duplicates)}")


def missing_required(report: ConformanceReport, require: Iterable[str]) -> tuple[str, ...]:
    required = set(require)
    return tuple(
        sorted(
            suite.suite_id
            for suite in report.suites
            if suite.outcome is SuiteOutcome.UNAVAILABLE and suite.framework in required
        )
    )


__all__ = ["ADAPTER_NAME", "available_suites", "missing_required", "run_conformance"]
