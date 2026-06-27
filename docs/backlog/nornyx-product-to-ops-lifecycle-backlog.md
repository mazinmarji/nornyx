# Backlog — Product-to-Operations Lifecycle Extension

## Backlog status

This backlog is intentionally deferred behind core language hardening.

Do not implement these as core blocks until GOAL-001 and GOAL-002 are stable.

## Candidate backlog items

### LIFE-001 — Handover block design

Define handover contracts:

```text
ProductToNornyx
NornyxToRelease
ReleaseToOperations
OperationsToBacklog
```

Acceptance:

```text
handover has required artifacts
handover can be validated
handover can produce Markdown/evidence template
```

### LIFE-002 — Assumption/open-question model

Define:

```text
assumption
open_question
decision_needed
```

Acceptance:

```text
LLM must not silently invent blocked details
decision owner can be specified
unresolved questions can block a goal
```

### LIFE-003 — Intake block

Define product discovery input:

```text
problem
users
hypotheses
constraints
success metrics
non-goals
```

Acceptance:

```text
intake can generate product brief and Nornyx goal candidates
```

### LIFE-004 — Prototype block

Define:

```text
wireframes
mockups
journeys
UX assumptions
acceptance behavior
```

Acceptance:

```text
prototype can map to user stories and acceptance tests
```

### LIFE-005 — Operations block

Define:

```text
runbook
SLO
monitoring
alerts
rollback
support playbook
known limitations
```

Acceptance:

```text
release cannot be marked operations-ready without required ops evidence
```

### LIFE-006 — Product evaluation block

Define product/business outcome validation:

```text
activation
retention
time saved
waste reduced
support tickets
pilot success
```

Acceptance:

```text
product_eval is distinct from software tests and AI evals
```

### LIFE-007 — Lifecycle state

Define states:

```text
idea
discovery
prototype
pre_implementation_ready
development
qa
release_candidate
operational
observed
improvement_backlog
deprecated
```

Acceptance:

```text
delivery state can render lifecycle stage
```

## Non-goals

This backlog does not create:

```text
a product-management tool
a design tool
a ticketing system
a production monitoring system
an operations console
```

Nornyx should generate contracts and evidence for those systems, not replace them.
