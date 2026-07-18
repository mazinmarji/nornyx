from pathlib import Path

import pytest

from nornyx.parser import NornyxParseError, load_nyx
from nornyx.checker import (
    CORE_TOP_LEVEL_BLOCKS,
    EXTENSION_TOP_LEVEL_BLOCKS,
    check_document,
    has_errors,
)
from nornyx.generator import generate_artifacts
from nornyx.context_builder import build_context_pack


@pytest.mark.parametrize(
    "source",
    [
        """\
nornyx: "0.1"
project: {name: First}
project: {name: Second}
""",
        """\
nornyx: "0.1"
project:
  name: First
  name: Second
""",
        """\
nornyx: "0.1"
project: {name: Example}
approvals:
  - name: HumanGate
    eligible_roles: [reviewer]
    eligible_roles: [owner]
""",
        """\
nornyx: "0.1"
project: {name: Example}
agents:
  - name: Builder
    role: First role
    role: Second role
""",
    ],
    ids=("top-level", "nested", "authorization", "list-item"),
)
def test_duplicate_yaml_keys_fail_closed_at_primary_parse_boundary(
    tmp_path: Path, source: str
) -> None:
    contract = tmp_path / "duplicate.nyx"
    contract.write_text(source, encoding="utf-8")

    with pytest.raises(NornyxParseError, match="duplicate key"):
        load_nyx(contract)


def test_duplicate_yaml_keys_fail_closed_in_referenced_policy(
    tmp_path: Path,
) -> None:
    source = tmp_path / "policies.nyx"
    source.write_text(
        """\
nornyx: "0.1"
project: {name: Policies}
policies:
  - name: SafeDelivery
    rules: [deny secrets_to_llm]
    rules: [require human_approval_before_merge]
""",
        encoding="utf-8",
    )
    contract = tmp_path / "service.nyx"
    contract.write_text(
        """\
nornyx: "0.1"
project: {name: Service}
policies:
  - name: SafeDelivery
    ref: policies.nyx#SafeDelivery
""",
        encoding="utf-8",
    )

    with pytest.raises(NornyxParseError, match="duplicate key"):
        load_nyx(contract)


def test_example_checks_clean():
    doc = load_nyx(Path("examples/governed_delivery_control_plane.nyx"))
    diagnostics = check_document(doc)
    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics]


def test_generator_creates_agents(tmp_path):
    doc = load_nyx(Path("examples/governed_delivery_control_plane.nyx"))
    paths = generate_artifacts(doc, tmp_path)
    generated_names = {p.name for p in paths}
    assert "AGENTS.md" in generated_names
    assert (tmp_path / "harness.yaml").exists()
    assert (tmp_path / "policy.yaml").exists()


def test_context_pack_has_entries():
    doc = load_nyx(Path("examples/governed_delivery_control_plane.nyx"))
    pack = build_context_pack(doc, Path("."))
    assert pack["schema"] == "nornyx.context_pack.v0.1"
    assert isinstance(pack["entries"], list)


def test_v01_core_block_surface_is_frozen():
    assert CORE_TOP_LEVEL_BLOCKS == [
        "nornyx",
        "project",
        "constitution",
        "intents",
        "contexts",
        "skills",
        "policies",
        "agents",
        "harnesses",
        "traces",
        "evals",
        "evidence",
        "approvals",
        "budgets",
        "goals",
    ]
    assert {"experimental", "connectors", "guardrails", "capabilities"}.issubset(
        set(EXTENSION_TOP_LEVEL_BLOCKS)
    )


def test_unknown_top_level_warns_but_deferred_extensions_do_not():
    base = {
        "nornyx": "0.1",
        "project": {"name": "Example"},
        "experimental": {"proposal": "backlog-only"},
    }
    diagnostics = check_document(base)
    assert not any(d.code == "UNKNOWN_TOP_LEVEL_BLOCK" for d in diagnostics)

    diagnostics = check_document({**base, "random_runtime": {}})
    assert any(d.code == "UNKNOWN_TOP_LEVEL_BLOCK" for d in diagnostics)


def test_named_core_block_entries_have_precise_diagnostics():
    diagnostics = check_document(
        {
            "nornyx": "0.1",
            "project": {"name": "Example"},
            "skills": ["PatchBuilder"],
            "policies": [{}],
        }
    )
    by_code = {d.code: d for d in diagnostics}
    assert by_code["INVALID_BLOCK_ENTRY"].path == "skills[0]"
    assert by_code["MISSING_POLICY_NAME"].path == "policies[0].name"


def test_core_mapping_blocks_reject_list_values():
    diagnostics = check_document(
        {
            "nornyx": "0.1",
            "project": {"name": "Example"},
            "constitution": [],
            "evidence": [],
        }
    )
    mapping_errors = [d for d in diagnostics if d.code == "INVALID_MAPPING_BLOCK"]

    assert {d.path for d in mapping_errors} == {"constitution", "evidence"}
    assert has_errors(diagnostics)


def test_core_mapping_blocks_accept_mapping_values():
    diagnostics = check_document(
        {
            "nornyx": "0.1",
            "project": {"name": "Example"},
            "constitution": {"principles": ["evidence_required"]},
            "evidence": {"required": ["test_report.json"]},
        }
    )

    assert not any(d.code == "INVALID_MAPPING_BLOCK" for d in diagnostics)
    assert not has_errors(diagnostics)


def test_harness_context_reference_is_checked():
    diagnostics = check_document(
        {
            "nornyx": "0.1",
            "project": {"name": "Example"},
            "contexts": [{"name": "RepoContext", "include": ["README.md"]}],
            "harnesses": [{"name": "DevHarness", "context": "MissingContext", "flow": []}],
        }
    )
    assert any(d.code == "UNKNOWN_CONTEXT_REFERENCE" for d in diagnostics)


def test_graph_contract_model_accepts_declared_nodes_edges_and_gates():
    diagnostics = check_document(
        {
            "nornyx": "0.2",
            "project": {"name": "Example"},
            "contexts": [{"name": "RepoContext", "include": ["README.md"]}],
            "agents": [{"name": "Builder"}],
            "graph": {
                "nodes": [
                    {"id": "context.repo", "kind": "context", "ref": "RepoContext"},
                    {"id": "agent.builder", "kind": "agent", "ref": "Builder"},
                ],
                "edges": [
                    {
                        "from": "context.repo",
                        "to": "agent.builder",
                        "relation": "authorizes_context_for",
                    }
                ],
            },
            "contracts": [
                {
                    "name": "BuildContract",
                    "nodes": ["context.repo", "agent.builder"],
                    "approval": "HumanReview",
                    "budget": "DevBudget",
                }
            ],
            "approvals": [{"name": "HumanReview"}],
            "budgets": [{"name": "DevBudget"}],
        }
    )

    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics]
    assert not any(d.code == "UNKNOWN_VERSION" for d in diagnostics)


def test_static_nornyx_graph_demo_checks_clean():
    doc = load_nyx(Path("examples/nornyx_graph_demo.nyx"))
    diagnostics = check_document(doc)

    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics]
    assert not any(
        d.code in {"UNKNOWN_GRAPH_RELATION", "INVALID_GRAPH_RELATION_PAIR"} for d in diagnostics
    )


def test_graph_node_refs_reject_unknown_named_core_references():
    diagnostics = check_document(
        {
            "nornyx": "0.2",
            "project": {"name": "Example"},
            "contexts": [{"name": "RepoContext", "include": ["README.md"]}],
            "graph": {
                "nodes": [
                    {"id": "context.missing", "kind": "context", "ref": "MissingContext"},
                    {"id": "custom.profile", "kind": "telecom_ops", "ref": "OptionalProfile"},
                ],
                "edges": [],
            },
        }
    )

    ref_errors = [d for d in diagnostics if d.code == "UNKNOWN_GRAPH_REF_REFERENCE"]

    assert len(ref_errors) == 1
    assert ref_errors[0].path == "graph.nodes[0].ref"
    assert has_errors(diagnostics)


def test_graph_edges_reject_unknown_node_references():
    diagnostics = check_document(
        {
            "nornyx": "0.1",
            "project": {"name": "Example"},
            "graph": {
                "nodes": [{"id": "agent.builder", "kind": "agent"}],
                "edges": [
                    {
                        "from": "context.repo",
                        "to": "agent.builder",
                        "relation": "authorizes_context_for",
                    }
                ],
            },
        }
    )

    assert any(d.code == "UNKNOWN_GRAPH_NODE_REFERENCE" for d in diagnostics)
    assert has_errors(diagnostics)


def test_graph_relation_pairs_reject_semantically_invalid_edges():
    diagnostics = check_document(
        {
            "nornyx": "0.2",
            "project": {"name": "Example"},
            "agents": [{"name": "Builder"}],
            "policies": [{"name": "SafePolicy"}],
            "graph": {
                "nodes": [
                    {"id": "agent.builder", "kind": "agent", "ref": "Builder"},
                    {"id": "policy.safe", "kind": "policy", "ref": "SafePolicy"},
                ],
                "edges": [
                    {
                        "from": "agent.builder",
                        "to": "policy.safe",
                        "relation": "governs",
                    }
                ],
            },
        }
    )

    relation_errors = [d for d in diagnostics if d.code == "INVALID_GRAPH_RELATION_PAIR"]

    assert len(relation_errors) == 1
    assert relation_errors[0].path == "graph.edges[0].relation"
    assert has_errors(diagnostics)


def test_graph_validation_warns_on_duplicate_self_and_unknown_relations():
    diagnostics = check_document(
        {
            "nornyx": "0.2",
            "project": {"name": "Example"},
            "agents": [{"name": "Builder"}],
            "graph": {
                "nodes": [{"id": "agent.builder", "kind": "agent", "ref": "Builder"}],
                "edges": [
                    {"from": "agent.builder", "to": "agent.builder", "relation": "custom_loop"},
                    {"from": "agent.builder", "to": "agent.builder", "relation": "custom_loop"},
                ],
            },
        }
    )
    codes = {d.code for d in diagnostics}

    assert {"GRAPH_SELF_EDGE", "DUPLICATE_GRAPH_EDGE", "UNKNOWN_GRAPH_RELATION"}.issubset(codes)
    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics]


def test_graph_evidence_refs_include_harness_flow_evidence_targets():
    diagnostics = check_document(
        {
            "nornyx": "0.2",
            "project": {"name": "Example"},
            "agents": [{"name": "Builder"}],
            "harnesses": [
                {
                    "name": "DevHarness",
                    "flow": [
                        {"agent": "Builder", "action": "implement"},
                        {"evidence": "DevEvidence"},
                    ],
                }
            ],
            "graph": {
                "nodes": [
                    {"id": "agent.builder", "kind": "agent", "ref": "Builder"},
                    {"id": "evidence.dev", "kind": "evidence", "ref": "DevEvidence"},
                ],
                "edges": [
                    {"from": "agent.builder", "to": "evidence.dev", "relation": "must_produce"}
                ],
            },
        }
    )

    assert not any(d.code == "UNKNOWN_GRAPH_REF_REFERENCE" for d in diagnostics)
    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics]


def test_contracts_warn_when_approval_budget_and_evidence_are_not_graph_covered():
    diagnostics = check_document(
        {
            "nornyx": "0.2",
            "project": {"name": "Example"},
            "agents": [{"name": "Builder"}],
            "approvals": [{"name": "HumanReview"}],
            "budgets": [{"name": "DevBudget"}],
            "graph": {
                "nodes": [{"id": "agent.builder", "kind": "agent", "ref": "Builder"}],
                "edges": [],
            },
            "contracts": [
                {
                    "name": "BuildContract",
                    "nodes": ["agent.builder"],
                    "approval": "HumanReview",
                    "budget": "DevBudget",
                }
            ],
        }
    )
    codes = {d.code for d in diagnostics}

    assert {
        "CONTRACT_APPROVAL_NOT_IN_GRAPH",
        "CONTRACT_BUDGET_NOT_IN_GRAPH",
        "CONTRACT_WITHOUT_EVIDENCE_NODE",
    }.issubset(codes)
    assert not has_errors(diagnostics), [d.to_dict() for d in diagnostics]


def test_contracts_reject_unknown_graph_approval_and_budget_references():
    diagnostics = check_document(
        {
            "nornyx": "0.1",
            "project": {"name": "Example"},
            "graph": {
                "nodes": [{"id": "agent.builder", "kind": "agent"}],
                "edges": [],
            },
            "contracts": [
                {
                    "name": "BuildContract",
                    "nodes": ["missing.node"],
                    "approval": "MissingApproval",
                    "budget": "MissingBudget",
                }
            ],
            "approvals": [{"name": "HumanReview"}],
            "budgets": [{"name": "DevBudget"}],
        }
    )
    codes = {d.code for d in diagnostics}

    assert {
        "UNKNOWN_CONTRACT_GRAPH_REFERENCE",
        "UNKNOWN_CONTRACT_APPROVAL_REFERENCE",
        "UNKNOWN_CONTRACT_BUDGET_REFERENCE",
    }.issubset(codes)
    assert has_errors(diagnostics)


def test_goal_packet_diagnostics_require_phase_evidence_and_gates():
    diagnostics = check_document(
        {
            "nornyx": "0.1",
            "project": {"name": "Example"},
            "goals": [
                {
                    "id": "GOAL-999",
                    "goal": "Show hardened diagnostics.",
                    "scope": "docs",
                    "non_goals": [],
                    "validation": [],
                }
            ],
        }
    )
    codes = {d.code for d in diagnostics}
    assert {
        "MISSING_GOAL_PHASE",
        "INVALID_GOAL_SCOPE",
        "MISSING_GOAL_EVIDENCE",
        "MISSING_GOAL_APPROVAL",
        "MISSING_GOAL_STOP_RULES",
    }.issubset(codes)
