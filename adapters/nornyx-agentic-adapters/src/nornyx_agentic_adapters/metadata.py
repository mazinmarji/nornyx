"""Adapter metadata: identity of one adapter build against a framework/SPI/nornyx."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdapterMetadata:
    """Declares one adapter's identity and its supported SPI/nornyx/framework ranges.

    ``framework_version_range`` and ``nornyx_version_range`` are human-readable
    PEP 440-style specifiers (e.g. ``"==1.15.4"``, ``">=1.8,<2"``); they are not
    enforced by this dataclass itself. The ``nornyx`` range is enforced by this
    package's own ``dependencies`` declaration; the framework range is enforced
    by each framework-specific submodule's own import-time check.
    """

    adapter_name: str
    adapter_version: str
    spi_version: str
    framework_name: str
    framework_version_range: str
    nornyx_version_range: str
