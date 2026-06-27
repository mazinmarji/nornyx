# ADR-0015 — Product-to-Operations Lifecycle Extension

## Status

Proposed

## Context

The ShelfWise Rescue A-to-Z example showed that Nornyx should not only govern implementation. A useful AI-native engineering language should connect:

```text
ideation
discovery
mocking / prototype
pre-implementation readiness
Nornyx-governed development
QA and release
operations
support
feedback
evergreen improvement
```

However, adding all product-management and operations concepts directly to the v0.1 language core would overload Nornyx.

## Decision

Nornyx will treat product-to-operations coverage as an optional **Lifecycle Extension**.

This extension is roadmap/backlog material, not immediate core language scope.

The extension will define future blocks such as:

```text
intake
persona
journey
prototype
assumption
open_question
decision_needed
handover
operations
product_eval
lifecycle_state
```

The first concept to promote later should be:

```text
handover
```

because it connects product discovery, Nornyx development, release, operations, and improvement.

## What belongs in the core now

Keep the current core focused on:

```text
project
goal
intent
context
agent
policy
harness
eval
evidence
approval
trace
budget
delivery_state
```

## What belongs in the extension roadmap

Add lifecycle blocks only when they can be checked, generated, or rendered:

```text
intake → product discovery input
prototype → UX/mock handover
handover → boundary contract between lifecycle phases
operations → runbook/SLO/monitoring/rollback/support
product_eval → business/user outcome validation
assumption/open_question/decision_needed → ambiguity control
lifecycle_state → product/service stage tracking
```

## Boundary

Nornyx should not become:

```text
a full product-management suite
a design tool
a ticketing system
a customer-support system
a BI platform
a production operations console
```

Nornyx may generate contracts, evidence templates, and handoff artifacts for those systems.

## Safety

This extension is declarative and local-only.

It must not:

```text
call LLMs
invoke connectors
write to production systems
handle credentials
approve releases
run deployments
create tickets automatically
```

## Consequences

Positive:

- gives Nornyx a product-to-ops path without scope explosion;
- helps LLMs avoid inventing product assumptions;
- makes handovers explicit;
- supports role-specific users;
- prepares Nornyx for enterprise lifecycle use.

Trade-off:

- most lifecycle blocks remain roadmap/backlog until core parser/checker maturity improves.
