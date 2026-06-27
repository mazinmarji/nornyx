# ADR-0018 — Requirement Triage Matrix

## Status

Proposed

## Context

Nornyx has accumulated many valuable concepts through examples and gap analysis:

```text
core language blocks
AI-agent controls
handover contracts
delivery state
portal renderers
pattern lifecycle
evergreen assurance
product-to-operations lifecycle ideas
regulated decision boundaries
evidence quality
data provenance
tenant boundaries
incident response
```

The risk is scope creep.

If every useful concept becomes immediate implementation scope, Nornyx will become another pile of docs, configs, patterns, and optional systems.

## Decision

Nornyx will use a Requirement Triage Matrix.

Every concept must be classified as one of:

```text
core_now
near_core_candidate
extension_backlog
profile_specific
outside_nornyx
rejected
```

The matrix becomes the control mechanism for deciding whether a new idea deserves:

```text
immediate implementation
small validator/docs
roadmap/backlog only
domain profile later
no action
```

## Classification rules

### core_now

Required for the v0.1 language to be useful.

Examples:

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

### near_core_candidate

High-value concept that prevents LLM misuse or unsafe handover, but should wait until parser/checker maturity.

Examples:

```text
handover
assumption
open_question
decision_needed
decision_boundary
evidence_quality
```

### extension_backlog

Useful future capability, but not v0.1 core.

Examples:

```text
intake
prototype
operations
product_eval
lifecycle_state
data_provenance
tenant_boundary
incident_response
```

### profile_specific

Useful for a domain profile, not universal core.

Examples:

```text
telecom_ops_profile
regulated_cold_chain_profile
civic_services_profile
financial_trading_profile
```

### outside_nornyx

Belongs to another system. Nornyx may define contracts for it but should not implement it.

Examples:

```text
identity provider
ticketing system
monitoring platform
product-management suite
BI dashboard
IoT stream processor
```

### rejected

Adds complexity without enough value, duplicates existing scope, or makes Nornyx the pile.

## Rule for new diffs

A new diff should be created only if it:

```text
improves core language correctness
prevents LLM misuse
reduces duplicated repo artifacts
strengthens evidence/safety/handover
adds a small validator for an accepted concept
hardens parser/checker/generator
```

Do not create diffs for:

```text
new ideas only
extra examples only
tool-specific hype
dashboard fantasies
platform scope expansion
```

unless explicitly classified as backlog documentation.

## Consequences

Positive:

- prevents scope creep;
- protects GOAL-001 core freeze;
- gives a clear roadmap;
- helps LLMs and humans know what belongs where;
- keeps Nornyx useful instead of bloated.

Trade-off:

- some good ideas will wait;
- classification must be maintained as evidence changes.
