"""The mechanical proof layer: a side-effect ledger on a single monotonic clock.

Nothing in this benchmark infers prevention from an exception message. Every
business tool with a side effect writes to this ledger, and every governance
decision is stamped on the *same* monotonically increasing counter. That makes
two otherwise-unprovable claims checkable:

* **Did the business callable actually run?** ``successes(scenario)`` counts
  completions, ``attempts(scenario)`` counts entries. A denied scenario must
  hold both at exactly zero; an allowed scenario must hold both at exactly one.
* **Was the decision recorded before execution?** Every entry carries a global
  ``seq``. ``ordering_ok(scenario)`` is true only when every decision for that
  scenario was stamped strictly before the first business-callable entry.

``attempts`` and ``successes`` are deliberately distinct: a governed action that
is authorized and then *fails* must show one attempt and zero successes, and
must never be reported as a completed side effect.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from typing import Any, Callable, Iterator


@dataclass(frozen=True)
class LedgerEntry:
    seq: int
    scenario: str
    kind: str  # "decision" | "attempt" | "success" | "failure"
    label: str
    detail: str = ""


class Ledger:
    """One monotonic clock shared by governance decisions and business effects."""

    def __init__(self) -> None:
        self._clock: Iterator[int] = count(1)
        self._entries: list[LedgerEntry] = []

    def _stamp(self, scenario: str, kind: str, label: str, detail: str = "") -> LedgerEntry:
        entry = LedgerEntry(next(self._clock), scenario, kind, label, detail)
        self._entries.append(entry)
        return entry

    # -- writers -------------------------------------------------------------
    def decision(self, scenario: str, code: str, effect: str) -> None:
        """Stamp a governance decision. Called only from the recorder hook."""
        self._stamp(scenario, "decision", code, effect)

    def attempt(self, scenario: str, tool: str) -> None:
        """Stamp entry into a business callable, before its work happens."""
        self._stamp(scenario, "attempt", tool)

    def success(self, scenario: str, tool: str, output: str) -> None:
        """Stamp completion of a business callable's real side effect."""
        self._stamp(scenario, "success", tool, output)

    def failure(self, scenario: str, tool: str, error: str) -> None:
        """Stamp a business callable that entered but did not complete."""
        self._stamp(scenario, "failure", tool, error)

    # -- readers -------------------------------------------------------------
    def _of(self, scenario: str, kind: str) -> list[LedgerEntry]:
        return [e for e in self._entries if e.scenario == scenario and e.kind == kind]

    def attempts(self, scenario: str) -> int:
        return len(self._of(scenario, "attempt"))

    def successes(self, scenario: str) -> int:
        return len(self._of(scenario, "success"))

    def failures(self, scenario: str) -> int:
        return len(self._of(scenario, "failure"))

    def decisions(self, scenario: str) -> int:
        return len(self._of(scenario, "decision"))

    def outputs(self, scenario: str) -> list[str]:
        return [e.detail for e in self._of(scenario, "success")]

    def ordering_ok(self, scenario: str) -> bool | None:
        """True when every business-callable entry was preceded by its own decision.

        A framework may invoke a governed tool more than once (CrewAI retries a
        failing tool internally). The check is therefore pairwise rather than
        global: the k-th entry into the business callable must be preceded by a
        k-th recorded decision. That is what distinguishes "each invocation was
        authorized" from "one authorization was silently reused".

        ``None`` when the question does not apply — no decision was recorded, or
        the callable never ran, so there is no ordering to verify.
        """
        decisions = sorted(e.seq for e in self._of(scenario, "decision"))
        entries = sorted(e.seq for e in self._of(scenario, "attempt"))
        if not decisions or not entries:
            return None
        if len(decisions) < len(entries):
            return False
        return all(decision < entry for decision, entry in zip(decisions, entries))

    def snapshot(self, scenario: str) -> dict[str, Any]:
        return {
            "decisions_recorded": self.decisions(scenario),
            "business_callable_attempts": self.attempts(scenario),
            "business_side_effects_completed": self.successes(scenario),
            "business_callable_failures": self.failures(scenario),
            "decision_recorded_before_execution": self.ordering_ok(scenario),
        }

    def timeline(self) -> list[dict[str, Any]]:
        return [
            {
                "seq": e.seq,
                "scenario": e.scenario,
                "kind": e.kind,
                "label": e.label,
                "detail": e.detail,
            }
            for e in self._entries
        ]

    def total_side_effects(self) -> int:
        return sum(1 for e in self._entries if e.kind == "success")


@dataclass
class BusinessTool:
    """One business capability with a genuine, ledger-recorded side effect.

    ``run`` is the single callable both variants execute. Variant A calls it
    directly from a plain CrewAI tool; Variant B passes the *same* callable to
    the supported adapter as the governed action. Neither variant gets its own
    copy of the business logic.
    """

    name: str
    describe: str
    work: Callable[..., str]
    ledger: Ledger = field(repr=False)
    scenario: str = ""

    def bind(self, scenario: str) -> "BusinessTool":
        """Return a copy of this tool bound to one scenario's ledger namespace."""
        return BusinessTool(self.name, self.describe, self.work, self.ledger, scenario)

    def run(self, *args: Any, **kwargs: Any) -> str:
        self.ledger.attempt(self.scenario, self.name)
        try:
            output = self.work(*args, **kwargs)
        except Exception as exc:
            self.ledger.failure(self.scenario, self.name, f"{type(exc).__name__}: {exc}")
            raise
        self.ledger.success(self.scenario, self.name, output)
        return output
