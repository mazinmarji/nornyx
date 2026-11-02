"""Graph-vocabulary checks keep every contract Nornyx 1.11.0 accepted loadable.

Issue #104 (ADR-0046) made the checker read profile relation constraints and
resolve ``profile``, ``project`` and ``contract`` node refs. Two of its
conditions were reported with the existing *error* codes, so contracts that
1.11.0 checked, locked and loaded stopped loading:

* a relation that the active profile declares but the core vocabulary does not,
  used with a pair the profile does not declare. 1.11.0 reported it as
  ``UNKNOWN_GRAPH_RELATION`` (warning), as docs/42 promised for custom
  relations;
* a ``profile``, ``project`` or ``contract`` node ``ref`` that does not resolve
  in the document. 1.11.0 treated those refs as free text.

Both are now warnings with their own codes, so the existing error codes keep
their 1.11.0 meaning: a core relation used with a wrong pair, and an unresolved
ref of the fourteen kinds 1.11.0 already resolved, are still errors.
``nornyx check --strict`` fails on the warnings, as on every warning.
"""

from __future__ import annotations

import json
import shutil
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import pytest
import yaml

from nornyx.agentic import (
    CapabilityRequest,
    EvaluationContext,
    EvidenceRecorder,
    load_authorizer,
)
from nornyx.agentic_artifacts import build_agentic_network_lock, write_agentic_network_lock
from nornyx.checker import GRAPH_RELATION_RULES, check_document, has_errors
from nornyx.cli import main
from nornyx.governance import GovernanceRegistry, compose_document_governance, registry_for_contract
from nornyx.governance.schemas import canonical_pack_hash
from nornyx.parser import load_nyx
from nornyx.repo_drift import check_repo_drift

ROOT = Path(__file__).resolve().parents[1]
AGENTIC_EXAMPLE = ROOT / "examples" / "agentic_network.nyx"
EVIDENCE = ROOT / "examples" / "governance_evidence"
AS_OF = "2026-07-17T10:00:00Z"
PAIR_WARNING = "UNDECLARED_GRAPH_RELATION_PAIR"
REF_WARNING = "UNRESOLVED_GRAPH_NODE_REF"
ADVISORY_REF_KINDS = ("profile", "project", "contract")
ENFORCED_REF_KINDS = (
    "intent", "context", "skill", "policy", "agent", "harness", "trace",
    "eval", "approval", "budget", "adapter", "connector", "goal", "evidence",
)


def _codes(diagnostics) -> set[tuple[str, str]]:
    return {(d.level, d.code) for d in diagnostics}


def _architecture_doc(*edges: dict, nodes: list[dict] | None = None) -> dict:
    """A small document under the built-in ``architecture_governance`` profile.

    That profile declares ``component exposes interface`` (a relation the core
    vocabulary does not have) and widens core ``governs`` with
    ``policy governs component``.
    """

    return {
        "nornyx": "0.2",
        "project": {"name": "Example", "profile": "architecture_governance"},
        "agents": [{"name": "Builder"}],
        "policies": [{"name": "SafePolicy"}],
        "goals": [],
        "graph": {
            "nodes": nodes
            or [
                {"id": "component.api", "kind": "component", "ref": "ApiService"},
                {"id": "interface.rest", "kind": "interface", "ref": "RestInterface"},
                {"id": "policy.safe", "kind": "policy", "ref": "SafePolicy"},
                {"id": "agent.builder", "kind": "agent", "ref": "Builder"},
            ],
            "edges": list(edges),
        },
    }


# ------------------------------------------------- profile-declared relations


def test_exposes_is_a_profile_relation_not_a_core_one() -> None:
    assert "exposes" not in GRAPH_RELATION_RULES
    assert "governs" in GRAPH_RELATION_RULES


@pytest.mark.parametrize(
    ("edge_from", "edge_to"),
    [
        ("interface.rest", "component.api"),  # declared pair reversed
        ("component.api", "agent.builder"),  # declared source, undeclared target
        ("policy.safe", "agent.builder"),  # both core kinds
    ],
)
def test_profile_relation_with_an_undeclared_pair_warns(edge_from: str, edge_to: str) -> None:
    diagnostics = check_document(
        _architecture_doc({"from": edge_from, "to": edge_to, "relation": "exposes"})
    )
    pair = [d for d in diagnostics if d.code == PAIR_WARNING]

    assert len(pair) == 1 and pair[0].level == "warning"
    assert pair[0].path == "graph.edges[0].relation"
    assert "INVALID_GRAPH_RELATION_PAIR" not in {d.code for d in diagnostics}
    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics]


def test_profile_relation_with_its_declared_pair_is_silent() -> None:
    diagnostics = check_document(
        _architecture_doc({"from": "component.api", "to": "interface.rest", "relation": "exposes"})
    )
    assert {d.code for d in diagnostics}.isdisjoint(
        {PAIR_WARNING, "INVALID_GRAPH_RELATION_PAIR", "UNKNOWN_GRAPH_RELATION"}
    )


@pytest.mark.parametrize(
    ("edge_from", "edge_to"),
    [
        ("component.api", "agent.builder"),  # profile source x core target
        ("policy.safe", "interface.rest"),  # core source x undeclared profile target
        ("agent.builder", "policy.safe"),  # core kinds, wrong pair
    ],
)
def test_core_relation_with_a_wrong_pair_is_still_an_error(edge_from: str, edge_to: str) -> None:
    diagnostics = check_document(
        _architecture_doc({"from": edge_from, "to": edge_to, "relation": "governs"})
    )
    assert ("error", "INVALID_GRAPH_RELATION_PAIR") in _codes(diagnostics)
    assert PAIR_WARNING not in {d.code for d in diagnostics}
    assert has_errors(diagnostics)


def test_relation_no_profile_declares_keeps_its_1_11_warning() -> None:
    diagnostics = check_document(
        _architecture_doc({"from": "policy.safe", "to": "agent.builder", "relation": "relates_to"})
    )
    assert ("warning", "UNKNOWN_GRAPH_RELATION") in _codes(diagnostics)
    assert not has_errors(diagnostics)


# ------------------------------------------------------------- node references


def _ref_doc(kind: str, ref: str) -> dict:
    return {
        "nornyx": "0.2",
        "project": {"name": "Example", "profile": "minimal"},
        "contracts": [{"name": "BuildContract", "nodes": []}],
        "graph": {"nodes": [{"id": f"{kind}.node", "kind": kind, "ref": ref}], "edges": []},
    }


@pytest.mark.parametrize("kind", ADVISORY_REF_KINDS)
def test_unresolved_profile_project_or_contract_ref_warns(kind: str) -> None:
    diagnostics = check_document(_ref_doc(kind, "NoSuchTarget"))
    refs = [d for d in diagnostics if d.code == REF_WARNING]

    assert len(refs) == 1 and refs[0].level == "warning"
    assert refs[0].path == "graph.nodes[0].ref"
    assert "UNKNOWN_GRAPH_REF_REFERENCE" not in {d.code for d in diagnostics}
    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics]


@pytest.mark.parametrize(
    ("kind", "ref"),
    [("profile", "minimal"), ("project", "Example"), ("contract", "BuildContract")],
)
def test_resolved_profile_project_or_contract_ref_is_silent(kind: str, ref: str) -> None:
    codes = {d.code for d in check_document(_ref_doc(kind, ref))}
    assert REF_WARNING not in codes and "UNKNOWN_GRAPH_REF_REFERENCE" not in codes


@pytest.mark.parametrize("kind", ENFORCED_REF_KINDS)
def test_unresolved_ref_of_a_kind_1_11_resolved_is_still_an_error(kind: str) -> None:
    diagnostics = check_document(_ref_doc(kind, "NoSuchTarget"))
    assert ("error", "UNKNOWN_GRAPH_REF_REFERENCE") in _codes(diagnostics)
    assert REF_WARNING not in {d.code for d in diagnostics}


# ------------------------------------------------------------ CLI and strict


def _cli(args: list[str]) -> tuple[int, str]:
    out = StringIO()
    with redirect_stdout(out):
        code = main(args)
    return code, out.getvalue()


def _custom_pack() -> dict:
    """The built-in agentic_network profile, re-identified as a project pack that
    declares ``component exposes interface`` and the two kinds it needs."""

    payload = GovernanceRegistry.builtins().resolve_profile("agentic_network").as_dict()
    payload["id"] = "org.test.graph_compat"
    payload["name"] = "graph_compat_custom"
    payload["display_name"] = "Graph compatibility (custom)"
    payload["graph"] = {
        "node_kinds": ["component", "interface"],
        "relationship_constraints": [
            {"from_kind": "component", "relation": "exposes", "to_kind": "interface"}
        ],
    }
    payload["provenance"]["source_tier"] = "project"
    payload["integrity"]["content_hash"] = canonical_pack_hash(payload)
    return payload


def _agentic_project(tmp_path: Path, case: str) -> Path:
    """An agentic-network contract that 1.11.0 checked, locked and loaded.

    ``ref``: one ``contract`` node whose ref resolves to nothing.
    ``pair``: a project pack declaring ``component exposes interface`` and an
    edge using the reversed pair.
    """

    shutil.copytree(EVIDENCE, tmp_path / "governance_evidence")
    document = yaml.safe_load(AGENTIC_EXAMPLE.read_text(encoding="utf-8"))
    if case == "ref":
        document["graph"] = {
            "nodes": [{"id": "contract.node", "kind": "contract", "ref": "NoSuchContract"}],
            "edges": [],
        }
    else:
        profiles = tmp_path / ".nornyx" / "profiles"
        profiles.mkdir(parents=True)
        (profiles / "graph_compat_custom.yaml").write_text(
            yaml.safe_dump(_custom_pack(), sort_keys=False), encoding="utf-8"
        )
        document["project"]["profile"] = "graph_compat_custom"
        document["graph"] = {
            "nodes": [
                {"id": "component.gateway", "kind": "component", "ref": "Gateway"},
                {"id": "interface.rest", "kind": "interface", "ref": "RestInterface"},
            ],
            "edges": [{"from": "interface.rest", "to": "component.gateway", "relation": "exposes"}],
        }
    contract = tmp_path / "project.nyx"
    contract.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return contract


CASES = [("ref", REF_WARNING), ("pair", PAIR_WARNING)]


@pytest.mark.parametrize(("case", "warning"), CASES)
def test_nornyx_check_passes_and_strict_promotes_the_warning(tmp_path: Path, case: str, warning: str) -> None:
    contract = _agentic_project(tmp_path, case)

    code, out = _cli(["check", "--as-of", AS_OF, str(contract)])
    assert code == 0, out

    code, out = _cli(["check", "--as-of", AS_OF, "--strict", str(contract)])
    assert code == 1
    assert warning in out and "STRICT_WARNINGS_PRESENT" in out


@pytest.mark.parametrize(("case", "warning"), CASES)
def test_agentic_network_commands_and_load_authorizer_accept_the_contract(
    tmp_path: Path, case: str, warning: str
) -> None:
    contract = _agentic_project(tmp_path, case)
    artifacts = tmp_path / "artifacts"
    lock = tmp_path / "nornyx.agentic_network.lock"

    code, out = _cli(["agentic-network", "generate", str(contract), "--out", str(artifacts), "--as-of", AS_OF])
    assert code == 0, out
    code, out = _cli([
        "agentic-network", "lock", str(contract), "--artifacts", str(artifacts),
        "--out", str(lock), "--as-of", AS_OF,
    ])
    assert code == 0, out
    code, out = _cli([
        "agentic-network", "lock-check", str(contract), "--lock", str(lock),
        "--artifacts", str(artifacts), "--as-of", AS_OF,
    ])
    assert code == 0, out

    authorizer = load_authorizer(contract, lock, validation_as_of=AS_OF)
    context = EvaluationContext(AS_OF, authorizer.subject_revision)
    recorder = EvidenceRecorder(authorizer, context, producer_id="producer-tests", producer_type="synthetic_harness")
    decision = authorizer.evaluate(
        CapabilityRequest("identity.researcher.local", "read_governed_context"), context=context
    )
    recorder.record_decision(decision, mission_id="GOAL-001")
    events = tmp_path / "events.json"
    events.write_text(json.dumps(recorder.stream()), encoding="utf-8")

    code, out = _cli([
        "agentic-network", "evidence-validate", str(contract), "--events", str(events),
        "--lock", str(lock), "--as-of", AS_OF, "--strict",
    ])
    assert code == 0, out


def test_load_authorizer_accepts_a_lock_built_for_the_mismatched_pack_pair(tmp_path: Path) -> None:
    contract = _agentic_project(tmp_path, "pair")
    document = load_nyx(contract)
    composition = compose_document_governance(document, registry=registry_for_contract(contract))
    lock = tmp_path / "nornyx.agentic_network.lock"
    write_agentic_network_lock(build_agentic_network_lock(document, composition), lock)

    authorizer = load_authorizer(contract, lock, validation_as_of=AS_OF)
    assert authorizer.contract_digest.startswith("sha256:")


@pytest.mark.parametrize(("case", "warning"), CASES)
def test_core_static_generate_and_repo_drift_accept_the_contract(
    tmp_path: Path, case: str, warning: str
) -> None:
    contract = _agentic_project(tmp_path, case)
    out_dir = tmp_path / "generated"

    code, out = _cli(["generate", str(contract), "--out", str(out_dir)])
    assert code == 0, out
    report = check_repo_drift(contract, out_dir)
    assert report.get("status") == "pass", report
