# Nornyx v1.0 Stable Generalized Agentic Contract Language

## Status

Local v1.0 stable-language completion surface. This marks the generalized
agentic contract language as locally stabilized across the v0.2-v0.9 maturity
bands. It does not publish, tag, push, change package versions, deploy, enable
live connectors, grant approvals, call models, or unlock regulated/enterprise
GOAL-100 work.

## Stable Contract Surface

v1.0 stabilizes the following contract-language surface:

- static Nornyx Graph node and edge declarations;
- generic contract blocks with graph, approval, and budget references;
- checker diagnostics for graph consistency and contract auditability;
- typed schemas for profile, adapter, connector, bounded-readiness, release,
  and stable-language reports;
- optional domain profile packs;
- contract-only adapter bridges and connector-conformance metadata;
- static bounded execution readiness reports;
- policy, eval, evidence, trace, approval, and budget semantics;
- artifact generation for local control-plane outputs;
- safe interoperability rules for adjacent tools and ecosystems.

## General Core

The core remains general around:

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

Domain names such as telecom ops, business ops, Governed Delivery Control Plane, Agentic Dev
OS, and GovernanceAdapter are optional profiles, optional adapters, or reference
implementations. They are not mandatory core language concepts.

## Stable-Language Report

`nornyx.release_readiness.build_stable_language_report()` combines the
release-candidate stabilization report with v1.0 stable-language checks.

It verifies:

- v1.0 stable-language docs and schemas exist;
- GOAL-033 through GOAL-042 are complete in PMO status;
- GOAL-033 through GOAL-042 evidence directories exist;
- GOAL-100 remains locked;
- the general core concepts are recorded;
- v1.0 non-goals are recorded;
- validation commands are declared;
- public v1.0 release still requires human approval.

The matching schema is `schemas/stable_language_report.schema.json`.

## Required Validation

```bash
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
python -m nornyx.cli check examples/nornyx_v04_adapter_contracts.nyx
python -m nornyx.cli release-check --out generated/release_readiness_v0_9.json
python scripts/dev/audit_pmo_status.py
python scripts/release/check_rc_stabilization.py
python scripts/release/check_stable_language.py
```

## Non-Goals

v1.0 does not mean:

- a full autonomous runtime;
- a general-purpose programming language;
- a production execution engine;
- unrestricted connector runtime;
- automatic approvals;
- self-modification;
- regulated or enterprise GOAL-100 promotion.

## Boundary

GOAL-042 records local stable-language completion only. Public release,
package-version changes, tags, pushes, announcements, connector/runtime
enablement, production deployment, and GOAL-100 promotion all remain separate
approval-gated work.
