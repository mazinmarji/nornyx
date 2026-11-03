"""enforce() against the real core recorder in explicit occurrence mode.

``enforce()`` records through the legacy ``record_decision`` call, which carries
no occurrence identity. An explicit-mode recorder requires one on every event.

The refusal comes from the core, not from this package: a core carrying the
recorder-mode guard makes ``record_decision`` raise ``ValueError`` on an
explicit recorder, so ``enforce()`` fails closed before the action runs and
leaves the stream untouched. Released cores 1.10.x and 1.11.0 have no guard:
the decision is acted on and the recorded stream fails validation, as
``docs/COMPATIBILITY.md`` ("Recorder mode per entry point") documents.

The branch is selected by probing the installed core's behaviour, never its
version. A candidate core built from the same commit as this package can carry
the guard while still reporting the previous release and SPI versions, so a
version-based gate would skip the guarded assertions on the one core that has
the guard. Neither branch skips. Legacy-mode behaviour is unchanged on every
core.
"""

from __future__ import annotations

import functools

import pytest
from nornyx.agentic import CapabilityRequest, EvidenceRecorder

from nornyx_agentic_adapters import AdapterDenied, enforce
from nornyx_agentic_adapters.conformance.harness import build_authorizer, build_context

_ALLOW = CapabilityRequest("identity.researcher.local", "read_governed_context")
_DENY = CapabilityRequest("identity.reviewer.local", "propose_research_finding")
_GUARD_MESSAGE = "explicit occurrence mode"


@functools.cache
def _core_guards_explicit_recorder() -> bool:
    """Return whether the installed core refuses legacy recording on an
    explicit occurrence-mode recorder, by trying it on a throwaway recorder."""
    authorizer = build_authorizer()
    context = build_context(authorizer)
    probe = EvidenceRecorder.for_occurrences(authorizer, context, producer_id="guard-probe")
    decision = authorizer.evaluate(_ALLOW, context=context)
    try:
        probe.record_decision(decision, mission_id="GOAL-001")
    except ValueError as exc:
        if _GUARD_MESSAGE not in str(exc):
            raise  # an unrelated failure must not pass as the guard
        return True
    return False


@pytest.fixture()
def runtime():
    authorizer = build_authorizer()
    return authorizer, build_context(authorizer)


@pytest.mark.parametrize("request_", [_ALLOW, _DENY], ids=["allow", "deny"])
def test_explicit_recorder_behaviour_matches_installed_core(runtime, request_) -> None:
    authorizer, context = runtime
    recorder = EvidenceRecorder.for_occurrences(authorizer, context, producer_id="explicit-enforce")
    calls: list[int] = []
    observed: list[object] = []

    def run() -> object:
        return enforce(
            authorizer, request_, context=context, recorder=recorder,
            mission_id="GOAL-001", action=lambda: calls.append(1),
            on_decision=observed.append,
        )

    if _core_guards_explicit_recorder():
        with pytest.raises(ValueError, match=_GUARD_MESSAGE):
            run()

        assert calls == []
        assert observed == []  # the hook never sees an unrecorded decision
        assert recorder.stream()["events"] == []
        assert recorder.validate()["status"] == "pass"
        return

    # Core without the guard (nornyx 1.10.x, 1.11.0): the documented old
    # behaviour. The decision is recorded and acted on as with a legacy
    # recorder (ALLOW runs the action exactly once; DENY raises AdapterDenied
    # without running it), but the explicit-mode stream lacks occurrence
    # identity and fails schema validation.
    if request_ is _ALLOW:
        run()
        assert calls == [1]
        expected = ["capability_requested", "capability_allowed"]
    else:
        with pytest.raises(AdapterDenied):
            run()
        assert calls == []
        expected = ["capability_requested", "capability_denied"]

    assert len(observed) == 1
    stream = recorder.stream()
    assert stream["occurrence_mode"] == "explicit"
    assert [event["event_type"] for event in stream["events"]] == expected
    report = recorder.validate()
    assert report["status"] == "fail"
    assert [d["code"] for d in report["diagnostics"] if d["level"] == "error"] == [
        "AN_EVT_SCHEMA_INVALID"
    ]


def test_legacy_recorder_behaviour_is_unchanged(runtime) -> None:
    authorizer, context = runtime
    recorder = EvidenceRecorder(authorizer, context, producer_id="legacy-enforce")
    calls: list[int] = []

    assert enforce(
        authorizer, _ALLOW, context=context, recorder=recorder,
        mission_id="GOAL-001", action=lambda: calls.append(1) or "ran",
    ) == "ran"

    assert calls == [1]
    assert [event["event_type"] for event in recorder.stream()["events"]] == [
        "capability_requested",
        "capability_allowed",
    ]
    assert recorder.validate()["status"] == "pass"
