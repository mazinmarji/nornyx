"""AdapterMetadata: frozen, no runtime enforcement beyond declaration."""

from __future__ import annotations

import dataclasses

import pytest

from nornyx_agentic_adapters import AdapterMetadata


def _metadata() -> AdapterMetadata:
    return AdapterMetadata(
        adapter_name="nornyx-agentic-adapters",
        adapter_version="0.1.0",
        spi_version="1.0",
        framework_name="crewai",
        framework_version_range="==1.15.4",
        nornyx_version_range=">=1.8,<2",
    )


def test_metadata_fields_roundtrip() -> None:
    metadata = _metadata()
    assert metadata.adapter_name == "nornyx-agentic-adapters"
    assert metadata.framework_name == "crewai"
    assert metadata.framework_version_range == "==1.15.4"


def test_metadata_is_frozen() -> None:
    metadata = _metadata()
    with pytest.raises(dataclasses.FrozenInstanceError):
        metadata.adapter_version = "9.9.9"  # type: ignore[misc]
