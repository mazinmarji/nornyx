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
