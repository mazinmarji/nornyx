"""``nornyx_agentic_adapters`` — supported framework adapters for the Nornyx
``nornyx.agentic`` authorization SPI (ADR-0039).

This base package imports no agent framework. Framework-specific behavior
(CrewAI, LangGraph) lives in separate, optional submodules gated by their own
extras (``pip install nornyx-agentic-adapters[crewai]`` /
``...[langgraph]``) — not yet present in this foundation release.

Cooperative Tier 2 (ADR-0040): enforcement here covers only the surfaces a
framework submodule explicitly declares and wraps in its coverage inventory.
Bypassing an adapter bypasses enforcement. Adapters never authenticate agents
or approvers, never attest that a runtime event is true, and never claim
independent (Tier 3) runtime assurance.
"""

from __future__ import annotations

import nornyx.agentic as _agentic

from ._compat import (
    MissingOptionalDependencyError,
    UnsupportedSPIVersionError,
    check_spi_version,
    require_extra,
)
from .binding import SurfaceBinding, validate_binding
from .coverage import CoverageInventory, SurfaceCoverage, SurfaceStatus
from .enforcement import enforce
from .errors import AdapterConfigurationError, AdapterDenied
from .metadata import AdapterMetadata

__version__ = "0.1.0"

check_spi_version(_agentic.SPI_VERSION)

__all__ = [
    "__version__",
    "AdapterMetadata",
    "CoverageInventory",
    "SurfaceCoverage",
    "SurfaceStatus",
    "enforce",
    "AdapterDenied",
    "AdapterConfigurationError",
    "UnsupportedSPIVersionError",
    "MissingOptionalDependencyError",
    "require_extra",
    "SurfaceBinding",
    "validate_binding",
]
