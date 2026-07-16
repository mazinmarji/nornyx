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

The 12 structured v1 packs under `nornyx/profiles_data/` are authoritative and
are included in the wheel. They are loaded through the local-only governance
registry by `nornyx init`, `nornyx profiles`, and pack-aware `nornyx check`.
The old root `profiles/*.yaml` mirrors were removed to prevent dual-source
drift. `nornyx.profiles` remains a compatibility facade: its historical v0.3
APIs return the exact validated v1-to-v0.3 projection, while `profile_pack_v1()`
and `nornyx profiles inspect` expose the authoritative object.

Each v0.3 pack declares:

- `version: v0.3`;
- `core_surface: v0.2`;
- `status: optional_profile`;
- required and recommended blocks;
- graph node kinds used by the starter document;
- validation rules;
- explicit non-goals;
- the allowed general core concept set.

The frozen compatibility schema remains
`schemas/domain_profile_pack.schema.json`; authoritative packs validate against
`schemas/profile_pack_v1.schema.json`. The projection report stays separate so
the strict v0.3 object receives no marker or unrecognized field.

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

Profile validation covers:

- v1 schema, canonical integrity hash, and packaged catalog completeness;
- exact v1-to-v0.3 projection and separate loss reporting;
- generated starter documents passing `nornyx check`;
- profile-only domain names not appearing as mandatory core concepts;
- non-goals that block runtime execution, automatic approvals, and production
  deployment.

The v0.6 domain-profile conformance surface is implemented. The additive
`architecture_governance` profile is v1-only and is not projected into the six
historical v0.3 domain-pack catalog. New profile semantics remain optional and
do not become stable core concepts.
