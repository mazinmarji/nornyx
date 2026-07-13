from __future__ import annotations

from copy import deepcopy
from importlib import resources
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from nornyx.governance import GovernanceError, Rule, normalize_approval
from nornyx.governance.composition import compose_governance
from nornyx.governance.loader import load_local_pack
from nornyx.governance.locks import lock_for_packs
from nornyx.governance.locks import write_lock
from nornyx.governance.projection import project_profile_to_v03
from nornyx.governance.registry import GovernanceRegistry
from nornyx.governance.rules import evaluate_rule
from nornyx.governance.schemas import canonical_pack_hash, validate_payload
from nornyx.cli import main
from nornyx.profiles import PROFILE_NAMES, profile_document, profile_pack_v1


FIXTURES = Path(__file__).parent / "fixtures" / "governance_extension"


def _yaml(name: str) -> dict[str, Any]:
    return yaml.safe_load((FIXTURES / name).read_text(encoding="utf-8"))


def _json(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _write_pack(path: Path, payload: dict[str, Any]) -> None:
    payload = deepcopy(payload)
    payload["integrity"]["content_hash"] = canonical_pack_hash(payload)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _rule(
    *,
    requirement: dict[str, Any],
    when: dict[str, Any] | None = None,
    rule_id: str = "TST-001",
) -> Rule:
    return Rule.from_dict(
        {
            "id": rule_id,
            "description": "Fixture-backed rule semantics.",
            "when": when,
            "require": [requirement],
            "severity": "error",
            "message": "Fixture requirement failed.",
        },
        source_id="test.fixture",
    )


def _codes(exc: GovernanceError) -> set[str]:
    return {item.code for item in exc.diagnostics}


def test_approval_normalization_cases_execute_against_the_runtime() -> None:
    for case in yaml.safe_load(
        (FIXTURES / "approval_normalization_cases.yaml").read_text(encoding="utf-8")
    ):
        normalized = normalize_approval(
            case["source"],
            shape=case["shape"],
            path=case["path"],
            fallback_id=case["id"],
        )
        assert normalized.resolution == case["expected_resolution"], case["id"]
        assert normalized.source_raw == case["source"], case["id"]
        validate_payload(normalized.to_dict(), "governance_approval_model_v1.schema.json")
        if diagnostic := case.get("expected_diagnostic"):
            assert diagnostic in {item.code for item in normalized.diagnostics}, case["id"]


def test_projection_cases_execute_against_the_runtime(tmp_path: Path) -> None:
    for case in _json("projection_cases.json"):
        payload = _yaml(case["source"])
        for mutation in case.get("mutations", []):
            current: Any = payload
            parts = mutation["path"].split(".")
            for part in parts[:-1]:
                current = current[part]
            current[parts[-1]] = mutation["value"]
        path = tmp_path / f"{case['id']}.yaml"
        _write_pack(path, payload)
        profile = load_local_pack(path, allowed_root=tmp_path)
        if case["result"] == "fail":
            with pytest.raises(GovernanceError) as caught:
                project_profile_to_v03(profile)  # type: ignore[arg-type]
            assert case["diagnostic"] in _codes(caught.value)
        else:
            result = project_profile_to_v03(profile)  # type: ignore[arg-type]
            assert result.legacy_dict() == _yaml(case["expected"])
            assert result.report.diagnostics[0].code == case["diagnostic"]
            assert "projected_from" not in result.legacy_view


def test_loader_is_local_schema_checked_and_path_bounded(tmp_path: Path) -> None:
    valid = _yaml("valid_profile_v1.yaml")
    path = tmp_path / "valid.yaml"
    _write_pack(path, valid)
    loaded = load_local_pack(path, allowed_root=tmp_path)
    assert loaded.id == valid["id"]

    with pytest.raises(GovernanceError) as remote:
        load_local_pack("https://example.invalid/profile.yaml", allowed_root=tmp_path)
    assert _codes(remote.value) == {"PACK_REMOTE_SOURCE_REJECTED"}

    outside = tmp_path.parent / "outside-profile.yaml"
    _write_pack(outside, valid)
    try:
        with pytest.raises(GovernanceError) as traversal:
            load_local_pack(outside, allowed_root=tmp_path)
        assert _codes(traversal.value) == {"PACK_PATH_OUTSIDE_ROOT"}
    finally:
        outside.unlink()

    malformed = deepcopy(valid)
    malformed["validation_rules"][0]["require"][0] = {
        "path": "changes[0].risk",
        "python": "pass",
    }
    malformed_path = tmp_path / "malformed.yaml"
    _write_pack(malformed_path, malformed)
    with pytest.raises(GovernanceError) as schema_error:
        load_local_pack(malformed_path, allowed_root=tmp_path)
    assert "PACK_SCHEMA_INVALID" in _codes(schema_error.value)


def test_loader_rejects_reserved_namespaces_and_resource_abuse(tmp_path: Path) -> None:
    payload = _yaml("valid_profile_v1.yaml")
    payload["id"] = "nornyx.builtin.squat"
    path = tmp_path / "squat.yaml"
    _write_pack(path, payload)
    with pytest.raises(GovernanceError) as reserved:
        load_local_pack(path, allowed_root=tmp_path, source_tier="project")
    assert _codes(reserved.value) == {"PACK_RESERVED_NAMESPACE"}

    with pytest.raises(GovernanceError) as encoding:
        from nornyx.governance.loader import load_pack_bytes

        load_pack_bytes(b"\xff", source_path="invalid.yaml", source_tier="project")
    assert _codes(encoding.value) == {"PACK_ENCODING_INVALID"}

    with pytest.raises(GovernanceError) as null_byte:
        load_pack_bytes(b"schema:\x00 invalid", source_path="null.yaml", source_tier="project")
    assert _codes(null_byte.value) == {"PACK_ENCODING_INVALID"}


def test_pack_hash_is_line_ending_independent(tmp_path: Path) -> None:
    payload = _yaml("valid_profile_v1.yaml")
    lf_path = tmp_path / "lf.yaml"
    _write_pack(lf_path, payload)
    crlf_path = tmp_path / "crlf.yaml"
    crlf_path.write_bytes(lf_path.read_bytes().replace(b"\n", b"\r\n"))
    lf = load_local_pack(lf_path, allowed_root=tmp_path)
    crlf = load_local_pack(crlf_path, allowed_root=tmp_path)
    assert lf.content_hash == crlf.content_hash


def test_loader_rejects_symlinked_pack_files(tmp_path: Path) -> None:
    payload = _yaml("valid_profile_v1.yaml")
    target = tmp_path / "target.yaml"
    link = tmp_path / "link.yaml"
    _write_pack(target, payload)
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(GovernanceError) as symlink:
        load_local_pack(link, allowed_root=tmp_path)
    assert _codes(symlink.value) == {"PACK_SYMLINK_REJECTED"}


def test_loader_checks_trust_root_components_before_resolving(
    tmp_path: Path,
    monkeypatch,
) -> None:
    payload = _yaml("valid_profile_v1.yaml")
    link_root = tmp_path / "link_root"
    profiles = link_root / "profiles"
    profiles.mkdir(parents=True)
    pack_path = profiles / "profile.yaml"
    _write_pack(pack_path, payload)

    original_is_symlink = Path.is_symlink

    def simulated_ancestor_symlink(path: Path) -> bool:
        return path == link_root or original_is_symlink(path)

    def unexpected_resolve(*args: Any, **kwargs: Any) -> Path:
        raise AssertionError("path resolution ran before symlink inspection")

    monkeypatch.setattr(Path, "is_symlink", simulated_ancestor_symlink)
    monkeypatch.setattr(Path, "resolve", unexpected_resolve)
    with pytest.raises(GovernanceError) as symlink:
        load_local_pack(
            pack_path,
            allowed_root=pack_path.parent,
            trust_root=tmp_path,
        )
    assert _codes(symlink.value) == {"PACK_SYMLINK_REJECTED"}


def test_loader_preserves_parent_traversal_before_symlink_inspection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    payload = _yaml("valid_profile_v1.yaml")
    root = tmp_path / "root"
    link = root / "link"
    real = root / "real"
    real.mkdir(parents=True)
    _write_pack(real / "profile.yaml", payload)
    candidate = link / ".." / "profile.yaml"

    original_is_symlink = Path.is_symlink

    def simulated_traversed_symlink(path: Path) -> bool:
        return path == link or original_is_symlink(path)

    def unexpected_resolve(*args: Any, **kwargs: Any) -> Path:
        raise AssertionError("path resolution ran before symlink inspection")

    monkeypatch.setattr(Path, "is_symlink", simulated_traversed_symlink)
    monkeypatch.setattr(Path, "resolve", unexpected_resolve)
    with pytest.raises(GovernanceError) as symlink:
        load_local_pack(
            candidate,
            allowed_root=candidate.parent,
            trust_root=tmp_path,
        )
    assert _codes(symlink.value) == {"PACK_SYMLINK_REJECTED"}


def test_loader_parent_traversal_cannot_escape_trust_root(tmp_path: Path) -> None:
    payload = _yaml("valid_profile_v1.yaml")
    trust_root = tmp_path / "trust"
    trust_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    pack_path = outside / "profile.yaml"
    _write_pack(pack_path, payload)
    traversing_path = trust_root / ".." / "outside" / "profile.yaml"

    with pytest.raises(GovernanceError) as traversal:
        load_local_pack(
            traversing_path,
            allowed_root=traversing_path.parent,
            trust_root=trust_root,
        )
    assert _codes(traversal.value) == {"PACK_PATH_OUTSIDE_ROOT"}


def test_registry_precedence_is_deterministic_and_cycles_fail_closed(tmp_path: Path) -> None:
    payload = _yaml("valid_profile_v1.yaml")
    project_path = tmp_path / "project.yaml"
    explicit_path = tmp_path / "explicit.yaml"
    _write_pack(project_path, payload)
    explicit = deepcopy(payload)
    explicit["version"] = "1.0.1"
    _write_pack(explicit_path, explicit)

    registry = GovernanceRegistry()
    registry.register_path(project_path, allowed_root=tmp_path, source_tier="project")
    registry.register_path(explicit_path, allowed_root=tmp_path, source_tier="explicit_path")
    assert registry.resolve_profile("delivery_profile").version == "1.0.1"
    assert registry.resolution_trace == (
        {
            "id": "org.example.delivery_profile",
            "selected_tier": "explicit_path",
            "shadowed_tier": "project",
        },
    )

    first = _yaml("valid_module_v1.yaml")
    first["id"] = "org.example.first"
    first["name"] = "first"
    first["dependencies"] = ["org.example.second"]
    second = deepcopy(first)
    second["id"] = "org.example.second"
    second["name"] = "second"
    second["dependencies"] = ["org.example.first"]
    first_path = tmp_path / "first.yaml"
    second_path = tmp_path / "second.yaml"
    _write_pack(first_path, first)
    _write_pack(second_path, second)
    cycle_registry = GovernanceRegistry()
    cycle_registry.register_path(first_path, allowed_root=tmp_path, source_tier="project")
    cycle_registry.register_path(second_path, allowed_root=tmp_path, source_tier="project")
    with pytest.raises(GovernanceError) as cycle:
        cycle_registry.dependency_order(None, ["first"])
    assert _codes(cycle.value) == {"PACK_DEPENDENCY_CYCLE"}


def test_registry_order_duplicate_detection_composition_and_locks(tmp_path: Path) -> None:
    profile_payload = _yaml("valid_profile_v1.yaml")
    module_payload = _yaml("valid_module_v1.yaml")
    profile_path = tmp_path / "z-profile.yaml"
    module_path = tmp_path / "a-module.yaml"
    _write_pack(profile_path, profile_payload)
    _write_pack(module_path, module_payload)

    registry = GovernanceRegistry()
    registry.register_directory(tmp_path, source_tier="project")
    assert registry.profile_names == ("delivery_profile",)
    assert registry.module_names == ("fixture_evidence_integrity",)

    with pytest.raises(GovernanceError) as duplicate:
        registry.register_path(profile_path, allowed_root=tmp_path, source_tier="project")
    assert _codes(duplicate.value) == {"PACK_DUPLICATE_IDENTITY"}

    first = compose_governance(
        registry,
        profile_identity="delivery_profile",
        module_ids=["fixture_evidence_integrity"],
    )
    second = compose_governance(
        registry,
        profile_identity="delivery_profile",
        module_ids=[
            "org.example.fixture_evidence_integrity",
            "fixture_evidence_integrity",
        ],
    )
    assert first.to_dict() == second.to_dict()
    assert "evidence" in first.required_blocks
    assert {item["id"] for item in first.evidence_requirements} == {
        "review_record",
        "test_report",
    }
    assert {item["element_kind"] for item in first.provenance} >= {
        "pack",
        "policy",
        "evidence",
        "approval",
        "evaluation",
        "rule",
        "starter_fragment",
    }

    lock = lock_for_packs([*first.modules, first.profile])  # type: ignore[list-item]
    assert compose_governance(
        registry,
        profile_identity="delivery_profile",
        module_ids=["fixture_evidence_integrity"],
        lock=lock,
    ).to_dict() == first.to_dict()
    shortened = type(lock)(lock.resolved[:-1])
    with pytest.raises(GovernanceError) as mismatch:
        compose_governance(
            registry,
            profile_identity="delivery_profile",
            module_ids=["fixture_evidence_integrity"],
            lock=shortened,
        )
    assert _codes(mismatch.value) == {"PACK_LOCK_SET_MISMATCH"}

    first_lock = write_lock(tmp_path / "first.lock", lock).read_bytes()
    second_lock = write_lock(tmp_path / "second.lock", lock).read_bytes()
    assert first_lock == second_lock
    assert b"timestamp" not in first_lock and b"generated_at" not in first_lock


def test_composition_rejects_cross_module_approval_weakening(tmp_path: Path) -> None:
    base = _yaml("valid_module_v1.yaml")
    base["rules"] = []
    denied = deepcopy(base)
    denied["id"] = "org.example.a_denied"
    denied["name"] = "a_denied"
    denied["approval_requirements"] = [
        {
            "id": "merge_gate",
            "required_roles": [],
            "eligible_roles": [],
            "denied_actor_types": ["ai_tool"],
            "required_evidence": [],
            "actions": ["merge"],
            "timing": "before_merge",
        }
    ]
    eligible = deepcopy(base)
    eligible["id"] = "org.example.b_eligible"
    eligible["name"] = "b_eligible"
    eligible["approval_requirements"] = [
        {
            "id": "merge_gate",
            "required_roles": [],
            "eligible_roles": ["ai_tool"],
            "denied_actor_types": [],
            "required_evidence": [],
            "actions": ["merge"],
            "timing": "before_merge",
        }
    ]
    denied_path = tmp_path / "a.yaml"
    eligible_path = tmp_path / "b.yaml"
    _write_pack(denied_path, denied)
    _write_pack(eligible_path, eligible)
    registry = GovernanceRegistry()
    registry.register_directory(tmp_path, source_tier="project")
    with pytest.raises(GovernanceError) as weakening:
        compose_governance(registry, profile_identity=None, module_ids=["b_eligible", "a_denied"])
    # The intrinsic prohibition now trips at the normalization boundary,
    # before the cross-pack monotonicity merge is even reached.
    assert _codes(weakening.value) == {"APPROVAL_CORE_DENIED_ACTOR_ELIGIBLE"}


def test_core_denied_actors_fail_at_the_normalization_boundary() -> None:
    # F1: an AI tool or execution surface can never normalize as an eligible
    # or required approver, so references_role fails closed on such gates.
    normalized = normalize_approval(
        {"id": "g", "eligible_approver_roles": ["ai_tool"], "required_evidence": ["x"]},
        shape="governed_package_gate",
        path="approvals[0]",
        fallback_id="g",
    )
    assert normalized.resolution == "invalid"
    assert "APPROVAL_CORE_DENIED_ACTOR_ELIGIBLE" in {
        item.code for item in normalized.diagnostics
    }
    rule = _rule(requirement={"path": "approvals", "references_role": "ai_tool"})
    document = {
        "approvals": [
            {"id": "g", "eligible_approver_roles": ["ai_tool"], "required_evidence": ["x"]}
        ]
    }
    diagnostics = evaluate_rule(document, rule)
    assert [item.code for item in diagnostics] == ["RULE_REFERENCE_TYPE_ERROR"]


def _genuine_normalized_approval() -> dict[str, Any]:
    return normalize_approval(
        {
            "name": "gate",
            "required_roles": ["reviewer"],
            "eligible_roles": ["reviewer", "security"],
            "denied_approver_types": ["ai_tool"],
            "required_evidence": ["review_record"],
            "required_for": ["merge"],
        },
        shape="generated_profile_approval",
        path="approvals[0]",
        fallback_id="gate",
    ).to_dict()


@pytest.mark.parametrize(
    "mutation_id",
    [
        # structural invariants
        "missing_id",
        "missing_resolution",
        "missing_required_roles",
        "missing_eligible_roles",
        "roles_as_mapping",
        "roles_as_null",
        "non_string_role_entry",
        "duplicate_roles",
        "unknown_resolution",
        "unknown_extra_field",
        # semantic invariants (schema-valid but forged)
        "resolution_invalid",
        "forged_complete_with_core_denied_eligible",
        "required_role_not_eligible",
        "eligible_role_also_denied",
        "complete_with_error_diagnostic",
        "reference_only_with_roles",
        "source_roles_removed",
        "source_shape_diverges",
        "canonical_roles_diverge_from_source",
    ],
)
def test_pre_normalized_approval_invariant_matrix(mutation_id: str) -> None:
    # A payload carrying the normalized-approval schema marker is re-validated
    # end to end: schema shape, diagnostic consistency, resolution/role
    # consistency, and full re-normalization of the semantic invariants.
    # Every mutation of a genuine normalized object must fail closed.
    base = _genuine_normalized_approval()
    source_roles_removed = deepcopy(base)
    source_roles_removed["source"]["raw"] = {"name": "gate"}
    source_shape_diverges = deepcopy(base)
    source_shape_diverges["source"]["shape"] = "legacy_goal_text"
    source_shape_diverges["source"]["raw"] = "no named approver"
    mutations: dict[str, dict[str, Any]] = {
        "missing_id": {key: value for key, value in base.items() if key != "id"},
        "missing_resolution": {
            key: value for key, value in base.items() if key != "resolution"
        },
        "missing_required_roles": {
            key: value for key, value in base.items() if key != "required_roles"
        },
        "missing_eligible_roles": {
            key: value for key, value in base.items() if key != "eligible_roles"
        },
        "roles_as_mapping": {**base, "eligible_roles": {"reviewer": False}},
        "roles_as_null": {**base, "required_roles": None},
        "non_string_role_entry": {**base, "eligible_roles": ["reviewer", 7]},
        "duplicate_roles": {**base, "eligible_roles": ["reviewer", "reviewer"]},
        "unknown_resolution": {**base, "resolution": "definitely_fine"},
        "unknown_extra_field": {**base, "trusted": True},
        "resolution_invalid": {**base, "resolution": "invalid"},
        "forged_complete_with_core_denied_eligible": {
            **base,
            "eligible_roles": ["reviewer", "ai_tool"],
            "denied_actor_types": [],
        },
        "required_role_not_eligible": {
            **base,
            "required_roles": ["ghost"],
            "eligible_roles": ["reviewer"],
        },
        "eligible_role_also_denied": {
            **base,
            "eligible_roles": ["reviewer", "ai_tool"],
        },
        "complete_with_error_diagnostic": {
            **base,
            "normalization_diagnostics": [
                {
                    "code": "APPROVAL_ACTOR_ELIGIBLE_AND_DENIED",
                    "level": "error",
                    "message": "forged",
                }
            ],
        },
        "reference_only_with_roles": {**base, "resolution": "reference_only"},
        "source_roles_removed": source_roles_removed,
        "source_shape_diverges": source_shape_diverges,
        "canonical_roles_diverge_from_source": {
            **base,
            "required_roles": [],
            "eligible_roles": ["admin"],
        },
    }
    payload = mutations[mutation_id]
    for role in ("reviewer", "admin", "ai_tool", "ghost"):
        rule = _rule(requirement={"path": "approvals", "references_role": role})
        diagnostics = evaluate_rule({"approvals": [payload]}, rule)
        assert [item.code for item in diagnostics] == [
            "RULE_REFERENCE_TYPE_ERROR"
        ], (mutation_id, role)


def test_pre_normalized_approval_genuine_payload_still_resolves() -> None:
    base = _genuine_normalized_approval()
    reviewer_rule = _rule(requirement={"path": "approvals", "references_role": "reviewer"})
    assert evaluate_rule({"approvals": [base]}, reviewer_rule) == ()
    ghost_rule = _rule(requirement={"path": "approvals", "references_role": "ghost"})
    diagnostics = evaluate_rule({"approvals": [base]}, ghost_rule)
    assert [item.code for item in diagnostics] == ["RULE_REQUIREMENT_FAILED"]

    reference_only = normalize_approval(
        "HumanMergeApproval",
        shape="legacy_contract_reference",
        path="contracts[0].approval",
        fallback_id="approval-0",
    ).to_dict()
    diagnostics = evaluate_rule({"approvals": [reference_only]}, reviewer_rule)
    assert [item.code for item in diagnostics] == ["RULE_REQUIREMENT_FAILED"]


def test_structural_errors_in_when_fail_closed() -> None:
    # F2: a malformed document must not silently disable a rule.
    rule = _rule(
        when={"path": "changes[].risk", "equals": "high"},
        requirement={"path": "approvals", "exists": True},
    )
    diagnostics = evaluate_rule({"changes": "not-a-list"}, rule)
    assert [item.code for item in diagnostics] == ["RULE_COLLECTION_TYPE_ERROR"]
    assert diagnostics[0].level == "error"


def test_all_mode_when_requires_a_single_satisfying_element() -> None:
    # F5: with same-prefix `all` predicates, the condition matches only if one
    # element satisfies every predicate.
    rule = _rule(
        when={
            "all": [
                {"path": "changes[].risk", "equals": "high"},
                {"path": "changes[].type", "equals": "feature"},
            ]
        },
        requirement={"path": "changes[].owner", "exists": True},
    )
    split = {
        "changes": [
            {"risk": "high", "type": "fix", "owner": "a"},
            {"risk": "low", "type": "feature", "owner": "b"},
        ]
    }
    assert evaluate_rule(split, rule) == ()
    joint = {
        "changes": [
            {"risk": "high", "type": "feature"},
            {"risk": "low", "type": "fix", "owner": "b"},
        ]
    }
    diagnostics = evaluate_rule(joint, rule)
    assert diagnostics and all(item.binding == (("changes", 0),) for item in diagnostics)


def test_duplicate_lock_entries_are_rejected(tmp_path: Path) -> None:
    # F3: duplicate lock ids must fail before dictionary collapse.
    from nornyx.governance.locks import load_lock, verify_lock
    from nornyx.governance.models import LockEntry, ProfileLock

    registry = GovernanceRegistry.builtins()
    profile = registry.resolve_profile("minimal")
    stale = LockEntry(
        id=profile.id,
        version="9.9.9",
        source_tier="builtin",
        content_hash="sha256:" + "0" * 64,
        path_hint="x",
    )
    fresh = LockEntry(
        id=profile.id,
        version=profile.version,
        source_tier="builtin",
        content_hash=profile.content_hash,
        path_hint="y",
    )
    with pytest.raises(GovernanceError) as duplicated:
        verify_lock(ProfileLock((stale, fresh)), [profile])
    assert _codes(duplicated.value) == {"PACK_LOCK_DUPLICATE_ID"}

    lock_path = tmp_path / "nornyx.profiles.lock"
    lock_path.write_text(
        json.dumps(
            {
                "schema": "nornyx.profiles_lock.v1",
                "resolved": [stale.to_dict(), fresh.to_dict()],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(GovernanceError) as loaded:
        load_lock(lock_path)
    assert _codes(loaded.value) == {"PACK_LOCK_DUPLICATE_ID"}


def test_rule_caps_apply_per_pack_and_per_composition(tmp_path: Path, monkeypatch) -> None:
    # F4: a pack over the per-pack cap fails to load, and composition enforces
    # the composed-rule cap.
    module = _yaml("valid_module_v1.yaml")

    def cap_rule(index: int) -> dict[str, Any]:
        return {
            "id": f"CAP-{index:03d}",
            "description": f"cap {index}",
            "require": [{"path": "project", "exists": True}],
            "severity": "warning",
            "message": f"cap {index}",
        }

    module["rules"] = [cap_rule(index) for index in range(201)]
    over_path = tmp_path / "over.yaml"
    _write_pack(over_path, module)
    with pytest.raises(GovernanceError) as over_cap:
        load_local_pack(over_path, allowed_root=tmp_path, source_tier="project")
    # The per-pack cap is enforced primarily by the schema (maxItems: 200);
    # the loader keeps PACK_LIMIT_EXCEEDED as a backstop for API callers.
    assert _codes(over_cap.value) <= {"PACK_SCHEMA_INVALID", "PACK_LIMIT_EXCEEDED"}
    assert _codes(over_cap.value)

    from nornyx.governance import composition as composition_module

    module["rules"] = [cap_rule(index) for index in range(3)]
    ok_path = tmp_path / "ok.yaml"
    _write_pack(ok_path, module)
    registry = GovernanceRegistry.builtins()
    registry.register_path(ok_path, allowed_root=tmp_path, source_tier="project")
    monkeypatch.setattr(composition_module, "MAX_COMPOSED_RULES", 2)
    with pytest.raises(GovernanceError) as composed_cap:
        compose_governance(
            registry,
            profile_identity=None,
            module_ids=["fixture_evidence_integrity"],
        )
    assert _codes(composed_cap.value) == {"PACK_LIMIT_EXCEEDED"}


def test_same_pack_duplicate_item_ids_are_fatal(tmp_path: Path) -> None:
    # F6: duplicate ids inside one pack are author errors, not merges.
    module = _yaml("valid_module_v1.yaml")
    module["rules"] = []
    module["policies"] = [
        {"id": "dup_policy", "deny": ["a"], "require": []},
        {"id": "dup_policy", "deny": ["b"], "require": []},
    ]
    path = tmp_path / "dup.yaml"
    _write_pack(path, module)
    registry = GovernanceRegistry.builtins()
    registry.register_path(path, allowed_root=tmp_path, source_tier="project")
    with pytest.raises(GovernanceError) as duplicated:
        compose_governance(
            registry,
            profile_identity=None,
            module_ids=["fixture_evidence_integrity"],
        )
    assert _codes(duplicated.value) == {"PACK_DUPLICATE_ID"}


def test_resolve_sees_project_tier_and_verifies_existing_locks(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    # F7: resolve discovers project-local packs and verifies an existing lock
    # instead of overwriting it; a stale lock exits 2.
    profile = _yaml("valid_profile_v1.yaml")
    profile_dir = tmp_path / ".nornyx" / "profiles"
    profile_dir.mkdir(parents=True)
    _write_pack(profile_dir / "delivery.yaml", profile)
    monkeypatch.chdir(tmp_path)

    assert main(["profiles", "resolve", "delivery_profile", "--lock", "--json"]) == 0
    written = json.loads(capsys.readouterr().out)
    assert written["status"] == "resolved"
    assert (tmp_path / "nornyx.profiles.lock").is_file()

    assert main(["profiles", "resolve", "delivery_profile", "--json"]) == 0
    verified = json.loads(capsys.readouterr().out)
    assert verified["lock_verified"] is True

    stale = deepcopy(profile)
    stale["version"] = "1.0.1"
    _write_pack(profile_dir / "delivery.yaml", stale)
    assert main(["profiles", "resolve", "delivery_profile", "--json"]) == 2
    mismatch = json.loads(capsys.readouterr().out)
    codes = {item["code"] for item in mismatch["diagnostics"]}
    assert "PACK_LOCK_MISMATCH" in codes


def test_composed_approvals_always_carry_core_denials(tmp_path: Path) -> None:
    # A single pack must not be able to make an AI tool or execution surface
    # an eligible approver, and every composed approval carries the core
    # denied set even when the pack declared none.
    base = _yaml("valid_module_v1.yaml")
    base["rules"] = []
    grant = deepcopy(base)
    grant["id"] = "org.example.ai_grant"
    grant["name"] = "ai_grant"
    grant["approval_requirements"] = [
        {
            "id": "merge_gate",
            "required_roles": [],
            "eligible_roles": ["ai_tool"],
            "denied_actor_types": [],
            "required_evidence": [],
            "actions": ["merge"],
            "timing": "before_merge",
        }
    ]
    grant_path = tmp_path / "grant.yaml"
    _write_pack(grant_path, grant)
    registry = GovernanceRegistry()
    registry.register_path(grant_path, allowed_root=tmp_path, source_tier="project")
    with pytest.raises(GovernanceError) as rejected:
        compose_governance(registry, profile_identity=None, module_ids=["ai_grant"])
    assert _codes(rejected.value) == {"APPROVAL_CORE_DENIED_ACTOR_ELIGIBLE"}

    clean = deepcopy(base)
    clean["id"] = "org.example.clean"
    clean["name"] = "clean"
    clean_path = tmp_path / "clean.yaml"
    _write_pack(clean_path, clean)
    clean_registry = GovernanceRegistry()
    clean_registry.register_path(clean_path, allowed_root=tmp_path, source_tier="project")
    composed = compose_governance(clean_registry, profile_identity=None, module_ids=["clean"])
    for approval in composed.approval_requirements:
        assert "ai_tool" in approval.denied_actor_types
        assert "execution_surface" in approval.denied_actor_types
        assert "execution_surface" in approval.denied_execution_surfaces


def test_check_warns_but_passes_for_unresolved_free_form_profile(tmp_path: Path, capsys) -> None:
    # project.profile has always been free-form; a value that matches no pack
    # must keep passing `nornyx check` (warning only). Explicit project.modules
    # remains fail-closed.
    contract = tmp_path / "legacy.nyx"
    contract.write_text(
        'nornyx: "0.1"\nproject:\n  name: Legacy\n  profile: my_custom_house_profile\n',
        encoding="utf-8",
    )
    assert main(["check", str(contract)]) == 0
    output = capsys.readouterr().out
    assert "PACK_NOT_RESOLVED" in output
    assert "Nornyx check passed" in output

    strict = tmp_path / "strict.nyx"
    strict.write_text(
        'nornyx: "0.1"\nproject:\n  name: Strict\n  profile: my_custom_house_profile\n'
        "  modules: [missing_module]\n",
        encoding="utf-8",
    )
    assert main(["check", str(strict)]) == 1
    assert "PACK_NOT_FOUND" in capsys.readouterr().out


def test_duplicate_equal_starter_fragments_merge_idempotently(tmp_path: Path) -> None:
    payload = _yaml("valid_profile_v1.yaml")
    extra = deepcopy(payload["starter_fragments"][-1])
    payload["starter_fragments"].append(extra)
    path = tmp_path / "dup.yaml"
    _write_pack(path, payload)
    pack = load_local_pack(path, allowed_root=tmp_path)
    from nornyx.profiles import render_profile_document

    document = render_profile_document(pack, "DupDemo")  # type: ignore[arg-type]
    single = load_local_pack(_single_fragment_copy(tmp_path, payload), allowed_root=tmp_path)
    assert document == render_profile_document(single, "DupDemo")  # type: ignore[arg-type]


def _single_fragment_copy(tmp_path: Path, payload: dict[str, Any]) -> Path:
    reduced = deepcopy(payload)
    reduced["starter_fragments"] = reduced["starter_fragments"][:-1]
    path = tmp_path / "single.yaml"
    _write_pack(path, reduced)
    return path


def test_org_tier_requires_a_matching_lock(tmp_path: Path) -> None:
    payload = _yaml("valid_module_v1.yaml")
    path = tmp_path / "org-module.yaml"
    _write_pack(path, payload)
    registry = GovernanceRegistry()
    module = registry.register_path(path, allowed_root=tmp_path, source_tier="org")
    with pytest.raises(GovernanceError) as required:
        compose_governance(
            registry,
            profile_identity=None,
            module_ids=["fixture_evidence_integrity"],
        )
    assert _codes(required.value) == {"PACK_LOCK_REQUIRED"}
    lock = lock_for_packs([module])
    result = compose_governance(
        registry,
        profile_identity=None,
        module_ids=["fixture_evidence_integrity"],
        lock=lock,
    )
    assert result.modules == (module,)


@pytest.mark.parametrize(
    ("value", "operator", "operand", "passes"),
    [
        ("high", "equals", "high", True),
        ("high", "not_equals", "low", True),
        ("high", "in", ["low", "high"], True),
        ("high", "not_in", ["low"], True),
        ("profile.alpha", "matches_id", "profile.*", True),
        (["test", "review"], "contains", "test", True),
        (["test", "review"], "contains_all", ["test", "review"], True),
        (["test"], "min_count", 1, True),
        (["test"], "max_count", 1, True),
    ],
)
def test_closed_rule_operators(
    value: Any,
    operator: str,
    operand: Any,
    passes: bool,
) -> None:
    diagnostics = evaluate_rule(
        {"value": value},
        _rule(requirement={"path": "value", operator: operand}),
    )
    assert (diagnostics == ()) is passes


def test_reference_rule_operators_normalize_approval_roles() -> None:
    document = {
        "approvals": [
            {
                "name": "HumanReview",
                "eligible_roles": ["reviewer"],
                "required_for": ["merge"],
            }
        ],
        "evidence": {"required": ["review_record"]},
        "gates": [{"id": "merge_gate"}],
    }
    assert evaluate_rule(
        document,
        _rule(requirement={"path": "approvals", "references_role": "reviewer"}),
    ) == ()
    assert evaluate_rule(
        document,
        _rule(requirement={"path": "evidence", "references_evidence": "review_record"}),
    ) == ()
    assert evaluate_rule(
        document,
        _rule(requirement={"path": "gates", "references_approval": "merge_gate"}),
    ) == ()


def test_packaged_builtin_authority_and_public_v1_api() -> None:
    root = resources.files("nornyx") / "profiles_data"
    catalog = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
    assert catalog["profiles"] == PROFILE_NAMES
    for name in PROFILE_NAMES:
        payload = yaml.safe_load((root / f"{name}.yaml").read_text(encoding="utf-8"))
        assert payload["integrity"]["content_hash"] == canonical_pack_hash(payload)
        assert profile_pack_v1(name) == payload
        stale_scopes = [
            scope
            for fragment in payload["starter_fragments"]
            if isinstance(fragment["content"], dict)
            for goal in fragment["content"].get("goals", [])
            for scope in goal.get("scope", [])
            if scope.startswith("profiles/")
        ]
        assert stale_scopes == [], name


def test_profiles_cli_and_explicit_profile_init(tmp_path: Path, monkeypatch, capsys) -> None:
    assert main(["profiles", "list", "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert [item["name"] for item in listed["profiles"]] == PROFILE_NAMES

    assert main(["profiles", "inspect", "minimal", "--json"]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["profile"]["schema"] == "nornyx.profile_pack.v1"

    payload = _yaml("valid_profile_v1.yaml")
    pack_path = tmp_path / "profile.yaml"
    _write_pack(pack_path, payload)
    assert main(["profiles", "validate", str(pack_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "valid"

    target = tmp_path / "explicit.nyx"
    assert main(
        [
            "init",
            "--profile-path",
            str(pack_path),
            "--name",
            "ExplicitDemo",
            "--out",
            str(target),
        ]
    ) == 0
    capsys.readouterr()
    rendered = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert rendered["project"]["name"] == "ExplicitDemo"
    assert rendered["project"]["profile"] == "delivery_profile"
    assert "test_report.json" in rendered["evidence"]["required"]

    monkeypatch.chdir(tmp_path)
    assert main(["profiles", "resolve", "minimal", "--lock", "--json"]) == 0
    resolved = json.loads(capsys.readouterr().out)
    assert resolved["status"] == "resolved"
    assert (tmp_path / "nornyx.profiles.lock").is_file()


def _assert_profile_cli_path_rejected(
    relative_path: Path,
    target: Path,
    capsys,
) -> None:
    assert main(["profiles", "validate", str(relative_path), "--json"]) == 1
    assert "PACK_SYMLINK_REJECTED" in capsys.readouterr().out

    assert main(
        [
            "init",
            "--profile-path",
            str(relative_path),
            "--name",
            "SymlinkRejected",
            "--out",
            str(target),
        ]
    ) == 1
    assert "PACK_SYMLINK_REJECTED" in capsys.readouterr().out
    assert not target.exists()


@pytest.mark.parametrize("link_kind", ["file", "directory"])
def test_profile_cli_entrypoints_reject_symlinked_pack_paths(
    link_kind: str,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    payload = _yaml("valid_profile_v1.yaml")
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    pack_path = real_dir / "profile.yaml"
    _write_pack(pack_path, payload)
    try:
        if link_kind == "file":
            requested = tmp_path / "profile-link.yaml"
            requested.symlink_to(pack_path)
        else:
            linked_dir = tmp_path / "profile-dir-link"
            linked_dir.symlink_to(real_dir, target_is_directory=True)
            requested = linked_dir / "profile.yaml"
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")

    monkeypatch.chdir(tmp_path)
    _assert_profile_cli_path_rejected(
        requested.relative_to(tmp_path),
        tmp_path / f"{link_kind}.nyx",
        capsys,
    )


def test_profile_cli_entrypoints_reject_symlinked_ancestor_above_pack_parent(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    payload = _yaml("valid_profile_v1.yaml")
    profiles = tmp_path / "real_root" / "profiles"
    profiles.mkdir(parents=True)
    _write_pack(profiles / "profile.yaml", payload)
    link_root = tmp_path / "link_root"
    try:
        link_root.symlink_to(tmp_path / "real_root", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")

    monkeypatch.chdir(tmp_path)
    _assert_profile_cli_path_rejected(
        Path("link_root") / "profiles" / "profile.yaml",
        tmp_path / "ancestor.nyx",
        capsys,
    )


def test_profile_cli_entrypoints_reject_symlink_before_parent_traversal(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    payload = _yaml("valid_profile_v1.yaml")
    root = tmp_path / "root"
    real = root / "real"
    (real / "subdir").mkdir(parents=True)
    _write_pack(real / "profile.yaml", payload)
    link = root / "link"
    try:
        link.symlink_to(real / "subdir", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")

    monkeypatch.chdir(tmp_path)
    _assert_profile_cli_path_rejected(
        Path("root") / "link" / ".." / "profile.yaml",
        tmp_path / "parent-traversal.nyx",
        capsys,
    )


@pytest.mark.parametrize(
    "source_mutation",
    [
        "invalid_raw",
        "invalid_timing",
        "malformed_revision_binding",
        "inconsistent_shape",
    ],
)
def test_check_fails_closed_on_adversarial_retained_approval_source(
    source_mutation: str,
    tmp_path: Path,
    capsys,
) -> None:
    approval = _genuine_normalized_approval()
    if source_mutation == "invalid_raw":
        approval["source"]["raw"] = ["not", "an", "approval"]
    elif source_mutation == "invalid_timing":
        approval["source"]["raw"]["timing"] = "after_everything"
    elif source_mutation == "malformed_revision_binding":
        approval["source"]["raw"]["revision_binding"] = {"kind": "git"}
    else:
        approval["source"]["shape"] = "legacy_goal_text"

    module = _yaml("valid_module_v1.yaml")
    module["rules"] = [
        {
            "id": "APPROVAL-001",
            "description": "A reviewer must be authorized.",
            "require": [
                {
                    "path": "experimental.normalized_approvals",
                    "references_role": "reviewer",
                }
            ],
            "severity": "error",
            "message": "A reviewer is required.",
        }
    ]
    module_dir = tmp_path / ".nornyx" / "modules"
    module_dir.mkdir(parents=True)
    _write_pack(module_dir / "fixture_evidence_integrity.yaml", module)

    document = profile_document("minimal", "ApprovalBoundary")
    document["project"]["modules"] = ["fixture_evidence_integrity"]
    document.setdefault("experimental", {})["normalized_approvals"] = [approval]
    contract = tmp_path / "project.nyx"
    contract.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    assert main(["check", str(contract)]) == 1
    assert "RULE_REFERENCE_TYPE_ERROR" in capsys.readouterr().out


def test_check_runs_project_local_module_rules(tmp_path: Path, capsys) -> None:
    module = _yaml("valid_module_v1.yaml")
    module["rules"] = [
        {
            "id": "GOV-001",
            "description": "A project marker is required.",
            "require": [{"path": "project.governance_marker", "equals": True}],
            "severity": "error",
            "message": "Project governance marker is required.",
        }
    ]
    module_dir = tmp_path / ".nornyx" / "modules"
    module_dir.mkdir(parents=True)
    _write_pack(module_dir / "fixture_evidence_integrity.yaml", module)

    document = profile_document("minimal", "LocalModule")
    document["project"]["modules"] = ["fixture_evidence_integrity"]
    contract = tmp_path / "project.nyx"
    contract.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    assert main(["check", str(contract)]) == 1
    output = capsys.readouterr().out
    assert "RULE_PATH_MISSING" in output
    assert "org.example.fixture_evidence_integrity/GOV-001" in output

    document["project"]["governance_marker"] = True
    contract.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    assert main(["check", str(contract)]) == 0
    assert "Nornyx check passed" in capsys.readouterr().out


def test_every_rule_semantics_fixture_executes_against_the_runtime() -> None:
    covered: set[str] = set()
    for case in _json("rule_semantics_cases.json"):
        case_id = case["id"]
        covered.add(case_id)
        if case_id == "when_collection_existential_match":
            document = {"changes": [{"risk": value} for value in case["input"]]}
            rule = _rule(
                when={"path": "changes[].risk", "equals": case["operand"]},
                requirement={"path": "missing", "exists": True},
            )
            assert evaluate_rule(document, rule)
        elif case_id in {"when_collection_existential_no_match", "empty_collection_when"}:
            values = case["input"]
            document = {"changes": [{"risk": value} for value in values]}
            rule = _rule(
                when={"path": "changes[].risk", "equals": case.get("operand", "high")},
                requirement={"path": "missing", "exists": True},
            )
            assert evaluate_rule(document, rule) == ()
        elif case_id.startswith("require_collection_universal"):
            document = {
                "changes": [{"required_evidence": value} for value in case["input"]]
            }
            rule = _rule(
                requirement={
                    "path": "changes[].required_evidence",
                    "contains": case["operand"],
                }
            )
            diagnostics = evaluate_rule(document, rule)
            if case["outcome"] == "pass":
                assert diagnostics == ()
            else:
                assert [item.path for item in diagnostics] == case["diagnostic_paths"]
        elif case_id == "empty_collection_require":
            diagnostics = evaluate_rule(
                {"changes": []},
                _rule(requirement={"path": "changes[].risk", "exists": True}),
            )
            assert [item.code for item in diagnostics] == ["RULE_EMPTY_COLLECTION"]
        elif case_id.startswith("missing_path_when"):
            operator = "not_exists" if case_id.endswith("not_exists") else "exists"
            diagnostics = evaluate_rule(
                {},
                _rule(
                    when={"path": "missing", operator: True},
                    requirement={"path": "also_missing", "exists": True},
                ),
            )
            assert bool(diagnostics) is (case["outcome"] == "match")
        elif case_id == "missing_path_require":
            diagnostics = evaluate_rule(
                {}, _rule(requirement={"path": "missing", "exists": True})
            )
            assert [item.code for item in diagnostics] == ["RULE_PATH_MISSING"]
        elif case_id in {"null_is_present", "null_equals_null"}:
            operator = {"exists": True} if case["operator"] == "exists" else {"equals": None}
            assert evaluate_rule(
                {"value": None}, _rule(requirement={"path": "value", **operator})
            ) == ()
        elif case_id == "wrong_value_type":
            diagnostics = evaluate_rule(
                {"value": case["input"]},
                _rule(requirement={"path": "value", "contains": case["operand"]}),
            )
            assert [item.code for item in diagnostics] == ["RULE_COLLECTION_TYPE_ERROR"]
        elif case_id == "nested_collections":
            document = {
                "systems": [
                    {"components": group}
                    for group in case["input"]
                ]
            }
            diagnostics = evaluate_rule(
                document,
                _rule(requirement={"path": "systems[].components[]", "equals": True}),
            )
            assert [item.path for item in diagnostics] == case["diagnostic_paths"]
        elif case_id == "duplicate_matches":
            document = {"changes": [{"risk": "high", "evidence": []}]}
            diagnostics = evaluate_rule(
                document,
                _rule(
                    when={
                        "any": [
                            {"path": "changes[].risk", "equals": "high"},
                            {"path": "changes[].risk", "equals": "high"},
                        ]
                    },
                    requirement={"path": "changes[].evidence", "contains": "test"},
                ),
            )
            assert len(diagnostics) == 1
            assert diagnostics[0].path == "changes[0].evidence"
        elif case_id in {"unknown_operator", "invalid_path"}:
            payload = _yaml("valid_profile_v1.yaml")
            predicate = payload["validation_rules"][0]["require"][0]
            if case_id == "unknown_operator":
                predicate.pop("contains")
                predicate["python"] = "pass"
            else:
                predicate["path"] = case["input"]
            with pytest.raises(GovernanceError) as invalid:
                validate_payload(payload, "profile_pack_v1.schema.json")
            assert _codes(invalid.value) == {"PACK_SCHEMA_INVALID"}
        elif case_id == "scalar_used_as_collection":
            diagnostics = evaluate_rule(
                {"changes": case["input"]},
                _rule(requirement={"path": "changes[]", "exists": True}),
            )
            assert [item.code for item in diagnostics] == ["RULE_COLLECTION_TYPE_ERROR"]
        elif case_id == "collection_used_as_scalar":
            diagnostics = evaluate_rule(
                {"risk": case["input"]},
                _rule(requirement={"path": "risk", "equals": case["operand"]}),
            )
            assert [item.code for item in diagnostics] == ["RULE_SCALAR_TYPE_ERROR"]
        elif case_id == "same_prefix_when_selection":
            document = {
                "changes": [
                    {"risk": "low", "evidence": []},
                    {"risk": "high", "evidence": ["test"]},
                ]
            }
            assert evaluate_rule(
                document,
                _rule(
                    when={"path": "changes[].risk", "equals": "high"},
                    requirement={"path": "changes[].evidence", "contains": "test"},
                ),
            ) == ()
        elif case_id == "nested_under_selected_prefix":
            rule = _rule(
                when={"path": "changes[].risk", "equals": "high"},
                requirement={"path": "changes[].evidence[].kind", "equals": "x"},
            )
            compliant = {
                "changes": [
                    {"risk": "high", "evidence": [{"kind": "x"}]},
                    {"risk": "low", "evidence": [{"kind": "bad"}]},
                ]
            }
            assert evaluate_rule(compliant, rule) == ()
            violating = {
                "changes": [
                    {"risk": "high", "evidence": [{"kind": "bad"}]},
                    {"risk": "low", "evidence": [{"kind": "x"}]},
                ]
            }
            diagnostics = evaluate_rule(violating, rule)
            assert [item.path for item in diagnostics] == ["changes[0].evidence[0].kind"]
        elif case_id == "when_type_errors_fail_closed":
            equals_on_list = evaluate_rule(
                {"risk": ["high"]},
                _rule(
                    when={"path": "risk", "equals": "high"},
                    requirement={"path": "x", "exists": True},
                ),
            )
            assert [item.code for item in equals_on_list] == ["RULE_SCALAR_TYPE_ERROR"]
            contains_on_scalar = evaluate_rule(
                {"tags": "prod"},
                _rule(
                    when={"path": "tags", "contains": "prod"},
                    requirement={"path": "x", "exists": True},
                ),
            )
            assert [item.code for item in contains_on_scalar] == ["RULE_COLLECTION_TYPE_ERROR"]
            # Ordinary missing/non-match semantics remain silent.
            assert evaluate_rule(
                {},
                _rule(
                    when={"path": "missing", "equals": "x"},
                    requirement={"path": "x", "exists": True},
                ),
            ) == ()
        elif case_id == "shared_ancestor_all_join":
            rule = _rule(
                when={
                    "all": [
                        {"path": "changes[].risk", "equals": "high"},
                        {"path": "changes[].evidence[].kind", "equals": "x"},
                    ]
                },
                requirement={"path": "changes[].owner", "exists": True},
            )
            cross_element = {
                "changes": [
                    {"risk": "high", "evidence": [{"kind": "bad"}]},
                    {"risk": "low", "evidence": [{"kind": "x"}]},
                ]
            }
            assert evaluate_rule(cross_element, rule) == ()
            same_element = {
                "changes": [
                    {"risk": "high", "evidence": [{"kind": "x"}]},
                    {"risk": "low", "evidence": [{"kind": "bad"}], "owner": "b"},
                ]
            }
            diagnostics = evaluate_rule(same_element, rule)
            assert diagnostics
            assert all(item.binding == (("changes", 0),) for item in diagnostics)
        elif case_id == "different_prefix_no_join":
            document = {
                "changes": [{"risk": "high"}],
                "approvals": [{"roles": ["reviewer"]}, {"roles": []}],
            }
            diagnostics = evaluate_rule(
                document,
                _rule(
                    when={"path": "changes[].risk", "equals": "high"},
                    requirement={"path": "approvals[].roles", "contains": "reviewer"},
                ),
            )
            assert [item.path for item in diagnostics] == ["approvals[1].roles"]
        else:  # pragma: no cover - fixture additions must add executable semantics above
            raise AssertionError(f"unimplemented rule fixture {case_id}")

    assert covered == {item["id"] for item in _json("rule_semantics_cases.json")}
