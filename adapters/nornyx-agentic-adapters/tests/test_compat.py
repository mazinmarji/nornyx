"""SPI-version compatibility and optional-dependency diagnostics."""

from __future__ import annotations

import pytest

from nornyx_agentic_adapters._compat import (
    MissingOptionalDependencyError,
    UnsupportedSPIVersionError,
    check_spi_version,
    require_extra,
)


def test_check_spi_version_accepts_supported_major() -> None:
    check_spi_version("1.0")
    check_spi_version("1.7")  # a hypothetical later minor is still major 1


def test_check_spi_version_rejects_unsupported_major() -> None:
    with pytest.raises(UnsupportedSPIVersionError):
        check_spi_version("2.0")


def test_check_spi_version_rejects_unparseable_version() -> None:
    with pytest.raises(UnsupportedSPIVersionError):
        check_spi_version("not-a-version")


def test_require_extra_gives_precise_diagnostic_when_absent() -> None:
    with pytest.raises(MissingOptionalDependencyError) as exc_info:
        require_extra("this_module_does_not_exist_anywhere", extra="crewai")
    message = str(exc_info.value)
    assert "this_module_does_not_exist_anywhere" in message
    assert "nornyx-agentic-adapters[crewai]" in message


def test_require_extra_returns_the_module_when_present() -> None:
    module = require_extra("json", extra="unused")
    assert module.__name__ == "json"


def test_installed_spi_version_is_actually_compatible() -> None:
    """Sanity: the SPI version this adapter package was built against still
    passes its own compatibility check (proves the import-time assertion in
    ``nornyx_agentic_adapters.__init__`` did not silently no-op)."""
    import nornyx.agentic as agentic

    check_spi_version(agentic.SPI_VERSION)
