"""The enforcement boundary: evaluate, record, then (only on ALLOW) execute.

:func:`enforce` is the one place a wrapped adapter action is ever invoked. It
guarantees decision-event intents are recorded before the wrapped callable
runs, and that the callable is never invoked unless the core SPI's ``Decision``
is ALLOW. Any unexpected internal error propagates from ``authorizer.evaluate``
or ``recorder.record_decision`` before ``action`` is reached, so it also fails
closed.
"""

from __future__ import annotations

from typing import Callable, TypeVar

from nornyx.agentic import AuthorizationRequest, Authorizer, EvaluationContext, EvidenceRecorder

from .errors import AdapterDenied

T = TypeVar("T")


def enforce(
    authorizer: Authorizer,
    request: AuthorizationRequest,
    *,
    context: EvaluationContext,
    recorder: EvidenceRecorder,
    mission_id: str,
    action: Callable[[], T],
) -> T:
    """Evaluate ``request``, record its decision intents, then run ``action``.

    On ALLOW: records the decision's intents, then calls ``action()`` exactly
    once and returns its result. The caller records any post-action
    observation via ``recorder.record_observation(...)`` only after ``action``
    has actually completed — this function does not do that on the caller's
    behalf, since observation semantics are framework/surface-specific.

    On DENY or APPROVAL_REQUIRED: records the decision's intents and raises
    :class:`AdapterDenied` without calling ``action``.
    """
    decision = authorizer.evaluate(request, context=context)
    recorder.record_decision(decision, mission_id=mission_id)
    if not decision.allowed:
        raise AdapterDenied(decision)
    return action()
