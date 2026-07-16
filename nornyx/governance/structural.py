from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
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
CORE_NON_EXCEPTABLE_NAMESPACES = ("nornyx.builtin", "nornyx.core")
CORE_DIAGNOSTIC_PREFIXES = (
    "APPROVAL_",
    "ARCH_",
    "CHANGE_",
    "EVIDENCE_",
    "EXCEPTION_",
    "GOVERNANCE_",
    "LOCK_",
    "PACK_",
    "PATH_",
    "RULE_",
    "SCHEMA_",
    "SOD_",
)
CORE_NON_EXCEPTABLE_DIAGNOSTICS = frozenset(
    {
        "FILE_ATTRIBUTE_REPARSE_POINT",
        "PROFILE_PROJECTION_LOSS_REPORTED",
        "PROFILE_PROJECTION_REQUIRED_FIELD_OMITTED",
        "PROFILE_PROJECTION_UNSUPPORTED",
    }
)
APPROVAL_EVIDENCE_TYPE = "approval_record"
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
EXCEPTION_STATUSES = {
    "requested",
    "approved",
    "active",
    "expired",
    "closed",
    "rejected",
}
RISK_TIERS = {"low", "medium", "high", "critical"}
ARCHITECTURE_IMPACTS = {"none", "minor", "major", "critical"}


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
    try:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            raise ValueError("timestamp must be a source string or datetime")
        if parsed.tzinfo is None:
            raise ValueError("timestamp must include a UTC offset")
        return parsed.astimezone(timezone.utc)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError("timestamp is outside the supported UTC range") from exc


def _as_list(value: Any) -> list[Any] | None:
    return value if isinstance(value, list) else None


def _canonical_source_string(value: Any) -> str | None:
    if (
        isinstance(value, str)
        and value.strip()
        and value == value.strip()
    ):
        return value
    return None


def _is_core_non_exceptable_control(
    control: str,
    *,
    selected_builtin_controls: frozenset[str] = frozenset(),
) -> bool:
    source_candidate = (
        control[len("control:") :]
        if control.casefold().startswith("control:")
        else control
    )
    candidate = source_candidate.casefold()
    if candidate in CORE_NON_EXCEPTABLE_CONTROLS:
        return True
    if candidate in selected_builtin_controls:
        return True
    if any(
        candidate == namespace
        or candidate.startswith(f"{namespace}.")
        or candidate.startswith(f"{namespace}:")
        or candidate.startswith(f"{namespace}/")
        for namespace in CORE_NON_EXCEPTABLE_NAMESPACES
    ):
        return True
    return (
        source_candidate in CORE_NON_EXCEPTABLE_DIAGNOSTICS
        or source_candidate.startswith(CORE_DIAGNOSTIC_PREFIXES)
    )


def _selected_builtin_control_ids(
    composition: CompositionResult,
) -> frozenset[str]:
    controls: set[str] = set()
    for module in composition.modules:
        if module.provenance.source_tier != "builtin":
            continue
        controls.update({module.id, module.name, *module.structural_checks})
        controls.update(rule.id for rule in module.rules)
        controls.update(rule.namespaced_id for rule in module.rules)
        for collection in (
            module.policies,
            module.evidence_requirements,
            module.approval_requirements,
            module.evaluations,
        ):
            for item in collection:
                for field in ("id", "name"):
                    value = _source_identity(item.get(field))
                    if value is not None:
                        controls.add(value)
        for evaluation in module.evaluations:
            controls.update(
                metric
                for metric in (_as_list(evaluation.get("metrics")) or [])
                if _source_identity(metric) is not None
            )
    return frozenset(control.casefold() for control in controls)


def _usable_evidence_records(
    document: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    """Return uniquely identified passing records with passing dependency chains."""

    block = document.get("governance_evidence")
    records = _as_list(block.get("records")) if isinstance(block, Mapping) else []
    by_id: dict[str, Mapping[str, Any]] = {}
    duplicate_ids: set[str] = set()
    for record in records or []:
        if not isinstance(record, Mapping):
            continue
        identifier = _canonical_source_string(record.get("id"))
        if identifier is None:
            continue
        if identifier in by_id:
            duplicate_ids.add(identifier)
        else:
            by_id[identifier] = record
    for identifier in duplicate_ids:
        by_id.pop(identifier, None)

    dependencies_by_id: dict[str, tuple[str, ...]] = {}
    dependents: dict[str, set[str]] = {identifier: set() for identifier in by_id}
    for identifier, record in by_id.items():
        dependencies, invalid = _strict_source_strings(record.get("dependencies"))
        if (
            record.get("status") != "pass"
            or invalid
            or any(dependency not in by_id for dependency in dependencies)
        ):
            continue
        dependencies_by_id[identifier] = dependencies
        for dependency in dependencies:
            dependents[dependency].add(identifier)

    usable: set[str] = set()
    queued = {
        identifier
        for identifier, dependencies in dependencies_by_id.items()
        if not dependencies
    }
    pending = sorted(queued, reverse=True)
    while pending:
        identifier = pending.pop()
        usable.add(identifier)
        for dependent in sorted(dependents[identifier]):
            dependencies = dependencies_by_id.get(dependent)
            if (
                dependencies is not None
                and dependent not in usable
                and dependent not in queued
                and set(dependencies) <= usable
            ):
                queued.add(dependent)
                pending.append(dependent)
        pending.sort(reverse=True)

    return tuple(by_id[identifier] for identifier in sorted(usable))


def _evidence_references(document: Mapping[str, Any]) -> set[str]:
    return {
        value
        for record in _usable_evidence_records(document)
        for value in (record.get("id"), record.get("type"))
        if _canonical_source_string(value) is not None
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


_SOURCE_IDENTITY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]*$")
_HUMAN_ACTOR_PREFIXES = frozenset({"human", "person", "user"})


def _source_identity(value: Any) -> str | None:
    source = _canonical_source_string(value)
    if source is None or len(source) > 128 or _SOURCE_IDENTITY_RE.fullmatch(source) is None:
        return None
    return source


def _human_actor_role(value: Any) -> str | None:
    actor = _source_identity(value)
    if actor is None or is_non_human_authority(actor):
        return None
    if ":" not in actor:
        return actor
    prefix, role = actor.split(":", 1)
    if prefix.casefold() not in _HUMAN_ACTOR_PREFIXES or not role or ":" in role:
        return None
    return role


def _actor_equivalence_key(value: Any) -> tuple[str, str] | None:
    actor = _source_identity(value)
    if actor is None:
        return None
    role = _human_actor_role(actor)
    if role is not None:
        return ("human_role", role.casefold())
    return ("actor", actor.casefold())


def _producer_actor_aliases(record: Mapping[str, Any]) -> set[str]:
    aliases: set[str] = set()
    producer = record.get("producer")
    if not isinstance(producer, Mapping):
        return aliases
    producer_id = _source_identity(producer.get("id"))
    producer_type = _source_identity(producer.get("type"))
    if producer_id is None or producer_type is None:
        return aliases
    aliases.add(producer_id)
    kind = producer_type.casefold()
    aliases.add(f"{kind}:{producer_id}")
    if kind == "human":
        human_id = producer_id
        if human_id.casefold().startswith("human."):
            human_id = human_id.split(".", 1)[1]
        aliases.add(f"user:{human_id}")
    if kind == "tool":
        tool = record.get("tool")
        tool_name = (
            _source_identity(tool.get("name"))
            if isinstance(tool, Mapping)
            else None
        )
        if tool_name is not None:
            aliases.update({tool_name, f"tool:{tool_name}"})
    return aliases


def _evidence_component_resolver(
    document: Mapping[str, Any],
) -> Callable[[set[str]], tuple[Mapping[str, Any], ...]]:
    records = _usable_evidence_records(document)
    by_id = {
        identifier: record
        for record in records
        if (identifier := _source_identity(record.get("id"))) is not None
    }
    graph: dict[str, set[str]] = {identifier: set() for identifier in by_id}
    for identifier, record in by_id.items():
        dependencies, invalid = _strict_source_strings(record.get("dependencies"))
        if invalid:
            continue
        for dependency in dependencies:
            if dependency in graph:
                graph[identifier].add(dependency)
                graph[dependency].add(identifier)
    component_by_id: dict[str, frozenset[str]] = {}
    remaining = set(by_id)
    while remaining:
        start = min(remaining)
        connected: set[str] = set()
        pending = [start]
        while pending:
            identifier = pending.pop()
            if identifier in connected:
                continue
            connected.add(identifier)
            pending.extend(sorted(graph[identifier] - connected, reverse=True))
        component = frozenset(connected)
        for identifier in component:
            component_by_id[identifier] = component
        remaining -= component

    identifiers_by_reference: dict[str, set[str]] = {}
    for identifier, record in by_id.items():
        identifiers_by_reference.setdefault(identifier, set()).add(identifier)
        evidence_type = _source_identity(record.get("type"))
        if evidence_type is not None:
            identifiers_by_reference.setdefault(evidence_type, set()).add(identifier)

    cache: dict[frozenset[str], tuple[Mapping[str, Any], ...]] = {}

    def resolve(references: set[str]) -> tuple[Mapping[str, Any], ...]:
        if not references:
            return records
        key = frozenset(references)
        if key not in cache:
            connected: set[str] = set()
            for reference in sorted(references):
                for identifier in identifiers_by_reference.get(reference, set()):
                    connected.update(component_by_id[identifier])
            cache[key] = tuple(
                by_id[identifier] for identifier in sorted(connected)
            )
        return cache[key]

    return resolve


def _evidence_component(
    document: Mapping[str, Any],
    references: set[str],
) -> tuple[Mapping[str, Any], ...]:
    return _evidence_component_resolver(document)(references)


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
    if "schema" in value and not isinstance(schema, str):
        return None
    if isinstance(schema, str) and schema in {
        "nornyx.normalized_approval.v1",
        "nornyx.normalized_approval.v2",
    }:
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
            elif (
                record.get("status") == "pass"
                and by_id[dependency].get("status") != "pass"
            ):
                diagnostics.append(
                    _diagnostic(
                        "EVIDENCE_DEPENDENCY_UNSATISFIED",
                        f"Passing evidence depends on non-passing evidence {dependency!r}.",
                        path=f"governance_evidence.records.{evidence_id}.dependencies",
                        source_id=source_id,
                    )
                )
        graph[evidence_id] = list(dependencies)
    dependency_counts = {
        evidence_id: sum(dependency in graph for dependency in dependencies)
        for evidence_id, dependencies in graph.items()
    }
    graph_dependents: dict[str, set[str]] = {
        evidence_id: set() for evidence_id in graph
    }
    for evidence_id, dependencies in graph.items():
        for dependency in dependencies:
            if dependency in graph_dependents:
                graph_dependents[dependency].add(evidence_id)
    pending = sorted(
        (
            evidence_id
            for evidence_id, count in dependency_counts.items()
            if count == 0
        ),
        reverse=True,
    )
    visited_count = 0
    while pending:
        evidence_id = pending.pop()
        visited_count += 1
        for dependent in sorted(graph_dependents[evidence_id]):
            dependency_counts[dependent] -= 1
            if dependency_counts[dependent] == 0:
                pending.append(dependent)
        pending.sort(reverse=True)

    if visited_count != len(graph):
        diagnostics.append(
            _diagnostic(
                "EVIDENCE_DEPENDENCY_CYCLE",
                "Evidence dependencies contain a cycle.",
                path="governance_evidence.records",
                source_id=source_id,
            )
        )

    available = _evidence_references(document)
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
        return (
            _diagnostic(
                "SOD_ASSIGNMENT_INVALID",
                "Separation-of-duties assignments must be a source array.",
                path="separation_of_duties.assignments",
                source_id=source_id,
            ),
        )
    if not assignments:
        return (
            _diagnostic(
                "SOD_ASSIGNMENT_REQUIRED",
                "At least one separation-of-duties assignment is required.",
                path="separation_of_duties.assignments",
                source_id=source_id,
            ),
        )

    changes = _as_list(document.get("changes"))
    changes_by_subject: dict[str, list[Mapping[str, Any]]] = {}
    for change in changes or []:
        if not isinstance(change, Mapping):
            continue
        change_id = _source_identity(change.get("id"))
        if change_id is None:
            continue
        changes_by_subject.setdefault(change_id, []).append(change)
        changes_by_subject.setdefault(f"change:{change_id}", []).append(change)

    approval_values = _as_list(document.get("approvals")) or []
    approvals = [
        approval
        for approval_index, value in enumerate(approval_values)
        if (
            approval := _normalize_document_approval(value, approval_index)
        ) is not None
        and approval.resolution == "complete"
    ]
    resolve_evidence_component = _evidence_component_resolver(document)
    evidence_context_cache: dict[
        tuple[frozenset[str], frozenset[str]],
        tuple[set[str], set[tuple[str, str]]],
    ] = {}

    diagnostics: list[GovernanceDiagnostic] = []
    resolved_subjects: set[str] = set()
    for index, raw in enumerate(assignments):
        if not isinstance(raw, Mapping):
            diagnostics.append(
                _diagnostic(
                    "SOD_ASSIGNMENT_INVALID",
                    "Each separation-of-duties assignment must be an object.",
                    path=f"separation_of_duties.assignments[{index}]",
                    source_id=source_id,
                )
            )
            continue
        path = f"separation_of_duties.assignments[{index}]"
        subject = _source_identity(raw.get("subject"))
        if subject is None:
            diagnostics.append(
                _diagnostic(
                    "SOD_SUBJECT_INVALID",
                    "Assignment subjects must be canonical source identities.",
                    path=f"{path}.subject",
                    source_id=source_id,
                )
            )

        author = _source_identity(raw.get("author"))
        author_role = _human_actor_role(author)
        if author is None or author_role is None:
            diagnostics.append(
                _diagnostic(
                    "SOD_AUTHOR_INVALID",
                    "The assignment author must be a canonical human identity.",
                    path=f"{path}.author",
                    source_id=source_id,
                )
            )

        approver_values, approvers_invalid = _strict_source_strings(
            raw.get("approvers")
        )
        approvers = tuple(
            value for value in approver_values if _source_identity(value) is not None
        )
        approver_roles = tuple(
            role
            for value in approvers
            if (role := _human_actor_role(value)) is not None
        )
        if not approver_values and not approvers_invalid:
            diagnostics.append(
                _diagnostic(
                    "SOD_APPROVER_REQUIRED",
                    "A separation-of-duties assignment requires at least one approver.",
                    path=f"{path}.approvers",
                    source_id=source_id,
                )
            )
        if (
            approvers_invalid
            or len(approvers) != len(approver_values)
            or len(set(role.casefold() for role in approver_roles)) != len(approver_roles)
        ):
            diagnostics.append(
                _diagnostic(
                    "SOD_APPROVER_INVALID",
                    "Approvers must be unique canonical human source identities.",
                    path=f"{path}.approvers",
                    source_id=source_id,
                )
            )
        non_human_approvers = sorted(
            item
            for item in approvers
            if is_non_human_authority(item) or _human_actor_role(item) is None
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
        author_key = _actor_equivalence_key(author)
        approver_keys = {
            key
            for value in approvers
            if (key := _actor_equivalence_key(value)) is not None
        }
        if (
            isinstance(raw.get("risk_tier"), str)
            and raw.get("risk_tier") in {"high", "critical"}
            and author_key is not None
            and author_key in approver_keys
        ):
            diagnostics.append(
                _diagnostic(
                    "SOD_SELF_APPROVAL",
                    "The author cannot approve their own high-risk change.",
                    path=path,
                    source_id=source_id,
                )
            )

        producer_values, producers_invalid = _strict_source_strings(
            raw.get("evidence_producers")
        )
        producers = tuple(
            value for value in producer_values if _source_identity(value) is not None
        )
        if producers_invalid or len(producers) != len(producer_values):
            diagnostics.append(
                _diagnostic(
                    "SOD_EVIDENCE_PRODUCER_INVALID",
                    "Evidence producers must be unique canonical source identities.",
                    path=f"{path}.evidence_producers",
                    source_id=source_id,
                )
            )
        if raw.get("require_evidence_independence") is True and not producer_values:
            diagnostics.append(
                _diagnostic(
                    "SOD_EVIDENCE_PRODUCER_REQUIRED",
                    "Evidence independence requires at least one declared producer.",
                    path=f"{path}.evidence_producers",
                    source_id=source_id,
                )
            )
        producer_keys = {
            key
            for value in producers
            if (key := _actor_equivalence_key(value)) is not None
        }
        if (
            raw.get("require_evidence_independence") is True
            and approver_keys & producer_keys
        ):
            diagnostics.append(
                _diagnostic(
                    "SOD_EVIDENCE_PRODUCER_SOLE_APPROVER",
                    "Approvers and evidence producers must be disjoint when independence is required.",
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
            if approver is not None and _human_actor_role(approver) is None:
                diagnostics.append(
                    _diagnostic(
                        "SOD_NON_HUMAN_APPROVER",
                        f"{approver_field} must identify a human actor.",
                        path=f"{path}.{approver_field}",
                        source_id=source_id,
                    )
                )
            requester_key = _actor_equivalence_key(requester)
            approver_key = _actor_equivalence_key(approver)
            if (
                requester_key is not None
                and approver_key is not None
                and requester_key == approver_key
            ):
                diagnostics.append(
                    _diagnostic(
                        code,
                        f"{requester_field} and {approver_field} must be disjoint.",
                        path=path,
                        source_id=source_id,
                    )
                )

        if subject is None:
            continue
        if changes is None:
            diagnostics.append(
                _diagnostic(
                    "SOD_SUBJECT_UNKNOWN",
                    "A separation assignment requires a corresponding governed change.",
                    path=f"{path}.subject",
                    source_id=source_id,
                )
            )
            continue
        matching_changes = changes_by_subject.get(subject, [])
        if len(matching_changes) != 1:
            diagnostics.append(
                _diagnostic(
                    "SOD_SUBJECT_UNKNOWN",
                    "Assignment subject must resolve to exactly one governed change.",
                    path=f"{path}.subject",
                    source_id=source_id,
                )
            )
            continue
        change = matching_changes[0]
        change_id = _source_identity(change.get("id"))
        if change_id is not None:
            if change_id in resolved_subjects:
                diagnostics.append(
                    _diagnostic(
                        "SOD_DUPLICATE_SUBJECT",
                        f"Separation assignment for change {change_id!r} is duplicated.",
                        path=f"{path}.subject",
                        source_id=source_id,
                    )
                )
            resolved_subjects.add(change_id)
        if raw.get("risk_tier") != change.get("risk_tier"):
            diagnostics.append(
                _diagnostic(
                    "SOD_RISK_TIER_MISMATCH",
                    "Assignment and governed change must declare the same risk tier.",
                    path=f"{path}.risk_tier",
                    source_id=source_id,
                )
            )

        duty = change.get("separation_of_duties")
        expected_author_role = (
            _human_actor_role(duty.get("author_role"))
            if isinstance(duty, Mapping)
            else None
        )
        expected_inline_approver = (
            _human_actor_role(duty.get("approver_role"))
            if isinstance(duty, Mapping)
            else None
        )
        if author_role is None or author_role != expected_author_role:
            diagnostics.append(
                _diagnostic(
                    "SOD_AUTHOR_ROLE_MISMATCH",
                    "Assignment author does not match the change author role.",
                    path=f"{path}.author",
                    source_id=source_id,
                )
            )
        change_role_values, change_roles_invalid = _strict_source_strings(
            change.get("approver_roles")
        )
        change_roles = {
            role
            for value in change_role_values
            if (role := _human_actor_role(value)) is not None
        }
        assigned_roles = set(approver_roles)
        if (
            change_roles_invalid
            or assigned_roles != change_roles
            or expected_inline_approver is None
            or expected_inline_approver not in assigned_roles
        ):
            diagnostics.append(
                _diagnostic(
                    "SOD_APPROVER_ROLE_MISMATCH",
                    "Assignment approvers must exactly implement the change approver roles.",
                    path=f"{path}.approvers",
                    source_id=source_id,
                )
            )

        approval_ids, approval_ids_invalid = _strict_source_strings(
            change.get("approval_ids")
        )
        action_ids = {
            value for value in (change_id, f"change:{change_id}") if value is not None
        }
        candidates = [
            approval
            for approval in approvals
            if approval.id in set(approval_ids)
            or action_ids & set(approval.actions_requiring_approval)
        ]
        linked_ids_valid = all(
            sum(approval.id == approval_id for approval in approvals) == 1
            for approval_id in approval_ids
        )
        gate_valid = (
            not approval_ids_invalid
            and linked_ids_valid
            and bool(candidates)
        )
        if candidates:
            eligible_roles = set(candidates[0].eligible_roles)
            for approval in candidates[1:]:
                eligible_roles &= set(approval.eligible_roles)
            required_roles = {
                role for approval in candidates for role in approval.required_roles
            }
            denied_roles = {
                role
                for approval in candidates
                for role in (
                    *approval.denied_actor_types,
                    *approval.denied_execution_surfaces,
                )
            }
            gate_valid = gate_valid and (
                bool(eligible_roles)
                and assigned_roles <= eligible_roles
                and required_roles <= assigned_roles
                and not assigned_roles & denied_roles
            )
        if not gate_valid:
            diagnostics.append(
                _diagnostic(
                    "SOD_APPROVAL_GATE_MISMATCH",
                    "Assignment approvers do not satisfy every linked approval gate.",
                    path=f"{path}.approvers",
                    source_id=source_id,
                )
            )

        change_evidence_refs = {
            value
            for field in ("required_evidence", "closure_evidence")
            for value in (_as_list(change.get(field)) or [])
            if _source_identity(value) is not None
        }
        transition = change.get("transition")
        if isinstance(transition, Mapping):
            change_evidence_refs.update(
                value
                for value in (_as_list(transition.get("evidence")) or [])
                if _source_identity(value) is not None
            )
        approval_evidence_refs = {
            value
            for approval in candidates
            for value in approval.required_evidence
        }
        evidence_refs = change_evidence_refs | approval_evidence_refs
        evidence_key = (
            frozenset(change_evidence_refs),
            frozenset(approval_evidence_refs),
        )
        if evidence_key not in evidence_context_cache:
            relevant_records = resolve_evidence_component(evidence_refs)
            producer_aliases = {
                alias
                for record in relevant_records
                for alias in _producer_actor_aliases(record)
            }
            actual_producer_keys = {
                key
                for record in relevant_records
                if not (
                    record.get("type") == APPROVAL_EVIDENCE_TYPE
                    and record.get("id") in approval_evidence_refs
                    and record.get("id") not in change_evidence_refs
                    and record.get("type") not in change_evidence_refs
                )
                for alias in _producer_actor_aliases(record)
                if (key := _actor_equivalence_key(alias)) is not None
            }
            evidence_context_cache[evidence_key] = (
                producer_aliases,
                actual_producer_keys,
            )
        producer_aliases, actual_producer_keys = evidence_context_cache[evidence_key]
        unknown_producers = set(producers) - producer_aliases
        if unknown_producers:
            diagnostics.append(
                _diagnostic(
                    "SOD_EVIDENCE_PRODUCER_UNKNOWN",
                    "Assignment evidence producers are not linked to the change evidence: "
                    + ", ".join(sorted(unknown_producers))
                    + ".",
                    path=f"{path}.evidence_producers",
                    source_id=source_id,
                )
            )
        if (
            raw.get("require_evidence_independence") is True
            and approver_keys & actual_producer_keys
            and not approver_keys & producer_keys
        ):
            diagnostics.append(
                _diagnostic(
                    "SOD_EVIDENCE_PRODUCER_SOLE_APPROVER",
                    "A linked evidence producer is also an approver despite required independence.",
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
    del document_root
    source_id = "exception_management.v1"
    block = document.get("exceptions")
    if not isinstance(block, Mapping):
        return ()
    entries = _as_list(block.get("entries"))
    if entries is None:
        return ()
    diagnostics: list[GovernanceDiagnostic] = []
    selected_builtin_controls = _selected_builtin_control_ids(composition)
    evidence_references = _evidence_references(document)
    usable_evidence_records = _usable_evidence_records(document)
    usable_evidence_by_id = {
        identifier: record
        for record in usable_evidence_records
        if (identifier := _source_identity(record.get("id"))) is not None
    }
    usable_ids_by_type: dict[str, set[str]] = {}
    artifact_counts: dict[str, int] = {}
    content_hash_counts: dict[str, int] = {}
    for identifier, record in usable_evidence_by_id.items():
        evidence_type = _source_identity(record.get("type"))
        if evidence_type is not None:
            usable_ids_by_type.setdefault(evidence_type, set()).add(identifier)
        for value, counts in (
            (_canonical_source_string(record.get("artifact")), artifact_counts),
            (_canonical_source_string(record.get("content_hash")), content_hash_counts),
        ):
            if value is not None:
                counts[value] = counts.get(value, 0) + 1
    approval_values = _as_list(document.get("approvals")) or []
    document_approvals = [
        approval
        for approval_index, value in enumerate(approval_values)
        if (
            approval := _normalize_document_approval(value, approval_index)
        ) is not None
        and approval.resolution == "complete"
    ]
    identifier_counts: dict[str, int] = {}
    parsed_entries: list[dict[str, Any]] = []
    for index, raw in enumerate(entries):
        if not isinstance(raw, Mapping):
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_ENTRY_INVALID",
                    "Each governed exception must be an object.",
                    path=f"exceptions.entries[{index}]",
                    source_id=source_id,
                )
            )
            continue
        path = f"exceptions.entries[{index}]"
        identifier = _source_identity(raw.get("id"))
        if identifier is None:
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_ID_INVALID",
                    "Exception ids must be canonical non-empty source strings.",
                    path=f"{path}.id",
                    source_id=source_id,
                )
            )
        else:
            identifier_counts[identifier] = identifier_counts.get(identifier, 0) + 1
            if identifier_counts[identifier] > 1:
                diagnostics.append(
                    _diagnostic(
                        "EXCEPTION_DUPLICATE_ID",
                        f"Exception id {identifier!r} is duplicated.",
                        path=f"{path}.id",
                        source_id=source_id,
                    )
                )

        control = _source_identity(raw.get("control"))
        if control is None:
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_CONTROL_INVALID",
                    "Exception controls must be canonical non-empty source strings.",
                    path=f"{path}.control",
                    source_id=source_id,
                )
            )
        elif _is_core_non_exceptable_control(
            control,
            selected_builtin_controls=selected_builtin_controls,
        ):
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_CORE_CONTROL_FORBIDDEN",
                    f"Core safety control {control!r} cannot be excepted.",
                    path=f"{path}.control",
                    source_id=source_id,
                )
            )

        scope_values, scope_invalid = _strict_source_strings(raw.get("scope"))
        scope = frozenset(
            value for value in scope_values if _source_identity(value) is not None
        )
        if scope_invalid or len(scope) != len(scope_values) or not scope:
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_SCOPE_INVALID",
                    "Exception scope must contain unique canonical source identities.",
                    path=f"{path}.scope",
                    source_id=source_id,
                )
            )

        authorities: dict[str, str | None] = {}
        for authority_field in (
            "requester",
            "approving_authority",
            "accountable_owner",
        ):
            authority = _source_identity(raw.get(authority_field))
            authorities[authority_field] = authority
            if authority is None:
                diagnostics.append(
                    _diagnostic(
                        "EXCEPTION_AUTHORITY_INVALID",
                        "Exception authorities must be canonical non-empty source strings.",
                        path=f"{path}.{authority_field}",
                        source_id=source_id,
                    )
                )
            elif _human_actor_role(authority) is None:
                diagnostics.append(
                    _diagnostic(
                        "EXCEPTION_NON_HUMAN_AUTHORITY",
                        f"Exception {authority_field} must identify a human actor.",
                        path=f"{path}.{authority_field}",
                        source_id=source_id,
                    )
                )
        requester_key = _actor_equivalence_key(authorities["requester"])
        approver_key = _actor_equivalence_key(authorities["approving_authority"])
        if (
            requester_key is not None
            and approver_key is not None
            and requester_key == approver_key
        ):
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_SELF_APPROVAL",
                    "Exception requester and approving authority must be disjoint.",
                    path=path,
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

        closure_values, closure_invalid = _strict_source_strings(
            raw.get("closure_evidence")
        )
        closure_evidence = set(closure_values)
        if closure_invalid:
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_CLOSURE_EVIDENCE_INVALID",
                    "Closure evidence must contain unique canonical source identities.",
                    path=f"{path}.closure_evidence",
                    source_id=source_id,
                )
            )

        starts: datetime | None = None
        expires: datetime | None = None
        interval_valid = False
        try:
            starts = _parse_time(raw.get("starts_at"))
            expires = _parse_time(raw.get("expires_at"))
            if starts is None or expires is None:
                raise ValueError("missing timestamp")
            interval_valid = starts < expires
            if not interval_valid:
                diagnostics.append(
                    _diagnostic(
                        "EXCEPTION_INTERVAL_INVALID",
                        "Exception expiry must be after its start time.",
                        path=path,
                        source_id=source_id,
                    )
                )
        except (TypeError, ValueError):
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_TIME_INVALID",
                    "Exception timestamps must be valid offset timestamps.",
                    path=path,
                    source_id=source_id,
                )
            )

        status_value = raw.get("status")
        status = (
            status_value
            if isinstance(status_value, str)
            and status_value in EXCEPTION_STATUSES
            else None
        )
        if status is None:
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_LIFECYCLE_INVALID",
                    "Exception status must be a supported lifecycle value.",
                    path=f"{path}.status",
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
        elif interval_valid and starts is not None and expires is not None:
            if status == "active" and as_of < starts:
                diagnostics.append(
                    _diagnostic(
                        "EXCEPTION_LIFECYCLE_INVALID",
                        "An active exception cannot precede its declared start.",
                        path=f"{path}.status",
                        source_id=source_id,
                    )
                )
            if status in {"approved", "active"} and expires <= as_of:
                diagnostics.append(
                    _diagnostic(
                        "EXCEPTION_EXPIRED",
                        "Approved or active exception has expired.",
                        path=f"{path}.expires_at",
                        source_id=source_id,
                    )
                )
            if status == "expired" and as_of < expires:
                diagnostics.append(
                    _diagnostic(
                        "EXCEPTION_LIFECYCLE_INVALID",
                        "An exception cannot be declared expired before its expiry.",
                        path=f"{path}.status",
                        source_id=source_id,
                    )
                )

        closure_required = status in {"closed", "expired"} or (
            status in {"approved", "active"}
            and as_of is not None
            and expires is not None
            and expires <= as_of
        )
        if closure_required and (
            closure_invalid
            or not closure_evidence
            or not closure_evidence <= evidence_references
        ):
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_CLOSURE_EVIDENCE_MISSING",
                    "Closed or expired exceptions require available closure evidence.",
                    path=f"{path}.closure_evidence",
                    source_id=source_id,
                )
            )

        parsed_entries.append(
            {
                "index": index,
                "path": path,
                "raw": raw,
                "id": identifier,
                "control": control,
                "scope": scope,
                "status": status,
                "starts": starts,
                "expires": expires,
                "interval_valid": interval_valid,
                "evidence": declared_evidence,
            }
        )

    unique_by_id = {
        entry["id"]: entry
        for entry in parsed_entries
        if entry["id"] is not None and identifier_counts.get(entry["id"]) == 1
    }

    renewal_evidence_usage: dict[str, int] = {}
    for entry in parsed_entries:
        renewal_values, _ = _strict_source_strings(
            entry["raw"].get("renewal_approval_evidence")
        )
        for reference in renewal_values:
            renewal_evidence_usage[reference] = (
                renewal_evidence_usage.get(reference, 0) + 1
            )

    def evidence_dependency_closure(references: set[str]) -> set[str]:
        pending: list[str] = []
        for reference in sorted(references, reverse=True):
            if reference in usable_evidence_by_id:
                pending.append(reference)
            else:
                pending.extend(sorted(usable_ids_by_type.get(reference, ()), reverse=True))
        resolved: set[str] = set()
        while pending:
            identifier = pending.pop()
            if identifier in resolved:
                continue
            resolved.add(identifier)
            record = usable_evidence_by_id[identifier]
            dependencies, invalid = _strict_source_strings(
                record.get("dependencies")
            )
            if not invalid:
                pending.extend(
                    dependency
                    for dependency in reversed(dependencies)
                    if dependency in usable_evidence_by_id
                )
        return resolved

    def ancestor_evidence_ids(prior_id: str) -> set[str]:
        references: set[str] = set()
        visited: set[str] = set()
        current: str | None = prior_id
        while current is not None and current not in visited:
            visited.add(current)
            ancestor = unique_by_id.get(current)
            if ancestor is None:
                break
            ancestor_raw = ancestor["raw"]
            references.update(
                value
                for field in (
                    "evidence",
                    "closure_evidence",
                    "renewal_approval_evidence",
                )
                for value in (_as_list(ancestor_raw.get(field)) or [])
                if _source_identity(value) is not None
            )
            renews = _source_identity(ancestor_raw.get("renews"))
            current = renews if renews in unique_by_id else None
        return evidence_dependency_closure(references)

    def is_human_approval_record(
        record: Mapping[str, Any] | None,
        authority_key: tuple[str, str] | None,
        *,
        approval_not_before: datetime | None,
        approval_not_after: datetime | None,
    ) -> bool:
        if (
            record is None
            or authority_key is None
            or approval_not_before is None
            or approval_not_after is None
        ):
            return False
        evidence_type = _source_identity(record.get("type"))
        producer = record.get("producer")
        artifact = _canonical_source_string(record.get("artifact"))
        content_hash = _canonical_source_string(record.get("content_hash"))
        try:
            generated = _parse_time(record.get("generated_at"))
        except ValueError:
            generated = None
        return (
            evidence_type == APPROVAL_EVIDENCE_TYPE
            and isinstance(producer, Mapping)
            and producer.get("type") == "human"
            and generated is not None
            and approval_not_before <= generated <= approval_not_after
            and artifact is not None
            and artifact_counts.get(artifact) == 1
            and content_hash is not None
            and content_hash_counts.get(content_hash) == 1
            and any(
                _actor_equivalence_key(alias) == authority_key
                for alias in _producer_actor_aliases(record)
            )
        )

    renewal_targets: dict[str, list[dict[str, Any]]] = {}
    renewal_edges: dict[str, str] = {}
    for entry in parsed_entries:
        raw = entry["raw"]
        path = entry["path"]
        renews_value = raw.get("renews")
        renews = _source_identity(renews_value) if renews_value is not None else None
        renewal_values, renewal_invalid = _strict_source_strings(
            raw.get("renewal_approval_evidence")
        )
        if renews_value is not None and renews is None:
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_RENEWAL_REFERENCE_INVALID",
                    "Renewal references must be canonical exception identities.",
                    path=f"{path}.renews",
                    source_id=source_id,
                )
            )
            continue
        if renews is None:
            if raw.get("renewal_approval_evidence") is not None:
                diagnostics.append(
                    _diagnostic(
                        "EXCEPTION_RENEWAL_REFERENCE_INVALID",
                        "Renewal approval evidence requires an explicit renewal reference.",
                        path=f"{path}.renewal_approval_evidence",
                        source_id=source_id,
                    )
                )
            continue

        current_id = entry["id"]
        prior = unique_by_id.get(renews)
        if current_id is None or renews == current_id or prior is None:
            diagnostics.append(
                _diagnostic(
                    "EXCEPTION_RENEWAL_REFERENCE_INVALID",
                    "Renewals must reference a distinct, uniquely identified prior exception.",
                    path=f"{path}.renews",
                    source_id=source_id,
                )
            )
        else:
            renewal_targets.setdefault(renews, []).append(entry)
            renewal_edges[current_id] = renews
            prior_raw = prior["raw"]
            if prior["status"] not in {"approved", "active", "expired", "closed"}:
                diagnostics.append(
                    _diagnostic(
                        "EXCEPTION_RENEWAL_REFERENCE_INVALID",
                        "Only an approved, active, expired, or closed exception can be renewed.",
                        path=f"{path}.renews",
                        source_id=source_id,
                    )
                )
            if prior_raw.get("renewal_policy") != "manual_reapproval":
                diagnostics.append(
                    _diagnostic(
                        "EXCEPTION_RENEWAL_NOT_ALLOWED",
                        "The prior exception does not permit manual renewal.",
                        path=f"{path}.renews",
                        source_id=source_id,
                    )
                )
            if entry["control"] != prior["control"] or entry["scope"] != prior["scope"]:
                diagnostics.append(
                    _diagnostic(
                        "EXCEPTION_RENEWAL_REFERENCE_INVALID",
                        "A renewal must preserve the prior exception control and scope.",
                        path=f"{path}.renews",
                        source_id=source_id,
                    )
                )
            if (
                entry["starts"] is not None
                and prior["expires"] is not None
                and entry["starts"] < prior["expires"]
            ):
                diagnostics.append(
                    _diagnostic(
                        "EXCEPTION_RENEWAL_INTERVAL_INVALID",
                        "A renewal cannot start before the prior exception expires.",
                        path=f"{path}.starts_at",
                        source_id=source_id,
                    )
                )

            prior_evidence_ids = ancestor_evidence_ids(renews)
            renewal_records = [
                usable_evidence_by_id.get(reference)
                for reference in renewal_values
            ]
            renewal_action = f"renew_exception:{current_id}"
            renewal_gates = [
                approval
                for approval in document_approvals
                if renewal_action in approval.actions_requiring_approval
            ]
            renewal_authority_role = _human_actor_role(
                raw.get("approving_authority")
            )
            renewal_authority_key = _actor_equivalence_key(
                raw.get("approving_authority")
            )
            gate_valid = bool(renewal_gates) and renewal_authority_role is not None
            if renewal_gates:
                eligible_roles = set(renewal_gates[0].eligible_roles)
                for approval in renewal_gates[1:]:
                    eligible_roles &= set(approval.eligible_roles)
                required_roles = {
                    role for approval in renewal_gates for role in approval.required_roles
                }
                denied_roles = {
                    role
                    for approval in renewal_gates
                    for role in (
                        *approval.denied_actor_types,
                        *approval.denied_execution_surfaces,
                    )
                }
                gate_evidence = {
                    reference
                    for approval in renewal_gates
                    for reference in approval.required_evidence
                }
                gate_valid = gate_valid and (
                    bool(eligible_roles)
                    and renewal_authority_role in eligible_roles
                    and required_roles <= {renewal_authority_role}
                    and renewal_authority_role not in denied_roles
                    and bool(gate_evidence)
                    and gate_evidence == set(renewal_values)
                )
            renewal_is_separately_approved = (
                not renewal_invalid
                and bool(renewal_values)
                and all(record is not None for record in renewal_records)
                and not set(renewal_values) & prior_evidence_ids
                and all(
                    renewal_evidence_usage.get(reference) == 1
                    for reference in renewal_values
                )
                and all(
                    is_human_approval_record(
                        record,
                        renewal_authority_key,
                        approval_not_before=prior["starts"],
                        approval_not_after=entry["starts"],
                    )
                    for record in renewal_records
                )
                and gate_valid
            )
            if not renewal_is_separately_approved:
                diagnostics.append(
                    _diagnostic(
                        "EXCEPTION_RENEWAL_APPROVAL_MISSING",
                        "Renewal requires new passing human-approval evidence by record id.",
                        path=f"{path}.renewal_approval_evidence",
                        source_id=source_id,
                    )
                )

    for target, renewals in sorted(renewal_targets.items()):
        if len(renewals) > 1:
            for renewal in renewals:
                diagnostics.append(
                    _diagnostic(
                        "EXCEPTION_RENEWAL_FORK_INVALID",
                        f"Prior exception {target!r} has multiple direct renewals.",
                        path=f"{renewal['path']}.renews",
                        source_id=source_id,
                    )
                )

    cyclic_renewals: set[str] = set()
    for start in sorted(renewal_edges):
        chain: list[str] = []
        positions: dict[str, int] = {}
        current = start
        while current in renewal_edges:
            if current in positions:
                cyclic_renewals.update(chain[positions[current] :])
                break
            positions[current] = len(chain)
            chain.append(current)
            current = renewal_edges[current]
    for identifier in sorted(cyclic_renewals):
        entry = unique_by_id[identifier]
        diagnostics.append(
            _diagnostic(
                "EXCEPTION_RENEWAL_REFERENCE_INVALID",
                "Exception renewal references contain a cycle.",
                path=f"{entry['path']}.renews",
                source_id=source_id,
            )
        )

    active_entries = [
        entry
        for entry in parsed_entries
        if entry["status"] in {"active", "approved"}
        and entry["interval_valid"]
        and entry["control"] is not None
        and entry["scope"]
    ]
    for position, first in enumerate(active_entries):
        for second in active_entries[position + 1 :]:
            if (
                first["control"] == second["control"]
                and first["scope"] & second["scope"]
                and first["starts"] < second["expires"]
                and second["starts"] < first["expires"]
            ):
                diagnostics.append(
                    _diagnostic(
                        "EXCEPTION_SCOPE_OVERLAP",
                        "Active exceptions for the same control overlap in scope and time.",
                        path=second["path"],
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

    evidence_ids = _evidence_references(document)
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

        risk_tier_value = raw.get("risk_tier")
        risk_tier = (
            risk_tier_value
            if isinstance(risk_tier_value, str) and risk_tier_value in RISK_TIERS
            else None
        )
        if risk_tier is None:
            diagnostics.append(
                _diagnostic(
                    "CHANGE_RISK_TIER_INVALID",
                    "Change risk tier must be a supported source value.",
                    path=f"{path}.risk_tier",
                    source_id=source_id,
                )
            )
        high_risk = risk_tier in {"high", "critical"}
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
        if (
            architecture_impact is not None
            and (
                not isinstance(architecture_impact, str)
                or architecture_impact not in ARCHITECTURE_IMPACTS
            )
        ):
            diagnostics.append(
                _diagnostic(
                    "CHANGE_ARCHITECTURE_IMPACT_INVALID",
                    "Architecture impact must be a supported source value.",
                    path=f"{path}.impacts.architecture",
                    source_id=source_id,
                )
            )
        if (
            isinstance(architecture_impact, str)
            and architecture_impact in {"major", "critical"}
        ):
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
