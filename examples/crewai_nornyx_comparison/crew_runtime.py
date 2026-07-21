"""Native CrewAI lifecycle helpers shared by both variants.

Both Variant A and Variant B build the *same* real ``Agent``/``Task``/``Crew``
objects and drive them through a genuine ``Crew.kickoff()``. The only thing
that changes is the callable the tool wraps: raw work (plain) or kernel-guarded
work (governed).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import common  # noqa: F401,E402  (telemetry kill switches side effect)

from crewai import Agent, Crew, Process, Task  # noqa: E402

from deterministic_llm import DeterministicLLM  # noqa: E402
from tools import make_tool  # noqa: E402


def build_agent(role: str, tool_name: str | None, final_answer: str) -> Agent:
    """Build one real CrewAI agent driven by the deterministic offline LLM."""

    return Agent(
        role=role,
        goal="Process the sanitized support request within declared bounds.",
        backstory="Deterministic offline agent in the governed support network.",
        allow_delegation=False,
        verbose=False,
        llm=DeterministicLLM(tool_name, final_answer),
    )


def kickoff_single_task(
    agent: Agent,
    tool_name: str,
    work: Callable[..., str],
    *,
    description: str,
    expected_output: str,
    final_answer: str | None = None,
) -> str:
    """Run one real single-task ``Crew.kickoff()`` and return the crew output.

    ``work`` is the callable the tool executes. For the governed variant it is
    the guarded callable, so the kernel's capability check runs inside the tool
    before the underlying work.
    """

    if final_answer is not None:
        # Re-script the agent's model for this task's tool + final answer.
        agent.llm = DeterministicLLM(tool_name, final_answer)
    task = Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        tools=[make_tool(tool_name, work)],
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
    return str(crew.kickoff())
