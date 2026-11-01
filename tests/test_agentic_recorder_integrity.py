"""EvidenceRecorder envelope and recording-mode integrity on every write path."""

from __future__ import annotations

import dataclasses
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
)
from nornyx.agentic_artifacts import _build_agentic_network_lock


ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-07-17T10:00:00Z"
OCCURRENCE = RuntimeOccurrence("node.read", "task.a", 1)
OBSERVATION = {
    "actor_ref": "identity.researcher.local",
    "capability_ref": "read_governed_context",
}
PRODUCER = {"producer_id": "integrity-tests", "producer_type": "synthetic_harness"}

# One value per recorder-stamped key, each different from what the recorder stamps.
ENVELOPE_OVERRIDES = {
    "producer": {"type": "external_runtime", "id": "someone-else", "version": "9.9"},
    "timestamp": "2026-01-01T00:00:00Z",
    "event_id": "GOAL-001-0099",
    "sequence": 7,
    "network_id": "other.network",
    "contract_digest": "sha256:" + "0" * 64,
    "network_lock_digest": "sha256:" + "0" * 64,
    "subject_revision": "other-revision",
    "mission_id": "GOAL-999",
    "event_type": "capability_denied",
}
# event_type and mission_id are named parameters of the observation calls, so
# Python itself refuses them as **fields there.
OBSERVATION_OVERRIDES = sorted(set(ENVELOPE_OVERRIDES) - {"event_type", "mission_id"})


@pytest.fixture(scope="module")
def runtime() -> tuple[Authorizer, EvaluationContext]:
    document = yaml.safe_load(
        (ROOT / "examples" / "agentic_network.nyx").read_text(encoding="utf-8")
    )
    composition = compose_document_governance(
        document, registry=GovernanceRegistry.builtins()
    )
    lock = build_agentic_network_lock(document, composition)
    authorizer = Authorizer(document, composition, lock)
    return authorizer, EvaluationContext(AS_OF, authorizer.subject_revision)


def _legacy(runtime, schema_version: str = "1.1", cls=EvidenceRecorder) -> EvidenceRecorder:
    authorizer, context = runtime
    if schema_version == "1.0":
        state = authorizer.state
        lock = _build_agentic_network_lock(
            state.document, state.composition, runtime_events_schema_version="1.0"
        )
        authorizer = Authorizer(state.document, state.composition, lock)
    return cls(authorizer, context, **PRODUCER)


def _explicit(runtime, cls=EvidenceRecorder) -> EvidenceRecorder:
    authorizer, context = runtime
    return cls.for_occurrences(authorizer, context, **PRODUCER)


def _decision(runtime, **extra_fields):
    authorizer, context = runtime
    decision = authorizer.evaluate(
        CapabilityRequest("identity.researcher.local", "read_governed_context"),
        context=context,
    )
    return dataclasses.replace(
        decision,
        event_intents=tuple(
            dataclasses.replace(intent, fields={**intent.fields, **extra_fields})
            for intent in decision.event_intents
        ),
    )


def _assert_refused_without_mutation(recorder: EvidenceRecorder, call, match: str) -> None:
    before = recorder.stream()
    with pytest.raises(ValueError, match=match):
        call()
    assert recorder.stream() == before
    assert recorder.validate()["status"] == "pass"


# --- caller fields cannot replace recorder-stamped envelope keys -------------


@pytest.mark.parametrize("key", OBSERVATION_OVERRIDES)
@pytest.mark.parametrize("mode", ["legacy", "explicit"])
def test_observation_fields_cannot_override_envelope_keys(runtime, mode, key) -> None:
    fields = {**OBSERVATION, key: ENVELOPE_OVERRIDES[key]}
    if mode == "legacy":
        recorder = _legacy(runtime)
        call = lambda: recorder.record_observation(  # noqa: E731
            "tool_invoked", mission_id="GOAL-001", **fields
        )
    else:
        recorder = _explicit(runtime)
        call = lambda: recorder.record_occurrence_observation(  # noqa: E731
            "tool_invoked", mission_id="GOAL-001", occurrence=OCCURRENCE, **fields
        )
    _assert_refused_without_mutation(recorder, call, f"cannot override {key}")


@pytest.mark.parametrize("key", sorted(ENVELOPE_OVERRIDES))
@pytest.mark.parametrize("mode", ["legacy", "explicit"])
def test_decision_intent_fields_cannot_override_envelope_keys(runtime, mode, key) -> None:
    decision = _decision(runtime, **{key: ENVELOPE_OVERRIDES[key]})
    if mode == "legacy":
        recorder = _legacy(runtime)
        call = lambda: recorder.record_decision(decision, mission_id="GOAL-001")  # noqa: E731
    else:
        recorder = _explicit(runtime)
        call = lambda: recorder.record_occurrence_decision(  # noqa: E731
            decision, mission_id="GOAL-001", occurrence=OCCURRENCE
        )
    _assert_refused_without_mutation(recorder, call, f"cannot override {key}")


def test_refused_override_leaves_sequence_state_untouched(runtime) -> None:
    recorder = _legacy(runtime)
    recorder.record_decision(_decision(runtime), mission_id="GOAL-001")
    with pytest.raises(ValueError, match="cannot override producer"):
        recorder.record_observation(
            "tool_invoked",
            mission_id="GOAL-001",
            **OBSERVATION,
            producer=ENVELOPE_OVERRIDES["producer"],
        )
    recorder.record_observation("tool_invoked", mission_id="GOAL-001", **OBSERVATION)
    events = recorder.stream()["events"]
    assert [event["sequence"] for event in events] == [1, 2, 3]
    assert {event["producer"]["id"] for event in events} == {"integrity-tests"}
    assert recorder.validate()["status"] == "pass"


# --- legacy recorders record no occurrence ------------------------------------


@pytest.mark.parametrize("schema_version", ["1.0", "1.1"])
@pytest.mark.parametrize("call", ["record_decision", "record_observation"])
def test_legacy_recorders_refuse_a_caller_supplied_occurrence(
    runtime, schema_version, call
) -> None:
    occurrence = {"operation_id": "node.read", "occurrence_id": "task.a", "attempt": 1}
    recorder = _legacy(runtime, schema_version)
    calls = {
        "record_decision": lambda: recorder.record_decision(
            _decision(runtime, occurrence=occurrence), mission_id="GOAL-001"
        ),
        "record_observation": lambda: recorder.record_observation(
            "tool_invoked", mission_id="GOAL-001", **OBSERVATION, occurrence=occurrence
        ),
    }
    _assert_refused_without_mutation(recorder, calls[call], "cannot override occurrence")


# --- private and subclass write paths -----------------------------------------


def test_direct_stamp_cannot_append_an_occurrence_less_event_to_an_explicit_stream(
    runtime,
) -> None:
    recorder = _explicit(runtime)
    _assert_refused_without_mutation(
        recorder,
        lambda: recorder._stamp("tool_invoked", "GOAL-001", OBSERVATION),
        "explicit occurrence mode",
    )


class _DropsOccurrence(EvidenceRecorder):
    def _build_event_unlocked(self, event_type, mission_id, seq, fields):
        event = super()._build_event_unlocked(event_type, mission_id, seq, fields)
        event.pop("occurrence", None)
        return event


class _AddsOccurrence(EvidenceRecorder):
    def _build_event_unlocked(self, event_type, mission_id, seq, fields):
        event = super()._build_event_unlocked(event_type, mission_id, seq, fields)
        event["occurrence"] = {"operation_id": "x", "occurrence_id": "y", "attempt": 1}
        return event


class _SpoofsProducer(EvidenceRecorder):
    def _build_event_unlocked(self, event_type, mission_id, seq, fields):
        event = super()._build_event_unlocked(event_type, mission_id, seq, fields)
        event["producer"] = dict(ENVELOPE_OVERRIDES["producer"])
        return event


class _ShiftsSequence(EvidenceRecorder):
    def _build_event_unlocked(self, event_type, mission_id, seq, fields):
        return super()._build_event_unlocked(event_type, mission_id, seq + 1, fields)


@pytest.mark.parametrize(
    ("cls", "mode", "match"),
    [
        (_DropsOccurrence, "explicit", "explicit occurrence mode"),
        (_AddsOccurrence, "legacy", "legacy recording"),
        (_SpoofsProducer, "legacy", "producer"),
        (_SpoofsProducer, "explicit", "producer"),
        (_ShiftsSequence, "legacy", "sequence"),
    ],
)
@pytest.mark.parametrize("path", ["decision", "observation"])
def test_builder_overrides_cannot_commit_an_inconsistent_event(
    runtime, cls, mode, match, path
) -> None:
    if mode == "legacy":
        recorder = _legacy(runtime, cls=cls)
        calls = {
            "decision": lambda: recorder.record_decision(
                _decision(runtime), mission_id="GOAL-001"
            ),
            "observation": lambda: recorder.record_observation(
                "tool_invoked", mission_id="GOAL-001", **OBSERVATION
            ),
        }
    else:
        recorder = _explicit(runtime, cls=cls)
        calls = {
            "decision": lambda: recorder.record_occurrence_decision(
                _decision(runtime), mission_id="GOAL-001", occurrence=OCCURRENCE
            ),
            "observation": lambda: recorder.record_occurrence_observation(
                "tool_invoked", mission_id="GOAL-001", occurrence=OCCURRENCE, **OBSERVATION
            ),
        }
    before = recorder.stream()
    with pytest.raises(ValueError, match=match):
        calls[path]()
    assert recorder.stream() == before


class _RecordsDuringInit(EvidenceRecorder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.record_observation("tool_invoked", mission_id="GOAL-001", **OBSERVATION)


def test_explicit_mode_cannot_be_set_on_a_recorder_that_already_recorded(runtime) -> None:
    with pytest.raises(ValueError, match="already recorded"):
        _explicit(runtime, cls=_RecordsDuringInit)


def test_resume_refuses_a_recorder_that_recorded_during_construction(runtime) -> None:
    authorizer, context = runtime
    prior = _explicit(runtime)
    prior.record_occurrence_decision(
        _decision(runtime), mission_id="GOAL-001", occurrence=OCCURRENCE
    )
    with pytest.raises(ValueError, match="already recorded"):
        _RecordsDuringInit.resume(authorizer, context, prior.stream(), **PRODUCER)


class _Key(str):
    pass


@pytest.mark.parametrize("path", ["decision", "observation"])
def test_reserved_names_are_refused_in_any_spelling(runtime, path) -> None:
    from types import MappingProxyType

    recorder = _legacy(runtime)
    spoof = ENVELOPE_OVERRIDES["producer"]
    if path == "observation":
        call = lambda: recorder.record_observation(  # noqa: E731
            "tool_invoked", mission_id="GOAL-001", **OBSERVATION, **{_Key("producer"): spoof}
        )
    else:
        decision = _decision(runtime)
        decision = dataclasses.replace(
            decision,
            event_intents=tuple(
                dataclasses.replace(
                    intent, fields=MappingProxyType({**intent.fields, _Key("producer"): spoof})
                )
                for intent in decision.event_intents
            ),
        )
        call = lambda: recorder.record_decision(decision, mission_id="GOAL-001")  # noqa: E731
    _assert_refused_without_mutation(recorder, call, "cannot override producer")


class _HonestView(dict):
    """A dict whose lookups show the honest event while its items say otherwise."""

    def __init__(self, honest, items):
        super().__init__(items)
        self._honest = honest

    def get(self, key, default=None):
        return self._honest.get(key, default)

    def __contains__(self, key):
        return key in self._honest


class _AlwaysEqual(str):
    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    __hash__ = str.__hash__


class _DisguisedSpoof(EvidenceRecorder):
    def _build_event_unlocked(self, event_type, mission_id, seq, fields):
        event = super()._build_event_unlocked(event_type, mission_id, seq, fields)
        return _HonestView(event, {**event, "producer": dict(ENVELOPE_OVERRIDES["producer"])})


class _EqualLookingProducer(EvidenceRecorder):
    def _build_event_unlocked(self, event_type, mission_id, seq, fields):
        event = super()._build_event_unlocked(event_type, mission_id, seq, fields)
        event["producer"] = {key: _AlwaysEqual("spoofed") for key in event["producer"]}
        return event


class _NoneOccurrence(EvidenceRecorder):
    def _build_event_unlocked(self, event_type, mission_id, seq, fields):
        event = super()._build_event_unlocked(event_type, mission_id, seq, fields)
        event["occurrence"] = None
        return event


class _OtherOccurrence(EvidenceRecorder):
    def _build_event_unlocked(self, event_type, mission_id, seq, fields):
        event = super()._build_event_unlocked(event_type, mission_id, seq, fields)
        event["occurrence"] = {**event["occurrence"], "occurrence_id": "task.other"}
        return event


class _FloatAttempt(EvidenceRecorder):
    def _build_event_unlocked(self, event_type, mission_id, seq, fields):
        event = super()._build_event_unlocked(event_type, mission_id, seq, fields)
        event["occurrence"] = {**event["occurrence"], "attempt": 1.0}
        return event


@pytest.mark.parametrize(
    ("cls", "mode", "match"),
    [
        (_DisguisedSpoof, "legacy", "plain dict"),
        (_EqualLookingProducer, "legacy", "producer"),
        (_NoneOccurrence, "explicit", "occurrence does not match"),
        (_OtherOccurrence, "explicit", "occurrence does not match"),
        (_FloatAttempt, "explicit", "occurrence does not match"),
    ],
)
def test_disguised_builder_output_cannot_pass_the_commit_check(
    runtime, cls, mode, match
) -> None:
    if mode == "legacy":
        recorder = _legacy(runtime, cls=cls)
        call = lambda: recorder.record_observation(  # noqa: E731
            "tool_invoked", mission_id="GOAL-001", **OBSERVATION
        )
    else:
        recorder = _explicit(runtime, cls=cls)
        call = lambda: recorder.record_occurrence_observation(  # noqa: E731
            "tool_invoked", mission_id="GOAL-001", occurrence=OCCURRENCE, **OBSERVATION
        )
    with pytest.raises(ValueError, match=match):
        call()
    assert recorder.stream()["events"] == []


def test_builder_cannot_mutate_an_event_after_commit(runtime) -> None:
    built: list[dict] = []

    class Retaining(EvidenceRecorder):
        def _build_event_unlocked(self, event_type, mission_id, seq, fields):
            event = super()._build_event_unlocked(event_type, mission_id, seq, fields)
            built.append(event)
            return event

    recorder = _legacy(runtime, cls=Retaining)
    recorder.record_decision(_decision(runtime), mission_id="GOAL-001")
    for event in built:
        event["producer"]["id"] = "someone-else"
    assert {event["producer"]["id"] for event in recorder.stream()["events"]} == {
        "integrity-tests"
    }


def test_refusal_mid_batch_leaves_events_and_sequences_untouched(runtime) -> None:
    calls = {"n": 0}

    class SecondBuildSpoofs(EvidenceRecorder):
        def _build_event_unlocked(self, event_type, mission_id, seq, fields):
            event = super()._build_event_unlocked(event_type, mission_id, seq, fields)
            calls["n"] += 1
            if calls["n"] == 2:
                event["producer"] = dict(ENVELOPE_OVERRIDES["producer"])
            return event

    recorder = _legacy(runtime, cls=SecondBuildSpoofs)
    with pytest.raises(ValueError, match="producer"):
        recorder.record_decision(_decision(runtime), mission_id="GOAL-001")
    assert recorder.stream()["events"] == []
    recorder.record_decision(_decision(runtime), mission_id="GOAL-001")
    assert [event["sequence"] for event in recorder.stream()["events"]] == [1, 2]
    assert recorder.validate()["status"] == "pass"


class _LyingFormat(str):
    def __format__(self, spec):
        return "GOAL-777"


def test_direct_stamp_canonicalizes_its_identifiers(runtime) -> None:
    recorder = _legacy(runtime)
    recorder.record_decision(_decision(runtime), mission_id="GOAL-001")
    recorder._stamp("tool_invoked", _LyingFormat("GOAL-001"), OBSERVATION)
    event = recorder.stream()["events"][-1]
    assert event["event_id"] == "GOAL-001-0003"
    assert type(event["mission_id"]) is str
    assert recorder.validate()["status"] == "pass"


def test_occurrence_values_are_read_past_subclass_hooks(runtime) -> None:
    class Shifting(RuntimeOccurrence):
        """Validates honestly, then answers differently once constructed."""

        def __post_init__(self):
            super().__post_init__()
            object.__setattr__(self, "_ready", True)

        def __getattribute__(self, name):
            if object.__getattribute__(self, "__dict__").get("_ready"):
                if name == "occurrence_id":
                    return ["caller", "owned"]
                if name == "attempt":
                    return object()
            return super().__getattribute__(name)

    recorder = _explicit(runtime)
    recorder.record_occurrence_decision(
        _decision(runtime), mission_id="GOAL-001", occurrence=Shifting("node.read", "task.a", 1)
    )
    recorder.record_occurrence_observation(
        "tool_invoked",
        mission_id="GOAL-001",
        occurrence=Shifting("node.read", "task.a", 1),
        **OBSERVATION,
    )
    occurrences = [event["occurrence"] for event in recorder.stream()["events"]]
    assert occurrences == [
        {"operation_id": "node.read", "occurrence_id": "task.a", "attempt": 1}
    ] * 3
    assert recorder.validate()["status"] == "pass"


def _forged_prefix(runtime, mode: str) -> dict:
    recorder = _explicit(runtime) if mode == "explicit" else _legacy(runtime)
    if mode == "explicit":
        recorder.record_occurrence_decision(
            _decision(runtime), mission_id="GOAL-001", occurrence=OCCURRENCE
        )
    else:
        recorder.record_decision(_decision(runtime), mission_id="GOAL-001")
    stream = recorder.stream()
    for event in stream["events"]:
        event["producer"] = dict(ENVELOPE_OVERRIDES["producer"])
    return stream


@pytest.mark.parametrize("mode", ["legacy", "explicit"])
def test_resume_refuses_prefix_events_from_another_producer(runtime, mode) -> None:
    # The validator now rejects a prefix whose events name another producer,
    # so resume() refuses it while validating the prior stream.
    authorizer, context = runtime
    with pytest.raises(ValueError, match="AN_EVT_PRODUCER_MISMATCH"):
        EvidenceRecorder.resume(authorizer, context, _forged_prefix(runtime, mode), **PRODUCER)


def test_refused_resume_leaves_a_leaked_recorder_in_its_own_mode(runtime) -> None:
    authorizer, context = runtime
    prior = _explicit(runtime)
    prior.record_occurrence_decision(
        _decision(runtime), mission_id="GOAL-001", occurrence=OCCURRENCE
    )
    leaked: list[EvidenceRecorder] = []

    class Leaking(_RecordsDuringInit):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            leaked.append(self)

    with pytest.raises(ValueError, match="already recorded"):
        Leaking.resume(authorizer, context, prior.stream(), **PRODUCER)
    stream = leaked[0].stream()
    assert stream["occurrence_mode"] == "legacy"
    assert [("occurrence" in event) for event in stream["events"]] == [False]


def test_resume_refuses_events_recorded_while_the_prefix_was_validated(
    runtime, monkeypatch
) -> None:
    import nornyx.agentic_evidence as evidence

    authorizer, context = runtime
    prior = _legacy(runtime)
    prior.record_decision(_decision(runtime), mission_id="GOAL-001")
    holder: list[EvidenceRecorder] = []

    class Exposing(EvidenceRecorder):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            holder.append(self)

    original = evidence.validate_runtime_events

    def recording_validator(*args, **kwargs):
        holder[0].record_observation("agent_invoked", mission_id="GOAL-002", **OBSERVATION)
        return original(*args, **kwargs)

    monkeypatch.setattr(evidence, "validate_runtime_events", recording_validator)
    with pytest.raises(ValueError, match="already recorded"):
        Exposing.resume(authorizer, context, prior.stream(), **PRODUCER)


# --- preserved behaviour ------------------------------------------------------


@pytest.mark.parametrize("schema_version", ["1.0", "1.1"])
def test_ordinary_legacy_recording_is_unchanged(runtime, schema_version) -> None:
    recorder = _legacy(runtime, schema_version)
    recorder.record_decision(_decision(runtime), mission_id="GOAL-001")
    recorder.record_observation("tool_invoked", mission_id="GOAL-001", **OBSERVATION)
    events = recorder.stream()["events"]
    assert [event["sequence"] for event in events] == [1, 2, 3]
    assert all("occurrence" not in event for event in events)
    assert recorder.validate()["status"] == "pass"


def test_ordinary_explicit_recording_is_unchanged(runtime) -> None:
    recorder = _explicit(runtime)
    recorder.record_occurrence_decision(
        _decision(runtime), mission_id="GOAL-001", occurrence=OCCURRENCE
    )
    recorder.record_occurrence_observation(
        "tool_invoked", mission_id="GOAL-001", occurrence=OCCURRENCE, **OBSERVATION
    )
    events = recorder.stream()["events"]
    assert [event["sequence"] for event in events] == [1, 2, 3]
    assert all(event["occurrence"]["occurrence_id"] == "task.a" for event in events)
    assert recorder.validate()["status"] == "pass"
