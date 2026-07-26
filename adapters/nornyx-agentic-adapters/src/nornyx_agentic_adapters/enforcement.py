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

from nornyx.agentic import (
    AuthorizationRequest,
    Authorizer,
    Decision,
    EvaluationContext,
    EvidenceRecorder,
)

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
    on_decision: Callable[[Decision], None] | None = None,
) -> T:
    """Evaluate ``request``, record its decision intents, then run ``action``.

    On ALLOW: records the decision's intents, then calls ``action()`` exactly
    once and returns its result. The caller records any post-action
    observation via ``recorder.record_observation(...)`` only after ``action``
    has actually completed — this function does not do that on the caller's
    behalf, since observation semantics are framework/surface-specific.

    On DENY or APPROVAL_REQUIRED: records the decision's intents and raises
    :class:`AdapterDenied` without calling ``action``.

    ``on_decision``, when supplied, is called with the authoritative
    :class:`~nornyx.agentic.Decision` after its intents are recorded and before
    any branch on the outcome — so a caller can read the decision's public
    ``basis`` (for example, the delegation that authorized a capability) without
    re-evaluating the request or reaching into internals. It is an observation
    hook only: it cannot change the outcome, and it never runs before the
    decision is recorded. It is invoked on DENY as well as ALLOW; an exception
    raised from it propagates before ``action`` is reached, so the boundary
    still fails closed.
    """
    decision = authorizer.evaluate(request, context=context)
    recorder.record_decision(decision, mission_id=mission_id)
    if on_decision is not None:
        on_decision(decision)
    if not decision.allowed:
        raise AdapterDenied(decision)
    return action()
