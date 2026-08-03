"""ADR-0043 M2-E: hostile and malformed input to the conformance kit.

The report is machine-checkable evidence, so the values in it must be exact
plain builtins and must not depend on a caller's retained container or on a
subclass that redefines equality, hashing, or stringification.

Runs in the base install: no framework extra is required.
"""

from __future__ import annotations

import json

import pytest

from nornyx_agentic_adapters import (
    AdapterConfigurationError,
    CoverageInventory,
    SurfaceCoverage,
    SurfaceStatus,
)
from nornyx_agentic_adapters.conformance import (
    run_conformance,
    serialize,
    validate_report,
)

BASE_SUITES = ["distribution", "enforcement_boundary"]


class HostileStr(str):
    """A ``str`` whose comparison and rendering lie."""

    calls = 0

    def __eq__(self, other: object) -> bool:  # noqa: D105
        type(self).calls += 1
        return True

    def __ne__(self, other: object) -> bool:  # noqa: D105
        return False

    def __hash__(self) -> int:  # noqa: D105
        return 0

    def __str__(self) -> str:  # noqa: D105
        type(self).calls += 1
        return "innocent"


class HostileList(list):
    def __iter__(self):  # noqa: D105
        raise AssertionError("hostile __iter__ was invoked")


def test_report_values_are_exact_plain_builtins() -> None:
    """A JSON-typed value that is secretly a subclass would round-trip
    differently than it compares, so every leaf must be an exact builtin."""
    payload = run_conformance(frameworks=BASE_SUITES).as_dict()

    def check(node: object, pointer: str) -> None:
        if isinstance(node, dict):
            assert type(node) is dict, pointer
            for key, value in node.items():
                assert type(key) is str, f"{pointer}: key {key!r}"
                check(value, f"{pointer}/{key}")
        elif isinstance(node, list):
            assert type(node) is list, pointer
            for index, value in enumerate(node):
                check(value, f"{pointer}/{index}")
        else:
            assert type(node) in (str, int, bool, type(None)), f"{pointer}: {type(node)}"

    check(payload, "")


def test_report_round_trips_through_json_unchanged() -> None:
    report = run_conformance(frameworks=BASE_SUITES)
    text = serialize(report)
    assert json.loads(text) == report.as_dict()
    assert validate_report(json.loads(text)) == ()


def test_a_retained_caller_container_cannot_alter_a_later_report() -> None:
    """The caller keeps a reference to the selection lists and mutates them
    after the run; the next report must be unaffected."""
    frameworks = list(BASE_SUITES)
    cases = ["neutral.enforce.allow"]
    first = serialize(run_conformance(frameworks=frameworks, case_ids=cases))
    frameworks.append("crewai")
    frameworks.clear()
    cases.append("forged.case")
    second = serialize(run_conformance(frameworks=list(BASE_SUITES), case_ids=["neutral.enforce.allow"]))
    assert first == second


def test_a_returned_report_dict_is_independent_of_later_mutation() -> None:
    report = run_conformance(frameworks=BASE_SUITES)
    payload = report.as_dict()
    payload["suites"][0]["cases"][0]["decision_events"].append("forged")
    payload["outcome"] = "fail"
    assert report.as_dict()["outcome"] == "pass"
    assert "forged" not in report.as_dict()["suites"][0]["cases"][0]["decision_events"]


def test_a_hostile_str_subclass_is_normalized_not_trusted() -> None:
    """A subclass whose ``__eq__`` always returns True and whose ``__str__``
    lies is normalized to its exact underlying value at the selection boundary.

    So it resolves to the case it actually names — not to whatever its
    overrides would have claimed — and its lying rendering never reaches the
    report.
    """
    HostileStr.calls = 0
    hostile = HostileStr("neutral.enforce.allow")
    report = run_conformance(frameworks=["enforcement_boundary"], case_ids=[hostile])
    selected = [case.case_id for suite in report.suites for case in suite.cases]
    assert selected == ["neutral.enforce.allow"]
    assert all(type(case_id) is str for case_id in selected)
    assert "innocent" not in serialize(report)


def test_a_hostile_str_subclass_naming_nothing_is_still_rejected() -> None:
    """Normalization must not become a way to smuggle an unmatched id past the
    check: the exact underlying value still has to name a real case."""
    with pytest.raises(ValueError, match="no conformance case matches"):
        run_conformance(
            frameworks=["enforcement_boundary"], case_ids=[HostileStr("no.such.case")]
        )


def test_a_plain_case_id_still_selects_normally() -> None:
    """The rejection above is about the hostile subclass, not about filtering."""
    report = run_conformance(
        frameworks=["enforcement_boundary"], case_ids=["neutral.enforce.allow"]
    )
    selected = [case.case_id for suite in report.suites for case in suite.cases]
    assert selected == ["neutral.enforce.allow"]
    assert all(type(case_id) is str for case_id in selected)
    assert "innocent" not in serialize(report)


def test_a_hash_colliding_subclass_cannot_pass_as_a_real_case_id() -> None:
    """Selection membership is set arithmetic, so a subclass that collides on
    hash and always compares equal would otherwise be treated as matched — the
    same failure the exemption check guards against, reached through a
    different pair of dunders. Ids are normalized to exact ``str`` first."""

    class EqSneaky(str):
        def __eq__(self, other: object) -> bool:  # noqa: D105
            return True

        def __hash__(self) -> int:  # noqa: D105
            return hash("neutral.enforce.allow")

    with pytest.raises(ValueError, match="no conformance case matches"):
        run_conformance(
            frameworks=["enforcement_boundary"], case_ids=[EqSneaky("bogus")]
        )


def test_unknown_suite_selection_is_rejected_rather_than_silently_empty() -> None:
    with pytest.raises(ValueError, match="unknown suite"):
        run_conformance(frameworks=["enforcement_boundary", "no_such_suite"])


def test_an_unmatched_case_id_is_rejected_not_reported_as_a_pass() -> None:
    """Selecting a case that does not exist must not produce a zero-case report
    that validates and exits 0 — a typo would read as a passing run."""
    with pytest.raises(ValueError, match="no conformance case matches"):
        run_conformance(frameworks=["enforcement_boundary"], case_ids=["no.such.case"])


# ------------------------------------------------------------------ inventory input
def test_coverage_inventory_rejects_non_surface_entries() -> None:
    with pytest.raises(AdapterConfigurationError):
        CoverageInventory(entries=(("tool_invocation", "crewai", "wrapped"),))


def test_coverage_inventory_detaches_a_retained_caller_list() -> None:
    entries = [SurfaceCoverage("tool_invocation", "crewai", SurfaceStatus.WRAPPED, "r")]
    inventory = CoverageInventory(entries=entries)
    entries.append(SurfaceCoverage("forged", "crewai", SurfaceStatus.WRAPPED, "r"))
    entries.clear()
    assert [e.surface for e in inventory.entries] == ["tool_invocation"]
    assert inventory.as_dict()["surfaces"][0]["surface"] == "tool_invocation"


def test_duplicate_surfaces_are_detectable_in_an_inventory() -> None:
    """``CoverageInventory`` does not itself forbid a duplicate surface, so the
    conformance suites assert uniqueness on the reported coverage. This pins
    that a duplicate really would be visible rather than collapsing silently."""
    inventory = CoverageInventory(
        entries=(
            SurfaceCoverage("tool_invocation", "crewai", SurfaceStatus.WRAPPED, "a"),
            SurfaceCoverage("tool_invocation", "crewai", SurfaceStatus.UNSUPPORTED, "b"),
        )
    )
    surfaces = [entry["surface"] for entry in inventory.as_dict()["surfaces"]]
    assert len(surfaces) == 2
    assert len(set(surfaces)) == 1, "a duplicate surface must remain visible, not collapse"


def test_coverage_inventory_output_is_sorted_and_deterministic() -> None:
    entries = (
        SurfaceCoverage("z_surface", "langgraph", SurfaceStatus.UNSUPPORTED, "z"),
        SurfaceCoverage("a_surface", "crewai", SurfaceStatus.WRAPPED, "a"),
    )
    first = CoverageInventory(entries=entries).as_dict()
    second = CoverageInventory(entries=tuple(reversed(entries))).as_dict()
    assert first == second
    assert [e["framework"] for e in first["surfaces"]] == ["crewai", "langgraph"]
