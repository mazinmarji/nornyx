"""AdapterDenied and AdapterConfigurationError basic shape."""

from __future__ import annotations

from nornyx.agentic import Decision, DecisionCode, DecisionEffect

from nornyx_agentic_adapters import AdapterConfigurationError, AdapterDenied


def test_adapter_denied_carries_the_decision_unmodified() -> None:
    decision = Decision(DecisionEffect.DENY, DecisionCode.CAPABILITY_DENIED, "no such capability")
    error = AdapterDenied(decision)
    assert error.decision is decision
    assert "CAPABILITY_DENIED" in str(error)
    assert "no such capability" in str(error)


def test_adapter_denied_message_falls_back_to_code_when_reason_blank() -> None:
    decision = Decision(DecisionEffect.DENY, DecisionCode.REQUEST_MALFORMED, "")
    error = AdapterDenied(decision)
    assert "REQUEST_MALFORMED" in str(error)


def test_adapter_configuration_error_is_a_value_error() -> None:
    assert issubclass(AdapterConfigurationError, ValueError)
