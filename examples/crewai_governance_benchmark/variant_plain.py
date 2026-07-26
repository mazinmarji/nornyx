"""Variant A — the same application with no Nornyx governance.

Ordinary CrewAI: real ``Agent``, ``Task``, ``Crew``, ``BaseTool``, and a real
``Crew.kickoff()``. Every application-level control the app would normally have
is kept (see ``business.py``); the *only* thing missing is the external,
revision-bound Nornyx authorization and evidence layer.

Nothing here is weakened to flatter the governed variant. Where the baseline
executes a prohibited action, it does so for the ordinary reason: the tool was
attached to the agent, and nothing else was asked.
"""

from __future__ import annotations

from typing import Any

from crewai_governance_benchmark import config  # noqa: F401  (telemetry kill-switch side effect)
from crewai_governance_benchmark.ledger import BusinessTool, Ledger
from crewai_governance_benchmark.runtime import FALLBACK_ANSWER, kickoff_single_task, plain_tool
from crewai_governance_benchmark.scenarios import LOAD, SCENARIOS, Scenario, work_callable

EXPECTED_OUTPUT = "The result of the requested remediation step."


def _run_scenario(scenario: Scenario, ledger: Ledger) -> dict[str, Any]:
    """Run one scenario with no governance at all."""
    if scenario.stage == LOAD:
        # A contract/lock drift check has no counterpart in an ungoverned app:
        # there is no contract to drift from. Reported, never silently dropped.
        return {
            "scenario": scenario.id,
            "outcome": "not_applicable",
            "business_output": None,
            "crew_output": None,
            "note": (
                "No contract exists in the baseline, so there is no lock to verify. "
                "Reported as not applicable rather than as a pass."
            ),
            **ledger.snapshot(scenario.id),
        }

    tool_impl = BusinessTool(
        name=scenario.tool,
        describe=scenario.tool_description,
        work=work_callable(scenario),
        ledger=ledger,
    ).bind(scenario.id)

    crew_output = kickoff_single_task(
        role=scenario.role,
        tool=plain_tool(scenario.tool, scenario.tool_description, tool_impl.run),
        description=scenario.task,
        expected_output=EXPECTED_OUTPUT,
        final_answer=(
            FALLBACK_ANSWER
            if scenario.expected_baseline_side_effects == 0
            else "Completed the requested remediation step."
        ),
    )

    outputs = ledger.outputs(scenario.id)
    if outputs:
        outcome, note = "executed", "No governance layer was consulted."
    elif ledger.failures(scenario.id):
        outcome = "refused_by_application"
        note = (
            "The application's own validation refused the work. This is the app's "
            "control, present identically in both variants."
        )
    else:
        outcome, note = "not_executed", "The business callable was never entered."

    return {
        "scenario": scenario.id,
        "outcome": outcome,
        "business_output": outputs[0] if outputs else None,
        "crew_output": crew_output,
        "note": note,
        **ledger.snapshot(scenario.id),
    }


def run(only: tuple[str, ...] | None = None) -> tuple[dict[str, dict[str, Any]], Ledger]:
    """Run every scenario in the ungoverned variant (or just ``only``)."""
    ledger = Ledger()
    selected = [s for s in SCENARIOS if only is None or s.id in only]
    results = {s.id: _run_scenario(s, ledger) for s in selected}
    return results, ledger
