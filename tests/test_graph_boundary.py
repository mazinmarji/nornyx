"""The ``graph:`` block is checked against a declared vocabulary (issue #104).

Before this suite existed, ``graph.nodes[].kind`` was an open string, a
profile's ``graph.node_kinds`` / ``graph.relationship_constraints`` were never
read, ``depends_on`` matched any pair of kinds, and no cycle was ever reported.
The fixture is the exact specimen from the issue: world-model entities in a
five-node cycle inside a governed contract, under ``telecom_ops``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nornyx.checker import (
    CORE_GRAPH_NODE_KINDS,
    GRAPH_RELATION_RULES,
    _graph_ref_targets,
    check_document,
    core_graph_vocabulary,
    graph_vocabulary_for_profile_pack,
    has_errors,
)
from nornyx.cli import main
from nornyx.parser import load_nyx
from nornyx.profiles import DOMAIN_PROFILE_NAMES, builtin_profile_registry, profile_document

ROOT = Path(__file__).resolve().parents[1]
SPECIMEN = ROOT / "tests" / "fixtures" / "graph_boundary" / "issue_104_probe.nyx"
NEW_CODES = {"UNKNOWN_GRAPH_NODE_KIND", "GRAPH_NODE_WITHOUT_REF", "GRAPH_CYCLE"}


def _codes(diagnostics) -> list[str]:
    return [d.code for d in diagnostics]


def _base(**graph) -> dict:
    return {
        "nornyx": "0.2",
        "project": {"name": "Example"},
        "agents": [{"name": "Builder"}],
        "policies": [{"name": "SafePolicy"}],
        "goals": [],
        "graph": graph,
    }


# --------------------------------------------------------------------- specimen


def test_issue_104_specimen_is_reported_as_warnings() -> None:
    diagnostics = check_document(load_nyx(SPECIMEN))
    by_code: dict[str, list] = {}
    for item in diagnostics:
        by_code.setdefault(item.code, []).append(item)

    unknown = by_code.get("UNKNOWN_GRAPH_NODE_KIND", [])
    assert [d.path for d in unknown] == [f"graph.nodes[{i}].kind" for i in range(5)]
    assert [d.message.split()[1] for d in unknown] == [
        "'customer'",
        "'service'",
        "'network_element'",
        "'alarm'",
        "'change'",
    ]
    assert all("declared by the active profile" in d.message for d in unknown), (
        "telecom_ops resolved from project.profile, so the message names the profile"
    )

    cycles = by_code.get("GRAPH_CYCLE", [])
    assert len(cycles) == 1
    assert cycles[0].message.endswith(
        "alarm.331, change.782, customer.a, resource.sbc17, service.voice"
    )

    # Pair validation is skipped for edges touching an unknown kind: the node
    # diagnostic already covers them, and no hard error is introduced.
    assert "INVALID_GRAPH_RELATION_PAIR" not in by_code
    assert "UNKNOWN_GRAPH_RELATION" not in by_code
    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics]


def test_issue_104_specimen_passes_plain_and_fails_strict_via_cli(capsys) -> None:
    assert main(["check", str(SPECIMEN)]) == 0, "warning-first: an existing contract keeps exit 0"
    plain = capsys.readouterr().out
    assert "UNKNOWN_GRAPH_NODE_KIND" in plain and "GRAPH_CYCLE" in plain

    assert main(["check", "--strict", str(SPECIMEN)]) == 1
    strict = capsys.readouterr().out
    assert "STRICT_WARNINGS_PRESENT" in strict
    assert "GRAPH_CYCLE" in strict and "UNKNOWN_GRAPH_NODE_KIND" in strict


# ------------------------------------------------------------- node vocabulary


def test_unknown_kind_is_a_warning_and_disables_the_depends_on_wildcard() -> None:
    diagnostics = check_document(
        _base(
            nodes=[
                {"id": "agent.builder", "kind": "agent", "ref": "Builder"},
                {"id": "customer.a", "kind": "customer", "ref": "Customer-A"},
            ],
            edges=[{"from": "agent.builder", "to": "customer.a", "relation": "depends_on"}],
        )
    )
    codes = _codes(diagnostics)

    assert codes.count("UNKNOWN_GRAPH_NODE_KIND") == 1
    assert "INVALID_GRAPH_RELATION_PAIR" not in codes
    assert not has_errors(diagnostics)


def test_depends_on_between_core_kinds_stays_clean() -> None:
    diagnostics = check_document(
        _base(
            nodes=[
                {"id": "agent.builder", "kind": "agent", "ref": "Builder"},
                {"id": "policy.safe", "kind": "policy", "ref": "SafePolicy"},
            ],
            edges=[{"from": "agent.builder", "to": "policy.safe", "relation": "depends_on"}],
        )
    )

    assert not any(code in NEW_CODES for code in _codes(diagnostics))
    assert not has_errors(diagnostics)


def test_core_vocabulary_is_self_consistent() -> None:
    rule_kinds = {
        kind
        for allowed_from, allowed_to in GRAPH_RELATION_RULES.values()
        for kind in allowed_from | allowed_to
    } - {"*"}
    assert rule_kinds <= CORE_GRAPH_NODE_KINDS
    assert set(_graph_ref_targets({})) <= CORE_GRAPH_NODE_KINDS
    assert core_graph_vocabulary().node_kinds == CORE_GRAPH_NODE_KINDS


# ------------------------------------------------------------ profile extension


def _architecture_doc(edge_from: str, edge_to: str, relation: str) -> dict:
    doc = _base(
        nodes=[
            {"id": "component.api", "kind": "component", "ref": "ApiService"},
            {"id": "interface.rest", "kind": "interface", "ref": "RestInterface"},
            {"id": "policy.safe", "kind": "policy", "ref": "SafePolicy"},
        ],
        edges=[{"from": edge_from, "to": edge_to, "relation": relation}],
    )
    doc["project"]["profile"] = "architecture_governance"
    return doc


def test_profile_node_kinds_and_constraints_extend_the_core_vocabulary() -> None:
    diagnostics = check_document(_architecture_doc("component.api", "interface.rest", "exposes"))

    assert "UNKNOWN_GRAPH_NODE_KIND" not in _codes(diagnostics)
    assert "UNKNOWN_GRAPH_RELATION" not in _codes(diagnostics)
    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics]


def test_profile_constraint_widens_a_core_relation_without_narrowing_it() -> None:
    # architecture_governance declares ``policy governs component``; core keeps
    # ``policy governs agent``.
    widened = check_document(_architecture_doc("policy.safe", "component.api", "governs"))
    assert "INVALID_GRAPH_RELATION_PAIR" not in _codes(widened)

    doc = _architecture_doc("policy.safe", "component.api", "governs")
    doc["graph"]["nodes"].append({"id": "agent.builder", "kind": "agent", "ref": "Builder"})
    doc["graph"]["edges"].append(
        {"from": "policy.safe", "to": "agent.builder", "relation": "governs"}
    )
    assert "INVALID_GRAPH_RELATION_PAIR" not in _codes(check_document(doc))


def test_profile_declared_relation_is_pair_checked_like_a_core_one() -> None:
    diagnostics = check_document(_architecture_doc("interface.rest", "component.api", "exposes"))
    pair_errors = [d for d in diagnostics if d.code == "INVALID_GRAPH_RELATION_PAIR"]

    assert len(pair_errors) == 1
    assert pair_errors[0].path == "graph.edges[0].relation"
    assert has_errors(diagnostics)


def test_an_explicit_vocabulary_argument_is_authoritative() -> None:
    doc = _architecture_doc("component.api", "interface.rest", "exposes")
    diagnostics = check_document(doc, graph_vocabulary=core_graph_vocabulary())
    codes = _codes(diagnostics)

    assert codes.count("UNKNOWN_GRAPH_NODE_KIND") == 2
    assert not has_errors(diagnostics)


def test_every_builtin_profile_graph_declaration_loads_as_a_superset_of_core() -> None:
    registry = builtin_profile_registry()
    for name in registry.profile_names:
        profile = registry.resolve_profile(name)
        vocabulary = graph_vocabulary_for_profile_pack(profile)
        assert CORE_GRAPH_NODE_KINDS <= vocabulary.node_kinds, name
        assert set(GRAPH_RELATION_RULES) <= set(vocabulary.relation_rules), name
        for constraint in (profile.raw.get("graph") or {}).get("relationship_constraints") or []:
            allowed_from, allowed_to = vocabulary.relation_rules[constraint["relation"]]
            assert constraint["from_kind"] in allowed_from, (name, constraint)
            assert constraint["to_kind"] in allowed_to, (name, constraint)


def test_unknown_profile_falls_back_to_the_core_vocabulary() -> None:
    doc = _architecture_doc("component.api", "interface.rest", "exposes")
    doc["project"]["profile"] = "no_such_profile"
    diagnostics = check_document(doc)

    assert _codes(diagnostics).count("UNKNOWN_GRAPH_NODE_KIND") == 2
    assert all("declared by the active profile" not in d.message for d in diagnostics)


# ----------------------------------------------------------------------- refs


def test_profile_project_and_contract_refs_resolve_in_document() -> None:
    doc = _base(
        nodes=[
            {"id": "profile.arch", "kind": "profile", "ref": "architecture_governance"},
            {"id": "project.self", "kind": "project", "ref": "Example"},
            {"id": "contract.build", "kind": "contract", "ref": "BuildContract"},
        ],
        edges=[],
    )
    doc["project"]["profile"] = "architecture_governance"
    doc["contracts"] = [{"name": "BuildContract", "nodes": ["contract.build"]}]
    assert "UNKNOWN_GRAPH_REF_REFERENCE" not in _codes(check_document(doc))

    doc["graph"]["nodes"][2]["ref"] = "MissingContract"
    doc["graph"]["nodes"][0]["ref"] = "other_profile"
    diagnostics = check_document(doc)
    ref_errors = [d.path for d in diagnostics if d.code == "UNKNOWN_GRAPH_REF_REFERENCE"]

    assert ref_errors == ["graph.nodes[0].ref", "graph.nodes[2].ref"]
    assert has_errors(diagnostics)


@pytest.mark.parametrize("kind", ["artifact", "module"])
def test_artifact_and_module_nodes_warn_without_a_ref(kind: str) -> None:
    missing = check_document(_base(nodes=[{"id": f"{kind}.x", "kind": kind}], edges=[]))
    present = check_document(
        _base(nodes=[{"id": f"{kind}.x", "kind": kind, "ref": "docs/x.md"}], edges=[])
    )

    assert _codes(missing).count("GRAPH_NODE_WITHOUT_REF") == 1
    assert "GRAPH_NODE_WITHOUT_REF" not in _codes(present)
    assert not has_errors(missing)


# --------------------------------------------------------------------- cycles


def test_inverse_relation_pairs_are_not_reported_as_cycles() -> None:
    diagnostics = check_document(
        _base(
            nodes=[
                {"id": "agent.builder", "kind": "agent", "ref": "Builder"},
                {"id": "policy.safe", "kind": "policy", "ref": "SafePolicy"},
            ],
            edges=[
                {"from": "policy.safe", "to": "agent.builder", "relation": "governs"},
                {"from": "agent.builder", "to": "policy.safe", "relation": "governed_by"},
            ],
        )
    )

    assert "GRAPH_CYCLE" not in _codes(diagnostics)
    assert not has_errors(diagnostics)


def test_a_real_cycle_is_reported_once_with_sorted_members() -> None:
    doc = _base(
        nodes=[
            {"id": f"goal.{n}", "kind": "goal", "ref": f"GOAL-00{i}"}
            for i, n in enumerate("cab", 1)
        ],
        edges=[
            {"from": "goal.c", "to": "goal.a", "relation": "depends_on"},
            {"from": "goal.a", "to": "goal.b", "relation": "depends_on"},
            {"from": "goal.b", "to": "goal.c", "relation": "depends_on"},
        ],
    )
    doc["goals"] = [
        {
            "id": f"GOAL-00{i}",
            "title": "t",
            "phase": "v0.1",
            "goal": "g",
            "scope": ["s"],
            "non_goals": ["n"],
            "validation": ["v"],
            "stop_rules": ["r"],
            "evidence": "e/",
            "approval": "required",
        }
        for i in (1, 2, 3)
    ]
    diagnostics = check_document(doc)
    cycles = [d for d in diagnostics if d.code == "GRAPH_CYCLE"]

    assert len(cycles) == 1
    assert cycles[0].message.endswith("goal.a, goal.b, goal.c")
    assert cycles[0].path == "graph.edges"
    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics]


def test_self_edges_keep_their_own_diagnostic_and_are_not_cycles() -> None:
    diagnostics = check_document(
        _base(
            nodes=[{"id": "agent.builder", "kind": "agent", "ref": "Builder"}],
            edges=[{"from": "agent.builder", "to": "agent.builder", "relation": "depends_on"}],
        )
    )
    codes = _codes(diagnostics)

    assert "GRAPH_SELF_EDGE" in codes
    assert "GRAPH_CYCLE" not in codes


# ------------------------------------------------------------- compatibility


@pytest.mark.parametrize(
    "example",
    ["examples/nornyx_graph_demo.nyx", "examples/nornyx_graph_demo_expanded.nyx"],
)
def test_shipped_graph_demos_gain_no_new_diagnostics(example: str) -> None:
    diagnostics = check_document(load_nyx(ROOT / example))

    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics]
    assert not any(code in NEW_CODES for code in _codes(diagnostics)), [
        d.to_dict() for d in diagnostics if d.code in NEW_CODES
    ]


def test_generated_domain_profile_documents_stay_diagnostic_free() -> None:
    for name in DOMAIN_PROFILE_NAMES:
        diagnostics = check_document(profile_document(name, "DemoProject"))
        assert not diagnostics, (name, [d.to_dict() for d in diagnostics])
