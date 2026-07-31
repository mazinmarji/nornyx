"""Focused assurance for the additive Authorizer construction-state SPI."""

from __future__ import annotations

from copy import deepcopy
import inspect
from pathlib import Path
import shutil
import socket
from typing import Any

import pytest

import nornyx.agentic.authz as authz_module
from nornyx.agentic import (
    Authorizer,
    AuthorizerLoadCode,
    AuthorizerLoadError,
    AuthorizerState,
    CapabilityRequest,
    DecisionCode,
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


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "agentic_network.nyx"
EVIDENCE = ROOT / "examples" / "governance_evidence"
AS_OF = "2026-07-17T10:00:00Z"


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
