"""Installation and distribution boundary conformance.

These cases substantiate the premise every other suite depends on: that the
kit is running from an installed distribution, resolving its own resources,
and importing no agent framework it was not asked to. A conformance result
measured against a source checkout would say nothing to a consumer.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any, Callable

from ... import __version__ as ADAPTER_VERSION
from .. import harness as H
from ..model import (
    CaseClassification,
    CaseOutcome,
    CaseResult,
    CountCheck,
    EvidenceValidation,
    ExecutionPath,
    SuiteOutcome,
    SuiteResult,
)
from ..report import load_report_schema

SUITE_ID = "distribution"
FRAMEWORK = "none"
_DETAIL_LIMIT = 240

_BASE_IMPORT_PROBE = (
    "import sys\n"
    "import nornyx_agentic_adapters\n"
    "import nornyx_agentic_adapters.conformance as c\n"
    "leaked = sorted(m for m in sys.modules if m.split('.')[0] in ('crewai', 'langgraph'))\n"
    "print('LEAKED=' + ','.join(leaked))\n"
    "print('VERSION=' + nornyx_agentic_adapters.__version__)\n"
)


def _result(
    case_id: str,
    *,
    problems: list[str],
    note: str = "",
) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        framework=FRAMEWORK,
        surface="distribution",
        declared_status="not_declared",
        classification=CaseClassification.DISTRIBUTION_BOUNDARY,
        outcome=CaseOutcome.FAIL if problems else CaseOutcome.PASS,
        execution_path=ExecutionPath.BOUNDARY,
        action_executions=CountCheck("exact", 0, 0),
        authorizations=CountCheck("exact", 0, 0),
        evidence_validation=EvidenceValidation.NOT_APPLICABLE,
        detail=" ".join(("; ".join(problems) if problems else note).split())[:_DETAIL_LIMIT],
    )


def _case_fixture_resource() -> CaseResult:
    """The contract fixture resolves through package resources, not a path."""
    problems: list[str] = []
    try:
        text = H.fixture_text()
    except Exception as exc:  # noqa: BLE001
        return _result(
            "distribution.fixture_resource_loads",
            problems=[f"the bundled fixture could not be read: {type(exc).__name__}"],
        )
    if "agentic_network" not in text:
        problems.append("the bundled fixture is not an agentic-network contract")
    try:
        document = H.load_document()
    except Exception as exc:  # noqa: BLE001
        problems.append(f"the bundled fixture did not parse: {type(exc).__name__}")
        document = {}
    frameworks = {
        binding.get("framework")
        for identity in document.get("agent_identities", [])
        for binding in identity.get("framework_bindings", [])
    }
    for required in ("crewai", "langgraph"):
        if required not in frameworks:
            problems.append(f"the fixture declares no {required} framework binding")
    return _result(
        "distribution.fixture_resource_loads",
        problems=problems,
        note="The contract fixture loaded from package resources, not a repository path.",
    )


def _case_schema_resource() -> CaseResult:
    """The bundled report schema loads and is closed at every object level."""
    problems: list[str] = []
    try:
        schema = load_report_schema()
    except Exception as exc:  # noqa: BLE001
        return _result(
            "distribution.schema_resource_is_closed",
            problems=[f"the bundled schema could not be read: {type(exc).__name__}"],
        )

    def walk(node: Any, pointer: str) -> None:
        if isinstance(node, dict):
            # Only subschemas that actually *define* an object shape must close
            # additionalProperties. Conditional applicators (`if`/`then`/`else`)
            # list properties to match against without declaring a type, and
            # closing them would change what they mean rather than tighten it.
            defines_object = node.get("type") == "object" and "properties" in node
            if defines_object and node.get("additionalProperties") is not False:
                problems.append(f"{pointer or '<root>'} does not close additionalProperties")
            for key, value in node.items():
                walk(value, f"{pointer}/{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{pointer}/{index}")

    walk(schema, "")
    if schema.get("$id") != "nornyx.agentic_runtime_conformance.v1":
        problems.append("the bundled schema does not declare the runtime-conformance id")
    return _result(
        "distribution.schema_resource_is_closed",
        problems=problems,
        note=(
            "The bundled report schema loaded from package resources and closes "
            "additionalProperties at every object level."
        ),
    )


def _case_base_import_is_framework_free() -> CaseResult:
    """Importing the base package and the kit pulls in no agent framework.

    Checked in a fresh interpreter, because this process may legitimately have
    imported a framework already for the framework suites.
    """
    problems: list[str] = []
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, same interpreter
            [sys.executable, "-c", _BASE_IMPORT_PROBE],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception as exc:  # noqa: BLE001
        return _result(
            "distribution.base_import_is_framework_free",
            problems=[f"the import probe could not run: {type(exc).__name__}"],
        )
    if completed.returncode != 0:
        return _result(
            "distribution.base_import_is_framework_free",
            problems=[f"the import probe exited {completed.returncode}"],
        )
    leaked = ""
    version = ""
    for line in completed.stdout.splitlines():
        if line.startswith("LEAKED="):
            leaked = line.removeprefix("LEAKED=").strip()
        elif line.startswith("VERSION="):
            version = line.removeprefix("VERSION=").strip()
    if leaked:
        problems.append(f"importing the base package pulled in: {leaked}")
    if version != ADAPTER_VERSION:
        problems.append(f"probe imported adapter {version!r}, expected {ADAPTER_VERSION!r}")
    return _result(
        "distribution.base_import_is_framework_free",
        problems=problems,
        note=(
            "A fresh interpreter importing the base package and the conformance "
            "kit loaded neither crewai nor langgraph."
        ),
    )


_CASES: tuple[Callable[[], CaseResult], ...] = (
    _case_fixture_resource,
    _case_schema_resource,
    _case_base_import_is_framework_free,
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
        framework_version=ADAPTER_VERSION,
        declared_coverage=(),
    )


__all__ = ["FRAMEWORK", "SUITE_ID", "run"]
