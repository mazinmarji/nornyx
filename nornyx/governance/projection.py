from __future__ import annotations

from types import MappingProxyType
from typing import Any

from .errors import GovernanceError
from .models import (
    GovernanceDiagnostic,
    ProfilePack,
    ProjectionReport,
    ProjectionResult,
)
from .schemas import validate_payload


def _failure(code: str, message: str, profile: ProfilePack) -> GovernanceError:
    return GovernanceError(
        GovernanceDiagnostic("error", code, message, source_id=profile.id)
    )


def project_profile_to_v03(profile: ProfilePack) -> ProjectionResult:
    raw = profile.as_dict()
    legacy = raw["compatibility"]["legacy_v0_3"]
    if not legacy["supported"] or legacy["mode"] != "exact_v0_3_view":
        raise _failure(
            "PROFILE_PROJECTION_UNSUPPORTED",
            f"Profile {profile.id!r} does not support an exact v0.3 view.",
            profile,
        )
    blocked = sorted(set(legacy["must_preserve"]) & set(legacy["omitted_fields"]))
    if blocked:
        raise _failure(
            "PROFILE_PROJECTION_REQUIRED_FIELD_OMITTED",
            f"Projection would omit must-preserve fields: {', '.join(blocked)}.",
            profile,
        )
    projected: dict[str, Any] = {
        "name": raw["name"],
        "version": "v0.3",
        "core_surface": "v0.2",
        "status": "optional_profile",
        "purpose": raw["purpose"],
        "domain": raw["domain"],
        "required_blocks": raw["required_blocks"],
        "recommended_blocks": raw["recommended_blocks"],
        "graph_node_kinds": raw["graph"]["node_kinds"],
        "validation_rules": legacy["validation_rules"],
        "conformance": legacy["conformance"],
        "non_goals": raw["non_goals"],
        "core_concepts": legacy["core_concepts"],
    }
    validate_payload(projected, "domain_profile_pack.schema.json")
    diagnostic = GovernanceDiagnostic(
        "warning",
        "PROFILE_PROJECTION_LOSS_REPORTED",
        "The exact legacy view omits declared v1-only fields.",
        source_id=profile.id,
    )
    report = ProjectionReport(
        source_schema="nornyx.profile_pack.v1",
        source_id=profile.id,
        source_version=profile.version,
        omitted_fields=tuple(legacy["omitted_fields"]),
        diagnostics=(diagnostic,),
    )
    return ProjectionResult(MappingProxyType(projected), report)
