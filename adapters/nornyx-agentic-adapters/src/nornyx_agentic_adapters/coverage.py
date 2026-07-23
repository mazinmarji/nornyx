"""Deterministic, closed coverage inventory of adapter-wrapped surfaces.

ADR-0040 Tier 2 claim eligibility requires a declared coverage inventory naming
which surfaces are wrapped. A core ``Decision`` governs exactly one request;
this inventory is the only place an adapter may make a broader claim, and it
must remain honest about it: unsupported and unwrapped surfaces are named,
not hidden, and the inventory never implies whole-application coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SurfaceStatus(Enum):
    WRAPPED = "wrapped"
    UNSUPPORTED = "unsupported"
    UNWRAPPED = "unwrapped"


@dataclass(frozen=True)
class SurfaceCoverage:
    surface: str
    framework: str
    status: SurfaceStatus
    reason: str = ""


@dataclass(frozen=True)
class CoverageInventory:
    """A closed set of declared surfaces and their wrap status.

    Never implies whole-application coverage (ADR-0040): it names exactly the
    surfaces an adapter declares, for the stated framework only.
    """

    entries: tuple[SurfaceCoverage, ...]

    def wrapped(self) -> tuple[SurfaceCoverage, ...]:
        return tuple(entry for entry in self.entries if entry.status is SurfaceStatus.WRAPPED)

    def as_dict(self) -> dict:
        """Deterministic, JSON-serializable representation (sorted for reproducibility)."""
        return {
            "surfaces": [
                {
                    "surface": entry.surface,
                    "framework": entry.framework,
                    "status": entry.status.value,
                    "reason": entry.reason,
                }
                for entry in sorted(self.entries, key=lambda entry: (entry.framework, entry.surface))
            ]
        }
