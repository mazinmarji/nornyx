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
    is_non_human_authority,
    normalize_approval,
    trusted_normalized_approval,
)
from .errors import GovernanceError
from .loader import read_local_file_bytes
from .models import (
    CompositionResult,
    EffectiveApproval,
    GovernanceDiagnostic,
    NormalizedApproval,
)


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
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("timestamp must be a source string or datetime")
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _as_list(value: Any) -> list[Any] | None:
    return value if isinstance(value, list) else None


def _evidence_references(document: Mapping[str, Any]) -> set[str]:
    block = document.get("governance_evidence")
    records = _as_list(block.get("records")) if isinstance(block, Mapping) else []
    return {
        value
        for record in records or []
        if isinstance(record, Mapping)
        for value in (record.get("id"), record.get("type"))
        if isinstance(value, str) and value.strip() and value == value.strip()
    }


def _strict_source_strings(value: Any) -> tuple[tuple[str, ...], bool]:
    if not isinstance(value, list):
        return (), value is not None
    result: list[str] = []
    invalid = False
    for item in value:
        if (
            not isinstance(item, str)
            or not item.strip()
            or item != item.strip()
            or item in result
        ):
            invalid = True
            continue
        result.append(item)
    return tuple(result), invalid


def _governed_subject_revision(
    document: Mapping[str, Any],
    *,
    source_id: str,
) -> tuple[str | None, tuple[GovernanceDiagnostic, ...]]:
    """Resolve one subject revision from independent top-level anchors."""

    diagnostics: list[GovernanceDiagnostic] = []
    anchors: list[tuple[str, Any]] = []
    evidence = document.get("governance_evidence")
    if isinstance(evidence, Mapping) and "subject_revision" in evidence:
        anchors.append(
            ("governance_evidence.subject_revision", evidence["subject_revision"])
        )
    architecture = document.get("architecture")
    if isinstance(architecture, Mapping) and "subject_revision" in architecture:
        anchors.append(("architecture.subject_revision", architecture["subject_revision"]))

    valid_anchors: list[tuple[str, str]] = []
    for path, value in anchors:
        if (
            not isinstance(value, str)
            or not value.strip()
            or value != value.strip()
        ):
            diagnostics.append(
                _diagnostic(
                    "APPROVAL_GOVERNED_REVISION_INVALID",
                    "Governed subject revisions must be canonical non-empty source strings.",
                    path=path,
                    source_id=source_id,
                )
            )
        else:
            valid_anchors.append((path, value))
    if not valid_anchors:
        diagnostics.append(
            _diagnostic(
                "APPROVAL_GOVERNED_REVISION_MISSING",
                "Human approval requires an independent governed subject revision.",
                path="governance_evidence.subject_revision",
                source_id=source_id,
            )
        )
        return None, tuple(diagnostics)
    revisions = {value for _, value in valid_anchors}
    if len(revisions) != 1:
        diagnostics.append(
            _diagnostic(
                "APPROVAL_GOVERNED_REVISION_CONFLICT",
                "Independent governed subject-revision anchors conflict.",
                path=valid_anchors[-1][0],
                source_id=source_id,
            )
        )
        return None, tuple(diagnostics)
    governed = valid_anchors[0][1]

    claims: list[tuple[str, Any]] = []
    if isinstance(evidence, Mapping):
        records = _as_list(evidence.get("records")) or []
        claims.extend(
            (f"governance_evidence.records[{index}].subject_revision", raw.get("subject_revision"))
            for index, raw in enumerate(records)
            if isinstance(raw, Mapping)
        )
    changes = _as_list(document.get("changes")) or []
    for index, raw in enumerate(changes):
        binding = raw.get("revision_binding") if isinstance(raw, Mapping) else None
        if isinstance(binding, Mapping):
            claims.append(
                (f"changes[{index}].revision_binding.revision", binding.get("revision"))
            )
    architecture_evidence = _as_list(document.get("architecture_evidence")) or []
    claims.extend(
        (f"architecture_evidence[{index}].subject_revision", raw.get("subject_revision"))
        for index, raw in enumerate(architecture_evidence)
        if isinstance(raw, Mapping)
    )
    for path, value in claims:
        if value != governed:
            diagnostics.append(
                _diagnostic(
                    "APPROVAL_GOVERNED_REVISION_CONFLICT",
                    "A revision-bearing governance record conflicts with the governed subject.",
                    path=path,
                    source_id=source_id,
                )
            )
    return governed, tuple(diagnostics)


def change_scope_hash(change: Mapping[str, Any]) -> str:
    scope = change.get("scope")
    excluded_scope = change.get("excluded_scope")
    payload = {
        "scope": sorted(scope) if isinstance(scope, list) and all(
            isinstance(item, str) for item in scope
        ) else {"invalid": scope},
        "excluded_scope": sorted(excluded_scope) if isinstance(excluded_scope, list) and all(
            isinstance(item, str) for item in excluded_scope
        ) else {"invalid": excluded_scope},
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _normalize_document_approval(
    value: Any,
    index: int,
) -> NormalizedApproval | EffectiveApproval | None:
    if not isinstance(value, Mapping):
        return None
    schema = value.get("schema")
    if schema in {"nornyx.normalized_approval.v1", "nornyx.normalized_approval.v2"}:
        return trusted_normalized_approval(value, expected_path=f"approvals[{index}]")
    if schema == "nornyx.effective_approval.v1":
        # Effective approvals are reporting output. Authenticating their pack
        # lineage requires a registry, which document structural evaluation
        # deliberately does not infer from attacker-controlled content.
        return None
    if isinstance(schema, str) and schema.startswith(
        ("nornyx.normalized_approval.", "nornyx.effective_approval.")
    ):
        return None
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
    governed_revision, revision_diagnostics = _governed_subject_revision(
        document,
        source_id=source_id,
    )
    diagnostics.extend(revision_diagnostics)
    denied_required = set(CORE_DENIED_ACTOR_TYPES)
    evidence_references = _evidence_references(document)
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
            if normalized is not None:
                diagnostics.extend(
                    _diagnostic(
                        item.code,
                        item.message,
                        path=path,
                        source_id=source_id,
                        level=item.level,
                    )
                    for item in normalized.diagnostics
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
        missing_evidence = set(normalized.required_evidence) - evidence_references
        if missing_evidence:
            diagnostics.append(
                _diagnostic(
                    "APPROVAL_EVIDENCE_MISSING",
                    "Approval prerequisite evidence is missing: "
                    + ", ".join(sorted(missing_evidence))
                    + ".",
                    path=f"{path}.required_evidence",
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
        elif is_non_human_authority(normalized.accountable_authority):
            diagnostics.append(
                _diagnostic(
                    "APPROVAL_NON_HUMAN_AUTHORITY",
                    "Approval accountable authority must identify a human role or actor.",
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
        elif governed_revision is not None and binding.get("revision") != governed_revision:
            diagnostics.append(
                _diagnostic(
                    "APPROVAL_REVISION_MISMATCH",
                    "Approval revision does not match the governed subject revision.",
                    path=f"{path}.revision_binding.revision",
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
    try:
        raw, _ = read_local_file_bytes(
            relative,
            allowed_root=root,
            code_prefix="EVIDENCE",
            noun="Evidence artifact",
            max_bytes=16 * 1024 * 1024,
        )
        return "sha256:" + hashlib.sha256(raw).hexdigest()
    except GovernanceError:
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
        evidence_id_value = raw.get("id")
        evidence_id = (
            evidence_id_value
            if isinstance(evidence_id_value, str)
            and evidence_id_value.strip()
            and evidence_id_value == evidence_id_value.strip()
            else None
        )
        if evidence_id is None:
            diagnostics.append(
                _diagnostic(
                    "EVIDENCE_ID_INVALID",
                    "Evidence ids must be canonical non-empty source strings.",
                    path=f"{path}.id",
                    source_id=source_id,
                )
            )
        elif evidence_id in by_id:
            diagnostics.append(
                _diagnostic(
                    "EVIDENCE_DUPLICATE_ID",
                    f"Evidence id {evidence_id!r} is duplicated.",
                    path=f"{path}.id",
                    source_id=source_id,
                )
            )
        elif evidence_id is not None:
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
        artifact_value = raw.get("artifact")
        artifact = (
            artifact_value
            if isinstance(artifact_value, str)
            and artifact_value.strip()
            and artifact_value == artifact_value.strip()
            else None
        )
        claimed_hash_value = raw.get("content_hash")
        claimed_hash = (
            claimed_hash_value
            if isinstance(claimed_hash_value, str)
            and claimed_hash_value.strip()
            and claimed_hash_value == claimed_hash_value.strip()
            else None
        )
        if artifact is None or claimed_hash is None:
            diagnostics.append(
                _diagnostic(
                    "EVIDENCE_SOURCE_VALUE_INVALID",
                    "Evidence artifact and content hash must be canonical source strings.",
                    path=path,
                    source_id=source_id,
                )
            )
        elif artifact in by_artifact and by_artifact[artifact] != claimed_hash:
            diagnostics.append(
                _diagnostic(
                    "EVIDENCE_HASH_SUBSTITUTION",
                    "The same artifact is claimed with conflicting content hashes.",
                    path=f"{path}.content_hash",
                    source_id=source_id,
                )
            )
        if artifact is not None and claimed_hash is not None:
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
            observed_hash = (
                _artifact_hash(document_root, artifact)
                if artifact is not None
                else None
            )
            if observed_hash is None:
                diagnostics.append(
                    _diagnostic(
                        "EVIDENCE_ARTIFACT_UNAVAILABLE",
                        "Evidence artifact is missing, unreadable, outside the root, or symlinked.",
                        path=f"{path}.artifact",
                        source_id=source_id,
                    )
                )
            elif claimed_hash is None or observed_hash != claimed_hash:
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
                generated = _parse_time(raw.get("generated_at"))
                expires = _parse_time(raw.get("expires_at"))
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

    graph: dict[str, list[str]] = {}
    for evidence_id, record in sorted(by_id.items()):
        dependencies, dependencies_invalid = _strict_source_strings(
            record.get("dependencies")
        )
        if dependencies_invalid:
            diagnostics.append(
                _diagnostic(
                    "EVIDENCE_DEPENDENCY_INVALID",
                    "Evidence dependencies must be unique canonical source strings.",
                    path=f"governance_evidence.records.{evidence_id}.dependencies",
                    source_id=source_id,
                )
            )
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
        graph[evidence_id] = list(dependencies)
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

    available = set(by_id)
    available.update(
        value
        for record in by_id.values()
        if isinstance((value := record.get("type")), str)
        and value.strip()
        and value == value.strip()
    )
    module_requirements = (
        requirement
        for module in composition.modules
        for requirement in module.evidence_requirements
    )
    for requirement in module_requirements:
        if requirement.get("required") is True:
            required_id_value = requirement.get("id") or requirement.get("type")
            required_type_value = requirement.get("type")
            required_id = (
                required_id_value if isinstance(required_id_value, str) else ""
            )
            required_type = (
                required_type_value if isinstance(required_type_value, str) else ""
            )
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
        non_human_approvers = sorted(
            str(item) for item in approvers if is_non_human_authority(item)
        )
        if non_human_approvers:
            diagnostics.append(
                _diagnostic(
                    "SOD_NON_HUMAN_APPROVER",
                    "Separation-of-duties approvers must be human actors: "
                    + ", ".join(non_human_approvers)
                    + ".",
                    path=f"{path}.approvers",
                    source_id=source_id,
                )
            )
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
            if is_non_human_authority(approver):
                diagnostics.append(
                    _diagnostic(
                        "SOD_NON_HUMAN_APPROVER",
                        f"{approver_field} must identify a human actor.",
                        path=f"{path}.{approver_field}",
                        source_id=source_id,
                    )
                )
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
    evidence_references = _evidence_references(document)
    for index, raw in enumerate(entries):
        if not isinstance(raw, Mapping):
            continue
        path = f"exceptions.entries[{index}]"
        identifier_value = raw.get("id")
        identifier = (
            identifier_value
            if isinstance(identifier_value, str)
            and identifier_value.strip()
            and identifier_value == identifier_value.strip()
            else ""
        )
        if not identifier:
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_ID_INVALID",
                    "Exception ids must be canonical non-empty source strings.",
                    path=f"{path}.id",
                    source_id=source_id,
                )
            )
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
        control_value = raw.get("control")
        control = (
            control_value
            if isinstance(control_value, str)
            and control_value.strip()
            and control_value == control_value.strip()
            else ""
        )
        if not control:
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_CONTROL_INVALID",
                    "Exception controls must be canonical non-empty source strings.",
                    path=f"{path}.control",
                    source_id=source_id,
                )
            )
        if control.startswith("nornyx.core.") or control in CORE_NON_EXCEPTABLE_CONTROLS:
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_CORE_CONTROL_FORBIDDEN",
                    f"Core safety control {control!r} cannot be excepted.",
                    path=f"{path}.control",
                    source_id=source_id,
                )
            )
        for authority_field in (
            "requester",
            "approving_authority",
            "accountable_owner",
        ):
            authority = raw.get(authority_field)
            if (
                not isinstance(authority, str)
                or not authority.strip()
                or authority != authority.strip()
            ):
                diagnostics.append(
                    _diagnostic(
                        "EXCEPTION_AUTHORITY_INVALID",
                        "Exception authorities must be canonical non-empty source strings.",
                        path=f"{path}.{authority_field}",
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
        if is_non_human_authority(raw.get("approving_authority")):
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_NON_HUMAN_AUTHORITY",
                    "Exception approving authority must identify a human actor.",
                    path=f"{path}.approving_authority",
                    source_id=source_id,
                )
            )
        if is_non_human_authority(raw.get("accountable_owner")):
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_NON_HUMAN_AUTHORITY",
                    "Exception accountable owner must identify a human actor.",
                    path=f"{path}.accountable_owner",
                    source_id=source_id,
                )
            )
        declared_evidence_values, evidence_invalid = _strict_source_strings(
            raw.get("evidence")
        )
        declared_evidence = set(declared_evidence_values)
        if evidence_invalid:
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_EVIDENCE_INVALID",
                    "Exception evidence names must be unique canonical source strings.",
                    path=f"{path}.evidence",
                    source_id=source_id,
                )
            )
        missing_evidence = declared_evidence - evidence_references
        if missing_evidence:
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_EVIDENCE_MISSING",
                    "Exception evidence is missing: "
                    + ", ".join(sorted(missing_evidence))
                    + ".",
                    path=f"{path}.evidence",
                    source_id=source_id,
                )
            )
        if raw.get("status") == "closed":
            closure_evidence = {
                item
                for item in (_as_list(raw.get("closure_evidence")) or [])
                if isinstance(item, str)
            }
            if not closure_evidence or not closure_evidence <= evidence_references:
                diagnostics.append(
                    _diagnostic(
                        "EXCEPTION_CLOSURE_EVIDENCE_MISSING",
                        "A closed exception requires available closure evidence.",
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
            starts = _parse_time(raw.get("starts_at"))
            expires = _parse_time(raw.get("expires_at"))
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
        value
        for record in evidence_records
        if isinstance(record, Mapping)
        for value in (record.get("id"), record.get("type"))
        if isinstance(value, str) and value.strip() and value == value.strip()
    }
    exception_block = document.get("exceptions")
    exception_entries = (
        _as_list(exception_block.get("entries"))
        if isinstance(exception_block, Mapping)
        else []
    ) or []
    exception_ids = {
        value
        for item in exception_entries
        if isinstance(item, Mapping)
        if isinstance((value := item.get("id")), str)
        and value.strip()
        and value == value.strip()
    }
    duty_block = document.get("separation_of_duties")
    duty_assignments = (
        _as_list(duty_block.get("assignments"))
        if isinstance(duty_block, Mapping)
        else []
    ) or []
    duty_subjects = {
        value
        for item in duty_assignments
        if isinstance(item, Mapping)
        if isinstance((value := item.get("subject")), str)
        and value.strip()
        and value == value.strip()
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
        change_id_value = raw.get("id")
        change_id = (
            change_id_value
            if isinstance(change_id_value, str)
            and change_id_value.strip()
            and change_id_value == change_id_value.strip()
            else ""
        )
        if not change_id:
            diagnostics.append(
                _diagnostic(
                    "CHANGE_ID_INVALID",
                    "Change ids must be canonical non-empty source strings.",
                    path=f"{path}.id",
                    source_id=source_id,
                )
            )
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
            previous_value = transition.get("from")
            target_value = transition.get("to")
            previous = previous_value if isinstance(previous_value, str) else ""
            target = target_value if isinstance(target_value, str) else ""
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
                item
                for item in (_as_list(transition.get("evidence")) or [])
                if isinstance(item, str) and item.strip() and item == item.strip()
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
            item
            for item in (_as_list(raw.get("required_evidence")) or [])
            if isinstance(item, str) and item.strip() and item == item.strip()
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

        exception_refs = {
            item
            for item in (_as_list(raw.get("exceptions")) or [])
            if isinstance(item, str) and item.strip() and item == item.strip()
        }
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
        declared_roles, roles_invalid = _strict_source_strings(raw.get("approver_roles"))
        approver_roles = set(declared_roles)
        non_human_roles = {
            role for role in declared_roles if is_non_human_authority(role)
        }
        if high_risk and roles_invalid:
            diagnostics.append(
                _diagnostic(
                    "CHANGE_APPROVER_ROLE_INVALID",
                    "High-risk change approver roles must be unique canonical strings.",
                    path=f"{path}.approver_roles",
                    source_id=source_id,
                )
            )
        if high_risk and non_human_roles:
            diagnostics.append(
                _diagnostic(
                    "CHANGE_NON_HUMAN_APPROVER",
                    "High-risk change approvers must all be human roles.",
                    path=f"{path}.approver_roles",
                    source_id=source_id,
                )
            )
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
            item
            for item in (_as_list(raw.get("approval_invalidated_on")) or [])
            if isinstance(item, str) and item.strip() and item == item.strip()
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

        matching_approvals: list[NormalizedApproval | EffectiveApproval] = []
        if high_risk and isinstance(binding, Mapping):
            approval_ids = {
                item
                for item in (_as_list(raw.get("approval_ids")) or [])
                if isinstance(item, str) and item.strip() and item == item.strip()
            }
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
                roles_authorized_any = False
                for approval in candidates:
                    eligible_roles = set(approval.eligible_roles)
                    required_roles = set(approval.required_roles)
                    denied_roles = set(approval.denied_actor_types) | set(
                        approval.denied_execution_surfaces
                    )
                    roles_authorized = (
                        bool(approver_roles)
                        and not roles_invalid
                        and not non_human_roles
                        and approver_roles <= eligible_roles
                        and required_roles <= approver_roles
                        and not approver_roles & denied_roles
                    )
                    if not roles_authorized:
                        continue
                    roles_authorized_any = True
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
                    matching_approvals.append(approval)
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
                    if not roles_authorized_any:
                        diagnostics.append(
                            _diagnostic(
                                "CHANGE_APPROVER_ROLE_UNAUTHORIZED",
                                "Every declared approver role must be eligible, human, "
                                "non-denied, and include all required roles.",
                                path=f"{path}.approver_roles",
                                source_id=source_id,
                            )
                        )

        if raw.get("reversibility") == "irreversible":
            authority = raw.get("irreversible_authority")
            authority_is_string = (
                isinstance(authority, str)
                and bool(authority.strip())
                and authority == authority.strip()
            )
            authority_is_non_human = is_non_human_authority(authority)
            if authority_is_non_human:
                diagnostics.append(
                    _diagnostic(
                        "CHANGE_NON_HUMAN_AUTHORITY",
                        "Irreversible authority must identify an eligible human role.",
                        path=f"{path}.irreversible_authority",
                        source_id=source_id,
                    )
                )
            if not authority_is_string or authority not in approver_roles:
                diagnostics.append(
                    _diagnostic(
                        "CHANGE_IRREVERSIBLE_AUTHORITY_MISSING",
                        "Irreversible change requires explicit authority among approver roles.",
                        path=f"{path}.irreversible_authority",
                        source_id=source_id,
                    )
                )
            elif not authority_is_non_human:
                authority_candidates = [
                    approval
                    for approval in matching_approvals
                    if authority in set(approval.eligible_roles)
                    and authority not in set(approval.denied_actor_types)
                    and authority not in set(approval.denied_execution_surfaces)
                ] if high_risk and isinstance(binding, Mapping) else []
                if high_risk and not authority_candidates:
                    diagnostics.append(
                        _diagnostic(
                            "CHANGE_IRREVERSIBLE_AUTHORITY_UNAUTHORIZED",
                            "Irreversible authority is not eligible under a matching approval.",
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
            closure_values, closure_invalid = _strict_source_strings(
                raw.get("closure_evidence")
            )
            closure = set(closure_values)
            if closure_invalid:
                diagnostics.append(
                    _diagnostic(
                        "CHANGE_CLOSURE_EVIDENCE_INVALID",
                        "Closure evidence names must be unique canonical source strings.",
                        path=f"{path}.closure_evidence",
                        source_id=source_id,
                    )
                )
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
