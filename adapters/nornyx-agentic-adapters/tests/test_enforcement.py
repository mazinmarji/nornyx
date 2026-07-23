"""enforce(): evaluate, record, then (only on ALLOW) execute exactly once.

Uses minimal duck-typed test doubles for the Authorizer/EvidenceRecorder
protocol (ADR-0039 itself defines ``Authorizer`` as a ``Protocol``) so these
tests exercise only the adapter's own enforcement contract, not the core SPI's
policy semantics — those are already exhaustively tested in the main nornyx
suite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from nornyx.agentic import CapabilityRequest, Decision, DecisionCode, DecisionEffect, EvaluationContext

from nornyx_agentic_adapters import AdapterDenied, enforce


@dataclass
class _FakeAuthorizer:
    decision: Decision
    calls: list[Any] = field(default_factory=list)
    raise_on_evaluate: Exception | None = None

    def evaluate(self, request: Any, *, context: Any) -> Decision:
        self.calls.append((request, context))
        if self.raise_on_evaluate is not None:
            raise self.raise_on_evaluate
        return self.decision


@dataclass
class _FakeRecorder:
    recorded: list[tuple[Decision, str]] = field(default_factory=list)
    raise_on_record: Exception | None = None

    def record_decision(self, decision: Decision, *, mission_id: str) -> None:
        if self.raise_on_record is not None:
            raise self.raise_on_record
        self.recorded.append((decision, mission_id))


_REQUEST = CapabilityRequest(identity_ref="identity:agent-1", capability_ref="capability:file_write")
_CONTEXT = EvaluationContext(decision_at="2026-07-23T00:00:00Z", observed_subject_revision="git:0123456789abcdef0123456789abcdef01234567")


def _allow() -> Decision:
    return Decision(DecisionEffect.ALLOW, DecisionCode.ALLOWED, "")


def _deny() -> Decision:
    return Decision(DecisionEffect.DENY, DecisionCode.CAPABILITY_DENIED, "denied for test")


def _approval_required() -> Decision:
    return Decision(DecisionEffect.APPROVAL_REQUIRED, DecisionCode.CROSSING_APPROVAL_REQUIRED, "needs approval")


def test_allow_invokes_action_exactly_once_and_returns_its_result() -> None:
    authorizer = _FakeAuthorizer(decision=_allow())
    recorder = _FakeRecorder()
    calls = []

    def action() -> str:
        calls.append(1)
        return "side-effect-happened"

    result = enforce(
        authorizer, _REQUEST, context=_CONTEXT, recorder=recorder, mission_id="mission-1", action=action
    )
    assert result == "side-effect-happened"
    assert len(calls) == 1
    assert recorder.recorded == [(authorizer.decision, "mission-1")]


def test_deny_never_invokes_action_and_raises_adapter_denied() -> None:
    authorizer = _FakeAuthorizer(decision=_deny())
    recorder = _FakeRecorder()
    calls = []

    def action() -> str:
        calls.append(1)
        return "should never happen"

    with pytest.raises(AdapterDenied) as exc_info:
        enforce(authorizer, _REQUEST, context=_CONTEXT, recorder=recorder, mission_id="mission-1", action=action)
    assert calls == []  # the wrapped side effect never ran
    assert exc_info.value.decision is authorizer.decision
    assert recorder.recorded == [(authorizer.decision, "mission-1")]  # decision intents still recorded


def test_approval_required_never_invokes_action() -> None:
    authorizer = _FakeAuthorizer(decision=_approval_required())
    recorder = _FakeRecorder()
    calls = []

    with pytest.raises(AdapterDenied):
        enforce(
            authorizer,
            _REQUEST,
            context=_CONTEXT,
            recorder=recorder,
            mission_id="mission-1",
            action=lambda: calls.append(1),
        )
    assert calls == []


def test_unexpected_evaluate_error_fails_closed() -> None:
    """A bug in evaluate() (not a policy deny) must also prevent the wrapped
    action from running — it fails closed by propagating before `action` is
    ever reached."""
    authorizer = _FakeAuthorizer(decision=_allow(), raise_on_evaluate=RuntimeError("boom"))
    recorder = _FakeRecorder()
    calls = []

    with pytest.raises(RuntimeError, match="boom"):
        enforce(
            authorizer,
            _REQUEST,
            context=_CONTEXT,
            recorder=recorder,
            mission_id="mission-1",
            action=lambda: calls.append(1),
        )
    assert calls == []
    assert recorder.recorded == []


def test_unexpected_record_decision_error_also_fails_closed() -> None:
    """A bug in the recorder must also prevent the wrapped action from running."""
    authorizer = _FakeAuthorizer(decision=_allow())
    recorder = _FakeRecorder(raise_on_record=ValueError("recorder bug"))
    calls = []

    with pytest.raises(ValueError, match="recorder bug"):
        enforce(
            authorizer,
            _REQUEST,
            context=_CONTEXT,
            recorder=recorder,
            mission_id="mission-1",
            action=lambda: calls.append(1),
        )
    assert calls == []
