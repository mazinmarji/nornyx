# Nornyx Decision Boundary and Evidence Quality

## Purpose

This document defines two regulated-system design candidates for Nornyx:

```text
decision_boundary
evidence_quality
```

They help Nornyx support complex agentic AI systems where AI can help but must not cross human, legal, operational, or safety authority boundaries.

## Decision boundary example

```nyx
decision_boundary ShipmentDisposition:
    ai_allowed:
        - propose_risk_score
        - explain_temperature_anomaly
        - suggest_manual_check
    ai_denied:
        - approve_disposal
        - release_blocked_shipment
        - notify_customer_without_policy
        - override_compliance_hold
    human_owner: ComplianceOwner
    approval_required: true
    evidence_required:
        - ai_recommendation
        - human_approval
        - reason_code
        - timestamp
```

## Evidence quality example

```nyx
evidence_quality ColdGuardAuditEvidence:
    required:
        - telemetry_snapshot
        - anomaly_reason
        - ai_recommendation
        - human_approval
        - customer_notification_record
    quality:
        - immutable_timestamp
        - source_hash
        - approver_identity
        - tenant_id
        - exportable_report
    retention: "2 years"
```

## Core rules

```text
AI-denied actions must not appear in allowed actions.
A decision boundary must name a human owner.
Approval-required boundaries must define evidence.
Audit-grade evidence should include timestamp, source/provenance, and identity.
```

## Boundary

Nornyx defines and validates the contract. Specialized systems still perform identity, signature, audit storage, compliance reporting, monitoring, ticketing, and operations execution.

## Machine-readable regulated control pack

The regulated candidate design is mirrored in:

```text
docs/backlog/nornyx-decision-boundary-evidence-quality.yaml
```

Validate it locally with:

```bash
python scripts/dev/check_regulated_controls.py
```

The checker validates decision-boundary shape, evidence-quality shape, and
coverage between `approval_required` decision evidence and the evidence-quality
contract. It also blocks unsafe safety flags such as automatic approval,
connector calls, LLM calls, deployment actions, and production writes.
