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

    # One guard around every executing suite, so `network_used` is derived from
    # an observation rather than declared. Any outbound attempt is blocked,
    # raises into the case that made it, and is counted here.
    guard = H.NetworkGuard()
    with guard.active():
        if distribution.SUITE_ID in selected:
            suites.append(distribution.run(wanted))
        if neutral.SUITE_ID in selected:
            suites.append(neutral.run(wanted))
        for framework, module in loaded:
            suites.append(module.run(wanted))
            executed_frameworks.append(framework)

    suites.sort(key=lambda suite: suite.suite_id)
    _validate_case_ids_unique(suites)

    produced = {case.case_id for suite in suites for case in suite.cases}
    if wanted is not None:
        # An unmatched case id must not yield a zero-case report that validates
        # and exits 0 — a typo would read as a passing run of that case.
        unmatched = sorted(wanted - produced)
        if unmatched:
            raise ValueError(f"no conformance case matches: {unmatched}")
    if not produced and any(
        suite.outcome is not SuiteOutcome.UNAVAILABLE for suite in suites
    ):
        raise ValueError("the selection produced no conformance cases")

    failed_cases = any(
        case.outcome is CaseOutcome.FAIL for suite in suites for case in suite.cases
    )
    missing_required = [
        suite.suite_id
        for suite in suites
        if suite.outcome is SuiteOutcome.UNAVAILABLE and suite.framework in required
    ]
    outcome = (
        RunOutcome.FAIL if (failed_cases or missing_required) else RunOutcome.PASS
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
            network_guard_active=True,
            network_used=guard.attempts > 0,
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
