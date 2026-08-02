"""Runtime adapter conformance for ``nornyx-agentic-adapters`` (ADR-0043).

Executes the real supported adapter paths under the exact declared framework
versions and emits a deterministic, schema-validated report of what actually
happened::

    python -m nornyx_agentic_adapters.conformance --summary

**Cooperative Tier 2, declared wrapped surfaces only.** A conformance result is
behavior observed under exactly the adapter, framework, Nornyx, SPI, and Python
versions the report names. It does not authenticate agents or approvers, does
not prove a recorded runtime event is true, does not prevent bypass, does not
imply whole-application coverage, and establishes no Tier 3 assurance.

This is distinct from the static ``nornyx.adapter_conformance.v0.7`` report,
which validates declared contract shape with execution disabled. This one
requires execution.

Importing this package imports no agent framework: the CrewAI and LangGraph
suites load only when their extras are present and their suite is selected.
"""

from __future__ import annotations

from .model import (
    ASSURANCE_TIER,
    CONFORMANCE_SCHEMA_ID,
    CONFORMANCE_SCHEMA_VERSION,
    LIMITATIONS,
    NON_GOALS,
    CaseClassification,
    CaseOutcome,
    CaseResult,
    ConformanceReport,
    CountCheck,
    EventOrder,
    EvidenceValidation,
    ExecutionPath,
    OccurrenceSummary,
    RunOutcome,
    RunSafety,
    SuiteOutcome,
    SuiteResult,
)
from .report import load_report_schema, serialize, validate_report, write_report
from .runner import available_suites, run_conformance

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
    "available_suites",
    "load_report_schema",
    "run_conformance",
    "serialize",
    "validate_report",
    "write_report",
]
