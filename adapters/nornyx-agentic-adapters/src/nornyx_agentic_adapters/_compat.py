"""Internal compatibility helpers: SPI-version assertion and optional-framework imports."""

from __future__ import annotations

import importlib
from typing import Any

SUPPORTED_SPI_MAJOR = 1


class UnsupportedSPIVersionError(RuntimeError):
    """Raised when the installed ``nornyx.agentic.SPI_VERSION`` is not a major
    version this adapter package build supports."""


def check_spi_version(spi_version: str) -> None:
    """Fail closed unless ``spi_version`` (e.g. ``"1.0"``) has a supported major.

    A new SPI minor version (a new optional request field, a new decision
    code) is compatible under ADR-0039's own minor-compatibility rule; a new
    major version is never assumed compatible.
    """
    try:
        major_str, _, _ = spi_version.partition(".")
        major = int(major_str)
    except (ValueError, AttributeError) as exc:
        raise UnsupportedSPIVersionError(
            f"Cannot parse nornyx.agentic.SPI_VERSION {spi_version!r}."
        ) from exc
    if major != SUPPORTED_SPI_MAJOR:
        raise UnsupportedSPIVersionError(
            f"nornyx.agentic.SPI_VERSION {spi_version!r} is not supported; "
            f"this adapter package supports SPI major version {SUPPORTED_SPI_MAJOR}."
        )


class MissingOptionalDependencyError(ImportError):
    """Raised when a framework-specific submodule is imported without its extra."""


def require_extra(module_name: str, *, extra: str) -> Any:
    """Import ``module_name``, raising a precise diagnostic if it is absent.

    For use by framework-specific submodules to fail with an actionable
    message (rather than a bare ``ImportError``) when their optional extra
    (e.g. ``pip install nornyx-agentic-adapters[crewai]``) was not installed.
    """
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise MissingOptionalDependencyError(
            f"{module_name!r} is not installed. Install it with "
            f"'pip install nornyx-agentic-adapters[{extra}]'."
        ) from exc
