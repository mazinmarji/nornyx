# Nornyx v0.3 Domain Profiles

## Status

Local v0.3 profile-pack surface. Profiles are optional overlays on the v0.2
static graph and contract model. They do not introduce a new core language
version, adapter runtime, live connector, model call, automatic approval, or
production deployment path.

## Built-in v0.3 profile packs

```text
ai_coding
agentic_repo_harness
telecom_ops
business_ops
ai_governance
finance_ops
```

`finance_ops` is included as an opt-in pack because some governed projects may
need finance operations language. It is not mandatory core.

## Core boundary

The Nornyx core remains general around:

```text
Intent
Agent
Policy
Eval
Approval
Evidence
Context
Artifact
Graph
Goal
Budget
Trace
```

Profile names such as `telecom_ops`, `business_ops`, `ai_governance`, and
`finance_ops` are profile metadata, not core language concepts.

## Pack contract

### Current source of truth

The v0.3 pack catalog in `nornyx/profiles.py` is authoritative today. The six
domain files under `profiles/` are repository mirrors checked against that
Python catalog; they are not loaded by `nornyx init`, `nornyx profiles`, or
`nornyx check`, and root `profiles/*.yaml` files are not included in the wheel.
The five base-profile YAML files are descriptive metadata only. Structured v1
packs and a loader are planned work, not current behavior.

Each v0.3 pack declares:

- `version: v0.3`;
- `core_surface: v0.2`;
- `status: optional_profile`;
- required and recommended blocks;
- graph node kinds used by the starter document;
- validation rules;
- explicit non-goals;
- the allowed general core concept set.

The pack schema is documented in `schemas/domain_profile_pack.schema.json`.
The Python catalog validator in `nornyx.profiles.validate_profile_pack_catalog`
checks the same basic safety invariants for local tests.

## Generated starter behavior

`nornyx init --profile <domain_profile>` creates a checkable starter document
with:

- `nornyx: "0.2"` because the profile uses the v0.2 graph/contract surface;
- `project.profile_pack` metadata;
- static `graph:` nodes and edges;
- static `contracts:` that reference declared graph nodes, approval, and budget;
- evidence, approval, budget, goal, guardrail, trace, and eval defaults.

These starters are contract documents only. They do not execute tools, connect
to MCP/A2A systems, call models, grant approvals, modify themselves, or deploy
anything.

## Validation

Profile validation currently covers:

- pack catalog shape;
- pack metadata files matching the Python catalog;
- generated starter documents passing `nornyx check`;
- profile-only domain names not appearing as mandatory core concepts;
- non-goals that block runtime execution, automatic approvals, and production
  deployment.

v0.6 is reserved for stricter domain-profile conformance after adapters and
ecosystem boundaries are clearer.
