# ADR-0017 — Decision Boundary and Evidence Quality

## Status

Proposed

## Context

The ColdGuard complex lifecycle example introduced regulated AI workflows where an AI system may classify, recommend, explain, or flag risk, but must not make final regulated or operational decisions.

The example also showed that evidence presence is not enough. Regulated systems need evidence quality: provenance, timestamps, source hashes, approver identity, retention, exportability, and tamper-resistance.

## Decision

Nornyx will add two regulated-system design candidates:

```text
decision_boundary
evidence_quality
```

These are near-core/extension candidates, not full runtime enforcement yet.

## Decision boundary

A decision boundary declares:

```text
what AI may recommend
what AI must not decide
which human role owns the decision
which approval is required
which evidence must be captured
which actions are blocked
```

## Evidence quality

Evidence quality declares:

```text
required evidence items
quality requirements
retention expectations
export needs
identity/provenance requirements
tamper-resistance expectations
```

## Safety

This addition is local/read-only validation and documentation. No runtime actions, connectors, LLM calls, credentials, approvals, deployments, or production writes are introduced.
