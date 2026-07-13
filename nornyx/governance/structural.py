from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any, Callable

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


StructuralCheck = Callable[..., tuple[GovernanceDiagnostic, ...]]
STRUCTURAL_CHECKS: dict[str, StructuralCheck] = {
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
