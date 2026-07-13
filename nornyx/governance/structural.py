from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from .architecture import architecture_conformance_check
from .approvals import (
    CORE_DENIED_ACTOR_TYPES,
    normalize_approval,
    trusted_normalized_approval,
)
from .errors import GovernanceError
from .models import CompositionResult, GovernanceDiagnostic, NormalizedApproval


CORE_NON_EXCEPTABLE_CONTROLS = {
    "ai_approver_denial",
    "data_only_packs",
    "no_automatic_approval",
    "no_executable_code",
    "no_external_tool_execution",
    "no_network_loading",
    "pack_integrity",
}
HIGH_IMPACT_ACTIONS = {
    "deploy",
    "external_write",
    "merge",
    "production_change",
    "promote",
    "release",
}
CHANGE_TRANSITIONS = {
    "draft": {"proposed", "cancelled"},
    "proposed": {"approved", "rejected", "cancelled"},
    "approved": {"in_progress", "cancelled"},
    "in_progress": {"completed", "rolled_back", "cancelled"},
    "completed": {"closed", "rolled_back"},
    "rolled_back": {"closed"},
    "rejected": {"closed"},
    "cancelled": {"closed"},
    "closed": set(),
}


def _diagnostic(
    code: str,
    message: str,
    *,
    path: str,
    source_id: str,
    level: str = "error",
) -> GovernanceDiagnostic:
    return GovernanceDiagnostic(  # type: ignore[arg-type]
        level,
        code,
        message,
        path=path,
        source_id=source_id,
    )


def _parse_time(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _as_list(value: Any) -> list[Any] | None:
    return value if isinstance(value, list) else None


def change_scope_hash(change: Mapping[str, Any]) -> str:
    payload = {
        "scope": sorted(str(item) for item in (_as_list(change.get("scope")) or [])),
        "excluded_scope": sorted(
            str(item) for item in (_as_list(change.get("excluded_scope")) or [])
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _normalize_document_approval(value: Any, index: int) -> NormalizedApproval | None:
    if not isinstance(value, Mapping):
        return None
    if value.get("schema") == "nornyx.normalized_approval.v1":
        return trusted_normalized_approval(value)
    governed = "id" in value and (
        "required_evidence" in value
        or any(
            field in value
            for field in (
                "eligible_approver_roles",
                "approver_roles",
                "approvers",
                "eligible_approvers",
            )
        )
    )
    try:
        return normalize_approval(
            value,
            shape="governed_package_gate" if governed else "ordinary_approval",
            path=f"approvals[{index}]",
            fallback_id=f"approval-{index}",
        )
    except (GovernanceError, AttributeError, KeyError, TypeError, ValueError):
        return None


def _human_approval(
    document: Mapping[str, Any],
    composition: CompositionResult,
    *,
    as_of: datetime | None,
    document_root: Path | None,
) -> tuple[GovernanceDiagnostic, ...]:
    del composition, document_root
    source_id = "human_approval.v1"
    approvals = _as_list(document.get("approvals"))
    if approvals is None or not approvals:
        return (
            _diagnostic(
                "APPROVAL_DECLARATION_REQUIRED",
                "Human approval governance requires at least one approval declaration.",
                path="approvals",
                source_id=source_id,
            ),
        )
    diagnostics: list[GovernanceDiagnostic] = []
    denied_required = set(CORE_DENIED_ACTOR_TYPES)
    for index, source in enumerate(approvals):
        path = f"approvals[{index}]"
        normalized = _normalize_document_approval(source, index)
        if normalized is None or normalized.resolution != "complete":
            diagnostics.append(
                _diagnostic(
                    "APPROVAL_DECLARATION_INVALID",
                    "Approval declaration cannot be authoritatively normalized.",
                    path=path,
                    source_id=source_id,
                )
            )
            continue
        if not normalized.required_roles or not normalized.eligible_roles:
            diagnostics.append(
                _diagnostic(
                    "APPROVAL_HUMAN_ROLE_REQUIRED",
                    "Approval must declare required and eligible human roles.",
                    path=path,
                    source_id=source_id,
                )
            )
        declared_denials = set(normalized.denied_actor_types) | set(
            normalized.denied_execution_surfaces
        )
        missing_denials = denied_required - declared_denials
        if missing_denials:
            diagnostics.append(
                _diagnostic(
                    "APPROVAL_CORE_DENIAL_MISSING",
                    "Approval must explicitly deny all non-human authority categories: "
                    + ", ".join(sorted(missing_denials))
                    + ".",
                    path=path,
                    source_id=source_id,
                )
            )
        if not normalized.actions_requiring_approval or not normalized.required_evidence:
            diagnostics.append(
                _diagnostic(
                    "APPROVAL_SCOPE_OR_EVIDENCE_MISSING",
                    "Approval must declare governed actions and prerequisite evidence.",
                    path=path,
                    source_id=source_id,
                )
            )
        if normalized.accountable_authority is None:
            diagnostics.append(
                _diagnostic(
                    "APPROVAL_AUTHORITY_MISSING",
                    "Approval must identify an accountable human authority.",
                    path=f"{path}.accountable_authority",
                    source_id=source_id,
                )
            )
        binding = normalized.revision_binding
        if not isinstance(binding, Mapping) or binding.get("exact") is not True:
            diagnostics.append(
                _diagnostic(
                    "APPROVAL_REVISION_BINDING_REQUIRED",
                    "Approval must bind to one exact governed revision.",
                    path=f"{path}.revision_binding",
                    source_id=source_id,
                )
            )
        if not normalized.invalidation_conditions:
            diagnostics.append(
                _diagnostic(
                    "APPROVAL_INVALIDATION_REQUIRED",
                    "Approval must declare invalidation conditions.",
                    path=f"{path}.invalidation_conditions",
                    source_id=source_id,
                )
            )
        high_impact = bool(set(normalized.actions_requiring_approval) & HIGH_IMPACT_ACTIONS)
        if high_impact and normalized.expires_at is None:
            diagnostics.append(
                _diagnostic(
                    "APPROVAL_EXPIRY_REQUIRED",
                    "High-impact approval must declare an expiry.",
                    path=f"{path}.expires_at",
                    source_id=source_id,
                )
            )
        if normalized.expires_at is not None:
            if as_of is None:
                diagnostics.append(
                    _diagnostic(
                        "GOVERNANCE_TIME_REQUIRED",
                        "An explicit validation time is required for expiring approvals.",
                        path=path,
                        source_id=source_id,
                    )
                )
            else:
                try:
                    if _parse_time(normalized.expires_at) <= as_of:
                        diagnostics.append(
                            _diagnostic(
                                "APPROVAL_EXPIRED",
                                "Approval has expired.",
                                path=f"{path}.expires_at",
                                source_id=source_id,
                            )
                        )
                except ValueError:
                    diagnostics.append(
                        _diagnostic(
                            "APPROVAL_EXPIRY_INVALID",
                            "Approval expiry is not a valid offset timestamp.",
                            path=f"{path}.expires_at",
                            source_id=source_id,
                        )
                    )
    return tuple(diagnostics)


def _artifact_hash(root: Path, relative: str) -> str | None:
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            return None
    try:
        if not current.is_file():
            return None
        resolved = current.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
        return "sha256:" + hashlib.sha256(resolved.read_bytes()).hexdigest()
    except (OSError, ValueError):
        return None


def _evidence_integrity(
    document: Mapping[str, Any],
    composition: CompositionResult,
    *,
    as_of: datetime | None,
    document_root: Path | None,
) -> tuple[GovernanceDiagnostic, ...]:
    source_id = "evidence_integrity.v1"
    block = document.get("governance_evidence")
    if not isinstance(block, Mapping):
        return ()
    records = _as_list(block.get("records"))
    subject_revision = block.get("subject_revision")
    if records is None:
        return ()
    diagnostics: list[GovernanceDiagnostic] = []
    by_id: dict[str, Mapping[str, Any]] = {}
    by_artifact: dict[str, str] = {}
    for index, raw in enumerate(records):
        if not isinstance(raw, Mapping):
            continue
        path = f"governance_evidence.records[{index}]"
        evidence_id = str(raw.get("id", ""))
        if evidence_id in by_id:
            diagnostics.append(
                _diagnostic(
                    "EVIDENCE_DUPLICATE_ID",
                    f"Evidence id {evidence_id!r} is duplicated.",
                    path=f"{path}.id",
                    source_id=source_id,
                )
            )
        else:
            by_id[evidence_id] = raw
        if raw.get("subject_revision") != subject_revision:
            diagnostics.append(
                _diagnostic(
                    "EVIDENCE_REVISION_MISMATCH",
                    "Evidence is not bound to the governed subject revision.",
                    path=f"{path}.subject_revision",
                    source_id=source_id,
                )
            )
        artifact = str(raw.get("artifact", ""))
        claimed_hash = str(raw.get("content_hash", ""))
        if artifact in by_artifact and by_artifact[artifact] != claimed_hash:
            diagnostics.append(
                _diagnostic(
                    "EVIDENCE_HASH_SUBSTITUTION",
                    "The same artifact is claimed with conflicting content hashes.",
                    path=f"{path}.content_hash",
                    source_id=source_id,
                )
            )
        by_artifact[artifact] = claimed_hash
        if document_root is None:
            diagnostics.append(
                _diagnostic(
                    "EVIDENCE_ARTIFACT_ROOT_REQUIRED",
                    "A trusted document root is required to verify evidence artifacts.",
                    path=f"{path}.artifact",
                    source_id=source_id,
                )
            )
        else:
            observed_hash = _artifact_hash(document_root, artifact)
            if observed_hash is None:
                diagnostics.append(
                    _diagnostic(
                        "EVIDENCE_ARTIFACT_UNAVAILABLE",
                        "Evidence artifact is missing, unreadable, outside the root, or symlinked.",
                        path=f"{path}.artifact",
                        source_id=source_id,
                    )
                )
            elif observed_hash != claimed_hash:
                diagnostics.append(
                    _diagnostic(
                        "EVIDENCE_ARTIFACT_HASH_MISMATCH",
                        "Evidence artifact hash does not match the declared content hash.",
                        path=f"{path}.content_hash",
                        source_id=source_id,
                    )
                )
        if as_of is None:
            diagnostics.append(
                _diagnostic(
                    "GOVERNANCE_TIME_REQUIRED",
                    "An explicit validation time is required for evidence freshness.",
                    path=path,
                    source_id=source_id,
                )
            )
        else:
            try:
                generated = _parse_time(str(raw.get("generated_at")))
                expires = _parse_time(str(raw.get("expires_at")))
                if generated is None or expires is None:
                    raise ValueError("missing timestamp")
                if generated > as_of:
                    diagnostics.append(
                        _diagnostic(
                            "EVIDENCE_GENERATED_IN_FUTURE",
                            "Evidence generation time is after the validation time.",
                            path=f"{path}.generated_at",
                            source_id=source_id,
                        )
                    )
                if generated >= expires or expires <= as_of:
                    diagnostics.append(
                        _diagnostic(
                            "EVIDENCE_STALE",
                            "Evidence is stale or has an invalid freshness interval.",
                            path=f"{path}.expires_at",
                            source_id=source_id,
                        )
                    )
            except ValueError:
                diagnostics.append(
                    _diagnostic(
                        "EVIDENCE_TIME_INVALID",
                        "Evidence timestamps must be valid offset timestamps.",
                        path=path,
                        source_id=source_id,
                    )
                )

    for evidence_id, record in sorted(by_id.items()):
        dependencies = _as_list(record.get("dependencies")) or []
        for dependency in dependencies:
            if dependency == evidence_id or dependency not in by_id:
                diagnostics.append(
                    _diagnostic(
                        "EVIDENCE_DEPENDENCY_INVALID",
                        f"Evidence dependency {dependency!r} is missing or self-referential.",
                        path=f"governance_evidence.records.{evidence_id}.dependencies",
                        source_id=source_id,
                    )
                )
    graph = {
        evidence_id: [str(item) for item in (_as_list(record.get("dependencies")) or [])]
        for evidence_id, record in by_id.items()
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(evidence_id: str) -> bool:
        if evidence_id in visiting:
            return True
        if evidence_id in visited:
            return False
        visiting.add(evidence_id)
        cyclic = any(item in graph and visit(item) for item in graph[evidence_id])
        visiting.remove(evidence_id)
        visited.add(evidence_id)
        return cyclic

    if any(visit(evidence_id) for evidence_id in sorted(graph)):
        diagnostics.append(
            _diagnostic(
                "EVIDENCE_DEPENDENCY_CYCLE",
                "Evidence dependencies contain a cycle.",
                path="governance_evidence.records",
                source_id=source_id,
            )
        )

    available = {
        str(record.get("id")) for record in by_id.values()
    } | {str(record.get("type")) for record in by_id.values()}
    module_requirements = (
        requirement
        for module in composition.modules
        for requirement in module.evidence_requirements
    )
    for requirement in module_requirements:
        if requirement.get("required") is True:
            required_id = str(requirement.get("id") or requirement.get("type") or "")
            required_type = str(requirement.get("type") or "")
            if required_id not in available and required_type not in available:
                diagnostics.append(
                    _diagnostic(
                        "EVIDENCE_REQUIRED_MISSING",
                        f"Required evidence {required_id or required_type!r} is missing.",
                        path="governance_evidence.records",
                        source_id=source_id,
                    )
                )
    return tuple(diagnostics)


def _separation_of_duties(
    document: Mapping[str, Any],
    composition: CompositionResult,
    *,
    as_of: datetime | None,
    document_root: Path | None,
) -> tuple[GovernanceDiagnostic, ...]:
    del composition, as_of, document_root
    source_id = "separation_of_duties.v1"
    block = document.get("separation_of_duties")
    if not isinstance(block, Mapping):
        return ()
    assignments = _as_list(block.get("assignments"))
    if assignments is None:
        return ()
    diagnostics: list[GovernanceDiagnostic] = []
    subjects: set[str] = set()
    for index, raw in enumerate(assignments):
        if not isinstance(raw, Mapping):
            continue
        path = f"separation_of_duties.assignments[{index}]"
        subject = str(raw.get("subject", ""))
        if subject in subjects:
            diagnostics.append(
                _diagnostic(
                    "SOD_DUPLICATE_SUBJECT",
                    f"Separation assignment for {subject!r} is duplicated.",
                    path=f"{path}.subject",
                    source_id=source_id,
                )
            )
        subjects.add(subject)
        author = raw.get("author")
        approvers = set(_as_list(raw.get("approvers")) or [])
        if raw.get("risk_tier") in {"high", "critical"} and author in approvers:
            diagnostics.append(
                _diagnostic(
                    "SOD_SELF_APPROVAL",
                    "The author cannot approve their own high-risk change.",
                    path=path,
                    source_id=source_id,
                )
            )
        producers = set(_as_list(raw.get("evidence_producers")) or [])
        if raw.get("require_evidence_independence") is True and approvers and approvers <= producers:
            diagnostics.append(
                _diagnostic(
                    "SOD_EVIDENCE_PRODUCER_SOLE_APPROVER",
                    "Evidence producers cannot be the only approvers when independence is required.",
                    path=path,
                    source_id=source_id,
                )
            )
        for requester_field, approver_field, code in (
            ("release_requester", "final_release_approver", "SOD_RELEASE_AUTHORITY_CONFLICT"),
            ("exception_requester", "exception_approver", "SOD_EXCEPTION_AUTHORITY_CONFLICT"),
        ):
            requester = raw.get(requester_field)
            approver = raw.get(approver_field)
            if requester is not None and requester == approver:
                diagnostics.append(
                    _diagnostic(
                        code,
                        f"{requester_field} and {approver_field} must be disjoint.",
                        path=path,
                        source_id=source_id,
                    )
                )
    return tuple(diagnostics)


def _exception_management(
    document: Mapping[str, Any],
    composition: CompositionResult,
    *,
    as_of: datetime | None,
    document_root: Path | None,
) -> tuple[GovernanceDiagnostic, ...]:
    del composition, document_root
    source_id = "exception_management.v1"
    block = document.get("exceptions")
    if not isinstance(block, Mapping):
        return ()
    entries = _as_list(block.get("entries"))
    if entries is None:
        return ()
    diagnostics: list[GovernanceDiagnostic] = []
    identifiers: set[str] = set()
    for index, raw in enumerate(entries):
        if not isinstance(raw, Mapping):
            continue
        path = f"exceptions.entries[{index}]"
        identifier = str(raw.get("id", ""))
        if identifier in identifiers:
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_DUPLICATE_ID",
                    f"Exception id {identifier!r} is duplicated.",
                    path=f"{path}.id",
                    source_id=source_id,
                )
            )
        identifiers.add(identifier)
        control = str(raw.get("control", ""))
        if control.startswith("nornyx.core.") or control in CORE_NON_EXCEPTABLE_CONTROLS:
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_CORE_CONTROL_FORBIDDEN",
                    f"Core safety control {control!r} cannot be excepted.",
                    path=f"{path}.control",
                    source_id=source_id,
                )
            )
        if raw.get("requester") == raw.get("approving_authority"):
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_SELF_APPROVAL",
                    "Exception requester and approving authority must be disjoint.",
                    path=path,
                    source_id=source_id,
                )
            )
        if raw.get("status") == "closed" and not (_as_list(raw.get("closure_evidence")) or []):
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_CLOSURE_EVIDENCE_MISSING",
                    "A closed exception requires closure evidence.",
                    path=f"{path}.closure_evidence",
                    source_id=source_id,
                )
            )
        if as_of is None:
            diagnostics.append(
                _diagnostic(
                    "GOVERNANCE_TIME_REQUIRED",
                    "An explicit validation time is required for governed exceptions.",
                    path=path,
                    source_id=source_id,
                )
            )
            continue
        try:
            starts = _parse_time(str(raw.get("starts_at")))
            expires = _parse_time(str(raw.get("expires_at")))
            if starts is None or expires is None:
                raise ValueError("missing timestamp")
            if starts >= expires:
                diagnostics.append(
                    _diagnostic(
                        "EXCEPTION_INTERVAL_INVALID",
                        "Exception expiry must be after its start time.",
                        path=path,
                        source_id=source_id,
                    )
                )
            if raw.get("status") in {"approved", "active"} and expires <= as_of:
                diagnostics.append(
                    _diagnostic(
                        "EXCEPTION_EXPIRED",
                        "Approved or active exception has expired.",
                        path=f"{path}.expires_at",
                        source_id=source_id,
                    )
                )
        except ValueError:
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_TIME_INVALID",
                    "Exception timestamps must be valid offset timestamps.",
                    path=path,
                    source_id=source_id,
                )
            )
    return tuple(diagnostics)


def _change_control(
    document: Mapping[str, Any],
    composition: CompositionResult,
    *,
    as_of: datetime | None,
    document_root: Path | None,
) -> tuple[GovernanceDiagnostic, ...]:
    del composition, as_of, document_root
    source_id = "change_control.v1"
    changes = _as_list(document.get("changes"))
    if changes is None:
        return ()
    diagnostics: list[GovernanceDiagnostic] = []

    evidence_block = document.get("governance_evidence")
    evidence_records = (
        _as_list(evidence_block.get("records"))
        if isinstance(evidence_block, Mapping)
        else []
    ) or []
    evidence_ids = {
        str(value)
        for record in evidence_records
        if isinstance(record, Mapping)
        for value in (record.get("id"), record.get("type"))
        if value is not None
    }
    exception_block = document.get("exceptions")
    exception_entries = (
        _as_list(exception_block.get("entries"))
        if isinstance(exception_block, Mapping)
        else []
    ) or []
    exception_ids = {
        str(item.get("id")) for item in exception_entries if isinstance(item, Mapping)
    }
    duty_block = document.get("separation_of_duties")
    duty_assignments = (
        _as_list(duty_block.get("assignments"))
        if isinstance(duty_block, Mapping)
        else []
    ) or []
    duty_subjects = {
        str(item.get("subject")) for item in duty_assignments if isinstance(item, Mapping)
    }
    approval_values = _as_list(document.get("approvals")) or []
    approvals = [
        normalized
        for index, value in enumerate(approval_values)
        if (normalized := _normalize_document_approval(value, index)) is not None
        and normalized.resolution == "complete"
    ]

    identifiers: set[str] = set()
    for index, raw in enumerate(changes):
        if not isinstance(raw, Mapping):
            continue
        path = f"changes[{index}]"
        change_id = str(raw.get("id", ""))
        if change_id in identifiers:
            diagnostics.append(
                _diagnostic(
                    "CHANGE_DUPLICATE_ID",
                    f"Change id {change_id!r} is duplicated.",
                    path=f"{path}.id",
                    source_id=source_id,
                )
            )
        identifiers.add(change_id)

        status = raw.get("status")
        transition = raw.get("transition")
        if status not in (None, "draft") and not isinstance(transition, Mapping):
            diagnostics.append(
                _diagnostic(
                    "CHANGE_TRANSITION_EVIDENCE_MISSING",
                    "A non-draft change requires a declared transition and evidence.",
                    path=f"{path}.transition",
                    source_id=source_id,
                )
            )
        if isinstance(transition, Mapping):
            previous = str(transition.get("from", ""))
            target = str(transition.get("to", ""))
            if target != status or target not in CHANGE_TRANSITIONS.get(previous, set()):
                diagnostics.append(
                    _diagnostic(
                        "CHANGE_LIFECYCLE_TRANSITION_INVALID",
                        f"Transition {previous!r} -> {target!r} is invalid for "
                        f"status {status!r}.",
                        path=f"{path}.transition",
                        source_id=source_id,
                    )
                )
            transition_evidence = {
                str(item) for item in (_as_list(transition.get("evidence")) or [])
            }
            if not transition_evidence or not transition_evidence <= evidence_ids:
                diagnostics.append(
                    _diagnostic(
                        "CHANGE_TRANSITION_EVIDENCE_MISSING",
                        "Lifecycle transition evidence is missing from governance evidence.",
                        path=f"{path}.transition.evidence",
                        source_id=source_id,
                    )
                )

        required_evidence = {
            str(item) for item in (_as_list(raw.get("required_evidence")) or [])
        }
        missing_evidence = required_evidence - evidence_ids
        if missing_evidence:
            diagnostics.append(
                _diagnostic(
                    "CHANGE_EVIDENCE_MISSING",
                    "Change-required evidence is missing: "
                    + ", ".join(sorted(missing_evidence))
                    + ".",
                    path=f"{path}.required_evidence",
                    source_id=source_id,
                )
            )

        exception_refs = {str(item) for item in (_as_list(raw.get("exceptions")) or [])}
        unknown_exceptions = exception_refs - exception_ids
        if unknown_exceptions:
            diagnostics.append(
                _diagnostic(
                    "CHANGE_EXCEPTION_UNKNOWN",
                    "Change references unknown governed exceptions: "
                    + ", ".join(sorted(unknown_exceptions))
                    + ".",
                    path=f"{path}.exceptions",
                    source_id=source_id,
                )
            )

        high_risk = raw.get("risk_tier") in {"high", "critical"}
        approver_roles = {
            str(item) for item in (_as_list(raw.get("approver_roles")) or [])
        }
        if high_risk and (not approver_roles or not required_evidence):
            diagnostics.append(
                _diagnostic(
                    "CHANGE_HIGH_RISK_GATES_MISSING",
                    "High-risk changes require approver roles and evidence.",
                    path=path,
                    source_id=source_id,
                )
            )
        if high_risk and not ({change_id, f"change:{change_id}"} & duty_subjects):
            diagnostics.append(
                _diagnostic(
                    "CHANGE_SOD_ASSIGNMENT_MISSING",
                    "High-risk change lacks a separation-of-duties assignment.",
                    path=path,
                    source_id=source_id,
                )
            )

        binding = raw.get("revision_binding")
        expected_scope_hash = change_scope_hash(raw)
        if high_risk and not isinstance(binding, Mapping):
            diagnostics.append(
                _diagnostic(
                    "CHANGE_REVISION_BINDING_REQUIRED",
                    "High-risk change must bind approval to an exact revision and scope.",
                    path=f"{path}.revision_binding",
                    source_id=source_id,
                )
            )
        if isinstance(binding, Mapping) and binding.get("scope_hash") != expected_scope_hash:
            diagnostics.append(
                _diagnostic(
                    "CHANGE_SCOPE_HASH_MISMATCH",
                    "Change scope hash does not match its included and excluded scope.",
                    path=f"{path}.revision_binding.scope_hash",
                    source_id=source_id,
                )
            )

        invalidated_on = {
            str(item) for item in (_as_list(raw.get("approval_invalidated_on")) or [])
        }
        if high_risk and not {"revision_change", "scope_change"} <= invalidated_on:
            diagnostics.append(
                _diagnostic(
                    "CHANGE_APPROVAL_INVALIDATION_MISSING",
                    "High-risk change must invalidate approval after revision or scope changes.",
                    path=f"{path}.approval_invalidated_on",
                    source_id=source_id,
                )
            )

        if high_risk and isinstance(binding, Mapping):
            approval_ids = {str(item) for item in (_as_list(raw.get("approval_ids")) or [])}
            candidates = [
                approval
                for approval in approvals
                if approval.id in approval_ids
                or change_id in approval.actions_requiring_approval
                or f"change:{change_id}" in approval.actions_requiring_approval
            ]
            if not candidates:
                diagnostics.append(
                    _diagnostic(
                        "CHANGE_APPROVAL_MISSING",
                        "High-risk change has no matching human approval declaration.",
                        path=f"{path}.approval_ids",
                        source_id=source_id,
                    )
                )
            else:
                valid = False
                revision_mismatch = False
                scope_mismatch = False
                for approval in candidates:
                    approval_roles = set(approval.required_roles) | set(
                        approval.eligible_roles
                    )
                    if not approver_roles & approval_roles:
                        continue
                    approval_binding = approval.revision_binding
                    if not isinstance(approval_binding, Mapping):
                        revision_mismatch = scope_mismatch = True
                        continue
                    if approval_binding.get("revision") != binding.get("revision"):
                        revision_mismatch = True
                        continue
                    if approval_binding.get("scope_hash") != expected_scope_hash:
                        scope_mismatch = True
                        continue
                    valid = True
                    break
                if not valid:
                    if revision_mismatch:
                        diagnostics.append(
                            _diagnostic(
                                "APPROVAL_STALE_FOR_REVISION",
                                "Matching approval is absent or stale for the change revision.",
                                path=f"{path}.revision_binding.revision",
                                source_id=source_id,
                            )
                        )
                    if scope_mismatch:
                        diagnostics.append(
                            _diagnostic(
                                "APPROVAL_STALE_FOR_SCOPE",
                                "Matching approval is stale for the current change scope.",
                                path=f"{path}.revision_binding.scope_hash",
                                source_id=source_id,
                            )
                        )
                    if not revision_mismatch and not scope_mismatch:
                        diagnostics.append(
                            _diagnostic(
                                "CHANGE_APPROVAL_MISSING",
                                "Matching approval does not authorize a declared approver role.",
                                path=f"{path}.approver_roles",
                                source_id=source_id,
                            )
                        )

        if raw.get("reversibility") == "irreversible":
            authority = raw.get("irreversible_authority")
            if authority is None or authority not in approver_roles:
                diagnostics.append(
                    _diagnostic(
                        "CHANGE_IRREVERSIBLE_AUTHORITY_MISSING",
                        "Irreversible change requires explicit authority among approver roles.",
                        path=f"{path}.irreversible_authority",
                        source_id=source_id,
                    )
                )
            if raw.get("rollback_required") is not True:
                diagnostics.append(
                    _diagnostic(
                        "CHANGE_ROLLBACK_REQUIRED",
                        "Irreversible change must explicitly require rollback planning.",
                        path=f"{path}.rollback_required",
                        source_id=source_id,
                    )
                )
        if raw.get("rollback_required") is True and raw.get("rollback_plan_artifact") is None:
            diagnostics.append(
                _diagnostic(
                    "CHANGE_ROLLBACK_ARTIFACT_MISSING",
                    "Rollback-required change must identify a rollback plan artifact.",
                    path=f"{path}.rollback_plan_artifact",
                    source_id=source_id,
                )
            )

        impacts = raw.get("impacts")
        architecture_impact = (
            impacts.get("architecture") if isinstance(impacts, Mapping) else None
        )
        if architecture_impact in {"major", "critical"}:
            if "architecture_decision_record" not in required_evidence:
                diagnostics.append(
                    _diagnostic(
                        "CHANGE_ARCHITECTURE_EVIDENCE_MISSING",
                        "Major architecture impact requires architecture decision evidence.",
                        path=f"{path}.required_evidence",
                        source_id=source_id,
                    )
                )

        if status == "closed":
            closure = {str(item) for item in (_as_list(raw.get("closure_evidence")) or [])}
            if not closure or not closure <= evidence_ids:
                diagnostics.append(
                    _diagnostic(
                        "CHANGE_CLOSURE_EVIDENCE_MISSING",
                        "Closed change requires available closure evidence.",
                        path=f"{path}.closure_evidence",
                        source_id=source_id,
                    )
                )
    return tuple(diagnostics)


StructuralCheck = Callable[..., tuple[GovernanceDiagnostic, ...]]
STRUCTURAL_CHECKS: dict[str, StructuralCheck] = {
    "architecture_conformance.v1": architecture_conformance_check,
    "change_control.v1": _change_control,
    "evidence_integrity.v1": _evidence_integrity,
    "exception_management.v1": _exception_management,
    "human_approval.v1": _human_approval,
    "separation_of_duties.v1": _separation_of_duties,
}


def evaluate_structural_checks(
    document: Mapping[str, Any],
    composition: CompositionResult,
    *,
    as_of: str | datetime | None = None,
    document_root: str | Path | None = None,
) -> tuple[GovernanceDiagnostic, ...]:
    try:
        resolved_time = _parse_time(as_of)
    except ValueError:
        return (
            _diagnostic(
                "GOVERNANCE_TIME_INVALID",
                "Validation time must be an offset timestamp.",
                path="validation.as_of",
                source_id="nornyx.governance",
            ),
        )
    root = Path(document_root) if document_root is not None else None
    diagnostics: list[GovernanceDiagnostic] = []
    for check_id in sorted(composition.structural_checks):
        check = STRUCTURAL_CHECKS.get(check_id)
        if check is None:
            diagnostics.append(
                _diagnostic(
                    "GOVERNANCE_STRUCTURAL_CHECK_UNKNOWN",
                    f"Unknown structural check {check_id!r}.",
                    path="project.modules",
                    source_id=check_id,
                )
            )
            continue
        diagnostics.extend(
            check(
                document,
                composition,
                as_of=resolved_time,
                document_root=root,
            )
        )
    return tuple(diagnostics)
