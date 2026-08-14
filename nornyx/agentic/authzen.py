"""Deterministic OpenID AuthZEN mapping for the public ``nornyx.agentic`` SPI.

This module implements a deliberately narrow interoperability boundary for the
OpenID AuthZEN Authorization API 1.0 Access Evaluation shape. It translates one
public Nornyx request type -- :class:`CapabilityRequest` -- to and from the
AuthZEN subject/action/resource/context information model and translates a
Nornyx :class:`Decision` to an AuthZEN boolean decision.

It is a codec and local evaluation bridge only. It does not implement an HTTP
server or client, authenticate callers, distribute policy, operate a PDP, own a
PEP, execute actions, or add hosted authorization-service deployment semantics.

The Nornyx mapping identifier is project-defined, not an OpenID Foundation
registered profile. AARP and COAZ are tracked separately as evolving AuthZEN
Working Group drafts; this module makes no conformance claim for either draft.
"""

from __future__ import annotations

from typing import Any, Mapping

from .authz import (
    Authorizer,
    CapabilityRequest,
    Decision,
    DecisionCode,
    DecisionEffect,
    EvaluationContext,
)

AUTHZEN_API_VERSION = "1.0"
AUTHZEN_ACCESS_EVALUATION_PATH = "/access/v1/evaluation"
NORNYX_AUTHZEN_CAPABILITY_PROFILE = "nornyx.authzen.capability.v1"

_SUBJECT_TYPE = "nornyx.agent"
_ACTION_NAME = "nornyx.capability.use"
_RESOURCE_TYPE = "nornyx.capability"


class AuthZENMappingError(ValueError):
    """Raised when an AuthZEN payload is outside the supported Nornyx mapping."""


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AuthZENMappingError(f"{field} must be an object")
    return value


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise AuthZENMappingError(f"{field} must be a non-empty string")
    return value


def capability_request_to_authzen(
    request: CapabilityRequest,
    *,
    context: EvaluationContext,
) -> dict[str, Any]:
    """Encode a Nornyx capability request as an AuthZEN Access Evaluation.

    Nornyx's revision and decision-time bindings are carried in the AuthZEN
    request ``context`` under the project-owned ``nornyx`` key. The AuthZEN
    standard permits context attributes but does not define these Nornyx
    semantics.
    """
    if not isinstance(request, CapabilityRequest):
        raise TypeError("request must be a CapabilityRequest")
    if not isinstance(context, EvaluationContext):
        raise TypeError("context must be an EvaluationContext")

    identity_ref = _string(request.identity_ref, "request.identity_ref")
    capability_ref = _string(request.capability_ref, "request.capability_ref")
    decision_at = _string(context.decision_at, "context.decision_at")
    revision = _string(
        context.observed_subject_revision,
        "context.observed_subject_revision",
    )

    return {
        "subject": {"type": _SUBJECT_TYPE, "id": identity_ref},
        "action": {"name": _ACTION_NAME},
        "resource": {"type": _RESOURCE_TYPE, "id": capability_ref},
        "context": {
            "nornyx": {
                "profile": NORNYX_AUTHZEN_CAPABILITY_PROFILE,
                "decision_at": decision_at,
                "observed_subject_revision": revision,
            }
        },
    }


def capability_request_from_authzen(
    payload: Mapping[str, Any],
) -> tuple[CapabilityRequest, EvaluationContext]:
    """Decode the supported AuthZEN capability mapping into Nornyx SPI values.

    The decoder fails closed on a different subject type, action name, resource
    type, profile identifier, or missing Nornyx revision/time context. Extra
    AuthZEN properties are ignored because they are not part of the Nornyx
    authorization decision represented by this mapping.
    """
    root = _object(payload, "payload")
    subject = _object(root.get("subject"), "subject")
    action = _object(root.get("action"), "action")
    resource = _object(root.get("resource"), "resource")
    context = _object(root.get("context"), "context")
    nornyx_context = _object(context.get("nornyx"), "context.nornyx")

    if _string(subject.get("type"), "subject.type") != _SUBJECT_TYPE:
        raise AuthZENMappingError("unsupported subject.type")
    if _string(action.get("name"), "action.name") != _ACTION_NAME:
        raise AuthZENMappingError("unsupported action.name")
    if _string(resource.get("type"), "resource.type") != _RESOURCE_TYPE:
        raise AuthZENMappingError("unsupported resource.type")
    if (
        _string(nornyx_context.get("profile"), "context.nornyx.profile")
        != NORNYX_AUTHZEN_CAPABILITY_PROFILE
    ):
        raise AuthZENMappingError("unsupported Nornyx AuthZEN profile")

    request = CapabilityRequest(
        identity_ref=_string(subject.get("id"), "subject.id"),
        capability_ref=_string(resource.get("id"), "resource.id"),
    )
    evaluation_context = EvaluationContext(
        decision_at=_string(
            nornyx_context.get("decision_at"),
            "context.nornyx.decision_at",
        ),
        observed_subject_revision=_string(
            nornyx_context.get("observed_subject_revision"),
            "context.nornyx.observed_subject_revision",
        ),
    )
    return request, evaluation_context


def decision_to_authzen(decision: Decision) -> dict[str, Any]:
    """Encode a Nornyx decision as an AuthZEN 1.0 Decision object.

    AuthZEN 1.0 has a boolean allow/deny decision. Nornyx
    ``APPROVAL_REQUIRED`` therefore maps to ``decision: false``: the PEP must
    not permit the operation. A namespaced Nornyx context preserves the richer
    effect/code for Nornyx-aware consumers without claiming AARP conformance.
    """
    if not isinstance(decision, Decision):
        raise TypeError("decision must be a Decision")
    if not isinstance(decision.effect, DecisionEffect):
        raise AuthZENMappingError("decision.effect is not a DecisionEffect")
    if not isinstance(decision.code, DecisionCode):
        raise AuthZENMappingError("decision.code is not a DecisionCode")
    if not isinstance(decision.reason, str):
        raise AuthZENMappingError("decision.reason must be a string")

    nornyx_context: dict[str, Any] = {
        "profile": NORNYX_AUTHZEN_CAPABILITY_PROFILE,
        "effect": decision.effect.value,
        "code": decision.code.value,
    }
    if decision.reason:
        nornyx_context["reason"] = decision.reason

    if decision.basis:
        basis: list[dict[str, str]] = []
        for item in decision.basis:
            if not all(isinstance(value, str) for value in (item.kind, item.ref, item.detail)):
                raise AuthZENMappingError("decision basis fields must be strings")
            row = {"kind": item.kind, "ref": item.ref}
            if item.detail:
                row["detail"] = item.detail
            basis.append(row)
        nornyx_context["basis"] = basis

    if decision.effect is DecisionEffect.APPROVAL_REQUIRED:
        nornyx_context["prerequisite"] = "human_approval"

    return {
        "decision": decision.effect is DecisionEffect.ALLOW,
        "context": {"nornyx": nornyx_context},
    }


def evaluate_authzen_capability(
    authorizer: Authorizer,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate one mapped AuthZEN capability request through Nornyx locally."""
    if not isinstance(authorizer, Authorizer):
        raise TypeError("authorizer must be an Authorizer")
    request, context = capability_request_from_authzen(payload)
    return decision_to_authzen(authorizer.evaluate(request, context=context))
