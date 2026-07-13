# ADR-0025 - Normalized Approval Contract

## Status

Accepted and implemented in Nornyx 1.5.x.

## Context

Ordinary contracts, generated starters, governed-package gates, references,
prose goal fields, and boolean approval requirements use different shapes.

## Decision

A loss-aware internal `nornyx.normalized_approval.v1` representation records
roles, denials, evidence, actions, timing, authority, revision binding,
the independent exact-revision requirement, invalidation, relative and
absolute expiry, diagnostics, and the full raw source. Known governed-package
role aliases map deterministically. Unknown role-bearing fields, non-string
accountable authority, and contradictions fail normalization. No default
approver is invented. Composition intersects non-empty eligibility sets and
fails when layers have no common eligible human role.

## Consequences

`references_role` semantics are consistent without changing legacy source
structures. Legacy text and booleans remain representable but cannot
be misrepresented as complete authority declarations.
