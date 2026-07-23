"""CoverageInventory: closed, frozen, deterministic serialization."""

from __future__ import annotations

import dataclasses
import json

import pytest

from nornyx_agentic_adapters import (
    AdapterConfigurationError,
    CoverageInventory,
    SurfaceCoverage,
    SurfaceStatus,
)


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


def test_entries_canonicalized_to_tuple_from_a_list() -> None:
    inventory = CoverageInventory(
        entries=[SurfaceCoverage("tool_invocation", "crewai", SurfaceStatus.WRAPPED)]
    )
    assert isinstance(inventory.entries, tuple)


def test_retained_caller_list_mutation_after_construction_has_no_effect() -> None:
    """F-2 regression: a caller building this from a retained list must not be
    able to alter the inventory by mutating that list afterward."""
    source = [SurfaceCoverage("tool_invocation", "crewai", SurfaceStatus.WRAPPED)]
    inventory = CoverageInventory(entries=source)
    before = inventory.as_dict()
    source.append(SurfaceCoverage("delegation", "crewai", SurfaceStatus.UNSUPPORTED))
    after = inventory.as_dict()
    assert before == after
    assert len(inventory.entries) == 1


def test_as_dict_is_stable_across_repeated_calls() -> None:
    inventory = _inventory()
    assert inventory.as_dict() == inventory.as_dict()


def test_equal_inventories_compare_equal_and_hash_equal() -> None:
    a = _inventory()
    b = _inventory()
    assert a == b
    assert hash(a) == hash(b)


def test_valid_tuple_construction_still_works() -> None:
    inventory = CoverageInventory(
        entries=(SurfaceCoverage("tool_invocation", "crewai", SurfaceStatus.WRAPPED),)
    )
    assert len(inventory.entries) == 1


def test_malformed_entry_fails_deterministically() -> None:
    with pytest.raises(AdapterConfigurationError):
        CoverageInventory(entries=({"surface": "tool_invocation"},))  # type: ignore[arg-type]
