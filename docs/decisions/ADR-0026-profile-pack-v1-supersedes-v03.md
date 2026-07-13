# ADR-0026 - Profile Pack v1 Supersedes v0.3

## Status

Accepted and implemented in Nornyx 1.5.x.

## Context

The strict historical schema fixes `version: v0.3`, `core_surface: v0.2`, and
rejects additional fields. A complete v1 pack cannot conform without lying.

## Decision

Keep v0.3 frozen and add a separate `nornyx.profile_pack.v1` schema. Legacy
projection produces an exact v0.3 object plus a separate loss/provenance report.
The legacy object contains no marker field. Projection fails when a declared
must-preserve semantic would be omitted.

## Consequences

Historical validation remains stable, new semantics are versioned honestly,
and legacy API compatibility is explicit rather than a silent reinterpretation.
