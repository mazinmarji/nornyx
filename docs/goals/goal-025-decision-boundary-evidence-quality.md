# GOAL-025 — Decision Boundary and Evidence Quality

## Goal

Add regulated-system design candidates for decision boundaries and evidence quality.

## Scope

Add decision boundary docs, evidence quality docs, schemas, local validators, illustrative example, tests, and evidence note.

## Non-goals

Do not add regulatory compliance engine, audit database, identity provider, cryptographic ledger, runtime connector enforcement, production approvals, or deployment automation.

## Acceptance

```powershell
python -m pytest -q tests/test_decision_boundary_evidence_quality.py
```

## Promotion rule

`decision_boundary` and `evidence_quality` should remain regulated/enterprise candidates until policy, capability, and evidence runtime enforcement mature.
