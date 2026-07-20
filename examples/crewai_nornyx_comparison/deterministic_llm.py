"""A deterministic, offline ``BaseLLM`` for native CrewAI execution.

The model is scripted, not stochastic: on a task's first call it emits a single
``Action:`` step naming the governed/plain tool, and on every later call it
emits a ``Final Answer:``. This drives CrewAI's real ReAct executor through a
genuine ``Crew.kickoff()`` while never touching a network, an API key, or an
external model. It mirrors the model used by the repository's native CrewAI
verification suite (``tests/test_agentic_crewai_native.py``).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import common  # noqa: F401,E402  (import for the telemetry kill switches side effect)

from crewai import BaseLLM  # noqa: E402


class DeterministicLLM(BaseLLM):
    """Scripted offline LLM: one tool call, then a final answer."""

    def __init__(self, tool_name: str | None, final_answer: str):
        super().__init__(model="nornyx-deterministic-offline")
        self._tool_name = tool_name
        self._final_answer = final_answer
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    def call(
        self,
        messages: Any,
        tools: Any = None,
        callbacks: Any = None,
        available_functions: Any = None,
        **kwargs: Any,
    ) -> str:
        self._call_count += 1
        if self._tool_name is not None and self._call_count == 1:
            return (
                "Thought: I must use the governed tool.\n"
                f"Action: {self._tool_name}\n"
                "Action Input: {}"
            )
        return (
            "Thought: I now can give a great answer\n"
            f"Final Answer: {self._final_answer}"
        )

    def supports_function_calling(self) -> bool:
        return False

    def supports_stop_words(self) -> bool:
        return False

    def get_context_window_size(self) -> int:
        return 8192
