from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
import re
from typing import TYPE_CHECKING, Any, Iterable, Mapping

from .errors import GovernanceError, error
from .models import (
    EffectiveApproval,
    GovernanceDiagnostic,
    GovernanceModule,
    NormalizedApproval,
    ProfilePack,
    immutable_mapping,
)
from .schemas import canonical_pack_hash, validate_payload

if TYPE_CHECKING:
    from .registry import GovernanceRegistry


ROLE_FIELDS = (
    "eligible_roles",
    "eligible_approver_roles",
    "approver_roles",
    "approvers",
    "eligible_approvers",
)
ROLE_MARKERS = ("role", "approver", "authorized", "people")

# These categories are intrinsically unable to hold approval authority. Packs
# and documents cannot redeclare them as human actors.
CORE_DENIED_ACTOR_TYPES = (
    "ai_tool",
    "execution_surface",
    "autonomous_agent",
    "model",
    "connector",
    "generated_output",
)
NON_HUMAN_AUTHORITY_EXACT = frozenset(
    (*CORE_DENIED_ACTOR_TYPES, "tool", "agent", "system", "service", "external_service")
)
NON_HUMAN_AUTHORITY_PREFIXES = (
    "ai_tool:",
    "execution_surface:",
    "autonomous_agent:",
    "agent:",
    "model:",
    "connector:",
    "generated_output:",
    "tool:",
    "system:",
    "service:",
    "external_service:",
)
TRUSTED_APPROVAL_RESOLUTIONS = {
    "complete",
    "reference_only",
    "legacy_text_preserved",
    "requirement_only",
}
APPROVAL_SHAPES = {
    "ordinary_approval",
    "generated_profile_approval",
    "governed_package_gate",
    "legacy_contract_reference",
    "legacy_goal_text",
    "legacy_boolean_requirement",
}
APPROVAL_TIMINGS = {
    "before_action",
    "before_merge",
    "before_release",
    "before_external_write",
    "unspecified",
    "legacy_text",
}
REVISION_KINDS = {"git", "artifact_hash", "package_manifest", "other"}

MAX_NORMALIZED_APPROVAL_BYTES = 128 * 1024
MAX_EFFECTIVE_APPROVAL_BYTES = 512 * 1024
MAX_EFFECTIVE_APPROVAL_SOURCES = 32
MAX_APPROVAL_JSON_DEPTH = 40
MAX_APPROVAL_JSON_NODES = 20_000
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_OFFSET_DATE_TIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
)


def is_non_human_authority(value: object) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().casefold()
    return normalized in NON_HUMAN_AUTHORITY_EXACT or normalized.startswith(
        NON_HUMAN_AUTHORITY_PREFIXES
    )


def _diagnostic(code: str, level: str, message: str, path: str) -> GovernanceDiagnostic:
    return GovernanceDiagnostic(level, code, message, path=path)  # type: ignore[arg-type]


def _values(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _strict_strings(
    values: Iterable[Any],
) -> tuple[tuple[str, ...], bool, bool]:
    result: list[str] = []
    duplicate = False
    invalid = False
    for value in values:
        if (
            not isinstance(value, str)
            or not value.strip()
            or value != value.strip()
        ):
            invalid = True
            continue
        if value in result:
            duplicate = True
        else:
            result.append(value)
    return tuple(result), duplicate, invalid


def _field_values(source: Mapping[str, Any], *fields: str) -> list[Any]:
    values: list[Any] = []
    for field in fields:
        values.extend(_values(source.get(field)))
    return values


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _bounded_json(value: Any, *, byte_limit: int) -> bytes:
    nodes = 0
    text_units = 0
    pending: list[tuple[Any, int]] = [(value, 0)]
    while pending:
        node, depth = pending.pop()
        nodes += 1
        if nodes > MAX_APPROVAL_JSON_NODES or depth > MAX_APPROVAL_JSON_DEPTH:
            raise ValueError("approval payload exceeds structural limits")
        if isinstance(node, Mapping):
            text_units += sum(len(key) for key in node if isinstance(key, str))
            pending.extend((child, depth + 1) for child in node.values())
        elif isinstance(node, list):
            pending.extend((child, depth + 1) for child in node)
        elif isinstance(node, str):
            text_units += len(node)
        if text_units > byte_limit:
            raise ValueError("approval payload exceeds its byte limit")
    encoded = _canonical_json(value)
    if len(encoded) > byte_limit:
        raise ValueError("approval payload exceeds its byte limit")
    return encoded


def _derived_identity(shape: str, path: str) -> str:
    digest = hashlib.sha256(
        _canonical_json({"shape": shape, "path": path})
    ).hexdigest()[:24]
    return f"approval:{digest}"


def _source_identity(
    source_value: Any,
    source: Mapping[str, Any],
    *,
    shape: str,
    path: str,
    fallback_id: str,
) -> tuple[str, GovernanceDiagnostic | None]:
    fallback = fallback_id
    if shape == "ordinary_approval":
        field = "name"
    elif shape == "generated_profile_approval":
        field = "id" if "id" in source else "name"
    elif shape == "governed_package_gate":
        field = "id"
    elif shape == "legacy_contract_reference":
        if (
            isinstance(source_value, str)
            and source_value.strip()
            and source_value == source_value.strip()
        ):
            return f"reference:{source_value}", None
        return fallback, _diagnostic(
            "APPROVAL_IDENTITY_INVALID",
            "error",
            "Approval source identities must be non-empty source strings.",
            path,
        )
    else:
        return fallback, None

    if field not in source:
        return fallback, None
    value = source[field]
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        return fallback, _diagnostic(
            "APPROVAL_IDENTITY_INVALID",
            "error",
            "Approval source identities must be non-empty source strings.",
            path,
        )
    return value, None


def _strict_revision_binding(
    value: Any,
    *,
    path: str,
) -> tuple[Mapping[str, Any] | None, GovernanceDiagnostic | None]:
    if value is None:
        return None, None
    if not isinstance(value, Mapping):
        return None, _diagnostic(
            "APPROVAL_REVISION_BINDING_INVALID",
            "error",
            "Approval revision_binding must be an exact structured binding.",
            path,
        )
    expected = {"kind", "revision", "exact", "scope_hash"}
    kind = value.get("kind")
    revision = value.get("revision")
    exact = value.get("exact")
    scope_hash = value.get("scope_hash")
    invalid = (
        set(value) - expected
        or not isinstance(kind, str)
        or kind not in REVISION_KINDS
        or not isinstance(revision, str)
        or not revision.strip()
        or revision != revision.strip()
        or exact is not True
        or (
            scope_hash is not None
            and (
                not isinstance(scope_hash, str)
                or _SHA256_RE.fullmatch(scope_hash) is None
            )
        )
    )
    if invalid:
        return None, _diagnostic(
            "APPROVAL_REVISION_BINDING_INVALID",
            "error",
            "Approval revision_binding requires an allowed kind, a non-empty "
            "source revision, exact=true, and an optional sha256 scope hash.",
            path,
        )
    return immutable_mapping(value), None


def _valid_offset_timestamp(value: str) -> bool:
    if _OFFSET_DATE_TIME_RE.fullmatch(value) is None:
        return False
    normalized = value.replace("t", "T", 1)
    if normalized[-1] in {"Z", "z"}:
        normalized = f"{normalized[:-1]}+00:00"
    try:
        return datetime.fromisoformat(normalized).tzinfo is not None
    except ValueError:
        return False


def normalize_approval(
    source_value: Mapping[str, Any] | str | bool,
    *,
    shape: str,
    path: str,
    fallback_id: str,
) -> NormalizedApproval:
    """Normalize one source approval without coercing authority metadata.

    ``fallback_id`` remains the legacy in-memory/public-v1 fallback for API
    compatibility. The verifiable v2 representation instead derives its
    fallback solely from the source shape and canonical source path.
    """

    if shape not in APPROVAL_SHAPES:
        raise error("APPROVAL_SOURCE_SHAPE_INVALID", f"Unknown approval shape {shape!r}.")
    if not isinstance(path, str) or not path.strip() or path != path.strip():
        raise error(
            "APPROVAL_SOURCE_PATH_INVALID",
            "Approval source paths must be non-empty canonical strings.",
        )
    retained_fallback = (
        fallback_id
        if isinstance(fallback_id, str)
        and fallback_id.strip()
        and fallback_id == fallback_id.strip()
        else _derived_identity(shape, path)
    )

    raw = (
        deepcopy(dict(source_value))
        if isinstance(source_value, Mapping)
        else deepcopy(source_value)
    )
    source = deepcopy(dict(source_value)) if isinstance(source_value, Mapping) else {}
    role_field = next((field for field in ROLE_FIELDS if field in source), "none")

    eligible, duplicate_eligible, invalid_eligible = _strict_strings(
        _field_values(source, *ROLE_FIELDS)
    )
    required, duplicate_required, invalid_required = _strict_strings(
        _field_values(source, "required_roles")
    )
    explicit_surfaces, duplicate_surfaces, invalid_surfaces = _strict_strings(
        _field_values(source, "denied_execution_surfaces")
    )
    denied, duplicate_denied, invalid_denied = _strict_strings(
        _field_values(source, "denied_approver_types", "denied_actor_types")
    )
    evidence, duplicate_evidence, invalid_evidence = _strict_strings(
        _field_values(source, "required_evidence")
    )
    actions, duplicate_actions, invalid_actions = _strict_strings(
        _field_values(
            source,
            "required_for",
            "actions",
            "actions_requiring_approval",
        )
    )
    invalidation, duplicate_invalidation, invalid_invalidation = _strict_strings(
        _field_values(source, "invalidation_conditions")
    )

    denied_surfaces = tuple(
        item
        for item in (*denied, *explicit_surfaces)
        if item == "execution_surface" or item in explicit_surfaces
    )
    denied_surfaces = tuple(dict.fromkeys(denied_surfaces))
    denied_actors = tuple(item for item in denied if item not in set(denied_surfaces))
    diagnostics: list[GovernanceDiagnostic] = []

    if any(
        (
            invalid_eligible,
            invalid_required,
            invalid_surfaces,
            invalid_denied,
            invalid_evidence,
            invalid_actions,
        )
    ):
        diagnostics.append(
            _diagnostic(
                "APPROVAL_VALUE_TYPE_INVALID",
                "error",
                "Approval roles, denials, evidence, and actions must be "
                "canonical non-empty source strings.",
                path,
            )
        )
    if any(
        (
            duplicate_eligible,
            duplicate_required,
            duplicate_surfaces,
            duplicate_denied,
            duplicate_evidence,
            duplicate_actions,
        )
    ):
        diagnostics.append(
            _diagnostic(
                "APPROVAL_DUPLICATE_ROLE_NORMALIZED",
                "info",
                "Duplicate approval values were removed in first-seen order.",
                path,
            )
        )
    if invalid_invalidation or duplicate_invalidation:
        diagnostics.append(
            _diagnostic(
                "APPROVAL_INVALIDATION_CONDITION_INVALID",
                "error",
                "Invalidation conditions must be unique canonical source strings.",
                path,
            )
        )

    known_role_fields = set(ROLE_FIELDS) | {
        "required_roles",
        "denied_approver_types",
        "denied_actor_types",
        "denied_execution_surfaces",
    }
    unknown = sorted(
        key
        for key in source
        if key not in known_role_fields and any(marker in key for marker in ROLE_MARKERS)
    )
    if unknown:
        diagnostics.append(
            _diagnostic(
                "APPROVAL_UNKNOWN_ROLE_FIELD",
                "error",
                f"Unknown role-bearing fields: {', '.join(unknown)}.",
                path,
            )
        )

    core_conflict = {
        item for item in (*eligible, *required) if is_non_human_authority(item)
    }
    if core_conflict:
        diagnostics.append(
            _diagnostic(
                "APPROVAL_CORE_DENIED_ACTOR_ELIGIBLE",
                "error",
                "Non-human identities can never be eligible or required approvers: "
                f"{', '.join(sorted(core_conflict))}.",
                path,
            )
        )
    denied_all = set(denied_actors) | set(denied_surfaces)
    if set(eligible) & denied_all:
        diagnostics.append(
            _diagnostic(
                "APPROVAL_ACTOR_ELIGIBLE_AND_DENIED",
                "error",
                "An actor category cannot be both eligible and denied.",
                path,
            )
        )
    if required and not set(required) <= set(eligible):
        diagnostics.append(
            _diagnostic(
                "APPROVAL_REQUIRED_ROLE_NOT_ELIGIBLE",
                "error",
                "Every required role must also be eligible.",
                path,
            )
        )
    if shape == "governed_package_gate" and not eligible:
        diagnostics.append(
            _diagnostic(
                "APPROVAL_MISSING_ELIGIBLE_ROLES",
                "error",
                "Governed-package approval gates require an eligible role field.",
                path,
            )
        )
    if shape == "governed_package_gate" and not (
        eligible or required or evidence or actions
    ):
        diagnostics.append(
            _diagnostic(
                "APPROVAL_EMPTY_REQUIREMENT",
                "error",
                "An approval gate with no roles, evidence, or actions is invalid.",
                path,
            )
        )

    accountable_authority = source.get("accountable_authority")
    if accountable_authority is not None and (
        not isinstance(accountable_authority, str)
        or not accountable_authority.strip()
        or accountable_authority != accountable_authority.strip()
    ):
        diagnostics.append(
            _diagnostic(
                "APPROVAL_ACCOUNTABLE_AUTHORITY_INVALID",
                "error",
                "Approval accountable authority must be a canonical non-empty "
                "source string.",
                path,
            )
        )
        accountable_authority = None
    elif is_non_human_authority(accountable_authority):
        diagnostics.append(
            _diagnostic(
                "APPROVAL_NON_HUMAN_AUTHORITY",
                "error",
                "Approval accountable authority must identify a human role or actor.",
                path,
            )
        )
        accountable_authority = None

    exact_revision_required = source.get("exact_revision_required", False)
    if not isinstance(exact_revision_required, bool):
        diagnostics.append(
            _diagnostic(
                "APPROVAL_EXACT_REVISION_REQUIREMENT_INVALID",
                "error",
                "exact_revision_required must be a boolean.",
                path,
            )
        )
        exact_revision_required = False

    expires_after = source.get("expires_after")
    if expires_after is not None and (
        not isinstance(expires_after, str)
        or not expires_after.strip()
        or expires_after != expires_after.strip()
    ):
        diagnostics.append(
            _diagnostic(
                "APPROVAL_EXPIRY_REQUIREMENT_INVALID",
                "error",
                "expires_after must be a canonical non-empty duration string.",
                path,
            )
        )
        expires_after = None

    normalized_id, identity_diagnostic = _source_identity(
        source_value,
        source,
        shape=shape,
        path=path,
        fallback_id=retained_fallback,
    )
    if identity_diagnostic is not None:
        diagnostics.append(identity_diagnostic)

    default_timing = "legacy_text" if shape == "legacy_goal_text" else "unspecified"
    timing = source.get("timing", default_timing)
    if not isinstance(timing, str) or timing not in APPROVAL_TIMINGS:
        diagnostics.append(
            _diagnostic(
                "APPROVAL_TIMING_INVALID",
                "error",
                "Approval timing must use one supported source string.",
                path,
            )
        )
        timing = default_timing

    revision_binding, revision_diagnostic = _strict_revision_binding(
        source.get("revision_binding"),
        path=path,
    )
    if revision_diagnostic is not None:
        diagnostics.append(revision_diagnostic)

    expires_at = source.get("expires_at")
    if expires_at is not None and (
        not isinstance(expires_at, str)
        or expires_at != expires_at.strip()
        or not _valid_offset_timestamp(expires_at)
    ):
        diagnostics.append(
            _diagnostic(
                "APPROVAL_EXPIRY_INVALID",
                "error",
                "Approval expiry must be a valid offset timestamp source string.",
                path,
            )
        )
        expires_at = None

    if shape == "legacy_contract_reference":
        resolution = "reference_only"
    elif shape == "legacy_goal_text":
        resolution = "legacy_text_preserved"
    elif shape == "legacy_boolean_requirement":
        resolution = "requirement_only"
    else:
        resolution = "complete"
    if any(item.level == "error" for item in diagnostics):
        resolution = "invalid"

    normalized = NormalizedApproval(
        id=normalized_id,
        required_roles=required,
        eligible_roles=eligible,
        denied_actor_types=denied_actors,
        denied_execution_surfaces=denied_surfaces,
        required_evidence=evidence,
        actions_requiring_approval=actions,
        timing=timing,
        accountable_authority=accountable_authority,
        revision_binding=revision_binding,
        exact_revision_required=exact_revision_required,
        invalidation_conditions=invalidation,
        expires_after=expires_after,
        expires_at=expires_at,
        resolution=resolution,
        diagnostics=tuple(diagnostics),
        source_shape=shape,
        source_path=path,
        source_raw=raw,
        role_field=role_field,
    )
    validate_payload(
        normalized.to_verifiable_dict(),
        "governance_approval_model_v2.schema.json",
    )
    return normalized


def _source_binding(source: Mapping[str, Any]) -> str:
    unsigned = {key: deepcopy(value) for key, value in source.items() if key != "binding"}
    return "sha256:" + hashlib.sha256(_canonical_json(unsigned)).hexdigest()


def trusted_normalized_approval(
    item: Mapping[str, Any],
    *,
    expected_shape: str | None = None,
    expected_path: str | None = None,
    expected_source: Any | None = None,
) -> NormalizedApproval | None:
    """Re-derive a claimed normalized approval from retained source.

    V2 binds all retained source metadata for mutation detection. Optional
    expected context is the authenticity boundary when the caller knows the
    actual document or pack location. Legacy v1 remains accepted for existing
    callers, but only v2 is used in newly emitted trust-boundary artifacts.
    """

    try:
        schema = item.get("schema")
        if schema == "nornyx.normalized_approval.v2":
            _bounded_json(item, byte_limit=MAX_NORMALIZED_APPROVAL_BYTES)
            validate_payload(dict(item), "governance_approval_model_v2.schema.json")
            source = item["source"]
            if source["binding"] != _source_binding(source):
                return None
            derived_fallback = _derived_identity(source["shape"], source["path"])
            if source["fallback_id"] != derived_fallback:
                return None
            verifiable = True
            fallback_id = derived_fallback
        elif schema == "nornyx.normalized_approval.v1":
            _bounded_json(item, byte_limit=MAX_NORMALIZED_APPROVAL_BYTES)
            validate_payload(dict(item), "governance_approval_model_v1.schema.json")
            source = item["source"]
            verifiable = False
            fallback_id = _derived_identity(source["shape"], source["path"])
        else:
            return None
        shape = source["shape"]
        path = source["path"]
        raw = source["raw"]
        if not isinstance(shape, str) or not isinstance(path, str):
            return None
        if expected_shape is not None and shape != expected_shape:
            return None
        if expected_path is not None and path != expected_path:
            return None
        if expected_source is not None and raw != expected_source:
            return None
        renormalized = normalize_approval(
            raw,
            shape=shape,
            path=path,
            fallback_id=fallback_id,
        )
    except (
        GovernanceError,
        AttributeError,
        KeyError,
        RecursionError,
        TypeError,
        ValueError,
    ):
        return None
    expected = (
        renormalized.to_verifiable_dict()
        if verifiable
        else renormalized.to_legacy_dict()
    )
    if expected != dict(item):
        return None
    if renormalized.resolution not in TRUSTED_APPROVAL_RESOLUTIONS:
        return None
    return renormalized


def _ordered_union(*groups: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for group in groups:
        for value in group:
            if value not in result:
                result.append(value)
    return tuple(result)


def _one_declared_value(
    sources: tuple[NormalizedApproval, ...],
    field: str,
    *,
    unspecified: tuple[Any, ...] = (None,),
) -> Any:
    values: list[Any] = []
    for source in sources:
        value = getattr(source, field)
        if value in unspecified:
            continue
        comparable = dict(value) if isinstance(value, Mapping) else value
        if comparable not in values:
            values.append(comparable)
    if len(values) > 1:
        raise error(
            "PACK_MONOTONICITY_APPROVAL",
            f"Approval {sources[0].id!r} has conflicting {field} values.",
        )
    return values[0] if values else None


def compose_effective_approval(
    source_values: Iterable[tuple[NormalizedApproval, Mapping[str, Any]]],
) -> EffectiveApproval:
    """Compose trusted leaves into one deterministic monotonic approval."""

    prepared: list[tuple[NormalizedApproval, dict[str, Any], str]] = []
    prepared_provenance: set[bytes] = set()
    for source_index, (normalized, provenance_value) in enumerate(source_values):
        if source_index >= MAX_EFFECTIVE_APPROVAL_SOURCES:
            raise error(
                "PACK_APPROVAL_SOURCE_LIMIT_EXCEEDED",
                "Effective approvals accept at most "
                f"{MAX_EFFECTIVE_APPROVAL_SOURCES} source approvals.",
            )
        if normalized.resolution != "complete":
            raise GovernanceError(*normalized.diagnostics)
        approval_payload = normalized.to_verifiable_dict()
        trusted = trusted_normalized_approval(approval_payload)
        if trusted is None:
            raise error(
                "PACK_MONOTONICITY_APPROVAL",
                "An approval source could not be independently re-normalized.",
            )
        provenance = deepcopy(dict(provenance_value))
        source_hash = "sha256:" + hashlib.sha256(
            _canonical_json(approval_payload)
        ).hexdigest()
        provenance_identity = _canonical_json(provenance)
        if provenance_identity in prepared_provenance:
            raise error(
                "PACK_APPROVAL_PROVENANCE_INVALID",
                "Effective approval sources must not repeat the same pack leaf.",
            )
        prepared_provenance.add(provenance_identity)
        prepared.append((trusted, provenance, source_hash))
    if not prepared:
        raise error(
            "PACK_APPROVAL_SOURCE_LIMIT_EXCEEDED",
            "Effective approvals require at least one source approval.",
        )
    prepared.sort(
        key=lambda item: (
            _canonical_json(item[1]),
            item[0].source_path.encode("utf-8"),
            item[2].encode("ascii"),
        )
    )
    sources = tuple(item[0] for item in prepared)
    identifiers = {item.id for item in sources}
    if len(identifiers) != 1:
        raise error(
            "PACK_MONOTONICITY_APPROVAL",
            "Only approval sources with the same canonical identity may compose.",
        )

    restricted_sources = tuple(source for source in sources if source.eligible_roles)
    if restricted_sources:
        eligible_set = set(restricted_sources[0].eligible_roles)
        for source in restricted_sources[1:]:
            eligible_set &= set(source.eligible_roles)
        eligible_roles = tuple(
            role for role in restricted_sources[0].eligible_roles if role in eligible_set
        )
    else:
        eligible_roles = ()
    required_roles = _ordered_union(*(item.required_roles for item in sources))
    if required_roles and not set(required_roles) <= set(eligible_roles):
        raise error(
            "PACK_MONOTONICITY_APPROVAL",
            f"Approval {sources[0].id!r} requires a role excluded by another layer.",
        )
    if len(restricted_sources) > 1 and not eligible_roles:
        raise error(
            "PACK_MONOTONICITY_APPROVAL",
            f"Approval {sources[0].id!r} has disjoint eligible-role restrictions.",
        )

    denied_actor_types = _ordered_union(
        *(item.denied_actor_types for item in sources),
        CORE_DENIED_ACTOR_TYPES,
    )
    denied_execution_surfaces = _ordered_union(
        *(item.denied_execution_surfaces for item in sources),
        ("execution_surface",),
    )
    contradictory = set(eligible_roles) & (
        set(denied_actor_types) | set(denied_execution_surfaces)
    )
    if contradictory:
        raise error(
            "PACK_MONOTONICITY_APPROVAL",
            f"Approval {sources[0].id!r} makes denied actors eligible: "
            f"{sorted(contradictory)}.",
        )

    timing = _one_declared_value(
        sources,
        "timing",
        unspecified=(None, "unspecified"),
    ) or "unspecified"
    accountable_authority = _one_declared_value(sources, "accountable_authority")
    revision_binding_value = _one_declared_value(sources, "revision_binding")
    revision_binding = (
        immutable_mapping(revision_binding_value)
        if isinstance(revision_binding_value, Mapping)
        else None
    )
    expires_after = _one_declared_value(sources, "expires_after")
    expires_at = _one_declared_value(sources, "expires_at")

    source_records: list[Mapping[str, Any]] = []
    source_order: list[str] = []
    for position, (normalized, provenance, source_hash) in enumerate(prepared):
        source_id = provenance.get("source_id")
        source_index = provenance.get("source_index")
        if (
            not isinstance(source_id, str)
            or not source_id.strip()
            or source_id != source_id.strip()
            or type(source_index) is not int
        ):
            raise error(
                "PACK_APPROVAL_PROVENANCE_INVALID",
                "Approval provenance requires a canonical source ID and integer index.",
            )
        expected_path = f"{source_id}.approval_requirements[{source_index}]"
        if (
            provenance.get("approval_path") != expected_path
            or normalized.source_path != expected_path
        ):
            raise error(
                "PACK_APPROVAL_PROVENANCE_INVALID",
                "Approval provenance ID, index, and path must bind the normalized source path.",
            )
        source_order.append(normalized.source_path)
        source_records.append(
            immutable_mapping(
                {
                    "position": position,
                    "hash": source_hash,
                    "approval": normalized.to_verifiable_dict(),
                    "provenance": provenance,
                }
            )
        )

    decisions = immutable_mapping(
        {
            "eligible_roles": "intersection_of_non_empty_sets",
            "required_roles": "ordered_union_then_subset_check",
            "denials": "ordered_union_with_intrinsic_core",
            "requirements": "ordered_union",
            "scalar_fields": "equal_or_single_declared_value",
            "source_order": source_order,
        }
    )
    effective = EffectiveApproval(
        id=sources[0].id,
        required_roles=required_roles,
        eligible_roles=eligible_roles,
        denied_actor_types=denied_actor_types,
        denied_execution_surfaces=denied_execution_surfaces,
        required_evidence=_ordered_union(
            *(item.required_evidence for item in sources)
        ),
        actions_requiring_approval=_ordered_union(
            *(item.actions_requiring_approval for item in sources)
        ),
        timing=timing,
        accountable_authority=accountable_authority,
        revision_binding=revision_binding,
        exact_revision_required=any(
            item.exact_revision_required for item in sources
        ),
        invalidation_conditions=_ordered_union(
            *(item.invalidation_conditions for item in sources)
        ),
        expires_after=expires_after,
        expires_at=expires_at,
        sources=tuple(source_records),
        decisions=decisions,
    )
    _bounded_json(effective.to_dict(), byte_limit=MAX_EFFECTIVE_APPROVAL_BYTES)
    validate_payload(
        effective.to_dict(),
        "effective_approval_v1.schema.json",
    )
    return effective


def _trusted_provenance_source(
    provenance: Mapping[str, Any],
    approval_payload: Mapping[str, Any],
    *,
    registry: GovernanceRegistry,
) -> bool:
    source_id = provenance.get("source_id")
    source_kind = provenance.get("source_kind")
    source_index = provenance.get("source_index")
    if not isinstance(source_id, str) or type(source_index) is not int:
        return False
    try:
        if source_kind == "profile":
            pack = registry.resolve_profile(source_id)
            if not isinstance(pack, ProfilePack):
                return False
        elif source_kind == "module":
            pack = registry.resolve_module(source_id)
            if not isinstance(pack, GovernanceModule):
                return False
        else:
            return False
    except GovernanceError:
        return False
    if pack.id != source_id:
        return False
    expected_path = f"{pack.id}.approval_requirements[{source_index}]"
    if provenance.get("approval_path") != expected_path:
        return False
    expected_provenance = {
        "source_id": pack.id,
        "source_kind": "module" if isinstance(pack, GovernanceModule) else "profile",
        "source_version": pack.version,
        "source_tier": pack.provenance.source_tier,
        "source_path": pack.provenance.source_path,
        "approval_path": expected_path,
        "source_index": source_index,
        "content_hash": pack.content_hash,
    }
    if dict(provenance) != expected_provenance:
        return False
    raw_pack = pack.as_dict()
    expected_schema = (
        "governance_module_v1.schema.json"
        if isinstance(pack, GovernanceModule)
        else "profile_pack_v1.schema.json"
    )
    validate_payload(raw_pack, expected_schema)
    integrity = raw_pack.get("integrity")
    raw_provenance = raw_pack.get("provenance")
    if (
        canonical_pack_hash(raw_pack) != pack.content_hash
        or not isinstance(integrity, Mapping)
        or integrity.get("content_hash") != pack.content_hash
        or raw_pack.get("id") != pack.id
        or raw_pack.get("version") != pack.version
        or not isinstance(raw_provenance, Mapping)
        or (
            pack.provenance.source_tier == "builtin"
            and raw_provenance.get("source_tier") != "builtin"
        )
        or raw_provenance.get("source_revision")
        != pack.provenance.source_revision
        or raw_provenance.get("author") != pack.provenance.author
    ):
        return False
    raw_approvals = raw_pack.get("approval_requirements")
    if (
        not isinstance(raw_approvals, list)
        or source_index < 0
        or source_index >= len(raw_approvals)
        or source_index >= len(pack.approval_requirements)
    ):
        return False
    raw_approval = raw_approvals[source_index]
    if (
        not isinstance(raw_approval, Mapping)
        or dict(pack.approval_requirements[source_index]) != dict(raw_approval)
        or approval_payload.get("source", {}).get("raw") != raw_approval
    ):
        return False
    return trusted_normalized_approval(
        approval_payload,
        expected_shape="generated_profile_approval",
        expected_path=expected_path,
        expected_source=raw_approval,
    ) is not None


def trusted_effective_approval(
    item: Mapping[str, Any],
    *,
    registry: GovernanceRegistry | None = None,
) -> EffectiveApproval | None:
    """Recompute an effective approval and authenticate every source pack.

    Built-in-only provenance is checked against the packaged catalog. Any
    project, organization, or explicit-path source requires the caller's
    already established registry as the independent trust context.
    """

    try:
        _bounded_json(item, byte_limit=MAX_EFFECTIVE_APPROVAL_BYTES)
        validate_payload(dict(item), "effective_approval_v1.schema.json")
        raw_sources = item["sources"]
        if not isinstance(raw_sources, list) or not (
            1 <= len(raw_sources) <= MAX_EFFECTIVE_APPROVAL_SOURCES
        ):
            return None
        provenances = [
            source.get("provenance") if isinstance(source, Mapping) else None
            for source in raw_sources
        ]
        if any(not isinstance(value, Mapping) for value in provenances):
            return None
        has_builtin = any(
            value.get("source_tier") == "builtin" for value in provenances
        )
        has_non_builtin = any(
            value.get("source_tier") != "builtin" for value in provenances
        )
        if has_non_builtin and registry is None:
            return None
        builtin_registry = None
        if has_builtin:
            from .registry import GovernanceRegistry

            builtin_registry = GovernanceRegistry.builtins()
        source_values: list[tuple[NormalizedApproval, Mapping[str, Any]]] = []
        seen_provenance: set[bytes] = set()
        for index, raw_source in enumerate(raw_sources):
            if not isinstance(raw_source, Mapping) or raw_source.get("position") != index:
                return None
            approval_payload = raw_source.get("approval")
            provenance = raw_source.get("provenance")
            source_hash = raw_source.get("hash")
            if not isinstance(approval_payload, Mapping) or not isinstance(
                provenance, Mapping
            ):
                return None
            expected_hash = "sha256:" + hashlib.sha256(
                _canonical_json(approval_payload)
            ).hexdigest()
            if source_hash != expected_hash:
                return None
            approval_path = provenance.get("approval_path")
            if not isinstance(approval_path, str):
                return None
            normalized = trusted_normalized_approval(
                approval_payload,
                expected_path=approval_path,
            )
            source_registry = (
                builtin_registry
                if provenance.get("source_tier") == "builtin"
                else registry
            )
            if (
                normalized is None
                or source_registry is None
                or not _trusted_provenance_source(
                    provenance,
                    approval_payload,
                    registry=source_registry,
                )
            ):
                return None
            provenance_identity = _canonical_json(provenance)
            if provenance_identity in seen_provenance:
                return None
            seen_provenance.add(provenance_identity)
            source_values.append((normalized, provenance))
        recomputed = compose_effective_approval(source_values)
    except (
        GovernanceError,
        AttributeError,
        KeyError,
        OSError,
        RecursionError,
        TypeError,
        ValueError,
    ):
        return None
    if recomputed.to_dict() != dict(item):
        return None
    return recomputed
