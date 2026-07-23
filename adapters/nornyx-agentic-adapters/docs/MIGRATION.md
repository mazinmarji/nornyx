# Migration status

**This document describes a plan, not a completed migration.** No migration
has happened yet. It is recorded here now, in the M2-A foundation release, so
the contract is fixed before the migration itself (ADR-0039 M2-D) is
implemented.

## What exists today, unaffected by this package

Nornyx's existing reference adapters live in the main `nornyx` repository
under `integrations/nornyx_agentic_adapters/` (added by AN-005 / ADR-0037).
That directory:

- is **not** part of the `nornyx` wheel;
- implements its own, hand-rolled framework-neutral decision logic
  (`GovernanceKernel`) that predates and duplicates what the `nornyx.agentic`
  SPI now formalizes;
- is **not touched by this package's 0.1.x release** — no code here migrates,
  wraps, deprecates, or removes it.

## What will change, in a future release (M2-D)

A subsequent, separately-audited milestone (ADR-0039 M2-D,
"Compatibility Shim Migration and Published-Package Proof") will:

1. Rewrite `GovernanceKernel`'s internals to delegate to
   `nornyx.agentic.authz.Authorizer` instead of its own hand-rolled logic,
   while preserving its existing public method signatures
   (`resolve_identity`, `check_capability`, `invoke_tool`,
   `request_delegation`, `request_handoff`/`complete_handoff`,
   `require_human_approval`, `record_zone_crossing`, `record_data_shared`) for
   backward compatibility.
2. Add a deprecation warning to the shim.
3. Publish an old-method → new-SPI-request mapping table here.
4. Keep the shim available for **at least one published Nornyx minor
   release** after the migration lands; removal is gated to no earlier than
   the *following* published minor release, and only after migration
   documentation and compatibility tests exist.

## Using this package today

Since no framework-specific adapter module exists yet in this 0.1.x release,
there is nothing to migrate *to* yet. Consumers of the existing
`integrations/nornyx_agentic_adapters/` reference code should continue using
it unchanged until M2-B (CrewAI) and M2-C (LangGraph) ship real,
supported adapters in this package, followed by M2-D's shim migration.
