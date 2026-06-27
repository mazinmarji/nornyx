# ADR-0016 — Handover Contracts and Ambiguity Controls

## Status

Proposed

## Context

The A-to-Z product/service examples showed that Nornyx should not start only when code implementation begins.

A practical AI-native engineering language must help with transitions:

```text
product discovery → Nornyx-governed development
Nornyx development → release
release → operations
operations → improvement backlog
```

The examples also showed that LLM agents often fill missing product or operational details silently. This creates risk.

## Decision

Nornyx will promote two near-core concepts for design and validation:

```text
handover
assumption / open_question / decision_needed
```

These are not full product-management features. They are control-plane contracts that help humans and LLMs move safely between lifecycle phases.

## Handover purpose

A handover declares:

```text
from_state
to_state
required artifacts
acceptance conditions
open questions
approval owner
evidence path
```

## Ambiguity-control purpose

Ambiguity controls prevent silent LLM invention.

They declare:

```text
assumptions the agent may rely on
open questions that need answers
decisions needed from a named owner
blocking vs non-blocking uncertainty
```

## What belongs now

Add local validators, schemas, docs, and examples.

## What does not belong now

Do not add:

```text
full product-management workflow
design-tool integration
ticketing integration
operations automation
deployment automation
connector calls
LLM calls
automatic approval
```

## Safety

This addition is local/read-only validation and documentation.

No runtime actions are introduced.

## Consequences

Positive:

- gives LLMs clearer transition boundaries;
- prevents silent assumptions;
- improves handover quality;
- makes Nornyx useful earlier and later in the lifecycle;
- keeps broader product/ops lifecycle concepts in backlog.

Trade-off:

- handover syntax must remain simple until the formal parser is mature.
