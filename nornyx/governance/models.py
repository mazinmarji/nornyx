from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
from types import MappingProxyType
from typing import Any, Literal, Mapping


PackSourceTier = Literal["builtin", "project", "org", "explicit_path"]


def immutable_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(deepcopy(dict(value or {})))


@dataclass(frozen=True, slots=True)
class GovernanceDiagnostic:
    level: Literal["error", "warning", "info"]
    code: str
    message: str
    path: str | None = None
    source_id: str | None = None
    binding: tuple[tuple[str, int], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "level": self.level,
            "code": self.code,
            "message": self.message,
        }
        if self.path is not None:
            payload["path"] = self.path
        if self.source_id is not None:
            payload["source_id"] = self.source_id
        if self.binding:
            payload["binding"] = [
                {"collection": collection, "index": index}
                for collection, index in self.binding
            ]
        return payload


@dataclass(frozen=True, slots=True)
class PackProvenance:
    author: str
    source_tier: PackSourceTier
    source_revision: str
    source_path: str

    def to_dict(self) -> dict[str, str]:
        return {
            "author": self.author,
            "source_tier": self.source_tier,
            "source_revision": self.source_revision,
            "source_path": self.source_path,
        }


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    description: str
    when: Mapping[str, Any] | None
    requirements: tuple[Mapping[str, Any], ...]
    severity: Literal["error", "warning"]
    message: str
    source_id: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], *, source_id: str) -> Rule:
        raw_when = value.get("when")
        return cls(
            id=str(value["id"]),
            description=str(value["description"]),
            when=immutable_mapping(raw_when) if isinstance(raw_when, Mapping) else None,
            requirements=tuple(
                immutable_mapping(item)
                for item in value.get("require", [])
                if isinstance(item, Mapping)
            ),
            severity=value["severity"],
            message=str(value["message"]),
            source_id=source_id,
        )

    @property
    def namespaced_id(self) -> str:
        return f"{self.source_id}/{self.id}"


@dataclass(frozen=True, slots=True)
class StarterFragment:
    target: str
    content: Any
    source_id: str
    source_index: int

    def copy_content(self) -> Any:
        return deepcopy(self.content)


@dataclass(frozen=True, slots=True)
class GovernanceBlockSchema:
    block: str
    schema_id: str
    source_id: str

    def to_dict(self) -> dict[str, str]:
        return {
            "block": self.block,
            "schema_id": self.schema_id,
            "source_id": self.source_id,
        }


@dataclass(frozen=True, slots=True)
class ProfilePack:
    id: str
    name: str
    display_name: str
    version: str
    compatible_core: str
    status: str
    purpose: str
    domain: str
    required_modules: tuple[str, ...]
    required_blocks: tuple[str, ...]
    recommended_blocks: tuple[str, ...]
    default_policies: tuple[Mapping[str, Any], ...]
    required_evidence: tuple[Mapping[str, Any], ...]
    default_evaluations: tuple[Mapping[str, Any], ...]
    approval_requirements: tuple[Mapping[str, Any], ...]
    validation_rules: tuple[Rule, ...]
    conflicts: tuple[str, ...]
    non_goals: tuple[str, ...]
    starter_fragments: tuple[StarterFragment, ...]
    provenance: PackProvenance
    content_hash: str
    raw: Mapping[str, Any] = field(repr=False)

    def as_dict(self) -> dict[str, Any]:
        return deepcopy(dict(self.raw))


@dataclass(frozen=True, slots=True)
class GovernanceModule:
    id: str
    name: str
    version: str
    compatible_core: str
    dependencies: tuple[str, ...]
    conflicts: tuple[str, ...]
    required_blocks: tuple[str, ...]
    policies: tuple[Mapping[str, Any], ...]
    evidence_requirements: tuple[Mapping[str, Any], ...]
    approval_requirements: tuple[Mapping[str, Any], ...]
    evaluations: tuple[Mapping[str, Any], ...]
    rules: tuple[Rule, ...]
    non_goals: tuple[str, ...]
    provenance: PackProvenance
    content_hash: str
    raw: Mapping[str, Any] = field(repr=False)
    block_schemas: tuple[GovernanceBlockSchema, ...] = ()
    structural_checks: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return deepcopy(dict(self.raw))


@dataclass(frozen=True, slots=True)
class NormalizedApproval:
    id: str
    required_roles: tuple[str, ...]
    eligible_roles: tuple[str, ...]
    denied_actor_types: tuple[str, ...]
    denied_execution_surfaces: tuple[str, ...]
    required_evidence: tuple[str, ...]
    actions_requiring_approval: tuple[str, ...]
    timing: str
    accountable_authority: str | None
    revision_binding: Mapping[str, Any] | None
    invalidation_conditions: tuple[str, ...]
    expires_at: str | None
    resolution: str
    diagnostics: tuple[GovernanceDiagnostic, ...]
    source_shape: str
    source_path: str
    source_raw: Any
    role_field: str
    exact_revision_required: bool | None = None
    expires_after: str | None = None
    effective_approval: EffectiveApproval | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def _legacy_serialized_fields(self) -> dict[str, Any]:
        legacy_revision_binding = (
            deepcopy(dict(self.revision_binding))
            if self.revision_binding
            else None
        )
        if legacy_revision_binding is not None:
            legacy_revision_binding.pop("scope_hash", None)
        return {
            "id": self.id,
            "required_roles": list(self.required_roles),
            "eligible_roles": list(self.eligible_roles),
            "denied_actor_types": list(self.denied_actor_types),
            "denied_execution_surfaces": list(self.denied_execution_surfaces),
            "required_evidence": list(self.required_evidence),
            "actions_requiring_approval": list(self.actions_requiring_approval),
            "timing": self.timing,
            "accountable_authority": self.accountable_authority,
            "revision_binding": legacy_revision_binding,
            "invalidation_conditions": list(self.invalidation_conditions),
            "expires_at": self.expires_at,
            "resolution": self.resolution,
            "normalization_diagnostics": [
                {"level": item.level, "code": item.code, "message": item.message}
                for item in self.diagnostics
            ],
        }

    def _extended_serialized_fields(self) -> dict[str, Any]:
        return {
            **self._legacy_serialized_fields(),
            "revision_binding": (
                deepcopy(dict(self.revision_binding))
                if self.revision_binding
                else None
            ),
            "exact_revision_required": bool(self.exact_revision_required),
            "expires_after": self.expires_after,
        }

    def _serialized_source(self) -> dict[str, Any]:
        fallback_id = "approval:" + hashlib.sha256(
            json.dumps(
                {"shape": self.source_shape, "path": self.source_path},
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()[:24]
        return {
            "shape": self.source_shape,
            "path": self.source_path,
            "raw": deepcopy(self.source_raw),
            "role_field": self.role_field,
            "fallback_id": fallback_id,
        }

    def _verifiable_identity(self, fallback_id: str) -> str:
        raw = self.source_raw
        source = raw if isinstance(raw, Mapping) else {}
        if self.source_shape == "ordinary_approval":
            field_name = "name"
        elif self.source_shape == "generated_profile_approval":
            field_name = "id" if "id" in source else "name"
        elif self.source_shape == "governed_package_gate":
            field_name = "id"
        elif self.source_shape == "legacy_contract_reference":
            if isinstance(raw, str) and raw.strip() and raw == raw.strip():
                return f"reference:{raw}"
            return fallback_id
        else:
            return fallback_id
        value = source.get(field_name)
        if isinstance(value, str) and value.strip() and value == value.strip():
            return value
        return fallback_id

    def to_dict(self) -> dict[str, Any]:
        return self.to_legacy_dict()

    def to_legacy_dict(self) -> dict[str, Any]:
        return {
            "schema": "nornyx.normalized_approval.v1",
            **self._legacy_serialized_fields(),
            "source": {
                "shape": self.source_shape,
                "path": self.source_path,
                "raw": deepcopy(self.source_raw),
                "role_field": self.role_field,
            },
        }

    def to_verifiable_dict(self) -> dict[str, Any]:
        """Return the bounded v2 representation used at trust boundaries.

        The source binding detects inconsistent mutation of retained source
        metadata. It is deliberately a consistency binding, not a signature;
        callers that require source authenticity must also supply trusted
        source context to the verifier.
        """

        source = self._serialized_source()
        identity = self._verifiable_identity(source["fallback_id"])
        encoded = json.dumps(
            source,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        source["binding"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
        return {
            "schema": "nornyx.normalized_approval.v2",
            **self._extended_serialized_fields(),
            "id": identity,
            "source": source,
        }


@dataclass(frozen=True, slots=True)
class EffectiveApproval:
    id: str
    required_roles: tuple[str, ...]
    eligible_roles: tuple[str, ...]
    denied_actor_types: tuple[str, ...]
    denied_execution_surfaces: tuple[str, ...]
    required_evidence: tuple[str, ...]
    actions_requiring_approval: tuple[str, ...]
    timing: str
    accountable_authority: str | None
    revision_binding: Mapping[str, Any] | None
    exact_revision_required: bool
    invalidation_conditions: tuple[str, ...]
    expires_after: str | None
    expires_at: str | None
    sources: tuple[Mapping[str, Any], ...]
    decisions: Mapping[str, Any]
    operation: str = "nornyx.monotonic_approval_composition.v1"

    @property
    def resolution(self) -> str:
        return "complete"

    @property
    def diagnostics(self) -> tuple[GovernanceDiagnostic, ...]:
        return ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "nornyx.effective_approval.v1",
            "id": self.id,
            "required_roles": list(self.required_roles),
            "eligible_roles": list(self.eligible_roles),
            "denied_actor_types": list(self.denied_actor_types),
            "denied_execution_surfaces": list(self.denied_execution_surfaces),
            "required_evidence": list(self.required_evidence),
            "actions_requiring_approval": list(self.actions_requiring_approval),
            "timing": self.timing,
            "accountable_authority": self.accountable_authority,
            "revision_binding": (
                deepcopy(dict(self.revision_binding))
                if self.revision_binding
                else None
            ),
            "exact_revision_required": self.exact_revision_required,
            "invalidation_conditions": list(self.invalidation_conditions),
            "expires_after": self.expires_after,
            "expires_at": self.expires_at,
            "resolution": "complete",
            "operation": self.operation,
            "decisions": deepcopy(dict(self.decisions)),
            "sources": [deepcopy(dict(item)) for item in self.sources],
        }


@dataclass(frozen=True, slots=True)
class ProjectionReport:
    source_schema: str
    source_id: str
    source_version: str
    omitted_fields: tuple[str, ...]
    diagnostics: tuple[GovernanceDiagnostic, ...]

    def to_dict(self) -> dict[str, Any]:
        primary = self.diagnostics[0].code if self.diagnostics else None
        return {
            "schema": "nornyx.profile_pack_projection_report.v1",
            "source": {
                "schema": self.source_schema,
                "id": self.source_id,
                "version": self.source_version,
            },
            "target": "nornyx.profile_pack.v0_3",
            "diagnostic": primary,
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "omitted_fields": list(self.omitted_fields),
        }


@dataclass(frozen=True, slots=True)
class ProjectionResult:
    legacy_view: Mapping[str, Any]
    report: ProjectionReport

    def legacy_dict(self) -> dict[str, Any]:
        return deepcopy(dict(self.legacy_view))


@dataclass(frozen=True, slots=True)
class LockEntry:
    id: str
    version: str
    source_tier: PackSourceTier
    content_hash: str
    path_hint: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "version": self.version,
            "source_tier": self.source_tier,
            "content_hash": self.content_hash,
            "path_hint": self.path_hint,
        }


@dataclass(frozen=True, slots=True)
class ProfileLock:
    resolved: tuple[LockEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "nornyx.profiles_lock.v1",
            "resolved": [entry.to_dict() for entry in sorted(self.resolved, key=lambda item: item.id)],
        }


@dataclass(frozen=True, slots=True)
class CompositionResult:
    profile: ProfilePack | None
    modules: tuple[GovernanceModule, ...]
    required_blocks: tuple[str, ...]
    policies: tuple[Mapping[str, Any], ...]
    evidence_requirements: tuple[Mapping[str, Any], ...]
    approval_requirements: tuple[NormalizedApproval, ...]
    evaluations: tuple[Mapping[str, Any], ...]
    rules: tuple[Rule, ...]
    non_goals: tuple[str, ...]
    starter_fragments: tuple[StarterFragment, ...]
    provenance: tuple[Mapping[str, Any], ...]
    diagnostics: tuple[GovernanceDiagnostic, ...] = ()
    block_schemas: tuple[GovernanceBlockSchema, ...] | None = None
    structural_checks: tuple[str, ...] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "nornyx.effective_governance.v1",
            "profile": self.profile.id if self.profile else None,
            "modules": [module.id for module in self.modules],
            "required_blocks": list(self.required_blocks),
            "policies": [deepcopy(dict(item)) for item in self.policies],
            "evidence_requirements": [deepcopy(dict(item)) for item in self.evidence_requirements],
            "approval_requirements": [
                item.to_legacy_dict() for item in self.approval_requirements
            ],
            "evaluations": [deepcopy(dict(item)) for item in self.evaluations],
            "rules": [rule.namespaced_id for rule in self.rules],
            "non_goals": list(self.non_goals),
            "starter_fragments": [
                {
                    "target": item.target,
                    "source_id": item.source_id,
                    "source_index": item.source_index,
                }
                for item in self.starter_fragments
            ],
            "provenance": [deepcopy(dict(item)) for item in self.provenance],
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }

    def to_effective_dict(self) -> dict[str, Any]:
        """Return governance output with separately versioned approvals."""

        return {
            "schema": "nornyx.effective_governance.v2",
            "profile": self.profile.id if self.profile else None,
            "modules": [module.id for module in self.modules],
            "required_blocks": list(self.required_blocks),
            "block_schemas": [
                item.to_dict() for item in (self.block_schemas or ())
            ],
            "structural_checks": list(self.structural_checks or ()),
            "policies": [deepcopy(dict(item)) for item in self.policies],
            "evidence_requirements": [
                deepcopy(dict(item)) for item in self.evidence_requirements
            ],
            "approval_requirements": [
                (
                    item.effective_approval.to_dict()
                    if item.effective_approval is not None
                    else item.to_verifiable_dict()
                )
                for item in self.approval_requirements
            ],
            "evaluations": [deepcopy(dict(item)) for item in self.evaluations],
            "rules": [rule.namespaced_id for rule in self.rules],
            "non_goals": list(self.non_goals),
            "starter_fragments": [
                {
                    "target": item.target,
                    "source_id": item.source_id,
                    "source_index": item.source_index,
                }
                for item in self.starter_fragments
            ],
            "provenance": [deepcopy(dict(item)) for item in self.provenance],
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }
