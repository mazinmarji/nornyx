from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .errors import GovernanceError, error
from .loader import read_local_file_bytes
from .models import CompositionResult, GovernanceDiagnostic
from .schemas import validate_governance_block, validate_payload


MAX_ARCHITECTURE_REPORT_BYTES = 4 * 1024 * 1024
MAX_ARCHITECTURE_REPORT_DEPTH = 20
MAX_ARCHITECTURE_REPORT_NODES = 50_000


def _diagnostic(
    code: str,
    message: str,
    *,
    path: str,
    level: str = "error",
) -> GovernanceDiagnostic:
    return GovernanceDiagnostic(  # type: ignore[arg-type]
        level,
        code,
        message,
        path=path,
        source_id="architecture_conformance.v1",
    )


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _as_records(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _record_map(value: Any) -> dict[str, Mapping[str, Any]]:
    return {
        str(item.get("id")): item
        for item in _as_records(value)
        if isinstance(item.get("id"), str)
    }


def _absolute_without_resolving(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def _safe_local_file(
    path: str | Path,
    *,
    allowed_root: str | Path,
) -> tuple[bytes, Path, str]:
    try:
        raw, resolved = read_local_file_bytes(
            path,
            allowed_root=allowed_root,
            code_prefix="ARCH_REPORT",
            noun="Architecture report",
            max_bytes=MAX_ARCHITECTURE_REPORT_BYTES,
        )
    except GovernanceError as exc:
        codes = {item.code for item in exc.diagnostics}
        stable_specific = {
            "ARCH_REPORT_LIMIT_EXCEEDED",
            "ARCH_REPORT_PATH_OUTSIDE_ROOT",
            "ARCH_REPORT_REMOTE_SOURCE_REJECTED",
            "ARCH_REPORT_SYMLINK_REJECTED",
        }
        if codes <= stable_specific:
            raise
        message = (
            "Architecture report must be a regular local file."
            if codes == {"ARCH_REPORT_PATH_TYPE_INVALID"}
            else "Architecture report is missing, unreadable, or outside the permitted root."
        )
        raise error(
            "ARCH_REPORT_UNAVAILABLE",
            message,
            path=str(path),
        ) from exc
    raw_root = _absolute_without_resolving(Path(allowed_root))
    try:
        resolved_root = Path(os.path.realpath(raw_root))
        artifact = resolved.relative_to(resolved_root).as_posix()
    except ValueError as exc:
        raise error(
            "ARCH_REPORT_UNAVAILABLE",
            "Architecture report is outside the permitted root.",
            path=str(path),
        ) from exc
    return raw, resolved, artifact


def _bounded_json(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_ARCHITECTURE_REPORT_BYTES:
        raise error(
            "ARCH_REPORT_LIMIT_EXCEEDED",
            "Architecture report exceeds the byte limit.",
        )

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        payload = json.loads(raw, object_pairs_hook=object_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise error("ARCH_REPORT_INVALID", f"Malformed architecture report: {exc}.") from exc
    if not isinstance(payload, dict):
        raise error("ARCH_REPORT_INVALID", "Architecture report must contain a JSON object.")

    nodes = 0

    def visit(value: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if depth > MAX_ARCHITECTURE_REPORT_DEPTH or nodes > MAX_ARCHITECTURE_REPORT_NODES:
            raise error(
                "ARCH_REPORT_LIMIT_EXCEEDED",
                "Architecture report exceeds structural limits.",
            )
        if isinstance(value, Mapping):
            for child in value.values():
                visit(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                visit(child, depth + 1)

    visit(payload, 0)
    return payload


def import_architecture_evidence(
    report_path: str | Path,
    *,
    allowed_root: str | Path,
) -> dict[str, Any]:
    """Import one bounded neutral report without running the named tool."""
    raw, _, artifact = _safe_local_file(report_path, allowed_root=allowed_root)
    payload = _bounded_json(raw)
    try:
        validate_payload(payload, "architecture_report_v1.schema.json")
    except GovernanceError as exc:
        details = "; ".join(item.message for item in exc.diagnostics)
        raise error(
            "ARCH_REPORT_INVALID",
            f"Architecture report does not satisfy nornyx.architecture_report.v1: {details}",
            path=artifact,
        ) from exc
    if payload["status"] == "pass" and payload["violations"]:
        raise error(
            "ARCH_REPORT_STATUS_INCONSISTENT",
            "A passing architecture report cannot contain violations.",
            path=artifact,
        )
    evidence = {
        **payload,
        "schema": "nornyx.architecture_evidence.v1",
        "artifact": artifact,
        "artifact_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
    }
    diagnostics = validate_governance_block(
        "architecture_evidence",
        [evidence],
        "https://nornyx.dev/schemas/architecture_evidence_v1.schema.json",
        source_id="nornyx.architecture_importer",
    )
    if diagnostics:
        raise GovernanceError(*diagnostics)
    return evidence


def _artifact_hash(root: Path, artifact: Any) -> str | None:
    if not isinstance(artifact, str):
        return None
    try:
        raw, _, _ = _safe_local_file(artifact, allowed_root=root)
        return "sha256:" + hashlib.sha256(raw).hexdigest()
    except GovernanceError:
        return None


def _add_unknown_reference(
    diagnostics: list[GovernanceDiagnostic],
    value: Any,
    known: set[str],
    *,
    path: str,
    kind: str,
) -> None:
    if isinstance(value, str) and value not in known:
        diagnostics.append(
            _diagnostic(
                "ARCH_REFERENCE_UNKNOWN",
                f"Architecture {kind} reference {value!r} is not declared.",
                path=path,
            )
        )


def _check_duplicate_ids(
    diagnostics: list[GovernanceDiagnostic],
    records: list[Mapping[str, Any]],
    *,
    path: str,
) -> None:
    seen: set[str] = set()
    for index, record in enumerate(records):
        identity = record.get("id")
        if not isinstance(identity, str):
            continue
        if identity in seen:
            diagnostics.append(
                _diagnostic(
                    "ARCH_DUPLICATE_ID",
                    f"Architecture id {identity!r} is duplicated within {path}.",
                    path=f"{path}[{index}].id",
                )
            )
        seen.add(identity)


def _check_evidence_record(
    record: Mapping[str, Any],
    check: Mapping[str, Any],
    *,
    index: int,
    subject_revision: Any,
    as_of: datetime | None,
    document_root: Path | None,
) -> list[GovernanceDiagnostic]:
    path = f"architecture_evidence[{index}]"
    diagnostics: list[GovernanceDiagnostic] = []
    if record.get("tool") != check.get("tool"):
        diagnostics.append(
            _diagnostic(
                "ARCH_EVIDENCE_TOOL_MISMATCH",
                "Architecture evidence was produced for a different declared tool.",
                path=f"{path}.tool",
            )
        )
    if record.get("schema") != check.get("evidence_schema"):
        diagnostics.append(
            _diagnostic(
                "ARCH_EVIDENCE_SCHEMA_MISMATCH",
                "Architecture evidence uses a different schema than the required check.",
                path=f"{path}.schema",
            )
        )
    if record.get("subject_revision") != subject_revision:
        diagnostics.append(
            _diagnostic(
                "ARCH_EVIDENCE_REVISION_MISMATCH",
                "Architecture evidence is not bound to the declared architecture revision.",
                path=f"{path}.subject_revision",
            )
        )
    if record.get("status") != "pass":
        diagnostics.append(
            _diagnostic(
                "ARCH_REQUIRED_CHECK_FAILED",
                "A required architecture check does not have passing evidence.",
                path=f"{path}.status",
            )
        )
    if record.get("status") == "pass" and record.get("violations"):
        diagnostics.append(
            _diagnostic(
                "ARCH_EVIDENCE_STATUS_INCONSISTENT",
                "Passing architecture evidence cannot contain violations.",
                path=f"{path}.violations",
            )
        )
    if as_of is None:
        diagnostics.append(
            _diagnostic(
                "ARCH_EVIDENCE_TIME_REQUIRED",
                "An explicit validation time is required for architecture evidence.",
                path=path,
            )
        )
    else:
        try:
            generated = _parse_time(record.get("generated_at"))
            expires = _parse_time(record.get("expires_at"))
            if generated > as_of:
                diagnostics.append(
                    _diagnostic(
                        "ARCH_EVIDENCE_GENERATED_IN_FUTURE",
                        "Architecture evidence was generated after the validation time.",
                        path=f"{path}.generated_at",
                    )
                )
            if generated >= expires or expires <= as_of:
                diagnostics.append(
                    _diagnostic(
                        "ARCH_EVIDENCE_STALE",
                        "Architecture evidence is stale or has an invalid freshness interval.",
                        path=f"{path}.expires_at",
                    )
                )
        except ValueError:
            diagnostics.append(
                _diagnostic(
                    "ARCH_EVIDENCE_TIME_INVALID",
                    "Architecture evidence timestamps must include valid UTC offsets.",
                    path=path,
                )
            )
    if document_root is None:
        diagnostics.append(
            _diagnostic(
                "ARCH_EVIDENCE_ARTIFACT_ROOT_REQUIRED",
                "A trusted document root is required to verify architecture evidence.",
                path=f"{path}.artifact",
            )
        )
    else:
        observed = _artifact_hash(document_root, record.get("artifact"))
        if observed is None:
            diagnostics.append(
                _diagnostic(
                    "ARCH_EVIDENCE_ARTIFACT_UNAVAILABLE",
                    "Architecture evidence artifact is missing, unreadable, outside the root, or symlinked.",
                    path=f"{path}.artifact",
                )
            )
        elif observed != record.get("artifact_sha256"):
            diagnostics.append(
                _diagnostic(
                    "ARCH_EVIDENCE_ARTIFACT_HASH_MISMATCH",
                    "Architecture evidence artifact hash does not match its declaration.",
                    path=f"{path}.artifact_sha256",
                )
            )
    return diagnostics


def architecture_conformance_check(
    document: Mapping[str, Any],
    composition: CompositionResult,
    *,
    as_of: datetime | None,
    document_root: Path | None,
) -> tuple[GovernanceDiagnostic, ...]:
    del composition
    architecture = document.get("architecture")
    evidence_value = document.get("architecture_evidence")
    if not isinstance(architecture, Mapping) or not isinstance(evidence_value, list):
        return ()
    diagnostics: list[GovernanceDiagnostic] = []

    groups = {
        name: _as_records(architecture.get(name))
        for name in (
            "descriptions",
            "viewpoints",
            "systems",
            "components",
            "modules",
            "layers",
            "bounded_contexts",
            "interfaces",
            "decisions",
            "principles",
            "constraints",
            "required_checks",
        )
    }
    boundaries = architecture.get("boundaries")
    boundary_groups = {
        name: _as_records(boundaries.get(name)) if isinstance(boundaries, Mapping) else []
        for name in ("trust", "data", "deployment")
    }
    for name, records in {**groups, **boundary_groups}.items():
        path = f"architecture.boundaries.{name}" if name in boundary_groups else f"architecture.{name}"
        _check_duplicate_ids(diagnostics, records, path=path)

    ids = {name: set(_record_map(records)) for name, records in groups.items()}
    boundary_ids = {name: set(_record_map(records)) for name, records in boundary_groups.items()}

    for index, record in enumerate(groups["descriptions"]):
        for ref in record.get("viewpoints", []):
            _add_unknown_reference(
                diagnostics,
                ref,
                ids["viewpoints"],
                path=f"architecture.descriptions[{index}].viewpoints",
                kind="viewpoint",
            )
    for index, record in enumerate(groups["systems"]):
        for ref in record.get("components", []):
            _add_unknown_reference(
                diagnostics,
                ref,
                ids["components"],
                path=f"architecture.systems[{index}].components",
                kind="component",
            )

    components = _record_map(groups["components"])
    layers = _record_map(groups["layers"])
    modules = _record_map(groups["modules"])
    for index, record in enumerate(groups["components"]):
        base = f"architecture.components[{index}]"
        _add_unknown_reference(diagnostics, record.get("system"), ids["systems"], path=f"{base}.system", kind="system")
        _add_unknown_reference(diagnostics, record.get("layer"), ids["layers"], path=f"{base}.layer", kind="layer")
        _add_unknown_reference(
            diagnostics,
            record.get("bounded_context"),
            ids["bounded_contexts"],
            path=f"{base}.bounded_context",
            kind="bounded context",
        )
        for ref in record.get("modules", []):
            _add_unknown_reference(diagnostics, ref, ids["modules"], path=f"{base}.modules", kind="module")
        for ref in record.get("depends_on", []):
            _add_unknown_reference(diagnostics, ref, ids["components"], path=f"{base}.depends_on", kind="component")
            target = components.get(str(ref))
            source_layer = layers.get(str(record.get("layer")))
            if target is not None and source_layer is not None:
                target_layer = target.get("layer")
                allowed = set(source_layer.get("may_depend_on", [])) | {record.get("layer")}
                if target_layer not in allowed:
                    diagnostics.append(
                        _diagnostic(
                            "ARCH_DEPENDENCY_DIRECTION_VIOLATION",
                            f"Component dependency on layer {target_layer!r} is not allowed by layer {record.get('layer')!r}.",
                            path=f"{base}.depends_on",
                        )
                    )

    for index, record in enumerate(groups["modules"]):
        base = f"architecture.modules[{index}]"
        _add_unknown_reference(diagnostics, record.get("component"), ids["components"], path=f"{base}.component", kind="component")
        _add_unknown_reference(diagnostics, record.get("layer"), ids["layers"], path=f"{base}.layer", kind="layer")
        for ref in record.get("depends_on", []):
            _add_unknown_reference(diagnostics, ref, ids["modules"], path=f"{base}.depends_on", kind="module")
            target = modules.get(str(ref))
            source_layer = layers.get(str(record.get("layer")))
            if target is not None and source_layer is not None:
                target_layer = target.get("layer")
                allowed = set(source_layer.get("may_depend_on", [])) | {record.get("layer")}
                if target_layer not in allowed:
                    diagnostics.append(
                        _diagnostic(
                            "ARCH_DEPENDENCY_DIRECTION_VIOLATION",
                            f"Module dependency on layer {target_layer!r} is not allowed by layer {record.get('layer')!r}.",
                            path=f"{base}.depends_on",
                        )
                    )

    for index, record in enumerate(groups["layers"]):
        for ref in record.get("may_depend_on", []):
            _add_unknown_reference(diagnostics, ref, ids["layers"], path=f"architecture.layers[{index}].may_depend_on", kind="layer")
            if ref == record.get("id"):
                diagnostics.append(
                    _diagnostic(
                        "ARCH_LAYER_DIRECTION_INVALID",
                        "Layer dependency declarations must not include the layer itself.",
                        path=f"architecture.layers[{index}].may_depend_on",
                    )
                )

    for index, record in enumerate(groups["interfaces"]):
        base = f"architecture.interfaces[{index}]"
        _add_unknown_reference(diagnostics, record.get("provider"), ids["components"], path=f"{base}.provider", kind="component")
        for ref in record.get("consumers", []):
            _add_unknown_reference(diagnostics, ref, ids["components"], path=f"{base}.consumers", kind="component")
        for field, kind in (
            ("trust_boundary", "trust"),
            ("data_boundary", "data"),
            ("deployment_boundary", "deployment"),
        ):
            if field in record:
                _add_unknown_reference(diagnostics, record.get(field), boundary_ids[kind], path=f"{base}.{field}", kind=f"{kind} boundary")

    for index, record in enumerate(groups["decisions"]):
        for ref in record.get("supersedes", []):
            _add_unknown_reference(diagnostics, ref, ids["decisions"], path=f"architecture.decisions[{index}].supersedes", kind="decision")
    for index, record in enumerate(groups["constraints"]):
        verifier = record.get("verified_by")
        if verifier != "human_review":
            _add_unknown_reference(diagnostics, verifier, ids["required_checks"], path=f"architecture.constraints[{index}].verified_by", kind="required check")

    exception_block = document.get("exceptions")
    exception_ids = {
        str(item.get("id"))
        for item in _as_records(exception_block.get("entries") if isinstance(exception_block, Mapping) else None)
    }
    for index, ref in enumerate(architecture.get("architecture_exceptions", [])):
        _add_unknown_reference(
            diagnostics,
            ref,
            exception_ids,
            path=f"architecture.architecture_exceptions[{index}]",
            kind="governed exception",
        )

    evidence_records = _as_records(evidence_value)
    evidence_by_check: dict[str, list[tuple[int, Mapping[str, Any]]]] = {}
    for index, record in enumerate(evidence_records):
        check_id = str(record.get("check_id", ""))
        evidence_by_check.setdefault(check_id, []).append((index, record))
        if check_id not in ids["required_checks"]:
            diagnostics.append(
                _diagnostic(
                    "ARCH_EVIDENCE_CHECK_UNKNOWN",
                    f"Architecture evidence references undeclared check {check_id!r}.",
                    path=f"architecture_evidence[{index}].check_id",
                )
            )
    for check_id, matches in sorted(evidence_by_check.items()):
        if len(matches) > 1:
            diagnostics.append(
                _diagnostic(
                    "ARCH_EVIDENCE_DUPLICATE_CHECK",
                    f"Architecture check {check_id!r} has multiple evidence records.",
                    path="architecture_evidence",
                )
            )

    subject_revision = architecture.get("subject_revision")
    for check in groups["required_checks"]:
        check_id = str(check.get("id", ""))
        matches = evidence_by_check.get(check_id, [])
        if not matches:
            diagnostics.append(
                _diagnostic(
                    "ARCH_EVIDENCE_MISSING",
                    f"Required architecture check {check_id!r} has no evidence.",
                    path="architecture_evidence",
                )
            )
            continue
        for index, record in matches:
            diagnostics.extend(
                _check_evidence_record(
                    record,
                    check,
                    index=index,
                    subject_revision=subject_revision,
                    as_of=as_of,
                    document_root=document_root,
                )
            )
    return tuple(diagnostics)
