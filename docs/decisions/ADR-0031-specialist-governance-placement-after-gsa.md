# ADR-0031 - Specialist Governance Placement After GSA

Status: Accepted

Date: 2026-07-13

## Context

The governance program named five possible later modules: supply chain, data
protection, lifecycle management, release control, and incident response. The
module-proliferation rule requires each later module to prove reuse, reconcile
duplicate semantics, close a high-priority control gap, or provide a stable
evidence contract needed by an existing feature.

The Stage E Governance Surface Analysis compared those candidates with current
scanner, governed-package, profile, lifecycle, release-readiness, checker, and
evidence behavior. Full results and priority tuples are in
`18_GSA_RESULTS.md`.

## Decisions

| Candidate | Final status | Placement |
|---|---|---|
| Supply-chain governance | `implemented_as_external_evidence_integration` | Keep deterministic inventory, hook/script/secret checks, Syft-like SBOM import, Gitleaks-like secret import, and package gates in the governed-package/scanner surface. Do not duplicate them in a module. |
| Data-protection governance | `not_required_after_GSA` | Keep no-secrets/no-PII/model-exposure controls profile-local and require evidence from organizational privacy, access, encryption, retention, and residency systems. No stable shared evidence contract exists in current features. |
| Lifecycle management | `not_required_after_GSA` | Keep lifecycle states owned by each governed object: changes, approvals, exceptions, architecture decisions, packs, and the existing product-to-operations advisory helper. A common module would create competing state machines. |
| Release control | `superseded` | Existing release-readiness and release-candidate stabilization reports own release identity, evidence gates, no-go conditions, and human approval. Shared change, evidence, approval, and separation modules provide reusable controls without a parallel release model. |
| Incident response | `not_required_after_GSA` | Operational incident systems remain action owners. Current Nornyx profiles have no stable incident evidence contract or two-profile reusable declaration proven by executable examples. |
| GSA runtime schema and CLI | `not_required_after_GSA` | GSA remains a documented method with validated advisory YAML templates; no runtime tooling is justified. |

## Re-entry Conditions

- Data protection may re-enter only when at least two profiles need the same
  bounded declaration and a versioned external evidence contract is available.
- Lifecycle may re-enter only if two object classes demonstrably share one
  state machine without weakening their existing semantics.
- Incident response may re-enter only with two profile adopters, a stable
  evidence envelope, and a design that performs no operational action.
- Raw supply-chain extensions belong in the governed-package/scanner program
  unless a non-package consumer proves reusable demand.
- Release control may re-enter only if an existing release-readiness use case
  cannot be expressed through the shared governance modules without duplicate
  release state.
- Structured GSA tooling may re-enter only if multiple completed analyses show
  repeatability problems that validated documents and tests cannot solve.

## Consequences

No Stage F module is justified. The module catalog freezes at the six modules
implemented through Architecture Governance. This avoids duplicate scanners,
privacy-platform scope, competing lifecycle and release models, and operational
incident execution while giving every candidate an unambiguous final status.

