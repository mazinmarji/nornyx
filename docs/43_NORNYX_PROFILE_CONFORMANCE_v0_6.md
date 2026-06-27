# Nornyx v0.6 Domain-Profile Conformance

## Status

Local v0.6 profile conformance surface. This hardens the v0.3 domain profile
packs without adding adapters, runtime execution, live connectors, model calls,
automatic approvals, production deployment, or mandatory domain-specific core
syntax.

## Conformance report

`nornyx.profiles.profile_conformance_report()` returns:

- `schema: nornyx.profile_conformance.v0.6`;
- profile pack metadata;
- conformance level;
- compatibility matrix;
- v1 readiness decisions;
- migration guidance;
- validation issues.

The report is local metadata only.

## Stability decisions

```text
ai_coding              stable_candidate
agentic_repo_harness   stable_candidate
ai_governance          stable_candidate
telecom_ops            profile_candidate
business_ops           profile_candidate
finance_ops            optional_candidate
```

`finance_ops` remains explicitly optional. Telecom and business operations
profiles remain profile candidates until adapter and connector-contract
conformance mature.

## Compatibility matrix

The v0.6 matrix separates:

- `compatible_with`: profile pairings expected to compose cleanly;
- `requires_review_with`: profile pairings that may compose but need human
  review because domain obligations can conflict;
- `conflicts_with`: reserved for explicit conflicts.

No current profile pair is marked as a hard conflict. Domain-heavy pairings are
review-gated rather than rejected.

## Core boundary

Every profile pack must keep the same general Nornyx core concept list:

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

Profile-specific terms such as `telecom_ops`, `business_ops`, `ai_governance`,
and `finance_ops` stay in profile metadata. They are not mandatory core
language concepts.

## Migration checks

Each profile declares migration guidance. Generated domain-profile starter
documents must:

- use the v0.2 graph/contract surface;
- pass `nornyx check` without diagnostics;
- include graph coverage for profile, context, agent, policy, approval, budget,
  evidence, and goal nodes;
- reference approval and budget names in contracts;
- keep profile non-goals aligned with the shared safety boundary.

## Non-goals

v0.6 does not:

- implement adapters;
- execute profile logic;
- override generic graph/contract safety rules;
- weaken policy, evidence, approval, or budget semantics;
- make domain profiles mandatory core language syntax.
