"""Framework-neutral core authorization engine for ``nornyx.agentic``.

Implements the SPI frozen by ADR-0039: a loaded, immutable, lock-verified
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
  semantics at evaluation.
- The ``Authorizer`` is immutable, synchronous, deterministic, reusable, and safe
  for concurrent evaluation; per-mission sequencing state lives only in the
  ``EvidenceRecorder``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
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
    GovernanceError,
    compose_document_governance,
    evaluate_document_governance,
    registry_for_contract,
)
from ..governance.agentic_network import (
    AGENTIC_APPROVAL_ID,
    EXTERNAL_ZONE_CLASSIFICATIONS,
    SENSITIVE_CATEGORIES,
    _mapping_items,
    _parse_time,
    _revocation_target_key,
    _strings,
)
from ..parser import load_nyx

SPI_VERSION = "1.0"

# Canonical subject-revision syntax (ADR-0039): git 40/64 lowercase hex, or
# sha256 64 lowercase hex. No branch names, abbreviated SHAs, or aliases.
_REVISION_RE = re.compile(r"^(?:git:[0-9a-f]{40}|git:[0-9a-f]{64}|sha256:[0-9a-f]{64})$")


def _valid_revision(value: Any) -> bool:
    return isinstance(value, str) and bool(_REVISION_RE.match(value))


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
    kind: str  # membership|delegation|capability|approval|zone|share|binding
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
    return DecisionEventIntent(
        event_type=event_type,
        fields={k: v for k, v in fields.items() if v is not None},
    )


# ---------------------------------------------------------------------- authorizer
class Authorizer:
    """One loaded, lock-verified contract. Immutable and concurrency-safe."""

    def __init__(
        self,
        document: Mapping[str, Any],
        composition: Any,
        lock_payload: Mapping[str, Any],
    ) -> None:
        self._document = document
        self._composition = composition
        self._lock_payload = lock_payload
        self.contract_digest = contract_digest(document)
        self.network_lock_digest = agentic_network_lock_digest(lock_payload)
        network = document.get("agentic_network")
        self._network: Mapping[str, Any] = network if isinstance(network, Mapping) else {}
        self.network_id = str(self._network.get("id"))
        self.subject_revision = str(self._network.get("subject_revision"))

        self._identities = {
            str(item["id"]): item
            for item in _mapping_items(document.get("agent_identities"))
            if isinstance(item.get("id"), str)
        }
        self._capabilities = {
            str(item["name"]): item
            for item in _mapping_items(document.get("capabilities"))
            if isinstance(item.get("name"), str)
        }
        self._memberships = _mapping_items(self._network.get("memberships"))
        self._zones = {
            str(item["id"]): item
            for item in _mapping_items(self._network.get("trust_zones"))
            if isinstance(item.get("id"), str)
        }
        self._delegations = {
            str(item["id"]): item
            for item in _mapping_items(self._network.get("delegations"))
            if isinstance(item.get("id"), str)
        }
        self._handoffs = {
            str(item["id"]): item
            for item in _mapping_items(self._network.get("handoffs"))
            if isinstance(item.get("id"), str)
        }
        self._revocations = _mapping_items(self._network.get("revocations"))
        # Approval requirements keyed by id, with the composed authority roles.
        self._approvals = {req.id: req for req in composition.approval_requirements}

    # ---- identity resolution (separate from policy decisions) ----
    def resolve_identity(self, framework: str, agent_key: str) -> str:
        matches = [
            identity_id
            for identity_id, identity in sorted(self._identities.items())
            if any(
                binding.get("framework") == framework
                and binding.get("agent_key") == agent_key
                for binding in _mapping_items(identity.get("framework_bindings"))
            )
        ]
        if not matches:
            raise IdentityResolutionError(
                IdentityResolutionCode.IDENTITY_UNKNOWN,
                f"Framework key {agent_key!r} maps to no declared {framework} identity.",
            )
        if len(matches) > 1:
            raise IdentityResolutionError(
                IdentityResolutionCode.IDENTITY_AMBIGUOUS,
                f"Framework key {agent_key!r} maps to multiple declared {framework} identities.",
            )
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
        return self._interval_contains(identity, ts) is True and not self._revoked_at(
            "agent_identity", ref, ts
        )

    def _holds_capability(self, actor: str, capability: str, ts: datetime | None) -> bool:
        identity = self._identities.get(actor)
        if identity is None or capability not in _strings(identity.get("capability_refs")):
            return False
        for membership in self._memberships:
            if membership.get("identity_ref") != actor:
                continue
            if membership.get("status") != "authorized":
                continue
            if self._interval_contains(membership, ts) is not True:
                continue
            if self._revoked_at("membership", str(membership.get("id")), ts):
                continue
            if capability in _strings(membership.get("capability_refs")):
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

    # ---- evaluation ----
    def evaluate(self, request: AuthorizationRequest, *, context: EvaluationContext) -> Decision:
        # Context validity (fail closed).
        ts = _parse_time(context.decision_at)
        if ts is None or not _valid_revision(context.observed_subject_revision):
            return Decision(
                DecisionEffect.DENY,
                DecisionCode.REQUEST_MALFORMED,
                "Malformed evaluation context (decision_at or observed_subject_revision).",
            )
        # Runtime target binding: always exact, unconditional.
        if context.observed_subject_revision != self.subject_revision:
            actor = self._actor_of(request)
            # policy_violation carries the schema-required actor_ref; omit the
            # intent when no actor is derivable (delegation/handoff requests).
            intents = (_intent("policy_violation", actor_ref=actor),) if actor else ()
            return Decision(
                DecisionEffect.DENY,
                DecisionCode.REVISION_MISMATCH,
                "observed_subject_revision does not exactly match the contract subject_revision.",
                basis=(DecisionBasis("binding", self.subject_revision),),
                event_intents=intents,
            )
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
        return Decision(
            DecisionEffect.DENY,
            DecisionCode.REQUEST_MALFORMED,
            f"Unsupported request type {type(request).__name__!r}.",
        )

    @staticmethod
    def _actor_of(request: AuthorizationRequest) -> str | None:
        return getattr(request, "identity_ref", None)

    def _capability(self, request: CapabilityRequest, ts: datetime | None) -> Decision:
        actor, capability = request.identity_ref, request.capability_ref
        if actor not in self._identities:
            return Decision(
                DecisionEffect.DENY,
                DecisionCode.REQUEST_MALFORMED,
                f"Identity {actor!r} is not declared; resolve it first.",
            )
        if capability not in self._capabilities:
            return Decision(
                DecisionEffect.DENY,
                DecisionCode.CAPABILITY_UNKNOWN,
                f"Capability {capability!r} is not declared in the contract.",
                event_intents=(_intent("policy_violation", actor_ref=actor),),
            )
        requested = _intent("capability_requested", actor_ref=actor, capability_ref=capability)
        held = self._holds_capability(actor, capability, ts) and self._identity_effective(actor, ts)
        delegation_ref = None
        if not held:
            delegation_ref = self._delegated(actor, capability, ts)
            if delegation_ref is None or not self._identity_effective(actor, ts):
                return Decision(
                    DecisionEffect.DENY,
                    DecisionCode.CAPABILITY_DENIED,
                    f"Identity {actor!r} neither holds nor validly receives {capability!r} at decision_at.",
                    basis=(DecisionBasis("capability", capability),),
                    event_intents=(
                        requested,
                        _intent(
                            "capability_denied",
                            actor_ref=actor,
                            capability_ref=capability,
                            policy_decision="deny",
                        ),
                    ),
                )
        basis_kind = "membership" if delegation_ref is None else "delegation"
        basis_ref = capability if delegation_ref is None else delegation_ref
        return Decision(
            DecisionEffect.ALLOW,
            DecisionCode.ALLOWED,
            "",
            basis=(DecisionBasis(basis_kind, basis_ref),),
            event_intents=(
                requested,
                _intent(
                    "capability_allowed",
                    actor_ref=actor,
                    capability_ref=capability,
                    policy_decision="allow",
                    delegation_ref=delegation_ref,
                ),
            ),
        )

    def _delegation(self, request: DelegationRequest, ts: datetime | None) -> Decision:
        delegation = self._delegations.get(request.delegation_id)
        if delegation is None:
            return Decision(
                DecisionEffect.DENY,
                DecisionCode.DELEGATION_UNKNOWN,
                f"Delegation {request.delegation_id!r} is not declared.",
            )
        delegator = str(delegation.get("delegator_ref"))
        delegate = str(delegation.get("delegate_ref"))
        requested = _intent(
            "delegation_requested",
            actor_ref=delegator,
            target_ref=delegate,
            delegation_ref=request.delegation_id,
        )
        active = (
            delegation.get("status") == "active"
            and self._interval_contains(delegation, ts) is True
            and not self._revoked_at("delegation", request.delegation_id, ts)
        )
        if not active:
            return Decision(
                DecisionEffect.DENY,
                DecisionCode.DELEGATION_INACTIVE,
                f"Delegation {request.delegation_id!r} is not active at decision_at.",
                basis=(DecisionBasis("delegation", request.delegation_id),),
                event_intents=(
                    requested,
                    _intent(
                        "delegation_rejected",
                        actor_ref=delegate,
                        delegation_ref=request.delegation_id,
                    ),
                ),
            )
        return Decision(
            DecisionEffect.ALLOW,
            DecisionCode.ALLOWED,
            "",
            basis=(DecisionBasis("delegation", request.delegation_id),),
            event_intents=(
                requested,
                _intent(
                    "delegation_accepted",
                    actor_ref=delegate,
                    delegation_ref=request.delegation_id,
                ),
            ),
        )

    def _handoff(self, request: HandoffRequest, ts: datetime | None) -> Decision:
        handoff = self._handoffs.get(request.handoff_id)
        if handoff is None:
            return Decision(
                DecisionEffect.DENY,
                DecisionCode.HANDOFF_UNKNOWN,
                f"Handoff {request.handoff_id!r} is not declared.",
            )
        source = str(handoff.get("from_identity_ref"))
        target = str(handoff.get("to_identity_ref"))
        for capability in _strings(handoff.get("required_capability_refs")):
            if not self._holds_capability(target, capability, ts) and (
                self._delegated(target, capability, ts) is None
            ):
                return Decision(
                    DecisionEffect.DENY,
                    DecisionCode.HANDOFF_AUTHORITY,
                    "A handoff transfers responsibility, never authority: the target "
                    f"does not hold {capability!r}.",
                    basis=(DecisionBasis("capability", capability),),
                    event_intents=(
                        _intent(
                            "policy_violation",
                            actor_ref=source,
                            target_ref=target,
                            handoff_ref=request.handoff_id,
                        ),
                    ),
                )
        # Authorized. handoff_initiated is a post-action OBSERVATION (adapter-emitted).
        return Decision(
            DecisionEffect.ALLOW,
            DecisionCode.ALLOWED,
            "",
            basis=(DecisionBasis("binding", request.handoff_id, "handoff authorized"),),
        )

    def _approval(self, request: ApprovalRequest, ts: datetime | None) -> Decision:
        actor = request.identity_ref
        a = request.approval
        requested = _intent("approval_requested", actor_ref=actor, approval_ref=a.approval_ref)
        effective = self._approvals.get(a.approval_ref)
        if effective is None:
            return Decision(
                DecisionEffect.DENY,
                DecisionCode.REQUEST_MALFORMED,
                f"Approval {a.approval_ref!r} is not a declared requirement.",
                event_intents=(requested,),
            )

        def rejected(code: DecisionCode, reason: str) -> Decision:
            return Decision(
                DecisionEffect.DENY,
                code,
                reason,
                basis=(DecisionBasis("approval", a.approval_ref),),
                event_intents=(
                    requested,
                    _intent(
                        "approval_rejected",
                        actor_ref=actor,
                        approval_ref=a.approval_ref,
                        approver={"role": a.role, "actor_type": a.claimed_actor_type},
                    ),
                ),
            )

        # Revision binding (independent, exact) when the requirement binds a revision.
        binding = effective.revision_binding
        if isinstance(binding, Mapping) and binding.get("revision"):
            if a.subject_revision != str(binding.get("revision")):
                return rejected(
                    DecisionCode.APPROVAL_REVISION_MISMATCH,
                    "Approval subject_revision does not match the required revision binding.",
                )
        # Actor type: a human is required; a denied actor type is rejected.
        denied_types = set(getattr(effective, "denied_actor_types", ()) or ())
        if a.claimed_actor_type != "human" or a.claimed_actor_type in denied_types:
            return rejected(
                DecisionCode.APPROVAL_NON_HUMAN,
                "AI systems, tools, models, and execution surfaces cannot approve.",
            )
        # Role: must be an eligible/required role of the composed requirement.
        eligible = set(getattr(effective, "eligible_roles", ()) or ()) | set(
            getattr(effective, "required_roles", ()) or ()
        )
        if a.role not in eligible:
            return rejected(
                DecisionCode.APPROVAL_ROLE_INVALID,
                f"Role {a.role!r} is outside the composed approval authority.",
            )
        # Temporal staleness/invalidation at decision_at.
        expires = _parse_time(a.expires_at) or _parse_time(getattr(effective, "expires_at", None))
        if expires is not None and ts is not None and ts >= expires:
            return rejected(DecisionCode.APPROVAL_STALE, "The approval is expired at decision_at.")
        if not a.granted:
            return rejected(
                DecisionCode.APPROVAL_NOT_GRANTED,
                "The supplied human approval record does not grant approval.",
            )
        return Decision(
            DecisionEffect.ALLOW,
            DecisionCode.ALLOWED,
            "",
            basis=(DecisionBasis("approval", a.approval_ref),),
            event_intents=(
                requested,
                _intent(
                    "approval_granted",
                    actor_ref=actor,
                    approval_ref=a.approval_ref,
                    approver={"role": a.role, "actor_type": "human"},
                ),
            ),
        )

    def _zone_crossing(self, request: ZoneCrossingRequest, ts: datetime | None) -> Decision:
        actor = request.identity_ref
        zone = self._zones.get(request.source_zone)
        if zone is None or request.target_zone not in _strings(
            zone.get("allowed_transition_targets")
        ):
            return Decision(
                DecisionEffect.DENY,
                DecisionCode.ZONE_CROSSING_DENIED,
                f"Crossing {request.source_zone!r} -> {request.target_zone!r} is not declared.",
                basis=(DecisionBasis("zone", request.target_zone),),
                event_intents=(
                    _intent(
                        "policy_violation",
                        actor_ref=actor,
                        source_zone_ref=request.source_zone if request.source_zone in self._zones else None,
                        target_zone_ref=request.target_zone if request.target_zone in self._zones else None,
                    ),
                ),
            )
        destination = self._zones.get(request.target_zone)
        needs_approval = (
            destination is not None
            and destination.get("classification") in EXTERNAL_ZONE_CLASSIFICATIONS
        )
        if needs_approval and request.approval is None:
            return Decision(
                DecisionEffect.APPROVAL_REQUIRED,
                DecisionCode.CROSSING_APPROVAL_REQUIRED,
                "External trust-zone crossings require a human approval.",
                basis=(DecisionBasis("zone", request.target_zone),),
                event_intents=(_intent("approval_requested", actor_ref=actor, approval_ref=AGENTIC_APPROVAL_ID),),
            )
        approval_intents: tuple[DecisionEventIntent, ...] = ()
        if needs_approval:
            sub = self._approval(ApprovalRequest(actor, request.approval), ts)
            if not sub.allowed:
                return sub
            # The approval materially authorized the crossing; its decision-event
            # intents (approval_requested + approval_granted) are preserved.
            approval_intents = sub.event_intents
        # Authorized. trust_zone_crossed is a post-action OBSERVATION.
        return Decision(
            DecisionEffect.ALLOW,
            DecisionCode.ALLOWED,
            "",
            basis=(DecisionBasis("zone", request.target_zone),),
            event_intents=approval_intents,
        )

    def _data_share(self, request: DataShareRequest, ts: datetime | None) -> Decision:
        actor = request.identity_ref
        categories = set(request.categories)
        sensitive = SENSITIVE_CATEGORIES & categories
        if sensitive:
            return Decision(
                DecisionEffect.DENY,
                DecisionCode.SENSITIVE_SHARING,
                "Sensitive categories are never shareable: " + ", ".join(sorted(sensitive)) + ".",
                basis=(DecisionBasis("share", sorted(sensitive)[0]),),
                event_intents=(_intent("policy_violation", actor_ref=actor, target_ref=request.target_ref),),
            )
        for zone_id in (request.source_zone, request.target_zone):
            zone = self._zones.get(zone_id)
            allowlist = set(_strings(zone.get("share_allowlist"))) if zone else set()
            uncovered = sorted(categories - allowlist)
            if uncovered:
                return Decision(
                    DecisionEffect.DENY,
                    DecisionCode.SHARE_NOT_ALLOWED,
                    f"Zone {zone_id!r} does not allow sharing: " + ", ".join(uncovered) + ".",
                    basis=(DecisionBasis("share", uncovered[0]),),
                    event_intents=(_intent("policy_violation", actor_ref=actor, target_ref=request.target_ref),),
                )
        # Authorized. data_shared is a post-action OBSERVATION.
        return Decision(
            DecisionEffect.ALLOW,
            DecisionCode.ALLOWED,
            "",
            basis=(DecisionBasis("share", "allowlisted"),),
        )


def load_authorizer(
    contract_path: str | Path,
    lock_path: str | Path,
    *,
    validation_as_of: str,
) -> Authorizer:
    """Load, validate (as of ``validation_as_of``), and lock-verify one contract.

    Fails closed with an :class:`AuthorizerLoadError` on any contract diagnostic,
    missing composition, invalid lock, or stale/mismatched lock.
    """
    registry = registry_for_contract(contract_path)
    document = load_nyx(contract_path)
    document_root = Path(contract_path).resolve().parent
    diagnostics = list(check_document(document))
    composition = compose_document_governance(document, registry=registry)
    if composition is None:
        raise AuthorizerLoadError(
            AuthorizerLoadCode.PROFILE_MISSING,
            "The contract does not resolve a governance profile.",
        )
    contributed = {item.block for item in (composition.block_schemas or ())}
    diagnostics = [
        item
        for item in diagnostics
        if not (item.code == "UNKNOWN_TOP_LEVEL_BLOCK" and item.path in contributed)
    ]
    diagnostics.extend(
        evaluate_document_governance(
            document,
            registry=registry,
            as_of=validation_as_of,
            document_root=document_root,
        )
    )
    if has_errors(diagnostics):
        codes = sorted({item.code for item in diagnostics if item.level == "error"})
        raise AuthorizerLoadError(
            AuthorizerLoadCode.CONTRACT_INVALID,
            "The contract fails governance validation: " + ", ".join(codes),
        )
    try:
        lock_payload = load_agentic_network_lock(lock_path)
    except GovernanceError as exc:
        raise AuthorizerLoadError(
            AuthorizerLoadCode.LOCK_INVALID,
            f"Cannot load the agentic-network lock: {exc}",
        ) from exc
    stale = verify_agentic_network_lock(lock_payload, document, composition)
    if stale:
        raise AuthorizerLoadError(
            AuthorizerLoadCode.LOCK_STALE,
            "Stale or mismatched agentic-network lock: "
            + ", ".join(sorted({item.code for item in stale})),
        )
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
    does not exactly equal the authorizer's ``subject_revision``. This refuses to
    silently stamp the contract revision over a mismatched runtime binding, even
    though the stamped value would itself be valid.

    It provides construction and consistency binding ONLY: it does not
    authenticate the adapter, attest the occurrence, or make an event true.
    """

    def __init__(
        self,
        authorizer: Authorizer,
        context: EvaluationContext,
        *,
        producer_id: str,
        producer_version: str = "1.0",
        producer_type: str = "framework_adapter",
    ) -> None:
        if producer_type not in {"framework_adapter", "synthetic_harness"}:
            raise ValueError(f"invalid producer_type {producer_type!r}")
        if context.observed_subject_revision != authorizer.subject_revision:
            raise ValueError(
                "observed_subject_revision does not match the contract subject_revision; "
                "the recorder refuses to bind a mismatched runtime revision."
            )
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
            # equals context.observed_subject_revision (verified at construction).
            "subject_revision": self._authorizer.subject_revision,
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

    def record_observation(
        self,
        event_type: str,
        *,
        mission_id: str,
        **fields: Any,
    ) -> None:
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
        """Validate the assembled stream against the exact contract state."""
        from ..agentic_evidence import validate_runtime_events

        return validate_runtime_events(
            self._authorizer._document,
            self._authorizer._composition,
            self._authorizer._lock_payload,
            self.stream(),
            events_root=events_root,
        )
