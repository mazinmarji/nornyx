# Nornyx v0.5 Graph Validation

## Status

Local v0.5 graph validation surface. These checks are static diagnostics only.
They do not execute graph edges, run adapters, call connectors, call models,
grant approvals, modify files, or deploy.

## Added checks

v0.5 hardens the existing v0.2 graph/contract surface with:

- graph relation source/target consistency for recognized relation names;
- duplicate edge warnings;
- self-edge warnings;
- known reference targets for intent, adapter, connector, and evidence graph
  nodes;
- evidence node checks for missing refs;
- contract auditability warnings when approval, budget, or evidence graph nodes
  are not represented in contract nodes.

## Recognized relation pairs

The checker recognizes a small static relation vocabulary, including:

```text
authorizes_context_for
bounds
depends_on
gates
gates_promotion
governs
must_produce
produces
requires_evidence
scopes_context
uses_connector
validates
validates_contract
```

Known relation names have source/target kind rules. For example, `governs`
must originate from a `policy` node, and `must_produce` should target an
`evidence` or `artifact` node.

Custom relation names are allowed but produce warnings so profile or adapter
authors can document them explicitly.

## Evidence completeness

Evidence graph refs can point to:

- entries in `evidence.required`;
- named evidence flow steps in `harnesses[].flow`.

Contracts that omit evidence nodes are still accepted, but the checker warns
because the graph is less auditable.

## Graph vocabulary and cycle diagnostics (ADR-0046, issue #104)

The checks above are applied against an explicit vocabulary:

- **Node kinds.** The core kinds are `adapter, agent, approval, artifact, budget,
  connector, context, contract, eval, evidence, goal, harness, intent, module,
  policy, profile, project, skill, trace`. The active profile's
  `graph.node_kinds` add to that set; a profile never removes a core kind. Any
  other kind warns `UNKNOWN_GRAPH_NODE_KIND`, and edges touching such a node are
  not pair-checked (the node diagnostic covers them). World-model entities do
  not belong in the contract graph; declare a domain kind in a profile if a
  governance relationship genuinely needs it.
- **Relations.** Each profile `graph.relationship_constraints` entry adds
  exactly one permitted `(from_kind, to_kind)` pair to the named relation,
  declaring the relation if it is not a core one. Declared pairs are kept apart
  from the core source/target sets and from each other: declaring
  `policy governs component` does not make `policy governs interface` or
  `component governs agent` legal. Profile-declared relations are pair-checked
  like core ones; `UNKNOWN_GRAPH_RELATION` no longer fires for them.
  `depends_on` matches known kinds only.
- **Refs.** `profile`, `project` and `contract` node refs resolve against
  `project.profile` / `project.profile_pack.name`, `project.name` and
  `contracts[].name` (`UNKNOWN_GRAPH_REF_REFERENCE`, error, as for the other
  in-document kinds). `artifact`, `module` and profile-declared kinds name
  things outside the document, so they must carry a `ref`
  (`GRAPH_NODE_WITHOUT_REF`, warning); path existence is not checked.
- **Cycles.** `GRAPH_CYCLE` warns once per strongly connected component of the
  **dependency** edges (`depends_on`): a cycle there is a circular dependency,
  the same defect the governance checks report for evidence dependencies and
  exception renewals. Edges are used exactly as declared, never reversed or
  renamed, and control, validation, production and audit relations do not take
  part, because their directions are not comparable and the language does not
  require them to form one global DAG. Self-edges keep `GRAPH_SELF_EDGE`.

The new codes are warnings so an existing contract keeps its exit status;
`nornyx check --strict` promotes them. `nornyx check`, the agentic-network
commands and `nornyx.agentic.load_authorizer` compose the document's governance
first (`governance.check_document_with_governance`) and check the graph against
the composed profile's vocabulary, so project- and organisation-supplied packs
extend it identically wherever a verdict is produced. Other callers resolve
`project.profile` against the built-in profiles; when that names no built-in
profile the checker says so (`GRAPH_VOCABULARY_PROFILE_UNRESOLVED`, warning),
and when the registry cannot be consulted at all it refuses to pass the graph
on core semantics (`GRAPH_VOCABULARY_UNAVAILABLE`, error).

## Non-goals

v0.5 does not add:

- graph execution;
- scheduling;
- graph traversal side effects;
- live connectors;
- automatic approvals;
- self-modification;
- production deployment.

Future maturity bands can tighten these diagnostics into release gates after
profile and adapter conformance rules are stable.
