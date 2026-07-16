# ADR-0021 - Change Governance as a Module

## Status

Accepted and implemented; compatibility boundary clarified by the PR #30
NO-GO remediation.

## Context

Governed packages already contain a minimal `changes` list. Making Change a
stable core concept would revise frozen language schemas, while defining a new
shape per profile would fragment meaning.

## Decision

Change Governance is a reusable declarative module. Its strict
`nornyx.change.v1` schema governs an explicitly selected top-level `changes`
block. Core concepts remain unchanged.

Nested `governed_package.changes` remains on the exact 1.x compatibility
projection: unrestricted JSON strings for `id`, `type`, and
`expected_artifacts`, plus arbitrary extension properties. The compatibility
adapter aligns the concept without delegating legacy package input to the
narrower governance identity schema. Nested package extensions do not acquire
generalized change authority.

Scanner hardening preceded Change Governance integration. The implemented
boundary is covered by base-vs-head mutation tests, source/package schema
mirror tests, and strict generalized-change tests.

## Consequences

Cross-domain reuse is possible without expanding the stable core. Preserving a
frozen package projection avoids an unapproved 1.x narrowing, at the cost of an
explicit adapter at that input boundary. Any future migration of nested package
changes to strict generalized semantics requires a separately versioned,
human-approved compatibility transition.
