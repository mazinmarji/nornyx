"""Framework-free enforcement kernel shared by every reference adapter.

Layer 2 of the ADR-0037 layering: it loads only local generated/resolved
Nornyx controls, verifies the agentic-network lock before use, maps runtime
identities to declared identities, checks capability ownership, validates
delegation and handoff requests, enforces trust-zone declarations at the
adapter boundary, requires externally supplied human approval, rejects
AI-produced approval, and emits standardized `nornyx.agentic_runtime_events.v1`
events bound to the exact contract digest and network lock digest.

The kernel never authenticates agents, discovers services, stores secrets,
contacts production systems, grants approvals, or modifies governance policy.
Enforcement is cooperative: callers that bypass the adapter bypass the hook,
and the final authority is Nornyx validation of the emitted evidence.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from nornyx.agentic_artifacts import (
    RUNTIME_EVENTS_SCHEMA_ID,
    RUNTIME_EVENTS_SCHEMA_VERSION,
    agentic_network_lock_digest,
    contract_digest,
    load_agentic_network_lock,
    verify_agentic_network_lock,
)
from nornyx.checker import check_document, has_errors
from nornyx.governance import (
    GovernanceError,
    compose_document_governance,
    evaluate_document_governance,
    registry_for_contract,
)
from nornyx.parser import load_nyx

SENSITIVE_CATEGORIES = frozenset({"secrets", "credentials", "tokens", "private_memory"})
AGENTIC_APPROVAL_ID = "agentic_network_authority"


class GovernanceViolation(RuntimeError):
    """A fail-closed adapter-boundary denial with a stable code."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


class DeterministicClock:
    """Deterministic event timestamps for reproducible demonstrations."""

    def __init__(self, start: str = "2026-07-17T10:00:00Z", step_seconds: int = 60):
        self._current = datetime.fromisoformat(start.replace("Z", "+00:00"))
        self._step = timedelta(seconds=step_seconds)

    def next(self) -> str:
        value = self._current
        self._current = value + self._step
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _items(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


class GovernanceKernel:
    """One loaded, lock-verified contract plus an evidence emitter."""

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
        self.document = document
        self.composition = composition
        self.lock_payload = lock_payload
        self.framework = framework
        self.contract_digest = contract_digest(document)
        self.lock_digest = agentic_network_lock_digest(lock_payload)
        network = document.get("agentic_network")
        self.network: Mapping[str, Any] = (
            network if isinstance(network, Mapping) else {}
        )
        self.network_id = str(self.network.get("id"))
        self.subject_revision = str(self.network.get("subject_revision"))
        self._producer = {
            "type": "framework_adapter",
            "id": producer_id,
            "version": producer_version,
        }
        self._clock = clock or DeterministicClock()
        self._events: list[dict[str, Any]] = []
        self._sequences: dict[str, int] = {}

        self._identities = {
            str(item["id"]): item
            for item in _items(document.get("agent_identities"))
            if isinstance(item.get("id"), str)
        }
        self._capabilities = {
            str(item["name"]): item
            for item in _items(document.get("capabilities"))
            if isinstance(item.get("name"), str)
        }
        self._memberships = _items(self.network.get("memberships"))
        self._zones = {
            str(item["id"]): item
            for item in _items(self.network.get("trust_zones"))
            if isinstance(item.get("id"), str)
        }
        self._delegations = {
            str(item["id"]): item
            for item in _items(self.network.get("delegations"))
            if isinstance(item.get("id"), str)
        }
        self._handoffs = {
            str(item["id"]): item
            for item in _items(self.network.get("handoffs"))
            if isinstance(item.get("id"), str)
        }
        self._module_roles: set[str] = set()
        for requirement in composition.approval_requirements:
            if requirement.id != AGENTIC_APPROVAL_ID:
                continue
            self._module_roles.update(requirement.required_roles)
            self._module_roles.update(requirement.eligible_roles)
            if requirement.accountable_authority is not None:
                self._module_roles.add(requirement.accountable_authority)

    # ------------------------------------------------------------------ load
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
        """Load, fully validate, and lock-verify one local contract.

        Fails closed on any contract diagnostic, missing composition, stale
        lock, or lock/contract mismatch.
        """

        registry = registry_for_contract(contract_path)
        document = load_nyx(contract_path)
        document_root = Path(contract_path).resolve().parent
        diagnostics = list(check_document(document))
        composition = compose_document_governance(document, registry=registry)
        if composition is None:
            raise GovernanceViolation(
                "AN_ADAPTER_PROFILE_MISSING",
                "The contract does not resolve a governance profile.",
            )
        contributed = {item.block for item in composition.block_schemas}
        diagnostics = [
            item
            for item in diagnostics
            if not (
                item.code == "UNKNOWN_TOP_LEVEL_BLOCK" and item.path in contributed
            )
        ]
        diagnostics.extend(
            evaluate_document_governance(
                document,
                registry=registry,
                as_of=as_of,
                document_root=document_root,
            )
        )
        if has_errors(diagnostics):
            codes = sorted(
                {item.code for item in diagnostics if item.level == "error"}
            )
            raise GovernanceViolation(
                "AN_ADAPTER_CONTRACT_INVALID",
                "The contract fails governance validation: " + ", ".join(codes),
            )
        try:
            lock_payload = load_agentic_network_lock(lock_path)
        except GovernanceError as exc:
            raise GovernanceViolation(
                "AN_ADAPTER_LOCK_INVALID",
                f"Cannot load the agentic-network lock: {exc}",
            ) from exc
        stale = verify_agentic_network_lock(lock_payload, document, composition)
        if stale:
            raise GovernanceViolation(
                "AN_ADAPTER_LOCK_STALE",
                "Stale or mismatched agentic-network lock: "
                + ", ".join(sorted({item.code for item in stale})),
            )
        return cls(
            document,
            composition,
            lock_payload,
            framework=framework,
            clock=clock,
        )

    # -------------------------------------------------------------- evidence
    def _emit(self, event_type: str, mission_id: str, **fields: Any) -> dict[str, Any]:
        sequence = self._sequences.get(mission_id, 0) + 1
        self._sequences[mission_id] = sequence
        event = {
            "event_id": f"{mission_id}-{sequence:04d}",
            "event_type": event_type,
            "mission_id": mission_id,
            "sequence": sequence,
            "timestamp": self._clock.next(),
            "network_id": self.network_id,
            "contract_digest": self.contract_digest,
            "network_lock_digest": self.lock_digest,
            "subject_revision": self.subject_revision,
            "producer": dict(self._producer),
        }
        event.update({key: value for key, value in fields.items() if value is not None})
        self._events.append(event)
        return event

    def events_payload(self) -> dict[str, Any]:
        return {
            "schema": RUNTIME_EVENTS_SCHEMA_ID,
            "schema_version": RUNTIME_EVENTS_SCHEMA_VERSION,
            "network_id": self.network_id,
            "producer": dict(self._producer),
            "events": [dict(event) for event in self._events],
        }

    def write_events(self, path: str | Path) -> Path:
        import json

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.events_payload(), sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return target

    # -------------------------------------------------------------- identity
    def resolve_identity(self, agent_key: str) -> str:
        """Map one framework agent key to the declared Nornyx identity."""

        matches = [
            identity_id
            for identity_id, identity in sorted(self._identities.items())
            if any(
                binding.get("framework") == self.framework
                and binding.get("agent_key") == agent_key
                for binding in _items(identity.get("framework_bindings"))
            )
        ]
        if len(matches) != 1:
            raise GovernanceViolation(
                "AN_ADAPTER_IDENTITY_UNKNOWN",
                f"Framework key {agent_key!r} does not map to exactly one "
                f"declared {self.framework} identity.",
            )
        return matches[0]

    def _identity_holds(self, identity_id: str, capability: str) -> bool:
        identity = self._identities.get(identity_id)
        if identity is None or capability not in _strings(
            identity.get("capability_refs")
        ):
            return False
        return any(
            membership.get("identity_ref") == identity_id
            and membership.get("status") == "authorized"
            and capability in _strings(membership.get("capability_refs"))
            for membership in self._memberships
        )

    def _delegated(self, identity_id: str, capability: str) -> str | None:
        for delegation_id, delegation in sorted(self._delegations.items()):
            if (
                delegation.get("delegate_ref") == identity_id
                and delegation.get("capability_ref") == capability
                and delegation.get("status") == "active"
            ):
                return delegation_id
        return None

    # ------------------------------------------------------------ capability
    def check_capability(
        self, identity_id: str, capability: str, *, mission_id: str
    ) -> dict[str, Any]:
        """Emit request + allow/deny evidence; raise on denial."""

        if identity_id not in self._identities:
            raise GovernanceViolation(
                "AN_ADAPTER_IDENTITY_UNKNOWN",
                f"Identity {identity_id!r} is not declared in the contract.",
            )
        if capability not in self._capabilities:
            # The undeclared name never enters typed evidence; the attempt is
            # recorded as a policy violation.
            self._emit(
                "policy_violation",
                mission_id,
                actor_ref=identity_id,
            )
            raise GovernanceViolation(
                "AN_ADAPTER_CAPABILITY_UNKNOWN",
                f"Capability {capability!r} is not declared in the contract.",
            )
        self._emit(
            "capability_requested",
            mission_id,
            actor_ref=identity_id,
            capability_ref=capability,
        )
        delegation_ref = None
        if not self._identity_holds(identity_id, capability):
            delegation_ref = self._delegated(identity_id, capability)
            if delegation_ref is None:
                self._emit(
                    "capability_denied",
                    mission_id,
                    actor_ref=identity_id,
                    capability_ref=capability,
                    policy_decision="deny",
                )
                raise GovernanceViolation(
                    "AN_ADAPTER_CAPABILITY_DENIED",
                    f"Identity {identity_id!r} neither holds nor validly "
                    f"receives capability {capability!r}.",
                )
        event = self._emit(
            "capability_allowed",
            mission_id,
            actor_ref=identity_id,
            capability_ref=capability,
            delegation_ref=delegation_ref,
            policy_decision="allow",
        )
        return event

    def invoke_tool(
        self, identity_id: str, capability: str, *, mission_id: str
    ) -> dict[str, Any]:
        allowance = self.check_capability(
            identity_id, capability, mission_id=mission_id
        )
        return self._emit(
            "tool_invoked",
            mission_id,
            actor_ref=identity_id,
            capability_ref=capability,
            delegation_ref=allowance.get("delegation_ref"),
        )

    # ------------------------------------------------------------ delegation
    def request_delegation(self, delegation_id: str, *, mission_id: str) -> None:
        delegation = self._delegations.get(delegation_id)
        if delegation is None:
            raise GovernanceViolation(
                "AN_ADAPTER_DELEGATION_UNKNOWN",
                f"Delegation {delegation_id!r} is not declared in the contract.",
            )
        delegator = str(delegation.get("delegator_ref"))
        delegate = str(delegation.get("delegate_ref"))
        self._emit(
            "delegation_requested",
            mission_id,
            actor_ref=delegator,
            target_ref=delegate,
            delegation_ref=delegation_id,
        )
        if delegation.get("status") != "active":
            self._emit(
                "delegation_rejected",
                mission_id,
                actor_ref=delegate,
                delegation_ref=delegation_id,
            )
            raise GovernanceViolation(
                "AN_ADAPTER_DELEGATION_INACTIVE",
                f"Delegation {delegation_id!r} is not active.",
            )
        self._emit(
            "delegation_accepted",
            mission_id,
            actor_ref=delegate,
            delegation_ref=delegation_id,
        )

    # --------------------------------------------------------------- handoff
    def request_handoff(self, handoff_id: str, *, mission_id: str) -> None:
        handoff = self._handoffs.get(handoff_id)
        if handoff is None:
            raise GovernanceViolation(
                "AN_ADAPTER_HANDOFF_UNKNOWN",
                f"Handoff {handoff_id!r} is not declared in the contract.",
            )
        source = str(handoff.get("from_identity_ref"))
        target = str(handoff.get("to_identity_ref"))
        for capability in _strings(handoff.get("required_capability_refs")):
            held = self._identity_holds(target, capability)
            delegated = self._delegated(target, capability)
            if not held and delegated is None:
                self._emit(
                    "policy_violation",
                    mission_id,
                    actor_ref=source,
                    target_ref=target,
                    handoff_ref=handoff_id,
                )
                raise GovernanceViolation(
                    "AN_ADAPTER_HANDOFF_AUTHORITY",
                    "A handoff transfers responsibility, never authority: the "
                    f"target does not hold capability {capability!r}.",
                )
        self._emit(
            "handoff_initiated",
            mission_id,
            actor_ref=source,
            target_ref=target,
            handoff_ref=handoff_id,
        )

    def complete_handoff(self, handoff_id: str, *, mission_id: str) -> None:
        handoff = self._handoffs.get(handoff_id)
        if handoff is None:
            raise GovernanceViolation(
                "AN_ADAPTER_HANDOFF_UNKNOWN",
                f"Handoff {handoff_id!r} is not declared in the contract.",
            )
        self._emit(
            "handoff_completed",
            mission_id,
            actor_ref=str(handoff.get("from_identity_ref")),
            target_ref=str(handoff.get("to_identity_ref")),
            handoff_ref=handoff_id,
        )

    # -------------------------------------------------------------- approval
    def require_human_approval(
        self,
        approval_record: Mapping[str, Any],
        *,
        mission_id: str,
        actor_ref: str,
        approval_ref: str = AGENTIC_APPROVAL_ID,
    ) -> None:
        """Verify one externally supplied human approval record.

        The adapter never grants approval; it validates the supplied record's
        shape, actor type, and role, and records the outcome as evidence.
        """

        self._emit(
            "approval_requested",
            mission_id,
            actor_ref=actor_ref,
            approval_ref=approval_ref,
        )
        actor_type = approval_record.get("actor_type")
        role = approval_record.get("role")
        granted = approval_record.get("granted") is True
        if actor_type != "human":
            # An AI approval attempt is a policy violation, never an approval
            # outcome; no fabricated approver enters the evidence stream.
            self._emit(
                "policy_violation",
                mission_id,
                actor_ref=actor_ref,
                approval_ref=approval_ref,
            )
            raise GovernanceViolation(
                "AN_ADAPTER_APPROVAL_NON_HUMAN",
                "AI systems, tools, models, and execution surfaces cannot "
                "approve; a human approval record is required.",
            )
        if not isinstance(role, str) or role not in self._module_roles:
            self._emit(
                "policy_violation",
                mission_id,
                actor_ref=actor_ref,
                approval_ref=approval_ref,
            )
            raise GovernanceViolation(
                "AN_ADAPTER_APPROVAL_ROLE_INVALID",
                f"Role {role!r} is outside the composed module authority.",
            )
        approver = {"role": role, "actor_type": "human"}
        if not granted:
            self._emit(
                "approval_rejected",
                mission_id,
                actor_ref=actor_ref,
                approval_ref=approval_ref,
                approver=approver,
            )
            raise GovernanceViolation(
                "AN_ADAPTER_APPROVAL_NOT_GRANTED",
                "The supplied human approval record does not grant approval.",
            )
        self._emit(
            "approval_granted",
            mission_id,
            actor_ref=actor_ref,
            approval_ref=approval_ref,
            approver=approver,
        )

    # ------------------------------------------------------------ zone/data
    def record_zone_crossing(
        self,
        identity_id: str,
        source_zone: str,
        target_zone: str,
        *,
        mission_id: str,
        approval_ref: str | None = None,
    ) -> None:
        zone = self._zones.get(source_zone)
        if zone is None or target_zone not in _strings(
            zone.get("allowed_transition_targets")
        ):
            self._emit(
                "policy_violation",
                mission_id,
                actor_ref=identity_id,
                source_zone_ref=source_zone if source_zone in self._zones else None,
                target_zone_ref=target_zone if target_zone in self._zones else None,
            )
            raise GovernanceViolation(
                "AN_ADAPTER_ZONE_CROSSING_DENIED",
                f"Crossing {source_zone!r} -> {target_zone!r} is not a "
                "declared allowed transition.",
            )
        self._emit(
            "trust_zone_crossed",
            mission_id,
            actor_ref=identity_id,
            source_zone_ref=source_zone,
            target_zone_ref=target_zone,
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
        sensitive = SENSITIVE_CATEGORIES & set(categories)
        if sensitive:
            self._emit(
                "policy_violation",
                mission_id,
                actor_ref=identity_id,
                target_ref=target_id,
            )
            raise GovernanceViolation(
                "AN_ADAPTER_SENSITIVE_SHARING",
                "Sensitive categories are never shareable: "
                + ", ".join(sorted(sensitive))
                + ".",
            )
        for zone_id in (source_zone, target_zone):
            zone = self._zones.get(zone_id)
            allowlist = (
                set(_strings(zone.get("share_allowlist"))) if zone else set()
            )
            uncovered = sorted(set(categories) - allowlist)
            if uncovered:
                self._emit(
                    "policy_violation",
                    mission_id,
                    actor_ref=identity_id,
                    target_ref=target_id,
                )
                raise GovernanceViolation(
                    "AN_ADAPTER_SHARE_NOT_ALLOWED",
                    f"Zone {zone_id!r} does not allow sharing: "
                    + ", ".join(uncovered)
                    + ".",
                )
        self._emit(
            "data_shared",
            mission_id,
            actor_ref=identity_id,
            target_ref=target_id,
            share_categories=sorted(categories),
            source_zone_ref=source_zone,
            target_zone_ref=target_zone,
        )
