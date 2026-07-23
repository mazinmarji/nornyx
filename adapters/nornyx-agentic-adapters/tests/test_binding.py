"""SurfaceBinding: fails closed on malformed or incomplete declarative mappings."""

from __future__ import annotations

import dataclasses

import pytest

from nornyx_agentic_adapters import AdapterConfigurationError, SurfaceBinding, validate_binding


def test_valid_binding_passes() -> None:
    validate_binding(SurfaceBinding("tool_invocation", "identity:agent-1", "capability:file_write"))


@pytest.mark.parametrize(
    "surface,identity_ref,capability_ref",
    [
        ("", "identity:agent-1", "capability:file_write"),
        ("tool_invocation", "", "capability:file_write"),
        ("tool_invocation", "identity:agent-1", ""),
        ("   ", "identity:agent-1", "capability:file_write"),
    ],
)
def test_blank_required_field_fails_closed(surface: str, identity_ref: str, capability_ref: str) -> None:
    binding = SurfaceBinding(surface, identity_ref, capability_ref)
    with pytest.raises(AdapterConfigurationError):
        validate_binding(binding)


def test_surface_binding_is_frozen() -> None:
    binding = SurfaceBinding("tool_invocation", "identity:agent-1", "capability:file_write")
    with pytest.raises(dataclasses.FrozenInstanceError):
        binding.surface = "other"  # type: ignore[misc]
