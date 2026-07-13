# ADR-0023 - Closed Declarative Rule Language

## Status

Accepted and implemented in Nornyx 1.5.x.

## Context

Prose validation rules imply enforcement without providing it. A general
expression language would create an execution and auditability risk.

## Decision

Rules use the closed operators and bounded path grammar in the v1 schema.
`when` collection traversal is existential; `require` traversal is universal
and fail-closed for empty or wrong-typed required collections. Unknown
operators and malformed paths are load-time errors.

No regex, script, template, function, variable, import, arbitrary expression,
or pack-defined operator is permitted. Adding an operator requires an ADR and
security, determinism, diagnostic, and resource-budget tests.

## Consequences

Rules remain inert data with predictable diagnostics. Relational joins and
other unsupported semantics stay in reviewed core checks or remain deferred.
