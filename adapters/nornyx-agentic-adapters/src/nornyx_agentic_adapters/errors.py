"""Public adapter-level error and denial types."""

from __future__ import annotations

from nornyx.agentic import Decision

from ._compat import MissingOptionalDependencyError, UnsupportedSPIVersionError

__all__ = [
    "AdapterDenied",
    "AdapterConfigurationError",
    "UnsupportedSPIVersionError",
    "MissingOptionalDependencyError",
]


class AdapterDenied(RuntimeError):
    """Raised by :func:`enforce` when the core SPI's :class:`Decision` is not ALLOW.

    Carries the deterministic core ``Decision`` (effect, code, reason, basis)
    so callers can inspect exactly why the wrapped action was blocked. Raising
    this — rather than returning a sentinel the caller must remember to check —
    guarantees the wrapped callable is never invoked on a non-ALLOW decision.
    """

    def __init__(self, decision: Decision) -> None:
        super().__init__(f"{decision.code.value}: {decision.reason or decision.code.value}")
        self.decision = decision


class AdapterConfigurationError(ValueError):
    """Raised for a malformed or incomplete adapter-owned declarative mapping.

    Adapters fail closed on missing or ambiguous binding information rather
    than guessing (e.g. an unrecognized surface name, an identity/capability
    mapping the adapter's own configuration never declared).
    """
