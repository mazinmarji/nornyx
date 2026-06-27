# Nornyx Language Specification v0.1

## Status

Frozen v0.1 core scaffold. v0.1 uses a YAML-compatible syntax to keep early effort focused on control-plane semantics instead of parser complexity.

## File extension

`.nyx`

## Canonical v0.1 top-level blocks

Nornyx v0.1 uses plural top-level names for collection blocks. The conceptual
blocks are project, constitution, intent, context, agent, skill, policy,
harness, eval, trace, evidence, approval, budget, and goal.

```text
nornyx
project
constitution
intents
contexts
skills
policies
agents
harnesses
traces
evals
evidence
approvals
budgets
goals
```

`nornyx` is the document version marker. `project` is a mapping. Collection
blocks such as `intents`, `contexts`, `agents`, `skills`, `policies`,
`harnesses`, `evals`, `traces`, `approvals`, `budgets`, and `goals` are lists.
`constitution` and `evidence` are mappings.

## Deferred extension blocks

The v0.1 checker may tolerate explicitly deferred extension/backlog blocks so
existing research examples can be inspected without promoting them into the
core. These blocks do not define stable v0.1 runtime behavior:

```text
experimental
graph
contracts
connectors
adapters
guardrails
capabilities
incidents
containment
supply_chain
```

## v0.2 graph and contract surface

Nornyx v0.2 introduces a static graph/contract surface while preserving
YAML-compatible v0.1 documents.

`graph` is a mapping with:

- `nodes`: list of mappings with `id` and `kind`;
- `edges`: list of mappings with `from`, `to`, and optional `relation`.

`contracts` is a list of named mappings that can reference graph node ids and
declared approval or budget names. The checker validates graph shape,
unresolved node references, known core `ref` references, contract node
references, approval references, and budget references.

Known graph node `kind` values such as `context`, `agent`, `policy`, `eval`,
`trace`, `approval`, `budget`, and `goal` are checked against their matching
named blocks when `ref` is supplied. Unknown/custom kinds remain allowed so
future domain profiles and adapters can use graph metadata without becoming
mandatory core language concepts.

These blocks are contract metadata only. They do not execute agents, tools,
connectors, models, approvals, or deployments.

The default JSON Schema path remains `schemas/nornyx_v0_1.schema.json` for
compatibility with existing tooling. Explicit schema targets are also available:

```bash
python -m nornyx.cli schema
python -m nornyx.cli schema --version 0.2
python -m nornyx.cli schema --version 1.0
```

The `0.2` target names the static graph/contract surface. The `1.0` target
names the stable generalized agentic contract-language surface. Schema
inspection does not execute agents, tools, connectors, models, approvals, or
deployments.

## v0.3 domain profile surface

Nornyx v0.3 adds optional domain profile packs. A profile pack is metadata and
starter-document guidance layered on the v0.2 static graph/contract surface; it
is not a new runtime and it does not make domain concepts mandatory core syntax.

The initial v0.3 packs are:

```text
ai_coding
agentic_repo_harness
telecom_ops
business_ops
ai_governance
finance_ops
```

These profiles can shape generated starter `.nyx` files and validation metadata
while the core remains general around Intent, Agent, Policy, Eval, Approval,
Evidence, Context, Artifact, Graph, Goal, Budget, and Trace.

Profile pack metadata is documented in
`docs/40_NORNYX_DOMAIN_PROFILES_v0_3.md` and
`schemas/domain_profile_pack.schema.json`.

## v0.4 adapter contract surface

Nornyx v0.4 adds a deferred `adapters` extension block for contract-only
ecosystem bridge metadata. Adapter contracts can reference connector manifests,
policies, evals, and evidence, but they do not execute connectors, call
networks, load credentials, run commands, deploy software, grant approvals, or
call models.

The initial adapter contract targets are Governed Delivery Control Plane, Agentic Development Harness,
GovernanceAdapter, telecom ops, and business ops. Their contract shape is documented in
`docs/41_NORNYX_ADAPTER_CONTRACTS_v0_4.md` and
`schemas/adapter_contract.schema.json`.

## v0.5 graph validation surface

Nornyx v0.5 hardens graph diagnostics with static relation source/target checks,
duplicate edge warnings, self-edge warnings, expanded known graph refs, and
contract auditability warnings for missing approval, budget, or evidence graph
coverage.

These checks are diagnostics only. They do not execute graph edges, schedule
work, run adapters, call connectors, call models, grant approvals, or deploy.

The v0.5 surface is documented in
`docs/42_NORNYX_GRAPH_VALIDATION_v0_5.md`.

## v0.6 domain-profile conformance surface

Nornyx v0.6 hardens profile packs with conformance metadata, compatibility
matrices, migration guidance, and v1 readiness decisions. This remains profile
metadata only and does not make domain concepts mandatory core syntax.

The v0.6 surface is documented in
`docs/43_NORNYX_PROFILE_CONFORMANCE_v0_6.md`.

## v0.7 adapter conformance surface

Nornyx v0.7 adds static adapter conformance reports and connector-contract
conformance schemas. The report validates adapter references to connectors,
policies, evals, and evidence, checks MCP/A2A connector conformance, and records
disabled safety flags.

This remains contract validation only. It does not enable live connectors, load
credentials, open networks, run commands, execute adapters, grant approvals, or
deploy.

The v0.7 surface is documented in
`docs/44_NORNYX_ADAPTER_CONFORMANCE_v0_7.md`.

## v0.8 bounded execution readiness surface

Nornyx v0.8 adds static bounded execution readiness reports. These reports
verify sandbox contracts, explicit capability gates, approval-before-action
gates, trace/evidence requirements, policy summaries, and adapter conformance
summaries.

This is readiness only. It does not execute tools, agents, graph edges,
adapters, connectors, models, shell commands, approvals, deployments, or
self-modification.

The v0.8 surface is documented in
`docs/45_NORNYX_BOUNDED_EXECUTION_READINESS_v0_8.md`.

## v0.9 release-candidate stabilization surface

Nornyx v0.9 adds local release-candidate stabilization reports. These reports
verify required maturity-band docs, schemas, examples, evidence, PMO state, and
locked future-goal boundaries.

This is evidence preparation only. It does not publish, tag, push, change
package versions, announce v1.0 readiness, unlock GOAL-042, or unlock GOAL-100.

The v0.9 surface is documented in
`docs/46_NORNYX_RELEASE_CANDIDATE_STABILIZATION_v0_9.md`.

## v1.0 stable generalized contract-language surface

Nornyx v1.0 records local stabilization of the generalized agentic contract
language surface across the v0.2-v0.9 maturity bands. The stable surface covers
static graph declarations, generic contract blocks, checker diagnostics, typed
schemas, optional profiles, contract-only adapters, policy/eval/evidence
semantics, approval gates, budget checks, trace semantics, artifact generation,
and safe interoperability rules.

The core remains general around Intent, Agent, Policy, Eval, Approval,
Evidence, Context, Artifact, Graph, Goal, Budget, and Trace. Domain profiles
and ecosystem adapters remain optional overlays.

This stable-language surface does not publish, tag, push, change package
versions, deploy, enable live connectors, call models, execute graph edges,
grant approvals, self-modify, or unlock GOAL-100.

The v1.0 surface is documented in
`docs/47_NORNYX_STABLE_GENERALIZED_CONTRACT_LANGUAGE_v1_0.md`.

## Core semantic idea

The `.nyx` file is the source of truth. Generated artifacts are compatibility outputs.

## Minimal document

```yaml
nornyx: "0.1"
project:
  name: ExampleProject

intents:
  - name: ExampleIntent
    goal: "Define what the system should achieve."
```

## Agent block

```yaml
agents:
  - name: Builder
    role: "Implement small scoped patches."
    skills: [PatchBuilder]
    policy: SafeEditPolicy
```

## Harness block

```yaml
harnesses:
  - name: DevHarness
    context: RepoContext
    flow:
      - agent: Builder
        action: implement
      - tool: tests
        action: run
      - evidence: DevEvidence
        action: pack
```

## v0.1 checker rules

The v0.1 checker validates:

- required top-level blocks;
- project name;
- core list block shape;
- core mapping block shape for `constitution` and `evidence`;
- graph node/edge shape, unresolved graph references, and known core graph refs;
- contract graph, approval, and budget references;
- agent skill references;
- agent policy references;
- harness agent references;
- harness eval references;
- evidence contract shape;
- suspicious unknown blocks.

## Future syntax

Future versions may move from YAML-compatible syntax to a dedicated parser, but the semantic model should remain stable.
