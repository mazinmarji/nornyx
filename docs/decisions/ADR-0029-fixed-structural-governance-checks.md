# ADR-0029 - Fixed Structural Governance Checks

## Status

Accepted for implementation in the governance-program branch.

## Context

The closed rule language safely handles local predicates, collection joins,
and reference checks. Relational controls such as author/approver separation,
revision-bound evidence, approval invalidation, exception expiry, and lifecycle
transitions need comparisons across governed objects. Extending the pack rule
language with arbitrary expressions would violate the language and security
boundaries.

## Decision

Nornyx will provide a small, versioned catalog of fixed structural check IDs.
Modules may select those IDs as data. Each check is implemented in reviewed
core Python, has a stable input contract and diagnostic set, is deterministic
for an explicit validation time, and has no network, subprocess, connector,
credential, or source-analysis behavior.

Unknown IDs fail pack schema validation. Checks cannot weaken one another,
override denials, grant approval, mutate input, or execute remediation.
Composition uses ordered set union, so adding a module can only retain or add
checks. Core safety invariants and pack integrity are outside the exception
mechanism.

Time-sensitive checks receive an explicit `as_of` value from the caller. The
validator never samples wall-clock time inside a rule or during deterministic
composition. CLI validation may supply the current UTC time as run provenance,
while tests and APIs can pin it.

## Consequences

Relational governance remains expressive enough for the program without
turning packs into programs. Adding a new structural check requires a reviewed
code and schema change, tests, diagnostics, documentation, and compatibility
analysis. Pack authors gain less flexibility than an expression engine, which
is an intentional security boundary.

