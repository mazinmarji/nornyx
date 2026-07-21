"""Variant A: ordinary CrewAI with no Nornyx.

A normal CrewAI application: no Nornyx imports, no contract, no lock, no adapter,
no runtime evidence, and no independent governance engine standing in for Nornyx.
The only application-level logic is the kind any functional support app would
contain (a naive "is it approved?" boolean), which is exactly what makes the
AI-approval gap visible.

Every runtime scenario builds the same ``Agent``/``Task``/business tool and runs
a genuine ``Crew.kickoff()`` — the identical topology the governed variant uses.
When a tool is attached, CrewAI executes it; nothing consults a capability
contract first. A shared side-effect ledger records whether the business
callable actually ran.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import common  # noqa: E402
from common import CLASSIFICATION  # noqa: E402
from crew_runtime import build_agent, kickoff_single_task  # noqa: E402
from scenarios import RUNTIME  # noqa: E402
from tools import SideEffectLedger, make_work  # noqa: E402


class PlainSupportNetwork:
    """The ungoverned CrewAI baseline."""

    def __init__(self, ledger: SideEffectLedger | None = None) -> None:
        self.ledger = ledger or SideEffectLedger()
        self.allowed_outputs: dict[str, str] = {}

    # ---- one runtime scenario: same Agent/Task/tool/kickoff as the governed run
    def _runtime(self, sid: str) -> dict:
        spec = RUNTIME[sid]
        agent = build_agent(spec["role"], spec["tool"], spec["final"])
        work = make_work(self.ledger, sid, spec["output"])
        result = kickoff_single_task(
            agent,
            spec["tool"],
            work,
            description=spec["desc"],
            expected_output="A short deterministic answer.",
        )
        note = (
            "CrewAI executes the attached tool; there is no capability contract."
            if spec["expect"] == "deny"
            else "CrewAI runs the allowed tool."
        )
        return {
            "outcome": "executed",
            "protected_work_executed": self.ledger.executed(sid),
            "diagnostic_code": None,
            "event_types": [],
            "business_output": result if self.ledger.executed(sid) else None,
            "note": note,
        }

    # ------------------------------------------------------------ workflow
    def run_workflow(self) -> dict:
        """A real multi-agent sequential ``Crew.kickoff()`` happy path."""

        from crewai import Crew, Process, Task  # local import keeps the header clean
        from common import POLICY_TEXT, REFUND_PROPOSAL, ROLE_ADVISOR, ROLE_COORDINATOR, ROLE_REFUND
        from tools import make_tool

        coordinator = build_agent(ROLE_COORDINATOR, "classify_tool", CLASSIFICATION)
        advisor = build_agent(ROLE_ADVISOR, "policy_tool", POLICY_TEXT)
        refund = build_agent(ROLE_REFUND, "refund_tool", REFUND_PROPOSAL)
        crew = Crew(
            agents=[coordinator, advisor, refund],
            tasks=[
                Task(description="Classify the sanitized refund request.",
                     expected_output="A classification.", agent=coordinator,
                     tools=[make_tool("classify_tool",
                                      make_work(self.ledger, "wf", CLASSIFICATION))]),
                Task(description="Cite the applicable declared refund policy.",
                     expected_output="A policy citation.", agent=advisor,
                     tools=[make_tool("policy_tool",
                                      make_work(self.ledger, "wf", POLICY_TEXT))]),
                Task(description="Propose a refund within the declared limit.",
                     expected_output="A refund proposal.", agent=refund,
                     tools=[make_tool("refund_tool",
                                      make_work(self.ledger, "wf", REFUND_PROPOSAL))]),
            ],
            process=Process.sequential,
        )
        return {"output": str(crew.kickoff()), "final_step": "refund_proposal"}

    # ------------------------------------------------------------ scenarios
    def run_scenarios(self) -> dict[str, dict]:
        s: dict[str, dict] = {}
        for sid in RUNTIME:
            s[sid] = self._runtime(sid)
        self.allowed_outputs = {
            "classify": s["S1"]["business_output"],
            "refund": s["S4"]["business_output"],
            "response": s["S8"]["business_output"],
        }

        # S12 contract drift / stale lock — nothing to be stale in the baseline.
        s["S12"] = {
            "outcome": "unaffected",
            "protected_work_executed": True,
            "diagnostic_code": None,
            "event_types": [],
            "business_output": s["S1"]["business_output"],
            "note": "No lock or contract exists, so drift cannot be detected.",
        }

        # S14 deliberate bypass — calling work directly always runs it.
        work = make_work(self.ledger, "S14", common.DELETE_RECORDS_OUTPUT)
        out = work()
        s["S14"] = {
            "outcome": "bypassed",
            "protected_work_executed": self.ledger.executed("S14"),
            "diagnostic_code": None,
            "event_types": [],
            "business_output": out,
            "note": "Direct call; there is no adapter in the baseline to bypass.",
        }
        return s
