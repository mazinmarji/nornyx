from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

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
    "governed_package",
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
    project = doc.get("project") if isinstance(doc.get("project"), dict) else {}
    profile_targets: set[str] = set()
    if _is_non_empty_string(project.get("profile")):
        profile_targets.add(str(project["profile"]))
    profile_pack = project.get("profile_pack")
    if isinstance(profile_pack, dict) and _is_non_empty_string(profile_pack.get("name")):
        profile_targets.add(str(profile_pack["name"]))
    targets["profile"] = profile_targets
    targets["project"] = {str(project["name"])} if _is_non_empty_string(project.get("name")) else set()
    targets["contract"] = set(_named_mapping(doc.get("contracts")))
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


def _relation_allows(allowed: set[str] | frozenset[str], kind: str) -> bool:
    return "*" in allowed or kind in allowed


# Graph node kinds the core language defines. A node whose kind is outside this
# set and outside the active profile's ``graph.node_kinds`` is not a governance
# concept the checker can reason about, so it is reported (as a warning, so an
# existing contract keeps its exit status; ``--strict`` promotes it).
CORE_GRAPH_NODE_KINDS: frozenset[str] = frozenset(
    {
        "adapter",
        "agent",
        "approval",
        "artifact",
        "budget",
        "connector",
        "context",
        "contract",
        "eval",
        "evidence",
        "goal",
        "harness",
        "intent",
        "module",
        "policy",
        "profile",
        "project",
        "skill",
        "trace",
    }
)

# Relations whose acyclicity the checker enforces. Only ``depends_on`` declares
# a dependency: a cycle over it is a circular dependency, the same defect
# ``governance/structural.py`` reports for evidence dependencies and exception
# renewals. The other relations are control, validation, production and audit
# statements whose directions are not comparable with one another, so a loop
# that mixes them is not a dependency cycle and is not reported (ADR-0046,
# revision 2).
DEPENDENCY_GRAPH_RELATIONS: frozenset[str] = frozenset({"depends_on"})


@dataclass(frozen=True)
class GraphRelationRule:
    """Allowed source/target kinds for one relation.

    ``allowed_from`` / ``allowed_to`` carry the core declaration exactly as
    ``GRAPH_RELATION_RULES`` states it: a source set and a target set, where
    ``*`` means any known kind. ``pairs`` carries profile-declared
    ``(from_kind, to_kind)`` pairs verbatim. A pair is allowed when the core
    declaration admits it or it is one of the exact declared pairs; declared
    pairs never combine with each other or with the core sets.
    """

    allowed_from: frozenset[str] = frozenset()
    allowed_to: frozenset[str] = frozenset()
    pairs: frozenset[tuple[str, str]] = frozenset()

    def allows(self, source_kind: str, target_kind: str) -> bool:
        if (
            self.allowed_from
            and self.allowed_to
            and _relation_allows(self.allowed_from, source_kind)
            and _relation_allows(self.allowed_to, target_kind)
        ):
            return True
        return (source_kind, target_kind) in self.pairs


@dataclass(frozen=True)
class GraphVocabulary:
    """The node kinds and relation rules one ``graph:`` block is checked against.

    ``core_graph_vocabulary()`` is the language's own vocabulary. A profile pack
    extends it: its ``graph.node_kinds`` add kinds and each
    ``graph.relationship_constraints`` entry adds exactly one permitted
    ``(from_kind, to_kind)`` pair to the named relation, declaring the relation
    when the verb is not a core one. Profiles only ever widen the vocabulary by
    the exact pairs they declare; a profile cannot remove a core kind or narrow
    a core relation.

    ``resolution`` records how the vocabulary was obtained: ``core`` (no profile
    requested), ``profile`` (a composed or built-in profile applied),
    ``unresolved`` (``project.profile`` names no known profile) or
    ``unavailable`` (the profile registry could not be consulted). The checker
    reports the last two, so core-only checking is never mistaken for profile
    checking.
    """

    node_kinds: frozenset[str]
    relation_rules: Mapping[str, GraphRelationRule]
    source: str = "core"
    resolution: str = "core"
    detail: str = ""


def core_graph_vocabulary() -> GraphVocabulary:
    return GraphVocabulary(
        node_kinds=CORE_GRAPH_NODE_KINDS,
        relation_rules={
            relation: GraphRelationRule(frozenset(allowed_from), frozenset(allowed_to))
            for relation, (allowed_from, allowed_to) in GRAPH_RELATION_RULES.items()
        },
    )


def graph_vocabulary_for_profile(profile_graph: Any, *, profile_id: str) -> GraphVocabulary:
    """Extend the core vocabulary with one profile pack's ``graph`` declaration."""
    base = core_graph_vocabulary()
    source = f"core+profile:{profile_id}"
    if not isinstance(profile_graph, Mapping):
        return GraphVocabulary(base.node_kinds, base.relation_rules, source, "profile")
    kinds = set(base.node_kinds)
    for kind in profile_graph.get("node_kinds") or []:
        if _is_non_empty_string(kind) and str(kind).strip() != "*":
            kinds.add(str(kind).strip())
    declared: dict[str, set[tuple[str, str]]] = {}
    for constraint in profile_graph.get("relationship_constraints") or []:
        if not isinstance(constraint, Mapping):
            continue
        from_kind = constraint.get("from_kind")
        relation = constraint.get("relation")
        to_kind = constraint.get("to_kind")
        if not all(_is_non_empty_string(value) for value in (from_kind, relation, to_kind)):
            continue
        if "*" in (str(from_kind).strip(), str(to_kind).strip()):
            # Only the core table may say "any kind"; a profile widens by exact
            # pairs, so a wildcard endpoint is not a declaration it can make.
            continue
        declared.setdefault(str(relation), set()).add((str(from_kind), str(to_kind)))
        kinds.add(str(from_kind))
        kinds.add(str(to_kind))
    rules = dict(base.relation_rules)
    for relation, pairs in declared.items():
        core_rule = base.relation_rules.get(relation, GraphRelationRule())
        rules[relation] = GraphRelationRule(
            core_rule.allowed_from, core_rule.allowed_to, frozenset(pairs)
        )
    return GraphVocabulary(frozenset(kinds), rules, source, "profile")


def graph_vocabulary_for_profile_pack(profile: Any) -> GraphVocabulary:
    """Vocabulary for a loaded profile pack (anything exposing ``raw`` and ``id``)."""
    raw = getattr(profile, "raw", None)
    graph = raw.get("graph") if isinstance(raw, Mapping) else None
    return graph_vocabulary_for_profile(graph, profile_id=str(getattr(profile, "id", "?")))


def graph_vocabulary_for_document(doc: Mapping[str, Any]) -> GraphVocabulary:
    """Best-effort vocabulary when no composed profile was supplied.

    Resolves ``project.profile`` against the built-in profile registry only
    (packaged data, no filesystem lookup). Project- and organisation-supplied
    packs are known to callers that compose the document's governance first
    and pass the composed vocabulary explicitly. The result says what happened:
    a profile that is not built in yields ``resolution="unresolved"`` and a
    registry that cannot be consulted yields ``resolution="unavailable"``;
    neither is silently reported as core checking.
    """
    project = doc.get("project")
    profile_name = project.get("profile") if isinstance(project, Mapping) else None
    core = core_graph_vocabulary()
    if not _is_non_empty_string(profile_name):
        return core
    profile_name = str(profile_name)
    try:
        from .governance.errors import GovernanceError
        from .profiles import builtin_profile_registry

        registry = builtin_profile_registry()
    except Exception as exc:  # noqa: BLE001 - surfaced as an error diagnostic, never hidden
        return GraphVocabulary(
            core.node_kinds, core.relation_rules, "core", "unavailable", f"{type(exc).__name__}: {exc}"
        )
    try:
        profile = registry.resolve_profile(profile_name)
    except GovernanceError as exc:
        if {item.code for item in exc.diagnostics} == {"PACK_NOT_FOUND"}:
            return GraphVocabulary(core.node_kinds, core.relation_rules, "core", "unresolved", profile_name)
        return GraphVocabulary(core.node_kinds, core.relation_rules, "core", "unavailable", str(exc))
    return graph_vocabulary_for_profile_pack(profile)


def _dependency_cycles(edges: list[tuple[str, str, str]]) -> list[list[str]]:
    """Strongly connected components of size > 1 among dependency edges.

    ``edges`` are ``(from, to, relation)`` triples exactly as declared. Only
    relations in ``DEPENDENCY_GRAPH_RELATIONS`` take part, edges are never
    reversed or renamed, and self-edges are ignored because they have their
    own diagnostic. The result is deterministic: components and their members
    are sorted.
    """
    adjacency: dict[str, set[str]] = {}
    for source, target, relation in edges:
        if relation not in DEPENDENCY_GRAPH_RELATIONS or source == target:
            continue
        adjacency.setdefault(source, set()).add(target)
        adjacency.setdefault(target, set())
    # Iterative Tarjan: a checker must return diagnostics, never raise, so no
    # recursion depth is tied to the size of the contract graph.
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components: list[list[str]] = []
    counter = 0
    for root in sorted(adjacency):
        if root in index:
            continue
        work: list[tuple[str, list[str], int]] = [(root, sorted(adjacency[root]), 0)]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            node, successors, position = work[-1]
            if position < len(successors):
                work[-1] = (node, successors, position + 1)
                successor = successors[position]
                if successor not in index:
                    index[successor] = low[successor] = counter
                    counter += 1
                    stack.append(successor)
                    on_stack.add(successor)
                    work.append((successor, sorted(adjacency[successor]), 0))
                elif successor in on_stack:
                    low[node] = min(low[node], index[successor])
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                component: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                if len(component) > 1:
                    components.append(sorted(component))
    return sorted(components)


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


def _validate_graph_contract_model(
    diagnostics: list[Diagnostic],
    doc: dict[str, Any],
    vocabulary: GraphVocabulary | None = None,
) -> None:
    if vocabulary is None:
        vocabulary = graph_vocabulary_for_document(doc)
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
        if vocabulary.resolution == "unresolved":
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "GRAPH_VOCABULARY_PROFILE_UNRESOLVED",
                    f"project.profile {vocabulary.detail!r} is not a known profile; "
                    "the graph was checked against the core vocabulary only",
                    "project.profile",
                    "Compose the document's governance (as `nornyx check` does) so a project or "
                    "organisation profile's graph.node_kinds and relationship_constraints apply.",
                )
            )
        elif vocabulary.resolution == "unavailable":
            diagnostics.append(
                Diagnostic(
                    "error",
                    "GRAPH_VOCABULARY_UNAVAILABLE",
                    "the profile registry could not be consulted for project.profile: "
                    + vocabulary.detail,
                    "project.profile",
                    "Profile graph semantics were requested but could not be applied; "
                    "the graph is not accepted on core semantics alone.",
                )
            )
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
            if kind and kind not in vocabulary.node_kinds:
                diagnostics.append(
                    Diagnostic(
                        "warning",
                        "UNKNOWN_GRAPH_NODE_KIND",
                        f"graph.nodes[{index}].kind {kind!r} is not a core graph kind"
                        + (
                            " or a kind declared by the active profile"
                            if vocabulary.source != "core"
                            else ""
                        ),
                        f"{path_prefix}.kind",
                        "Graph nodes name governance concepts (intent, agent, policy, approval, evidence, ...). "
                        "Declare a domain kind in the active profile's `graph.node_kinds`; do not put "
                        "world-model entities in the contract graph.",
                    )
                )
            ref = node.get("ref")
            if _is_non_empty_string(node_id) and _is_non_empty_string(ref):
                node_refs[str(node_id)] = str(ref)
            if (
                kind
                and kind in vocabulary.node_kinds
                and kind not in graph_ref_targets
                and not _is_non_empty_string(ref)
            ):
                diagnostics.append(
                    Diagnostic(
                        "warning",
                        "GRAPH_NODE_WITHOUT_REF",
                        f"graph.nodes[{index}] {kind} node has no ref",
                        f"{path_prefix}.ref",
                        f"A {kind} node names something outside this document; give it a `ref` so the graph stays auditable.",
                    )
                )
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
                rule = vocabulary.relation_rules.get(relation)
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
                elif source_kind in vocabulary.node_kinds and target_kind in vocabulary.node_kinds:
                    # An unknown kind already carries UNKNOWN_GRAPH_NODE_KIND; do not
                    # turn it into a pair error as well.
                    if not rule.allows(source_kind, target_kind):
                        diagnostics.append(
                            Diagnostic(
                                "error",
                                "INVALID_GRAPH_RELATION_PAIR",
                                f"Relation {relation!r} does not match {source_kind!r} -> {target_kind!r}",
                                f"{path_prefix}.relation",
                                "Use a relation whose source and target kinds match the declared graph nodes.",
                            )
                        )
        for component in _dependency_cycles(
            [
                (str(edge["from"]), str(edge["to"]), str(edge.get("relation", "")))
                for edge in edges
                if isinstance(edge, dict)
                and _is_non_empty_string(edge.get("from"))
                and _is_non_empty_string(edge.get("to"))
                and str(edge["from"]) in node_ids
                and str(edge["to"]) in node_ids
            ]
        ):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "GRAPH_CYCLE",
                    "graph.edges form a dependency cycle (depends_on) among nodes: " + ", ".join(component),
                    "graph.edges",
                    "A depends_on cycle is a circular dependency; break it, or state the relationship "
                    "with a directed control relation instead.",
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


def _check_policy_rule_vocabulary(diagnostics: list[Diagnostic], doc: dict[str, Any]) -> None:
    """Warn when a `policies.deny` rule name is unknown to the policy matcher.

    `deny` accepts free text. The matcher only ever considers names containing
    one of `EVALUATED_DENY_RULE_NAME_TOKENS`, so a name outside that vocabulary
    is stored, rendered, reviewed -- and evaluated by nothing. That reads as a
    governed control while being inert, which is worse than an omission,
    because an omission is visible.

    This is a warning, not an error: existing contracts may already carry such
    names, and failing them by default would be a breaking change. `nornyx
    check --strict` promotes it.

    Scope note: this diagnoses the rule *name* only. It deliberately says
    nothing about whether an in-vocabulary rule matches any particular declared
    flow -- that depends on the flow's step text and is not decided here.
    """
    from .policy_runtime import (
        EVALUATED_DENY_RULE_NAME_TOKENS,
        is_evaluated_deny_rule_name,
        normalize_policy_rules,
    )

    known = ", ".join(sorted(set(EVALUATED_DENY_RULE_NAME_TOKENS)))
    for policy in doc.get("policies", []) or []:
        if not isinstance(policy, dict):
            continue
        name = policy.get("name") or "<unnamed>"
        for rule in normalize_policy_rules(policy)["deny"]:
            if is_evaluated_deny_rule_name(rule):
                continue
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "UNKNOWN_POLICY_RULE",
                    (
                        f"`{rule}` is outside the evaluated policy-rule vocabulary. "
                        "It is accepted as text, but Nornyx does not evaluate this "
                        "rule name under the current policy matcher."
                    ),
                    f"policies.{name}.deny",
                    (
                        f"Recognized rule-name tokens: {known}. If no evaluated rule "
                        "fits, keep the instruction as guidance rather than encoding "
                        "it here. Use `nornyx check --strict` to fail on unknown names."
                    ),
                )
            )


def check_document(
    doc: dict[str, Any],
    *,
    graph_vocabulary: GraphVocabulary | None = None,
) -> list[Diagnostic]:
    """Validate one parsed ``.nyx`` document.

    ``graph_vocabulary`` is the node-kind/relation vocabulary the ``graph:``
    block is checked against. Callers that have composed the document's
    governance pass ``graph_vocabulary_for_profile_pack(composition.profile)``;
    otherwise the checker resolves ``project.profile`` against the built-in
    profiles and falls back to the core vocabulary.
    """
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

    _check_policy_rule_vocabulary(diagnostics, doc)

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


    _validate_graph_contract_model(diagnostics, doc, graph_vocabulary)

    if "governed_package" in doc:
        from .governed_package import validate_governed_package

        package = doc.get("governed_package")
        if isinstance(package, dict):
            diagnostics.extend(validate_governed_package(package))
        else:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "INVALID_GOVERNED_PACKAGE",
                    "governed_package must be a mapping",
                    "governed_package",
                )
            )

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
