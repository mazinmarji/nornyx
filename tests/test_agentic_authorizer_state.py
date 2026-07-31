"""Focused assurance for the additive Authorizer construction-state SPI."""

from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import dataclass, field, fields, is_dataclass, replace
import inspect
import json
from pathlib import Path
import shutil
import socket
import textwrap
from typing import Any, Mapping

import pytest

import nornyx.agentic.authz as authz_module
from nornyx.agentic import (
    ApprovalAssertion,
    ApprovalRequest,
    Authorizer,
    AuthorizerLoadCode,
    AuthorizerLoadError,
    AuthorizerState,
    CapabilityRequest,
    DecisionCode,
    DecisionEffect,
    EvaluationContext,
    EvidenceRecorder,
    SPI_VERSION,
    agentic_network_lock_digest,
    build_agentic_network_lock,
    compose_document_governance,
    contract_digest,
    load_authorizer,
    load_nyx,
    registry_for_contract,
    validate_runtime_events,
    verify_agentic_network_lock,
    write_agentic_network_lock,
)
from nornyx.governance import (
    CompositionResult,
    EffectiveApproval,
    GovernanceBlockSchema,
    GovernanceDiagnostic,
    GovernanceModule,
    NormalizedApproval,
    ProfilePack,
    Rule,
    StarterFragment,
)
from nornyx.governance.models import PackProvenance


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "agentic_network.nyx"
EVIDENCE = ROOT / "examples" / "governance_evidence"
AS_OF = "2026-07-17T10:00:00Z"
APPROVAL_REF = "agentic_network_authority"
ACTOR = "identity.researcher.local"

# The closed set of dataclass shapes a CompositionResult can carry. Field-by-
# field reconstruction in the frozen snapshot is only sound for keyword-
# constructible shapes, so this set is pinned rather than assumed.
COMPOSITION_DATACLASSES = (
    CompositionResult,
    EffectiveApproval,
    GovernanceBlockSchema,
    GovernanceDiagnostic,
    GovernanceModule,
    NormalizedApproval,
    PackProvenance,
    ProfilePack,
    Rule,
    StarterFragment,
)


def _controls(
    contract_path: Path = EXAMPLE,
) -> tuple[dict[str, Any], Any, dict[str, Any]]:
    document = load_nyx(contract_path)
    composition = compose_document_governance(
        document,
        registry=registry_for_contract(contract_path),
    )
    assert composition is not None
    lock_payload = build_agentic_network_lock(document, composition)
    return document, composition, lock_payload


def _local_controls(tmp_path: Path) -> tuple[Path, Path, dict[str, Any], Any, dict[str, Any]]:
    contract_path = tmp_path / "agentic_network.nyx"
    shutil.copyfile(EXAMPLE, contract_path)
    shutil.copytree(EVIDENCE, tmp_path / "governance_evidence")
    document, composition, lock_payload = _controls(contract_path)
    lock_path = tmp_path / "nornyx.agentic_network.lock"
    write_agentic_network_lock(lock_payload, lock_path)
    return contract_path, lock_path, document, composition, lock_payload


def _requirement(composition: Any, approval_ref: str) -> Any:
    return next(
        item
        for item in composition.approval_requirements
        if item.id == approval_ref
    )


def _mutable_binding_controls() -> tuple[dict[str, Any], Any, dict[str, Any], dict[str, Any]]:
    """Controls whose approval requirement carries a caller-owned mutable binding.

    ``revision_binding`` is the one decision-relevant approval field that is a
    mutable mapping rather than a tuple, so it is the exact surface on which an
    index built from the constructor parameter — instead of from the frozen
    retained composition — diverges from the retained state.
    """

    document, composition, _lock_payload = _controls()
    caller_binding: dict[str, Any] = {}
    composition = replace(
        composition,
        approval_requirements=tuple(
            replace(item, revision_binding=caller_binding)
            if item.id == APPROVAL_REF
            else item
            for item in composition.approval_requirements
        ),
    )
    lock_payload = build_agentic_network_lock(document, composition)
    return document, composition, lock_payload, caller_binding


def _granted_approval(subject_revision: str) -> ApprovalAssertion:
    """A human approval the example contract grants at ``AS_OF``."""

    return ApprovalAssertion(
        approval_ref=APPROVAL_REF,
        claimed_approver_ref="alice",
        claimed_actor_type="human",
        role="network_governance_owner",
        granted=True,
        action_ref="approve_agentic_network_contract",
        subject_revision=subject_revision,
        issued_at="2026-07-17T09:00:00Z",
        evidence_refs=("agentic_network_contract_review",),
    )


def _mutable_object_ids(value: Any, found: set[int] | None = None, depth: int = 0) -> set[int]:
    """Identity of every mutable container and dataclass reachable from ``value``.

    Only ``dict``/``list``/``set`` and dataclass instances are collected. Frozen
    snapshots contain none of those types, and immutable singletons such as
    ``()`` or ``frozenset()`` are legitimately shared, so this set is exactly the
    caller-owned state that must never be reachable from the Authorizer.
    """

    if found is None:
        found = set()
    if depth > 40 or id(value) in found:
        return found
    if is_dataclass(value) and not isinstance(value, type):
        found.add(id(value))
        for item in fields(value):
            _mutable_object_ids(getattr(value, item.name), found, depth + 1)
    elif isinstance(value, (dict, list, set)):
        found.add(id(value))
        items = value.values() if isinstance(value, dict) else value
        for item in items:
            _mutable_object_ids(item, found, depth + 1)
    elif isinstance(value, (Mapping, tuple, frozenset)):
        for item in (value.values() if isinstance(value, Mapping) else value):
            _mutable_object_ids(item, found, depth + 1)
    return found


def _reachable_object_ids(value: Any, found: set[int] | None = None, depth: int = 0) -> set[int]:
    """Identity of every container and dataclass reachable from ``value``."""

    if found is None:
        found = set()
    if depth > 40 or id(value) in found:
        return found
    if is_dataclass(value) and not isinstance(value, type):
        found.add(id(value))
        for item in fields(value):
            _reachable_object_ids(getattr(value, item.name), found, depth + 1)
    elif isinstance(value, Mapping):
        found.add(id(value))
        for item in value.values():
            _reachable_object_ids(item, found, depth + 1)
    elif isinstance(value, (list, tuple, set, frozenset)):
        found.add(id(value))
        for item in value:
            _reachable_object_ids(item, found, depth + 1)
    return found


def _reachable_dataclasses(value: Any, found: set[type] | None = None, depth: int = 0) -> set[type]:
    if found is None:
        found = set()
    if depth > 40:
        return found
    if is_dataclass(value) and not isinstance(value, type):
        found.add(type(value))
        for item in fields(value):
            _reachable_dataclasses(getattr(value, item.name), found, depth + 1)
    elif isinstance(value, Mapping):
        for item in value.values():
            _reachable_dataclasses(item, found, depth + 1)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _reachable_dataclasses(item, found, depth + 1)
    return found


def _container_kinds(value: Any, path: str = "") -> list[tuple[str, str]]:
    """Every container encountered in a serializer payload, with its exact type."""

    found: list[tuple[str, str]] = [(path, type(value).__name__)]
    if isinstance(value, Mapping):
        for key, item in value.items():
            found.extend(_container_kinds(item, f"{path}.{key}"))
    elif isinstance(value, (list, tuple, set, frozenset)):
        for index, item in enumerate(value):
            found.extend(_container_kinds(item, f"{path}[{index}]"))
    else:
        return []
    return found


def _compatibility_validate(authorizer: Authorizer, events: dict[str, Any]) -> dict[str, Any]:
    """Representative compatibility consumer using public state only."""

    state = authorizer.state
    return validate_runtime_events(
        state.document,
        state.composition,
        state.lock_payload,
        events,
    )


def test_state_is_the_exact_authorizer_construction_and_load_contract_is_unchanged(
    tmp_path: Path,
) -> None:
    contract_path, lock_path, document, composition, lock_payload = _local_controls(
        tmp_path
    )
    authorizer = load_authorizer(contract_path, lock_path, validation_as_of=AS_OF)

    assert SPI_VERSION == "1.2"
    assert type(authorizer) is Authorizer
    assert str(inspect.signature(load_authorizer)) == (
        "(contract_path: 'str | Path', lock_path: 'str | Path', *, "
        "validation_as_of: 'str') -> 'Authorizer'"
    )
    assert type(authorizer.state) is AuthorizerState
    assert authorizer.state is authorizer.state

    state = authorizer.state
    assert state._document is authorizer._document
    assert state._composition is authorizer._composition
    assert state._lock_payload is authorizer._lock_payload
    assert state.document == document
    assert state.composition.to_effective_dict() == composition.to_effective_dict()
    assert state.lock_payload == lock_payload
    assert build_agentic_network_lock(state.document, state.composition) == lock_payload
    assert verify_agentic_network_lock(
        state.lock_payload,
        state.document,
        state.composition,
    ) == ()


def test_state_access_does_not_read_network_or_files_and_survives_source_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract_path, lock_path, document, composition, lock_payload = _local_controls(
        tmp_path
    )
    calls = {"contract": 0, "composition": 0, "lock": 0, "verification": 0}
    real_load_nyx = authz_module.load_nyx
    real_compose = authz_module.compose_document_governance
    real_load_lock = authz_module.load_agentic_network_lock
    real_verify = authz_module.verify_agentic_network_lock

    def counted_contract(path: str | Path) -> Any:
        calls["contract"] += 1
        return real_load_nyx(path)

    def counted_lock(path: str | Path) -> Any:
        calls["lock"] += 1
        return real_load_lock(path)

    def counted_composition(*args: Any, **kwargs: Any) -> Any:
        calls["composition"] += 1
        return real_compose(*args, **kwargs)

    def counted_verification(*args: Any, **kwargs: Any) -> Any:
        calls["verification"] += 1
        return real_verify(*args, **kwargs)

    def no_network(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("load_authorizer must not access the network")

    monkeypatch.setattr(authz_module, "load_nyx", counted_contract)
    monkeypatch.setattr(authz_module, "compose_document_governance", counted_composition)
    monkeypatch.setattr(authz_module, "load_agentic_network_lock", counted_lock)
    monkeypatch.setattr(authz_module, "verify_agentic_network_lock", counted_verification)
    monkeypatch.setattr(socket, "socket", no_network)

    authorizer = load_authorizer(contract_path, lock_path, validation_as_of=AS_OF)
    expected_calls = {
        "contract": 1,
        "composition": 1,
        "lock": 1,
        "verification": 1,
    }
    assert calls == expected_calls
    before = (
        authorizer.state.document,
        authorizer.state.composition.to_effective_dict(),
        authorizer.state.lock_payload,
    )

    contract_path.write_text("changed after validated construction\n", encoding="utf-8")
    lock_path.unlink()
    after = (
        authorizer.state.document,
        authorizer.state.composition.to_effective_dict(),
        authorizer.state.lock_payload,
    )

    assert after == before
    assert after[0] == document
    assert after[1] == composition.to_effective_dict()
    assert after[2] == lock_payload
    assert calls == expected_calls


def test_original_objects_and_returned_views_are_fully_detached() -> None:
    document, composition, lock_payload = _controls()
    authorizer = Authorizer(document, composition, lock_payload)
    state = authorizer.state
    expected_document = state.document
    expected_composition = state.composition.to_effective_dict()
    expected_lock = state.lock_payload
    expected_decision = authorizer.evaluate(
        CapabilityRequest(
            "identity.researcher.local",
            "read_governed_context",
        ),
        context=EvaluationContext(
            decision_at=AS_OF,
            observed_subject_revision=authorizer.subject_revision,
        ),
    )

    document["agent_identities"][0]["status"] = "inactive"
    document["agentic_network"]["memberships"].clear()
    composition.policies[0]["deny"].append("caller-mutation")
    composition.profile.raw["graph"]["node_kinds"].append("caller-mutation")
    composition.approval_requirements[0].source_raw["caller-mutation"] = True
    lock_payload["records"]["memberships"].clear()

    document_view = state.document
    composition_view = state.composition
    lock_view = state.lock_payload
    document_view["agent_identities"][0]["status"] = "inactive"
    document_view["agentic_network"]["memberships"].clear()
    composition_view.policies[0]["deny"].append("consumer-mutation")
    composition_view.profile.raw["graph"]["node_kinds"].append(
        "consumer-mutation"
    )
    composition_view.approval_requirements[0].source_raw["consumer-mutation"] = (
        True
    )
    lock_view["records"]["memberships"].clear()

    assert state.document == expected_document
    assert state.composition.to_effective_dict() == expected_composition
    assert state.lock_payload == expected_lock
    with pytest.raises(AttributeError):
        state.contract_digest = "sha256:" + "0" * 64
    with pytest.raises(TypeError):
        state._document["agentic_network"]["id"] = "mutated"
    with pytest.raises(AttributeError):
        state._document["agentic_network"]["memberships"].append({})
    with pytest.raises(TypeError):
        state._composition.profile.raw["graph"]["node_kinds"] = []
    with pytest.raises(TypeError):
        state._lock_payload["records"]["memberships"][0]["digest"] = "mutated"

    actual_decision = authorizer.evaluate(
        CapabilityRequest(
            "identity.researcher.local",
            "read_governed_context",
        ),
        context=EvaluationContext(
            decision_at=AS_OF,
            observed_subject_revision=authorizer.subject_revision,
        ),
    )
    assert expected_decision.code is actual_decision.code is DecisionCode.ALLOWED


def test_state_digests_and_composition_hashes_match_authorizer_and_verified_lock() -> None:
    document, composition, lock_payload = _controls()
    authorizer = Authorizer(document, composition, lock_payload)
    state = authorizer.state

    assert contract_digest(state.document) == state.contract_digest
    assert state.contract_digest == authorizer.contract_digest
    assert state.lock_payload["source_contract_digest"] == authorizer.contract_digest
    assert agentic_network_lock_digest(state.lock_payload) == state.network_lock_digest
    assert state.network_lock_digest == authorizer.network_lock_digest
    assert state.composition.profile is not None
    assert (
        state.lock_payload["profile"]["content_hash"]
        == state.composition.profile.content_hash
    )
    assert {
        item["id"]: item["content_hash"]
        for item in state.lock_payload["modules"]
    } == {
        item.id: item.content_hash for item in state.composition.modules
    }


def test_public_state_supports_compatibility_and_evidence_without_private_access() -> None:
    document, composition, lock_payload = _controls()
    authorizer = Authorizer(document, composition, lock_payload)
    context = EvaluationContext(
        decision_at=AS_OF,
        observed_subject_revision=authorizer.subject_revision,
    )
    recorder = EvidenceRecorder(
        authorizer,
        context,
        producer_id="state-compatibility-test",
        producer_type="synthetic_harness",
    )
    decision = authorizer.evaluate(
        CapabilityRequest(
            "identity.researcher.local",
            "read_governed_context",
        ),
        context=context,
    )
    recorder.record_decision(decision, mission_id="M.state")

    report = _compatibility_validate(authorizer, recorder.stream())
    assert report["status"] == "pass", report["diagnostics"]
    source = inspect.getsource(_compatibility_validate)
    assert "._document" not in source
    assert "._composition" not in source
    assert "._lock_payload" not in source


# ------------------------------------------- retained state vs. constructor parameters
def test_mutating_a_caller_owned_approval_binding_cannot_change_a_decision() -> None:
    """Every index must be built from the frozen state, never from a parameter."""

    document, composition, lock_payload, caller_binding = _mutable_binding_controls()
    authorizer = Authorizer(document, composition, lock_payload)
    context = EvaluationContext(
        decision_at=AS_OF,
        observed_subject_revision=authorizer.subject_revision,
    )
    request = ApprovalRequest(ACTOR, _granted_approval(authorizer.subject_revision))
    before = authorizer.evaluate(request, context=context)
    assert before.effect is DecisionEffect.ALLOW
    assert before.code is DecisionCode.ALLOWED
    composition_before = authorizer.state.composition.to_effective_dict()

    # The caller still owns everything it passed in. Declaring a required
    # revision that the assertion cannot match is precisely the divergence an
    # index built from the constructor parameter allowed: it turns this ALLOW
    # into APPROVAL_REVISION_MISMATCH without the Authorizer ever being reloaded.
    caller_binding["revision"] = "git:" + "9" * 40
    _requirement(composition, APPROVAL_REF).source_raw["caller-mutation"] = True

    after = authorizer.evaluate(request, context=context)
    assert after.effect is before.effect is DecisionEffect.ALLOW
    assert after.code is before.code is DecisionCode.ALLOWED
    assert after.reason == before.reason
    assert after.basis == before.basis
    assert after.event_intents == before.event_intents

    retained = _requirement(authorizer.state.composition, APPROVAL_REF)
    assert retained.revision_binding == {}
    assert "caller-mutation" not in retained.source_raw
    assert authorizer._approvals[APPROVAL_REF].revision_binding == {}
    assert authorizer.state.composition.to_effective_dict() == composition_before

    # The same mutation applied to a freshly constructed Authorizer *does* change
    # the decision, which proves the assertion above is a real guard and not a
    # contract the example simply never exercises.
    diverged = Authorizer(document, composition, lock_payload)
    assert diverged.evaluate(request, context=context).code is (
        DecisionCode.APPROVAL_REVISION_MISMATCH
    )


def test_no_retained_state_or_index_shares_an_object_with_the_constructor_inputs() -> None:
    """Closes the general case behind the approval-index divergence."""

    document, composition, lock_payload, _binding = _mutable_binding_controls()
    caller_owned = (
        _mutable_object_ids(document)
        | _mutable_object_ids(composition)
        | _mutable_object_ids(lock_payload)
    )
    authorizer = Authorizer(document, composition, lock_payload)

    retained: set[int] = set()
    for name in vars(authorizer):
        _reachable_object_ids(getattr(authorizer, name), retained)
    for name in ("_document", "_composition", "_lock_payload"):
        _reachable_object_ids(getattr(authorizer.state, name), retained)

    assert caller_owned
    assert retained
    assert caller_owned.isdisjoint(retained)


def test_the_constructor_drops_its_parameters_before_building_any_index() -> None:
    """The parameters are unreachable after the snapshot, so divergence cannot recur."""

    parameters = {"document", "composition", "lock_payload"}
    body = ast.parse(
        textwrap.dedent(inspect.getsource(Authorizer.__init__))
    ).body[0].body
    dropped = [
        position
        for position, node in enumerate(body)
        if isinstance(node, ast.Delete)
        and {
            target.id for target in node.targets if isinstance(target, ast.Name)
        } == parameters
    ]
    assert len(dropped) == 1, "Authorizer.__init__ must drop its parameters exactly once"

    def named(statements: list[ast.stmt]) -> set[str]:
        return {
            node.id
            for statement in statements
            for node in ast.walk(statement)
            if isinstance(node, ast.Name) and node.id in parameters
        }

    before, after = body[: dropped[0]], body[dropped[0] + 1 :]
    assert after, "the indexes must be built after the parameters are dropped"
    # Consumed exactly once, to build the frozen snapshot, and never read again.
    assert named(before) == parameters
    assert named(after) == set()

    indexes = ast.Module(body=after, type_ignores=[])
    reads = [
        ast.unparse(node)
        for node in ast.walk(indexes)
        if isinstance(node, ast.Attribute) and node.attr == "approval_requirements"
    ]
    assert reads == ["self._composition.approval_requirements"]


# ------------------------------------------------------- retained CompositionResult
def test_retained_composition_serializers_match_the_unfrozen_composition() -> None:
    document, composition, lock_payload = _controls()
    authorizer = Authorizer(document, composition, lock_payload)
    frozen = authorizer._composition
    detached = authorizer.state.composition

    assert isinstance(frozen, CompositionResult)
    assert isinstance(detached, CompositionResult)
    for model in (frozen, detached):
        assert model.to_dict() == composition.to_dict()
        assert model.to_effective_dict() == composition.to_effective_dict()
        assert model.profile is not None
        assert model.profile.as_dict() == composition.profile.as_dict()
        assert [item.as_dict() for item in model.modules] == [
            item.as_dict() for item in composition.modules
        ]
        assert [
            item.to_legacy_dict() for item in model.approval_requirements
        ] == [item.to_legacy_dict() for item in composition.approval_requirements]
        assert [
            item.to_verifiable_dict() for item in model.approval_requirements
        ] == [item.to_verifiable_dict() for item in composition.approval_requirements]
        assert [
            item.effective_approval.to_dict()
            for item in model.approval_requirements
            if item.effective_approval is not None
        ] == [
            item.effective_approval.to_dict()
            for item in composition.approval_requirements
            if item.effective_approval is not None
        ]
    # The detached view is an equal, independent model, not the retained one.
    assert detached == composition
    assert detached is not frozen
    assert authorizer.state.composition is not detached


def test_retained_composition_serializer_output_is_plain_and_json_encodable() -> None:
    document, composition, lock_payload = _controls()
    authorizer = Authorizer(document, composition, lock_payload)
    frozen = authorizer._composition
    payloads = [
        frozen.to_dict(),
        frozen.to_effective_dict(),
        frozen.profile.as_dict(),
        *(item.to_legacy_dict() for item in frozen.approval_requirements),
        *(item.to_verifiable_dict() for item in frozen.approval_requirements),
        *(item.as_dict() for item in frozen.modules),
    ]
    for payload in payloads:
        offenders = [
            path
            for path, kind in _container_kinds(payload)
            if kind not in {"dict", "list"}
        ]
        assert offenders == []
        assert json.loads(json.dumps(payload, sort_keys=True)) == payload


def test_serializer_output_is_detached_and_mutating_it_cannot_reach_the_authorizer() -> None:
    document, composition, lock_payload = _controls()
    authorizer = Authorizer(document, composition, lock_payload)
    frozen = authorizer._composition
    context = EvaluationContext(
        decision_at=AS_OF,
        observed_subject_revision=authorizer.subject_revision,
    )
    request = ApprovalRequest(ACTOR, _granted_approval(authorizer.subject_revision))
    expected_decision = authorizer.evaluate(request, context=context)
    expected_dict = frozen.to_dict()
    expected_effective = frozen.to_effective_dict()
    expected_profile = frozen.profile.as_dict()
    expected_legacy = frozen.approval_requirements[0].to_legacy_dict()

    payload = frozen.to_dict()
    payload["policies"][0]["deny"].append("serializer-mutation")
    payload["approval_requirements"][0]["eligible_roles"].append("serializer-mutation")
    effective = frozen.to_effective_dict()
    effective["provenance"][0]["serializer-mutation"] = True
    profile_raw = frozen.profile.as_dict()
    profile_raw["graph"]["node_kinds"].append("serializer-mutation")
    legacy = frozen.approval_requirements[0].to_legacy_dict()
    legacy["required_evidence"].append("serializer-mutation")
    detached_view = authorizer.state.composition
    detached_view.policies[0]["deny"].append("view-mutation")

    assert frozen.to_dict() == expected_dict
    assert frozen.to_effective_dict() == expected_effective
    assert frozen.profile.as_dict() == expected_profile
    assert frozen.approval_requirements[0].to_legacy_dict() == expected_legacy
    assert authorizer.state.composition.to_dict() == expected_dict
    actual_decision = authorizer.evaluate(request, context=context)
    assert actual_decision.code is expected_decision.code is DecisionCode.ALLOWED
    assert actual_decision.basis == expected_decision.basis

    # The retained snapshot itself stays structurally read-only.
    with pytest.raises(TypeError):
        frozen.profile.raw["graph"]["node_kinds"] = []
    with pytest.raises(AttributeError):
        frozen.profile.raw["graph"]["node_kinds"].append("snapshot-mutation")


def test_frozen_and_detached_compositions_are_both_validator_compatible(
    tmp_path: Path,
) -> None:
    contract_path, lock_path, _document, composition, lock_payload = _local_controls(
        tmp_path
    )
    authorizer = load_authorizer(contract_path, lock_path, validation_as_of=AS_OF)
    state = authorizer.state
    context = EvaluationContext(
        decision_at=AS_OF,
        observed_subject_revision=authorizer.subject_revision,
    )
    recorder = EvidenceRecorder(
        authorizer,
        context,
        producer_id="state-serializer-test",
        producer_type="synthetic_harness",
    )
    recorder.record_decision(
        authorizer.evaluate(
            CapabilityRequest(ACTOR, "read_governed_context"), context=context
        ),
        mission_id="M.serializers",
    )
    stream = recorder.stream()

    # The frozen retained model is what EvidenceRecorder.resume() hands to the
    # validator; the detached view is what public consumers get.
    for model in (authorizer._composition, state.composition, composition):
        assert verify_agentic_network_lock(state.lock_payload, state.document, model) == ()
        assert build_agentic_network_lock(state.document, model) == lock_payload
        report = validate_runtime_events(
            state.document, model, state.lock_payload, stream
        )
        assert report["status"] == "pass", report["diagnostics"]

    resumed = EvidenceRecorder.resume(
        authorizer,
        context,
        stream,
        producer_id="state-serializer-test",
        producer_type="synthetic_harness",
    )
    assert resumed.stream()["events"] == stream["events"]


# --------------------------------------------- bounded dataclass reconstruction
def test_every_retained_composition_dataclass_shape_is_keyword_constructible() -> None:
    _document, composition, _lock_payload = _controls()
    reachable = _reachable_dataclasses(composition)

    assert reachable
    assert reachable <= set(COMPOSITION_DATACLASSES)
    assert {CompositionResult, NormalizedApproval, ProfilePack} <= reachable
    for cls in COMPOSITION_DATACLASSES:
        spec = fields(cls)
        assert spec, cls.__name__
        assert [item.name for item in spec if not item.init] == [], cls.__name__
        assert not hasattr(cls, "__post_init__"), cls.__name__


def test_freeze_and_detach_round_trip_every_reachable_composition_dataclass() -> None:
    _document, composition, _lock_payload = _controls()
    frozen = authz_module._deep_freeze(composition)
    detached = authz_module._detach_composition(frozen)

    assert _reachable_dataclasses(frozen) == _reachable_dataclasses(composition)
    assert _reachable_dataclasses(detached) == _reachable_dataclasses(composition)
    assert detached == composition
    assert detached is not composition
    assert authz_module._deep_freeze(frozen).to_effective_dict() == (
        composition.to_effective_dict()
    )


def test_unsupported_dataclass_shapes_fail_deliberately() -> None:
    @dataclass(frozen=True)
    class NonConstructorField:
        kept: str
        derived: str = field(init=False, default="derived")

    @dataclass(frozen=True)
    class RejectsItsOwnFields:
        value: Any

        def __post_init__(self) -> None:
            if type(self.value) is not list:
                raise ValueError("value must be an exact list")

    for helper in (authz_module._deep_freeze, authz_module._detach_composition):
        with pytest.raises(TypeError, match="NonConstructorField"):
            helper(NonConstructorField("kept"))
    with pytest.raises(TypeError, match="RejectsItsOwnFields"):
        authz_module._deep_freeze(RejectsItsOwnFields([1, 2]))


def test_detachment_restores_container_kinds_and_preserves_frozenset() -> None:
    source = {
        "mapping": {"nested": {"leaf": 1}},
        "list": [1, [2, 3]],
        "tuple": (1, (2, 3)),
        "frozen": frozenset({"a", "b"}),
        "set": {"c"},
    }
    frozen = authz_module._deep_freeze(source)
    detached = authz_module._detach_composition(frozen)

    assert type(detached["mapping"]) is dict
    assert type(detached["mapping"]["nested"]) is dict
    assert type(detached["list"]) is list
    assert type(detached["list"][1]) is list
    assert type(detached["tuple"]) is tuple
    assert type(detached["tuple"][1]) is tuple
    # A frozenset stays a frozenset instead of degrading to a mutable set.
    assert type(detached["frozen"]) is frozenset
    assert detached["frozen"] == frozenset({"a", "b"})
    # Freezing a set is one-way (documented as sets->frozensets), so detachment
    # cannot invent set-ness back; it must not invent it for a frozenset either.
    assert type(detached["set"]) is frozenset

    # deepcopy of the frozen snapshot restores the same ordinary containers,
    # which is what every governance serializer relies on.
    copied = deepcopy(frozen)
    assert type(copied) is dict
    assert type(copied["mapping"]) is dict
    assert type(copied["list"]) is list
    assert type(copied["list"][1]) is list
    assert copied["list"] == [1, [2, 3]]
    assert copied["mapping"] == {"nested": {"leaf": 1}}
    with pytest.raises(TypeError):
        frozen["mapping"] = {}
    with pytest.raises(AttributeError):
        frozen["list"].append(4)


def test_invalid_and_stale_lock_diagnostics_are_unchanged(tmp_path: Path) -> None:
    contract_path, _lock_path, _document, _composition, lock_payload = (
        _local_controls(tmp_path)
    )
    invalid_path = tmp_path / "invalid.lock"
    invalid_path.write_text("{ not valid json", encoding="utf-8")
    with pytest.raises(AuthorizerLoadError) as invalid:
        load_authorizer(contract_path, invalid_path, validation_as_of=AS_OF)
    assert invalid.value.code is AuthorizerLoadCode.LOCK_INVALID
    assert str(invalid.value) == (
        "LOCK_INVALID: Cannot load the agentic-network lock: "
        "AgenticArtifactError"
    )

    stale_payload = deepcopy(lock_payload)
    stale_payload["source_contract_digest"] = "sha256:" + "0" * 64
    stale_path = tmp_path / "stale.lock"
    write_agentic_network_lock(stale_payload, stale_path)
    with pytest.raises(AuthorizerLoadError) as stale:
        load_authorizer(contract_path, stale_path, validation_as_of=AS_OF)
    assert stale.value.code is AuthorizerLoadCode.LOCK_STALE
    assert str(stale.value) == (
        "LOCK_STALE: Stale or mismatched agentic-network lock: "
        "AN_LOCK_SOURCE_STALE"
    )
