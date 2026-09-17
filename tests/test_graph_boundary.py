"""The ``graph:`` block is checked against a declared vocabulary (issue #104).

Before this suite existed, ``graph.nodes[].kind`` was an open string, a
profile's ``graph.node_kinds`` / ``graph.relationship_constraints`` were never
read, ``depends_on`` matched any pair, and no cycle was ever reported. The
fixture is the exact specimen from the issue: world-model entities in a
five-node ``depends_on`` cycle inside a governed contract, under ``telecom_ops``.

Sections marked B1/B2 pin the repairs from the independent review of the first
repair: exact profile relation pairs (no Cartesian widening) and dependency-only
cycle semantics (no inverse folding).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nornyx.checker import (
    CORE_GRAPH_NODE_KINDS,
    DEPENDENCY_GRAPH_RELATIONS,
    GRAPH_RELATION_RULES,
    _dependency_cycles,
    _graph_ref_targets,
    check_document,
    core_graph_vocabulary,
    graph_vocabulary_for_profile,
    graph_vocabulary_for_profile_pack,
    has_errors,
)
from nornyx.cli import main
from nornyx.parser import load_nyx
from nornyx.profiles import DOMAIN_PROFILE_NAMES, builtin_profile_registry, profile_document

ROOT = Path(__file__).resolve().parents[1]
SPECIMEN = ROOT / "tests" / "fixtures" / "graph_boundary" / "issue_104_probe.nyx"
NEW_CODES = {
    "UNKNOWN_GRAPH_NODE_KIND",
    "GRAPH_NODE_WITHOUT_REF",
    "GRAPH_CYCLE",
    "GRAPH_VOCABULARY_PROFILE_UNRESOLVED",
    "GRAPH_VOCABULARY_UNAVAILABLE",
}


def _codes(diagnostics) -> list[str]:
    return [d.code for d in diagnostics]


def _goal(identifier: str) -> dict:
    return {
        "id": identifier,
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


def _base(**graph) -> dict:
    """A document declaring one of every block a graph node may reference."""
    return {
        "nornyx": "0.2",
        "project": {"name": "Example"},
        "agents": [{"name": "Builder"}],
        "policies": [{"name": "SafePolicy"}],
        "evals": [{"name": "QualityEval", "metrics": ["tests_pass"]}],
        "contexts": [{"name": "RepoContext", "include": ["README.md"]}],
        "approvals": [{"name": "HumanReview"}],
        "budgets": [{"name": "DevBudget"}],
        "goals": [],
        "graph": graph,
    }


NODES = {
    "agent.builder": {"id": "agent.builder", "kind": "agent", "ref": "Builder"},
    "policy.safe": {"id": "policy.safe", "kind": "policy", "ref": "SafePolicy"},
    "eval.quality": {"id": "eval.quality", "kind": "eval", "ref": "QualityEval"},
    "context.repo": {"id": "context.repo", "kind": "context", "ref": "RepoContext"},
    "approval.human": {"id": "approval.human", "kind": "approval", "ref": "HumanReview"},
    "budget.dev": {"id": "budget.dev", "kind": "budget", "ref": "DevBudget"},
    "artifact.spec": {"id": "artifact.spec", "kind": "artifact", "ref": "docs/spec.md"},
}


def _doc(*edges: tuple[str, str, str]) -> dict:
    ids = {source for source, _, _ in edges} | {target for _, _, target in edges}
    return _base(
        nodes=[NODES[node_id] for node_id in sorted(ids)],
        edges=[{"from": s, "to": t, "relation": r} for s, r, t in edges],
    )


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
    assert "GRAPH_VOCABULARY_PROFILE_UNRESOLVED" not in by_code, "telecom_ops is built in"
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
                NODES["agent.builder"],
                {"id": "customer.a", "kind": "customer", "ref": "Customer-A"},
            ],
            edges=[{"from": "agent.builder", "to": "customer.a", "relation": "depends_on"}],
        )
    )
    codes = _codes(diagnostics)

    assert codes.count("UNKNOWN_GRAPH_NODE_KIND") == 1
    assert "INVALID_GRAPH_RELATION_PAIR" not in codes
    assert not has_errors(diagnostics)


def test_unknown_relation_still_warns_when_an_endpoint_kind_is_unknown() -> None:
    diagnostics = check_document(
        _base(
            nodes=[
                {"id": "resource.sbc17", "kind": "network_element", "ref": "SBC-17"},
                {"id": "alarm.331", "kind": "alarm", "ref": "Alarm-331"},
            ],
            edges=[{"from": "resource.sbc17", "to": "alarm.331", "relation": "affected_by"}],
        )
    )
    codes = _codes(diagnostics)

    assert codes.count("UNKNOWN_GRAPH_NODE_KIND") == 2
    assert codes.count("UNKNOWN_GRAPH_RELATION") == 1
    assert "INVALID_GRAPH_RELATION_PAIR" not in codes


def test_depends_on_between_core_kinds_stays_clean() -> None:
    diagnostics = check_document(_doc(("agent.builder", "depends_on", "policy.safe")))

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
    assert DEPENDENCY_GRAPH_RELATIONS <= set(GRAPH_RELATION_RULES)


# ------------------------------------------------- B1: exact relation pairs


def _vocabulary(*triples: tuple[str, str, str]):
    return graph_vocabulary_for_profile(
        {
            "node_kinds": sorted({k for k, _, _ in triples} | {k for _, _, k in triples}),
            "relationship_constraints": [
                {"from_kind": s, "relation": r, "to_kind": t} for s, r, t in triples
            ],
        },
        profile_id="org.test.pairs",
    )


def test_b1_one_profile_pair_does_not_cross_with_the_core_sets() -> None:
    governs = _vocabulary(("component", "governs", "interface")).relation_rules["governs"]

    assert governs.allows("policy", "agent"), "core pair survives"
    assert governs.allows("component", "interface"), "the exact declared pair"
    assert not governs.allows("policy", "interface"), "core source x profile target"
    assert not governs.allows("component", "agent"), "profile source x core target"
    assert not governs.allows("component", "goal")
    assert not governs.allows("interface", "component"), "declared pairs are ordered"


def test_b1_two_profile_triples_do_not_imply_crossed_pairs() -> None:
    links = _vocabulary(("A", "links", "B"), ("C", "links", "D")).relation_rules["links"]

    assert links.allows("A", "B") and links.allows("C", "D")
    assert not links.allows("A", "D") and not links.allows("C", "B")
    assert not links.allows("B", "A") and not links.allows("A", "A")
    assert links.allowed_from == frozenset() and links.allowed_to == frozenset(), (
        "a profile-only relation carries no core sets to multiply"
    )


def test_b1_a_profile_cannot_declare_a_wildcard_endpoint() -> None:
    vocabulary = graph_vocabulary_for_profile(
        {
            "node_kinds": ["*", "component"],
            "relationship_constraints": [
                {"from_kind": "*", "relation": "governs", "to_kind": "component"},
                {"from_kind": "component", "relation": "exposes", "to_kind": "*"},
            ],
        },
        profile_id="org.test.wildcard",
    )

    assert "*" not in vocabulary.node_kinds
    assert vocabulary.relation_rules["governs"].pairs == frozenset()
    assert "exposes" not in vocabulary.relation_rules
    assert not vocabulary.relation_rules["governs"].allows("agent", "component")


def test_b1_profile_pairs_never_narrow_core_rules() -> None:
    core = core_graph_vocabulary().relation_rules
    extended = _vocabulary(("component", "governs", "interface")).relation_rules
    for relation, rule in core.items():
        for source in rule.allowed_from - {"*"}:
            for target in rule.allowed_to - {"*"}:
                assert core[relation].allows(source, target), (relation, source, target)
                assert extended[relation].allows(source, target), (relation, source, target)


def _architecture_doc(edge_from: str, edge_to: str, relation: str) -> dict:
    doc = _base(
        nodes=[
            {"id": "component.api", "kind": "component", "ref": "ApiService"},
            {"id": "interface.rest", "kind": "interface", "ref": "RestInterface"},
            NODES["policy.safe"],
            NODES["agent.builder"],
        ],
        edges=[{"from": edge_from, "to": edge_to, "relation": relation}],
    )
    doc["project"]["profile"] = "architecture_governance"
    return doc


@pytest.mark.parametrize(
    ("edge_from", "relation", "edge_to"),
    [
        ("component.api", "exposes", "interface.rest"),  # profile-only relation, declared pair
        ("policy.safe", "governs", "component.api"),  # core relation widened by a declared pair
        ("policy.safe", "governs", "agent.builder"),  # core pair, untouched by the profile
    ],
)
def test_b1_exact_declared_and_core_pairs_pass_through_check_document(
    edge_from: str, relation: str, edge_to: str
) -> None:
    diagnostics = check_document(_architecture_doc(edge_from, edge_to, relation))

    assert "INVALID_GRAPH_RELATION_PAIR" not in _codes(diagnostics)
    assert "UNKNOWN_GRAPH_RELATION" not in _codes(diagnostics)
    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics]


@pytest.mark.parametrize(
    ("edge_from", "relation", "edge_to"),
    [
        ("policy.safe", "governs", "interface.rest"),  # core source x profile target
        ("component.api", "governs", "agent.builder"),  # profile source x core target
        ("interface.rest", "exposes", "component.api"),  # declared pair reversed
        ("component.api", "exposes", "agent.builder"),  # declared source, undeclared target
    ],
)
def test_b1_crossed_pairs_are_rejected_through_check_document(
    edge_from: str, relation: str, edge_to: str
) -> None:
    diagnostics = check_document(_architecture_doc(edge_from, edge_to, relation))
    pair_errors = [d for d in diagnostics if d.code == "INVALID_GRAPH_RELATION_PAIR"]

    assert len(pair_errors) == 1
    assert pair_errors[0].path == "graph.edges[0].relation"
    assert has_errors(diagnostics)


def test_b1_depends_on_wildcard_ranges_over_known_kinds_only() -> None:
    depends_on = core_graph_vocabulary().relation_rules["depends_on"]
    assert depends_on.allowed_from == frozenset({"*"}) == depends_on.allowed_to
    assert depends_on.allows("agent", "goal") and depends_on.allows("goal", "agent")

    diagnostics = check_document(
        _base(
            nodes=[NODES["agent.builder"], {"id": "thing.x", "kind": "thing", "ref": "X"}],
            edges=[{"from": "thing.x", "to": "agent.builder", "relation": "depends_on"}],
        )
    )
    codes = _codes(diagnostics)
    assert codes.count("UNKNOWN_GRAPH_NODE_KIND") == 1
    assert "INVALID_GRAPH_RELATION_PAIR" not in codes, (
        "the node warning carries it, not a pair error"
    )
    assert not has_errors(diagnostics), "warning-first; --strict promotes it (specimen test)"


# ------------------------------------------------------------ profile extension


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
        assert vocabulary.resolution == "profile", name
        assert CORE_GRAPH_NODE_KINDS <= vocabulary.node_kinds, name
        assert set(GRAPH_RELATION_RULES) <= set(vocabulary.relation_rules), name
        for constraint in (profile.raw.get("graph") or {}).get("relationship_constraints") or []:
            rule = vocabulary.relation_rules[constraint["relation"]]
            assert rule.allows(constraint["from_kind"], constraint["to_kind"]), (name, constraint)
            assert (constraint["from_kind"], constraint["to_kind"]) in rule.pairs, (
                name,
                constraint,
            )


def test_unknown_profile_is_reported_and_checked_against_core() -> None:
    doc = _architecture_doc("component.api", "interface.rest", "exposes")
    doc["project"]["profile"] = "no_such_profile"
    diagnostics = check_document(doc)
    codes = _codes(diagnostics)

    assert codes.count("UNKNOWN_GRAPH_NODE_KIND") == 2
    assert codes.count("GRAPH_VOCABULARY_PROFILE_UNRESOLVED") == 1
    assert all("declared by the active profile" not in d.message for d in diagnostics)
    assert not has_errors(diagnostics), "a free-form project.profile has never failed a contract"


def test_documents_without_a_graph_do_not_report_vocabulary_resolution() -> None:
    doc = _base(nodes=[], edges=[])
    del doc["graph"]
    doc["project"]["profile"] = "no_such_profile"

    assert "GRAPH_VOCABULARY_PROFILE_UNRESOLVED" not in _codes(check_document(doc))


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


# -------------------------------------------- B2: dependency-only cycle semantics


def test_b2_reviewer_counterexample_is_not_folded_away_and_is_not_a_dependency_cycle() -> None:
    # Both edges are legal core pairs and, as declared, form a two-node loop.
    doc = _doc(
        ("eval.quality", "must_produce", "artifact.spec"),
        ("artifact.spec", "validated_by", "eval.quality"),
    )
    diagnostics = check_document(doc)

    assert "INVALID_GRAPH_RELATION_PAIR" not in _codes(diagnostics)
    assert "GRAPH_CYCLE" not in _codes(diagnostics), (
        "not a dependency cycle: outside the checked class"
    )
    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics]

    # Nothing was reversed or renamed: the same loop over depends_on IS reported,
    # and a non-dependency edge never closes a dependency cycle.
    raw = [
        ("eval.quality", "artifact.spec", "must_produce"),
        ("artifact.spec", "eval.quality", "validated_by"),
    ]
    assert _dependency_cycles(raw) == []
    assert _dependency_cycles([(s, t, "depends_on") for s, t, _ in raw]) == [
        ["artifact.spec", "eval.quality"]
    ]
    assert _dependency_cycles([("a", "b", "depends_on"), ("b", "a", "validated_by")]) == []


@pytest.mark.parametrize(
    ("legal", "linguistic_inverse"),
    [
        (
            ("artifact.spec", "validated_by", "eval.quality"),
            ("eval.quality", "validates", "artifact.spec"),
        ),
        (
            ("artifact.spec", "governed_by", "policy.safe"),
            ("policy.safe", "governs", "artifact.spec"),
        ),
        (
            ("artifact.spec", "gated_by", "approval.human"),
            ("approval.human", "gates", "artifact.spec"),
        ),
        (("artifact.spec", "bounded_by", "budget.dev"), ("budget.dev", "bounds", "artifact.spec")),
        (
            ("eval.quality", "uses_context", "context.repo"),
            ("context.repo", "authorizes_context_for", "eval.quality"),
        ),
    ],
)
def test_b2_every_former_inverse_pair_is_asymmetric_so_folding_would_launder_legality(
    legal: tuple[str, str, str], linguistic_inverse: tuple[str, str, str]
) -> None:
    accepted = check_document(_doc(legal))
    assert "INVALID_GRAPH_RELATION_PAIR" not in _codes(accepted), legal
    assert "GRAPH_CYCLE" not in _codes(accepted)
    assert not has_errors(accepted), [d.to_dict() for d in accepted]

    rejected = check_document(_doc(linguistic_inverse))
    assert _codes(rejected).count("INVALID_GRAPH_RELATION_PAIR") == 1, linguistic_inverse


def test_b2_a_relationship_declared_from_both_ends_is_not_a_cycle() -> None:
    diagnostics = check_document(
        _doc(
            ("policy.safe", "governs", "agent.builder"),
            ("agent.builder", "governed_by", "policy.safe"),
        )
    )

    assert "GRAPH_CYCLE" not in _codes(diagnostics)
    assert not has_errors(diagnostics)


def test_b2_a_loop_mixing_relation_classes_is_not_a_dependency_cycle() -> None:
    doc = _base(
        nodes=[{"id": "goal.a", "kind": "goal", "ref": "GOAL-001"}, NODES["eval.quality"]],
        edges=[
            {"from": "goal.a", "to": "eval.quality", "relation": "depends_on"},
            {"from": "eval.quality", "to": "goal.a", "relation": "validates"},
        ],
    )
    doc["goals"] = [_goal("GOAL-001")]
    diagnostics = check_document(doc)

    assert "GRAPH_CYCLE" not in _codes(diagnostics)
    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics]


def _goal_graph(edges: list[tuple[str, str]], ids: str) -> dict:
    doc = _base(
        nodes=[
            {"id": f"goal.{n}", "kind": "goal", "ref": f"GOAL-00{i}"} for i, n in enumerate(ids, 1)
        ],
        edges=[
            {"from": f"goal.{s}", "to": f"goal.{t}", "relation": "depends_on"} for s, t in edges
        ],
    )
    doc["goals"] = [_goal(f"GOAL-00{i}") for i in range(1, len(ids) + 1)]
    return doc


def test_b2_a_genuine_multi_node_dependency_cycle_is_reported_once() -> None:
    diagnostics = check_document(_goal_graph([("c", "a"), ("a", "b"), ("b", "c")], "cab"))
    cycles = [d for d in diagnostics if d.code == "GRAPH_CYCLE"]

    assert len(cycles) == 1
    assert cycles[0].message.endswith("goal.a, goal.b, goal.c")
    assert cycles[0].path == "graph.edges"
    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics]


def test_b2_multiple_components_are_reported_deterministically() -> None:
    edges = [("a", "b"), ("b", "a"), ("d", "e"), ("e", "f"), ("f", "d"), ("c", "a"), ("f", "c")]
    forward = [
        d.message for d in check_document(_goal_graph(edges, "abcdef")) if d.code == "GRAPH_CYCLE"
    ]
    reversed_order = [
        d.message
        for d in check_document(_goal_graph(edges[::-1], "abcdef"))
        if d.code == "GRAPH_CYCLE"
    ]

    assert forward == reversed_order
    assert [m.split(": ")[1] for m in forward] == ["goal.a, goal.b", "goal.d, goal.e, goal.f"]


def test_b2_self_edges_keep_their_own_diagnostic_and_are_not_cycles() -> None:
    diagnostics = check_document(
        _base(
            nodes=[NODES["agent.builder"]],
            edges=[{"from": "agent.builder", "to": "agent.builder", "relation": "depends_on"}],
        )
    )
    codes = _codes(diagnostics)

    assert "GRAPH_SELF_EDGE" in codes
    assert "GRAPH_CYCLE" not in codes


def _long_chain(size: int, *, close: bool) -> dict:
    doc = _base(
        nodes=[{"id": f"goal.g{i}", "kind": "goal", "ref": f"GOAL-{i:04d}"} for i in range(size)],
        edges=[
            {"from": f"goal.g{i}", "to": f"goal.g{i + 1}", "relation": "depends_on"}
            for i in range(size - 1)
        ]
        + (
            [{"from": f"goal.g{size - 1}", "to": "goal.g0", "relation": "depends_on"}]
            if close
            else []
        ),
    )
    doc["goals"] = [_goal(f"GOAL-{i:04d}") for i in range(size)]
    return doc


def test_b2_a_very_long_dependency_cycle_is_detected_without_recursion() -> None:
    size = 5000
    cycles = [d for d in check_document(_long_chain(size, close=True)) if d.code == "GRAPH_CYCLE"]

    assert len(cycles) == 1
    assert cycles[0].message.count("goal.g") == size


def test_b2_a_very_long_acyclic_chain_is_checked_without_recursion_and_stays_clean() -> None:
    diagnostics = check_document(_long_chain(5000, close=False))

    assert "GRAPH_CYCLE" not in _codes(diagnostics)
    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics][:3]


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
