"""Deprecated compatibility facade over the supported Nornyx agentic SPI.

``GovernanceKernel`` preserves the unpackaged ADR-0037 reference API while
delegating every authorization decision to ``nornyx.agentic.Authorizer`` and
all runtime-event construction to ``nornyx.agentic.EvidenceRecorder``.  It is
not an independent policy or evidence engine.

The shim remains cooperative Tier 2: callers can bypass it, identity and
approval claims are not authenticated, and recorded observations are caller
assertions.  New integrations should use ``nornyx-agentic-adapters`` together
with the public ``nornyx.agentic`` SPI.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, TypeVar
import warnings

from nornyx.agentic import (
    ApprovalAssertion,
    ApprovalRequest,
    Authorizer,
    AuthorizerLoadCode,
    AuthorizerLoadError,
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
    agentic_network_lock_digest,
    compose_document_governance,
    contract_digest,
    load_agentic_network_lock,
    load_authorizer,
    load_nyx,
    registry_for_contract,
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
    """Deprecated legacy surface backed exclusively by SPI 1.1 primitives."""

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
        self.document = document
        self.composition = composition
        self.lock_payload = lock_payload
        self.framework = _plain_string(framework, "framework")
        self._producer_id = _plain_string(producer_id, "producer_id")
        self._producer_version = _plain_string(producer_version, "producer_version")
        self._clock = clock or DeterministicClock()

        network = document.get("agentic_network")
        self.network: Mapping[str, Any] = network if isinstance(network, Mapping) else {}
        self._identities = {
            str.__str__(item["id"]): item
            for item in _items(document.get("agent_identities"))
            if isinstance(item.get("id"), str)
        }
        self._handoffs = {
            str.__str__(item["id"]): item
            for item in _items(self.network.get("handoffs"))
            if isinstance(item.get("id"), str)
        }
        self._gates = _items(self.network.get("network_gates"))

        authorizer = Authorizer(document, composition, lock_payload)
        self._bind(authorizer, decision_at=self._clock.current)

    def _bind(self, authorizer: Authorizer, *, decision_at: str) -> None:
        """Bind the authoritative SPI objects; never retain a second policy engine."""

        self._authorizer = authorizer
        self._recorder_authorizer = authorizer
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
        self.contract_digest = authorizer.contract_digest
        self.lock_digest = authorizer.network_lock_digest
        self.network_id = authorizer.network_id
        self.subject_revision = authorizer.subject_revision

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
        """Load through ``load_authorizer`` and preserve legacy load codes."""

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

        # The legacy object exposed these snapshots publicly.  Reload them only
        # after the SPI load succeeds, then compare public digests so a file
        # changed between reads fails closed rather than binding mixed state.
        try:
            document = load_nyx(contract_path)
            composition = compose_document_governance(
                document,
                registry=registry_for_contract(contract_path),
            )
            lock_payload = load_agentic_network_lock(lock_path)
        except Exception as exc:  # noqa: BLE001 - legacy deterministic boundary
            raise GovernanceViolation(
                "AN_ADAPTER_CONTRACT_INVALID",
                "The public compatibility snapshots could not be loaded.",
            ) from exc
        if composition is None:
            raise GovernanceViolation(
                "AN_ADAPTER_PROFILE_MISSING",
                "The contract does not resolve a governance profile.",
            )
        if (
            contract_digest(document) != authorizer.contract_digest
            or agentic_network_lock_digest(lock_payload)
            != authorizer.network_lock_digest
        ):
            raise GovernanceViolation(
                "AN_ADAPTER_LOCK_STALE",
                "The contract or lock changed while the compatibility shim was loading.",
            )

        # Construction is the one warning point.  Suppress the constructor's
        # internal frame here and re-emit at the external classmethod caller so
        # one normal load path produces one actionable warning, not two.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            kernel = cls(
                document,
                composition,
                lock_payload,
                framework=framework,
                clock=clock,
            )
        kernel._bind(authorizer, decision_at=as_of)
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
        if identity not in self._identities:
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
        handoff = self._handoffs.get(ref)
        if handoff is None:  # defensive: an ALLOW cannot reach this branch
            raise GovernanceViolation(
                "AN_ADAPTER_HANDOFF_UNKNOWN",
                f"Handoff {ref!r} is not declared in the contract.",
            )
        self._record_observation(
            "handoff_initiated",
            _plain_string(mission_id, "mission_id"),
            actor_ref=str(handoff.get("from_identity_ref")),
            target_ref=str(handoff.get("to_identity_ref")),
            handoff_ref=ref,
        )

    def complete_handoff(self, handoff_id: str, *, mission_id: str) -> None:
        ref = _plain_string(handoff_id, "handoff_id")
        mission = _plain_string(mission_id, "mission_id")
        handoff = self._handoffs.get(ref)
        if handoff is None:
            raise GovernanceViolation(
                "AN_ADAPTER_HANDOFF_UNKNOWN",
                f"Handoff {ref!r} is not declared in the contract.",
            )
        # Completion is the second observation in the already-authorized
        # request_handoff lifecycle; re-evaluating here would duplicate the
        # authorization and could not authorize a second surface.
        self._record_observation(
            "handoff_completed",
            mission,
            actor_ref=str(handoff.get("from_identity_ref")),
            target_ref=str(handoff.get("to_identity_ref")),
            handoff_ref=ref,
        )

    # -------------------------------------------------------------- approval
    def _approval_requirement(self, approval_ref: str) -> Any | None:
        for requirement in self.composition.approval_requirements:
            if requirement.id == approval_ref:
                return requirement
        return None

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
        candidates = sorted(self._gates, key=lambda item: str(item.get("id")))
        for gate in candidates:
            if (
                source_zone in _strings(gate.get("source_zone_refs"))
                and target_zone in _strings(gate.get("target_zone_refs"))
                and approval_ref in _strings(gate.get("required_approval_refs"))
            ):
                actions = _strings(gate.get("action_classes"))
                if actions:
                    return actions[0]
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
