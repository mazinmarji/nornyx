"""EvidenceRecorder under forced two-thread interleavings.

Every decisive test here parks one writer inside the recorder lock with
``threading.Event`` gates, proves a second writer has attempted the lock and is
blocked on it, then releases the first writer and checks the final order. The
probe lock wraps the recorder's own lock rather than replacing it, so a recorder
whose lock stopped excluding would fail these tests. Every wait is bounded, so a
deadlock fails a test instead of hanging the suite. The many-thread stress test
at the end is a supplement only.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import sys
import threading
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
OBSERVATION = {
    "actor_ref": "identity.researcher.local",
    "capability_ref": "read_governed_context",
}
PRODUCER = {"producer_id": "concurrency-tests", "producer_type": "synthetic_harness"}
SPOOFED_PRODUCER = {"type": "external_runtime", "id": "someone-else", "version": "9.9"}
TIMEOUT = 5.0
MODES = ["legacy-1.0", "legacy", "explicit"]
EVENT_TYPES = {
    "decision": ["capability_requested", "capability_allowed"],
    "observation": ["tool_invoked"],
}


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


# --- synchronization harness --------------------------------------------------


class _ProbeLock:
    """Wraps the recorder's own lock and counts acquire attempts and holds.

    A second caller increments ``attempts`` the moment it enters ``acquire()``,
    then blocks inside the wrapped lock; ``acquired`` moves only once a caller
    holds it. While a parked writer holds the lock, ``attempts`` ahead of
    ``acquired`` proves the other writer is blocked, not merely unscheduled.
    """

    def __init__(self, inner) -> None:
        self._inner = inner
        self._cond = threading.Condition()
        self.attempts = 0
        self.acquired = 0

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        with self._cond:
            self.attempts += 1
            self._cond.notify_all()
        ok = self._inner.acquire(blocking, timeout)
        if ok:
            with self._cond:
                self.acquired += 1
                self._cond.notify_all()
        return ok

    def release(self) -> None:
        self._inner.release()

    def __enter__(self) -> _ProbeLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.release()
        return False

    def wait_for_attempts(self, count: int) -> bool:
        with self._cond:
            return self._cond.wait_for(lambda: self.attempts >= count, TIMEOUT)


class _Gate:
    """Parks the first recorder hook call matching ``predicate`` until released."""

    def __init__(self, predicate) -> None:
        self._predicate = predicate
        self._mutex = threading.Lock()
        self._claimed = False
        self.parked = threading.Event()
        self.release = threading.Event()

    def check(self, hook: str, **call) -> None:
        with self._mutex:
            if self._claimed or not self._predicate(hook, call):
                return
            self._claimed = True
        self.parked.set()
        if not self.release.wait(TIMEOUT):
            raise AssertionError("deadlock guard: the gate was never released")


class _Worker:
    def __init__(self, target) -> None:
        self.result = None
        self.error: BaseException | None = None
        self.done = threading.Event()
        self.thread = threading.Thread(target=self._run, args=(target,), daemon=True)

    def _run(self, target) -> None:
        try:
            self.result = target()
        except BaseException as exc:  # noqa: BLE001 - surfaced by the test
            self.error = exc
        finally:
            self.done.set()

    def join(self) -> None:
        self.thread.join(TIMEOUT)
        assert not self.thread.is_alive(), "deadlock guard: worker did not finish"


class _Harness:
    """Starts workers and gates, and always releases and joins them on teardown."""

    def __init__(self) -> None:
        self.gates: list[_Gate] = []
        self.workers: list[_Worker] = []

    def gate(self, predicate) -> _Gate:
        gate = _Gate(predicate)
        self.gates.append(gate)
        return gate

    def start(self, target) -> _Worker:
        worker = _Worker(target)
        self.workers.append(worker)
        worker.thread.start()
        return worker

    def close(self) -> None:
        for gate in self.gates:
            gate.release.set()
        for worker in self.workers:
            worker.thread.join(TIMEOUT)


@pytest.fixture
def harness():
    active = _Harness()
    yield active
    active.close()


def _instrumented(*, gate: _Gate | None = None, leak: list | None = None, spoof=None):
    """A recorder subclass whose hooks park on ``gate`` and whose lock is probed.

    ``init`` runs at the end of construction, outside the lock;
    ``mode_install_checked`` runs inside the lock just after the empty-recorder
    check of ``for_occurrences()``/``resume()`` passed and before the mode or
    prefix is installed; ``build`` runs inside the lock before each event of a
    write is built. ``spoof`` marks built events whose producer is replaced, so
    the real commit-point check refuses them.
    """

    class Instrumented(EvidenceRecorder):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._lock = _ProbeLock(self._lock)
            if leak is not None:
                leak.append(self)
            if gate is not None:
                gate.check("init")

        def _require_no_events(self, action):
            super()._require_no_events(action)
            if gate is not None:
                gate.check("mode_install_checked")

        def _build_checked_unlocked(self, event_type, mission_id, seq, fields, occurrence=None):
            if gate is not None:
                gate.check("build", event_type=event_type, mission_id=mission_id, fields=fields)
            return super()._build_checked_unlocked(event_type, mission_id, seq, fields, occurrence)

        def _build_event_unlocked(self, event_type, mission_id, seq, fields):
            event = super()._build_event_unlocked(event_type, mission_id, seq, fields)
            if spoof is not None and spoof(event):
                event["producer"] = dict(SPOOFED_PRODUCER)
            return event

    return Instrumented


# --- recording helpers --------------------------------------------------------


def _authorizer(runtime, schema_version: str = "1.1") -> Authorizer:
    authorizer, _ = runtime
    if schema_version == "1.0":
        state = authorizer.state
        lock = _build_agentic_network_lock(
            state.document, state.composition, runtime_events_schema_version="1.0"
        )
        authorizer = Authorizer(state.document, state.composition, lock)
    return authorizer


def _recorder(runtime, mode: str, cls=EvidenceRecorder) -> EvidenceRecorder:
    _, context = runtime
    if mode == "explicit":
        return cls.for_occurrences(_authorizer(runtime), context, **PRODUCER)
    schema_version = "1.0" if mode == "legacy-1.0" else "1.1"
    return cls(_authorizer(runtime, schema_version), context, **PRODUCER)


def _digest(tag: str) -> str:
    return "sha256:" + hashlib.sha256(tag.encode("utf-8")).hexdigest()


TAGS = {_digest(tag): tag for tag in ("seed", "a", "b", "c", "d", "e")}


def _occurrence(tag: str) -> RuntimeOccurrence:
    return RuntimeOccurrence("node.read", f"task.{tag}", 1)


def _decision(runtime, tag: str):
    authorizer, context = runtime
    decision = authorizer.evaluate(
        CapabilityRequest("identity.researcher.local", "read_governed_context"),
        context=context,
    )
    return dataclasses.replace(
        decision,
        event_intents=tuple(
            dataclasses.replace(intent, fields={**intent.fields, "input_digest": _digest(tag)})
            for intent in decision.event_intents
        ),
    )


def _write(runtime, recorder, mode: str, kind: str, tag: str, mission: str = "GOAL-001"):
    """Record one tagged call. Explicit calls use the occurrence ``task.<tag>``,
    so an explicit observation needs that occurrence's decision first."""

    explicit = mode == "explicit"
    if kind == "decision":
        decision = _decision(runtime, tag)
        if explicit:
            return lambda: recorder.record_occurrence_decision(
                decision, mission_id=mission, occurrence=_occurrence(tag)
            )
        return lambda: recorder.record_decision(decision, mission_id=mission)
    fields = {**OBSERVATION, "input_digest": _digest(tag)}
    if explicit:
        return lambda: recorder.record_occurrence_observation(
            "tool_invoked", mission_id=mission, occurrence=_occurrence(tag), **fields
        )
    return lambda: recorder.record_observation("tool_invoked", mission_id=mission, **fields)


def _seed(runtime, recorder, mode: str, missions, observers=()) -> None:
    """Give each mission a prior allowance and, in explicit mode, each
    ``(tag, mission)`` observer the decision for its own occurrence."""

    for mission in missions:
        _write(runtime, recorder, mode, "decision", "seed", mission)()
    if mode == "explicit":
        for tag, mission in observers:
            _write(runtime, recorder, mode, "decision", tag, mission)()


def _last_event_of(kind: str, tag: str):
    """Predicate parking a call at its last build: inside the batch for a decision."""

    def predicate(hook, call):
        return (
            hook == "build"
            and call["fields"].get("input_digest") == _digest(tag)
            and call["event_type"] == EVENT_TYPES[kind][-1]
        )

    return predicate


def _private_state(recorder) -> tuple[list, dict]:
    # Read directly: stream() would queue on the lock a parked writer holds.
    return copy.deepcopy(recorder._events), dict(recorder._sequences)


def _runs(events) -> list[tuple[tuple[str, str], list[str]]]:
    """Group consecutive events by (mission, tag) into ordered runs of types."""

    runs: list[tuple[tuple[str, str], list[str]]] = []
    for event in events:
        key = (event["mission_id"], TAGS[event["input_digest"]])
        if runs and runs[-1][0] == key:
            runs[-1][1].append(event["event_type"])
        else:
            runs.append((key, [event["event_type"]]))
    return runs


def _assert_contiguous_and_valid(recorder) -> list[dict]:
    events = recorder.stream()["events"]
    by_mission: dict[str, list[int]] = {}
    for event in events:
        by_mission.setdefault(event["mission_id"], []).append(event["sequence"])
        assert event["event_id"] == f"{event['mission_id']}-{event['sequence']:04d}"
    for sequences in by_mission.values():
        assert sequences == list(range(1, len(sequences) + 1))
    assert len({event["event_id"] for event in events}) == len(events)
    report = recorder.validate()
    assert report["status"] == "pass", report["diagnostics"]
    return events


# --- atomic batches and ordering on every write path ---------------------------


@pytest.mark.parametrize("waiting", ["decision", "observation"])
@pytest.mark.parametrize("parked", ["decision", "observation"])
@pytest.mark.parametrize("mode", MODES)
def test_a_writer_parked_in_the_lock_blocks_every_other_write_path(
    runtime, harness, mode, parked, waiting
) -> None:
    gate = harness.gate(_last_event_of(parked, "a"))
    recorder = _recorder(runtime, mode, _instrumented(gate=gate))
    observers = [(tag, "GOAL-001") for tag, kind in (("a", parked), ("b", waiting)) if kind == "observation"]
    _seed(runtime, recorder, mode, ["GOAL-001"], observers)
    probe = recorder._lock
    before = _private_state(recorder)
    attempts, acquired = probe.attempts, probe.acquired

    writer_a = harness.start(_write(runtime, recorder, mode, parked, "a"))
    assert gate.parked.wait(TIMEOUT), "deadlock guard: A never reached its last build"
    # A holds the lock with part (or all) of its call built, nothing committed.
    assert probe.acquired == acquired + 1
    assert _private_state(recorder) == before

    writer_b = harness.start(_write(runtime, recorder, mode, waiting, "b"))
    assert probe.wait_for_attempts(attempts + 2), "deadlock guard: B never tried the lock"
    assert probe.acquired == acquired + 1
    assert not writer_b.done.is_set()
    assert _private_state(recorder) == before

    gate.release.set()
    writer_a.join()
    writer_b.join()
    assert writer_a.error is None and writer_b.error is None

    events = _assert_contiguous_and_valid(recorder)
    assert _runs(events[len(before[0]):]) == [
        (("GOAL-001", "a"), EVENT_TYPES[parked]),
        (("GOAL-001", "b"), EVENT_TYPES[waiting]),
    ]
    assert probe.attempts == probe.acquired


@pytest.mark.parametrize("mode", MODES)
def test_a_batch_refused_at_commit_leaves_no_trace_while_a_blocked_writer_proceeds(
    runtime, harness, mode
) -> None:
    gate = harness.gate(_last_event_of("decision", "a"))
    spoof = lambda event: (  # noqa: E731
        event.get("input_digest") == _digest("a")
        and event["event_type"] == "capability_allowed"
    )
    recorder = _recorder(runtime, mode, _instrumented(gate=gate, spoof=spoof))
    _seed(runtime, recorder, mode, ["GOAL-001"], [("b", "GOAL-001"), ("c", "GOAL-001")])
    probe = recorder._lock
    before = _private_state(recorder)
    attempts, acquired = probe.attempts, probe.acquired

    writer_a = harness.start(_write(runtime, recorder, mode, "decision", "a"))
    assert gate.parked.wait(TIMEOUT), "deadlock guard: A never reached its second build"
    writer_b = harness.start(_write(runtime, recorder, mode, "observation", "b"))
    assert probe.wait_for_attempts(attempts + 2), "deadlock guard: B never tried the lock"
    assert probe.acquired == acquired + 1
    assert not writer_b.done.is_set()
    assert _private_state(recorder) == before

    gate.release.set()
    writer_a.join()
    writer_b.join()
    assert isinstance(writer_a.error, ValueError)
    assert "producer" in str(writer_a.error)
    assert writer_b.error is None

    # A's first event was built but never committed, and its two sequence
    # numbers were never consumed: B takes the very next one.
    _write(runtime, recorder, mode, "observation", "c")()
    events = _assert_contiguous_and_valid(recorder)
    new = events[len(before[0]):]
    assert _runs(new) == [
        (("GOAL-001", "b"), ["tool_invoked"]),
        (("GOAL-001", "c"), ["tool_invoked"]),
    ]
    assert [event["sequence"] for event in new] == [len(before[0]) + 1, len(before[0]) + 2]
    assert all(event["producer"]["id"] == PRODUCER["producer_id"] for event in events)


@pytest.mark.parametrize("mode", MODES)
def test_writers_queued_behind_a_parked_batch_keep_every_mission_contiguous(
    runtime, harness, mode
) -> None:
    gate = harness.gate(_last_event_of("decision", "a"))
    recorder = _recorder(runtime, mode, _instrumented(gate=gate))
    waiting = [
        ("decision", "b", "GOAL-002"),
        ("observation", "c", "GOAL-001"),
        ("observation", "d", "GOAL-002"),
        ("decision", "e", "GOAL-001"),
    ]
    _seed(runtime, recorder, mode, ["GOAL-001", "GOAL-002"], [("c", "GOAL-001"), ("d", "GOAL-002")])
    probe = recorder._lock
    before = _private_state(recorder)
    attempts, acquired = probe.attempts, probe.acquired

    writer_a = harness.start(_write(runtime, recorder, mode, "decision", "a"))
    assert gate.parked.wait(TIMEOUT), "deadlock guard: A never reached its second build"
    queued = [
        harness.start(_write(runtime, recorder, mode, kind, tag, mission))
        for kind, tag, mission in waiting
    ]
    assert probe.wait_for_attempts(attempts + 1 + len(waiting)), (
        "deadlock guard: the queued writers never tried the lock"
    )
    assert probe.acquired == acquired + 1
    assert not any(worker.done.is_set() for worker in queued)
    assert _private_state(recorder) == before

    gate.release.set()
    for worker in [writer_a, *queued]:
        worker.join()
        assert worker.error is None

    events = _assert_contiguous_and_valid(recorder)
    runs = _runs(events[len(before[0]):])
    # A held the lock, so it commits first; the queued writers may then commit
    # in any order, but each call's events stay adjacent and in order.
    assert runs[0] == (("GOAL-001", "a"), EVENT_TYPES["decision"])
    assert sorted(runs[1:]) == sorted(
        ((mission, tag), EVENT_TYPES[kind]) for kind, tag, mission in waiting
    )


# --- mode and prefix install against a racing record ---------------------------


@pytest.mark.parametrize("call", ["decision", "observation"])
def test_for_occurrences_orders_a_racing_legacy_record_after_the_switch(
    runtime, harness, call
) -> None:
    authorizer, context = runtime
    leak: list[EvidenceRecorder] = []
    gate = harness.gate(lambda hook, _call: hook == "mode_install_checked")
    cls = _instrumented(gate=gate, leak=leak)

    installer = harness.start(lambda: cls.for_occurrences(authorizer, context, **PRODUCER))
    assert gate.parked.wait(TIMEOUT), "deadlock guard: for_occurrences never took the lock"
    recorder = leak[0]
    probe = recorder._lock
    # The empty check passed under the lock; the mode is not switched yet.
    assert recorder._occurrence_mode == "legacy"
    assert probe.acquired == 1

    # Mode is still legacy, so B passes the early legacy check and queues.
    racer = harness.start(_write(runtime, recorder, "legacy", call, "b"))
    assert probe.wait_for_attempts(2), "deadlock guard: the record never tried the lock"
    assert probe.acquired == 1
    assert not racer.done.is_set()
    assert recorder._events == []

    gate.release.set()
    installer.join()
    racer.join()
    assert installer.error is None and installer.result is recorder
    # Ordered after the switch: the commit-point check refuses the
    # occurrence-less event rather than mixing it into the explicit stream.
    assert isinstance(racer.error, ValueError)
    assert "occurrence does not match" in str(racer.error)
    stream = recorder.stream()
    assert stream["occurrence_mode"] == "explicit"
    assert stream["events"] == []

    _write(runtime, recorder, "explicit", "decision", "c")()
    events = _assert_contiguous_and_valid(recorder)
    assert [event["occurrence"]["occurrence_id"] for event in events] == ["task.c"] * 2


def test_for_occurrences_is_refused_when_a_racing_record_lands_first(runtime, harness) -> None:
    authorizer, context = runtime
    leak: list[EvidenceRecorder] = []
    gate = harness.gate(lambda hook, _call: hook == "init")
    cls = _instrumented(gate=gate, leak=leak)

    installer = harness.start(lambda: cls.for_occurrences(authorizer, context, **PRODUCER))
    assert gate.parked.wait(TIMEOUT), "deadlock guard: construction never finished"
    recorder = leak[0]
    racer = harness.start(_write(runtime, recorder, "legacy", "decision", "b"))
    racer.join()
    assert racer.error is None

    gate.release.set()
    installer.join()
    assert isinstance(installer.error, ValueError)
    assert "already recorded" in str(installer.error)
    stream = recorder.stream()
    assert stream["occurrence_mode"] == "legacy"
    assert [("occurrence" in event) for event in stream["events"]] == [False, False]
    _assert_contiguous_and_valid(recorder)


def _prior_stream(runtime, mode: str) -> dict:
    prior = _recorder(runtime, mode)
    _write(runtime, prior, mode, "decision", "seed")()
    return prior.stream()


@pytest.mark.parametrize("prefix_mode", MODES)
def test_resume_installs_its_prefix_before_a_racing_record(
    runtime, harness, prefix_mode
) -> None:
    _, context = runtime
    authorizer = _authorizer(runtime, "1.0" if prefix_mode == "legacy-1.0" else "1.1")
    prior = _prior_stream(runtime, prefix_mode)
    leak: list[EvidenceRecorder] = []
    gate = harness.gate(lambda hook, _call: hook == "mode_install_checked")
    cls = _instrumented(gate=gate, leak=leak)

    installer = harness.start(lambda: cls.resume(authorizer, context, prior, **PRODUCER))
    assert gate.parked.wait(TIMEOUT), "deadlock guard: resume never took the lock"
    recorder = leak[0]
    probe = recorder._lock
    assert recorder._events == [] and recorder._sequences == {}

    racer = harness.start(_write(runtime, recorder, "legacy", "observation", "b"))
    assert probe.wait_for_attempts(2), "deadlock guard: the record never tried the lock"
    assert probe.acquired == 1
    assert not racer.done.is_set()
    assert recorder._events == []

    gate.release.set()
    installer.join()
    racer.join()
    assert installer.error is None and installer.result is recorder
    events = _assert_contiguous_and_valid(recorder)
    assert events[: len(prior["events"])] == prior["events"]
    if prefix_mode == "explicit":
        # The record queued behind an explicit prefix is refused, never mixed in.
        assert isinstance(racer.error, ValueError)
        assert "occurrence does not match" in str(racer.error)
        assert events == prior["events"]
        assert recorder.stream()["occurrence_mode"] == "explicit"
    else:
        # The record is ordered after the prefix and continues its numbering.
        assert racer.error is None
        assert _runs(events[len(prior["events"]):]) == [(("GOAL-001", "b"), ["tool_invoked"])]
        assert events[-1]["sequence"] == len(prior["events"]) + 1


@pytest.mark.parametrize("prefix_mode", MODES)
def test_resume_is_refused_when_a_racing_record_lands_first(
    runtime, harness, monkeypatch, prefix_mode
) -> None:
    import nornyx.agentic_evidence as evidence

    _, context = runtime
    authorizer = _authorizer(runtime, "1.0" if prefix_mode == "legacy-1.0" else "1.1")
    prior = _prior_stream(runtime, prefix_mode)
    leak: list[EvidenceRecorder] = []
    gate = harness.gate(lambda hook, _call: hook == "validate")
    original = evidence.validate_runtime_events

    def parking_validator(*args, **kwargs):
        gate.check("validate")
        return original(*args, **kwargs)

    monkeypatch.setattr(evidence, "validate_runtime_events", parking_validator)
    cls = _instrumented(leak=leak)

    installer = harness.start(lambda: cls.resume(authorizer, context, prior, **PRODUCER))
    assert gate.parked.wait(TIMEOUT), "deadlock guard: resume never validated the prefix"
    recorder = leak[0]
    racer = harness.start(_write(runtime, recorder, "legacy", "decision", "b", "GOAL-002"))
    racer.join()
    assert racer.error is None

    gate.release.set()
    installer.join()
    assert isinstance(installer.error, ValueError)
    assert "already recorded" in str(installer.error)
    events = _assert_contiguous_and_valid(recorder)
    # Only the racing record: no prefix event was installed beside it.
    assert _runs(events) == [(("GOAL-002", "b"), EVENT_TYPES["decision"])]
    assert all("occurrence" not in event for event in events)


# --- supplementary stress -----------------------------------------------------


@pytest.mark.parametrize("mode", MODES)
def test_bounded_concurrent_writers_keep_streams_contiguous_and_valid(runtime, mode) -> None:
    """Supplementary scheduler stress only; the gated tests above are the proof."""

    recorder = _recorder(runtime, mode)
    threads_n, calls_n = 6, 10
    start = threading.Barrier(threads_n, timeout=TIMEOUT)
    errors: list[BaseException] = []

    def worker(index: int) -> None:
        try:
            start.wait()
            mission = f"GOAL-00{1 + index % 2}"
            for call in range(calls_n):
                tag = f"t{index}-c{call}"
                _write(runtime, recorder, mode, "decision", tag, mission)()
                _write(runtime, recorder, mode, "observation", tag, mission)()
        except BaseException as exc:  # noqa: BLE001 - surfaced below
            errors.append(exc)

    previous = sys.getswitchinterval()
    try:
        sys.setswitchinterval(1e-6)
        threads = [threading.Thread(target=worker, args=(n,), daemon=True) for n in range(threads_n)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(TIMEOUT * 4)
    finally:
        sys.setswitchinterval(previous)
    assert not any(thread.is_alive() for thread in threads), "deadlock guard"
    assert not errors

    events = _assert_contiguous_and_valid(recorder)
    assert len(events) == threads_n * calls_n * 3
    for index, event in enumerate(events):
        if event["event_type"] == "capability_requested":
            paired = events[index + 1]
            assert paired["event_type"] == "capability_allowed"
            assert paired["input_digest"] == event["input_digest"]
            assert paired["sequence"] == event["sequence"] + 1
