"""Composed profile graph vocabulary reaches every supported validation consumer.

Issue #104, review finding B3: ``nornyx check`` composed the profile and checked
the graph against it, but ``load_authorizer`` and other consumers still called
``check_document(document)`` bare, so a project-supplied profile's declared
relation pairs never applied there. These tests go through the real public
paths (``nornyx.agentic.load_authorizer``, ``nornyx check``) with a custom
profile discovered from ``<contract dir>/.nornyx/profiles/``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from nornyx.agentic import AuthorizerLoadError, load_authorizer
from nornyx.agentic.authz import AuthorizerLoadCode
from nornyx.agentic_artifacts import build_agentic_network_lock, write_agentic_network_lock
from nornyx.checker import check_document, has_errors
from nornyx.cli import main
from nornyx.governance import (
    GovernanceRegistry,
    check_document_with_governance,
    compose_document_governance,
    registry_for_contract,
)
from nornyx.governance.errors import error
from nornyx.governance.schemas import canonical_pack_hash
from nornyx.parser import load_nyx

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "agentic_network.nyx"
EVIDENCE = ROOT / "examples" / "governance_evidence"
AS_OF = "2026-07-17T10:00:00Z"
PROFILE_ID = "org.test.agentic_graph"
PROFILE_NAME = "agentic_graph_custom"

WIDENED_CORE_EDGE = {"from": "goal.network", "to": "agent.researcher", "relation": "governs"}
PROFILE_ONLY_EDGE = {"from": "component.gateway", "to": "interface.rest", "relation": "exposes"}
MISMATCHED_EDGE = {"from": "interface.rest", "to": "component.gateway", "relation": "exposes"}


def _custom_profile_payload(**overrides) -> dict:
    """The built-in agentic_network profile re-identified as a project pack that
    declares two graph kinds, one profile-only relation, and one widening of a
    core relation between two core kinds."""
    payload = GovernanceRegistry.builtins().resolve_profile("agentic_network").as_dict()
    payload["id"] = PROFILE_ID
    payload["name"] = PROFILE_NAME
    payload["display_name"] = "Agentic Graph (custom)"
    payload["graph"] = {
        "node_kinds": ["component", "interface"],
        "relationship_constraints": [
            {"from_kind": "component", "relation": "exposes", "to_kind": "interface"},
            {"from_kind": "goal", "relation": "governs", "to_kind": "agent"},
        ],
    }
    payload["provenance"]["source_tier"] = "project"
    payload.update(overrides)
    payload["integrity"]["content_hash"] = canonical_pack_hash(payload)
    return payload


def _project(
    tmp_path: Path, *edges: dict, profile: str = PROFILE_NAME, pack: dict | None = None
) -> tuple[Path, dict]:
    shutil.copytree(EVIDENCE, tmp_path / "governance_evidence")
    profiles = tmp_path / ".nornyx" / "profiles"
    profiles.mkdir(parents=True)
    (profiles / f"{PROFILE_NAME}.yaml").write_text(
        yaml.safe_dump(pack or _custom_profile_payload(), sort_keys=False), encoding="utf-8"
    )
    document = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    document["project"]["profile"] = profile
    document["graph"] = {
        "nodes": [
            {"id": "goal.network", "kind": "goal", "ref": "GOAL-001"},
            {"id": "agent.researcher", "kind": "agent", "ref": "Researcher"},
            {"id": "component.gateway", "kind": "component", "ref": "Gateway"},
            {"id": "interface.rest", "kind": "interface", "ref": "RestInterface"},
        ],
        "edges": list(edges),
    }
    contract = tmp_path / "project.nyx"
    contract.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return contract, load_nyx(contract)


def _load(tmp_path: Path, contract: Path, document: dict):
    composition = compose_document_governance(document, registry=registry_for_contract(contract))
    lock_path = tmp_path / "nornyx.agentic_network.lock"
    write_agentic_network_lock(build_agentic_network_lock(document, composition), lock_path)
    return load_authorizer(contract, lock_path, validation_as_of=AS_OF)


# -------------------------------------------------------------- load_authorizer


def test_b3_widened_core_relation_loads_only_under_the_custom_profile(tmp_path: Path) -> None:
    contract, document = _project(tmp_path, WIDENED_CORE_EDGE)
    authorizer = _load(tmp_path, contract, document)
    assert authorizer.contract_digest.startswith("sha256:")

    builtin_dir = tmp_path / "builtin"
    builtin_dir.mkdir()
    contract, document = _project(builtin_dir, WIDENED_CORE_EDGE, profile="agentic_network")
    with pytest.raises(AuthorizerLoadError) as caught:
        _load(builtin_dir, contract, document)
    assert caught.value.code is AuthorizerLoadCode.CONTRACT_INVALID
    assert "INVALID_GRAPH_RELATION_PAIR" in str(caught.value)


def test_b3_relation_declared_only_by_the_custom_profile_is_honored(tmp_path: Path) -> None:
    contract, document = _project(tmp_path, PROFILE_ONLY_EDGE)

    assert _load(tmp_path, contract, document).contract_digest.startswith("sha256:")


def test_b3_mismatched_custom_profile_relation_fails_closed(tmp_path: Path) -> None:
    contract, document = _project(tmp_path, MISMATCHED_EDGE)

    with pytest.raises(AuthorizerLoadError) as caught:
        _load(tmp_path, contract, document)
    assert caught.value.code is AuthorizerLoadCode.CONTRACT_INVALID
    assert "INVALID_GRAPH_RELATION_PAIR" in str(caught.value)


def test_b3_unknown_profile_never_yields_a_weaker_successful_load(tmp_path: Path) -> None:
    contract, document = _project(tmp_path, WIDENED_CORE_EDGE, profile="no_such_profile")
    lock_path = tmp_path / "nornyx.agentic_network.lock"
    lock_path.write_text("{}", encoding="utf-8")

    with pytest.raises(AuthorizerLoadError) as caught:
        load_authorizer(contract, lock_path, validation_as_of=AS_OF)
    assert caught.value.code is AuthorizerLoadCode.PROFILE_MISSING


def test_b3_tampered_custom_profile_fails_closed_instead_of_degrading(tmp_path: Path) -> None:
    pack = _custom_profile_payload()
    pack["integrity"]["content_hash"] = "sha256:" + "0" * 64
    contract, document = _project(tmp_path, WIDENED_CORE_EDGE, pack=pack)
    lock_path = tmp_path / "nornyx.agentic_network.lock"
    lock_path.write_text("{}", encoding="utf-8")

    with pytest.raises(AuthorizerLoadError) as caught:
        load_authorizer(contract, lock_path, validation_as_of=AS_OF)
    assert caught.value.code is AuthorizerLoadCode.CONTRACT_INVALID
    assert "Cannot load the contract" in str(caught.value)


def test_b3_custom_profile_with_an_unresolvable_module_fails_closed(tmp_path: Path) -> None:
    pack = _custom_profile_payload(required_modules=["org.test.missing_module"])
    contract, document = _project(tmp_path, PROFILE_ONLY_EDGE, pack=pack)
    lock_path = tmp_path / "nornyx.agentic_network.lock"
    lock_path.write_text("{}", encoding="utf-8")

    with pytest.raises(AuthorizerLoadError) as caught:
        load_authorizer(contract, lock_path, validation_as_of=AS_OF)
    assert caught.value.code is AuthorizerLoadCode.CONTRACT_INVALID


# ------------------------------------------------------------ CLI parity


def test_b3_nornyx_check_applies_the_same_composed_vocabulary(tmp_path: Path, capsys) -> None:
    contract, _ = _project(tmp_path, WIDENED_CORE_EDGE, PROFILE_ONLY_EDGE)
    assert main(["check", "--as-of", AS_OF, str(contract)]) == 0, capsys.readouterr().out
    out = capsys.readouterr().out
    assert "GRAPH_VOCABULARY_PROFILE_UNRESOLVED" not in out
    assert "UNKNOWN_GRAPH_NODE_KIND" not in out

    rejected = tmp_path / "rejected"
    rejected.mkdir()
    contract, _ = _project(rejected, MISMATCHED_EDGE)
    assert main(["check", "--as-of", AS_OF, str(contract)]) == 1
    assert "INVALID_GRAPH_RELATION_PAIR" in capsys.readouterr().out


# ------------------------------------------ the shared helper and the fallback


def test_b3_bare_checker_reports_that_a_custom_profile_was_not_applied(tmp_path: Path) -> None:
    contract, document = _project(tmp_path, WIDENED_CORE_EDGE)

    bare = check_document(document)
    assert "GRAPH_VOCABULARY_PROFILE_UNRESOLVED" in [d.code for d in bare]
    assert "INVALID_GRAPH_RELATION_PAIR" in [d.code for d in bare], (
        "core-only checking rejects the widened pair, and says why it is core-only"
    )

    composed, composition = check_document_with_governance(
        document, registry=registry_for_contract(contract)
    )
    assert composition is not None and composition.profile.id == PROFILE_ID
    assert "GRAPH_VOCABULARY_PROFILE_UNRESOLVED" not in [d.code for d in composed]
    assert "INVALID_GRAPH_RELATION_PAIR" not in [d.code for d in composed]
    assert not has_errors(composed), [d.to_dict() for d in composed]


def _builtin_profile_doc() -> dict:
    return {
        "nornyx": "0.2",
        "project": {"name": "Example", "profile": "telecom_ops"},
        "agents": [{"name": "Builder"}],
        "graph": {
            "nodes": [{"id": "agent.builder", "kind": "agent", "ref": "Builder"}],
            "edges": [],
        },
    }


def test_b3_registry_failure_is_an_error_not_silent_core_checking(monkeypatch) -> None:
    import nornyx.profiles

    def broken_registry():
        raise RuntimeError("profile registry unavailable")

    monkeypatch.setattr(nornyx.profiles, "builtin_profile_registry", broken_registry)
    diagnostics = check_document(_builtin_profile_doc())

    unavailable = [d for d in diagnostics if d.code == "GRAPH_VOCABULARY_UNAVAILABLE"]
    assert len(unavailable) == 1 and unavailable[0].level == "error"
    assert "RuntimeError" in unavailable[0].message
    assert has_errors(diagnostics)


def test_b3_unexpected_profile_resolution_failure_is_an_error(monkeypatch) -> None:
    def broken_resolve(self, identity):
        raise error("PACK_INTEGRITY_MISMATCH", "simulated corrupt pack", source_id=identity)

    monkeypatch.setattr(GovernanceRegistry, "resolve_profile", broken_resolve)
    diagnostics = check_document(_builtin_profile_doc())

    assert [d.code for d in diagnostics if d.level == "error"] == ["GRAPH_VOCABULARY_UNAVAILABLE"]
    assert "PACK_INTEGRITY_MISMATCH" in next(
        d.message for d in diagnostics if d.code == "GRAPH_VOCABULARY_UNAVAILABLE"
    )


def test_b3_only_pack_not_found_is_treated_as_an_unresolved_profile(monkeypatch) -> None:
    diagnostics = check_document(
        {**_builtin_profile_doc(), "project": {"name": "Example", "profile": "ghost"}}
    )

    assert [d.code for d in diagnostics if d.level == "warning"] == [
        "GRAPH_VOCABULARY_PROFILE_UNRESOLVED"
    ]
    assert not has_errors(diagnostics)


# ---------------------------------------------- agentic-network CLI path


def test_b3_agentic_network_generate_applies_the_composed_vocabulary(
    tmp_path: Path, capsys
) -> None:
    contract, _ = _project(tmp_path, WIDENED_CORE_EDGE, PROFILE_ONLY_EDGE)
    code = main(
        [
            "agentic-network",
            "generate",
            str(contract),
            "--out",
            str(tmp_path / "out"),
            "--as-of",
            AS_OF,
        ]
    )
    out = capsys.readouterr().out
    assert code == 0, out
    assert "INVALID_GRAPH_RELATION_PAIR" not in out

    rejected = tmp_path / "rejected"
    rejected.mkdir()
    contract, _ = _project(rejected, MISMATCHED_EDGE)
    code = main(
        [
            "agentic-network",
            "generate",
            str(contract),
            "--out",
            str(rejected / "out"),
            "--as-of",
            AS_OF,
        ]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "INVALID_GRAPH_RELATION_PAIR" in out
