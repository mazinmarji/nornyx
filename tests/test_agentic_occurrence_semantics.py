"""ADR-0042 runtime occurrence, retry, replay, and continuation corpus."""

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
    verify_agentic_network_lock,
)
from nornyx.agentic_artifacts import _build_agentic_network_lock


ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-07-17T10:00:00Z"
LATER = "2026-07-17T10:05:00Z"


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


def _recorder(
    runtime: tuple[Authorizer, EvaluationContext],
) -> EvidenceRecorder:
    authorizer, context = runtime
    return EvidenceRecorder.for_occurrences(
        authorizer,
        context,
        producer_id="occurrence-tests",
        producer_type="synthetic_harness",
    )


def _decision(runtime: tuple[Authorizer, EvaluationContext]):
    authorizer, context = runtime
    return authorizer.evaluate(
        CapabilityRequest(
            "identity.researcher.local", "read_governed_context"
        ),
        context=context,
    )


def _record_success(
    recorder: EvidenceRecorder,
    decision,
    occurrence: RuntimeOccurrence,
) -> None:
    recorder.record_occurrence_decision(
        decision, mission_id="GOAL-001", occurrence=occurrence
    )
    recorder.record_occurrence_observation(
        "tool_invoked",
        mission_id="GOAL-001",
        occurrence=occurrence,
        actor_ref="identity.researcher.local",
        capability_ref="read_governed_context",
    )


def test_runtime_occurrence_rejects_invalid_identity_and_attempt() -> None:
    with pytest.raises(ValueError):
        RuntimeOccurrence("bad operation", "task.1", 1)
    with pytest.raises(ValueError):
        RuntimeOccurrence("node.read", "task.1", True)
    with pytest.raises(ValueError):
        RuntimeOccurrence("node.read", "task.1", 0)


def test_new_legacy_calls_remain_legacy(runtime) -> None:
    authorizer, context = runtime
    recorder = EvidenceRecorder(
        authorizer,
        context,
        producer_id="occurrence-tests",
        producer_type="synthetic_harness",
    )
    stream = recorder.stream()
    assert stream["schema_version"] == "1.1"
    assert stream["occurrence_mode"] == "legacy"
    with pytest.raises(ValueError):
        recorder.record_occurrence_observation(
            "runtime_failed",
            mission_id="GOAL-001",
            occurrence=RuntimeOccurrence("node.read", "task.1", 1),
            actor_ref="identity.researcher.local",
        )


def test_historical_1_0_lock_and_recorder_remain_valid(runtime) -> None:
    authorizer, context = runtime
    state = authorizer.state
    document = state.document
    composition = state.composition
    lock = _build_agentic_network_lock(
        document, composition, runtime_events_schema_version="1.0"
    )
    assert verify_agentic_network_lock(lock, document, composition) == ()
    historical = Authorizer(document, composition, lock)
    recorder = EvidenceRecorder(
        historical,
        context,
        producer_id="occurrence-tests",
        producer_type="synthetic_harness",
    )
    assert recorder.stream()["schema_version"] == "1.0"
    assert "occurrence_mode" not in recorder.stream()
    assert recorder.validate()["status"] == "pass"


def test_loop_repetition_uses_new_occurrences(runtime) -> None:
    recorder = _recorder(runtime)
    decision = _decision(runtime)
    _record_success(
        recorder, decision, RuntimeOccurrence("node.read", "task.loop.1", 1)
    )
    _record_success(
        recorder, decision, RuntimeOccurrence("node.read", "task.loop.2", 1)
    )
    report = recorder.validate()
    assert report["status"] == "pass", report["diagnostics"]


def test_explicit_stream_rejects_missing_or_mixed_occurrence_metadata(runtime) -> None:
    recorder = _recorder(runtime)
    _record_success(
        recorder,
        _decision(runtime),
        RuntimeOccurrence("node.read", "task.explicit", 1),
    )
    missing = recorder.stream()
    del missing["events"][0]["occurrence"]
    authorizer, _context = runtime
    from nornyx.agentic import validate_runtime_events

    state = authorizer.state
    report = validate_runtime_events(
        state.document,
        state.composition,
        state.lock_payload,
        missing,
    )
    assert "AN_EVT_SCHEMA_INVALID" in {
        item["code"] for item in report["diagnostics"]
    }

    legacy = EvidenceRecorder(
        authorizer,
        runtime[1],
        producer_id="legacy-mixed",
        producer_type="synthetic_harness",
    )
    legacy.record_observation(
        "runtime_failed",
        mission_id="GOAL-001",
        actor_ref="identity.researcher.local",
    )
    mixed = legacy.stream()
    mixed["events"][0]["occurrence"] = {
        "operation_id": "node.read",
        "occurrence_id": "task.mixed",
        "attempt": 1,
    }
    report = validate_runtime_events(
        state.document,
        state.composition,
        state.lock_payload,
        mixed,
    )
    assert "AN_EVT_SCHEMA_INVALID" in {
        item["code"] for item in report["diagnostics"]
    }


def test_retry_is_same_occurrence_with_next_attempt(runtime) -> None:
    recorder = _recorder(runtime)
    decision = _decision(runtime)
    first = RuntimeOccurrence("node.read", "task.retry", 1)
    recorder.record_occurrence_decision(
        decision, mission_id="GOAL-001", occurrence=first
    )
    recorder.record_occurrence_observation(
        "runtime_failed",
        mission_id="GOAL-001",
        occurrence=first,
        actor_ref="identity.researcher.local",
    )
    _record_success(
        recorder, decision, RuntimeOccurrence("node.read", "task.retry", 2)
    )
    assert recorder.max_recorded_attempt(
        mission_id="GOAL-001",
        operation_id="node.read",
        occurrence_id="task.retry",
    ) == 2
    report = recorder.validate()
    assert report["status"] == "pass", report["diagnostics"]


def test_allowance_does_not_leak_between_attempts(runtime) -> None:
    recorder = _recorder(runtime)
    decision = _decision(runtime)
    first = RuntimeOccurrence("node.read", "task.retry", 1)
    recorder.record_occurrence_decision(
        decision, mission_id="GOAL-001", occurrence=first
    )
    recorder.record_occurrence_observation(
        "runtime_failed",
        mission_id="GOAL-001",
        occurrence=first,
        actor_ref="identity.researcher.local",
    )
    recorder.record_occurrence_observation(
        "tool_invoked",
        mission_id="GOAL-001",
        occurrence=RuntimeOccurrence("node.read", "task.retry", 2),
        actor_ref="identity.researcher.local",
        capability_ref="read_governed_context",
    )
    codes = {item["code"] for item in recorder.validate()["diagnostics"]}
    assert "AN_EVT_TOOL_WITHOUT_ALLOWANCE" in codes


def test_exact_replay_ignores_restamped_transport_fields(runtime) -> None:
    recorder = _recorder(runtime)
    occurrence = RuntimeOccurrence("node.read", "task.replay", 1)
    decision = _decision(runtime)
    recorder.record_occurrence_decision(
        decision, mission_id="GOAL-001", occurrence=occurrence
    )
    for _ in range(2):
        recorder.record_occurrence_observation(
            "runtime_failed",
            mission_id="GOAL-001",
            occurrence=occurrence,
            actor_ref="identity.researcher.local",
        )
    codes = [item["code"] for item in recorder.validate()["diagnostics"]]
    assert "AN_EVT_REPLAY" in codes


def test_successful_occurrence_cannot_be_retried(runtime) -> None:
    recorder = _recorder(runtime)
    decision = _decision(runtime)
    _record_success(
        recorder, decision, RuntimeOccurrence("node.read", "task.done", 1)
    )
    recorder.record_occurrence_decision(
        decision,
        mission_id="GOAL-001",
        occurrence=RuntimeOccurrence("node.read", "task.done", 2),
    )
    codes = {item["code"] for item in recorder.validate()["diagnostics"]}
    assert "AN_EVT_ATTEMPT_AFTER_SUCCESS" in codes


def test_occurrence_operation_is_immutable_and_attempts_are_contiguous(runtime) -> None:
    recorder = _recorder(runtime)
    decision = _decision(runtime)
    recorder.record_occurrence_decision(
        decision,
        mission_id="GOAL-001",
        occurrence=RuntimeOccurrence("node.read", "task.shared", 1),
    )
    recorder.record_occurrence_decision(
        decision,
        mission_id="GOAL-001",
        occurrence=RuntimeOccurrence("node.other", "task.shared", 3),
    )
    codes = {item["code"] for item in recorder.validate()["diagnostics"]}
    assert "AN_EVT_OCCURRENCE_OPERATION_MISMATCH" in codes
    assert "AN_EVT_ATTEMPT_GAP" in codes


def test_parallel_occurrences_can_interleave(runtime) -> None:
    recorder = _recorder(runtime)
    decision = _decision(runtime)
    left = RuntimeOccurrence("node.left", "task.left", 1)
    right = RuntimeOccurrence("node.right", "task.right", 1)
    recorder.record_occurrence_decision(
        decision, mission_id="GOAL-001", occurrence=left
    )
    recorder.record_occurrence_decision(
        decision, mission_id="GOAL-001", occurrence=right
    )
    for occurrence in (right, left):
        recorder.record_occurrence_observation(
            "tool_invoked",
            mission_id="GOAL-001",
            occurrence=occurrence,
            actor_ref="identity.researcher.local",
            capability_ref="read_governed_context",
        )
    assert recorder.validate()["status"] == "pass"


def test_resume_preserves_prefix_and_offsets_an_incomplete_attempt(runtime) -> None:
    authorizer, context = runtime
    recorder = _recorder(runtime)
    decision = _decision(runtime)
    first = RuntimeOccurrence("node.read", "task.resumed", 1)
    recorder.record_occurrence_decision(
        decision, mission_id="GOAL-001", occurrence=first
    )
    prefix = recorder.stream()
    resumed = EvidenceRecorder.resume(
        authorizer,
        EvaluationContext(LATER, authorizer.subject_revision),
        prefix,
        producer_id="occurrence-tests",
        producer_type="synthetic_harness",
    )
    assert resumed.stream() == prefix
    assert resumed.max_recorded_attempt(
        mission_id="GOAL-001",
        operation_id="node.read",
        occurrence_id="task.resumed",
    ) == 1
    _record_success(
        resumed, decision, RuntimeOccurrence("node.read", "task.resumed", 2)
    )
    assert resumed.validate()["status"] == "pass"
    assert [item["sequence"] for item in resumed.stream()["events"]] == list(
        range(1, len(resumed.stream()["events"]) + 1)
    )


def test_resume_rejects_wrong_producer_clock_and_tampering(runtime) -> None:
    authorizer, _context = runtime
    recorder = _recorder(runtime)
    recorder.record_occurrence_decision(
        _decision(runtime),
        mission_id="GOAL-001",
        occurrence=RuntimeOccurrence("node.read", "task.resumed", 1),
    )
    prefix = recorder.stream()
    with pytest.raises(ValueError, match="producer"):
        EvidenceRecorder.resume(
            authorizer,
            EvaluationContext(LATER, authorizer.subject_revision),
            prefix,
            producer_id="different",
            producer_type="synthetic_harness",
        )
    with pytest.raises(ValueError, match="must not precede"):
        EvidenceRecorder.resume(
            authorizer,
            EvaluationContext("2026-07-17T09:00:00Z", authorizer.subject_revision),
            prefix,
            producer_id="occurrence-tests",
            producer_type="synthetic_harness",
        )
    tampered = deepcopy(prefix)
    tampered["events"][0]["contract_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="not valid"):
        EvidenceRecorder.resume(
            authorizer,
            EvaluationContext(LATER, authorizer.subject_revision),
            tampered,
            producer_id="occurrence-tests",
            producer_type="synthetic_harness",
        )
