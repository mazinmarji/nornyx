"""enforce() against the real core recorder in explicit occurrence mode.

``enforce()`` records through the legacy ``record_decision`` call, which carries
no occurrence identity. An explicit-mode recorder requires one on every event,
so the call must fail closed before the action runs and leave the recorder's
stream untouched, rather than running the action and emitting a stream that
fails validation. Legacy-mode behaviour is unchanged.
"""

from __future__ import annotations

import pytest
from nornyx.agentic import CapabilityRequest, EvidenceRecorder

from nornyx_agentic_adapters import enforce
from nornyx_agentic_adapters.conformance.harness import build_authorizer, build_context

_ALLOW = CapabilityRequest("identity.researcher.local", "read_governed_context")
_DENY = CapabilityRequest("identity.reviewer.local", "propose_research_finding")


@pytest.fixture()
def runtime():
    authorizer = build_authorizer()
    return authorizer, build_context(authorizer)


@pytest.mark.parametrize("request_", [_ALLOW, _DENY], ids=["allow", "deny"])
def test_explicit_recorder_fails_closed_before_action(runtime, request_) -> None:
    authorizer, context = runtime
    recorder = EvidenceRecorder.for_occurrences(authorizer, context, producer_id="explicit-enforce")
    calls: list[int] = []
    observed: list[object] = []

    with pytest.raises(ValueError, match="explicit occurrence mode"):
        enforce(
            authorizer, request_, context=context, recorder=recorder,
            mission_id="GOAL-001", action=lambda: calls.append(1),
            on_decision=observed.append,
        )

    assert calls == []
    assert observed == []  # the hook never sees an unrecorded decision
    assert recorder.stream()["events"] == []
    assert recorder.validate()["status"] == "pass"


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
