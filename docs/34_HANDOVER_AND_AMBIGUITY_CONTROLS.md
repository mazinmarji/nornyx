# Nornyx Handover and Ambiguity Controls

## Purpose

This document defines the near-core design for handover contracts and ambiguity controls.

The goal is to help both LLM agents and human users by making transitions and unknowns explicit.

## Handover contracts

A handover connects two lifecycle phases.

Examples:

```text
ProductToNornyx
NornyxToRelease
ReleaseToOperations
OperationsToBacklog
```

A handover should declare:

```text
name
from_state
to_state
required artifacts
acceptance conditions
evidence path
approval owner
blocking open questions
```

## Example handover

```nyx
handover ProductToNornyx:
    from: product_discovery
    to: governed_development
    required:
        - problem_statement
        - personas
        - user_journeys
        - prototype_screens
        - acceptance_criteria
        - constraints
        - risks
        - success_metrics
    approval: ProductOwner
    evidence: "docs/qa/evidence/GOAL-023/"
```

## Ambiguity controls

Ambiguity controls stop the LLM from inventing details.

Use:

```text
assumption
open_question
decision_needed
```

## Example ambiguity controls

```nyx
assumption WebFirstMVP:
    text: "MVP supports a web app only, not native mobile apps."
    risk: low
    can_proceed: true

open_question CitizenPhoneNumber:
    question: "Should user phone number be mandatory or optional?"
    owner: ProductOwner
    blocks:
        - notification_flow

decision_needed AIVisibility:
    owner: ProductOwner
    question: "Should AI category suggestion be visible to external users?"
    required_before:
        - public_beta
```

## Core rules

```text
A blocking open question must prevent completion.
A decision_needed item must name an owner.
An assumption must state whether work can proceed.
A handover cannot be accepted if required artifacts are missing.
```

## Renderers

Handover and ambiguity state should be renderable as:

```text
shell
markdown
json
Developer PMO Portal
future IDE panel
```

## Boundary

Nornyx should validate and render these contracts.

Nornyx should not become a product-management, design, ticketing, or operations platform.

## Machine-readable control pack

The near-core design is mirrored in:

```text
docs/backlog/nornyx-handover-and-ambiguity-controls.yaml
```

Validate it locally with:

```bash
python scripts/dev/check_handover_controls.py
```

The checker validates each handover and ambiguity control, then verifies that
handover `blocking_open_questions` entries point to declared `open_question`
controls. This keeps handover readiness explicit without adding approvals,
ticketing, connector calls, deployment actions, or runtime automation.
