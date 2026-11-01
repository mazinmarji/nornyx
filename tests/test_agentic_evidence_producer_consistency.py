"""Validator: every runtime event's producer equals the envelope producer.

This is internal consistency of the supplied stream. It never authenticates a
producer or proves that an event happened.
"""

from __future__ import annotations

from copy import deepcopy
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
from nornyx.agentic_artifacts import _build_agentic_network_lock


ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-07-17T10:00:00Z"
OCCURRENCE = RuntimeOccurrence("node.read", "task.a", 1)
OBSERVATION = {
    "actor_ref": "identity.researcher.local",
    "capability_ref": "read_governed_context",
}
PRODUCER = {"producer_id": "producer-tests", "producer_type": "synthetic_harness"}
OTHER_PRODUCER = {"type": "external_runtime", "id": "someone-else", "version": "9.9"}
MODES = ["1.0", "1.1-legacy", "1.1-explicit"]


@pytest.fixture(scope="module")
def setup():
    document = yaml.safe_load(
        (ROOT / "examples" / "agentic_network.nyx").read_text(encoding="utf-8")
    )
    composition = compose_document_governance(
        document, registry=GovernanceRegistry.builtins()
    )
    return document, composition


def _recorded(setup, mode: str) -> tuple[dict, dict]:
    """A valid recorder-built stream with at least three events, and its lock."""

    document, composition = setup
    if mode == "1.0":
        lock = _build_agentic_network_lock(
            document, composition, runtime_events_schema_version="1.0"
        )
    else:
        lock = build_agentic_network_lock(document, composition)
    authorizer = Authorizer(document, composition, lock)
    context = EvaluationContext(AS_OF, authorizer.subject_revision)
    decision = authorizer.evaluate(
        CapabilityRequest("identity.researcher.local", "read_governed_context"),
        context=context,
    )
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
    assert len(stream["events"]) >= 3
    return stream, lock


def _validate(setup, lock: dict, stream: dict) -> dict:
    document, composition = setup
    return validate_runtime_events(document, composition, lock, stream)


def _mismatch_paths(report: dict) -> list[str]:
    return [
        item["path"]
        for item in report["diagnostics"]
        if item["code"] == "AN_EVT_PRODUCER_MISMATCH"
    ]


@pytest.mark.parametrize("mode", MODES)
def test_consistent_producers_still_pass(setup, mode) -> None:
    stream, lock = _recorded(setup, mode)
    report = _validate(setup, lock, stream)
    assert report["status"] == "pass", report["diagnostics"]
    assert _mismatch_paths(report) == []


@pytest.mark.parametrize("mode", MODES)
def test_one_event_naming_another_producer_fails(setup, mode) -> None:
    stream, lock = _recorded(setup, mode)
    stream["events"][1]["producer"] = dict(OTHER_PRODUCER)
    report = _validate(setup, lock, stream)
    assert report["status"] == "fail"
    assert _mismatch_paths(report) == ["events[1].producer"]


@pytest.mark.parametrize("mode", MODES)
def test_every_event_naming_another_producer_fails(setup, mode) -> None:
    stream, lock = _recorded(setup, mode)
    for event in stream["events"]:
        event["producer"] = dict(OTHER_PRODUCER)
    report = _validate(setup, lock, stream)
    assert report["status"] == "fail"
    # Diagnostics sort by path string, so compare as sets.
    assert set(_mismatch_paths(report)) == {
        f"events[{index}].producer" for index in range(len(stream["events"]))
    }


@pytest.mark.parametrize("mode", MODES)
def test_envelope_naming_another_producer_fails(setup, mode) -> None:
    stream, lock = _recorded(setup, mode)
    stream["producer"] = dict(OTHER_PRODUCER)
    report = _validate(setup, lock, stream)
    assert report["status"] == "fail"
    assert len(_mismatch_paths(report)) == len(stream["events"])


@pytest.mark.parametrize("field", ["type", "id", "version"])
@pytest.mark.parametrize("mode", MODES)
def test_any_single_producer_field_difference_fails(setup, mode, field) -> None:
    stream, lock = _recorded(setup, mode)
    producer = deepcopy(stream["producer"])
    producer[field] = (
        "external_runtime" if field == "type" else f"other-{producer[field]}"
    )
    stream["events"][0]["producer"] = producer
    report = _validate(setup, lock, stream)
    assert report["status"] == "fail"
    assert _mismatch_paths(report) == ["events[0].producer"]


@pytest.mark.parametrize("mode", MODES)
def test_missing_or_non_object_producers_are_left_to_the_schema(setup, mode) -> None:
    stream, lock = _recorded(setup, mode)
    del stream["events"][0]["producer"]
    stream["events"][1]["producer"] = "not-an-object"
    report = _validate(setup, lock, stream)
    codes = {item["code"] for item in report["diagnostics"]}
    assert "AN_EVT_SCHEMA_INVALID" in codes
    assert _mismatch_paths(report) == []


@pytest.mark.parametrize("mode", MODES)
def test_malformed_object_producer_is_reported_by_schema_and_mismatch(setup, mode) -> None:
    stream, lock = _recorded(setup, mode)
    producer = deepcopy(stream["producer"])
    del producer["version"]
    stream["events"][0]["producer"] = producer
    report = _validate(setup, lock, stream)
    codes = {item["code"] for item in report["diagnostics"]}
    assert "AN_EVT_SCHEMA_INVALID" in codes
    # The schema diagnostic cannot name the event; the mismatch does.
    assert _mismatch_paths(report) == ["events[0].producer"]


@pytest.mark.parametrize("mode", MODES)
def test_reordered_producer_keys_still_pass(setup, mode) -> None:
    stream, lock = _recorded(setup, mode)
    for event in stream["events"]:
        event["producer"] = dict(reversed(list(event["producer"].items())))
    assert list(stream["events"][0]["producer"]) != list(stream["producer"])
    report = _validate(setup, lock, stream)
    assert report["status"] == "pass", report["diagnostics"]


@pytest.mark.parametrize("mode", MODES)
def test_duplicate_event_id_is_still_reported_alongside_a_mismatch(setup, mode) -> None:
    stream, lock = _recorded(setup, mode)
    stream["events"][1]["event_id"] = stream["events"][0]["event_id"]
    stream["events"][1]["producer"] = dict(OTHER_PRODUCER)
    report = _validate(setup, lock, stream)
    codes = {item["code"] for item in report["diagnostics"]}
    assert "AN_EVT_DUPLICATE_ID" in codes
    assert _mismatch_paths(report) == ["events[1].producer"]


def test_recorder_decision_events_carry_the_envelope_producer(setup) -> None:
    # Guards the recorder side of the rule: every recorded event is stamped
    # with exactly the envelope producer, so recorder streams never trip it.
    stream, _ = _recorded(setup, "1.1-legacy")
    assert all(event["producer"] == stream["producer"] for event in stream["events"])
