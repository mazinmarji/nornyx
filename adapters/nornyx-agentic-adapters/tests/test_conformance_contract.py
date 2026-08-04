"""ADR-0043 M2-E: the frozen public contract of the runtime-conformance kit.

These tests pin the parts a consumer depends on and the parts that keep the
report honest: the public API surface, the report schema's identity and
strictness, the claim wording, and the source-level hygiene that makes a
conformance result mean what it says.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from nornyx_agentic_adapters import conformance
from nornyx_agentic_adapters.conformance import (
    CONFORMANCE_SCHEMA_ID,
    CONFORMANCE_SCHEMA_VERSION,
    CaseOutcome,
    CountCheck,
    EventOrder,
    ExecutionPath,
    SuiteOutcome,
    load_report_schema,
    validate_report,
)
from nornyx_agentic_adapters.conformance import harness as H
from nornyx_agentic_adapters.conformance import model as M

KIT_ROOT = Path(conformance.__file__).resolve().parent

#: Adding a name here is a reviewed change; removing or renaming one is a
#: breaking change to the adapter package's public surface.
FROZEN_SURFACE = {
    "ASSURANCE_TIER",
    "CONFORMANCE_SCHEMA_ID",
    "CONFORMANCE_SCHEMA_VERSION",
    "LIMITATIONS",
    "NON_GOALS",
    "CaseClassification",
    "CaseOutcome",
    "CaseResult",
    "ConformanceReport",
    "CountCheck",
    "EventOrder",
    "EvidenceValidation",
    "ExecutionPath",
    "OccurrenceSummary",
    "RunOutcome",
    "RunSafety",
    "SuiteOutcome",
    "SuiteResult",
    "available_suites",
    "load_report_schema",
    "run_conformance",
    "serialize",
    "validate_report",
    "write_report",
}


def test_public_surface_is_frozen() -> None:
    assert set(conformance.__all__) == FROZEN_SURFACE
    for name in FROZEN_SURFACE:
        assert hasattr(conformance, name), name


def test_schema_identity_is_pinned_and_distinct_from_static_v07() -> None:
    assert CONFORMANCE_SCHEMA_ID == "nornyx.agentic_runtime_conformance.v1"
    assert CONFORMANCE_SCHEMA_VERSION == "1.0"
    # The static report validates declared contract shape with execution
    # disabled and is depended on by bounded-execution readiness. Runtime
    # conformance executes adapters for real; sharing an identifier would make
    # one of the two reports a lie.
    assert CONFORMANCE_SCHEMA_ID != "nornyx.adapter_conformance.v0.7"
    schema = load_report_schema()
    assert schema["$id"] == CONFORMANCE_SCHEMA_ID
    assert "adapter_conformance_report" not in schema["$id"]


def test_bundled_schema_closes_every_object_definition() -> None:
    schema = load_report_schema()
    open_objects: list[str] = []

    def walk(node: object, pointer: str) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                if node.get("additionalProperties") is not False:
                    open_objects.append(pointer or "<root>")
            for key, value in node.items():
                walk(value, f"{pointer}/{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{pointer}/{index}")

    walk(schema, "")
    assert open_objects == []


@pytest.fixture(scope="module")
def valid_report() -> dict:
    """A minimal payload that validates, used to prove the schema *rejects*."""
    return {
        "schema": CONFORMANCE_SCHEMA_ID,
        "schema_version": CONFORMANCE_SCHEMA_VERSION,
        "adapter_name": "nornyx-agentic-adapters",
        "adapter_version": "0.2.0",
        "nornyx_version": "1.11.0",
        "spi_version": "1.2",
        "python_version": "3.13.0",
        "assurance_tier": "tier_2_cooperative",
        "outcome": "pass",
        "safety": {
            "adapter_actions_executed": True,
            "frameworks_executed": [],
            "guarded_suites": ["enforcement_boundary"],
            "blocked_outbound_attempts": 0,
            "blocked_process_attempts": 0,
            "scripted_in_process_model_called": False,
            "external_model_service_called": False,
            "external_connectors_used": False,
            "credentials_loaded": False,
        },
        "suites": [
            {
                "suite_id": "enforcement_boundary",
                "framework": "none",
                "outcome": "pass",
                "framework_version": "1.11.0",
                "declared_coverage": [],
                "cases": [
                    {
                        "case_id": "neutral.enforce.allow",
                        "framework": "none",
                        "surface": "enforce",
                        "declared_status": "not_declared",
                        "classification": "governed",
                        "outcome": "pass",
                        "execution_path": "boundary",
                        "action_executions": {"kind": "exact", "expected": 1, "observed": 1},
                        "authorizations": {"kind": "exact", "expected": 1, "observed": 1},
                        "decision_events": ["capability_requested"],
                        "observation_events": [],
                        "evidence_diagnostics": [],
                        "event_order": "recorded",
                        "evidence_validation": "pass",
                        "detail": "",
                    }
                ],
            }
        ],
        "limitations": ["Cooperative Tier 2, declared wrapped surfaces only."],
        "non_goals": ["Not an attestation of runtime truth."],
    }


def test_schema_accepts_a_well_formed_report(valid_report: dict) -> None:
    assert validate_report(valid_report) == ()


@pytest.mark.parametrize(
    "mutate,expected_fragment",
    [
        (lambda r: r.update({"totally_new_key": 1}), "totally_new_key"),
        (lambda r: r.update({"outcome": "green"}), "outcome"),
        (lambda r: r.update({"assurance_tier": "tier_3_independent"}), "assurance_tier"),
        (lambda r: r.update({"schema": "nornyx.adapter_conformance.v0.7"}), "schema"),
        (lambda r: r["suites"][0]["cases"][0].update({"outcome": "skipped"}), "outcome"),
        (lambda r: r["suites"][0]["cases"][0].update({"invented": True}), "invented"),
        (
            lambda r: r["suites"][0]["cases"][0].update({"declared_status": "partial"}),
            "declared_status",
        ),
        (
            lambda r: r["suites"][0]["cases"][0].update({"execution_path": "simulated"}),
            "execution_path",
        ),
    ],
)
def test_schema_rejects_invalid_reports(valid_report: dict, mutate, expected_fragment: str) -> None:
    payload = json.loads(json.dumps(valid_report))
    mutate(payload)
    diagnostics = validate_report(payload)
    assert diagnostics, f"schema accepted an invalid report ({expected_fragment})"
    assert any(expected_fragment in d for d in diagnostics), diagnostics


def test_schema_requires_a_reason_when_a_count_is_not_exact(valid_report: dict) -> None:
    payload = json.loads(json.dumps(valid_report))
    # An inexact count must say why it is inexact, so a reader can tell a
    # framework-controlled number from an adapter guarantee.
    payload["suites"][0]["cases"][0]["authorizations"] = {"kind": "at_least", "expected": 1}
    assert validate_report(payload), "an at_least count must state a reason"

    payload["suites"][0]["cases"][0]["authorizations"] = {
        "kind": "at_least",
        "expected": 1,
        "reason": "the framework executor controls repetition on this path",
    }
    assert validate_report(payload) == ()

    # ... and it may not smuggle an observed value back in: the whole point is
    # that the number is not reproducible.
    payload["suites"][0]["cases"][0]["authorizations"]["observed"] = 3
    assert validate_report(payload)


def test_schema_requires_a_reason_for_normalized_event_order(valid_report: dict) -> None:
    payload = json.loads(json.dumps(valid_report))
    payload["suites"][0]["cases"][0]["event_order"] = "normalized"
    assert validate_report(payload), "normalized order must state why"
    payload["suites"][0]["cases"][0]["normalization_reason"] = "executor-controlled retry"
    assert validate_report(payload) == ()


def test_not_representable_must_cross_reference_a_covering_case(valid_report: dict) -> None:
    payload = json.loads(json.dumps(valid_report))
    payload["suites"][0]["cases"][0]["outcome"] = "not_representable"
    assert validate_report(payload), "a not-representable case must name covered_by"
    payload["suites"][0]["cases"][0]["covered_by"] = "neutral.enforce.approval_required"
    assert validate_report(payload) == ()


def test_count_check_rejects_incoherent_combinations() -> None:
    with pytest.raises(ValueError):
        CountCheck("exact", 1)  # exact must record what it observed
    with pytest.raises(ValueError):
        CountCheck("at_least", 1, 3)  # at_least must not claim a value
    with pytest.raises(ValueError):
        CountCheck("at_least", 1)  # at_least must say why
    with pytest.raises(ValueError):
        CountCheck("approximately", 1, 1)


def test_case_result_rejects_unjustified_normalization() -> None:
    kwargs = dict(
        case_id="x",
        framework="none",
        surface="s",
        declared_status="not_declared",
        classification=M.CaseClassification.GOVERNED,
        outcome=CaseOutcome.PASS,
        action_executions=CountCheck("exact", 0, 0),
        authorizations=CountCheck("exact", 0, 0),
    )
    with pytest.raises(ValueError):
        M.CaseResult(**kwargs, event_order=EventOrder.NORMALIZED)
    with pytest.raises(ValueError):
        M.CaseResult(**kwargs, normalization_reason="unused")
    with pytest.raises(ValueError):
        M.CaseResult(**{**kwargs, "outcome": CaseOutcome.NOT_REPRESENTABLE})


# ------------------------------------------------------------------ claim integrity
def test_limitations_state_the_tier_2_boundary_verbatim() -> None:
    limitations = " ".join(M.LIMITATIONS)
    assert "Cooperative Tier 2, declared wrapped surfaces only." in M.LIMITATIONS
    for required in (
        "does not authenticate agents or approvers",
        "does not prove that a recorded runtime event is true",
        "does not prevent bypass",
        "does not imply whole-application coverage",
        "establishes no Tier 3",
        # The guard permits loopback, which is a real widening of "no network";
        # deleting that disclosure must fail a test, not pass quietly.
        "permits loopback",
        # The kit really does instantiate and drive a model abstraction. The
        # limitation must say "no external model service or endpoint", never a
        # bare "no model", which would be false on its ordinary reading.
        "no external model service or endpoint",
        "scripted, offline, in-process model",
    ):
        assert required in limitations, required


def test_limitations_never_assert_that_no_model_was_called() -> None:
    """The kit instantiates a model abstraction and CrewAI's executor calls it,
    so a bare "no model" claim would be false. Asserted negatively as well as
    positively: a newly added limitation reading "Conformance calls no model."
    would satisfy a presence-only check."""
    import re

    limitations = " ".join(M.LIMITATIONS)
    assert "no external model service or endpoint" in limitations
    assert "scripted, offline, in-process model" in limitations
    # Case-insensitive and singular/plural: "No model is called." and
    # "No models are called." must fail this too, not only the one bigram.
    assert not re.search(r"no\s+models?", limitations, re.IGNORECASE), limitations


def test_the_kit_makes_no_prohibited_assurance_claim() -> None:
    text = " ".join(M.LIMITATIONS + M.NON_GOALS + (M.ASSURANCE_TIER,)).lower()
    for prohibited in ("tamper-proof", "mandatory enforcement", "complete coverage"):
        assert prohibited not in text, prohibited
    assert M.ASSURANCE_TIER == "tier_2_cooperative"


def test_report_carries_no_permanent_test_count_as_a_product_claim() -> None:
    schema = load_report_schema()
    forbidden = {"tests_passed", "total_tests", "pass_rate", "score", "coverage_percent"}
    assert not forbidden & set(schema["properties"])


def test_declared_event_type_sets_match_the_installed_core() -> None:
    """The kit declares these sets itself so shipped code depends on no core
    internal; this test reaches into the core precisely so drift is caught."""
    from nornyx.agentic.authz import PHASE_INTENT, PHASE_OBSERVATION

    assert set(PHASE_INTENT) == set(H.DECISION_EVENT_TYPES)
    assert set(PHASE_OBSERVATION) == set(H.OBSERVATION_EVENT_TYPES)


# ------------------------------------------------------------------ source hygiene
def _kit_sources() -> list[Path]:
    return sorted(KIT_ROOT.rglob("*.py"))


def test_the_kit_never_resolves_a_path_above_its_own_package() -> None:
    """The fixture and schema must come from package resources.

    A ``parents[n]`` walk works in a source checkout and fails from an
    installed wheel, which is exactly the environment a conformance result is
    supposed to be meaningful in.
    """
    offenders: list[str] = []
    for path in _kit_sources():
        text = path.read_text(encoding="utf-8")
        for marker in ("parents[", "os.pardir", '".."', "'..'"):
            if marker in text:
                offenders.append(f"{path.name}: {marker}")
    assert offenders == []


def test_suites_never_record_evidence_themselves() -> None:
    """A suite that recorded its own events could manufacture any sequence it
    wanted; every event in the report must have come from the adapter."""
    recording = {
        "record_decision",
        "record_observation",
        "record_occurrence_decision",
        "record_occurrence_observation",
    }
    offenders: list[str] = []
    for path in sorted((KIT_ROOT / "suites").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in recording:
                    offenders.append(f"{path.name}:{node.lineno} calls {node.func.attr}")
    assert offenders == []


def test_no_framework_is_imported_at_kit_import_time() -> None:
    """Importing the kit must not import an agent framework, so the base
    install keeps working without extras."""
    for path in (KIT_ROOT / "__init__.py", KIT_ROOT / "runner.py", KIT_ROOT / "harness.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            roots: list[str] = []
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots = [node.module.split(".")[0]]
            assert not ({"crewai", "langgraph"} & set(roots)), f"{path.name}: {roots}"


def test_enum_values_are_stable_strings() -> None:
    assert {m.value for m in CaseOutcome} == {"pass", "fail", "not_representable"}
    assert {m.value for m in SuiteOutcome} == {"pass", "fail", "unavailable"}
    assert {m.value for m in ExecutionPath} == {"native", "direct", "boundary"}
    assert {m.value for m in EventOrder} == {"recorded", "normalized"}
