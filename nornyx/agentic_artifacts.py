"""AN-003: deterministic agentic-network governance artifacts and network lock.

Every output is a static, non-executable declaration derived canonically from
the parsed contract and its resolved governance composition. Outputs are
timestamp-free, machine-independent, and byte-stable across platforms and
across semantically irrelevant source formatting. The lock binds reviewed
content; it never attests runtime behavior, producer identity, or truth.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .governance.agentic_network import SENSITIVE_CATEGORIES, _IMMUTABLE_REVISION_RE
from .governance.errors import GovernanceError
from .governance.loader import (
    MAX_PACK_BYTES,
    _is_link_or_reparse,
    read_local_file_bytes,
    reject_remote_or_device_path,
)
from .governance.locks import _prepare_lock_output
from .governance.models import CompositionResult, GovernanceDiagnostic
from .governance.schemas import validate_payload


LOCK_SCHEMA_ID = "nornyx.agentic_network_lock.v1"
LOCK_FORMAT_VERSION = "1.0"
GENERATION_FORMAT_VERSION = "1.0"
DEFAULT_ARTIFACT_DIR = "generated/agentic_network"
DEFAULT_LOCK_NAME = "nornyx.agentic_network.lock"
GENERATION_MANIFEST_NAME = "agentic_generation_manifest.json"

RUNTIME_EVENTS_SCHEMA_ID = "nornyx.agentic_runtime_events.v1"
RUNTIME_EVENTS_SCHEMA_VERSION = "1.0"
RUNTIME_EVENT_TYPES: tuple[str, ...] = (
    "agent_invoked",
    "capability_requested",
    "capability_allowed",
    "capability_denied",
    "delegation_requested",
    "delegation_accepted",
    "delegation_rejected",
    "handoff_initiated",
    "handoff_completed",
    "trust_zone_crossed",
    "data_shared",
    "approval_requested",
    "approval_granted",
    "approval_rejected",
    "tool_invoked",
    "policy_violation",
    "identity_revoked",
    "runtime_failed",
)

ARTIFACT_NAMES: tuple[str, ...] = (
    "network_manifest.json",
    "identity_manifest.json",
    "capability_matrix.json",
    "trust_zone_map.json",
    "delegation_policy_bundle.json",
    "handoff_manifest.json",
    "runtime_evidence_contract.json",
    "a2a_declaration.json",
    "mcp_capability_declaration.json",
)

# Exact key segments (split on non-alphanumerics) that mark transport,
# credential, or execution material. Segment matching avoids false positives
# on reviewed declaration fields such as `execution_mode` and `agent_key`.
_FORBIDDEN_KEY_SEGMENTS = frozenset(
    {
        "apikey",
        "bearer",
        "cmd",
        "command",
        "commands",
        "credential",
        "credentials",
        "endpoint",
        "endpoints",
        "host",
        "hostname",
        "hosts",
        "ip",
        "password",
        "passwords",
        "port",
        "ports",
        "secret",
        "secrets",
        "session",
        "sessions",
        "shell",
        "token",
        "tokens",
        "uri",
        "url",
        "urls",
    }
)
_FORBIDDEN_KEY_PAIRS = frozenset(
    {("api", "key"), ("key", "material"), ("private", "key"), ("access", "key")}
)
_KEY_SPLIT_RE = re.compile(r"[^a-z0-9]+")
_IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
# Reviewed schema-identifier namespace (a name, resolved locally, never fetched).
_SCHEMA_ID_RE = re.compile(
    r"^https://nornyx\.dev/schemas/[a-z0-9_.-]+\.schema\.json$"
)


class AgenticArtifactError(GovernanceError):
    """Raised when generation or locking must fail closed."""


def error(
    code: str, message: str, *, path: str | None = None
) -> AgenticArtifactError:
    """Build this module's fail-closed error as an ``AgenticArtifactError``.

    Every generation, lock, and load failure in this module raises the
    module's own error type so narrow ``except AgenticArtifactError`` handlers
    observe them; it remains a ``GovernanceError`` for existing broad catches.
    """

    return AgenticArtifactError(
        GovernanceDiagnostic("error", code, message, path=path)
    )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _rendered_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _items(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _sorted_records(value: Any, key: str) -> list[dict[str, Any]]:
    records = [
        json.loads(_canonical_bytes(item))
        for item in _items(value)
        if isinstance(item.get(key), str)
    ]
    return sorted(records, key=lambda item: str(item[key]))


def _record_digests(value: Any, key: str) -> list[dict[str, str]]:
    return [
        {"id": str(item[key]), "digest": _digest(item)}
        for item in _sorted_records(value, key)
    ]


# Record collections whose order is not semantic: they are keyed sets and are
# canonically sorted before digesting so formatting and record-order
# permutations of the source cannot change governed-content hashes. Leaf
# arrays (globs, refs, categories) keep their declared order.
_KEYED_TOP_COLLECTIONS: dict[str, tuple[str, ...]] = {
    "agent_identities": ("id",),
    "capabilities": ("name",),
    "approvals": ("id", "name"),
    "policies": ("id", "name"),
    "contexts": ("name",),
    "agents": ("name",),
    "intents": ("name",),
    "goals": ("id",),
}
_KEYED_NETWORK_COLLECTIONS = (
    "trust_zones",
    "memberships",
    "protocol_targets",
    "network_gates",
    "revocations",
    "delegations",
    "handoffs",
    "relations",
)


def _record_sort_key(item: Any, fields: tuple[str, ...]) -> tuple[int, str]:
    if isinstance(item, Mapping):
        for field in fields:
            value = item.get(field)
            if isinstance(value, str):
                return (0, value)
    return (1, _canonical_bytes(item).decode("utf-8"))


def _sorted_collection(value: Any, fields: tuple[str, ...]) -> Any:
    if not isinstance(value, list):
        return value
    return sorted(value, key=lambda item: _record_sort_key(item, fields))


def _canonical_contract_view(document: Mapping[str, Any]) -> dict[str, Any]:
    view = json.loads(_canonical_bytes(document))
    for block, fields in _KEYED_TOP_COLLECTIONS.items():
        if block in view:
            view[block] = _sorted_collection(view[block], fields)
    network = view.get("agentic_network")
    if isinstance(network, dict):
        for collection in _KEYED_NETWORK_COLLECTIONS:
            if collection in network:
                network[collection] = _sorted_collection(
                    network[collection], ("id",)
                )
    evidence = view.get("governance_evidence")
    if isinstance(evidence, dict) and "records" in evidence:
        evidence["records"] = _sorted_collection(evidence["records"], ("id",))
    return view


def contract_digest(document: Mapping[str, Any]) -> str:
    """Canonical governed-content digest of the parsed contract.

    Stable under source formatting and keyed-record reordering; changed by any
    semantic edit to a governed record or leaf value.
    """

    return _digest(_canonical_contract_view(document))


def _forbidden_key(key: str) -> bool:
    segments = [
        segment for segment in _KEY_SPLIT_RE.split(key.casefold()) if segment
    ]
    if any(segment in _FORBIDDEN_KEY_SEGMENTS for segment in segments):
        return True
    return any(pair in _FORBIDDEN_KEY_PAIRS for pair in zip(segments, segments[1:]))


def _scan_forbidden(value: Any, *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _forbidden_key(str(key)):
                raise error(
                    "AN_ARTIFACT_FORBIDDEN_FIELD",
                    f"Generated declarations must not contain field {key!r}.",
                    path=path,
                )
            _scan_forbidden(item, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _scan_forbidden(item, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        if _SCHEMA_ID_RE.fullmatch(value):
            return
        lowered = value.casefold()
        if "://" in lowered or lowered.startswith(("http:", "https:", "ssh:", "ftp:")):
            raise error(
                "AN_ARTIFACT_FORBIDDEN_VALUE",
                "Generated declarations must not contain URLs or transport "
                "references.",
                path=path,
            )
        if _IPV4_RE.fullmatch(value):
            raise error(
                "AN_ARTIFACT_FORBIDDEN_VALUE",
                "Generated declarations must not contain IP addresses.",
                path=path,
            )


def _network(document: Mapping[str, Any]) -> Mapping[str, Any]:
    network = document.get("agentic_network")
    if not isinstance(network, Mapping):
        raise error(
            "AN_ARTIFACT_NETWORK_MISSING",
            "The contract does not declare an agentic_network block.",
            path="agentic_network",
        )
    return network


def _pack_entry(pack: Any) -> dict[str, str]:
    return {
        "id": pack.id,
        "name": pack.name,
        "version": pack.version,
        "content_hash": pack.content_hash,
    }


def _composition_summary(composition: CompositionResult) -> dict[str, Any]:
    if composition.profile is None:
        raise error(
            "AN_ARTIFACT_PROFILE_MISSING",
            "Agentic-network generation requires a resolved profile.",
            path="project.profile",
        )
    return {
        "profile": _pack_entry(composition.profile),
        "modules": sorted(
            (_pack_entry(module) for module in composition.modules),
            key=lambda item: item["id"],
        ),
        "block_schemas": sorted(
            (
                {"block": item.block, "schema_id": item.schema_id}
                for item in (composition.block_schemas or ())
            ),
            key=lambda item: (item["block"], item["schema_id"]),
        ),
        "structural_checks": sorted(composition.structural_checks or ()),
    }


def build_agentic_network_artifacts(
    document: Mapping[str, Any],
    composition: CompositionResult,
) -> dict[str, dict[str, Any]]:
    """Build every deterministic artifact payload (excluding the manifest)."""

    network = _network(document)
    network_id = network.get("id")
    subject_revision = network.get("subject_revision")
    if not isinstance(network_id, str) or not isinstance(subject_revision, str):
        raise error(
            "AN_ARTIFACT_NETWORK_MISSING",
            "agentic_network requires an id and a subject_revision.",
            path="agentic_network",
        )
    source_digest = contract_digest(document)
    summary = _composition_summary(composition)

    identities = _sorted_records(document.get("agent_identities"), "id")
    capabilities = _sorted_records(document.get("capabilities"), "name")
    zones = _sorted_records(network.get("trust_zones"), "id")
    memberships = _sorted_records(network.get("memberships"), "id")
    gates = _sorted_records(network.get("network_gates"), "id")
    protocols = _sorted_records(network.get("protocol_targets"), "id")
    delegations = _sorted_records(network.get("delegations"), "id")
    handoffs = _sorted_records(network.get("handoffs"), "id")
    relations = _sorted_records(network.get("relations"), "id")
    revocations = _sorted_records(network.get("revocations"), "id")

    binding = {
        "network_id": network_id,
        "subject_revision": subject_revision,
        "source_contract_digest": source_digest,
    }

    network_manifest = {
        "schema": "nornyx.agentic_network_manifest.v1",
        **binding,
        **summary,
        "counts": {
            "agent_identities": len(identities),
            "capabilities": len(capabilities),
            "trust_zones": len(zones),
            "memberships": len(memberships),
            "network_gates": len(gates),
            "protocol_targets": len(protocols),
            "delegations": len(delegations),
            "handoffs": len(handoffs),
            "relations": len(relations),
            "revocations": len(revocations),
        },
    }

    identity_manifest = {
        "schema": "nornyx.agentic_identity_manifest.v1",
        **binding,
        "identities": [
            {**item, "digest": _digest(item)} for item in identities
        ],
    }

    capability_matrix = {
        "schema": "nornyx.agentic_capability_matrix.v1",
        **binding,
        "capabilities": [
            {**item, "digest": _digest(item)} for item in capabilities
        ],
        "identity_assignments": [
            {
                "identity": item["id"],
                "capabilities": sorted(
                    ref
                    for ref in item.get("capability_refs", [])
                    if isinstance(ref, str)
                ),
            }
            for item in identities
        ],
        "membership_assignments": [
            {
                "membership": item["id"],
                "identity": item.get("identity_ref"),
                "trust_zone": item.get("trust_zone_ref"),
                "capabilities": sorted(
                    ref
                    for ref in item.get("capability_refs", [])
                    if isinstance(ref, str)
                ),
            }
            for item in memberships
        ],
    }

    trust_zone_map = {
        "schema": "nornyx.agentic_trust_zone_map.v1",
        **binding,
        "trust_zones": [{**item, "digest": _digest(item)} for item in zones],
        "network_gates": [{**item, "digest": _digest(item)} for item in gates],
        "memberships": [
            {
                "membership": item["id"],
                "identity": item.get("identity_ref"),
                "trust_zone": item.get("trust_zone_ref"),
                "status": item.get("status"),
            }
            for item in memberships
        ],
    }

    delegation_policy_bundle = {
        "schema": "nornyx.agentic_delegation_policy_bundle.v1",
        **binding,
        "capability_policies": [
            {
                "capability": item["name"],
                "delegable": item.get("delegable"),
                "max_delegation_depth": item.get("max_delegation_depth"),
                "risk": item.get("risk"),
            }
            for item in capabilities
        ],
        "delegations": [{**item, "digest": _digest(item)} for item in delegations],
        "revocations": [{**item, "digest": _digest(item)} for item in revocations],
    }

    handoff_manifest = {
        "schema": "nornyx.agentic_handoff_manifest.v1",
        **binding,
        "handoffs": [{**item, "digest": _digest(item)} for item in handoffs],
        "relations": [{**item, "digest": _digest(item)} for item in relations],
    }

    runtime_evidence_contract = {
        "schema": "nornyx.agentic_runtime_evidence_contract.v1",
        **binding,
        "events_schema": RUNTIME_EVENTS_SCHEMA_ID,
        "events_schema_version": RUNTIME_EVENTS_SCHEMA_VERSION,
        "allowed_event_types": sorted(RUNTIME_EVENT_TYPES),
        "required_event_binding": {
            "contract_digest": True,
            "network_lock_digest": True,
            "subject_revision": True,
            "network_id": True,
        },
        "limitations": [
            "Validated evidence proves conformance of supplied records only.",
            "Hash validity proves content binding, not event truth.",
            "Nornyx does not observe, operate, or monitor the runtime.",
        ],
    }

    def _protocol_declaration(protocol_name: str, schema_id: str) -> dict[str, Any]:
        matching = [
            item for item in protocols if item.get("protocol") == protocol_name
        ]
        return {
            "schema": schema_id,
            **binding,
            "protocol": protocol_name,
            "compatibility": (
                f"{protocol_name}-compatible declaration; not a runtime, server, "
                "endpoint, or transport"
            ),
            "execution_mode": "contract_only",
            "live_connector_execution": False,
            "declared_targets": [
                {
                    "id": item["id"],
                    "version_label": item.get("version"),
                    "identities": sorted(
                        ref
                        for ref in item.get("identity_refs", [])
                        if isinstance(ref, str)
                    ),
                    "capabilities": sorted(
                        ref
                        for ref in item.get("capability_refs", [])
                        if isinstance(ref, str)
                    ),
                    "message_classes": sorted(
                        {
                            action
                            for capability in capabilities
                            if capability["name"] in item.get("capability_refs", [])
                            for action in capability.get("actions", [])
                            if isinstance(action, str)
                        }
                    ),
                    "source_zone": item.get("source_zone_ref"),
                    "target_zone": item.get("trust_zone_ref"),
                    "share": sorted(
                        ref
                        for ref in item.get("share", [])
                        if isinstance(ref, str)
                    ),
                    "required_approvals": sorted(
                        ref
                        for ref in item.get("required_approval_refs", [])
                        if isinstance(ref, str)
                    ),
                    "required_evidence": sorted(
                        ref
                        for ref in item.get("required_evidence_refs", [])
                        if isinstance(ref, str)
                    ),
                }
                for item in matching
            ],
            "denied_sensitive_categories": sorted(SENSITIVE_CATEGORIES),
        }

    a2a_declaration = _protocol_declaration(
        "a2a", "nornyx.a2a_compatible_declaration.v1"
    )
    mcp_declaration = _protocol_declaration(
        "mcp", "nornyx.mcp_compatible_capability_declaration.v1"
    )

    artifacts = {
        "network_manifest.json": network_manifest,
        "identity_manifest.json": identity_manifest,
        "capability_matrix.json": capability_matrix,
        "trust_zone_map.json": trust_zone_map,
        "delegation_policy_bundle.json": delegation_policy_bundle,
        "handoff_manifest.json": handoff_manifest,
        "runtime_evidence_contract.json": runtime_evidence_contract,
        "a2a_declaration.json": a2a_declaration,
        "mcp_capability_declaration.json": mcp_declaration,
    }
    for name, payload in artifacts.items():
        _scan_forbidden(payload, path=name)
    return artifacts


def render_agentic_network_artifacts(
    document: Mapping[str, Any],
    composition: CompositionResult,
) -> dict[str, bytes]:
    """Render every artifact (including the generation manifest) to bytes."""

    artifacts = build_agentic_network_artifacts(document, composition)
    rendered = {name: _rendered_bytes(payload) for name, payload in artifacts.items()}
    network = _network(document)
    manifest = {
        "schema": "nornyx.agentic_generation_manifest.v1",
        "generation_format_version": GENERATION_FORMAT_VERSION,
        "network_id": network.get("id"),
        "subject_revision": network.get("subject_revision"),
        "source_contract_digest": contract_digest(document),
        "artifacts": [
            {"path": name, "sha256": _sha256_hex(raw)}
            for name, raw in sorted(rendered.items())
        ],
    }
    rendered[GENERATION_MANIFEST_NAME] = _rendered_bytes(manifest)
    return rendered


def write_agentic_network_artifacts(
    document: Mapping[str, Any],
    composition: CompositionResult,
    out_dir: str | Path,
) -> list[Path]:
    reject_remote_or_device_path(
        out_dir, code_prefix="AN_ARTIFACT", noun="Artifact output"
    )
    rendered = render_agentic_network_artifacts(document, composition)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in sorted(rendered):
        target = out / name
        try:
            metadata = os.lstat(target)
        except FileNotFoundError:
            metadata = None
        except OSError as exc:
            raise error(
                "AN_ARTIFACT_WRITE_ERROR",
                f"Cannot inspect the artifact output: {exc}",
                path=str(target),
            ) from exc
        if metadata is not None and (
            _is_link_or_reparse(metadata) or not stat.S_ISREG(metadata.st_mode)
        ):
            raise error(
                "AN_ARTIFACT_OUTPUT_INVALID",
                "Refusing to overwrite a symlinked, reparse-point, or "
                "non-regular artifact output.",
                path=str(target),
            )
        with open(target, "wb") as stream:
            stream.write(rendered[name])
        written.append(target)
    return written


def build_agentic_network_lock(
    document: Mapping[str, Any],
    composition: CompositionResult,
) -> dict[str, Any]:
    network = _network(document)
    network_id = network.get("id")
    subject_revision = network.get("subject_revision")
    if not isinstance(subject_revision, str) or not _IMMUTABLE_REVISION_RE.fullmatch(
        subject_revision
    ):
        raise error(
            "AN_LOCK_REVISION_MUTABLE",
            "The network lock requires an immutable content-addressed "
            "subject revision.",
            path="agentic_network.subject_revision",
        )
    rendered = render_agentic_network_artifacts(document, composition)
    summary = _composition_summary(composition)
    payload = {
        "schema": LOCK_SCHEMA_ID,
        "lock_format_version": LOCK_FORMAT_VERSION,
        "generation_format_version": GENERATION_FORMAT_VERSION,
        "network_id": network_id,
        "subject_revision": subject_revision,
        "source_contract_digest": contract_digest(document),
        **summary,
        "runtime_events_schema": {
            "id": RUNTIME_EVENTS_SCHEMA_ID,
            "version": RUNTIME_EVENTS_SCHEMA_VERSION,
        },
        "protocol_declarations": sorted(
            (
                {
                    "id": item["id"],
                    "protocol": item.get("protocol"),
                    "version_label": item.get("version"),
                    "execution_mode": item.get("execution_mode"),
                }
                for item in _sorted_records(network.get("protocol_targets"), "id")
            ),
            key=lambda item: str(item["id"]),
        ),
        "records": {
            "agent_identities": _record_digests(
                document.get("agent_identities"), "id"
            ),
            "capabilities": _record_digests(document.get("capabilities"), "name"),
            "trust_zones": _record_digests(network.get("trust_zones"), "id"),
            "memberships": _record_digests(network.get("memberships"), "id"),
            "network_gates": _record_digests(network.get("network_gates"), "id"),
            "protocol_targets": _record_digests(
                network.get("protocol_targets"), "id"
            ),
            "delegations": _record_digests(network.get("delegations"), "id"),
            "handoffs": _record_digests(network.get("handoffs"), "id"),
            "relations": _record_digests(network.get("relations"), "id"),
            "revocations": _record_digests(network.get("revocations"), "id"),
        },
        "approval_requirements": sorted(
            item.id for item in composition.approval_requirements
        ),
        "evidence_requirements": sorted(
            str(item.get("id"))
            for item in composition.evidence_requirements
            if isinstance(item.get("id"), str)
        ),
        "artifacts": [
            {"path": name, "sha256": _sha256_hex(raw)}
            for name, raw in sorted(rendered.items())
        ],
    }
    validate_payload(payload, "agentic_network_lock_v1.schema.json")
    return payload


def agentic_network_lock_digest(lock_payload: Mapping[str, Any]) -> str:
    return _digest(lock_payload)


def write_agentic_network_lock(
    lock_payload: Mapping[str, Any],
    path: str | Path,
) -> Path:
    supplied = Path(path)
    target = _prepare_lock_output(supplied, allowed_root=None, trust_root=None)
    content = _rendered_bytes(lock_payload)
    target.parent.mkdir(parents=True, exist_ok=True)
    target = _prepare_lock_output(target, allowed_root=None, trust_root=None)
    descriptor = -1
    temporary: Path | None = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        for _ in range(100):
            candidate = target.parent / f".{target.name}.{secrets.token_hex(8)}.tmp"
            try:
                descriptor = os.open(candidate, flags, 0o666)
            except FileExistsError:
                continue
            temporary = candidate
            break
        if temporary is None:
            raise OSError("cannot allocate a unique lock temporary")
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except OSError as exc:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass
        raise error(
            "AN_LOCK_WRITE_ERROR",
            f"Cannot write the agentic-network lock: {exc}",
            path=str(target),
        ) from exc
    return supplied


def load_agentic_network_lock(path: str | Path) -> dict[str, Any]:
    reject_remote_or_device_path(
        path, code_prefix="AN_LOCK", noun="Agentic-network lock"
    )
    supplied = Path(path)
    lock_path = supplied if supplied.is_absolute() else Path.cwd() / supplied
    raw, resolved = read_local_file_bytes(
        lock_path,
        allowed_root=lock_path.parent,
        trust_root=None,
        code_prefix="AN_LOCK",
        noun="Agentic-network lock",
        max_bytes=MAX_PACK_BYTES,
    )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise error(
            "AN_LOCK_MALFORMED",
            "Agentic-network lock must be UTF-8.",
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
            "AN_LOCK_MALFORMED",
            f"Cannot parse the agentic-network lock: {exc}",
            path=str(resolved),
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema") != LOCK_SCHEMA_ID:
        raise error(
            "AN_LOCK_MALFORMED",
            "Agentic-network lock must declare the "
            f"{LOCK_SCHEMA_ID!r} schema.",
            path=str(resolved),
        )
    validate_payload(payload, "agentic_network_lock_v1.schema.json")
    return payload


def _mismatch(
    code: str, message: str, *, path: str
) -> GovernanceDiagnostic:
    return GovernanceDiagnostic(
        "error", code, message, path=path, source_id=LOCK_SCHEMA_ID
    )


def verify_agentic_network_lock(
    lock_payload: Mapping[str, Any],
    document: Mapping[str, Any],
    composition: CompositionResult,
    *,
    artifacts_dir: str | Path | None = None,
) -> tuple[GovernanceDiagnostic, ...]:
    """Compare a stored lock against the current contract state, fail closed."""

    diagnostics: list[GovernanceDiagnostic] = []
    expected = build_agentic_network_lock(document, composition)

    field_codes = {
        "network_id": "AN_LOCK_NETWORK_MISMATCH",
        "subject_revision": "AN_LOCK_REVISION_MISMATCH",
        "source_contract_digest": "AN_LOCK_SOURCE_STALE",
        "profile": "AN_LOCK_PROFILE_MISMATCH",
        "modules": "AN_LOCK_MODULE_MISMATCH",
        "block_schemas": "AN_LOCK_SCHEMA_MISMATCH",
        "structural_checks": "AN_LOCK_CHECKS_MISMATCH",
        "runtime_events_schema": "AN_LOCK_SCHEMA_MISMATCH",
        "protocol_declarations": "AN_LOCK_PROTOCOL_MISMATCH",
        "approval_requirements": "AN_LOCK_APPROVAL_MISMATCH",
        "evidence_requirements": "AN_LOCK_EVIDENCE_MISMATCH",
        "lock_format_version": "AN_LOCK_FORMAT_MISMATCH",
        "generation_format_version": "AN_LOCK_FORMAT_MISMATCH",
    }
    for field, code in field_codes.items():
        if lock_payload.get(field) != expected.get(field):
            diagnostics.append(
                _mismatch(
                    code,
                    f"Lock field {field!r} does not match the current contract "
                    "state.",
                    path=field,
                )
            )

    locked_records = (
        lock_payload.get("records")
        if isinstance(lock_payload.get("records"), Mapping)
        else {}
    )
    for collection, expected_entries in expected["records"].items():
        locked_entries = locked_records.get(collection)
        if locked_entries != expected_entries:
            diagnostics.append(
                _mismatch(
                    "AN_LOCK_RECORD_MISMATCH",
                    f"Locked {collection} digests do not match the current "
                    "contract records.",
                    path=f"records.{collection}",
                )
            )

    locked_artifacts = {
        str(item.get("path")): str(item.get("sha256"))
        for item in _items(lock_payload.get("artifacts"))
    }
    expected_artifacts = {
        str(item["path"]): str(item["sha256"]) for item in expected["artifacts"]
    }
    for path_name in sorted(set(locked_artifacts) | set(expected_artifacts)):
        if locked_artifacts.get(path_name) != expected_artifacts.get(path_name):
            diagnostics.append(
                _mismatch(
                    "AN_LOCK_ARTIFACT_MISMATCH",
                    f"Locked artifact hash for {path_name!r} does not match the "
                    "regenerated artifact.",
                    path=f"artifacts.{path_name}",
                )
            )

    if artifacts_dir is not None:
        reject_remote_or_device_path(
            artifacts_dir, code_prefix="AN_ARTIFACT", noun="Artifact directory"
        )
        directory = Path(artifacts_dir)
        for path_name, expected_hash in sorted(locked_artifacts.items()):
            target = directory / path_name
            try:
                metadata = os.lstat(target)
            except FileNotFoundError:
                diagnostics.append(
                    _mismatch(
                        "AN_LOCK_ARTIFACT_MISSING",
                        f"Locked artifact {path_name!r} is missing on disk.",
                        path=f"artifacts.{path_name}",
                    )
                )
                continue
            except OSError as exc:
                diagnostics.append(
                    _mismatch(
                        "AN_LOCK_ARTIFACT_MISSING",
                        f"Cannot inspect locked artifact {path_name!r}: {exc}",
                        path=f"artifacts.{path_name}",
                    )
                )
                continue
            if not stat.S_ISREG(metadata.st_mode):
                diagnostics.append(
                    _mismatch(
                        "AN_LOCK_ARTIFACT_MISMATCH",
                        f"Locked artifact {path_name!r} must be a regular file.",
                        path=f"artifacts.{path_name}",
                    )
                )
                continue
            if _sha256_hex(target.read_bytes()) != expected_hash:
                diagnostics.append(
                    _mismatch(
                        "AN_LOCK_ARTIFACT_MISMATCH",
                        f"On-disk artifact {path_name!r} does not match the "
                        "locked hash.",
                        path=f"artifacts.{path_name}",
                    )
                )
        if directory.is_dir():
            for entry in sorted(directory.iterdir()):
                if not entry.is_file():
                    continue
                if entry.name not in locked_artifacts:
                    diagnostics.append(
                        _mismatch(
                            "AN_LOCK_ARTIFACT_UNEXPECTED",
                            f"Unexpected governed artifact {entry.name!r} in the "
                            "artifact directory.",
                            path=f"artifacts.{entry.name}",
                        )
                    )

    return tuple(
        sorted(
            diagnostics,
            key=lambda item: (item.code, item.path or "", item.message),
        )
    )
