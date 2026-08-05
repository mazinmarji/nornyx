"""Pip-only, registry-backed distribution-conformance example.

Installs a **published** `nornyx-agentic-adapters` from PyPI into a clean
environment with no repository checkout available, resolves the bundled
conformance schema and contract fixture through `importlib.resources` from the
installed wheel, runs the conformance kit, and emits an independently auditable
record of where every artifact actually came from.

This is not an installation smoke test. A smoke test answers "did pip exit 0";
this answers "is the artifact on the index the one we think we published, and is
its package data really there and really intact". It can therefore fail for a
genuine distribution defect -- an undeclared `package-data` entry, a truncated
resource, a version that resolved to something else -- and it names which.

Entry point::

    python -m examples.pip_only_conformance --json

See `README.md` for the failure taxonomy and what each class does and does not
claim.
"""

from __future__ import annotations

from .failures import DISTRIBUTION_FAILURE_CLASSES, FailureClass, PipOnlyExampleError
from .provenance import (
    PYPI_HOSTS,
    PYPI_INDEX_URL,
    ArtifactProvenance,
    parse_install_report,
    provenance_violations,
)
from .runner import (
    DEFAULT_VERSION,
    DISTRIBUTION_NAME,
    ExampleResult,
    check_process_consistency,
    parse_envelope,
    raise_for_envelope,
    repository_roots,
    run_example,
)

__all__ = [
    "DEFAULT_VERSION",
    "DISTRIBUTION_FAILURE_CLASSES",
    "DISTRIBUTION_NAME",
    "PYPI_HOSTS",
    "PYPI_INDEX_URL",
    "ArtifactProvenance",
    "ExampleResult",
    "FailureClass",
    "PipOnlyExampleError",
    "check_process_consistency",
    "parse_envelope",
    "parse_install_report",
    "provenance_violations",
    "raise_for_envelope",
    "repository_roots",
    "run_example",
]
