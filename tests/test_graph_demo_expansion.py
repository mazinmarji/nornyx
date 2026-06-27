from __future__ import annotations

from pathlib import Path

from nornyx.checker import check_document, has_errors
from nornyx.parser import load_nyx


EXAMPLE = Path("examples/nornyx_graph_demo_expanded.nyx")
DOC = Path("docs/63_NORNYX_GRAPH_DEMO_EXPANDED.md")
README = Path("README.md")

REQUIRED_NODE_KINDS = {
    "intent",
    "context",
    "agent",
    "skill",
    "policy",
    "eval",
    "approval",
    "evidence",
    "budget",
    "trace",
    "goal",
    "artifact",
    "module",
}

REQUIRED_RELATIONS = {
    "uses_context",
    "has_skill",
    "governed_by",
    "validated_by",
    "gated_by",
    "bounded_by",
    "produces_evidence",
    "records_trace",
    "satisfies_intent",
    "produces_artifact",
}


def load_demo() -> dict:
    return load_nyx(EXAMPLE)


def test_expanded_graph_demo_checks_clean() -> None:
    diagnostics = check_document(load_demo())

    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics]
    assert not any(
        d.code in {"UNKNOWN_GRAPH_RELATION", "INVALID_GRAPH_RELATION_PAIR"}
        for d in diagnostics
    )


def test_expanded_graph_demo_covers_required_node_kinds() -> None:
    graph = load_demo()["graph"]
    kinds = {node["kind"] for node in graph["nodes"]}

    assert REQUIRED_NODE_KINDS.issubset(kinds)


def test_expanded_graph_demo_covers_required_relation_types() -> None:
    graph = load_demo()["graph"]
    relations = {edge["relation"] for edge in graph["edges"]}

    assert REQUIRED_RELATIONS.issubset(relations)


def test_expanded_graph_demo_declares_auditability_coverage() -> None:
    graph = load_demo()["graph"]
    contract = load_demo()["contracts"][0]
    node_ids = set(contract["nodes"])
    relations = {(edge["from"], edge["to"], edge["relation"]) for edge in graph["edges"]}

    assert "approval.product_owner" in node_ids
    assert "evidence.expanded_graph_demo" in node_ids
    assert "budget.expanded_graph_demo" in node_ids
    assert "trace.expanded_graph" in node_ids
    assert ("goal.graph_demo_expansion", "approval.product_owner", "gated_by") in relations
    assert ("goal.graph_demo_expansion", "budget.expanded_graph_demo", "bounded_by") in relations
    assert ("goal.graph_demo_expansion", "trace.expanded_graph", "records_trace") in relations


def test_expanded_graph_demo_preserves_static_safety_boundary() -> None:
    demo = load_demo()
    goal = demo["goals"][0]

    assert "connectors" not in demo
    assert "adapters" not in demo
    assert "graph_runtime_execution" in goal["non_goals"]
    assert "live_connector_execution" in goal["non_goals"]
    assert "model_calls" in goal["non_goals"]
    assert "GOAL-100_promotion" in goal["non_goals"]


def test_expanded_graph_docs_are_product_facing_and_non_runtime() -> None:
    doc = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")

    assert "Graph edges are semantic, audit, and control relationships" in doc
    assert "Governed Delivery Control Plane or Agentic Development Harness" in doc
    assert "docs/63_NORNYX_GRAPH_DEMO_EXPANDED.md" in readme
