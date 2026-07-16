from __future__ import annotations

from pathlib import Path

from .loader import MAX_PACK_BYTES, parse_bounded_yaml_mapping, read_local_file_bytes
from .models import GovernanceDiagnostic
from .registry import GovernanceRegistry
from .runtime import evaluate_document_governance


def validate_governance_evidence_file(
    path: str | Path,
    *,
    allowed_root: str | Path,
    trust_root: str | Path | None = None,
    as_of: str | None = None,
) -> tuple[GovernanceDiagnostic, ...]:
    """Validate one bounded local ``nornyx.governance_evidence.v1`` set.

    The file may be JSON or YAML. Its artifact paths are resolved relative to
    the evidence file's directory. Validation never executes producers or
    retrieves artifacts from a network.
    """

    raw, resolved = read_local_file_bytes(
        path,
        allowed_root=allowed_root,
        trust_root=trust_root,
        code_prefix="EVIDENCE",
        noun="Evidence",
        max_bytes=MAX_PACK_BYTES,
    )
    payload = parse_bounded_yaml_mapping(
        raw,
        source_path=resolved.as_posix(),
        code_prefix="EVIDENCE",
        noun="Evidence",
    )
    document = {
        "project": {"modules": ["evidence_integrity"]},
        "governance_evidence": payload,
    }
    return evaluate_document_governance(
        document,
        registry=GovernanceRegistry.builtins(),
        as_of=as_of,
        document_root=resolved.parent,
    )
