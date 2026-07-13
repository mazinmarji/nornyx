# ADR-0028 - Bounded Governance Block Schemas

## Status

Accepted for implementation in the governance-program branch.

## Context

Governance modules need to define the shape of optional blocks such as
`changes`, `exceptions`, and `architecture` without adding those domains to
the twelve stable core concepts. The current pack schemas can declare required
block names and rules, but cannot bind a block to a schema. Accepting arbitrary
inline JSON Schema would create an unbounded validation language and expose
remote references, recursive schema bombs, custom formats, and inconsistent
composition.

## Decision

Modules may declare a bounded list of block-schema bindings. A binding names a
top-level block and a stable schema identity. The identity must resolve from
the schemas bundled in the installed Nornyx distribution. Network retrieval,
filesystem references, dynamic references, custom formats, callbacks, and
inline schemas are rejected.

The loader validates every referenced schema against a reviewed JSON Schema
2020-12 subset. The subset permits structural validation and local bundled
`$ref` values, rejects remote references and dynamic execution surfaces, caps
schema size, depth, nodes, references, and composed bindings, and detects
reference cycles before document validation.

Composition is monotonic. Equal block/schema bindings merge idempotently. Two
different schemas claiming the same block fail with a stable conflict
diagnostic. A selected module's block schema validates only that block; it does
not reinterpret unrelated document content or mutate the stable core schema.

Third-party project and organization modules may select only schema identities
that are already bundled and reviewed. Adding a new schema requires a Nornyx
code review and release; a data pack cannot smuggle a validator into the
runtime.

## Consequences

Nornyx gains a minimum data-only extension mechanism without a general-purpose
policy language. Optional governance domains remain outside the stable core,
schema behavior is deterministic and wheel-installable, and old contracts that
do not select modules retain their current meaning. The tradeoff is deliberate:
external pack authors cannot invent new validation languages or ship arbitrary
schemas in v1.

