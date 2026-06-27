# Product-to-Operations Lifecycle Roadmap for Nornyx

## Purpose

This document captures the lifecycle gaps identified from the A-to-Z ShelfWise Rescue example and assigns them to the right Nornyx maturity stage.

The goal is to cover the full path:

```text
idea → mockup → pre-implementation → Nornyx development → release → operations → feedback
```

without overloading the v0.1 language core.

## Lifecycle concepts

| Concept | Purpose | Placement |
|---|---|---|
| `intake` | Product problem, users, hypotheses, constraints | Future lifecycle extension |
| `persona` | User roles and needs | Future lifecycle extension |
| `journey` | User journey / workflow | Future lifecycle extension |
| `prototype` | Mockups, wireframes, UX assumptions | Future lifecycle extension |
| `assumption` | Explicit assumptions to prevent LLM invention | Near-term design backlog |
| `open_question` | Questions needing human decision | Near-term design backlog |
| `decision_needed` | Owner-bound decision request | Near-term design backlog |
| `handover` | Contract between lifecycle phases | Candidate for promotion after GOAL-001 |
| `operations` | Runbook, SLO, monitoring, rollback, support | Future lifecycle extension |
| `product_eval` | Product/business outcome validation | Future lifecycle extension |
| `lifecycle_state` | Track idea/discovery/dev/release/ops/improvement stage | Future lifecycle extension |

## Recommended promotion order

### Stage 1 — Add to roadmap/backlog now

```text
intake
prototype
operations
product_eval
lifecycle_state
```

### Stage 2 — Add near-term design specs

```text
assumption
open_question
decision_needed
handover
```

### Stage 3 — Promote after core spec freeze

```text
handover
```

Reason: handover is the highest leverage concept because it connects:

```text
product discovery → development → release → operations → improvement
```

### Stage 4 — Promote after parser/checker maturity

```text
intake
prototype
operations
product_eval
lifecycle_state
```

## Example handover chain

```text
ProductToNornyx
  requires problem, users, mockups, acceptance, constraints, risks

NornyxToRelease
  requires tests, evals, evidence, approval, release notes

ReleaseToOperations
  requires runbook, monitoring, rollback, support playbook, known limitations

OperationsToBacklog
  requires incidents, feedback, metrics, improvement candidates
```

## Role impact

| Role | Needs |
|---|---|
| Founder / CEO | roadmap, risk, product evidence, traction |
| Product manager | personas, stories, acceptance, backlog |
| Designer | journeys, mockups, usability assumptions |
| Developer | implementation goals, context, tests, evidence |
| QA | acceptance tests, regression, evidence |
| Security | data, permissions, threat model |
| Operations | runbook, monitoring, incidents, rollback |
| Support | known issues, escalation, FAQ |
| Customer | release notes and behavior clarity |

## Boundary rule

Do not add lifecycle features unless they improve at least one:

```text
LLM ambiguity control
handover quality
operations readiness
role-specific visibility
product evidence
```

## Machine-readable backlog

The roadmap is mirrored in:

```text
docs/backlog/nornyx-product-to-ops-lifecycle.yaml
```

Validate it locally with:

```bash
python scripts/dev/check_product_lifecycle.py
```

The validator keeps lifecycle concepts out of the v0.1 core by requiring the
extension to remain roadmap/candidate metadata. `handover` may appear as the
first candidate, but promotion still requires a separate goal, tests, evidence,
and human approval.
