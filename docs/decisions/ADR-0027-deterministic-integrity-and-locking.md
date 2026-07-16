# ADR-0027 - Deterministic Integrity and Locking

## Status

Accepted and implemented in Nornyx 1.5.x.

## Context

Textual YAML hashing is sensitive to comments, order, and line endings. Existing
provenance locks also demonstrate how timestamps can destroy byte stability.

## Decision

Hash parsed pack content without `integrity` using compact sorted-key JSON,
UTF-8, and `ensure_ascii=False`. Profile locks contain no time fields and list
resolved entries deterministically. Identical inputs produce byte-identical
locks. Hash, version, source-tier, and missing-pack mismatches fail closed.

Composition preserves provenance per element and uses fixed layer, dependency,
identifier, and fragment ordering. Limits bound files, paths, and rule counts.

## Consequences

Integrity is cross-platform and reproducible. Provenance time belongs in
separate run evidence, not in deterministic resolution locks.
