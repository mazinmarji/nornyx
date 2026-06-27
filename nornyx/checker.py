from __future__ import annotations

from typing import Any
from .errors import Diagnostic

REQUIRED_TOP_LEVEL = ["nornyx", "project"]
NAMED_LIST_BLOCKS = [
    "intents",
    "contexts",
    "skills",
    "policies",
    "agents",
    "harnesses",
    "traces",
    "evals",
    "approvals",
    "budgets",
]
SINGULAR_BLOCK_NAMES = {
    "policies": "policy",
    "harnesses": "harness",
    "traces": "trace",
    "evals": "eval",
}
CORE_LIST_BLOCKS = [
    *NAMED_LIST_BLOCKS,
    "goals",
]

CORE_MAPPING_BLOCKS = ["constitution", "evidence"]

CORE_TOP_LEVEL_BLOCKS = [
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

EXTENSION_TOP_LEVEL_BLOCKS = [
    "experimental",
    "graph",
    "contracts",
    "adapters",
    "connectors",
    "guardrails",
    "capabilities",
    "incidents",
    "containment",
    "supply_chain",
]


def _names(items: Any) -> set[str]:
    if not isinstance(items, list):
        return set()
    return {item.get("name") for item in items if isinstance(item, dict) and item.get("name")}


def _path(block: str, index: int, field: str | None = None) -> str:
    base = f"{block}[{index}]"
    return f"{base}.{field}" if field else base


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def _named_mapping(items: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        return {}
    return {
        str(item["name"]): item
        for item in items
        if isinstance(item, dict) and _is_non_empty_string(item.get("name"))
    }


def _goal_ids(items: Any) -> set[str]:
    if not isinstance(items, list):
        return set()
    return {
        str(item["id"])
        for item in items
        if isinstance(item, dict) and _is_non_empty_string(item.get("id"))
    }


def _evidence_targets(doc: dict[str, Any]) -> set[str]:
    targets: set[str] = set()
    evidence = doc.get("evidence")
    if isinstance(evidence, dict):
        required = evidence.get("required")
        if isinstance(required, list):
            targets.update(str(item) for item in required if _is_non_empty_string(item))
    for harness in doc.get("harnesses", []) or []:
        if not isinstance(harness, dict):
            continue
        for step in harness.get("flow", []) or []:
            if isinstance(step, dict) and _is_non_empty_string(step.get("evidence")):
                targets.add(str(step["evidence"]))
    return targets


def _graph_ref_targets(doc: dict[str, Any]) -> dict[str, set[str]]:
    named_blocks = {
        "intent": "intents",
        "context": "contexts",
        "skill": "skills",
        "policy": "policies",
        "agent": "agents",
        "harness": "harnesses",
        "trace": "traces",
        "eval": "evals",
        "approval": "approvals",
        "budget": "budgets",
        "adapter": "adapters",
        "connector": "connectors",
    }
    targets = {
        kind: set(_named_mapping(doc.get(block)))
        for kind, block in named_blocks.items()
    }
    targets["goal"] = _goal_ids(doc.get("goals"))
    targets["evidence"] = _evidence_targets(doc)
    return targets


GRAPH_RELATION_RULES: dict[str, tuple[set[str], set[str]]] = {
    "authorizes_context_for": ({"context"}, {"agent", "harness", "adapter"}),
    "bounded_by": ({"goal", "agent", "harness", "artifact", "module"}, {"budget"}),
    "bounds": ({"budget"}, {"goal", "agent", "harness", "adapter", "connector"}),
    "depends_on": ({"*"}, {"*"}),
    "gated_by": ({"goal", "agent", "harness", "artifact", "module"}, {"approval"}),
    "gates": ({"approval"}, {"goal", "agent", "harness", "adapter", "connector"}),
    "gates_promotion": ({"approval"}, {"goal", "adapter", "connector"}),
    "governs": ({"policy"}, {"agent", "harness", "adapter", "connector", "goal"}),
    "governed_by": ({"agent", "harness", "artifact", "module", "goal"}, {"policy"}),
    "has_skill": ({"agent"}, {"skill"}),
    "must_produce": ({"agent", "harness", "adapter", "eval"}, {"evidence", "artifact"}),
    "produces": ({"agent", "harness", "adapter", "eval"}, {"evidence", "artifact"}),
    "produces_artifact": ({"agent", "harness", "goal"}, {"artifact", "module"}),
    "produces_evidence": ({"agent", "harness", "eval", "goal"}, {"evidence"}),
    "records_trace": ({"agent", "harness", "eval", "goal"}, {"trace"}),
    "requires_evidence": ({"goal", "contract", "adapter", "harness"}, {"evidence"}),
    "scopes_context": ({"profile", "project", "adapter"}, {"context"}),
    "satisfies_intent": ({"goal", "artifact", "module"}, {"intent"}),
    "uses_connector": ({"adapter", "harness", "agent"}, {"connector"}),
    "uses_context": ({"agent", "harness", "eval", "goal"}, {"context"}),
    "validates": ({"eval"}, {"goal", "contract", "adapter", "policy"}),
    "validated_by": ({"goal", "contract", "adapter", "policy", "artifact", "module"}, {"eval"}),
    "validates_contract": ({"eval"}, {"contract", "adapter"}),
}


def _relation_allows(allowed: set[str], kind: str) -> bool:
    return "*" in allowed or kind in allowed


def _validate_named_entries(
    diagnostics: list[Diagnostic],
    doc: dict[str, Any],
    block: str,
) -> None:
    for index, item in enumerate(doc.get(block, []) or []):
        if not isinstance(item, dict):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "INVALID_BLOCK_ENTRY",
                    f"{block}[{index}] must be a mapping",
                    _path(block, index),
                    f"Use an object with at least `name:` for `{block}` entries.",
                )
            )
            continue
        if not _is_non_empty_string(item.get("name")):
            singular = SINGULAR_BLOCK_NAMES.get(block, block.removesuffix("s"))
            diagnostics.append(
                Diagnostic(
                    "error",
                    f"MISSING_{singular.upper()}_NAME",
                    f"{block}[{index}].name is required",
                    _path(block, index, "name"),
                    f"Add a stable name so other blocks can reference this `{singular}`.",
                )
            )


def _validate_string_list_field(
    diagnostics: list[Diagnostic],
    code_prefix: str,
    path_prefix: str,
    data: dict[str, Any],
    field: str,
    *,
    required: bool,
) -> None:
    value = data.get(field)
    if value is None:
        if required:
            diagnostics.append(
                Diagnostic(
                    "error",
                    f"MISSING_{code_prefix}_{field.upper()}",
                    f"{path_prefix}.{field} is required",
                    f"{path_prefix}.{field}",
                    f"Add `{field}:` with at least one entry.",
                )
            )
        return
    if (
        not isinstance(value, list)
        or (required and not value)
        or not all(_is_non_empty_string(item) for item in value)
    ):
        diagnostics.append(
            Diagnostic(
                "error",
                f"INVALID_{code_prefix}_{field.upper()}",
                f"{path_prefix}.{field} must be a list of non-empty strings",
                f"{path_prefix}.{field}",
            )
        )


def _validate_graph_contract_model(diagnostics: list[Diagnostic], doc: dict[str, Any]) -> None:
    graph = doc.get("graph")
    if graph is not None and not isinstance(graph, dict):
        diagnostics.append(
            Diagnostic(
                "error",
                "INVALID_GRAPH_BLOCK",
                "graph must be a mapping",
                "graph",
                "Use `graph:` with `nodes:` and `edges:` lists.",
            )
        )
        graph = None

    node_ids: set[str] = set()
    node_kinds: dict[str, str] = {}
    node_refs: dict[str, str] = {}
    graph_ref_targets = _graph_ref_targets(doc)
    if isinstance(graph, dict):
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        if not isinstance(nodes, list):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "INVALID_GRAPH_NODES",
                    "graph.nodes must be a list",
                    "graph.nodes",
                    "Use `nodes:` followed by node mappings with `id:` and `kind:`.",
                )
            )
            nodes = []
        if not isinstance(edges, list):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "INVALID_GRAPH_EDGES",
                    "graph.edges must be a list",
                    "graph.edges",
                    "Use `edges:` followed by edge mappings with `from:` and `to:`.",
                )
            )
            edges = []

        for index, node in enumerate(nodes):
            path_prefix = _path("graph.nodes", index)
            if not isinstance(node, dict):
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "INVALID_GRAPH_NODE",
                        f"graph.nodes[{index}] must be a mapping",
                        path_prefix,
                    )
                )
                continue
            node_id = node.get("id")
            if not _is_non_empty_string(node_id):
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "MISSING_GRAPH_NODE_ID",
                        f"graph.nodes[{index}].id is required",
                        f"{path_prefix}.id",
                    )
                )
            elif str(node_id) in node_ids:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "DUPLICATE_GRAPH_NODE_ID",
                        f"Graph node id {node_id!r} is duplicated",
                        f"{path_prefix}.id",
                    )
                )
            else:
                node_id_text = str(node_id)
                node_ids.add(node_id_text)
            if not _is_non_empty_string(node.get("kind")):
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "MISSING_GRAPH_NODE_KIND",
                        f"graph.nodes[{index}].kind is required",
                        f"{path_prefix}.kind",
                    )
                )
            kind = str(node.get("kind", "")).strip()
            if _is_non_empty_string(node_id) and kind:
                node_kinds[str(node_id)] = kind
            ref = node.get("ref")
            if _is_non_empty_string(node_id) and _is_non_empty_string(ref):
                node_refs[str(node_id)] = str(ref)
            if _is_non_empty_string(ref) and kind in graph_ref_targets and str(ref) not in graph_ref_targets[kind]:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "UNKNOWN_GRAPH_REF_REFERENCE",
                        f"graph.nodes[{index}].ref references unknown {kind} {ref!r}",
                        f"{path_prefix}.ref",
                        f"Define the referenced `{kind}` or remove the graph node ref.",
                    )
                )
            if kind == "evidence" and not _is_non_empty_string(ref):
                diagnostics.append(
                    Diagnostic(
                        "warning",
                        "GRAPH_EVIDENCE_NODE_WITHOUT_REF",
                        f"graph.nodes[{index}] evidence node has no ref",
                        f"{path_prefix}.ref",
                        "Reference an evidence flow step or evidence.required entry so graph evidence is auditable.",
                    )
                )

        seen_edges: set[tuple[str, str, str]] = set()
        for index, edge in enumerate(edges):
            path_prefix = _path("graph.edges", index)
            if not isinstance(edge, dict):
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "INVALID_GRAPH_EDGE",
                        f"graph.edges[{index}] must be a mapping",
                        path_prefix,
                    )
                )
                continue
            from_value = str(edge.get("from")) if _is_non_empty_string(edge.get("from")) else ""
            to_value = str(edge.get("to")) if _is_non_empty_string(edge.get("to")) else ""
            relation = str(edge.get("relation")) if _is_non_empty_string(edge.get("relation")) else ""
            if from_value and to_value and relation:
                edge_key = (from_value, to_value, relation)
                if edge_key in seen_edges:
                    diagnostics.append(
                        Diagnostic(
                            "warning",
                            "DUPLICATE_GRAPH_EDGE",
                            f"graph.edges[{index}] duplicates edge {from_value!r} -> {to_value!r} with relation {relation!r}",
                            path_prefix,
                            "Remove duplicate graph edges to keep the semantic graph unambiguous.",
                        )
                    )
                seen_edges.add(edge_key)
            if from_value and to_value and from_value == to_value:
                diagnostics.append(
                    Diagnostic(
                        "warning",
                        "GRAPH_SELF_EDGE",
                        f"graph.edges[{index}] points from and to the same node",
                        path_prefix,
                        "Use self-edges only when the relation is intentional and documented.",
                    )
                )
            for field in ["from", "to"]:
                value = edge.get(field)
                if not _is_non_empty_string(value):
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            f"MISSING_GRAPH_EDGE_{field.upper()}",
                            f"graph.edges[{index}].{field} is required",
                            f"{path_prefix}.{field}",
                        )
                    )
                elif str(value) not in node_ids:
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "UNKNOWN_GRAPH_NODE_REFERENCE",
                            f"graph.edges[{index}].{field} references unknown node {value!r}",
                            f"{path_prefix}.{field}",
                            "Declare the node in `graph.nodes` before referencing it.",
                        )
                    )
            if not _is_non_empty_string(edge.get("relation")):
                diagnostics.append(
                    Diagnostic(
                        "warning",
                        "GRAPH_EDGE_WITHOUT_RELATION",
                        f"graph.edges[{index}] has no relation",
                        f"{path_prefix}.relation",
                    )
                )
            elif from_value in node_kinds and to_value in node_kinds:
                source_kind = node_kinds[from_value]
                target_kind = node_kinds[to_value]
                rule = GRAPH_RELATION_RULES.get(relation)
                if rule is None:
                    diagnostics.append(
                        Diagnostic(
                            "warning",
                            "UNKNOWN_GRAPH_RELATION",
                            f"graph.edges[{index}].relation {relation!r} is not a recognized v0.5 relation",
                            f"{path_prefix}.relation",
                            "Keep custom relations documented under a profile or adapter contract.",
                        )
                    )
                else:
                    allowed_from, allowed_to = rule
                    if not _relation_allows(allowed_from, source_kind) or not _relation_allows(allowed_to, target_kind):
                        diagnostics.append(
                            Diagnostic(
                                "error",
                                "INVALID_GRAPH_RELATION_PAIR",
                                f"Relation {relation!r} does not match {source_kind!r} -> {target_kind!r}",
                                f"{path_prefix}.relation",
                                "Use a relation whose source and target kinds match the declared graph nodes.",
                            )
                        )

    contracts = doc.get("contracts")
    if contracts is None:
        return
    if not isinstance(contracts, list):
        diagnostics.append(
            Diagnostic(
                "error",
                "INVALID_CONTRACTS_BLOCK",
                "contracts must be a list",
                "contracts",
                "Use `contracts:` followed by named contract mappings.",
            )
        )
        return

    approvals = _named_mapping(doc.get("approvals"))
    budgets = _named_mapping(doc.get("budgets"))
    for index, contract in enumerate(contracts):
        path_prefix = _path("contracts", index)
        if not isinstance(contract, dict):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "INVALID_CONTRACT_ENTRY",
                    f"contracts[{index}] must be a mapping",
                    path_prefix,
                )
            )
            continue
        if not _is_non_empty_string(contract.get("name")):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "MISSING_CONTRACT_NAME",
                    f"contracts[{index}].name is required",
                    f"{path_prefix}.name",
                )
            )
        contract_node_refs: set[str] = set()
        for field in ["nodes", "edges"]:
            value = contract.get(field)
            if value is None:
                continue
            if not isinstance(value, list) or not all(_is_non_empty_string(item) for item in value):
                diagnostics.append(
                    Diagnostic(
                        "error",
                        f"INVALID_CONTRACT_{field.upper()}",
                        f"contracts[{index}].{field} must be a list of node ids",
                        f"{path_prefix}.{field}",
                    )
                )
                continue
            if field == "nodes":
                contract_node_refs.update(str(item) for item in value)
            if node_ids:
                for item in value:
                    if str(item) not in node_ids:
                        diagnostics.append(
                            Diagnostic(
                                "error",
                                "UNKNOWN_CONTRACT_GRAPH_REFERENCE",
                                f"Contract {contract.get('name', '<unnamed>')} references unknown graph node {item!r}",
                                f"{path_prefix}.{field}",
                            )
                        )
        approval = contract.get("approval")
        if approval and str(approval) not in approvals:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "UNKNOWN_CONTRACT_APPROVAL_REFERENCE",
                    f"Contract {contract.get('name', '<unnamed>')} references unknown approval {approval!r}",
                    f"{path_prefix}.approval",
                )
            )
        elif approval and node_ids:
            approval_covered = any(
                node_id in contract_node_refs
                and node_kinds.get(node_id) == "approval"
                and node_refs.get(node_id) == str(approval)
                for node_id in node_ids
            )
            if not approval_covered:
                diagnostics.append(
                    Diagnostic(
                        "warning",
                        "CONTRACT_APPROVAL_NOT_IN_GRAPH",
                        f"Contract {contract.get('name', '<unnamed>')} approval {approval!r} is not represented by a contract graph node",
                        f"{path_prefix}.approval",
                        "Add an approval graph node to the contract nodes list for stronger auditability.",
                    )
                )
        budget = contract.get("budget")
        if budget and str(budget) not in budgets:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "UNKNOWN_CONTRACT_BUDGET_REFERENCE",
                    f"Contract {contract.get('name', '<unnamed>')} references unknown budget {budget!r}",
                    f"{path_prefix}.budget",
                )
            )
        elif budget and node_ids:
            budget_covered = any(
                node_id in contract_node_refs
                and node_kinds.get(node_id) == "budget"
                and node_refs.get(node_id) == str(budget)
                for node_id in node_ids
            )
            if not budget_covered:
                diagnostics.append(
                    Diagnostic(
                        "warning",
                        "CONTRACT_BUDGET_NOT_IN_GRAPH",
                        f"Contract {contract.get('name', '<unnamed>')} budget {budget!r} is not represented by a contract graph node",
                        f"{path_prefix}.budget",
                        "Add a budget graph node to the contract nodes list for stronger auditability.",
                    )
                )
        if node_ids and not any(node_kinds.get(node_id) == "evidence" for node_id in contract_node_refs):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "CONTRACT_WITHOUT_EVIDENCE_NODE",
                    f"Contract {contract.get('name', '<unnamed>')} has no evidence graph node",
                    f"{path_prefix}.nodes",
                    "Add an evidence node when the contract should prove audit artifacts explicitly.",
                )
            )


def check_document(doc: dict[str, Any]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    for key in REQUIRED_TOP_LEVEL:
        if key not in doc:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "MISSING_TOP_LEVEL_BLOCK",
                    f"Missing required top-level block: {key}",
                    key,
                    f"Add `{key}:` to the .nyx file.",
                )
            )

    version = doc.get("nornyx")
    if version not in {"0.1", 0.1, "0.2", 0.2}:
        diagnostics.append(
            Diagnostic(
                "warning",
                "UNKNOWN_VERSION",
                f"Expected nornyx: '0.1' or '0.2', got {version!r}",
                "nornyx",
                "Use `nornyx: \"0.1\"` for the scaffold or `nornyx: \"0.2\"` for graph contracts.",
            )
        )

    project = doc.get("project")
    if isinstance(project, dict):
        if not project.get("name"):
            diagnostics.append(
                Diagnostic("error", "MISSING_PROJECT_NAME", "project.name is required", "project.name")
            )
    elif "project" in doc:
        diagnostics.append(Diagnostic("error", "INVALID_PROJECT", "project must be a mapping"))

    for block in CORE_LIST_BLOCKS:
        if block in doc and not isinstance(doc[block], list):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "INVALID_BLOCK_TYPE",
                    f"{block} must be a list",
                    block,
                    f"Use `{block}:` followed by `- ...` entries.",
                )
            )

    for block in CORE_MAPPING_BLOCKS:
        if block in doc and not isinstance(doc[block], dict):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "INVALID_MAPPING_BLOCK",
                    f"{block} must be a mapping",
                    block,
                    f"Use `{block}:` followed by key/value fields.",
                )
            )

    for block in NAMED_LIST_BLOCKS:
        _validate_named_entries(diagnostics, doc, block)

    skill_names = _names(doc.get("skills"))
    policy_names = _names(doc.get("policies"))
    agent_names = _names(doc.get("agents"))
    context_names = _names(doc.get("contexts"))
    eval_names = _names(doc.get("evals"))

    for agent in doc.get("agents", []) or []:
        if not isinstance(agent, dict):
            diagnostics.append(Diagnostic("error", "INVALID_AGENT", "agent entries must be mappings"))
            continue
        name = agent.get("name")
        if not name:
            continue
        for skill in agent.get("skills", []) or []:
            if skill not in skill_names:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "UNKNOWN_SKILL_REFERENCE",
                        f"Agent {name} references unknown skill {skill!r}",
                        f"agents.{name}.skills",
                        "Define the skill in the `skills` block or remove the reference.",
                    )
                )
        policy = agent.get("policy")
        if policy and policy not in policy_names:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "UNKNOWN_POLICY_REFERENCE",
                    f"Agent {name} references unknown policy {policy!r}",
                    f"agents.{name}.policy",
                )
            )

    for harness in doc.get("harnesses", []) or []:
        if not isinstance(harness, dict):
            diagnostics.append(Diagnostic("error", "INVALID_HARNESS", "harness entries must be mappings"))
            continue
        hname = harness.get("name", "<unnamed>")
        context = harness.get("context")
        if context and context not in context_names:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "UNKNOWN_CONTEXT_REFERENCE",
                    f"Harness {hname} references unknown context {context!r}",
                    f"harnesses.{hname}.context",
                    "Define the context in the `contexts` block or update the harness reference.",
                )
            )
        if not harness.get("flow"):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "HARNESS_WITHOUT_FLOW",
                    f"Harness {hname} has no flow",
                    f"harnesses.{hname}.flow",
                )
            )
        for step in harness.get("flow", []) or []:
            if not isinstance(step, dict):
                diagnostics.append(
                    Diagnostic("error", "INVALID_FLOW_STEP", f"Harness {hname} has invalid flow step")
                )
                continue
            if "agent" in step and step["agent"] not in agent_names:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "UNKNOWN_AGENT_REFERENCE",
                        f"Harness {hname} references unknown agent {step['agent']!r}",
                    )
                )
            if "eval" in step and step["eval"] not in eval_names:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "UNKNOWN_EVAL_REFERENCE",
                        f"Harness {hname} references unknown eval {step['eval']!r}",
                    )
                )

    for ctx in doc.get("contexts", []) or []:
        if not isinstance(ctx, dict):
            continue
        if not ctx.get("include"):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "CONTEXT_WITHOUT_INCLUDE",
                    f"Context {ctx.get('name', '<unnamed>')} has no include patterns",
                )
            )


    _validate_graph_contract_model(diagnostics, doc)

    for goal in doc.get("goals", []) or []:
        if not isinstance(goal, dict):
            diagnostics.append(Diagnostic("error", "INVALID_GOAL", "goal entries must be mappings"))
            continue
        gid = goal.get("id", "<unnamed>")
        path_prefix = f"goals.{gid}"
        if not _is_non_empty_string(goal.get("id")):
            diagnostics.append(Diagnostic("error", "MISSING_GOAL_ID", "goal.id is required"))
        if not _is_non_empty_string(goal.get("phase")):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "MISSING_GOAL_PHASE",
                    f"Goal {gid} must declare a phase",
                    f"{path_prefix}.phase",
                    "Use a stable phase such as `v0.1` so roadmap ordering is reviewable.",
                )
            )
        if not _is_non_empty_string(goal.get("goal")):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "MISSING_GOAL_OUTCOME",
                    f"Goal {gid} must declare a clear `goal` outcome",
                    f"goals.{gid}.goal",
                )
            )
        _validate_string_list_field(diagnostics, "GOAL", path_prefix, goal, "scope", required=True)
        _validate_string_list_field(diagnostics, "GOAL", path_prefix, goal, "non_goals", required=True)
        _validate_string_list_field(diagnostics, "GOAL", path_prefix, goal, "validation", required=True)
        _validate_string_list_field(diagnostics, "GOAL", path_prefix, goal, "stop_rules", required=True)
        if not _is_non_empty_list(goal.get("validation")):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "GOAL_WITHOUT_VALIDATION",
                    f"Goal {gid} has no validation gates",
                    f"goals.{gid}.validation",
                )
            )
        if not _is_non_empty_string(goal.get("evidence")):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "MISSING_GOAL_EVIDENCE",
                    f"Goal {gid} has no evidence path",
                    f"{path_prefix}.evidence",
                )
            )
        if not _is_non_empty_string(goal.get("approval")):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "MISSING_GOAL_APPROVAL",
                    f"Goal {gid} has no approval rule",
                    f"{path_prefix}.approval",
                )
            )

    evidence = doc.get("evidence")
    if evidence and isinstance(evidence, dict):
        required = evidence.get("required", [])
        if not isinstance(required, list):
            diagnostics.append(
                Diagnostic("error", "INVALID_EVIDENCE_REQUIRED", "evidence.required must be a list")
            )

    known = set(CORE_TOP_LEVEL_BLOCKS + EXTENSION_TOP_LEVEL_BLOCKS)
    for key in doc.keys():
        if key not in known:
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "UNKNOWN_TOP_LEVEL_BLOCK",
                    f"Unknown top-level block: {key}",
                    key,
                    "Keep experimental blocks under `experimental:` until the spec stabilizes.",
                )
            )

    return diagnostics


def has_errors(diagnostics: list[Diagnostic]) -> bool:
    return any(d.level == "error" for d in diagnostics)
