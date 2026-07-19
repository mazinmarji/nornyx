"""AN-004: local runtime-event evidence validation against an exact contract.

Nornyx ingests supplied local event files and validates conformance against
the exact contract, resolved composition, agentic-network lock, and subject
revision. Nornyx does not operate agents, intercept messages, call models,
invoke tools, open connectors, listen on networks, load credentials, grant
approvals, or monitor production. Accepting evidence proves conformance of the
supplied records only; hash validity proves content binding, not event truth.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .agentic_artifacts import (
    RUNTIME_EVENTS_SCHEMA_ID,
    RUNTIME_EVENTS_SCHEMA_VERSION,
    agentic_network_lock_digest,
    contract_digest,
    verify_agentic_network_lock,
)
from .governance.agentic_network import (
    AGENTIC_APPROVAL_ID,
    SENSITIVE_CATEGORIES,
    _mapping_items,
    _parse_time,
    _revocation_target_key,
    _strings,
)
from .governance.errors import error
from .governance.loader import read_local_file_bytes, reject_remote_or_device_path
from .governance.models import CompositionResult, GovernanceDiagnostic
from .governance.schemas import FORMAT_CHECKER, load_bundled_schema, schema_registry


REPORT_SCHEMA = "nornyx.agentic_evidence_report.v1"
MAX_EVENTS_BYTES = 8 * 1024 * 1024
EXTERNAL_ZONE_CLASSIFICATIONS = frozenset(
    {"external", "external_contract_only", "contract_only"}
)

_REQUIRED_FIELDS_BY_TYPE: dict[str, tuple[str, ...]] = {
    "capability_requested": ("capability_ref",),
    "capability_allowed": ("capability_ref", "policy_decision"),
    "capability_denied": ("capability_ref", "policy_decision"),
    "tool_invoked": ("capability_ref",),
    "delegation_requested": ("delegation_ref",),
    "delegation_accepted": ("delegation_ref",),
    "delegation_rejected": ("delegation_ref",),
    "handoff_initiated": ("handoff_ref", "target_ref"),
    "handoff_completed": ("handoff_ref", "target_ref"),
    "trust_zone_crossed": ("source_zone_ref", "target_zone_ref"),
    "data_shared": ("share_categories", "target_ref"),
    "approval_requested": ("approval_ref",),
    "approval_granted": ("approval_ref", "approver"),
    "approval_rejected": ("approval_ref", "approver"),
    "identity_revoked": ("target_ref",),
}
_EXPECTED_DECISION = {"capability_allowed": "allow", "capability_denied": "deny"}

LIMITATIONS = (
    "Validated evidence proves conformance of supplied records only.",
    "Hash validity proves content binding, not event truth.",
    "Nornyx does not observe, operate, or monitor the runtime.",
)


def _diagnostic(code: str, message: str, *, path: str) -> GovernanceDiagnostic:
    return GovernanceDiagnostic(
        "error", code, message, path=path, source_id=RUNTIME_EVENTS_SCHEMA_ID
    )


def load_runtime_events(path: str | Path) -> tuple[dict[str, Any], Path]:
    """Load one bounded local runtime-events JSON file, failing closed."""

    reject_remote_or_device_path(
        path, code_prefix="AN_EVT", noun="Runtime-event evidence"
    )
    supplied = Path(path)
    events_path = supplied if supplied.is_absolute() else Path.cwd() / supplied
    raw, resolved = read_local_file_bytes(
        events_path,
        allowed_root=events_path.parent,
        trust_root=None,
        code_prefix="AN_EVT",
        noun="Runtime-event evidence",
        max_bytes=MAX_EVENTS_BYTES,
    )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise error(
            "AN_EVT_MALFORMED",
            "Runtime-event evidence must be UTF-8.",
            path=str(resolved),
        ) from exc

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key {key!r}")
            result[key] = value
        return result

    try:
        payload = json.loads(text, object_pairs_hook=object_pairs)
    except (ValueError, json.JSONDecodeError) as exc:
        raise error(
            "AN_EVT_MALFORMED",
            f"Cannot parse runtime-event evidence: {exc}",
            path=str(resolved),
        ) from exc
    if not isinstance(payload, dict):
        raise error(
            "AN_EVT_MALFORMED",
            "Runtime-event evidence must be one top-level JSON object.",
            path=str(resolved),
        )
    return payload, resolved.parent


def _schema_diagnostics(payload: Mapping[str, Any]) -> list[GovernanceDiagnostic]:
    validator = Draft202012Validator(
        load_bundled_schema("agentic_runtime_events_v1.schema.json"),
        registry=schema_registry(),
        format_checker=FORMAT_CHECKER,
    )
    diagnostics = []
    for item in sorted(
        validator.iter_errors(dict(payload)),
        key=lambda item: list(map(str, item.absolute_path)),
    ):
        suffix = ".".join(str(part) for part in item.absolute_path)
        diagnostics.append(
            _diagnostic(
                "AN_EVT_SCHEMA_INVALID",
                item.message,
                path=f"events_file.{suffix}" if suffix else "events_file",
            )
        )
    return diagnostics


def _interval_contains(
    item: Mapping[str, Any], timestamp: datetime | None
) -> bool | None:
    valid_from = _parse_time(item.get("valid_from"))
    expires_at = _parse_time(item.get("expires_at"))
    if valid_from is None or expires_at is None or timestamp is None:
        return None
    return valid_from <= timestamp < expires_at


def validate_runtime_events(
    document: Mapping[str, Any],
    composition: CompositionResult,
    lock_payload: Mapping[str, Any],
    events_payload: Mapping[str, Any],
    *,
    events_root: Path | None = None,
) -> dict[str, Any]:
    """Validate supplied runtime-event evidence; returns a deterministic report."""

    diagnostics: list[GovernanceDiagnostic] = list(
        _schema_diagnostics(events_payload)
    )

    network = document.get("agentic_network")
    network = network if isinstance(network, Mapping) else {}
    expected_network_id = network.get("id")
    expected_revision = network.get("subject_revision")
    expected_contract = contract_digest(document)
    expected_lock = agentic_network_lock_digest(lock_payload)

    for item in verify_agentic_network_lock(lock_payload, document, composition):
        diagnostics.append(
            _diagnostic(
                "AN_EVT_LOCK_STALE",
                f"The supplied lock is stale: {item.message}",
                path=f"lock.{item.path}",
            )
        )

    identities = {
        str(item["id"]): item
        for item in _mapping_items(document.get("agent_identities"))
        if isinstance(item.get("id"), str)
    }
    capabilities = {
        str(item["name"]): item
        for item in _mapping_items(document.get("capabilities"))
        if isinstance(item.get("name"), str)
    }
    zones = {
        str(item["id"]): item
        for item in _mapping_items(network.get("trust_zones"))
        if isinstance(item.get("id"), str)
    }
    gates = _mapping_items(network.get("network_gates"))
    memberships = _mapping_items(network.get("memberships"))
    delegations = {
        str(item["id"]): item
        for item in _mapping_items(network.get("delegations"))
        if isinstance(item.get("id"), str)
    }
    handoffs = {
        str(item["id"]): item
        for item in _mapping_items(network.get("handoffs"))
        if isinstance(item.get("id"), str)
    }
    revocations = _mapping_items(network.get("revocations"))
    approval_ids = {item.id for item in composition.approval_requirements}
    approval_ids.update(
        str(item.get("id") or item.get("name"))
        for item in _mapping_items(document.get("approvals"))
        if isinstance(item.get("id") or item.get("name"), str)
    )
    module_roles: set[str] = set()
    for requirement in composition.approval_requirements:
        if requirement.id != AGENTIC_APPROVAL_ID:
            continue
        module_roles.update(requirement.required_roles)
        module_roles.update(requirement.eligible_roles)
        if requirement.accountable_authority is not None:
            module_roles.add(requirement.accountable_authority)

    def revoked_at(kind: str, ref: str, timestamp: datetime | None) -> bool:
        if timestamp is None:
            return False
        for revocation in revocations:
            key = _revocation_target_key(revocation.get("target"))
            if key != (kind, ref):
                continue
            effective = _parse_time(revocation.get("effective_at"))
            if effective is not None and timestamp >= effective:
                return True
        return False

    def identity_effective(ref: str, timestamp: datetime | None) -> bool:
        identity = identities.get(ref)
        if identity is None:
            return False
        if identity.get("status") != "active":
            return False
        return _interval_contains(identity, timestamp) is True and not revoked_at(
            "agent_identity", ref, timestamp
        )

    def holds_capability(
        actor: str, capability: str, timestamp: datetime | None
    ) -> bool:
        identity = identities.get(actor)
        if identity is None or capability not in _strings(
            identity.get("capability_refs")
        ):
            return False
        for membership in memberships:
            if membership.get("identity_ref") != actor:
                continue
            if membership.get("status") != "authorized":
                continue
            if _interval_contains(membership, timestamp) is not True:
                continue
            if revoked_at("membership", str(membership.get("id")), timestamp):
                continue
            if capability in _strings(membership.get("capability_refs")):
                return True
        return False

    def delegated_capability(
        actor: str,
        capability: str,
        delegation_ref: Any,
        timestamp: datetime | None,
    ) -> bool:
        if not isinstance(delegation_ref, str):
            return False
        delegation = delegations.get(delegation_ref)
        if delegation is None:
            return False
        return (
            delegation.get("delegate_ref") == actor
            and delegation.get("capability_ref") == capability
            and delegation.get("status") == "active"
            and _interval_contains(delegation, timestamp) is True
            and not revoked_at("delegation", delegation_ref, timestamp)
        )

    events = [
        item
        for item in (
            events_payload.get("events")
            if isinstance(events_payload.get("events"), list)
            else []
        )
        if isinstance(item, Mapping)
    ]

    if events_payload.get("network_id") not in (None, expected_network_id):
        diagnostics.append(
            _diagnostic(
                "AN_EVT_NETWORK_MISMATCH",
                "Evidence file network does not match the contract network.",
                path="events_file.network_id",
            )
        )

    seen_ids: dict[str, int] = {}
    seen_sequences: dict[tuple[str, int], int] = {}
    seen_content: dict[str, int] = {}
    by_mission: dict[str, list[tuple[int, Mapping[str, Any]]]] = {}

    for index, event in enumerate(events):
        path = f"events[{index}]"
        event_id = event.get("event_id")
        mission = event.get("mission_id")
        sequence = event.get("sequence")
        event_type = event.get("event_type")
        timestamp = _parse_time(event.get("timestamp"))
        actor_ref = event.get("actor_ref")

        if isinstance(event_id, str):
            if event_id in seen_ids:
                diagnostics.append(
                    _diagnostic(
                        "AN_EVT_DUPLICATE_ID",
                        f"Event id {event_id!r} appears more than once.",
                        path=f"{path}.event_id",
                    )
                )
            else:
                seen_ids[event_id] = index
        content_key = hashlib.sha256(
            json.dumps(
                {
                    key: value
                    for key, value in event.items()
                    if key not in {"event_id", "sequence"}
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        if content_key in seen_content:
            diagnostics.append(
                _diagnostic(
                    "AN_EVT_REPLAY",
                    "Event content replays an earlier event.",
                    path=path,
                )
            )
        else:
            seen_content[content_key] = index
        if isinstance(mission, str) and isinstance(sequence, int):
            key = (mission, sequence)
            if key in seen_sequences:
                diagnostics.append(
                    _diagnostic(
                        "AN_EVT_DUPLICATE_SEQUENCE",
                        f"Sequence {sequence} appears twice in mission "
                        f"{mission!r}.",
                        path=f"{path}.sequence",
                    )
                )
            else:
                seen_sequences[key] = index
            by_mission.setdefault(mission, []).append((index, event))

        for field, expected in (
            ("network_id", expected_network_id),
            ("subject_revision", expected_revision),
            ("contract_digest", expected_contract),
            ("network_lock_digest", expected_lock),
        ):
            observed = event.get(field)
            if observed is None or observed == expected:
                continue
            code = {
                "network_id": "AN_EVT_NETWORK_MISMATCH",
                "subject_revision": "AN_EVT_REVISION_MISMATCH",
                "contract_digest": "AN_EVT_CONTRACT_MISMATCH",
                "network_lock_digest": "AN_EVT_LOCK_MISMATCH",
            }[field]
            diagnostics.append(
                _diagnostic(
                    code,
                    f"Event {field} does not match the validated contract state.",
                    path=f"{path}.{field}",
                )
            )

        if isinstance(event_type, str):
            for field in _REQUIRED_FIELDS_BY_TYPE.get(event_type, ()):
                if event.get(field) in (None, [], {}):
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_FIELD_REQUIRED",
                            f"Event type {event_type!r} requires field {field!r}.",
                            path=f"{path}.{field}",
                        )
                    )
            expected_decision = _EXPECTED_DECISION.get(event_type)
            observed_decision = event.get("policy_decision")
            if (
                expected_decision is not None
                and observed_decision is not None
                and observed_decision != expected_decision
            ):
                diagnostics.append(
                    _diagnostic(
                        "AN_EVT_DECISION_CONTRADICTION",
                        f"Event type {event_type!r} contradicts policy decision "
                        f"{observed_decision!r}.",
                        path=f"{path}.policy_decision",
                    )
                )

        if isinstance(actor_ref, str):
            if actor_ref not in identities:
                diagnostics.append(
                    _diagnostic(
                        "AN_EVT_ACTOR_UNKNOWN",
                        f"Unknown actor identity {actor_ref!r}.",
                        path=f"{path}.actor_ref",
                    )
                )
            elif revoked_at("agent_identity", actor_ref, timestamp):
                diagnostics.append(
                    _diagnostic(
                        "AN_EVT_ACTOR_REVOKED",
                        "The acting identity is revoked at the event time.",
                        path=f"{path}.actor_ref",
                    )
                )
            elif not identity_effective(actor_ref, timestamp):
                diagnostics.append(
                    _diagnostic(
                        "AN_EVT_ACTOR_NOT_EFFECTIVE",
                        "The acting identity is not effective at the event time.",
                        path=f"{path}.actor_ref",
                    )
                )
        target_ref = event.get("target_ref")
        if isinstance(target_ref, str):
            if target_ref not in identities:
                diagnostics.append(
                    _diagnostic(
                        "AN_EVT_TARGET_UNKNOWN",
                        f"Unknown target identity {target_ref!r}.",
                        path=f"{path}.target_ref",
                    )
                )
            elif event_type != "identity_revoked" and revoked_at(
                "agent_identity", target_ref, timestamp
            ):
                diagnostics.append(
                    _diagnostic(
                        "AN_EVT_TARGET_REVOKED",
                        "The target identity is revoked at the event time.",
                        path=f"{path}.target_ref",
                    )
                )
        capability_ref = event.get("capability_ref")
        if isinstance(capability_ref, str) and capability_ref not in capabilities:
            diagnostics.append(
                _diagnostic(
                    "AN_EVT_CAPABILITY_UNKNOWN",
                    f"Undeclared capability {capability_ref!r}.",
                    path=f"{path}.capability_ref",
                )
            )
        delegation_ref = event.get("delegation_ref")
        if isinstance(delegation_ref, str) and delegation_ref not in delegations:
            diagnostics.append(
                _diagnostic(
                    "AN_EVT_DELEGATION_UNKNOWN",
                    f"Undeclared delegation {delegation_ref!r}.",
                    path=f"{path}.delegation_ref",
                )
            )
        handoff_ref = event.get("handoff_ref")
        if isinstance(handoff_ref, str) and handoff_ref not in handoffs:
            diagnostics.append(
                _diagnostic(
                    "AN_EVT_HANDOFF_UNKNOWN",
                    f"Undeclared handoff {handoff_ref!r}.",
                    path=f"{path}.handoff_ref",
                )
            )
        for field in ("source_zone_ref", "target_zone_ref"):
            zone_ref = event.get(field)
            if isinstance(zone_ref, str) and zone_ref not in zones:
                diagnostics.append(
                    _diagnostic(
                        "AN_EVT_ZONE_UNKNOWN",
                        f"Undeclared trust zone {zone_ref!r}.",
                        path=f"{path}.{field}",
                    )
                )
        approval_ref = event.get("approval_ref")
        if isinstance(approval_ref, str) and approval_ref not in approval_ids:
            diagnostics.append(
                _diagnostic(
                    "AN_EVT_APPROVAL_UNKNOWN",
                    f"Undeclared approval {approval_ref!r}.",
                    path=f"{path}.approval_ref",
                )
            )

        if event_type in {"capability_allowed", "tool_invoked"} and isinstance(
            capability_ref, str
        ) and capability_ref in capabilities and isinstance(actor_ref, str):
            if not holds_capability(
                actor_ref, capability_ref, timestamp
            ) and not delegated_capability(
                actor_ref, capability_ref, delegation_ref, timestamp
            ):
                diagnostics.append(
                    _diagnostic(
                        "AN_EVT_CAPABILITY_NOT_HELD",
                        f"Actor {actor_ref!r} neither holds nor validly receives "
                        f"capability {capability_ref!r} at the event time.",
                        path=f"{path}.capability_ref",
                    )
                )

        if event_type in {"delegation_accepted"} and isinstance(delegation_ref, str):
            delegation = delegations.get(delegation_ref)
            if delegation is not None:
                if delegation.get("delegate_ref") != actor_ref:
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_DELEGATION_ACTOR_MISMATCH",
                            "Only the declared delegate can accept a delegation.",
                            path=f"{path}.actor_ref",
                        )
                    )
                if _interval_contains(delegation, timestamp) is False:
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_DELEGATION_EXPIRED",
                            "The delegation is outside its validity window at "
                            "the event time.",
                            path=f"{path}.delegation_ref",
                        )
                    )
                if revoked_at("delegation", delegation_ref, timestamp):
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_DELEGATION_REVOKED",
                            "The delegation is revoked at the event time.",
                            path=f"{path}.delegation_ref",
                        )
                    )

        if event_type == "handoff_initiated" and isinstance(handoff_ref, str):
            handoff = handoffs.get(handoff_ref)
            if handoff is not None and (
                handoff.get("from_identity_ref") != actor_ref
                or handoff.get("to_identity_ref") != target_ref
            ):
                diagnostics.append(
                    _diagnostic(
                        "AN_EVT_HANDOFF_PARTY_MISMATCH",
                        "Handoff parties must match the declared handoff record.",
                        path=f"{path}.handoff_ref",
                    )
                )

        if event_type == "trust_zone_crossed":
            source_zone = zones.get(str(event.get("source_zone_ref")))
            target_zone_name = event.get("target_zone_ref")
            if source_zone is not None and isinstance(target_zone_name, str):
                if target_zone_name not in _strings(
                    source_zone.get("allowed_transition_targets")
                ):
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_CROSSING_NOT_DECLARED",
                            "The trust-zone crossing is not a declared allowed "
                            "transition.",
                            path=f"{path}.target_zone_ref",
                        )
                    )
                covering = [
                    gate
                    for gate in gates
                    if str(event.get("source_zone_ref"))
                    in _strings(gate.get("source_zone_refs"))
                    and target_zone_name in _strings(gate.get("target_zone_refs"))
                ]
                if not covering:
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_CROSSING_UNGOVERNED",
                            "No declared gate governs this trust-zone crossing.",
                            path=f"{path}.target_zone_ref",
                        )
                    )
                target_zone = zones.get(target_zone_name)
                if (
                    target_zone is not None
                    and target_zone.get("classification")
                    in EXTERNAL_ZONE_CLASSIFICATIONS
                    and event.get("approval_ref") != AGENTIC_APPROVAL_ID
                ):
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_CROSSING_APPROVAL_MISSING",
                            "External trust-zone crossings require the human "
                            "agentic-network approval.",
                            path=f"{path}.approval_ref",
                        )
                    )

        if event_type == "data_shared":
            categories = set(_strings(event.get("share_categories")))
            sensitive = categories & SENSITIVE_CATEGORIES
            if sensitive:
                diagnostics.append(
                    _diagnostic(
                        "AN_EVT_SENSITIVE_SHARING",
                        "Sensitive categories were shared: "
                        + ", ".join(sorted(sensitive))
                        + ".",
                        path=f"{path}.share_categories",
                    )
                )
            for field in ("source_zone_ref", "target_zone_ref"):
                zone = zones.get(str(event.get(field)))
                if zone is None:
                    continue
                uncovered = sorted(
                    categories
                    - SENSITIVE_CATEGORIES
                    - set(_strings(zone.get("share_allowlist")))
                )
                if uncovered:
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_SHARE_NOT_ALLOWED",
                            f"Shared categories exceed the {field} allowlist: "
                            + ", ".join(uncovered)
                            + ".",
                            path=f"{path}.share_categories",
                        )
                    )

        if event_type in {"approval_granted", "approval_rejected"}:
            approver = event.get("approver")
            if isinstance(approver, Mapping):
                if approver.get("actor_type") != "human":
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_APPROVAL_NON_HUMAN",
                            "Approval outcomes require a human approver.",
                            path=f"{path}.approver.actor_type",
                        )
                    )
                role = approver.get("role")
                if isinstance(role, str) and role not in module_roles:
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_APPROVAL_ROLE_INVALID",
                            f"Approver role {role!r} is outside the composed "
                            "module authority.",
                            path=f"{path}.approver.role",
                        )
                    )

        artifact = event.get("evidence_artifact")
        if isinstance(artifact, Mapping):
            artifact_path = artifact.get("path")
            declared_hash = artifact.get("sha256")
            if events_root is None:
                diagnostics.append(
                    _diagnostic(
                        "AN_EVT_ARTIFACT_MISSING",
                        "Evidence artifacts require a local evidence root.",
                        path=f"{path}.evidence_artifact.path",
                    )
                )
            elif isinstance(artifact_path, str) and isinstance(declared_hash, str):
                try:
                    raw, _resolved = read_local_file_bytes(
                        events_root / artifact_path,
                        allowed_root=events_root,
                        trust_root=None,
                        code_prefix="AN_EVT",
                        noun="Evidence artifact",
                        max_bytes=MAX_EVENTS_BYTES,
                    )
                except Exception:  # GovernanceError and OS failures fail closed
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_ARTIFACT_MISSING",
                            f"Evidence artifact {artifact_path!r} cannot be read "
                            "inside the evidence root.",
                            path=f"{path}.evidence_artifact.path",
                        )
                    )
                else:
                    if hashlib.sha256(raw).hexdigest() != declared_hash:
                        diagnostics.append(
                            _diagnostic(
                                "AN_EVT_ARTIFACT_HASH_MISMATCH",
                                f"Evidence artifact {artifact_path!r} does not "
                                "match its declared hash.",
                                path=f"{path}.evidence_artifact.sha256",
                            )
                        )

    for mission, mission_events in sorted(by_mission.items()):
        ordered = sorted(
            mission_events, key=lambda item: (item[1].get("sequence"), item[0])
        )
        sequences = [
            event.get("sequence")
            for _, event in ordered
            if isinstance(event.get("sequence"), int)
        ]
        if sequences and sequences != list(range(1, len(sequences) + 1)):
            diagnostics.append(
                _diagnostic(
                    "AN_EVT_SEQUENCE_GAP",
                    f"Mission {mission!r} sequences must be contiguous from 1.",
                    path=f"missions.{mission}",
                )
            )
        last_time: datetime | None = None
        allowed_capabilities: set[tuple[Any, Any]] = set()
        requested_delegations: set[Any] = set()
        requested_approvals: set[Any] = set()
        initiated_handoffs: set[Any] = set()
        decisions: dict[tuple[Any, Any], str] = {}
        ids_in_mission = {
            event.get("event_id")
            for _, event in ordered
            if isinstance(event.get("event_id"), str)
        }
        sequence_by_id = {
            event.get("event_id"): event.get("sequence")
            for _, event in ordered
            if isinstance(event.get("event_id"), str)
        }
        for index, event in ordered:
            path = f"events[{index}]"
            timestamp = _parse_time(event.get("timestamp"))
            if timestamp is not None:
                if last_time is not None and timestamp < last_time:
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_ORDER_INVALID",
                            "Event timestamps must not decrease along the "
                            "mission sequence.",
                            path=f"{path}.timestamp",
                        )
                    )
                last_time = timestamp
            for dependency in _strings(event.get("depends_on")):
                if dependency not in ids_in_mission:
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_DEPENDENCY_MISSING",
                            f"Dependency event {dependency!r} is absent from "
                            "the mission stream.",
                            path=f"{path}.depends_on",
                        )
                    )
                    continue
                dependency_sequence = sequence_by_id.get(dependency)
                if (
                    isinstance(dependency_sequence, int)
                    and isinstance(event.get("sequence"), int)
                    and dependency_sequence >= event.get("sequence")
                ):
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_ORDER_INVALID",
                            f"Dependency event {dependency!r} must precede this "
                            "event in the mission sequence.",
                            path=f"{path}.depends_on",
                        )
                    )

            event_type = event.get("event_type")
            actor = event.get("actor_ref")
            capability = event.get("capability_ref")
            if event_type == "capability_allowed":
                allowed_capabilities.add((actor, capability))
                previous = decisions.get((actor, capability))
                if previous == "deny":
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_DECISION_CONTRADICTION",
                            "The same mission both denies and allows the "
                            "capability for this actor.",
                            path=f"{path}.event_type",
                        )
                    )
                decisions[(actor, capability)] = "allow"
            elif event_type == "capability_denied":
                previous = decisions.get((actor, capability))
                if previous == "allow":
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_DECISION_CONTRADICTION",
                            "The same mission both allows and denies the "
                            "capability for this actor.",
                            path=f"{path}.event_type",
                        )
                    )
                decisions[(actor, capability)] = "deny"
            elif event_type == "tool_invoked":
                if (actor, capability) not in allowed_capabilities:
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_TOOL_WITHOUT_ALLOWANCE",
                            "Tool invocation requires a prior capability "
                            "allowance in the mission.",
                            path=f"{path}.event_type",
                        )
                    )
            elif event_type == "delegation_requested":
                requested_delegations.add(event.get("delegation_ref"))
            elif event_type in {"delegation_accepted", "delegation_rejected"}:
                if event.get("delegation_ref") not in requested_delegations:
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_ACCEPTANCE_WITHOUT_REQUEST",
                            "Delegation outcomes require a prior delegation "
                            "request in the mission.",
                            path=f"{path}.event_type",
                        )
                    )
            elif event_type == "handoff_initiated":
                initiated_handoffs.add(event.get("handoff_ref"))
            elif event_type == "handoff_completed":
                if event.get("handoff_ref") not in initiated_handoffs:
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_COMPLETION_WITHOUT_INITIATION",
                            "Handoff completion requires a prior initiation in "
                            "the mission.",
                            path=f"{path}.event_type",
                        )
                    )
            elif event_type == "approval_requested":
                requested_approvals.add(event.get("approval_ref"))
            elif event_type in {"approval_granted", "approval_rejected"}:
                if event.get("approval_ref") not in requested_approvals:
                    diagnostics.append(
                        _diagnostic(
                            "AN_EVT_GRANT_WITHOUT_REQUEST",
                            "Approval outcomes require a prior approval request "
                            "in the mission.",
                            path=f"{path}.event_type",
                        )
                    )

    ordered_diagnostics = tuple(
        sorted(
            diagnostics,
            key=lambda item: (item.code, item.path or "", item.message),
        )
    )
    counts: dict[str, int] = {}
    for event in events:
        event_type = event.get("event_type")
        if isinstance(event_type, str):
            counts[event_type] = counts.get(event_type, 0) + 1
    return {
        "schema": REPORT_SCHEMA,
        "status": "fail" if ordered_diagnostics else "pass",
        "network_id": expected_network_id,
        "subject_revision": expected_revision,
        "contract_digest": expected_contract,
        "network_lock_digest": expected_lock,
        "events_schema": RUNTIME_EVENTS_SCHEMA_ID,
        "events_schema_version": RUNTIME_EVENTS_SCHEMA_VERSION,
        "event_count": len(events),
        "mission_count": len(by_mission),
        "counts_by_type": dict(sorted(counts.items())),
        "diagnostics": [item.to_dict() for item in ordered_diagnostics],
        "limitations": list(LIMITATIONS),
        "safety": {
            "models_called": False,
            "tools_executed": False,
            "external_connectors_used": False,
            "network_used": False,
            "producers_executed": False,
        },
    }
