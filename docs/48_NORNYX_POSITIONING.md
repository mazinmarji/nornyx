# Nornyx Positioning

## What Nornyx Is

Nornyx is a vendor-neutral governance contract language for AI software
delivery that defines deterministic controls and authorization semantics,
binds decisions and supplied evidence to governed revisions, and preserves
that governance meaning across supported integrations. It provides checkable
contracts for intent, context, agents, skills, policies, evals, approvals,
evidence, budgets, traces, graph relationships, profiles, and adapter
contracts.

Its practical role is to replace scattered control artifacts such as
`AGENTS.md`, skills folders, prompt packs, context packs, harness scripts, eval
configs, policy docs, evidence templates, and approval checklists with a single
`.nyx` source of truth.

Nornyx is intentionally vendor-neutral. Its durable role is to preserve one
reviewed governance meaning across heterogeneous execution and enforcement
surfaces, bind that meaning to exact revisions and evidence, and provide
conformance boundaries that external policy engines, gateways, runtimes, and
platform controls can consume without making those systems part of Nornyx.

## What Nornyx Is Not

Nornyx is not:

- a full autonomous runtime;
- a general-purpose programming language;
- a LangGraph, CrewAI, or LangChain replacement;
- a production execution engine;
- a live MCP/A2A connector runtime;
- an agent gateway or traffic proxy;
- an agent registry or marketplace;
- an IAM system, identity issuer, secrets manager, or credential broker;
- a sandbox, service mesh, content-filtering/DLP layer, or model guardrail;
- a SIEM, telemetry store, or hyperscaler observability service;
- a hosted generic authorization service in Public Core;
- automatic approval or self-modification;
- regulated/enterprise GOAL-100 promotion.

These boundaries are strategic as well as technical: Nornyx should interoperate
with runtime, gateway, identity, sandbox, cloud, and policy-engine products
rather than duplicate infrastructure that those platforms already own.

## Best Use Cases

- Declare governed AI/software delivery contracts.
- Check policy, eval, approval, budget, evidence, and trace relationships.
- Generate local control-plane artifacts from `.nyx` files.
- Model static Nornyx Graph relationships for review and evidence.
- Bind decisions, approvals, evidence, locks, and generated artifacts to an
  exact governed revision.
- Define deterministic, vendor-neutral authorization semantics and prove that a
  supported external mapping preserves those semantics.
- Compare supported governed revisions or decision fixtures deterministically
  when a generic Core use case requires change/conformance analysis.
- Prepare optional profile, adapter, protocol, and standards mappings without
  enabling runtime execution.

## Interoperability Position

Public Nornyx owns portable semantics, mappings, schemas, deterministic
conformance tests, and honest claim boundaries. It should prefer established
external standards and policy surfaces over a proprietary connector treadmill.

Current and candidate interoperability surfaces include OpenID AuthZEN,
MCP/A2A declarations, and feasibility or projection work for policy engines or
policy languages such as OPA/Rego, Cedar, and agent-era decision specifications.
A mapping or projection remains subordinate to the `.nyx` source contract: it
must not become a second authoritative policy source, and a successful mapping
does not imply that an external PEP enforced the result.

Generic revision lineage, deterministic before/after semantic comparison,
decision-regression fixtures, and evidence-correlation identifiers may belong in
Public Core when they are independently useful to Nornyx consumers. These remain
portable language/conformance primitives and do not imply hosted operational
services or runtime enforcement.

## Release and Distribution

Nornyx publishes a Python package to PyPI (`pip install nornyx`) for the stable
vendor-neutral governance contract language on the 1.x line. The package
(distribution) version is independent of the Nornyx language/schema version — see
[VERSIONING.md](VERSIONING.md). Publishing the package does not deploy software,
enable live connectors, call models, grant automatic approvals, or unlock
GOAL-100. Nornyx remains an executable specification layer, not a runtime.

## Future Tracks

Future work may include schema splits, sharper adoption docs, static Nornyx
Graph demos, editor tooling, standards-aligned semantic projections,
cross-platform conformance proof, generic revision/decision comparison where
adoption demonstrates need, and thin distributable adapters. Runtime ownership,
broad connector hosting, and platform-specific infrastructure remain gated or
out of scope. Each track requires scoped goals, validation, evidence, and
explicit approval.
