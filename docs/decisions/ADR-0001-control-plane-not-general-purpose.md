# ADR-0001: Nornyx Starts as a Control-Plane Language

## Status

Accepted for v0.1.

## Context

A full general-purpose language would require a compiler, package manager, standard library, debugger, LSP, runtime, ecosystem, and adoption strategy. That is too large for the initial product.

## Decision

Nornyx v0.1 will be an executable AI-engineering specification and generator. It will govern existing languages and tools rather than replace them.

## Consequences

Positive:

- faster MVP;
- lower adoption friction;
- interoperability with current ecosystems;
- immediate value through artifact generation.

Negative:

- some people may call it a DSL/config language;
- broader language ambitions are deferred.
