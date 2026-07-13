from __future__ import annotations

from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .models import CompositionResult, GovernanceModule, ProfilePack
from .registry import GovernanceRegistry
from .runtime import compose_document_governance, evaluate_document_governance


def _item_id(value: Mapping[str, Any], fallback: str) -> str:
    return str(value.get("id") or value.get("name") or value.get("type") or fallback)


def _pack_row(pack: ProfilePack | GovernanceModule) -> dict[str, Any]:
    if isinstance(pack, GovernanceModule):
        return {
            "kind": "module",
            "id": pack.id,
            "name": pack.name,
            "version": pack.version,
            "dependencies": list(pack.dependencies),
            "required_blocks": list(pack.required_blocks),
            "block_schemas": [item.to_dict() for item in pack.block_schemas],
            "active_controls": {
                "policies": [_item_id(item, "policy") for item in pack.policies],
                "structural_checks": list(pack.structural_checks),
                "rules": [item.namespaced_id for item in pack.rules],
            },
            "required_evidence": [
                deepcopy(dict(item)) for item in pack.evidence_requirements
            ],
            "approval_requirements": [
                deepcopy(dict(item)) for item in pack.approval_requirements
            ],
            "provenance": pack.provenance.to_dict(),
            "content_hash": pack.content_hash,
        }
    return {
        "kind": "profile",
        "id": pack.id,
        "name": pack.name,
        "version": pack.version,
        "dependencies": list(pack.required_modules),
        "required_blocks": list(pack.required_blocks),
        "block_schemas": [],
        "active_controls": {
            "policies": [_item_id(item, "policy") for item in pack.default_policies],
            "structural_checks": [],
            "rules": [item.namespaced_id for item in pack.validation_rules],
        },
        "required_evidence": [deepcopy(dict(item)) for item in pack.required_evidence],
        "approval_requirements": [
            deepcopy(dict(item)) for item in pack.approval_requirements
        ],
        "provenance": pack.provenance.to_dict(),
        "content_hash": pack.content_hash,
    }


def _exception_status(document: Mapping[str, Any]) -> dict[str, Any]:
    block = document.get("exceptions")
    entries = block.get("entries") if isinstance(block, Mapping) else None
    if not isinstance(entries, list):
        return {"declared": 0, "by_status": {}, "entries": []}
    normalized = []
    for index, item in enumerate(entries):
        if not isinstance(item, Mapping):
            normalized.append(
                {"id": f"invalid-{index}", "status": "invalid", "control": None}
            )
            continue
        normalized.append(
            {
                "id": str(item.get("id") or f"unnamed-{index}"),
                "status": str(item.get("status") or "unknown"),
                "control": item.get("control"),
                "expires_at": item.get("expires_at"),
            }
        )
    counts = Counter(str(item["status"]) for item in normalized)
    return {
        "declared": len(normalized),
        "by_status": dict(sorted(counts.items())),
        "entries": normalized,
    }


def _effective_controls(composition: CompositionResult) -> dict[str, Any]:
    return {
        "policies": [_item_id(item, "policy") for item in composition.policies],
        "structural_checks": list(composition.structural_checks),
        "rules": [item.namespaced_id for item in composition.rules],
    }


def build_governance_report(
    document: Mapping[str, Any],
    *,
    registry: GovernanceRegistry,
    lock_path: str | Path | None = None,
    as_of: str | None = None,
    document_root: str | Path | None = None,
) -> dict[str, Any]:
    """Build a deterministic-shape, read-only governance inspection report."""

    composition = compose_document_governance(
        document,
        registry=registry,
        lock_path=lock_path,
    )
    if composition is None:
        diagnostics = evaluate_document_governance(
            document,
            registry=registry,
            lock_path=None,
            as_of=as_of,
            document_root=document_root,
        )
        lock = {
            "status": "not_applicable" if lock_path is not None else "absent",
            "path": Path(lock_path).as_posix() if lock_path is not None else None,
        }
        return {
            "schema": "nornyx.governance_inspection.v1",
            "status": "not_selected",
            "profile": None,
            "modules": [],
            "lock": lock,
            "resolution_trace": list(registry.resolution_trace),
            "active_controls": {"policies": [], "structural_checks": [], "rules": []},
            "required_evidence": [],
            "approval_requirements": [],
            "exception_status": _exception_status(document),
            "matrix": [],
            "diagnostics": [item.to_dict() for item in diagnostics],
        }
    lock = {
        "status": "verified" if lock_path is not None else "absent",
        "path": Path(lock_path).as_posix() if lock_path is not None else None,
    }
    diagnostics = evaluate_document_governance(
        document,
        registry=registry,
        lock_path=lock_path,
        as_of=as_of,
        document_root=document_root,
    )
    has_errors = any(item.level == "error" for item in diagnostics)
    matrix = [
        *([_pack_row(composition.profile)] if composition.profile is not None else []),
        *[_pack_row(module) for module in composition.modules],
    ]
    return {
        "schema": "nornyx.governance_inspection.v1",
        "status": "fail" if has_errors else "pass",
        "profile": composition.profile.id if composition.profile else None,
        "modules": [module.id for module in composition.modules],
        "lock": lock,
        "resolution_trace": list(registry.resolution_trace),
        "active_controls": _effective_controls(composition),
        "required_blocks": list(composition.required_blocks),
        "required_evidence": [
            deepcopy(dict(item)) for item in composition.evidence_requirements
        ],
        "approval_requirements": [
            item.to_dict() for item in composition.approval_requirements
        ],
        "exception_status": _exception_status(document),
        "matrix": matrix,
        "effective": composition.to_dict(),
        "diagnostics": [item.to_dict() for item in diagnostics],
    }
