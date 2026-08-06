"""Reproducible external adoption pilot (M5-A-1).

Installs the published `nornyx-agentic-adapters` with its CrewAI extra from
PyPI into a clean environment — no repository checkout — and runs one action
three ways: ungoverned, governed and authorized, governed and unauthorized.

The point is comparative. Ungoverned, the action runs and no evidence exists.
Governed and authorized, it still runs, and now there is a decision and an
evidence stream. Governed and unauthorized, it does not run at all.

Entry point::

    python -m examples.external_adoption_pilot --json

See `README.md` for the failure taxonomy and what each class does and does not
claim.
"""

from __future__ import annotations

from .failures import DISTRIBUTION_FAILURE_CLASSES, PilotError, PilotFailure
from .runner import (
    ADAPTER_DISTRIBUTION,
    ADAPTER_VERSION,
    CREWAI_VERSION,
    PYPI_INDEX_URL,
    PilotResult,
    check_process_consistency,
    parse_envelope,
    raise_for_envelope,
    repository_roots,
    run_pilot,
)

__all__ = [
    "ADAPTER_DISTRIBUTION",
    "ADAPTER_VERSION",
    "CREWAI_VERSION",
    "DISTRIBUTION_FAILURE_CLASSES",
    "PYPI_INDEX_URL",
    "PilotError",
    "PilotFailure",
    "PilotResult",
    "check_process_consistency",
    "parse_envelope",
    "raise_for_envelope",
    "repository_roots",
    "run_pilot",
]
