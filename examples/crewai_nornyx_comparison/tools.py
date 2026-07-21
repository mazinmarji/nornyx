"""Real CrewAI tools plus a side-effect ledger.

The ledger is the load-bearing piece of evidence for the whole comparison: a
protected unit of work increments its counter *only when it actually runs*. A
denied Nornyx path must leave the counter at zero, proving the work callable
never executed. The tools themselves are genuine ``crewai.tools.BaseTool``
objects — the exact type CrewAI's executor invokes during ``Crew.kickoff()``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import common  # noqa: F401,E402  (telemetry kill switches side effect)

from crewai.tools import BaseTool  # noqa: E402


class SideEffectLedger:
    """Counts how many times each scenario's protected work actually ran."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def record(self, key: str) -> None:
        self._counts[key] = self._counts.get(key, 0) + 1

    def count(self, key: str) -> int:
        return self._counts.get(key, 0)

    def executed(self, key: str) -> bool:
        return self.count(key) > 0

    def snapshot(self) -> dict[str, int]:
        return dict(sorted(self._counts.items()))


def make_work(ledger: SideEffectLedger, key: str, output: str) -> Callable[..., str]:
    """Return a protected work callable that records execution then returns output."""

    def work(*_args: Any, **_kwargs: Any) -> str:
        ledger.record(key)
        return output

    return work


class _CallableTool(BaseTool):
    """A CrewAI tool that runs one bound callable and returns its string result."""

    name: str = "support_tool"
    description: str = "Execute one bounded unit of governed support work."

    def _run(self, *args: Any, **kwargs: Any) -> str:
        return self._callable()  # type: ignore[attr-defined]


def make_tool(name: str, callable_: Callable[..., str]) -> _CallableTool:
    """Wrap a callable in a real CrewAI tool.

    For Variant A the callable is the raw work; for Variant B it is the
    kernel-guarded work returned by ``CrewAIGovernanceAdapter.guarded_task``.
    """

    tool = _CallableTool()
    tool.name = name
    # The bound callable lives outside the pydantic field model.
    object.__setattr__(tool, "_callable", callable_)
    return tool
