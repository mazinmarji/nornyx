from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
import yaml

from nornyx import __version__
from nornyx.profiles import PROFILE_NAMES, write_profile


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
BUNDLED_SCHEMA_DIR = ROOT / "nornyx" / "schemas"
FIXTURES = ROOT / "tests" / "fixtures" / "governance_extension"
GOLDEN = FIXTURES / "starter_golden"
GOVERNANCE_SCHEMA_FILES = (
    "profile_pack_v1.schema.json",
    "governance_module_v1.schema.json",
    "governance_approval_model_v1.schema.json",
    "governance_approval_model_v2.schema.json",
    "effective_approval_v1.schema.json",
    "effective_governance_v2.schema.json",
    "profiles_lock_v1.schema.json",
    "governance_evidence_v1.schema.json",
    "separation_of_duties_v1.schema.json",
    "governance_exception_v1.schema.json",
    "change_v1.schema.json",
    "governed_package.schema.json",
    "architecture_v1.schema.json",
    "architecture_evidence_v1.schema.json",
    "architecture_report_v1.schema.json",
)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _registry() -> Registry:
    registry = Registry()
    for path in SCHEMA_DIR.glob("*.schema.json"):
        contents = _json(path)
        if "$id" in contents:
            registry = registry.with_resource(contents["$id"], Resource.from_contents(contents))
    return registry


def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(_json(SCHEMA_DIR / name), registry=_registry())


def _set_path(value: dict[str, Any], path: str, replacement: Any) -> None:
    parts = path.split(".")
    current: Any = value
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    final = parts[-1]
    if isinstance(current, list):
        current[int(final)] = replacement
    else:
        current[final] = replacement


def _canonical_lf(value: bytes) -> bytes:
    return value.replace(b"\r\n", b"\n")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _unique(values: list[Any]) -> tuple[list[str], bool]:
    result: list[str] = []
    duplicate = False
    for value in values:
        text = str(value)
        if text in result:
            duplicate = True
        else:
            result.append(text)
    return result, duplicate


def _normalization_diagnostic(code: str, level: str, message: str) -> dict[str, str]:
    return {"code": code, "level": level, "message": message}


def _normalize_approval(case: dict[str, Any]) -> dict[str, Any]:
    shape = case["shape"]
    raw = deepcopy(case["source"])
    source = raw if isinstance(raw, dict) else {}
    role_fields = (
        "eligible_roles",
        "eligible_approver_roles",
        "approver_roles",
        "approvers",
        "eligible_approvers",
    )
    role_field = next((field for field in role_fields if field in source), "none")
    eligible_values: list[Any] = []
    for field in role_fields:
        value = source.get(field, [])
        eligible_values.extend(value if isinstance(value, list) else [value])
    eligible, duplicate_eligible = _unique(eligible_values)
    required, duplicate_required = _unique(source.get("required_roles", []))
    denied_values, duplicate_denied = _unique(source.get("denied_approver_types", []))
    denied_surfaces = [item for item in denied_values if item == "execution_surface"]
    denied_actors = [item for item in denied_values if item != "execution_surface"]
    evidence, duplicate_evidence = _unique(source.get("required_evidence", []))
    actions, duplicate_actions = _unique(source.get("required_for", []))
    diagnostics: list[dict[str, str]] = []

    if any((duplicate_eligible, duplicate_required, duplicate_denied, duplicate_evidence, duplicate_actions)):
        diagnostics.append(
            _normalization_diagnostic(
                "APPROVAL_DUPLICATE_ROLE_NORMALIZED",
                "info",
                "Duplicate approval values were removed in first-seen order.",
            )
        )

    known_role_fields = set(role_fields) | {"required_roles", "denied_approver_types"}
    suspicious_unknown = [
        key
        for key in source
        if key not in known_role_fields
        and any(marker in key for marker in ("role", "approver", "authorized", "people"))
    ]
    if suspicious_unknown:
        diagnostics.append(
            _normalization_diagnostic(
                "APPROVAL_UNKNOWN_ROLE_FIELD",
                "error",
                f"Unknown role-bearing fields: {', '.join(sorted(suspicious_unknown))}.",
            )
        )

    core_conflict = (set(eligible) | set(required)) & {"ai_tool", "execution_surface"}
    if core_conflict:
        diagnostics.append(
            _normalization_diagnostic(
                "APPROVAL_CORE_DENIED_ACTOR_ELIGIBLE",
                "error",
                "AI tools and execution surfaces can never be eligible or "
                f"required approvers: {', '.join(sorted(core_conflict))}.",
            )
        )
    denied_all = set(denied_actors) | set(denied_surfaces)
    if set(eligible) & denied_all:
        diagnostics.append(
            _normalization_diagnostic(
                "APPROVAL_ACTOR_ELIGIBLE_AND_DENIED",
                "error",
                "An actor category cannot be both eligible and denied.",
            )
        )
    if required and not set(required) <= set(eligible):
        diagnostics.append(
            _normalization_diagnostic(
                "APPROVAL_REQUIRED_ROLE_NOT_ELIGIBLE",
                "error",
                "Every required role must also be eligible.",
            )
        )
    if shape == "governed_package_gate" and not eligible:
        diagnostics.append(
            _normalization_diagnostic(
                "APPROVAL_MISSING_ELIGIBLE_ROLES",
                "error",
                "Governed-package approval gates require an eligible role field.",
            )
        )
    if shape == "governed_package_gate" and not (eligible or required or evidence or actions):
        diagnostics.append(
            _normalization_diagnostic(
                "APPROVAL_EMPTY_REQUIREMENT",
                "error",
                "An approval gate with no roles, evidence, or actions is invalid.",
            )
        )

    accountable_authority = source.get("accountable_authority")
    if accountable_authority is not None and (
        not isinstance(accountable_authority, str)
        or not accountable_authority.strip()
    ):
        diagnostics.append(
            _normalization_diagnostic(
                "APPROVAL_ACCOUNTABLE_AUTHORITY_INVALID",
                "error",
                "Approval accountable authority must be a non-empty source string.",
            )
        )
        accountable_authority = None

    if shape in {"ordinary_approval", "generated_profile_approval"}:
        normalized_id = str(source.get("name", case["id"]))
        resolution = "complete"
        timing = "unspecified"
    elif shape == "governed_package_gate":
        normalized_id = str(source.get("id", case["id"]))
        resolution = "complete"
        timing = "unspecified"
    elif shape == "legacy_contract_reference":
        normalized_id = f"reference:{raw}"
        resolution = "reference_only"
        timing = "unspecified"
    elif shape == "legacy_goal_text":
        normalized_id = case["id"]
        resolution = "legacy_text_preserved"
        timing = "legacy_text"
    else:
        normalized_id = case["id"]
        resolution = "requirement_only"
        timing = "unspecified"
    if any(item["level"] == "error" for item in diagnostics):
        resolution = "invalid"

    return {
        "schema": "nornyx.normalized_approval.v1",
        "id": normalized_id,
        "required_roles": required,
        "eligible_roles": eligible,
        "denied_actor_types": denied_actors,
        "denied_execution_surfaces": denied_surfaces,
        "required_evidence": evidence,
        "actions_requiring_approval": actions,
        "timing": timing,
        "accountable_authority": accountable_authority,
        "revision_binding": source.get("revision_binding"),
        "invalidation_conditions": list(source.get("invalidation_conditions", [])),
        "expires_at": source.get("expires_at"),
        "resolution": resolution,
        "normalization_diagnostics": diagnostics,
        "source": {"shape": shape, "path": case["path"], "raw": raw, "role_field": role_field},
    }


def _project_v1_to_v03(pack: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    legacy = pack["compatibility"]["legacy_v0_3"]
    if not legacy["supported"] or legacy["mode"] != "exact_v0_3_view":
        raise ValueError("PROFILE_PROJECTION_UNSUPPORTED")
    blocked = sorted(set(legacy["must_preserve"]) & set(legacy["omitted_fields"]))
    if blocked:
        raise ValueError("PROFILE_PROJECTION_REQUIRED_FIELD_OMITTED:" + ",".join(blocked))
    projected = {
        "name": pack["name"],
        "version": "v0.3",
        "core_surface": "v0.2",
        "status": "optional_profile",
        "purpose": pack["purpose"],
        "domain": pack["domain"],
        "required_blocks": pack["required_blocks"],
        "recommended_blocks": pack["recommended_blocks"],
        "graph_node_kinds": pack["graph"]["node_kinds"],
        "validation_rules": legacy["validation_rules"],
        "conformance": legacy["conformance"],
        "non_goals": pack["non_goals"],
        "core_concepts": legacy["core_concepts"],
    }
    report = {
        "schema": "nornyx.profile_pack_projection_report.v1",
        "source": {"schema": pack["schema"], "id": pack["id"], "version": pack["version"]},
        "target": "nornyx.profile_pack.v0_3",
        "diagnostic": "PROFILE_PROJECTION_LOSS_REPORTED",
        "omitted_fields": legacy["omitted_fields"],
    }
    return projected, report


def test_governance_schemas_are_valid_and_bundled_copies_are_exact() -> None:
    for name in GOVERNANCE_SCHEMA_FILES:
        root_schema = _json(SCHEMA_DIR / name)
        Draft202012Validator.check_schema(root_schema)
        assert (SCHEMA_DIR / name).read_bytes() == (BUNDLED_SCHEMA_DIR / name).read_bytes()


def test_v03_and_v1_profile_fixtures_validate_against_separate_schemas() -> None:
    v03 = _yaml(FIXTURES / "valid_profile_v03.yaml")
    v1 = _yaml(FIXTURES / "valid_profile_v1.yaml")

    _validator("domain_profile_pack.schema.json").validate(v03)
    _validator("profile_pack_v1.schema.json").validate(v1)
    assert list(_validator("domain_profile_pack.schema.json").iter_errors(v1))
    assert list(_validator("profile_pack_v1.schema.json").iter_errors(v03))


def test_v1_schema_rejects_invalid_versions_operators_paths_and_metadata() -> None:
    valid = _yaml(FIXTURES / "valid_profile_v1.yaml")
    validator = _validator("profile_pack_v1.schema.json")
    for case in _json(FIXTURES / "invalid_profile_cases.json"):
        candidate = deepcopy(valid)
        _set_path(candidate, case["path"], case["value"])
        assert list(validator.iter_errors(candidate)), case["id"]


def test_legacy_projection_is_exact_and_loss_is_reported_out_of_band() -> None:
    v03_validator = _validator("domain_profile_pack.schema.json")
    for case in _json(FIXTURES / "projection_cases.json"):
        source = _yaml(FIXTURES / case["source"])
        for mutation in case.get("mutations", []):
            _set_path(source, mutation["path"], mutation["value"])
        if case["result"] == "fail":
            try:
                _project_v1_to_v03(source)
            except ValueError as exc:
                assert case["diagnostic"] in str(exc)
            else:
                raise AssertionError(f"projection case {case['id']} should fail")
            continue
        projected, report = _project_v1_to_v03(source)
        assert projected == _yaml(FIXTURES / case["expected"])
        v03_validator.validate(projected)
        assert report["diagnostic"] == case["diagnostic"]
        assert "projected_from" not in projected


def test_governance_module_is_data_only_and_security_flags_cannot_be_relaxed() -> None:
    valid = _yaml(FIXTURES / "valid_module_v1.yaml")
    validator = _validator("governance_module_v1.schema.json")
    validator.validate(valid)
    for case in _json(FIXTURES / "module_security_cases.json"):
        candidate = deepcopy(valid)
        _set_path(candidate, case["path"], case["value"])
        assert list(validator.iter_errors(candidate)), case["id"]


def test_profiles_lock_forbids_timestamps_and_is_schema_deterministic() -> None:
    schema = _json(SCHEMA_DIR / "profiles_lock_v1.schema.json")
    serialized = json.dumps(schema)
    assert "generated_at" not in serialized
    assert "timestamp" not in serialized
    valid = {
        "schema": "nornyx.profiles_lock.v1",
        "resolved": [
            {
                "id": "org.example.delivery_profile",
                "version": "1.0.0",
                "source_tier": "project",
                "content_hash": "sha256:" + "0" * 64,
                "path_hint": ".nornyx/profiles/delivery_profile.yaml",
            }
        ],
    }
    _validator("profiles_lock_v1.schema.json").validate(valid)
    invalid = deepcopy(valid)
    invalid["generated_at"] = "2026-01-01T00:00:00Z"
    assert list(_validator("profiles_lock_v1.schema.json").iter_errors(invalid))


def test_rule_semantics_fixture_covers_every_normative_collection_case() -> None:
    cases = _json(FIXTURES / "rule_semantics_cases.json")
    ids = {case["id"] for case in cases}
    required = {
        "when_collection_existential_match",
        "when_collection_existential_no_match",
        "require_collection_universal_pass",
        "require_collection_universal_per_element_failure",
        "empty_collection_when",
        "empty_collection_require",
        "missing_path_when_exists",
        "missing_path_when_not_exists",
        "missing_path_require",
        "null_is_present",
        "null_equals_null",
        "wrong_value_type",
        "nested_collections",
        "duplicate_matches",
        "unknown_operator",
        "invalid_path",
        "scalar_used_as_collection",
        "collection_used_as_scalar",
        "same_prefix_when_selection",
        "different_prefix_no_join",
        "nested_under_selected_prefix",
        "when_type_errors_fail_closed",
        "shared_ancestor_all_join",
    }
    assert ids == required
    assert next(item for item in cases if item["id"] == "empty_collection_require")["outcome"] == "fail_closed"
    assert next(item for item in cases if item["id"] == "unknown_operator")["outcome"] == "schema_error"


def test_approval_shapes_normalize_losslessly_to_the_draft_internal_contract() -> None:
    cases = _yaml(FIXTURES / "approval_normalization_cases.yaml")
    validator = _validator("governance_approval_model_v1.schema.json")
    observed_shapes = set()
    for case in cases:
        normalized = _normalize_approval(case)
        validator.validate(normalized)
        observed_shapes.add(case["shape"])
        assert normalized["resolution"] == case["expected_resolution"]
        assert normalized["source"]["raw"] == case["source"]
        if "expected_diagnostic" in case:
            assert case["expected_diagnostic"] in {
                item["code"] for item in normalized["normalization_diagnostics"]
            }
    assert observed_shapes == {
        "ordinary_approval",
        "generated_profile_approval",
        "governed_package_gate",
        "legacy_contract_reference",
        "legacy_goal_text",
        "legacy_boolean_requirement",
    }


def test_current_main_starter_goldens_are_complete_hashed_and_deterministic() -> None:
    manifest = _json(GOLDEN / "manifest.json")
    assert manifest["source_commit"] == "a274e7d85e2ea9b7925a4d9caa3b83e5f4fe3652"
    assert manifest["nornyx_version"] == __version__ == "1.6.0"
    assert manifest["profile_order"] == PROFILE_NAMES
    assert {entry["profile"] for entry in manifest["profiles"]} == set(PROFILE_NAMES)

    for entry in manifest["profiles"]:
        fixture = (GOLDEN / entry["file"]).read_bytes()
        assert _sha256(fixture) == entry["sha256"]
        assert _sha256(_canonical_lf(fixture)) == entry["canonical_lf_sha256"]
        assert entry["compatibility_class"] == "semantic_equivalence_allowed"
        assert entry["allowed_normalization"] == "CRLF_to_LF_only"

        with tempfile.TemporaryDirectory(prefix="nornyx-golden-test-") as tmp:
            first = Path(tmp) / "first.nyx"
            second = Path(tmp) / "second.nyx"
            write_profile(first, entry["profile"], manifest["project_name"])
            write_profile(second, entry["profile"], manifest["project_name"])
            first_bytes = first.read_bytes()
            assert first_bytes == second.read_bytes()
            assert _canonical_lf(first_bytes) == _canonical_lf(fixture)
            assert yaml.safe_load(first_bytes) == yaml.safe_load(fixture)


def test_pr1_adds_no_profile_loader_or_runtime_composition_package() -> None:
    assert not (ROOT / "nornyx" / "packs").exists()
    assert not (ROOT / "nornyx" / "packs_data").exists()
    assert not (ROOT / "nornyx" / "rules.py").exists()
    assert not (ROOT / "nornyx" / "compose.py").exists()
