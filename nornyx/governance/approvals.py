from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .models import GovernanceDiagnostic, NormalizedApproval, immutable_mapping
from .errors import GovernanceError
from .schemas import validate_payload


ROLE_FIELDS = (
    "eligible_roles",
    "eligible_approver_roles",
    "approver_roles",
    "approvers",
    "eligible_approvers",
)
ROLE_MARKERS = ("role", "approver", "authorized", "people")
# Intrinsic, non-declarable prohibition: these actor categories can never be
# eligible or required approvers, regardless of what any document declares.
CORE_DENIED_ACTOR_TYPES = (
    "ai_tool",
    "execution_surface",
    "autonomous_agent",
    "model",
    "connector",
    "generated_output",
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


def is_non_human_authority(value: object) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.casefold()
    return normalized in CORE_DENIED_ACTOR_TYPES or normalized.startswith(
        NON_HUMAN_AUTHORITY_PREFIXES
    )


def _as_values(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _unique(values: list[Any]) -> tuple[tuple[str, ...], bool, bool]:
    result: list[str] = []
    duplicate = False
    invalid = False
    for value in values:
        if not isinstance(value, str) or not value:
            invalid = True
            continue
        if value in result:
            duplicate = True
        else:
            result.append(value)
    return tuple(result), duplicate, invalid


def _diagnostic(code: str, level: str, message: str, path: str) -> GovernanceDiagnostic:
    return GovernanceDiagnostic(level, code, message, path=path)  # type: ignore[arg-type]


def normalize_approval(
    source_value: Mapping[str, Any] | str | bool,
    *,
    shape: str,
    path: str,
    fallback_id: str,
) -> NormalizedApproval:
    raw = deepcopy(dict(source_value)) if isinstance(source_value, Mapping) else deepcopy(source_value)
    source = deepcopy(dict(source_value)) if isinstance(source_value, Mapping) else {}
    role_field = next((field for field in ROLE_FIELDS if field in source), "none")
    eligible_values: list[Any] = []
    for field in ROLE_FIELDS:
        eligible_values.extend(_as_values(source.get(field)))
    eligible, duplicate_eligible, invalid_eligible = _unique(eligible_values)
    required, duplicate_required, invalid_required = _unique(
        _as_values(source.get("required_roles"))
    )
    denied, duplicate_denied, invalid_denied = _unique(
        _as_values(source.get("denied_approver_types"))
        + _as_values(source.get("denied_actor_types"))
        + _as_values(source.get("denied_execution_surfaces"))
    )
    evidence, duplicate_evidence, invalid_evidence = _unique(
        _as_values(source.get("required_evidence"))
    )
    actions, duplicate_actions, invalid_actions = _unique(
        _as_values(source.get("required_for"))
        + _as_values(source.get("actions"))
        + _as_values(source.get("actions_requiring_approval"))
    )
    explicit_surfaces = set(_as_values(source.get("denied_execution_surfaces")))
    denied_surfaces = tuple(
        item for item in denied if item == "execution_surface" or item in explicit_surfaces
    )
    denied_actors = tuple(item for item in denied if item not in set(denied_surfaces))
    diagnostics: list[GovernanceDiagnostic] = []

    if any(
        (
            invalid_eligible,
            invalid_required,
            invalid_denied,
            invalid_evidence,
            invalid_actions,
        )
    ):
        diagnostics.append(
            _diagnostic(
                "APPROVAL_VALUE_TYPE_INVALID",
                "error",
                "Approval role, denial, evidence, and action values must be "
                "non-empty strings.",
                path,
            )
        )

    if any((duplicate_eligible, duplicate_required, duplicate_denied, duplicate_evidence, duplicate_actions)):
        diagnostics.append(
            _diagnostic(
                "APPROVAL_DUPLICATE_ROLE_NORMALIZED",
                "info",
                "Duplicate approval values were removed in first-seen order.",
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
                "AI tools and execution surfaces can never be eligible or "
                f"required approvers: {', '.join(sorted(core_conflict))}.",
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
    if shape == "governed_package_gate" and not (eligible or required or evidence or actions):
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
    ):
        diagnostics.append(
            _diagnostic(
                "APPROVAL_ACCOUNTABLE_AUTHORITY_INVALID",
                "error",
                "Approval accountable authority must be a non-empty source string.",
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
        not isinstance(expires_after, str) or not expires_after
    ):
        diagnostics.append(
            _diagnostic(
                "APPROVAL_EXPIRY_REQUIREMENT_INVALID",
                "error",
                "expires_after must be a non-empty duration string.",
                path,
            )
        )
        expires_after = None

    if shape in {"ordinary_approval", "generated_profile_approval"}:
        normalized_id = str(source.get("name", fallback_id))
        resolution = "complete"
        timing = "unspecified"
    elif shape == "governed_package_gate":
        normalized_id = str(source.get("id", fallback_id))
        resolution = "complete"
        timing = "unspecified"
    elif shape == "legacy_contract_reference":
        normalized_id = f"reference:{source_value}"
        resolution = "reference_only"
        timing = "unspecified"
    elif shape == "legacy_goal_text":
        normalized_id = fallback_id
        resolution = "legacy_text_preserved"
        timing = "legacy_text"
    else:
        normalized_id = fallback_id
        resolution = "requirement_only"
        timing = "unspecified"
    if any(item.level == "error" for item in diagnostics):
        resolution = "invalid"

    revision_binding = source.get("revision_binding")
    normalized = NormalizedApproval(
        id=normalized_id,
        required_roles=required,
        eligible_roles=eligible,
        denied_actor_types=denied_actors,
        denied_execution_surfaces=denied_surfaces,
        required_evidence=evidence,
        actions_requiring_approval=actions,
        timing=str(source.get("timing", timing)),
        accountable_authority=accountable_authority,
        revision_binding=(
            immutable_mapping(revision_binding)
            if isinstance(revision_binding, Mapping)
            else None
        ),
        exact_revision_required=exact_revision_required,
        invalidation_conditions=tuple(str(item) for item in _as_values(source.get("invalidation_conditions"))),
        expires_after=expires_after,
        expires_at=str(source["expires_at"]) if source.get("expires_at") is not None else None,
        resolution=resolution,
        diagnostics=tuple(diagnostics),
        source_shape=shape,
        source_path=path,
        source_raw=raw,
        role_field=role_field,
    )
    validate_payload(normalized.to_dict(), "governance_approval_model_v1.schema.json")
    return normalized


def trusted_normalized_approval(item: Mapping[str, Any]) -> NormalizedApproval | None:
    """Re-derive a claimed normalized approval from its retained source."""
    try:
        validate_payload(dict(item), "governance_approval_model_v1.schema.json")
        source = item["source"]
        renormalized = normalize_approval(
            source["raw"],
            shape=str(source["shape"]),
            path=str(source["path"]),
            fallback_id=str(item["id"]),
        )
    except (GovernanceError, AttributeError, KeyError, TypeError, ValueError):
        return None
    if renormalized.to_dict() != dict(item):
        return None
    if renormalized.resolution not in TRUSTED_APPROVAL_RESOLUTIONS:
        return None
    return renormalized
