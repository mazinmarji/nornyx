"""Native CrewAI lifecycle helpers shared by both variants.

Both Variant A and Variant B build the *same* real ``Agent``/``Task``/``Crew``
objects with the same role, description, expected output, and deterministic
model, and drive them through a genuine ``Crew.kickoff()``. The only object that
differs is the tool instance: a plain ``BaseTool`` in Variant A, and the
supported adapter's governed ``BaseTool`` in Variant B — both wrapping the
identical business callable from ``business.py``.
"""

from __future__ import annotations

from typing import Any, Callable

from crewai_governance_benchmark import config  # noqa: F401  (telemetry kill-switch side effect)

from crewai import Agent, Crew, Process, Task  # noqa: E402
from crewai.tools import BaseTool  # noqa: E402

from crewai_governance_benchmark.deterministic_llm import DeterministicLLM  # noqa: E402

# The fallback answer the scripted model produces when its tool call did not
# yield a usable result (a governed denial, or an application-rule refusal).
FALLBACK_ANSWER = "I could not complete that action under the declared bounds."

AGENT_GOAL = "Remediate the sanitized customer case within declared bounds."
AGENT_BACKSTORY = "Deterministic offline agent on the governed remediation desk."


class PlainTool(BaseTool):
    """An ordinary CrewAI tool: it runs the business callable directly.

    This is what a normal CrewAI application looks like. There is no governance
    hook of any kind; the tool being attached to the agent is the only thing that
    decides whether the work may happen.
    """

    def _run(self, *args: Any, **kwargs: Any) -> str:
        return self._business_callable(*args, **kwargs)  # type: ignore[attr-defined]


def plain_tool(name: str, description: str, business_callable: Callable[..., str]) -> PlainTool:
    """Build an ungoverned CrewAI tool around ``business_callable``."""
    tool = PlainTool(name=name, description=description)
    # The bound callable lives outside the pydantic field model.
    object.__setattr__(tool, "_business_callable", business_callable)
    return tool


def build_agent(role: str, tool_name: str | None, final_answer: str) -> Agent:
    """Build one real CrewAI agent driven by the deterministic offline model."""
    return Agent(
        role=role,
        goal=AGENT_GOAL,
        backstory=AGENT_BACKSTORY,
        allow_delegation=False,
        verbose=False,
        llm=DeterministicLLM(tool_name, final_answer),
    )


def kickoff_single_task(
    *,
    role: str,
    tool: BaseTool,
    description: str,
    expected_output: str,
    final_answer: str,
) -> str:
    """Run one real single-task ``Crew.kickoff()`` and return the crew output.

    Identical in both variants: same agent role, same task text, same scripted
    model, same sequential process. Only ``tool`` differs.
    """
    agent = build_agent(role, tool.name, final_answer)
    task = Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        tools=[tool],
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
    return str(crew.kickoff())
