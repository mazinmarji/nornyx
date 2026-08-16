from __future__ import annotations

import pytest

from nornyx.agentic.authz import (
    Authorizer,
    CapabilityRequest,
    Decision,
    DecisionBasis,
    DecisionCode,
    DecisionEffect,
    EvaluationContext,
)
from nornyx.agentic.authzen import (
    AUTHZEN_ACCESS_EVALUATION_PATH,
    AUTHZEN_API_VERSION,
    NORNYX_AUTHZEN_CAPABILITY_PROFILE,
    AuthZENMappingError,
    capability_request_from_authzen,
    capability_request_to_authzen,
    decision_to_authzen,
    evaluate_authzen_capability,
)

REVISION = "git:" + "a" * 40
DECISION_AT = "2026-08-10T10:00:00Z"


def _request() -> CapabilityRequest:
    return CapabilityRequest(
        identity_ref="agent.research",
        capability_ref="research.summarize",
    )


def _context() -> EvaluationContext:
    return EvaluationContext(
        decision_at=DECISION_AT,
        observed_subject_revision=REVISION,
    )


def _payload() -> dict[str, object]:
    return capability_request_to_authzen(_request(), context=_context())


def test_authzen_constants_pin_final_api_surface() -> None:
    assert AUTHZEN_API_VERSION == "1.0"
    assert AUTHZEN_ACCESS_EVALUATION_PATH == "/access/v1/evaluation"
    assert NORNYX_AUTHZEN_CAPABILITY_PROFILE == "nornyx.authzen.capability.v1"


def test_capability_request_maps_to_authzen_access_evaluation() -> None:
    payload = _payload()

    assert payload == {
        "subject": {"type": "nornyx.agent", "id": "agent.research"},
        "action": {"name": "nornyx.capability.use"},
        "resource": {
            "type": "nornyx.capability",
            "id": "research.summarize",
        },
        "context": {
            "nornyx": {
                "profile": "nornyx.authzen.capability.v1",
                "decision_at": DECISION_AT,
                "observed_subject_revision": REVISION,
            }
        },
    }


def test_authzen_capability_mapping_round_trips_to_public_spi() -> None:
    request, context = capability_request_from_authzen(_payload())

    assert request == _request()
    assert context == _context()


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("subject", "type"), "user"),
        (("action", "name"), "read"),
        (("resource", "type"), "document"),
        (("context", "nornyx", "profile"), "other.profile"),
    ],
)
def test_authzen_decoder_rejects_different_semantics(
    path: tuple[str, ...],
    value: str,
) -> None:
    payload = _payload()
    target = payload
    for key in path[:-1]:
        target = target[key]  # type: ignore[assignment,index]
    target[path[-1]] = value  # type: ignore[index]

    with pytest.raises(AuthZENMappingError):
        capability_request_from_authzen(payload)


def test_authzen_decoder_requires_nornyx_revision_context() -> None:
    payload = _payload()
    nornyx_context = payload["context"]["nornyx"]  # type: ignore[index]
    del nornyx_context["observed_subject_revision"]  # type: ignore[index]

    with pytest.raises(AuthZENMappingError):
        capability_request_from_authzen(payload)


def test_allow_decision_maps_to_authzen_true_with_nornyx_context() -> None:
    result = decision_to_authzen(
        Decision(
            DecisionEffect.ALLOW,
            DecisionCode.ALLOWED,
            basis=(DecisionBasis("membership", "research.summarize"),),
        )
    )

    assert result["decision"] is True
    assert result["context"]["nornyx"] == {
        "profile": NORNYX_AUTHZEN_CAPABILITY_PROFILE,
        "effect": "allow",
        "code": "ALLOWED",
        "basis": [{"kind": "membership", "ref": "research.summarize"}],
    }


def test_deny_decision_maps_to_authzen_false() -> None:
    result = decision_to_authzen(
        Decision(
            DecisionEffect.DENY,
            DecisionCode.CAPABILITY_DENIED,
            "Capability is not held.",
        )
    )

    assert result["decision"] is False
    assert result["context"]["nornyx"]["effect"] == "deny"
    assert result["context"]["nornyx"]["code"] == "CAPABILITY_DENIED"


def test_approval_required_is_non_permitting_in_authzen_1_0() -> None:
    result = decision_to_authzen(
        Decision(
            DecisionEffect.APPROVAL_REQUIRED,
            DecisionCode.APPROVAL_REQUIRED,
            "Human approval is required.",
        )
    )

    assert result["decision"] is False
    assert result["context"]["nornyx"]["effect"] == "approval_required"
    assert result["context"]["nornyx"]["prerequisite"] == "human_approval"


class _StubAuthorizer(Authorizer):
    def __init__(self, decision: Decision) -> None:
        object.__setattr__(self, "decision", decision)

    def evaluate(
        self,
        request: object,
        *,
        context: EvaluationContext,
    ) -> Decision:
        assert request == _request()
        assert context == _context()
        return self.decision


def test_local_bridge_decodes_evaluates_and_encodes_without_transport() -> None:
    authorizer = _StubAuthorizer(
        Decision(DecisionEffect.ALLOW, DecisionCode.ALLOWED)
    )

    assert evaluate_authzen_capability(authorizer, _payload())["decision"] is True
