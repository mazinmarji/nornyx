"""Deprecated compatibility facade over the supported Nornyx agentic SPI.

``GovernanceKernel`` preserves the unpackaged ADR-0037 reference API while
delegating every authorization decision to ``nornyx.agentic.Authorizer`` and
all runtime-event construction to ``nornyx.agentic.EvidenceRecorder``.  It is
not an independent policy or evidence engine.

**Single source of authority.**  One ``Authorizer`` is constructed (or loaded
through ``load_authorizer``) and its public ``Authorizer.state`` — the SPI 1.2
``AuthorizerState`` — is the only source for every legacy compatibility
projection this shim exposes.  The shim never reads Authorizer private
attributes, never retains caller-supplied contract/composition/lock structures
as a second source of truth, and never re-reads, re-composes, re-authorizes, or
re-verifies policy after the Authorizer has been constructed.  Because of that,
the legacy ``document`` / ``composition`` / ``lock_payload`` / ``network``
surfaces are **non-authoritative read-only projections**: they are derived from
``Authorizer.state`` on each access, they cannot be reassigned, and mutating a
returned projection cannot reach the Authorizer or any later projection.

This shim therefore requires Nornyx **1.11.0** (SPI **1.2**) or newer.  It is
unpackaged: it ships in neither the core wheel nor ``nornyx-agentic-adapters``.

The shim remains cooperative Tier 2: callers can bypass it, identity and
approval claims are not authenticated, and recorded observations are caller
assertions.  New integrations should use ``nornyx-agentic-adapters`` together
with the public ``nornyx.agentic`` SPI.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, TypeVar
import warnings

from nornyx.agentic import (
    ApprovalAssertion,
    ApprovalRequest,
    Authorizer,
    AuthorizerLoadCode,
    AuthorizerLoadError,
    AuthorizerState,
    CapabilityRequest,
    DataShareRequest,
    Decision,
    DecisionCode,
    DelegationRequest,
    EvaluationContext,
    EvidenceRecorder,
    HandoffRequest,
    IdentityResolutionError,
    ZoneCrossingRequest,
    load_authorizer,
)

AGENTIC_APPROVAL_ID = "agentic_network_authority"
_DEPRECATION_TEXT = (
    "integrations.nornyx_reference_adapters.GovernanceKernel is deprecated; "
    "migrate to the supported nornyx-agentic-adapters package and the "
    "nornyx.agentic SPI."
)
_MALFORMED = "AN_ADAPTER_REQUEST_MALFORMED"
_EVIDENCE_INVALID = "AN_ADAPTER_EVIDENCE_INVALID"

T = TypeVar("T")


class GovernanceViolation(RuntimeError):
    """A fail-closed legacy adapter-boundary denial with a stable code."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


class DeterministicClock:
    """Legacy deterministic-clock surface retained for source compatibility.

    Each immutable SPI recorder is bound to one
    ``EvaluationContext.decision_at``. The shim advances this explicit clock
    between decision/observation batches by resuming through the public recorder
    API; no wall clock is read. ``current`` supplies the direct-constructor
    context, while ``from_local_controls`` starts validation at ``as_of``.
    """

    def __init__(self, start: str = "2026-07-17T10:00:00Z", step_seconds: int = 60):
        self._current = datetime.fromisoformat(start.replace("Z", "+00:00"))
        self._step = timedelta(seconds=step_seconds)

    @property
    def current(self) -> str:
        return self._current.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def next(self) -> str:
        value = self._current
        self._current = value + self._step
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _items(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str.__str__(item) for item in value if isinstance(item, str))


def _plain_string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise GovernanceViolation(_MALFORMED, f"{field} must be a string.")
    plain = str.__str__(value)
    if not plain:
        raise GovernanceViolation(_MALFORMED, f"{field} must not be empty.")
    return plain


def _plain_optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _plain_string(value, field)


_LOAD_CODES = {
    AuthorizerLoadCode.CONTRACT_INVALID: "AN_ADAPTER_CONTRACT_INVALID",
    AuthorizerLoadCode.PROFILE_MISSING: "AN_ADAPTER_PROFILE_MISSING",
    AuthorizerLoadCode.LOCK_INVALID: "AN_ADAPTER_LOCK_INVALID",
    AuthorizerLoadCode.LOCK_STALE: "AN_ADAPTER_LOCK_STALE",
}

@dataclass(frozen=True)
class _ApprovalSpec:
    """Immutable legacy view of one composed approval requirement.

    Derived once from ``AuthorizerState.composition``.  It carries only the
    fields the legacy diagnostic defaults need, all as immutable scalars and
    tuples, so it can neither be mutated into drift nor act as a second
    interpretation of approval policy.  Approval *integrity* is decided by the
    Authorizer alone; this only supplies legacy defaults for fields a caller
    omitted.
    """

    id: str
    actions_requiring_approval: tuple[str, ...]
    required_evidence: tuple[str, ...]
    required_roles: tuple[str, ...]
    eligible_roles: tuple[str, ...]


@dataclass(frozen=True)
class _GateSpec:
    """Immutable legacy view of one network gate, for action-ref lookup."""

    id: str
    source_zone_refs: frozenset[str]
    target_zone_refs: frozenset[str]
    required_approval_refs: frozenset[str]
    action_classes: tuple[str, ...]


def _spec_strings(source: Any, key: str) -> tuple[str, ...]:
    if not isinstance(source, Mapping):
        return ()
    return _strings(source.get(key))


_DECISION_CODES = {
    DecisionCode.CAPABILITY_UNKNOWN: "AN_ADAPTER_CAPABILITY_UNKNOWN",
    DecisionCode.CAPABILITY_DENIED: "AN_ADAPTER_CAPABILITY_DENIED",
    DecisionCode.DELEGATION_UNKNOWN: "AN_ADAPTER_DELEGATION_UNKNOWN",
    DecisionCode.DELEGATION_INACTIVE: "AN_ADAPTER_DELEGATION_INACTIVE",
    DecisionCode.HANDOFF_UNKNOWN: "AN_ADAPTER_HANDOFF_UNKNOWN",
    DecisionCode.HANDOFF_AUTHORITY: "AN_ADAPTER_HANDOFF_AUTHORITY",
    DecisionCode.APPROVAL_REQUIRED: "AN_ADAPTER_APPROVAL_NOT_GRANTED",
    DecisionCode.APPROVAL_NON_HUMAN: "AN_ADAPTER_APPROVAL_NON_HUMAN",
    DecisionCode.APPROVAL_ROLE_INVALID: "AN_ADAPTER_APPROVAL_ROLE_INVALID",
    DecisionCode.APPROVAL_NOT_GRANTED: "AN_ADAPTER_APPROVAL_NOT_GRANTED",
    DecisionCode.APPROVAL_STALE: "AN_ADAPTER_APPROVAL_NOT_GRANTED",
    DecisionCode.APPROVAL_REVISION_MISMATCH: "AN_ADAPTER_APPROVAL_NOT_GRANTED",
    DecisionCode.APPROVAL_ACTION_MISMATCH: "AN_ADAPTER_APPROVAL_NOT_GRANTED",
    DecisionCode.APPROVAL_EVIDENCE_MISSING: "AN_ADAPTER_APPROVAL_NOT_GRANTED",
    DecisionCode.ZONE_CROSSING_DENIED: "AN_ADAPTER_ZONE_CROSSING_DENIED",
    DecisionCode.CROSSING_APPROVAL_REQUIRED: "AN_ADAPTER_CROSSING_APPROVAL_REQUIRED",
    DecisionCode.SENSITIVE_SHARING: "AN_ADAPTER_SENSITIVE_SHARING",
    DecisionCode.SHARE_NOT_ALLOWED: "AN_ADAPTER_SHARE_NOT_ALLOWED",
}


class GovernanceKernel:
    """Deprecated legacy surface backed exclusively by public SPI 1.2 state."""

    def __init__(
        self,
        document: Mapping[str, Any],
        composition: Any,
        lock_payload: Mapping[str, Any],
        *,
        framework: str,
        producer_id: str = "nornyx.reference_adapter",
        producer_version: str = "1.0",
        clock: DeterministicClock | None = None,
    ):
        warnings.warn(_DEPRECATION_TEXT, DeprecationWarning, stacklevel=2)
        # The caller keeps ownership of these objects.  ``Authorizer`` deep-freezes
        # them into its own construction state, so nothing here is retained: the
        # only state this shim reads afterwards is ``authorizer.state``.  Direct
        # construction is not validated, composed, or lock-verified — that is a
        # property of the SPI, unchanged by this shim; ``from_local_controls`` is
        # the assured path.
        authorizer = Authorizer(document, composition, lock_payload)
        self._setup(
            authorizer,
            framework=framework,
            producer_id=producer_id,
            producer_version=producer_version,
            clock=clock,
            decision_at=None,
        )

    def _setup(
        self,
        authorizer: Authorizer,
        *,
        framework: str,
        producer_id: str,
        producer_version: str,
        clock: DeterministicClock | None,
        decision_at: str | None,
    ) -> None:
        """Initialize one kernel around exactly one already-built Authorizer."""

        self.framework = _plain_string(framework, "framework")
        self._producer_id = _plain_string(producer_id, "producer_id")
        self._producer_version = _plain_string(producer_version, "producer_version")
        self._clock = clock or DeterministicClock()
        self._bind(
            authorizer,
            decision_at=self._clock.current if decision_at is None else decision_at,
        )

    def _bind(self, authorizer: Authorizer, *, decision_at: str) -> None:
        """Bind one Authorizer and derive every projection from its public state.

        This is the single source of authority.  ``Authorizer.state`` is read
        once here; no caller-supplied structure, no reload, and no second
        composition is retained.
        """

        self._authorizer = authorizer
        self._recorder_authorizer = authorizer
        state: AuthorizerState = authorizer.state
        self._state = state
        self._context = EvaluationContext(
            decision_at=_plain_string(decision_at, "decision_at"),
            observed_subject_revision=authorizer.subject_revision,
        )
        self._recorder = EvidenceRecorder(
            authorizer,
            self._context,
            producer_id=self._producer_id,
            producer_version=self._producer_version,
        )
        self.contract_digest = state.contract_digest
        self.lock_digest = state.network_lock_digest
        self.network_id = authorizer.network_id
        self.subject_revision = authorizer.subject_revision
        self._index_state(state)

    def _index_state(self, state: AuthorizerState) -> None:
        """Build the immutable legacy lookup indexes from public state only.

        Every retained value below is an immutable scalar, tuple, or frozenset,
        so no index can be mutated into disagreement with the Authorizer, and no
        index can outlive or override an Authorizer decision.
        """

        document = state.document
        network = document.get("agentic_network")
        network_map: Mapping[str, Any] = network if isinstance(network, Mapping) else {}

        self._identity_ids = frozenset(
            str.__str__(item["id"])
            for item in _items(document.get("agent_identities"))
            if isinstance(item.get("id"), str)
        )
        self._handoff_endpoints = MappingProxyType(
            {
                str.__str__(item["id"]): (
                    str(item.get("from_identity_ref")),
                    str(item.get("to_identity_ref")),
                )
                for item in _items(network_map.get("handoffs"))
                if isinstance(item.get("id"), str)
            }
        )
        self._gate_specs = tuple(
            _GateSpec(
                id=str(gate.get("id")),
                source_zone_refs=frozenset(_spec_strings(gate, "source_zone_refs")),
                target_zone_refs=frozenset(_spec_strings(gate, "target_zone_refs")),
                required_approval_refs=frozenset(
                    _spec_strings(gate, "required_approval_refs")
                ),
                action_classes=_spec_strings(gate, "action_classes"),
            )
            for gate in _items(network_map.get("network_gates"))
        )
        self._approval_specs = MappingProxyType(
            {
                str(requirement.id): _ApprovalSpec(
                    id=str(requirement.id),
                    actions_requiring_approval=tuple(
                        str(item)
                        for item in (
                            getattr(requirement, "actions_requiring_approval", ()) or ()
                        )
                    ),
                    required_evidence=tuple(
                        str(item)
                        for item in (getattr(requirement, "required_evidence", ()) or ())
                    ),
                    required_roles=tuple(
                        str(item)
                        for item in (getattr(requirement, "required_roles", ()) or ())
                    ),
                    eligible_roles=tuple(
                        str(item)
                        for item in (getattr(requirement, "eligible_roles", ()) or ())
                    ),
                )
                for requirement in state.composition.approval_requirements
            }
        )

    # ------------------------------------------- non-authoritative projections
    @property
    def document(self) -> dict[str, Any]:
        """Non-authoritative projection of the Authorizer's contract document.

        A fresh detached copy on every access.  Mutating it cannot reach the
        Authorizer, this kernel, or any later projection, and it can never
        change an authorization outcome.
        """

        return self._state.document

    @property
    def composition(self) -> Any:
        """Non-authoritative projection of the effective governance composition."""

        return self._state.composition

    @property
    def lock_payload(self) -> dict[str, Any]:
        """Non-authoritative projection of the verified agentic-network lock."""

        return self._state.lock_payload

    @property
    def network(self) -> Mapping[str, Any]:
        """Non-authoritative projection of the contract's ``agentic_network``."""

        network = self._state.document.get("agentic_network")
        return network if isinstance(network, Mapping) else {}

    @classmethod
    def from_local_controls(
        cls,
        contract_path: str | Path,
        lock_path: str | Path,
        *,
        framework: str,
        as_of: str,
        clock: DeterministicClock | None = None,
    ) -> "GovernanceKernel":
        """Load through ``load_authorizer`` and preserve legacy load codes.

        ``load_authorizer`` is the only read.  Its Authorizer is validated,
        composed, and lock-verified, and its ``state`` is the sole source of the
        legacy compatibility projections — the shim performs no second read,
        composition, verification, or authorization of its own.
        """

        try:
            authorizer = load_authorizer(
                contract_path,
                lock_path,
                validation_as_of=as_of,
            )
        except AuthorizerLoadError as exc:
            raise GovernanceViolation(
                _LOAD_CODES[exc.code],
                str(exc).partition(": ")[2] or str(exc),
            ) from exc

        # Bypass __init__: constructing through it would build a second
        # Authorizer from re-read inputs, which is exactly the split-brain this
        # shim must not have.  One load, one Authorizer, one state.
        kernel = cls.__new__(cls)
        kernel._setup(
            authorizer,
            framework=framework,
            producer_id="nornyx.reference_adapter",
            producer_version="1.0",
            clock=clock,
            decision_at=as_of,
        )
        warnings.warn(_DEPRECATION_TEXT, DeprecationWarning, stacklevel=2)
        return kernel

    # -------------------------------------------------------------- evidence
    def events_payload(self) -> dict[str, Any]:
        return self._recorder.stream()

    def write_events(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.events_payload(), sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return target

    def _record_decision(self, decision: Decision, mission_id: str) -> None:
        try:
            self._recorder.record_decision(decision, mission_id=mission_id)
        except (TypeError, ValueError) as exc:
            raise GovernanceViolation(
                _EVIDENCE_INVALID,
                "The SPI recorder refused decision evidence before execution.",
            ) from exc

    def _record_observation(
        self, event_type: str, mission_id: str, **fields: Any
    ) -> dict[str, Any]:
        self._advance_recorder()
        try:
            self._recorder.record_observation(
                event_type,
                mission_id=mission_id,
                **fields,
            )
        except (TypeError, ValueError) as exc:
            raise GovernanceViolation(
                _EVIDENCE_INVALID,
                "The SPI recorder refused post-execution evidence.",
            ) from exc
        return self.events_payload()["events"][-1]

    def _advance_recorder(self) -> None:
        """Advance deterministic legacy time through validated SPI resumption."""

        decision_at = self._clock.next()
        if decision_at == self._context.decision_at:
            return
        context = EvaluationContext(decision_at, self.subject_revision)
        try:
            recorder = EvidenceRecorder.resume(
                self._recorder_authorizer,
                context,
                self._recorder.stream(),
                producer_id=self._producer_id,
                producer_version=self._producer_version,
            )
        except (TypeError, ValueError) as exc:
            raise GovernanceViolation(
                _EVIDENCE_INVALID,
                "The SPI recorder refused deterministic legacy continuation.",
            ) from exc
        self._context = context
        self._recorder = recorder

    def _authorize(
        self,
        request: Any,
        *,
        mission_id: str,
        fallback_code: str,
    ) -> Decision:
        mission = _plain_string(mission_id, "mission_id")
        self._advance_recorder()
        decision = self._authorizer.evaluate(request, context=self._context)
        self._record_decision(decision, mission)
        if not decision.allowed:
            code = _DECISION_CODES.get(decision.code, fallback_code)
            raise GovernanceViolation(code, decision.reason or "Authorization denied.")
        return decision

    # -------------------------------------------------------------- identity
    def resolve_identity(self, agent_key: str) -> str:
        key = _plain_string(agent_key, "agent_key")
        try:
            return self._authorizer.resolve_identity(self.framework, key)
        except IdentityResolutionError as exc:
            raise GovernanceViolation(
                "AN_ADAPTER_IDENTITY_UNKNOWN",
                f"Framework key {key!r} does not map to exactly one "
                f"declared {self.framework} identity.",
            ) from exc

    def _identity(self, identity_id: str) -> str:
        identity = _plain_string(identity_id, "identity_id")
        if identity not in self._identity_ids:
            raise GovernanceViolation(
                "AN_ADAPTER_IDENTITY_UNKNOWN",
                f"Identity {identity!r} is not declared in the contract.",
            )
        return identity

    # ------------------------------------------------------------ capability
    def check_capability(
        self, identity_id: str, capability: str, *, mission_id: str
    ) -> dict[str, Any]:
        identity = self._identity(identity_id)
        capability_ref = _plain_string(capability, "capability")
        self._authorize(
            CapabilityRequest(identity, capability_ref),
            mission_id=mission_id,
            fallback_code="AN_ADAPTER_CAPABILITY_DENIED",
        )
        return self.events_payload()["events"][-1]

    def _execute_tool_callable(
        self,
        identity_id: str,
        capability: str,
        work: Callable[[], T],
        *,
        mission_id: str,
    ) -> T:
        """Authorize once, execute once, then record success or runtime failure."""

        identity = self._identity(identity_id)
        capability_ref = _plain_string(capability, "capability")
        mission = _plain_string(mission_id, "mission_id")
        if not callable(work):
            raise GovernanceViolation(_MALFORMED, "Protected work must be callable.")
        decision = self._authorize(
            CapabilityRequest(identity, capability_ref),
            mission_id=mission,
            fallback_code="AN_ADAPTER_CAPABILITY_DENIED",
        )
        delegation_ref = next(
            (item.ref for item in decision.basis if item.kind == "delegation"),
            None,
        )
        try:
            result = work()
        except Exception:
            self._record_observation(
                "runtime_failed",
                mission,
                actor_ref=identity,
                capability_ref=capability_ref,
                delegation_ref=delegation_ref,
            )
            raise
        self._record_observation(
            "tool_invoked",
            mission,
            actor_ref=identity,
            capability_ref=capability_ref,
            delegation_ref=delegation_ref,
        )
        return result

    def invoke_tool(
        self, identity_id: str, capability: str, *, mission_id: str
    ) -> dict[str, Any]:
        # The historical method has no callable parameter.  Treat entry into
        # this method as its complete protected occurrence; framework wrappers
        # use _execute_tool_callable so their real callable is observed only
        # after it actually returns.
        self._execute_tool_callable(
            identity_id,
            capability,
            lambda: None,
            mission_id=mission_id,
        )
        return self.events_payload()["events"][-1]

    # ------------------------------------------------------------ delegation
    def request_delegation(self, delegation_id: str, *, mission_id: str) -> None:
        ref = _plain_string(delegation_id, "delegation_id")
        self._authorize(
            DelegationRequest(ref),
            mission_id=mission_id,
            fallback_code="AN_ADAPTER_DELEGATION_INACTIVE",
        )

    # --------------------------------------------------------------- handoff
    def request_handoff(self, handoff_id: str, *, mission_id: str) -> None:
        ref = _plain_string(handoff_id, "handoff_id")
        self._authorize(
            HandoffRequest(ref),
            mission_id=mission_id,
            fallback_code="AN_ADAPTER_HANDOFF_AUTHORITY",
        )
        endpoints = self._handoff_endpoints.get(ref)
        if endpoints is None:  # defensive: an ALLOW cannot reach this branch
            raise GovernanceViolation(
                "AN_ADAPTER_HANDOFF_UNKNOWN",
                f"Handoff {ref!r} is not declared in the contract.",
            )
        source_ref, target_ref = endpoints
        self._record_observation(
            "handoff_initiated",
            _plain_string(mission_id, "mission_id"),
            actor_ref=source_ref,
            target_ref=target_ref,
            handoff_ref=ref,
        )

    def complete_handoff(self, handoff_id: str, *, mission_id: str) -> None:
        ref = _plain_string(handoff_id, "handoff_id")
        mission = _plain_string(mission_id, "mission_id")
        endpoints = self._handoff_endpoints.get(ref)
        if endpoints is None:
            raise GovernanceViolation(
                "AN_ADAPTER_HANDOFF_UNKNOWN",
                f"Handoff {ref!r} is not declared in the contract.",
            )
        source_ref, target_ref = endpoints
        # Completion is the second observation in the already-authorized
        # request_handoff lifecycle; re-evaluating here would duplicate the
        # authorization and could not authorize a second surface.
        self._record_observation(
            "handoff_completed",
            mission,
            actor_ref=source_ref,
            target_ref=target_ref,
            handoff_ref=ref,
        )

    # -------------------------------------------------------------- approval
    def _approval_requirement(self, approval_ref: str) -> _ApprovalSpec | None:
        return self._approval_specs.get(approval_ref)

    @staticmethod
    def _approval_mapping(approval_record: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(approval_record, Mapping):
            raise GovernanceViolation(_MALFORMED, "approval_record must be a mapping.")
        try:
            if isinstance(approval_record, dict):
                pairs = dict.items(approval_record)
            else:
                pairs = approval_record.items()
            snapshot: dict[str, Any] = {}
            for key, value in pairs:
                if not isinstance(key, str):
                    raise GovernanceViolation(
                        _MALFORMED,
                        "approval_record keys must be strings.",
                    )
                snapshot[str.__str__(key)] = value
            return snapshot
        except GovernanceViolation:
            raise
        except Exception as exc:  # noqa: BLE001 - hostile Mapping callback boundary
            raise GovernanceViolation(
                _MALFORMED,
                "approval_record could not be normalized safely.",
            ) from exc

    def _approval_assertion(
        self,
        approval_record: Mapping[str, Any],
        *,
        approval_ref: str,
        action_ref: str | None = None,
    ) -> ApprovalAssertion:
        record = self._approval_mapping(approval_record)
        requirement = self._approval_requirement(approval_ref)

        role_value = record.get("role")
        role = str.__str__(role_value) if isinstance(role_value, str) else ""
        actor_type_value = record.get("actor_type")
        actor_type = (
            str.__str__(actor_type_value)
            if isinstance(actor_type_value, str)
            else "legacy_invalid"
        )
        claimed_ref = record.get("claimed_approver_ref", record.get("approver_ref"))
        if claimed_ref is None:
            claimed_ref = f"legacy.approver.{role or 'unknown'}"
        claimed_ref = _plain_string(claimed_ref, "claimed_approver_ref")

        if action_ref is None:
            supplied_action = record.get("action_ref")
            if supplied_action is not None:
                action_ref = _plain_string(supplied_action, "action_ref")
            else:
                actions = tuple(
                    getattr(requirement, "actions_requiring_approval", ()) or ()
                )
                action_ref = str(actions[0]) if actions else "legacy.unsupported"

        supplied_revision = record.get("subject_revision")
        subject_revision = (
            _plain_string(supplied_revision, "subject_revision")
            if supplied_revision is not None
            else self.subject_revision
        )
        issued_at = _plain_optional_string(record.get("issued_at"), "issued_at")
        if issued_at is None:
            issued_at = self._context.decision_at
        expires_at = _plain_optional_string(record.get("expires_at"), "expires_at")

        supplied_evidence = record.get("evidence_refs")
        if supplied_evidence is None:
            evidence_refs = tuple(
                str(item)
                for item in (getattr(requirement, "required_evidence", ()) or ())
            )
        elif isinstance(supplied_evidence, (list, tuple)) and all(
            isinstance(item, str) for item in supplied_evidence
        ):
            evidence_refs = tuple(str.__str__(item) for item in supplied_evidence)
        else:
            raise GovernanceViolation(
                _MALFORMED,
                "approval_record.evidence_refs must be a list or tuple of strings.",
            )

        return ApprovalAssertion(
            approval_ref=approval_ref,
            claimed_approver_ref=claimed_ref,
            claimed_actor_type=actor_type,
            role=role,
            granted=record.get("granted") is True,
            action_ref=action_ref,
            subject_revision=subject_revision,
            issued_at=issued_at,
            expires_at=expires_at,
            evidence_refs=evidence_refs,
        )

    def require_human_approval(
        self,
        approval_record: Mapping[str, Any],
        *,
        mission_id: str,
        actor_ref: str,
        approval_ref: str = AGENTIC_APPROVAL_ID,
    ) -> None:
        actor = self._identity(actor_ref)
        ref = _plain_string(approval_ref, "approval_ref")
        assertion = self._approval_assertion(approval_record, approval_ref=ref)
        self._authorize(
            ApprovalRequest(actor, assertion),
            mission_id=mission_id,
            fallback_code="AN_ADAPTER_APPROVAL_NOT_GRANTED",
        )

    # ------------------------------------------------------------ zone/data
    def _zone_action_ref(
        self, source_zone: str, target_zone: str, approval_ref: str
    ) -> str | None:
        for gate in sorted(self._gate_specs, key=lambda spec: spec.id):
            if (
                source_zone in gate.source_zone_refs
                and target_zone in gate.target_zone_refs
                and approval_ref in gate.required_approval_refs
                and gate.action_classes
            ):
                return gate.action_classes[0]
        return None

    def record_zone_crossing(
        self,
        identity_id: str,
        source_zone: str,
        target_zone: str,
        *,
        mission_id: str,
        approval_ref: str | None = None,
    ) -> None:
        identity = self._identity(identity_id)
        source = _plain_string(source_zone, "source_zone")
        target = _plain_string(target_zone, "target_zone")
        mission = _plain_string(mission_id, "mission_id")
        assertion = None
        if approval_ref is not None:
            ref = _plain_string(approval_ref, "approval_ref")
            requirement = self._approval_requirement(ref)
            roles = tuple(getattr(requirement, "required_roles", ()) or ())
            if not roles:
                roles = tuple(getattr(requirement, "eligible_roles", ()) or ())
            role = str(roles[0]) if roles else ""
            assertion = self._approval_assertion(
                {"role": role, "actor_type": "human", "granted": True},
                approval_ref=ref,
                action_ref=self._zone_action_ref(source, target, ref),
            )
        self._authorize(
            ZoneCrossingRequest(identity, source, target, assertion),
            mission_id=mission,
            fallback_code="AN_ADAPTER_ZONE_CROSSING_DENIED",
        )
        self._record_observation(
            "trust_zone_crossed",
            mission,
            actor_ref=identity,
            source_zone_ref=source,
            target_zone_ref=target,
            approval_ref=approval_ref,
        )

    def record_data_shared(
        self,
        identity_id: str,
        target_id: str,
        categories: list[str],
        *,
        mission_id: str,
        source_zone: str,
        target_zone: str,
    ) -> None:
        identity = self._identity(identity_id)
        target = self._identity(target_id)
        mission = _plain_string(mission_id, "mission_id")
        source = _plain_string(source_zone, "source_zone")
        target_zone_ref = _plain_string(target_zone, "target_zone")
        if not isinstance(categories, list) or not all(
            isinstance(item, str) for item in categories
        ):
            raise GovernanceViolation(
                _MALFORMED,
                "categories must be a list of strings.",
            )
        normalized = tuple(str.__str__(item) for item in categories)
        self._authorize(
            DataShareRequest(identity, target, normalized, source, target_zone_ref),
            mission_id=mission,
            fallback_code="AN_ADAPTER_SHARE_NOT_ALLOWED",
        )
        self._record_observation(
            "data_shared",
            mission,
            actor_ref=identity,
            target_ref=target,
            share_categories=sorted(normalized),
            source_zone_ref=source,
            target_zone_ref=target_zone_ref,
        )
