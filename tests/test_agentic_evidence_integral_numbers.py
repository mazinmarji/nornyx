"""Validator: whole-number floats in integer fields reach every semantic check.

The runtime-events schema types ``sequence`` and ``occurrence.attempt`` as JSON
Schema integers, and JSON Schema accepts a whole-number float such as ``2.0``
as an integer. A value the schema accepts must not silently skip the
validator's semantic checks, so a stream written with whole-number floats must
get exactly the diagnostics of the same stream written with integers. Values
the schema rejects (booleans, fractions, non-finite or out-of-range numbers)
are not converted and still fail.
"""

from __future__ import annotations

import json
import math
import shutil
from contextlib import redirect_stdout
from copy import deepcopy
from enum import IntEnum
from io import StringIO
from pathlib import Path

import pytest
import yaml

from nornyx.agentic import (
    Authorizer,
    CapabilityRequest,
    EvaluationContext,
    EvidenceRecorder,
    GovernanceRegistry,
    RuntimeOccurrence,
    build_agentic_network_lock,
    compose_document_governance,
    validate_runtime_events,
)
from nornyx.agentic_artifacts import (
    _build_agentic_network_lock,
    write_agentic_network_lock,
)
from nornyx.cli import main as cli_main
from nornyx.governance.schemas import load_bundled_schema


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "agentic_network.nyx"
AS_OF = "2026-07-17T10:00:00Z"
LATER = "2026-07-17T11:00:00Z"
OCCURRENCE = RuntimeOccurrence("node.read", "task.a", 1)
OBSERVATION = {
    "actor_ref": "identity.researcher.local",
    "capability_ref": "read_governed_context",
}
PRODUCER = {"producer_id": "producer-tests", "producer_type": "synthetic_harness"}
MODES = ["1.0", "1.1-legacy", "1.1-explicit"]


@pytest.fixture(scope="module")
def setup():
    document = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    composition = compose_document_governance(
        document, registry=GovernanceRegistry.builtins()
    )
    return document, composition


def _authorizer(setup, mode: str) -> tuple[Authorizer, dict]:
    document, composition = setup
    if mode == "1.0":
        lock = _build_agentic_network_lock(
            document, composition, runtime_events_schema_version="1.0"
        )
    else:
        lock = build_agentic_network_lock(document, composition)
    return Authorizer(document, composition, lock), lock


def _decision(authorizer: Authorizer, context: EvaluationContext):
    return authorizer.evaluate(
        CapabilityRequest("identity.researcher.local", "read_governed_context"),
        context=context,
    )


def _recorded(setup, mode: str) -> tuple[dict, dict]:
    """A valid three-event recorder stream (requested, allowed, invoked)."""

    authorizer, lock = _authorizer(setup, mode)
    context = EvaluationContext(AS_OF, authorizer.subject_revision)
    decision = _decision(authorizer, context)
    if mode == "1.1-explicit":
        recorder = EvidenceRecorder.for_occurrences(authorizer, context, **PRODUCER)
        recorder.record_occurrence_decision(
            decision, mission_id="GOAL-001", occurrence=OCCURRENCE
        )
        recorder.record_occurrence_observation(
            "tool_invoked", mission_id="GOAL-001", occurrence=OCCURRENCE, **OBSERVATION
        )
    else:
        recorder = EvidenceRecorder(authorizer, context, **PRODUCER)
        recorder.record_decision(decision, mission_id="GOAL-001")
        recorder.record_observation("tool_invoked", mission_id="GOAL-001", **OBSERVATION)
    stream = recorder.stream()
    assert [event["sequence"] for event in stream["events"]] == [1, 2, 3]
    return stream, lock


def _validate(setup, lock: dict, stream: dict) -> dict:
    document, composition = setup
    return validate_runtime_events(document, composition, lock, stream)


def _diagnostics(report: dict) -> list[tuple[str, str]]:
    return sorted((item["code"], item["path"]) for item in report["diagnostics"])


def _codes(report: dict) -> set[str]:
    return {item["code"] for item in report["diagnostics"]}


def _float_event(event: dict) -> None:
    event["sequence"] = float(event["sequence"])
    occurrence = event.get("occurrence")
    if isinstance(occurrence, dict):
        occurrence["attempt"] = float(occurrence["attempt"])


def _as_floats(stream: dict, *, only: int | None = None) -> dict:
    """The same stream with integer fields written as whole-number floats."""

    floated = deepcopy(stream)
    for index, event in enumerate(floated["events"]):
        if only is None or index == only:
            _float_event(event)
    return floated


def _appended(stream: dict, **fields) -> int:
    """Append a copy of the last event with ``fields`` replaced; return its index."""

    event = deepcopy(stream["events"][-1])
    event.update(fields)
    stream["events"].append(event)
    return len(stream["events"]) - 1


# Each mutation turns a valid stream into one the validator must reject,
# using integers, and returns the index of the event it targets.


def _missing_allowance(stream: dict, mode: str) -> int:
    del stream["events"][1]
    stream["events"][1]["sequence"] = 2
    return 1


def _duplicate_sequence(stream: dict, mode: str) -> int:
    stream["events"][2]["sequence"] = 2
    return 2


def _sequence_gap(stream: dict, mode: str) -> int:
    stream["events"][2]["sequence"] = 5
    return 2


def _dependency_after_dependent(stream: dict, mode: str) -> int:
    stream["events"][1]["depends_on"] = [stream["events"][2]["event_id"]]
    return 2


def _approval_without_request(stream: dict, mode: str) -> int:
    index = _appended(
        stream,
        event_id="GOAL-001-0004",
        sequence=4,
        event_type="approval_granted",
        approval_ref="agentic_network_authority",
        approver={"role": "network_governance_owner", "actor_type": "human"},
    )
    del stream["events"][index]["capability_ref"]
    return index


def _delegation_without_request(stream: dict, mode: str) -> int:
    index = _appended(
        stream,
        event_id="GOAL-001-0004",
        sequence=4,
        event_type="delegation_accepted",
        delegation_ref="delegation.research",
    )
    del stream["events"][index]["capability_ref"]
    return index


def _handoff_without_initiation(stream: dict, mode: str) -> int:
    index = _appended(
        stream,
        event_id="GOAL-001-0004",
        sequence=4,
        event_type="handoff_completed",
        handoff_ref="handoff.review",
        target_ref="identity.reviewer.local",
    )
    del stream["events"][index]["capability_ref"]
    return index


def _second_terminal_outcome(stream: dict, mode: str) -> int:
    return _appended(
        stream, event_id="GOAL-001-0004", sequence=4, event_type="agent_invoked"
    )


def _retry_after_success(stream: dict, mode: str) -> int:
    index = _appended(stream, event_id="GOAL-001-0004", sequence=4)
    stream["events"][index]["occurrence"]["attempt"] = 2
    return index


def _attempt_gap(stream: dict, mode: str) -> int:
    index = _appended(
        stream, event_id="GOAL-001-0004", sequence=4, event_type="runtime_failed"
    )
    stream["events"][index]["occurrence"]["attempt"] = 3
    return index


MUTATIONS = {
    "missing_allowance": (_missing_allowance, "AN_EVT_TOOL_WITHOUT_ALLOWANCE", MODES),
    "duplicate_sequence": (_duplicate_sequence, "AN_EVT_DUPLICATE_SEQUENCE", MODES),
    "sequence_gap": (_sequence_gap, "AN_EVT_SEQUENCE_GAP", MODES),
    "dependency_order": (_dependency_after_dependent, "AN_EVT_ORDER_INVALID", MODES),
    "approval_without_request": (
        _approval_without_request,
        "AN_EVT_GRANT_WITHOUT_REQUEST",
        MODES,
    ),
    "delegation_without_request": (
        _delegation_without_request,
        "AN_EVT_ACCEPTANCE_WITHOUT_REQUEST",
        MODES,
    ),
    "handoff_without_initiation": (
        _handoff_without_initiation,
        "AN_EVT_COMPLETION_WITHOUT_INITIATION",
        MODES,
    ),
    "second_terminal_outcome": (
        _second_terminal_outcome,
        "AN_EVT_ATTEMPT_OUTCOME_CONTRADICTION",
        ["1.1-explicit"],
    ),
    "retry_after_success": (
        _retry_after_success,
        "AN_EVT_ATTEMPT_AFTER_SUCCESS",
        ["1.1-explicit"],
    ),
    "attempt_gap": (_attempt_gap, "AN_EVT_ATTEMPT_GAP", ["1.1-explicit"]),
}
MUTATION_CASES = [
    pytest.param(name, mode, id=f"{name}-{mode}")
    for name, (_, _, modes) in MUTATIONS.items()
    for mode in modes
]


@pytest.mark.parametrize("floats", ["all", "target"])
@pytest.mark.parametrize("name, mode", MUTATION_CASES)
def test_whole_float_numbers_get_the_integer_verdict(setup, name, mode, floats) -> None:
    mutate, expected_code, _ = MUTATIONS[name]
    stream, lock = _recorded(setup, mode)
    target = mutate(stream, mode)
    integer_report = _validate(setup, lock, stream)
    assert integer_report["status"] == "fail"
    assert expected_code in _codes(integer_report)

    floated = _as_floats(stream, only=None if floats == "all" else target)
    float_report = _validate(setup, lock, floated)
    assert float_report["status"] == "fail"
    assert _diagnostics(float_report) == _diagnostics(integer_report)
    assert float_report["mission_count"] == integer_report["mission_count"]


@pytest.mark.parametrize("mode", MODES)
def test_valid_stream_with_whole_float_numbers_still_passes(setup, mode) -> None:
    stream, lock = _recorded(setup, mode)
    report = _validate(setup, lock, _as_floats(stream))
    assert report["status"] == "pass", report["diagnostics"]
    assert report["mission_count"] == 1


@pytest.mark.parametrize("mode", MODES)
def test_validation_does_not_modify_the_supplied_stream(setup, mode) -> None:
    stream, lock = _recorded(setup, mode)
    floated = _as_floats(stream)
    snapshot = json.dumps(floated, sort_keys=True)
    _validate(setup, lock, floated)
    # json.dumps tells 2.0 from 2, which == does not.
    assert json.dumps(floated, sort_keys=True) == snapshot


def test_whole_float_attempt_cannot_evade_replay_detection(setup) -> None:
    # Replay compares event content without event_id and sequence, so an
    # attempt written as 1.0 must not make an exact replay look different.
    stream, lock = _recorded(setup, "1.1-explicit")
    index = _appended(stream, event_id="GOAL-001-0004", sequence=4)
    assert "AN_EVT_REPLAY" in _codes(_validate(setup, lock, stream))
    stream["events"][index]["occurrence"]["attempt"] = 1.0
    assert "AN_EVT_REPLAY" in _codes(_validate(setup, lock, stream))


SCHEMA_REJECTED_NUMBERS = [
    pytest.param(True, id="true"),
    pytest.param(False, id="false"),
    pytest.param(2.5, id="fraction"),
    pytest.param(1.0000001, id="near-whole"),
    pytest.param(math.nan, id="nan"),
    pytest.param(math.inf, id="inf"),
    pytest.param(-math.inf, id="-inf"),
    pytest.param(0.0, id="zero"),
    pytest.param(-0.0, id="negative-zero"),
    pytest.param(-2.0, id="negative"),
    pytest.param(1_000_001.0, id="above-maximum"),
    pytest.param(1e300, id="huge-float"),
    pytest.param(2**64, id="huge-int"),
    pytest.param("2", id="string"),
]


@pytest.mark.parametrize("value", SCHEMA_REJECTED_NUMBERS)
@pytest.mark.parametrize("mode", MODES)
def test_schema_rejected_sequence_still_fails(setup, mode, value) -> None:
    stream, lock = _recorded(setup, mode)
    stream["events"][2]["sequence"] = value
    report = _validate(setup, lock, stream)
    assert report["status"] == "fail"
    assert "AN_EVT_SCHEMA_INVALID" in _codes(report)


@pytest.mark.parametrize("value", SCHEMA_REJECTED_NUMBERS)
def test_schema_rejected_attempt_still_fails(setup, value) -> None:
    stream, lock = _recorded(setup, "1.1-explicit")
    stream["events"][2]["occurrence"]["attempt"] = value
    report = _validate(setup, lock, stream)
    assert report["status"] == "fail"
    assert "AN_EVT_SCHEMA_INVALID" in _codes(report)


@pytest.mark.parametrize("value", SCHEMA_REJECTED_NUMBERS)
def test_only_schema_valid_whole_floats_are_converted(value) -> None:
    from nornyx.agentic_evidence import _schema_integer

    result = _schema_integer(value)
    assert result is value


@pytest.mark.parametrize(
    "value, expected", [(1.0, 1), (2.0, 2), (1_000_000.0, 1_000_000), (7, 7)]
)
def test_schema_valid_whole_floats_become_exact_ints(value, expected) -> None:
    from nornyx.agentic_evidence import _schema_integer

    result = _schema_integer(value)
    assert type(result) is int
    assert result == expected


def test_conversion_bounds_match_the_bundled_schema() -> None:
    from nornyx.agentic_evidence import _schema_integer

    schema = load_bundled_schema("agentic_runtime_events_v1.schema.json")
    defs = schema["$defs"]
    for field in (
        defs["event"]["properties"]["sequence"],
        defs["occurrence"]["properties"]["attempt"],
    ):
        assert field["type"] == "integer"
        assert type(_schema_integer(float(field["minimum"]))) is int
        assert type(_schema_integer(float(field["maximum"]))) is int
        assert type(_schema_integer(float(field["minimum"] - 1))) is float
        assert type(_schema_integer(float(field["maximum"] + 1))) is float


class _Float(float):
    """A plain float subclass, as numpy.float64 is."""


class _Int(int):
    """A plain int subclass."""


class _Attempt(IntEnum):
    TWO = 2


@pytest.mark.parametrize(
    "value, expected",
    [(_Float(2.0), 2), (_Int(2), 2), (_Attempt.TWO, 2), (_Float(1_000_000.0), 1_000_000)],
)
def test_schema_valid_subclass_numbers_become_exact_ints(value, expected) -> None:
    from nornyx.agentic_evidence import _schema_integer

    result = _schema_integer(value)
    assert type(result) is int
    assert result == expected


@pytest.mark.parametrize(
    "value", [_Float(2.5), _Float(math.nan), _Float(0.0), _Int(0), _Int(1_000_001)]
)
def test_schema_rejected_subclass_numbers_are_not_converted(value) -> None:
    from nornyx.agentic_evidence import _schema_integer

    assert _schema_integer(value) is value


@pytest.mark.parametrize("number", [_Float, _Int])
@pytest.mark.parametrize("mode", MODES)
def test_subclass_sequence_gets_the_integer_verdict(setup, mode, number) -> None:
    # The direct API can receive numbers the JSON loader never produces, such
    # as numpy.float64; the schema accepts them, so the checks must see them.
    stream, lock = _recorded(setup, mode)
    target = _missing_allowance(stream, mode)
    integer_report = _validate(setup, lock, stream)
    stream["events"][target]["sequence"] = number(stream["events"][target]["sequence"])
    report = _validate(setup, lock, stream)
    assert "AN_EVT_TOOL_WITHOUT_ALLOWANCE" in _codes(report)
    assert _diagnostics(report) == _diagnostics(integer_report)


@pytest.mark.parametrize("attempt", [_Float(2.0), _Int(2), _Attempt.TWO])
def test_subclass_attempt_gets_the_integer_verdict(setup, attempt) -> None:
    stream, lock = _recorded(setup, "1.1-explicit")
    target = _retry_after_success(stream, "1.1-explicit")
    integer_report = _validate(setup, lock, stream)
    stream["events"][target]["occurrence"]["attempt"] = attempt
    report = _validate(setup, lock, stream)
    assert "AN_EVT_ATTEMPT_AFTER_SUCCESS" in _codes(report)
    assert _diagnostics(report) == _diagnostics(integer_report)


def _run_cli(setup, lock: dict, stream: dict, tmp_path: Path, name: str) -> tuple[int, dict]:
    document, _ = setup
    contract = tmp_path / "contract.nyx"
    if not contract.exists():
        shutil.copytree(
            EXAMPLE.parent / "governance_evidence", tmp_path / "governance_evidence"
        )
        contract.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    lock_path = tmp_path / f"{name}.lock"
    write_agentic_network_lock(lock, lock_path)
    events_path = tmp_path / f"{name}.json"
    events_path.write_text(json.dumps(stream, indent=2), encoding="utf-8")
    report_path = tmp_path / f"{name}.report.json"
    with redirect_stdout(StringIO()):
        code = cli_main(
            [
                "agentic-network",
                "evidence-validate",
                str(contract),
                "--events",
                str(events_path),
                "--lock",
                str(lock_path),
                "--as-of",
                "2026-07-17T00:00:00Z",
                "--out",
                str(report_path),
                "--strict",
            ]
        )
    return code, json.loads(report_path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("mode", MODES)
def test_cli_gives_the_same_verdict_for_2_and_2_0(setup, mode, tmp_path) -> None:
    stream, lock = _recorded(setup, mode)
    target = _missing_allowance(stream, mode)
    floated = _as_floats(stream, only=target)
    text = json.dumps(floated)
    assert '"sequence": 2.0' in text

    integer_code, integer_report = _run_cli(setup, lock, stream, tmp_path, "int")
    float_code, float_report = _run_cli(setup, lock, floated, tmp_path, "float")
    assert integer_code == 1
    assert "AN_EVT_TOOL_WITHOUT_ALLOWANCE" in _codes(integer_report)
    assert float_code == 1
    assert _diagnostics(float_report) == _diagnostics(integer_report)


@pytest.mark.parametrize("mode", MODES)
def test_resume_refuses_a_float_prefix_the_validator_rejects(setup, mode) -> None:
    stream, _ = _recorded(setup, mode)
    target = _missing_allowance(stream, mode)
    floated = _as_floats(stream, only=target)
    authorizer, _ = _authorizer(setup, mode)
    context = EvaluationContext(LATER, authorizer.subject_revision)
    with pytest.raises(ValueError, match="AN_EVT_TOOL_WITHOUT_ALLOWANCE"):
        EvidenceRecorder.resume(authorizer, context, floated, **PRODUCER)


@pytest.mark.parametrize("mode", MODES)
def test_resume_stores_whole_float_numbers_as_ints_and_continues(setup, mode) -> None:
    stream, _ = _recorded(setup, mode)
    floated = _as_floats(stream)
    authorizer, _ = _authorizer(setup, mode)
    context = EvaluationContext(LATER, authorizer.subject_revision)
    recorder = EvidenceRecorder.resume(authorizer, context, floated, **PRODUCER)

    prefix = recorder.stream()["events"]
    assert [event["sequence"] for event in prefix] == [1, 2, 3]
    assert all(type(event["sequence"]) is int for event in prefix)
    if mode == "1.1-explicit":
        assert all(type(event["occurrence"]["attempt"]) is int for event in prefix)

    decision = _decision(authorizer, context)
    if mode == "1.1-explicit":
        recorder.record_occurrence_decision(
            decision,
            mission_id="GOAL-001",
            occurrence=RuntimeOccurrence("node.read", "task.b", 1),
        )
    else:
        recorder.record_decision(decision, mission_id="GOAL-001")
    events = recorder.stream()["events"]
    assert [event["sequence"] for event in events] == [1, 2, 3, 4, 5]
    report = recorder.validate()
    assert report["status"] == "pass", report["diagnostics"]


def test_resumed_whole_float_attempt_counts_as_recorded(setup) -> None:
    stream, _ = _recorded(setup, "1.1-explicit")
    authorizer, _ = _authorizer(setup, "1.1-explicit")
    context = EvaluationContext(LATER, authorizer.subject_revision)
    recorder = EvidenceRecorder.resume(
        authorizer, context, _as_floats(stream), **PRODUCER
    )
    assert (
        recorder.max_recorded_attempt(
            mission_id="GOAL-001", operation_id="node.read", occurrence_id="task.a"
        )
        == 1
    )
