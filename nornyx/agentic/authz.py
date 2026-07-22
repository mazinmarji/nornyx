"""Framework-neutral core authorization engine for ``nornyx.agentic``.

Implements the SPI frozen by ADR-0039: a loaded, deeply-immutable, lock-verified
``Authorizer`` that evaluates discriminated authorization requests against Nornyx
contract semantics and returns typed ``Decision`` objects carrying *decision-event
intents only*. A separate ``EvidenceRecorder`` turns those intents (and
adapter-supplied post-action observations) into a schema-valid
``nornyx.agentic_runtime_events.v1`` stream bound to the contract, lock, and the
already-verified observed subject revision.

Boundaries (ADR-0039 / ADR-0040 Tier 2, cooperative):

- The engine authorizes *declared Nornyx concepts only*. It never parses raw
  shell commands, file paths, URLs, or tool arguments.
- It imports no agent framework, executes no tool, authenticates no approver,
  grants no approval, and asserts no runtime-event truth.
- It reads no wall-clock time. ``validation_as_of`` governs load-time document
  validation; ``EvaluationContext.decision_at`` governs *all* temporal action
  semantics (identity/membership/delegation/handoff/approval/revocation validity).
- The ``Authorizer`` is *deeply immutable*: its retained document, lock, and all
  derived indexes are recursively frozen (mappings→read-only, lists→tuples,
  sets→frozensets), detached from the caller's inputs. It is synchronous,
  deterministic, reusable, and safe for concurrent evaluation; per-mission
  sequencing state lives only in the ``EvidenceRecorder``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from ..agentic_artifacts import (
    RUNTIME_EVENTS_SCHEMA_ID,
    RUNTIME_EVENTS_SCHEMA_VERSION,
    agentic_network_lock_digest,
    contract_digest,
    load_agentic_network_lock,
    verify_agentic_network_lock,
)
from ..checker import check_document, has_errors
from ..governance import (
    compose_document_governance,
    evaluate_document_governance,
    registry_for_contract,
)
from ..governance.agentic_network import (
    EXTERNAL_ZONE_CLASSIFICATIONS,
    SENSITIVE_CATEGORIES,
    _parse_duration,
    _parse_time,
    _revocation_target_key,
)
from ..parser import load_nyx

SPI_VERSION = "1.0"

# Canonical subject-revision syntax (ADR-0039): git 40/64 lowercase hex, or
# sha256 64 lowercase hex. No branch names, abbreviated SHAs, or aliases.
_REVISION_RE = re.compile(r"^(?:git:[0-9a-f]{40}|git:[0-9a-f]{64}|sha256:[0-9a-f]{64})$")

# Runtime-event producer types permitted by nornyx.agentic_runtime_events.v1.
_PRODUCER_TYPES = frozenset({"framework_adapter", "synthetic_harness", "external_runtime"})


def _valid_revision(value: Any) -> bool:
    return isinstance(value, str) and bool(_REVISION_RE.match(value))


def _all_str(value: Any) -> bool:
    return isinstance(value, tuple) and all(isinstance(item, str) for item in value)


# Tuple-aware readers (the frozen snapshot uses tuples, not lists).
def _map_items(value: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, (list, tuple)):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _str_items(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(item for item in value if isinstance(item, str))
    return ()


def _deep_freeze(value: Any) -> Any:
    """Recursively freeze: mapping→read-only, list/tuple→tuple, set→frozenset.

    Container copies are new, so the result shares no mutable reference with the
    input; scalars are shared but immutable.
    """
    if isinstance(value, Mapping):
        return MappingProxyType({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_deep_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    """Detached ordinary-container copy of a frozen snapshot (for validators)."""
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return {_thaw(item) for item in value}
    return value


# --------------------------------------------------------------------------- enums
class DecisionEffect(Enum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"


class AuthorizerLoadCode(Enum):
    CONTRACT_INVALID = "CONTRACT_INVALID"
    PROFILE_MISSING = "PROFILE_MISSING"
    LOCK_INVALID = "LOCK_INVALID"
    LOCK_STALE = "LOCK_STALE"


class IdentityResolutionCode(Enum):
    IDENTITY_UNKNOWN = "IDENTITY_UNKNOWN"
    IDENTITY_AMBIGUOUS = "IDENTITY_AMBIGUOUS"


class DecisionCode(Enum):
    ALLOWED = "ALLOWED"
    CAPABILITY_UNKNOWN = "CAPABILITY_UNKNOWN"
    CAPABILITY_DENIED = "CAPABILITY_DENIED"
    DELEGATION_UNKNOWN = "DELEGATION_UNKNOWN"
    DELEGATION_INACTIVE = "DELEGATION_INACTIVE"
    HANDOFF_UNKNOWN = "HANDOFF_UNKNOWN"
    HANDOFF_AUTHORITY = "HANDOFF_AUTHORITY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_NON_HUMAN = "APPROVAL_NON_HUMAN"
    APPROVAL_ROLE_INVALID = "APPROVAL_ROLE_INVALID"
    APPROVAL_NOT_GRANTED = "APPROVAL_NOT_GRANTED"
    APPROVAL_STALE = "APPROVAL_STALE"
    APPROVAL_REVISION_MISMATCH = "APPROVAL_REVISION_MISMATCH"
    # Added under ADR-0039 minor-compatibility (new decision-code members):
    APPROVAL_ACTION_MISMATCH = "APPROVAL_ACTION_MISMATCH"
    APPROVAL_EVIDENCE_MISSING = "APPROVAL_EVIDENCE_MISSING"
    PARTY_INEFFECTIVE = "PARTY_INEFFECTIVE"
    ZONE_CROSSING_DENIED = "ZONE_CROSSING_DENIED"
    CROSSING_APPROVAL_REQUIRED = "CROSSING_APPROVAL_REQUIRED"
    SENSITIVE_SHARING = "SENSITIVE_SHARING"
    SHARE_NOT_ALLOWED = "SHARE_NOT_ALLOWED"
    REVISION_MISMATCH = "REVISION_MISMATCH"
    REQUEST_MALFORMED = "REQUEST_MALFORMED"


# -------------------------------------------------------------------------- errors
class AuthorizerLoadError(RuntimeError):
    """Fail-closed load-time failure carrying an :class:`AuthorizerLoadCode`."""

    def __init__(self, code: AuthorizerLoadCode, message: str):
        super().__init__(f"{code.value}: {message}")
        self.code = code


class IdentityResolutionError(RuntimeError):
    """Raised by :meth:`Authorizer.resolve_identity`; not a policy decision."""

    def __init__(self, code: IdentityResolutionCode, message: str):
        super().__init__(f"{code.value}: {message}")
        self.code = code


# ----------------------------------------------------------------- context + models
@dataclass(frozen=True)
class EvaluationContext:
    decision_at: str  # evaluation instant governing ALL temporal semantics
    observed_subject_revision: str  # MANDATORY; must equal the contract subject_revision


@dataclass(frozen=True)
class ApprovalAssertion:
    approval_ref: str
    claimed_approver_ref: str
    claimed_actor_type: str
    role: str
    granted: bool
    action_ref: str
    subject_revision: str
    issued_at: str | None = None
    expires_at: str | None = None
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapabilityRequest:
    identity_ref: str
    capability_ref: str


@dataclass(frozen=True)
class DelegationRequest:
    delegation_id: str


@dataclass(frozen=True)
class HandoffRequest:
    handoff_id: str


@dataclass(frozen=True)
class ApprovalRequest:
    identity_ref: str
    approval: ApprovalAssertion


@dataclass(frozen=True)
class ZoneCrossingRequest:
    identity_ref: str
    source_zone: str
    target_zone: str
    approval: ApprovalAssertion | None = None


@dataclass(frozen=True)
class DataShareRequest:
    identity_ref: str
    target_ref: str
    categories: tuple[str, ...]
    source_zone: str
    target_zone: str


AuthorizationRequest = (
    CapabilityRequest
    | DelegationRequest
    | HandoffRequest
    | ApprovalRequest
    | ZoneCrossingRequest
    | DataShareRequest
)


@dataclass(frozen=True)
class DecisionBasis:
    kind: str  # membership|delegation|capability|approval|zone|gate|binding|share
    ref: str
    detail: str = ""


@dataclass(frozen=True)
class DecisionEventIntent:
    event_type: str  # a decision-phase event type only (see PHASE_INTENT)
    fields: Mapping[str, Any]  # no timestamp/sequence/producer/digests


@dataclass(frozen=True)
class Decision:
    effect: DecisionEffect
    code: DecisionCode
    reason: str = ""
    basis: tuple[DecisionBasis, ...] = ()
    event_intents: tuple[DecisionEventIntent, ...] = ()

    @property
    def allowed(self) -> bool:
        return self.effect is DecisionEffect.ALLOW


# Frozen event phases (ADR-0039). Only intents may originate from ``evaluate``.
PHASE_INTENT = frozenset(
    {
        "capability_requested",
        "capability_allowed",
        "capability_denied",
        "delegation_requested",
        "delegation_accepted",
        "delegation_rejected",
        "approval_requested",
        "approval_granted",
        "approval_rejected",
        "policy_violation",
    }
)
PHASE_OBSERVATION = frozenset(
    {
        "agent_invoked",
        "tool_invoked",
        "handoff_initiated",
        "handoff_completed",
        "trust_zone_crossed",
        "data_shared",
        "identity_revoked",
        "runtime_failed",
    }
)


def _intent(event_type: str, **fields: Any) -> DecisionEventIntent:
    assert event_type in PHASE_INTENT, event_type
    return DecisionEventIntent(event_type=event_type, fields={k: v for k, v in fields.items() if v is not None})


def _deny(code: DecisionCode, reason: str, *, basis: tuple[DecisionBasis, ...] = (), intents: tuple[DecisionEventIntent, ...] = ()) -> Decision:
    return Decision(DecisionEffect.DENY, code, reason, basis=basis, event_intents=intents)


def _timestamp_ok(value: Any) -> bool:
    return value is None or (isinstance(value, str) and _parse_time(value) is not None)


def _approval_shape_ok(a: Any) -> bool:
    if not isinstance(a, ApprovalAssertion):
        return False
    strs = (a.approval_ref, a.claimed_approver_ref, a.claimed_actor_type, a.role, a.action_ref, a.subject_revision)
    if not all(isinstance(v, str) for v in strs):
        return False
    if not isinstance(a.granted, bool):
        return False
    # Temporal fields must be absent or valid, parseable timestamps (fail closed).
    if not _timestamp_ok(a.issued_at) or not _timestamp_ok(a.expires_at):
        return False
    return _all_str(a.evidence_refs)


# ---------------------------------------------------------------------- authorizer
class Authorizer:
    """One loaded, lock-verified contract. Deeply immutable and thread-safe."""

    def __init__(self, document: Mapping[str, Any], composition: Any, lock_payload: Mapping[str, Any]) -> None:
        object.__setattr__(self, "_frozen", False)
        # Deep-frozen, detached snapshots of all retained contract state.
        self._document = _deep_freeze(document)
        self._lock_payload = _deep_freeze(lock_payload)
        self._composition = composition
        # Digests are computed from the frozen snapshot content.
        self.contract_digest = contract_digest(_thaw(self._document))
        self.network_lock_digest = agentic_network_lock_digest(_thaw(self._lock_payload))
        network = self._document.get("agentic_network")
        self._network: Mapping[str, Any] = network if isinstance(network, Mapping) else MappingProxyType({})
        self.network_id = str(self._network.get("id"))
        self.subject_revision = str(self._network.get("subject_revision"))

        self._identities = MappingProxyType(
            {str(item["id"]): item for item in _map_items(self._document.get("agent_identities")) if isinstance(item.get("id"), str)}
        )
        self._capabilities = MappingProxyType(
            {str(item["name"]): item for item in _map_items(self._document.get("capabilities")) if isinstance(item.get("name"), str)}
        )
        self._memberships = _map_items(self._network.get("memberships"))
        self._zones = MappingProxyType(
            {str(item["id"]): item for item in _map_items(self._network.get("trust_zones")) if isinstance(item.get("id"), str)}
        )
        self._gates = _map_items(self._network.get("network_gates"))
        self._delegations = MappingProxyType(
            {str(item["id"]): item for item in _map_items(self._network.get("delegations")) if isinstance(item.get("id"), str)}
        )
        self._handoffs = MappingProxyType(
            {str(item["id"]): item for item in _map_items(self._network.get("handoffs")) if isinstance(item.get("id"), str)}
        )
        self._revocations = _map_items(self._network.get("revocations"))
        self._approvals = MappingProxyType({req.id: req for req in composition.approval_requirements})
        object.__setattr__(self, "_frozen", True)

    # ---- structural immutability ----
    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_frozen", False):
            raise AttributeError(f"Authorizer is immutable; cannot set {name!r}")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        raise AttributeError("Authorizer is immutable")

    # ---- identity resolution (separate from policy decisions) ----
    def resolve_identity(self, framework: str, agent_key: str) -> str:
        matches = [
            identity_id
            for identity_id, identity in sorted(self._identities.items())
            if any(binding.get("framework") == framework and binding.get("agent_key") == agent_key for binding in _map_items(identity.get("framework_bindings")))
        ]
        if not matches:
            raise IdentityResolutionError(IdentityResolutionCode.IDENTITY_UNKNOWN, f"Framework key {agent_key!r} maps to no declared {framework} identity.")
        if len(matches) > 1:
            raise IdentityResolutionError(IdentityResolutionCode.IDENTITY_AMBIGUOUS, f"Framework key {agent_key!r} maps to multiple declared {framework} identities.")
        return matches[0]

    # ---- temporal helpers (all evaluated at decision_at) ----
    @staticmethod
    def _interval_contains(item: Mapping[str, Any], ts: datetime | None) -> bool | None:
        valid_from = _parse_time(item.get("valid_from"))
        expires_at = _parse_time(item.get("expires_at"))
        if valid_from is None or expires_at is None or ts is None:
            return None
        return valid_from <= ts < expires_at

    def _revoked_at(self, kind: str, ref: str, ts: datetime | None) -> bool:
        if ts is None:
            return False
        for revocation in self._revocations:
            if _revocation_target_key(revocation.get("target")) != (kind, ref):
                continue
            effective = _parse_time(revocation.get("effective_at"))
            if effective is not None and ts >= effective:
                return True
        return False

    def _identity_effective(self, ref: str, ts: datetime | None) -> bool:
        identity = self._identities.get(ref)
        if identity is None or identity.get("status") != "active":
            return False
        return self._interval_contains(identity, ts) is True and not self._revoked_at("agent_identity", ref, ts)

    def _zone_member(self, actor: str, zone: str, ts: datetime | None) -> bool:
        for membership in self._memberships:
            if membership.get("identity_ref") != actor or membership.get("trust_zone_ref") != zone:
                continue
            if membership.get("status") != "authorized":
                continue
            if self._interval_contains(membership, ts) is not True:
                continue
            if self._revoked_at("membership", str(membership.get("id")), ts):
                continue
            return True
        return False

    def _holds_capability(self, actor: str, capability: str, ts: datetime | None) -> bool:
        identity = self._identities.get(actor)
        if identity is None or capability not in _str_items(identity.get("capability_refs")):
            return False
        for membership in self._memberships:
            if membership.get("identity_ref") != actor or membership.get("status") != "authorized":
                continue
            if self._interval_contains(membership, ts) is not True:
                continue
            if self._revoked_at("membership", str(membership.get("id")), ts):
                continue
            if capability in _str_items(membership.get("capability_refs")):
                return True
        return False

    def _delegated(self, actor: str, capability: str, ts: datetime | None) -> str | None:
        for delegation_id, delegation in sorted(self._delegations.items()):
            if (
                delegation.get("delegate_ref") == actor
                and delegation.get("capability_ref") == capability
                and delegation.get("status") == "active"
                and self._interval_contains(delegation, ts) is True
                and not self._revoked_at("delegation", delegation_id, ts)
            ):
                return delegation_id
        return None

    # ---- request-shape validation (fail closed before any dict/set access) ----
    @staticmethod
    def _shape_ok(request: AuthorizationRequest) -> bool:
        if isinstance(request, CapabilityRequest):
            return isinstance(request.identity_ref, str) and isinstance(request.capability_ref, str)
        if isinstance(request, DelegationRequest):
            return isinstance(request.delegation_id, str)
        if isinstance(request, HandoffRequest):
            return isinstance(request.handoff_id, str)
        if isinstance(request, ApprovalRequest):
            return isinstance(request.identity_ref, str) and _approval_shape_ok(request.approval)
        if isinstance(request, ZoneCrossingRequest):
            return (
                isinstance(request.identity_ref, str)
                and isinstance(request.source_zone, str)
                and isinstance(request.target_zone, str)
                and (request.approval is None or _approval_shape_ok(request.approval))
            )
        if isinstance(request, DataShareRequest):
            return (
                isinstance(request.identity_ref, str)
                and isinstance(request.target_ref, str)
                and isinstance(request.source_zone, str)
                and isinstance(request.target_zone, str)
                and _all_str(request.categories)
            )
        return False

    # ---- evaluation ----
    def evaluate(self, request: AuthorizationRequest, *, context: EvaluationContext) -> Decision:
        if not isinstance(context, EvaluationContext):
            return _deny(DecisionCode.REQUEST_MALFORMED, "context is not an EvaluationContext.")
        ts = _parse_time(context.decision_at)
        if ts is None or not _valid_revision(context.observed_subject_revision):
            return _deny(DecisionCode.REQUEST_MALFORMED, "Malformed evaluation context (decision_at or observed_subject_revision).")
        if not isinstance(request, AuthorizationRequest) or not self._shape_ok(request):
            return _deny(DecisionCode.REQUEST_MALFORMED, "Malformed authorization request.")
        if context.observed_subject_revision != self.subject_revision:
            actor = self._actor_of(request)
            intents = (_intent("policy_violation", actor_ref=actor),) if actor else ()
            return _deny(DecisionCode.REVISION_MISMATCH, "observed_subject_revision does not exactly match the contract subject_revision.", basis=(DecisionBasis("binding", self.subject_revision),), intents=intents)
        if isinstance(request, CapabilityRequest):
            return self._capability(request, ts)
        if isinstance(request, DelegationRequest):
            return self._delegation(request, ts)
        if isinstance(request, HandoffRequest):
            return self._handoff(request, ts)
        if isinstance(request, ApprovalRequest):
            return self._approval(request, ts)
        if isinstance(request, ZoneCrossingRequest):
            return self._zone_crossing(request, ts)
        if isinstance(request, DataShareRequest):
            return self._data_share(request, ts)
        return _deny(DecisionCode.REQUEST_MALFORMED, f"Unsupported request type {type(request).__name__!r}.")

    @staticmethod
    def _actor_of(request: AuthorizationRequest) -> str | None:
        return getattr(request, "identity_ref", None)

    def _known_effective(self, ref: str, ts: datetime | None) -> Decision | None:
        if ref not in self._identities:
            return _deny(DecisionCode.REQUEST_MALFORMED, f"Identity {ref!r} is not declared; resolve it first.")
        if not self._identity_effective(ref, ts):
            return _deny(
                DecisionCode.PARTY_INEFFECTIVE,
                f"Identity {ref!r} is inactive, outside its validity window, or revoked at decision_at.",
                basis=(DecisionBasis("binding", ref),),
                intents=(_intent("policy_violation", actor_ref=ref),),
            )
        return None

    def _capability(self, request: CapabilityRequest, ts: datetime | None) -> Decision:
        actor, capability = request.identity_ref, request.capability_ref
        bad = self._known_effective(actor, ts)
        if bad is not None:
            return bad
        if capability not in self._capabilities:
            return _deny(DecisionCode.CAPABILITY_UNKNOWN, f"Capability {capability!r} is not declared in the contract.", intents=(_intent("policy_violation", actor_ref=actor),))
        requested = _intent("capability_requested", actor_ref=actor, capability_ref=capability)
        delegation_ref = None
        if not self._holds_capability(actor, capability, ts):
            delegation_ref = self._delegated(actor, capability, ts)
            if delegation_ref is None:
                return _deny(
                    DecisionCode.CAPABILITY_DENIED,
                    f"Identity {actor!r} neither holds nor validly receives {capability!r} at decision_at.",
                    basis=(DecisionBasis("capability", capability),),
                    intents=(requested, _intent("capability_denied", actor_ref=actor, capability_ref=capability, policy_decision="deny")),
                )
        basis = DecisionBasis("membership" if delegation_ref is None else "delegation", capability if delegation_ref is None else delegation_ref)
        return Decision(
            DecisionEffect.ALLOW,
            DecisionCode.ALLOWED,
            "",
            basis=(basis,),
            event_intents=(requested, _intent("capability_allowed", actor_ref=actor, capability_ref=capability, policy_decision="allow", delegation_ref=delegation_ref)),
        )

    def _delegation(self, request: DelegationRequest, ts: datetime | None) -> Decision:
        delegation = self._delegations.get(request.delegation_id)
        if delegation is None:
            return _deny(DecisionCode.DELEGATION_UNKNOWN, f"Delegation {request.delegation_id!r} is not declared.")
        delegator = str(delegation.get("delegator_ref"))
        delegate = str(delegation.get("delegate_ref"))
        for party in (delegator, delegate):
            bad = self._known_effective(party, ts)
            if bad is not None:
                return bad
        requested = _intent("delegation_requested", actor_ref=delegator, target_ref=delegate, delegation_ref=request.delegation_id)
        active = delegation.get("status") == "active" and self._interval_contains(delegation, ts) is True and not self._revoked_at("delegation", request.delegation_id, ts)
        if not active:
            return _deny(
                DecisionCode.DELEGATION_INACTIVE,
                f"Delegation {request.delegation_id!r} is not active at decision_at.",
                basis=(DecisionBasis("delegation", request.delegation_id),),
                intents=(requested, _intent("delegation_rejected", actor_ref=delegate, delegation_ref=request.delegation_id)),
            )
        return Decision(
            DecisionEffect.ALLOW,
            DecisionCode.ALLOWED,
            "",
            basis=(DecisionBasis("delegation", request.delegation_id),),
            event_intents=(requested, _intent("delegation_accepted", actor_ref=delegate, delegation_ref=request.delegation_id)),
        )

    def _handoff(self, request: HandoffRequest, ts: datetime | None) -> Decision:
        handoff = self._handoffs.get(request.handoff_id)
        if handoff is None:
            return _deny(DecisionCode.HANDOFF_UNKNOWN, f"Handoff {request.handoff_id!r} is not declared.")
        source = str(handoff.get("from_identity_ref"))
        target = str(handoff.get("to_identity_ref"))
        for party in (source, target):
            bad = self._known_effective(party, ts)
            if bad is not None:
                return bad
        for capability in _str_items(handoff.get("required_capability_refs")):
            if not self._holds_capability(target, capability, ts) and self._delegated(target, capability, ts) is None:
                return _deny(
                    DecisionCode.HANDOFF_AUTHORITY,
                    f"A handoff transfers responsibility, never authority: the target does not hold {capability!r}.",
                    basis=(DecisionBasis("capability", capability),),
                    intents=(_intent("policy_violation", actor_ref=source, target_ref=target, handoff_ref=request.handoff_id),),
                )
        # Authorized. handoff_initiated is a post-action OBSERVATION (adapter-emitted).
        return Decision(DecisionEffect.ALLOW, DecisionCode.ALLOWED, "", basis=(DecisionBasis("binding", request.handoff_id, "handoff authorized"),))

    def _approval(self, request: ApprovalRequest, ts: datetime | None, *, governed_actions: frozenset[str] | None = None) -> Decision:
        actor = request.identity_ref
        a = request.approval
        bad = self._known_effective(actor, ts)
        if bad is not None:
            return bad
        requested = _intent("approval_requested", actor_ref=actor, approval_ref=a.approval_ref)
        effective = self._approvals.get(a.approval_ref)
        if effective is None:
            return _deny(DecisionCode.REQUEST_MALFORMED, f"Approval {a.approval_ref!r} is not a declared requirement.", intents=(requested,))

        def rejected(code: DecisionCode, reason: str) -> Decision:
            return _deny(code, reason, basis=(DecisionBasis("approval", a.approval_ref),), intents=(requested, _intent("approval_rejected", actor_ref=actor, approval_ref=a.approval_ref, approver={"role": a.role, "actor_type": a.claimed_actor_type})))

        # Universal context binding: the approval must be for the current subject
        # revision. Any governed change bumps subject_revision (and lock
        # verification rejects drift), so this enforces the invalidation
        # conditions that the assertion alone cannot otherwise establish.
        if a.subject_revision != self.subject_revision:
            return rejected(DecisionCode.APPROVAL_REVISION_MISMATCH, "Approval subject_revision does not match the contract subject_revision.")
        # A declared revision_binding is an additional, independent exact check.
        binding = effective.revision_binding
        if isinstance(binding, Mapping) and binding.get("revision") and a.subject_revision != str(binding.get("revision")):
            return rejected(DecisionCode.APPROVAL_REVISION_MISMATCH, "Approval subject_revision does not match the required revision binding.")
        # Action scope: governed by the gate for a crossing, else by the requirement.
        action_scope = governed_actions if governed_actions is not None else frozenset(getattr(effective, "actions_requiring_approval", ()) or ())
        if action_scope and a.action_ref not in action_scope:
            return rejected(DecisionCode.APPROVAL_ACTION_MISMATCH, f"Approval action {a.action_ref!r} is outside the governed action scope.")
        denied_types = set(getattr(effective, "denied_actor_types", ()) or ())
        if a.claimed_actor_type != "human" or a.claimed_actor_type in denied_types:
            return rejected(DecisionCode.APPROVAL_NON_HUMAN, "AI systems, tools, models, and execution surfaces cannot approve.")
        eligible = set(getattr(effective, "eligible_roles", ()) or ()) | set(getattr(effective, "required_roles", ()) or ())
        if a.role not in eligible:
            return rejected(DecisionCode.APPROVAL_ROLE_INVALID, f"Role {a.role!r} is outside the composed approval authority.")
        required_evidence = set(getattr(effective, "required_evidence", ()) or ())
        if required_evidence and not required_evidence.issubset(set(a.evidence_refs)):
            return rejected(DecisionCode.APPROVAL_EVIDENCE_MISSING, "The approval does not reference all required evidence.")
        # Temporal validity at decision_at: earliest applicable expiry across the
        # assertion expiry, the effective absolute expiry, and issued_at +
        # expires_after. Future-issued approvals fail closed. (Field FORMATS were
        # validated in _approval_shape_ok; malformed values never reach here.)
        issued = _parse_time(a.issued_at)
        max_age = _parse_duration(getattr(effective, "expires_after", None))
        if getattr(effective, "expires_after", None) is not None and issued is None:
            return rejected(DecisionCode.APPROVAL_STALE, "The requirement uses a relative expiry but the approval declares no issuance time.")
        if issued is not None and ts is not None and ts < issued:
            return rejected(DecisionCode.APPROVAL_STALE, "The approval is issued after decision_at (not yet valid).")
        expiries: list[datetime] = [c for c in (_parse_time(a.expires_at), _parse_time(getattr(effective, "expires_at", None))) if c is not None]
        if issued is not None and max_age is not None:
            expiries.append(issued + max_age)
        if expiries and ts is not None and ts >= min(expiries):
            return rejected(DecisionCode.APPROVAL_STALE, "The approval is expired at decision_at (earliest applicable expiry).")
        if not a.granted:
            return rejected(DecisionCode.APPROVAL_NOT_GRANTED, "The supplied human approval record does not grant approval.")
        return Decision(
            DecisionEffect.ALLOW,
            DecisionCode.ALLOWED,
            "",
            basis=(DecisionBasis("approval", a.approval_ref),),
            event_intents=(requested, _intent("approval_granted", actor_ref=actor, approval_ref=a.approval_ref, approver={"role": a.role, "actor_type": "human"})),
        )

    def _governing_gates(self, source: str, target: str) -> tuple[Mapping[str, Any], ...]:
        return tuple(gate for gate in self._gates if source in _str_items(gate.get("source_zone_refs")) and target in _str_items(gate.get("target_zone_refs")))

    def _zone_crossing(self, request: ZoneCrossingRequest, ts: datetime | None) -> Decision:
        actor = request.identity_ref
        bad = self._known_effective(actor, ts)
        if bad is not None:
            return bad
        zone = self._zones.get(request.source_zone)
        if zone is None or request.target_zone not in _str_items(zone.get("allowed_transition_targets")):
            return _deny(
                DecisionCode.ZONE_CROSSING_DENIED,
                f"Crossing {request.source_zone!r} -> {request.target_zone!r} is not declared.",
                basis=(DecisionBasis("zone", request.target_zone),),
                intents=(_intent("policy_violation", actor_ref=actor, source_zone_ref=request.source_zone if request.source_zone in self._zones else None, target_zone_ref=request.target_zone if request.target_zone in self._zones else None),),
            )
        if not self._zone_member(actor, request.source_zone, ts):
            return _deny(
                DecisionCode.ZONE_CROSSING_DENIED,
                f"Identity {actor!r} has no valid membership in source zone {request.source_zone!r}.",
                basis=(DecisionBasis("zone", request.source_zone),),
                intents=(_intent("policy_violation", actor_ref=actor, source_zone_ref=request.source_zone, target_zone_ref=request.target_zone),),
            )
        destination = self._zones.get(request.target_zone)
        needs_approval = destination is not None and destination.get("classification") in EXTERNAL_ZONE_CLASSIFICATIONS
        approval_intents: tuple[DecisionEventIntent, ...] = ()
        gate_basis: tuple[DecisionBasis, ...] = ()
        if needs_approval:
            gates = self._governing_gates(request.source_zone, request.target_zone)
            if not gates:
                return _deny(
                    DecisionCode.ZONE_CROSSING_DENIED,
                    "No declared gate governs this external trust-zone crossing.",
                    basis=(DecisionBasis("zone", request.target_zone),),
                    intents=(_intent("policy_violation", actor_ref=actor, source_zone_ref=request.source_zone, target_zone_ref=request.target_zone),),
                )
            if request.approval is None:
                expected = sorted({r for g in gates for r in _str_items(g.get("required_approval_refs"))})
                return Decision(
                    DecisionEffect.APPROVAL_REQUIRED,
                    DecisionCode.CROSSING_APPROVAL_REQUIRED,
                    "External trust-zone crossings require a human approval.",
                    basis=(DecisionBasis("zone", request.target_zone),),
                    event_intents=(_intent("approval_requested", actor_ref=actor, approval_ref=(expected[0] if expected else None)),),
                )
            ar, ac = request.approval.approval_ref, request.approval.action_ref
            # Per-gate authority: one individual gate must require this approval
            # AND govern this action. No union across gates.
            matched = [g for g in gates if ar in _str_items(g.get("required_approval_refs")) and ac in _str_items(g.get("action_classes"))]
            if not matched:
                approval_gates = [g for g in gates if ar in _str_items(g.get("required_approval_refs"))]
                if approval_gates:
                    return _deny(
                        DecisionCode.APPROVAL_ACTION_MISMATCH,
                        f"Action {ac!r} is not governed by the gate(s) requiring approval {ar!r} for this crossing.",
                        basis=(DecisionBasis("zone", request.target_zone),),
                        intents=(_intent("policy_violation", actor_ref=actor, source_zone_ref=request.source_zone, target_zone_ref=request.target_zone),),
                    )
                return _deny(
                    DecisionCode.CROSSING_APPROVAL_REQUIRED,
                    f"Approval {ar!r} is not required by any gate governing this crossing.",
                    basis=(DecisionBasis("zone", request.target_zone),),
                    intents=(_intent("policy_violation", actor_ref=actor, source_zone_ref=request.source_zone, target_zone_ref=request.target_zone),),
                )
            gate_basis = tuple(DecisionBasis("gate", str(g.get("id"))) for g in matched)
            sub = self._approval(ApprovalRequest(actor, request.approval), ts, governed_actions=frozenset({ac}))
            if not sub.allowed:
                return sub
            approval_intents = sub.event_intents
        # Authorized. trust_zone_crossed is a post-action OBSERVATION.
        return Decision(DecisionEffect.ALLOW, DecisionCode.ALLOWED, "", basis=(DecisionBasis("zone", request.target_zone),) + gate_basis, event_intents=approval_intents)

    def _data_share(self, request: DataShareRequest, ts: datetime | None) -> Decision:
        actor = request.identity_ref
        for party in (actor, request.target_ref):
            bad = self._known_effective(party, ts)
            if bad is not None:
                return bad
        categories = set(request.categories)
        sensitive = SENSITIVE_CATEGORIES & categories
        if sensitive:
            return _deny(DecisionCode.SENSITIVE_SHARING, "Sensitive categories are never shareable: " + ", ".join(sorted(sensitive)) + ".", basis=(DecisionBasis("share", sorted(sensitive)[0]),), intents=(_intent("policy_violation", actor_ref=actor, target_ref=request.target_ref),))
        for zone_id in (request.source_zone, request.target_zone):
            zone = self._zones.get(zone_id)
            allowlist = set(_str_items(zone.get("share_allowlist"))) if zone else set()
            uncovered = sorted(categories - allowlist)
            if uncovered:
                return _deny(DecisionCode.SHARE_NOT_ALLOWED, f"Zone {zone_id!r} does not allow sharing: " + ", ".join(uncovered) + ".", basis=(DecisionBasis("share", uncovered[0]),), intents=(_intent("policy_violation", actor_ref=actor, target_ref=request.target_ref),))
        # Authorized. data_shared is a post-action OBSERVATION.
        return Decision(DecisionEffect.ALLOW, DecisionCode.ALLOWED, "", basis=(DecisionBasis("share", "allowlisted"),))


def load_authorizer(contract_path: str | Path, lock_path: str | Path, *, validation_as_of: str) -> Authorizer:
    """Load, validate (as of ``validation_as_of``), and lock-verify one contract.

    Fails closed with an :class:`AuthorizerLoadError` mapping every stage failure
    deterministically into the frozen load taxonomy: contract/parser/registry/
    check/composition -> CONTRACT_INVALID; missing profile -> PROFILE_MISSING;
    lock read/parse -> LOCK_INVALID; lock verification -> LOCK_STALE.
    """
    try:
        registry = registry_for_contract(contract_path)
        document = load_nyx(contract_path)
    except AuthorizerLoadError:
        raise
    except Exception as exc:  # noqa: BLE001 - deterministic fail-closed mapping
        raise AuthorizerLoadError(AuthorizerLoadCode.CONTRACT_INVALID, f"Cannot load the contract: {type(exc).__name__}") from exc
    if not isinstance(document, Mapping):
        raise AuthorizerLoadError(AuthorizerLoadCode.CONTRACT_INVALID, "The contract is not a mapping/object.")
    document_root = Path(contract_path).resolve().parent
    try:
        diagnostics = list(check_document(document))
        composition = compose_document_governance(document, registry=registry)
    except Exception as exc:  # noqa: BLE001
        raise AuthorizerLoadError(AuthorizerLoadCode.CONTRACT_INVALID, f"The contract fails to compose: {type(exc).__name__}") from exc
    if composition is None:
        raise AuthorizerLoadError(AuthorizerLoadCode.PROFILE_MISSING, "The contract does not resolve a governance profile.")
    contributed = {item.block for item in (composition.block_schemas or ())}
    diagnostics = [item for item in diagnostics if not (item.code == "UNKNOWN_TOP_LEVEL_BLOCK" and item.path in contributed)]
    try:
        diagnostics.extend(evaluate_document_governance(document, registry=registry, as_of=validation_as_of, document_root=document_root))
    except Exception as exc:  # noqa: BLE001
        raise AuthorizerLoadError(AuthorizerLoadCode.CONTRACT_INVALID, f"The contract fails governance evaluation: {type(exc).__name__}") from exc
    if has_errors(diagnostics):
        codes = sorted({item.code for item in diagnostics if item.level == "error"})
        raise AuthorizerLoadError(AuthorizerLoadCode.CONTRACT_INVALID, "The contract fails governance validation: " + ", ".join(codes))
    try:
        lock_payload = load_agentic_network_lock(lock_path)
    except Exception as exc:  # noqa: BLE001
        raise AuthorizerLoadError(AuthorizerLoadCode.LOCK_INVALID, f"Cannot load the agentic-network lock: {type(exc).__name__}") from exc
    try:
        stale = verify_agentic_network_lock(lock_payload, document, composition)
    except Exception as exc:  # noqa: BLE001
        raise AuthorizerLoadError(AuthorizerLoadCode.LOCK_STALE, f"Cannot verify the agentic-network lock: {type(exc).__name__}") from exc
    if stale:
        raise AuthorizerLoadError(AuthorizerLoadCode.LOCK_STALE, "Stale or mismatched agentic-network lock: " + ", ".join(sorted({item.code for item in stale})))
    return Authorizer(document, composition, lock_payload)


# ------------------------------------------------------------------ evidence recorder
class EvidenceRecorder:
    """Deterministic construction + consistency binding for runtime evidence.

    Turns decision-event intents and adapter-supplied post-action observations
    into a schema-valid ``nornyx.agentic_runtime_events.v1`` stream bound to the
    contract, lock, and already-verified observed subject revision. It stamps ids,
    mission-local sequence numbers, producer, timestamps (from the bound
    ``context.decision_at`` — no wall-clock), and binding digests.

    The bound ``EvaluationContext`` is validated **once at construction**: the
    recorder fails closed (``ValueError``) if ``context.observed_subject_revision``
    does not exactly equal the authorizer's ``subject_revision``.

    It provides construction and consistency binding ONLY: it does not
    authenticate the adapter, attest the occurrence, or make an event true.
    Permitting the ``external_runtime`` producer label confers no Tier-3 assurance.
    """

    def __init__(self, authorizer: Authorizer, context: EvaluationContext, *, producer_id: str, producer_version: str = "1.0", producer_type: str = "framework_adapter") -> None:
        if producer_type not in _PRODUCER_TYPES:
            raise ValueError(f"invalid producer_type {producer_type!r}; permitted: {sorted(_PRODUCER_TYPES)}")
        if context.observed_subject_revision != authorizer.subject_revision:
            raise ValueError("observed_subject_revision does not match the contract subject_revision; the recorder refuses to bind a mismatched runtime revision.")
        self._authorizer = authorizer
        self._context = context
        self._producer = {"type": producer_type, "id": producer_id, "version": producer_version}
        self._events: list[dict[str, Any]] = []
        self._sequences: dict[str, int] = {}

    def _stamp(self, event_type: str, mission_id: str, fields: Mapping[str, Any]) -> None:
        seq = self._sequences.get(mission_id, 0) + 1
        self._sequences[mission_id] = seq
        event: dict[str, Any] = {
            "event_id": f"{mission_id}-{seq:04d}",
            "event_type": event_type,
            "mission_id": mission_id,
            "sequence": seq,
            "timestamp": self._context.decision_at,
            "network_id": self._authorizer.network_id,
            "contract_digest": self._authorizer.contract_digest,
            "network_lock_digest": self._authorizer.network_lock_digest,
            "subject_revision": self._authorizer.subject_revision,  # == verified observed revision
            "producer": dict(self._producer),
        }
        event.update({k: v for k, v in fields.items() if v is not None})
        self._events.append(event)

    def record_decision(self, decision: Decision, *, mission_id: str) -> None:
        """Record the decision's intents. Intents only — never observations."""
        for intent in decision.event_intents:
            if intent.event_type not in PHASE_INTENT:
                raise ValueError(f"{intent.event_type!r} is not a decision-event intent")
            self._stamp(intent.event_type, mission_id, intent.fields)

    def record_observation(self, event_type: str, *, mission_id: str, **fields: Any) -> None:
        """Record a post-action observation. Only the adapter, after the action."""
        if event_type not in PHASE_OBSERVATION:
            raise ValueError(f"{event_type!r} is not a post-action observation")
        self._stamp(event_type, mission_id, fields)

    def stream(self) -> dict[str, Any]:
        return {
            "schema": RUNTIME_EVENTS_SCHEMA_ID,
            "schema_version": RUNTIME_EVENTS_SCHEMA_VERSION,
            "network_id": self._authorizer.network_id,
            "producer": dict(self._producer),
            "events": [dict(event) for event in self._events],
        }

    def validate(self, *, events_root: Path | None = None) -> dict[str, Any]:
        """Validate the assembled stream against a detached thaw of the snapshot."""
        from ..agentic_evidence import validate_runtime_events

        return validate_runtime_events(
            _thaw(self._authorizer._document),
            self._authorizer._composition,
            _thaw(self._authorizer._lock_payload),
            self.stream(),
            events_root=events_root,
        )
