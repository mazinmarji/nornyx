# ADR-0021 - Change Governance as a Module

## Status

Accepted; implementation is mandatory in governance-program Stage C.

## Context

Governed packages already contain a minimal `changes` list. Making Change a
stable core concept would revise frozen language schemas, while defining a new
shape per profile would fragment meaning.

## Decision

Change Governance will be a reusable declarative module. Its future shared
schema keeps governed-package `id`, `type`, and `expected_artifacts` compatible
and adds optional lifecycle fields. Core concepts remain unchanged.

The scanner-hardening work must merge before Change Governance integration.
That PR owns reconciliation with settled governed-package evidence, approvals,
schema, and examples. PR 1 adds no change schema or runtime behavior.

## Consequences

Cross-domain reuse is possible without expanding the stable core. Integration
is sequenced and testable, but implementation waits for the module loader and
composition engine.
