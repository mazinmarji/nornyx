"""CoverageInventory: closed, frozen, deterministic serialization."""

from __future__ import annotations

import dataclasses
import json

import pytest

from nornyx_agentic_adapters import CoverageInventory, SurfaceCoverage, SurfaceStatus


def _inventory() -> CoverageInventory:
    return CoverageInventory(
        entries=(
            SurfaceCoverage("tool_invocation", "crewai", SurfaceStatus.WRAPPED),
            SurfaceCoverage(
                "delegation", "crewai", SurfaceStatus.UNSUPPORTED, "no reliable public hook"
            ),
        )
    )


def test_wrapped_returns_only_wrapped_entries() -> None:
    inventory = _inventory()
    wrapped = inventory.wrapped()
    assert len(wrapped) == 1
    assert wrapped[0].surface == "tool_invocation"


def test_as_dict_is_deterministic_and_json_serializable() -> None:
    inventory = _inventory()
    first = json.dumps(inventory.as_dict(), sort_keys=True)
    second = json.dumps(inventory.as_dict(), sort_keys=True)
    assert first == second
    payload = inventory.as_dict()
    # Sorted by (framework, surface): "delegation" < "tool_invocation" alphabetically.
    assert payload["surfaces"][0]["surface"] == "delegation"
    assert payload["surfaces"][0]["status"] == "unsupported"
    assert payload["surfaces"][0]["reason"] == "no reliable public hook"
    assert payload["surfaces"][1]["surface"] == "tool_invocation"
    assert payload["surfaces"][1]["status"] == "wrapped"


def test_as_dict_orders_entries_regardless_of_input_order() -> None:
    a = CoverageInventory(
        entries=(
            SurfaceCoverage("z_surface", "crewai", SurfaceStatus.WRAPPED),
            SurfaceCoverage("a_surface", "crewai", SurfaceStatus.WRAPPED),
        )
    )
    b = CoverageInventory(
        entries=(
            SurfaceCoverage("a_surface", "crewai", SurfaceStatus.WRAPPED),
            SurfaceCoverage("z_surface", "crewai", SurfaceStatus.WRAPPED),
        )
    )
    assert a.as_dict() == b.as_dict()


def test_surface_coverage_is_frozen() -> None:
    entry = SurfaceCoverage("tool_invocation", "crewai", SurfaceStatus.WRAPPED)
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.status = SurfaceStatus.UNWRAPPED  # type: ignore[misc]


def test_coverage_inventory_is_frozen() -> None:
    inventory = _inventory()
    with pytest.raises(dataclasses.FrozenInstanceError):
        inventory.entries = ()  # type: ignore[misc]


def test_coverage_never_claims_unnamed_surfaces() -> None:
    """The inventory is closed: only what's explicitly named exists in it."""
    inventory = _inventory()
    named = {entry.surface for entry in inventory.entries}
    assert named == {"tool_invocation", "delegation"}
