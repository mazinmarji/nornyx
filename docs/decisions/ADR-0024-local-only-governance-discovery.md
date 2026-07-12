# ADR-0024 - Local-Only Governance Discovery

## Status

Accepted for specification; loader implementation deferred.

## Context

Remote loading and Python entry-point discovery would place network state or
third-party code installation on the governance trust path.

## Decision

Future discovery is local only: explicit path, project directory, configured
organization directory, then bundled data. URLs, network fetching, and Python
entry points are excluded. Paths are canonicalized and symlinked pack files are
rejected. Organization-tier content requires a committed lock.

## Consequences

Resolution can be deterministic, offline, and reviewable. Organizations can
still distribute approved files through their existing repository mechanisms.
