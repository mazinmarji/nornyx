from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Any, Iterable

from .models import CompositionResult, GovernanceDiagnostic


SENSITIVE_CATEGORIES = frozenset({"secrets", "credentials", "tokens", "private_memory"})
EXTERNAL_ZONE_CLASSIFICATIONS = frozenset({"external", "external_contract_only", "contract_only"})
AGENTIC_APPROVAL_ID = "agentic_network_authority"
APPROVAL_RECORD_ID = "approval_record"
CONTRACT_REVIEW_ID = "agentic_network_contract_review"
_DURATION_RE = re.compile(r"^(?:P(?P<days>[1-9][0-9]*)D|PT(?P<hours>[1-9][0-9]*)H)$")
_IMMUTABLE_REVISION_RE = re.compile(
    r"^(?:git:(?:[0-9a-f]{40}|[0-9a-f]{64})|sha256:[0-9a-f]{64})$"
)
_SYMBOLIC_REVISION_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._/-]*$")


def _diagnostic(code: str, message: str, *, path: str) -> GovernanceDiagnostic:
    return GovernanceDiagnostic(
        "error",
        code,
        message,
        path=path,
        source_id="agentic_network_foundation.v1",
    )


def _mapping_items(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _name_set(items: Iterable[Mapping[str, Any]], *fields: str) -> set[str]:
    values: set[str] = set()
    for item in items:
        for field in fields:
            value = item.get(field)
            if isinstance(value, str):
                values.add(value)
    return values


def _index_unique(
    items: list[Mapping[str, Any]],
    *,
    field: str,
    path: str,
    code: str,
    noun: str,
    diagnostics: list[GovernanceDiagnostic],
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(items):
        value = item.get(field)
        if not isinstance(value, str):
            continue
        if value in result:
            diagnostics.append(
                _diagnostic(
                    code,
                    f"{noun} identifier {value!r} is duplicated.",
                    path=f"{path}[{index}].{field}",
                )
            )
        else:
            result[value] = item
    return result


def _unknown_references(
    values: Iterable[str],
    known: set[str],
    *,
    path: str,
    code: str,
    noun: str,
    diagnostics: list[GovernanceDiagnostic],
) -> None:
    for value in sorted(set(values) - known):
        diagnostics.append(
            _diagnostic(
                code,
                f"Unknown {noun} reference {value!r}.",
                path=path,
            )
        )


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (OverflowError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _validate_interval(
    item: Mapping[str, Any],
    *,
    path: str,
    active_status: str,
    as_of: datetime | None,
    diagnostics: list[GovernanceDiagnostic],
) -> None:
    valid_from = _parse_time(item.get("valid_from"))
    expires_at = _parse_time(item.get("expires_at"))
    if valid_from is None or expires_at is None or valid_from >= expires_at:
        diagnostics.append(
            _diagnostic(
                "AN_AUTHORIZATION_INTERVAL_INVALID",
                "Authorization validity must use offset timestamps with valid_from before expires_at.",
                path=path,
            )
        )
        return
    if item.get("status") != active_status or as_of is None:
        return
    if as_of < valid_from:
        diagnostics.append(
            _diagnostic(
                "AN_AUTHORIZATION_NOT_YET_VALID",
                f"{active_status.capitalize()} authorization is not yet valid.",
                path=f"{path}.valid_from",
            )
        )
    if as_of >= expires_at:
        diagnostics.append(
            _diagnostic(
                "AN_AUTHORIZATION_EXPIRED",
                f"{active_status.capitalize()} authorization is expired.",
                path=f"{path}.expires_at",
            )
        )


def _composition_reference_sets(
    document: Mapping[str, Any],
    composition: CompositionResult,
) -> tuple[set[str], set[str], set[str]]:
    approval_refs = {item.id for item in composition.approval_requirements}
    approval_refs.update(_name_set(_mapping_items(document.get("approvals")), "id", "name"))

    evidence_refs: set[str] = set()
    for item in composition.evidence_requirements:
        evidence_refs.update(_name_set((item,), "id"))
    evidence_block = document.get("governance_evidence")
    if isinstance(evidence_block, Mapping):
        evidence_refs.update(_name_set(_mapping_items(evidence_block.get("records")), "id"))

    policy_refs = _name_set(composition.policies, "id", "name")
    policy_refs.update(_name_set(_mapping_items(document.get("policies")), "id", "name"))
    return approval_refs, evidence_refs, policy_refs


def _check_governance_references(
    item: Mapping[str, Any],
    *,
    path: str,
    approval_refs: set[str],
    evidence_refs: set[str],
    policy_refs: set[str] | None,
    diagnostics: list[GovernanceDiagnostic],
) -> None:
    _unknown_references(
        _strings(item.get("required_approval_refs")),
        approval_refs,
        path=f"{path}.required_approval_refs",
        code="AN_APPROVAL_UNKNOWN",
        noun="approval",
        diagnostics=diagnostics,
    )
    _unknown_references(
        _strings(item.get("required_evidence_refs")),
        evidence_refs,
        path=f"{path}.required_evidence_refs",
        code="AN_EVIDENCE_UNKNOWN",
        noun="evidence",
        diagnostics=diagnostics,
    )
    if policy_refs is not None:
        _unknown_references(
            _strings(item.get("required_policy_refs")),
            policy_refs,
            path=f"{path}.required_policy_refs",
            code="AN_POLICY_UNKNOWN",
            noun="policy",
            diagnostics=diagnostics,
        )


def _sensitive_boundary(
    item: Mapping[str, Any],
    *,
    path: str,
    diagnostics: list[GovernanceDiagnostic],
) -> None:
    never_share = set(_strings(item.get("never_share")))
    missing = SENSITIVE_CATEGORIES - never_share
    shared = set(_strings(item.get("share"))) | set(_strings(item.get("share_allowlist")))
    leaked = SENSITIVE_CATEGORIES & shared
    if missing or leaked:
        details = []
        if missing:
            details.append(
                "missing mandatory never-share categories: " + ", ".join(sorted(missing))
            )
        if leaked:
            details.append(
                "sensitive categories appear in sharing declarations: " + ", ".join(sorted(leaked))
            )
        diagnostics.append(
            _diagnostic(
                "AN_SENSITIVE_SHARE_BOUNDARY_MISSING",
                "; ".join(details) + ".",
                path=path,
            )
        )


def _parse_duration(value: Any) -> timedelta | None:
    if not isinstance(value, str):
        return None
    match = _DURATION_RE.fullmatch(value)
    if match is None:
        return None
    if match.group("days") is not None:
        return timedelta(days=int(match.group("days")))
    return timedelta(hours=int(match.group("hours")))


def _authorization_problem(
    item: Mapping[str, Any],
    *,
    active_status: str,
    as_of: datetime | None,
) -> str | None:
    if item.get("status") != active_status:
        return "inactive"
    valid_from = _parse_time(item.get("valid_from"))
    expires_at = _parse_time(item.get("expires_at"))
    if valid_from is None or expires_at is None or valid_from >= expires_at:
        return "invalid_interval"
    if as_of is None:
        return "validation_time_required"
    if as_of < valid_from:
        return "not_yet_valid"
    if as_of >= expires_at:
        return "expired"
    return None


def _revocation_target_key(target: Any) -> tuple[str, ...] | None:
    if not isinstance(target, Mapping):
        return None
    kind = target.get("kind")
    if kind == "agent_identity" and isinstance(target.get("identity_ref"), str):
        return ("agent_identity", target["identity_ref"])
    if kind == "membership" and isinstance(target.get("membership_ref"), str):
        return ("membership", target["membership_ref"])
    if kind == "protocol_target" and isinstance(target.get("protocol_target_ref"), str):
        return ("protocol_target", target["protocol_target_ref"])
    if kind == "approval_record" and isinstance(target.get("approval_record_ref"), str):
        return ("approval_record", target["approval_record_ref"])
    if kind == "capability_assignment" and all(
        isinstance(target.get(field), str)
        for field in ("principal_type", "principal_ref", "capability_ref")
    ):
        return (
            "capability_assignment",
            str(target["principal_type"]),
            str(target["principal_ref"]),
            str(target["capability_ref"]),
        )
    return None


def _producer_role(producer_id: str) -> str:
    for separator in (".", ":"):
        if separator in producer_id:
            producer_id = producer_id.rsplit(separator, 1)[-1]
    return producer_id


def _revision_problem(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return "required"
    if _IMMUTABLE_REVISION_RE.fullmatch(value):
        return None
    if any(character.isspace() for character in value) or "://" in value:
        return "malformed"
    if value.startswith("refs/") or _SYMBOLIC_REVISION_RE.fullmatch(value):
        return "mutable"
    if ":" not in value:
        return "malformed"
    algorithm, payload = value.split(":", 1)
    if algorithm not in {"git", "sha256"}:
        return "unsupported_algorithm"
    if algorithm == "git" and _SYMBOLIC_REVISION_RE.fullmatch(payload):
        return "mutable"
    return "malformed"


def _validate_immutable_revision(
    value: Any,
    *,
    path: str,
    noun: str,
    diagnostics: list[GovernanceDiagnostic],
) -> str | None:
    problem = _revision_problem(value)
    if problem is None:
        return str(value)
    code, message = {
        "required": (
            "AN_REVISION_REQUIRED",
            f"{noun} requires an immutable content-addressed revision.",
        ),
        "mutable": (
            "AN_REVISION_MUTABLE",
            f"{noun} must not use a mutable or symbolic revision.",
        ),
        "unsupported_algorithm": (
            "AN_REVISION_ALGORITHM_UNSUPPORTED",
            f"{noun} uses an unsupported revision algorithm.",
        ),
        "malformed": (
            "AN_REVISION_MALFORMED",
            f"{noun} must use git:<40-or-64-hex> or sha256:<64-hex>.",
        ),
    }[problem]
    diagnostics.append(_diagnostic(code, message, path=path))
    return None


def _canonical_evidence_record(
    records: list[Mapping[str, Any]],
    *,
    record_id: str,
    record_type: str,
    missing_code: str,
    type_code: str,
    ambiguous_code: str,
    noun: str,
    diagnostics: list[GovernanceDiagnostic],
) -> Mapping[str, Any] | None:
    id_matches = [item for item in records if item.get("id") == record_id]
    for record in id_matches:
        if record.get("type") != record_type:
            diagnostics.append(
                _diagnostic(
                    type_code,
                    f"{noun} {record_id!r} must have type {record_type!r}.",
                    path=f"governance_evidence.records[{records.index(record)}].type",
                )
            )
    canonical = [item for item in id_matches if item.get("type") == record_type]
    if not canonical:
        diagnostics.append(
            _diagnostic(
                missing_code,
                f"Required {noun.lower()} {record_id!r} with type {record_type!r} is missing.",
                path="governance_evidence.records",
            )
        )
        return None
    if len(canonical) > 1:
        diagnostics.append(
            _diagnostic(
                ambiguous_code,
                f"Exactly one canonical {noun.lower()} is permitted.",
                path="governance_evidence.records",
            )
        )
        return None
    return canonical[0]


def _validate_revision_and_authority(
    document: Mapping[str, Any],
    composition: CompositionResult,
    network: Mapping[str, Any],
    *,
    as_of: datetime | None,
    effective_revocations: set[tuple[str, ...]],
    required_actions: set[str],
    diagnostics: list[GovernanceDiagnostic],
) -> dict[str, Mapping[str, Any]]:
    evidence = document.get("governance_evidence")
    evidence_mapping = evidence if isinstance(evidence, Mapping) else {}
    records = _mapping_items(evidence_mapping.get("records"))
    records_by_id = {
        str(item["id"]): item for item in records if isinstance(item.get("id"), str)
    }

    network_revision = _validate_immutable_revision(
        network.get("subject_revision"),
        path="agentic_network.subject_revision",
        noun="Agentic-network governance",
        diagnostics=diagnostics,
    )
    evidence_revision = _validate_immutable_revision(
        evidence_mapping.get("subject_revision"),
        path="governance_evidence.subject_revision",
        noun="Governance evidence",
        diagnostics=diagnostics,
    )
    if network_revision is not None and evidence_revision is not None and (
        evidence_revision != network_revision
    ):
        diagnostics.append(
            _diagnostic(
                "AN_REVISION_MISMATCH",
                "Governance evidence is bound to a different subject revision.",
                path="governance_evidence.subject_revision",
            )
        )

    contract_requirement = next(
        (
            item
            for item in composition.evidence_requirements
            if item.get("id") == CONTRACT_REVIEW_ID
        ),
        None,
    )
    contract_type = (
        contract_requirement.get("type")
        if isinstance(contract_requirement, Mapping)
        and isinstance(contract_requirement.get("type"), str)
        else None
    )
    if contract_type is None:
        diagnostics.append(
            _diagnostic(
                "AN_CONTRACT_REVIEW_REQUIREMENT_MISSING",
                "The composed module does not define the required contract-review evidence type.",
                path="governance_evidence.records",
            )
        )
        contract_review = None
    else:
        contract_review = _canonical_evidence_record(
            records,
            record_id=CONTRACT_REVIEW_ID,
            record_type=contract_type,
            missing_code="AN_CONTRACT_REVIEW_MISSING",
            type_code="AN_CONTRACT_REVIEW_TYPE_INVALID",
            ambiguous_code="AN_CONTRACT_REVIEW_AMBIGUOUS",
            noun="Contract-review evidence record",
            diagnostics=diagnostics,
        )
    approval_record = _canonical_evidence_record(
        records,
        record_id=APPROVAL_RECORD_ID,
        record_type="approval_record",
        missing_code="AN_APPROVAL_RECORD_MISSING",
        type_code="AN_APPROVAL_RECORD_TYPE_INVALID",
        ambiguous_code="AN_APPROVAL_AMBIGUOUS",
        noun="Approval evidence record",
        diagnostics=diagnostics,
    )

    for record_id, record in (
        (CONTRACT_REVIEW_ID, contract_review),
        (APPROVAL_RECORD_ID, approval_record),
    ):
        if record is None:
            continue
        record_index = records.index(record)
        record_revision = _validate_immutable_revision(
            record.get("subject_revision"),
            path=f"governance_evidence.records[{record_index}].subject_revision",
            noun=f"Evidence record {record_id!r}",
            diagnostics=diagnostics,
        )
        if network_revision is not None and record_revision is not None and (
            record_revision != network_revision
        ):
            diagnostics.append(
                _diagnostic(
                    "AN_REVISION_MISMATCH",
                    f"Evidence record {record_id!r} is bound to a different subject revision.",
                    path=f"governance_evidence.records[{record_index}].subject_revision",
                )
            )

    declarations = _mapping_items(document.get("approvals"))
    declaration = next(
        (
            item
            for item in declarations
            if item.get("id") == AGENTIC_APPROVAL_ID or item.get("name") == AGENTIC_APPROVAL_ID
        ),
        None,
    )
    approval_requirement = next(
        (item for item in composition.approval_requirements if item.id == AGENTIC_APPROVAL_ID),
        None,
    )
    declaration_authority_valid = False
    effective_allowed_roles: set[str] = set()
    module_allowed_roles: set[str] = set()
    if approval_requirement is None:
        diagnostics.append(
            _diagnostic(
                "AN_APPROVAL_MODULE_REQUIREMENT_MISSING",
                "The composed module does not define the required agentic-network authority.",
                path="approvals",
            )
        )
    else:
        module_required_roles = set(approval_requirement.required_roles)
        module_eligible_roles = set(approval_requirement.eligible_roles)
        module_allowed_roles = module_required_roles | module_eligible_roles
        if approval_requirement.accountable_authority is not None:
            module_allowed_roles.add(approval_requirement.accountable_authority)

    if declaration is None:
        diagnostics.append(
            _diagnostic(
                "AN_APPROVAL_DECLARATION_MISSING",
                f"Approval declaration {AGENTIC_APPROVAL_ID!r} is required.",
                path="approvals",
            )
        )
    else:
        declaration_index = declarations.index(declaration)
        declaration_path = f"approvals[{declaration_index}]"
        declared_required_roles = set(_strings(declaration.get("required_roles")))
        declared_eligible_roles = set(_strings(declaration.get("eligible_roles")))
        declared_authority = declaration.get("accountable_authority")
        contradiction = False
        unauthorized_required = declared_required_roles - module_allowed_roles
        unauthorized_eligible = declared_eligible_roles - (
            set(approval_requirement.eligible_roles)
            if approval_requirement is not None
            else set()
        )
        for field, unauthorized in (
            ("required_roles", unauthorized_required),
            ("eligible_roles", unauthorized_eligible),
        ):
            if unauthorized:
                contradiction = True
                diagnostics.append(
                    _diagnostic(
                        "AN_APPROVAL_DECLARED_ROLE_UNAUTHORIZED",
                        "Document approval roles are absent from the composed module authority: "
                        + ", ".join(sorted(unauthorized))
                        + ".",
                        path=f"{declaration_path}.{field}",
                    )
                )
        if approval_requirement is not None:
            omitted_roles = set(approval_requirement.required_roles) - declared_required_roles
            if omitted_roles:
                contradiction = True
                diagnostics.append(
                    _diagnostic(
                        "AN_APPROVAL_MODULE_ROLE_OMITTED",
                        "Document approval requirements omit module-required roles: "
                        + ", ".join(sorted(omitted_roles))
                        + ".",
                        path=f"{declaration_path}.required_roles",
                    )
                )
            if declared_authority != approval_requirement.accountable_authority:
                contradiction = True
                diagnostics.append(
                    _diagnostic(
                        "AN_APPROVAL_ACCOUNTABLE_AUTHORITY_MISMATCH",
                        "Document accountable authority must match the composed module authority.",
                        path=f"{declaration_path}.accountable_authority",
                    )
                )
        document_allowed_roles = declared_required_roles | declared_eligible_roles
        effective_allowed_roles = module_allowed_roles & document_allowed_roles
        if not effective_allowed_roles:
            contradiction = True
        if contradiction:
            diagnostics.append(
                _diagnostic(
                    "AN_APPROVAL_DECLARATION_MODULE_CONTRADICTION",
                    "Document approval authority contradicts the composed module requirement.",
                    path=declaration_path,
                )
            )
        else:
            declaration_authority_valid = approval_requirement is not None

        declared_actions = set(_strings(declaration.get("required_for")))
        missing_actions = required_actions - declared_actions
        if missing_actions:
            diagnostics.append(
                _diagnostic(
                    "AN_APPROVAL_ACTION_MISSING",
                    "Approval declaration does not cover required actions: "
                    + ", ".join(sorted(missing_actions))
                    + ".",
                    path=f"approvals[{declaration_index}].required_for",
                )
            )
        binding = declaration.get("revision_binding")
        bound_revision = binding.get("revision") if isinstance(binding, Mapping) else None
        binding_path = f"approvals[{declaration_index}].revision_binding.revision"
        validated_bound_revision = _validate_immutable_revision(
            bound_revision,
            path=binding_path,
            noun="Approval declaration",
            diagnostics=diagnostics,
        )
        if validated_bound_revision is not None and (
            binding.get("exact") is not True
            or network_revision is None
            or validated_bound_revision != network_revision
        ):
            diagnostics.append(
                _diagnostic(
                    "AN_REVISION_MISMATCH",
                    "Approval declaration must bind exactly to the agentic-network revision.",
                    path=binding_path,
                )
            )

    if approval_record is None:
        return records_by_id
    record_index = records.index(approval_record)
    producer = approval_record.get("producer")
    if not isinstance(producer, Mapping) or producer.get("type") != "human":
        diagnostics.append(
            _diagnostic(
                "AN_APPROVAL_HUMAN_REQUIRED",
                "Agentic-network approval evidence must be produced by an authorized human.",
                path=f"governance_evidence.records[{record_index}].producer.type",
            )
        )
    elif isinstance(producer.get("id"), str):
        producer_role = _producer_role(str(producer["id"]))
        if producer_role not in module_allowed_roles:
            diagnostics.append(
                _diagnostic(
                    "AN_APPROVAL_PRODUCER_OUTSIDE_MODULE_AUTHORITY",
                    "Approval producer is outside the composed module authority.",
                    path=f"governance_evidence.records[{record_index}].producer.id",
                )
            )
        elif declaration_authority_valid and producer_role not in effective_allowed_roles:
            diagnostics.append(
                _diagnostic(
                    "AN_APPROVAL_ROLE_INVALID",
                    "Approval producer is not an eligible agentic-network authority.",
                    path=f"governance_evidence.records[{record_index}].producer.id",
                )
            )

    if approval_record.get("status") != "pass":
        diagnostics.append(
            _diagnostic(
                "AN_APPROVAL_RECORD_INVALID",
                "Approval evidence must have pass status.",
                path=f"governance_evidence.records[{record_index}].status",
            )
        )
    if ("approval_record", APPROVAL_RECORD_ID) in effective_revocations:
        diagnostics.append(
            _diagnostic(
                "AN_APPROVAL_REVOKED",
                "The approval record has been revoked or superseded.",
                path=f"governance_evidence.records[{record_index}].id",
            )
        )

    maximum_age = _parse_duration(
        approval_requirement.expires_after if approval_requirement is not None else None
    )
    generated_at = _parse_time(approval_record.get("generated_at"))
    expires_at = _parse_time(approval_record.get("expires_at"))
    if generated_at is None or expires_at is None or generated_at >= expires_at:
        diagnostics.append(
            _diagnostic(
                "AN_APPROVAL_INTERVAL_INVALID",
                "Approval evidence requires a valid generated-at/expiry interval.",
                path=f"governance_evidence.records[{record_index}]",
            )
        )
    else:
        if maximum_age is not None and expires_at - generated_at > maximum_age:
            diagnostics.append(
                _diagnostic(
                    "AN_APPROVAL_EXPIRY_EXCESSIVE",
                    "Approval evidence exceeds the permitted relative-expiry policy.",
                    path=f"governance_evidence.records[{record_index}].expires_at",
                )
            )
        if as_of is None:
            diagnostics.append(
                _diagnostic(
                    "AN_VALIDATION_TIME_REQUIRED",
                    "Approval validation requires an explicit as_of time.",
                    path=f"governance_evidence.records[{record_index}]",
                )
            )
        elif as_of < generated_at:
            diagnostics.append(
                _diagnostic(
                    "AN_APPROVAL_NOT_YET_VALID",
                    "Approval evidence was generated after the validation time.",
                    path=f"governance_evidence.records[{record_index}].generated_at",
                )
            )
        elif as_of >= expires_at or (
            maximum_age is not None and as_of - generated_at >= maximum_age
        ):
            diagnostics.append(
                _diagnostic(
                    "AN_APPROVAL_EXPIRED",
                    "Approval evidence is expired or stale.",
                    path=f"governance_evidence.records[{record_index}].expires_at",
                )
            )

    if declaration is not None and generated_at is not None and maximum_age is not None:
        declaration_index = declarations.index(declaration)
        declaration_expiry = _parse_time(declaration.get("expires_at"))
        if declaration_expiry is None or declaration_expiry > generated_at + maximum_age:
            diagnostics.append(
                _diagnostic(
                    "AN_APPROVAL_EXPIRY_EXCESSIVE",
                    "Approval declaration exceeds the permitted relative-expiry policy.",
                    path=f"approvals[{declaration_index}].expires_at",
                )
            )
    return records_by_id


def agentic_network_foundation_check(
    document: Mapping[str, Any],
    composition: CompositionResult,
    *,
    as_of: datetime | None,
    document_root: Path | None,
) -> tuple[GovernanceDiagnostic, ...]:
    """Validate static AN-001 relationships without executing or observing a network."""

    del document_root
    network = document.get("agentic_network")
    if not isinstance(network, Mapping):
        return ()

    diagnostics: list[GovernanceDiagnostic] = []
    identities = _mapping_items(document.get("agent_identities"))
    capabilities = _mapping_items(document.get("capabilities"))
    agents = _mapping_items(document.get("agents"))
    zones = _mapping_items(network.get("trust_zones"))
    memberships = _mapping_items(network.get("memberships"))
    protocols = _mapping_items(network.get("protocol_targets"))
    gates = _mapping_items(network.get("network_gates"))
    revocations = _mapping_items(network.get("revocations"))

    identity_by_id = _index_unique(
        identities,
        field="id",
        path="agent_identities",
        code="AN_IDENTITY_DUPLICATE",
        noun="Agent identity",
        diagnostics=diagnostics,
    )
    capability_by_name = _index_unique(
        capabilities,
        field="name",
        path="capabilities",
        code="AN_CAPABILITY_DUPLICATE",
        noun="Capability",
        diagnostics=diagnostics,
    )
    zone_by_id = _index_unique(
        zones,
        field="id",
        path="agentic_network.trust_zones",
        code="AN_TRUST_ZONE_DUPLICATE",
        noun="Trust zone",
        diagnostics=diagnostics,
    )
    membership_by_id = _index_unique(
        memberships,
        field="id",
        path="agentic_network.memberships",
        code="AN_MEMBERSHIP_DUPLICATE",
        noun="Membership",
        diagnostics=diagnostics,
    )
    protocol_by_id = _index_unique(
        protocols,
        field="id",
        path="agentic_network.protocol_targets",
        code="AN_PROTOCOL_TARGET_DUPLICATE",
        noun="Protocol target",
        diagnostics=diagnostics,
    )
    gate_by_id = _index_unique(
        gates,
        field="id",
        path="agentic_network.network_gates",
        code="AN_GATE_DUPLICATE",
        noun="Network gate",
        diagnostics=diagnostics,
    )
    revocation_by_id = _index_unique(
        revocations,
        field="id",
        path="agentic_network.revocations",
        code="AN_REVOCATION_DUPLICATE",
        noun="Revocation",
        diagnostics=diagnostics,
    )

    identity_ids = set(identity_by_id)
    capability_names = set(capability_by_name)
    zone_ids = set(zone_by_id)
    membership_ids = set(membership_by_id)
    protocol_ids = set(protocol_by_id)
    gate_ids = set(gate_by_id)
    revocation_ids = set(revocation_by_id)
    role_names = _name_set(agents, "name")
    approval_refs, evidence_refs, policy_refs = _composition_reference_sets(document, composition)
    context_names = _name_set(_mapping_items(document.get("contexts")), "name")
    other_scope_names = set().union(
        _name_set(agents, "name"),
        _name_set(_mapping_items(document.get("goals")), "id", "title"),
        _name_set(_mapping_items(document.get("contracts")), "id", "name"),
        _name_set(_mapping_items(document.get("policies")), "id", "name"),
        _name_set(_mapping_items(document.get("budgets")), "id", "name"),
    )

    evidence_block = document.get("governance_evidence")
    evidence_records = (
        _mapping_items(evidence_block.get("records")) if isinstance(evidence_block, Mapping) else []
    )
    evidence_record_ids = _name_set(evidence_records, "id")

    revocation_target_by_id: dict[str, tuple[str, ...]] = {}
    effective_revocations: set[tuple[str, ...]] = set()
    for index, revocation in enumerate(revocations):
        path = f"agentic_network.revocations[{index}]"
        target_key = _revocation_target_key(revocation.get("target"))
        target_known = False
        if target_key is not None:
            kind = target_key[0]
            if kind == "agent_identity":
                target_known = target_key[1] in identity_ids
            elif kind == "membership":
                target_known = target_key[1] in membership_ids
            elif kind == "protocol_target":
                target_known = target_key[1] in protocol_ids
            elif kind == "approval_record":
                target_known = target_key[1] in evidence_record_ids
            elif kind == "capability_assignment":
                _, principal_type, principal_ref, capability_ref = target_key
                principal = (
                    identity_by_id.get(principal_ref)
                    if principal_type == "agent_identity"
                    else membership_by_id.get(principal_ref)
                    if principal_type == "membership"
                    else None
                )
                target_known = principal is not None and capability_ref in _strings(
                    principal.get("capability_refs")
                )
        if not target_known:
            diagnostics.append(
                _diagnostic(
                    "AN_REVOCATION_TARGET_UNKNOWN",
                    "Revocation target is malformed, ambiguous, or does not exist.",
                    path=f"{path}.target",
                )
            )
        revocation_id = revocation.get("id")
        if isinstance(revocation_id, str) and target_key is not None and target_known:
            revocation_target_by_id[revocation_id] = target_key

        effective_at = _parse_time(revocation.get("effective_at"))
        if effective_at is None:
            diagnostics.append(
                _diagnostic(
                    "AN_REVOCATION_TIME_INVALID",
                    "Revocation effective_at must be a valid offset timestamp.",
                    path=f"{path}.effective_at",
                )
            )
        elif (
            as_of is not None and as_of >= effective_at and target_key is not None and target_known
        ):
            effective_revocations.add(target_key)

        _check_governance_references(
            revocation,
            path=path,
            approval_refs=approval_refs,
            evidence_refs=evidence_refs,
            policy_refs=None,
            diagnostics=diagnostics,
        )

    required_approval_actions = {
        "external_share"
        for protocol in protocols
        if (
            isinstance(protocol.get("trust_zone_ref"), str)
            and protocol.get("trust_zone_ref") in zone_by_id
            and zone_by_id[str(protocol.get("trust_zone_ref"))].get("classification")
            in EXTERNAL_ZONE_CLASSIFICATIONS
        )
    }
    _validate_revision_and_authority(
        document,
        composition,
        network,
        as_of=as_of,
        effective_revocations=effective_revocations,
        required_actions=required_approval_actions,
        diagnostics=diagnostics,
    )

    subject_pairs: dict[tuple[str, str], int] = {}
    binding_pairs: dict[tuple[str, str], tuple[int, int]] = {}
    for index, identity in enumerate(identities):
        path = f"agent_identities[{index}]"
        pair = (identity.get("namespace"), identity.get("subject"))
        if all(isinstance(value, str) for value in pair):
            typed_pair = (str(pair[0]), str(pair[1]))
            if typed_pair in subject_pairs:
                diagnostics.append(
                    _diagnostic(
                        "AN_IDENTITY_SUBJECT_DUPLICATE",
                        f"Identity namespace/subject pair {typed_pair!r} is duplicated.",
                        path=f"{path}.subject",
                    )
                )
            else:
                subject_pairs[typed_pair] = index
        for binding_index, binding in enumerate(_mapping_items(identity.get("framework_bindings"))):
            binding_pair = (binding.get("framework"), binding.get("agent_key"))
            if not all(isinstance(value, str) for value in binding_pair):
                continue
            typed_binding = (str(binding_pair[0]), str(binding_pair[1]))
            if typed_binding in binding_pairs:
                diagnostics.append(
                    _diagnostic(
                        "AN_IDENTITY_BINDING_DUPLICATE",
                        f"Framework binding {typed_binding!r} is duplicated.",
                        path=f"{path}.framework_bindings[{binding_index}]",
                    )
                )
            else:
                binding_pairs[typed_binding] = (index, binding_index)

        role_ref = identity.get("role_ref")
        if isinstance(role_ref, str) and role_ref not in role_names:
            diagnostics.append(
                _diagnostic(
                    "AN_IDENTITY_ROLE_UNKNOWN",
                    f"Agent identity references unknown role {role_ref!r}.",
                    path=f"{path}.role_ref",
                )
            )
        _unknown_references(
            _strings(identity.get("capability_refs")),
            capability_names,
            path=f"{path}.capability_refs",
            code="AN_CAPABILITY_UNKNOWN",
            noun="capability",
            diagnostics=diagnostics,
        )
        _unknown_references(
            _strings(identity.get("revocation_refs")),
            revocation_ids,
            path=f"{path}.revocation_refs",
            code="AN_REVOCATION_UNKNOWN",
            noun="revocation",
            diagnostics=diagnostics,
        )
        identity_id = identity.get("id")
        for revocation_ref in _strings(identity.get("revocation_refs")):
            target_key = revocation_target_by_id.get(revocation_ref)
            if target_key is not None and target_key != ("agent_identity", identity_id):
                diagnostics.append(
                    _diagnostic(
                        "AN_REVOCATION_REFERENCE_MISMATCH",
                        "Identity revocation reference targets another subject.",
                        path=f"{path}.revocation_refs",
                    )
                )
        if identity.get("authority") != "non_human" or identity.get("can_approve") is not False:
            diagnostics.append(
                _diagnostic(
                    "AN_NON_HUMAN_APPROVAL_INVALID",
                    "Agent identities must remain non-human and cannot approve.",
                    path=path,
                )
            )
        _validate_interval(
            identity,
            path=path,
            active_status="active",
            as_of=as_of,
            diagnostics=diagnostics,
        )

    for index, capability in enumerate(capabilities):
        path = f"capabilities[{index}]"
        scope_refs = _strings(capability.get("scope_refs"))
        if len(scope_refs) != len(set(scope_refs)):
            diagnostics.append(
                _diagnostic(
                    "AN_CAPABILITY_SCOPE_DUPLICATE",
                    "Capability scope references must be unique.",
                    path=f"{path}.scope_refs",
                )
            )
        if capability.get("scope_type") != "context":
            diagnostics.append(
                _diagnostic(
                    "AN_CAPABILITY_SCOPE_CLASS_UNSUPPORTED",
                    "AN-001 capabilities may reference only declared contexts.",
                    path=f"{path}.scope_type",
                )
            )
        for scope_ref in sorted(set(scope_refs)):
            if scope_ref in context_names and scope_ref in other_scope_names:
                diagnostics.append(
                    _diagnostic(
                        "AN_CAPABILITY_SCOPE_AMBIGUOUS",
                        f"Capability scope {scope_ref!r} collides across object kinds.",
                        path=f"{path}.scope_refs",
                    )
                )
            elif scope_ref not in context_names:
                code = (
                    "AN_CAPABILITY_SCOPE_WRONG_KIND"
                    if scope_ref in other_scope_names
                    else "AN_CAPABILITY_SCOPE_UNKNOWN"
                )
                diagnostics.append(
                    _diagnostic(
                        code,
                        f"Capability scope {scope_ref!r} is not a declared context.",
                        path=f"{path}.scope_refs",
                    )
                )
        if capability.get("delegable") is not False:
            diagnostics.append(
                _diagnostic(
                    "AN_DELEGATION_FORBIDDEN",
                    "Delegation is outside AN-001 and must remain disabled.",
                    path=f"{path}.delegable",
                )
            )
        gate_refs = _strings(capability.get("required_gate_refs"))
        _unknown_references(
            gate_refs,
            gate_ids,
            path=f"{path}.required_gate_refs",
            code="AN_GATE_UNKNOWN",
            noun="network gate",
            diagnostics=diagnostics,
        )
        _check_governance_references(
            capability,
            path=path,
            approval_refs=approval_refs,
            evidence_refs=evidence_refs,
            policy_refs=None,
            diagnostics=diagnostics,
        )
        if capability.get("risk") in {"high", "critical"} and not gate_refs:
            diagnostics.append(
                _diagnostic(
                    "AN_GATE_REQUIRED",
                    "High and critical capabilities require at least one network gate.",
                    path=f"{path}.required_gate_refs",
                )
            )

    for index, zone in enumerate(zones):
        path = f"agentic_network.trust_zones[{index}]"
        _unknown_references(
            _strings(zone.get("allowed_transition_targets")),
            zone_ids,
            path=f"{path}.allowed_transition_targets",
            code="AN_TRUST_ZONE_UNKNOWN",
            noun="trust zone",
            diagnostics=diagnostics,
        )
        for field in ("ingress_gate_refs", "egress_gate_refs"):
            _unknown_references(
                _strings(zone.get(field)),
                gate_ids,
                path=f"{path}.{field}",
                code="AN_GATE_UNKNOWN",
                noun="network gate",
                diagnostics=diagnostics,
            )
        if zone.get("classification") in EXTERNAL_ZONE_CLASSIFICATIONS:
            _sensitive_boundary(zone, path=path, diagnostics=diagnostics)

    for index, membership in enumerate(memberships):
        path = f"agentic_network.memberships[{index}]"
        identity_ref = membership.get("identity_ref")
        if isinstance(identity_ref, str) and identity_ref not in identity_ids:
            diagnostics.append(
                _diagnostic(
                    "AN_IDENTITY_UNKNOWN",
                    f"Membership references unknown identity {identity_ref!r}.",
                    path=f"{path}.identity_ref",
                )
            )
        zone_ref = membership.get("trust_zone_ref")
        if isinstance(zone_ref, str) and zone_ref not in zone_ids:
            diagnostics.append(
                _diagnostic(
                    "AN_TRUST_ZONE_UNKNOWN",
                    f"Membership references unknown trust zone {zone_ref!r}.",
                    path=f"{path}.trust_zone_ref",
                )
            )
        membership_capabilities = set(_strings(membership.get("capability_refs")))
        _unknown_references(
            membership_capabilities,
            capability_names,
            path=f"{path}.capability_refs",
            code="AN_CAPABILITY_UNKNOWN",
            noun="capability",
            diagnostics=diagnostics,
        )
        identity = identity_by_id.get(str(identity_ref))
        if identity is not None:
            escalation = membership_capabilities - set(_strings(identity.get("capability_refs")))
            if escalation:
                diagnostics.append(
                    _diagnostic(
                        "AN_CAPABILITY_ESCALATION",
                        "Membership assigns capabilities absent from its identity: "
                        + ", ".join(sorted(escalation))
                        + ".",
                        path=f"{path}.capability_refs",
                    )
                )
        _unknown_references(
            _strings(membership.get("revocation_refs")),
            revocation_ids,
            path=f"{path}.revocation_refs",
            code="AN_REVOCATION_UNKNOWN",
            noun="revocation",
            diagnostics=diagnostics,
        )
        membership_id = membership.get("id")
        for revocation_ref in _strings(membership.get("revocation_refs")):
            target_key = revocation_target_by_id.get(revocation_ref)
            if target_key is not None and target_key != ("membership", membership_id):
                diagnostics.append(
                    _diagnostic(
                        "AN_REVOCATION_REFERENCE_MISMATCH",
                        "Membership revocation reference targets another subject.",
                        path=f"{path}.revocation_refs",
                    )
                )
        _validate_interval(
            membership,
            path=path,
            active_status="authorized",
            as_of=as_of,
            diagnostics=diagnostics,
        )

    for index, protocol in enumerate(protocols):
        path = f"agentic_network.protocol_targets[{index}]"
        identity_refs = _strings(protocol.get("identity_refs"))
        source_membership_refs = _strings(protocol.get("source_membership_refs"))
        capability_refs = _strings(protocol.get("capability_refs"))
        gate_refs = _strings(protocol.get("required_gate_refs"))
        _unknown_references(
            identity_refs,
            identity_ids,
            path=f"{path}.identity_refs",
            code="AN_IDENTITY_UNKNOWN",
            noun="agent identity",
            diagnostics=diagnostics,
        )
        _unknown_references(
            source_membership_refs,
            membership_ids,
            path=f"{path}.source_membership_refs",
            code="AN_MEMBERSHIP_UNKNOWN",
            noun="source membership",
            diagnostics=diagnostics,
        )
        _unknown_references(
            capability_refs,
            capability_names,
            path=f"{path}.capability_refs",
            code="AN_CAPABILITY_UNKNOWN",
            noun="capability",
            diagnostics=diagnostics,
        )
        _unknown_references(
            gate_refs,
            gate_ids,
            path=f"{path}.required_gate_refs",
            code="AN_GATE_UNKNOWN",
            noun="network gate",
            diagnostics=diagnostics,
        )
        source_zone_ref = protocol.get("source_zone_ref")
        target_zone_ref = protocol.get("trust_zone_ref")
        for field, zone_ref in (
            ("source_zone_ref", source_zone_ref),
            ("trust_zone_ref", target_zone_ref),
        ):
            if isinstance(zone_ref, str) and zone_ref not in zone_ids:
                diagnostics.append(
                    _diagnostic(
                        "AN_TRUST_ZONE_UNKNOWN",
                        f"Protocol target references unknown trust zone {zone_ref!r}.",
                        path=f"{path}.{field}",
                    )
                )
        _check_governance_references(
            protocol,
            path=path,
            approval_refs=approval_refs,
            evidence_refs=evidence_refs,
            policy_refs=None,
            diagnostics=diagnostics,
        )
        _sensitive_boundary(protocol, path=path, diagnostics=diagnostics)

        protocol_id = protocol.get("id")
        if (
            isinstance(protocol_id, str)
            and (
                "protocol_target",
                protocol_id,
            )
            in effective_revocations
        ):
            diagnostics.append(
                _diagnostic(
                    "AN_PROTOCOL_REVOKED",
                    "Protocol target has an effective revocation.",
                    path=f"{path}.id",
                )
            )

        source_zone = zone_by_id.get(str(source_zone_ref))
        target_zone = zone_by_id.get(str(target_zone_ref))
        external_target = (
            target_zone is not None
            and target_zone.get("classification") in EXTERNAL_ZONE_CLASSIFICATIONS
        )
        if (
            source_zone is not None
            and isinstance(target_zone_ref, str)
            and target_zone_ref not in _strings(source_zone.get("allowed_transition_targets"))
        ):
            diagnostics.append(
                _diagnostic(
                    "AN_PROTOCOL_TRANSITION_NOT_ALLOWED",
                    "Protocol source-to-target transition is not explicitly allowed.",
                    path=f"{path}.trust_zone_ref",
                )
            )

        source_memberships = [
            membership_by_id[ref] for ref in source_membership_refs if ref in membership_by_id
        ]
        for membership_ref in source_membership_refs:
            membership = membership_by_id.get(membership_ref)
            if membership is None:
                continue
            if membership.get("trust_zone_ref") != source_zone_ref:
                diagnostics.append(
                    _diagnostic(
                        "AN_PROTOCOL_MEMBERSHIP_WRONG_ZONE",
                        "Source membership is not authorized in the protocol source zone.",
                        path=f"{path}.source_membership_refs",
                    )
                )
            if membership.get("identity_ref") not in identity_refs:
                diagnostics.append(
                    _diagnostic(
                        "AN_PROTOCOL_MEMBERSHIP_WRONG_IDENTITY",
                        "Source membership belongs to an unreferenced identity.",
                        path=f"{path}.source_membership_refs",
                    )
                )
            membership_problem = _authorization_problem(
                membership,
                active_status="authorized",
                as_of=as_of,
            )
            if membership_problem is not None:
                diagnostics.append(
                    _diagnostic(
                        "AN_PROTOCOL_MEMBERSHIP_UNAUTHORIZED",
                        f"Source membership is not effective: {membership_problem}.",
                        path=f"{path}.source_membership_refs",
                    )
                )
            if ("membership", membership_ref) in effective_revocations:
                diagnostics.append(
                    _diagnostic(
                        "AN_PROTOCOL_MEMBERSHIP_REVOKED",
                        "Source membership has an effective revocation.",
                        path=f"{path}.source_membership_refs",
                    )
                )

        for identity_ref in identity_refs:
            identity = identity_by_id.get(identity_ref)
            if identity is None:
                continue
            identity_problem = _authorization_problem(
                identity,
                active_status="active",
                as_of=as_of,
            )
            if identity_problem is not None:
                diagnostics.append(
                    _diagnostic(
                        "AN_PROTOCOL_IDENTITY_UNAUTHORIZED",
                        f"Protocol identity is not effective: {identity_problem}.",
                        path=f"{path}.identity_refs",
                    )
                )
            if ("agent_identity", identity_ref) in effective_revocations:
                diagnostics.append(
                    _diagnostic(
                        "AN_PROTOCOL_IDENTITY_REVOKED",
                        "Protocol identity has an effective revocation.",
                        path=f"{path}.identity_refs",
                    )
                )
            applicable_memberships = [
                membership
                for membership in source_memberships
                if membership.get("identity_ref") == identity_ref
                and membership.get("trust_zone_ref") == source_zone_ref
            ]
            if not applicable_memberships:
                diagnostics.append(
                    _diagnostic(
                        "AN_PROTOCOL_MEMBERSHIP_REQUIRED",
                        "Protocol identity requires an explicit source membership.",
                        path=f"{path}.source_membership_refs",
                    )
                )
            for capability_ref in capability_refs:
                assigned_memberships = [
                    membership
                    for membership in applicable_memberships
                    if capability_ref in _strings(membership.get("capability_refs"))
                ]
                if (
                    capability_ref not in _strings(identity.get("capability_refs"))
                    or not assigned_memberships
                ):
                    diagnostics.append(
                        _diagnostic(
                            "AN_PROTOCOL_CAPABILITY_UNAUTHORIZED",
                            f"Capability {capability_ref!r} is not assigned through the identity and source membership.",
                            path=f"{path}.capability_refs",
                        )
                    )
                    continue
                if (
                    "capability_assignment",
                    "agent_identity",
                    identity_ref,
                    capability_ref,
                ) in effective_revocations or any(
                    (
                        "capability_assignment",
                        "membership",
                        str(membership.get("id")),
                        capability_ref,
                    )
                    in effective_revocations
                    for membership in assigned_memberships
                ):
                    diagnostics.append(
                        _diagnostic(
                            "AN_PROTOCOL_CAPABILITY_REVOKED",
                            f"Capability {capability_ref!r} has an effective revocation.",
                            path=f"{path}.capability_refs",
                        )
                    )

        required_actions = {
            action
            for capability_ref in capability_refs
            if capability_ref in capability_by_name
            for action in _strings(capability_by_name[capability_ref].get("actions"))
        }
        if external_target:
            required_actions.add("external_share")
        required_capability_gates = {
            gate_ref
            for capability_ref in capability_refs
            if capability_ref in capability_by_name
            for gate_ref in _strings(capability_by_name[capability_ref].get("required_gate_refs"))
        }
        missing_capability_gates = required_capability_gates - set(gate_refs)
        if missing_capability_gates:
            diagnostics.append(
                _diagnostic(
                    "AN_PROTOCOL_CAPABILITY_GATE_MISSING",
                    "Protocol omits capability gates: "
                    + ", ".join(sorted(missing_capability_gates))
                    + ".",
                    path=f"{path}.required_gate_refs",
                )
            )
        if not gate_refs:
            diagnostics.append(
                _diagnostic(
                    "AN_PROTOCOL_GATE_REQUIRED",
                    "Every protocol target requires a semantically applicable gate.",
                    path=f"{path}.required_gate_refs",
                )
            )
        covered_actions: set[str] = set()
        for gate_ref in gate_refs:
            gate = gate_by_id.get(gate_ref)
            if gate is None:
                continue
            gate_actions = set(_strings(gate.get("action_classes")))
            covered_actions.update(gate_actions)
            if source_zone_ref not in _strings(gate.get("source_zone_refs")):
                diagnostics.append(
                    _diagnostic(
                        "AN_PROTOCOL_GATE_SOURCE_MISMATCH",
                        f"Gate {gate_ref!r} does not cover the protocol source zone.",
                        path=f"{path}.required_gate_refs",
                    )
                )
            if target_zone_ref not in _strings(gate.get("target_zone_refs")):
                diagnostics.append(
                    _diagnostic(
                        "AN_PROTOCOL_GATE_TARGET_MISMATCH",
                        f"Gate {gate_ref!r} does not cover the protocol target zone.",
                        path=f"{path}.required_gate_refs",
                    )
                )
            if source_zone is not None and gate_ref not in _strings(
                source_zone.get("egress_gate_refs")
            ):
                diagnostics.append(
                    _diagnostic(
                        "AN_PROTOCOL_EGRESS_GATE_MISSING",
                        f"Source zone does not declare gate {gate_ref!r} for egress.",
                        path=f"{path}.required_gate_refs",
                    )
                )
            if target_zone is not None and gate_ref not in _strings(
                target_zone.get("ingress_gate_refs")
            ):
                diagnostics.append(
                    _diagnostic(
                        "AN_PROTOCOL_INGRESS_GATE_MISSING",
                        f"Target zone does not declare gate {gate_ref!r} for ingress.",
                        path=f"{path}.required_gate_refs",
                    )
                )
            if external_target and AGENTIC_APPROVAL_ID not in _strings(
                gate.get("required_approval_refs")
            ):
                diagnostics.append(
                    _diagnostic(
                        "AN_PROTOCOL_GATE_APPROVAL_MISSING",
                        "External-boundary gate lacks agentic-network human approval.",
                        path=f"{path}.required_gate_refs",
                    )
                )
            if external_target and CONTRACT_REVIEW_ID not in _strings(
                gate.get("required_evidence_refs")
            ):
                diagnostics.append(
                    _diagnostic(
                        "AN_PROTOCOL_GATE_EVIDENCE_MISSING",
                        "External-boundary gate lacks contract-review evidence.",
                        path=f"{path}.required_gate_refs",
                    )
                )
        missing_actions = required_actions - covered_actions
        if missing_actions:
            diagnostics.append(
                _diagnostic(
                    "AN_PROTOCOL_GATE_ACTION_MISMATCH",
                    "Referenced gates do not cover protocol actions: "
                    + ", ".join(sorted(missing_actions))
                    + ".",
                    path=f"{path}.required_gate_refs",
                )
            )
        if external_target:
            if AGENTIC_APPROVAL_ID not in _strings(protocol.get("required_approval_refs")):
                diagnostics.append(
                    _diagnostic(
                        "AN_PROTOCOL_APPROVAL_REQUIRED",
                        "External protocol target requires human agentic-network approval.",
                        path=f"{path}.required_approval_refs",
                    )
                )
            if CONTRACT_REVIEW_ID not in _strings(protocol.get("required_evidence_refs")):
                diagnostics.append(
                    _diagnostic(
                        "AN_PROTOCOL_EVIDENCE_REQUIRED",
                        "External protocol target requires contract-review evidence.",
                        path=f"{path}.required_evidence_refs",
                    )
                )

        shared = _strings(protocol.get("share"))
        if len(shared) != len(set(shared)):
            diagnostics.append(
                _diagnostic(
                    "AN_SHARE_CATEGORY_DUPLICATE",
                    "Protocol sharing categories must be unique.",
                    path=f"{path}.share",
                )
            )
        source_allowlist = (
            set(_strings(source_zone.get("share_allowlist"))) if source_zone is not None else set()
        )
        target_allowlist = (
            set(_strings(target_zone.get("share_allowlist"))) if target_zone is not None else set()
        )
        for category in sorted(set(shared)):
            if category not in source_allowlist and category not in target_allowlist:
                diagnostics.append(
                    _diagnostic(
                        "AN_SHARE_CATEGORY_UNKNOWN",
                        f"Shared category {category!r} is absent from both zone allowlists.",
                        path=f"{path}.share",
                    )
                )
            elif category not in source_allowlist:
                diagnostics.append(
                    _diagnostic(
                        "AN_SHARE_NOT_ALLOWED_SOURCE",
                        f"Source zone does not allow shared category {category!r}.",
                        path=f"{path}.share",
                    )
                )
            elif category not in target_allowlist:
                diagnostics.append(
                    _diagnostic(
                        "AN_SHARE_NOT_ALLOWED_TARGET",
                        f"Target zone does not allow shared category {category!r}.",
                        path=f"{path}.share",
                    )
                )

    for index, gate in enumerate(gates):
        path = f"agentic_network.network_gates[{index}]"
        for field in ("source_zone_refs", "target_zone_refs"):
            _unknown_references(
                _strings(gate.get(field)),
                zone_ids,
                path=f"{path}.{field}",
                code="AN_TRUST_ZONE_UNKNOWN",
                noun="trust zone",
                diagnostics=diagnostics,
            )
        _check_governance_references(
            gate,
            path=path,
            approval_refs=approval_refs,
            evidence_refs=evidence_refs,
            policy_refs=policy_refs,
            diagnostics=diagnostics,
        )

    for index, revocation in enumerate(revocations):
        path = f"agentic_network.revocations[{index}]"
        target_key = _revocation_target_key(revocation.get("target"))
        if target_key is None or target_key not in effective_revocations:
            continue
        status = (
            identity_by_id[target_key[1]].get("status")
            if target_key[0] == "agent_identity"
            else membership_by_id[target_key[1]].get("status")
            if target_key[0] == "membership"
            else None
        )
        if status in {"active", "authorized"} or target_key[0] in {
            "capability_assignment",
            "protocol_target",
        }:
            diagnostics.append(
                _diagnostic(
                    "AN_AUTHORIZATION_REVOKED",
                    f"Revocation {revocation.get('id')!r} is effective.",
                    path=f"{path}.target",
                )
            )

    return tuple(
        sorted(
            diagnostics,
            key=lambda item: (item.code, item.path or "", item.message),
        )
    )
