"""Deterministic local harness (Layer 3 substitute) for safe demonstrations.

Provides a fake model and inert tools so both reference adapters can be
demonstrated end to end with no API keys, no sockets, no external writes, no
production endpoints, and byte-reproducible emitted evidence.
"""

from __future__ import annotations

from typing import Any


class FakeModel:
    """Returns canned deterministic completions; never contacts a network."""

    def __init__(self, responses: dict[str, str]):
        self._responses = dict(responses)
        self.calls: list[str] = []

    def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self._responses.get(prompt, "deterministic-default-response")


class InertTool:
    """Records invocations and returns a fixed local result; performs no IO."""

    def __init__(self, name: str, result: str):
        self.name = name
        self._result = result
        self.invocations: list[dict[str, Any]] = []

    def run(self, **arguments: Any) -> str:
        self.invocations.append(dict(sorted(arguments.items())))
        return self._result


class DuckAgent:
    """A minimal CrewAI-shaped agent stand-in (role/goal attributes only)."""

    def __init__(self, role: str, goal: str = "governed local demonstration"):
        self.role = role
        self.goal = goal
