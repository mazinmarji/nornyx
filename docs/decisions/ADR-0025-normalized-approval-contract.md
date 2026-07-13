# ADR-0025 - Normalized Approval Contract

## Status

Accepted and implemented in Nornyx 1.5.x.

## Context

Ordinary contracts, generated starters, governed-package gates, references,
prose goal fields, and boolean approval requirements use different shapes.

## Decision

A loss-aware internal `nornyx.normalized_approval.v1` representation records
roles, denials, evidence, actions, timing, authority, revision binding,
invalidation, expiry, diagnostics, and the full raw source. Known governed-
package role aliases map deterministically. Unknown role-bearing fields and
contradictions fail normalization. No default approver is invented.

## Consequences

`references_role` semantics are consistent without changing legacy source
structures. Legacy text and booleans remain representable but cannot
be misrepresented as complete authority declarations.
