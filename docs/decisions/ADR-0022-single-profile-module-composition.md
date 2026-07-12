# ADR-0022 - Single Profile and Additive Modules

## Status

Accepted for specification; implementation deferred.

## Context

Multiple profiles create ambiguous terminology, starter ownership, defaults,
and compatibility interactions. Reusable modules already provide composition.

## Decision

The MVP accepts zero or one primary profile plus zero or more governance
modules. Composition order is core, dependency-ordered modules, optional
profile, organization policy, project contract, then governed exceptions.

Denials, mandatory evidence, and mandatory approvals accumulate. Later layers
may tighten but not silently remove controls. No removal syntax exists. Invalid
or ambiguous composition fails closed. Multi-profile composition is deferred.

## Consequences

Starter identity remains unambiguous and safety is monotonic. A future demand
for overlays should first be tested as a module rather than a second profile.
