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

from .errors import AdapterConfigurationError


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

    ``entries`` is canonicalized to a tuple of ``SurfaceCoverage`` at
    construction, regardless of what iterable the caller passed in — a caller
    that builds this from a retained ``list`` and mutates that list afterward
    cannot alter the inventory once constructed, since the stored value is a
    fresh, independent tuple, not a reference to the caller's container.
    """

    entries: tuple[SurfaceCoverage, ...]

    def __post_init__(self) -> None:
        entries = tuple(self.entries)
        for entry in entries:
            if not isinstance(entry, SurfaceCoverage):
                raise AdapterConfigurationError(
                    f"CoverageInventory entries must be SurfaceCoverage instances; "
                    f"got {type(entry).__name__!r}."
                )
        object.__setattr__(self, "entries", entries)

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
