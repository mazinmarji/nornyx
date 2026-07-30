# Migration status

**This document describes a plan, not a completed migration.** The behavioural
migration (ADR-0039 M2-D) has not happened yet. It is recorded here now so the
contract is fixed before the migration itself is implemented.

## Completed: the legacy reference tree's import name

The AN-005 reference adapters used to live at
`integrations/nornyx_agentic_adapters/` — the **same import name** as this
installed distribution. Any process that put `integrations/` on `sys.path`
silently rebound that name to the unpackaged legacy tree, and the failure
surfaced as an `ImportError` on a public name such as `AdapterDenied`.

| Before | After |
| --- | --- |
| `integrations/nornyx_agentic_adapters/` | `integrations/nornyx_reference_adapters/` |
| `from nornyx_agentic_adapters.governance_kernel import GovernanceKernel` | `from nornyx_reference_adapters.governance_kernel import GovernanceKernel` |
| `from nornyx_agentic_adapters.crewai_adapter import CrewAIGovernanceAdapter` | `from nornyx_reference_adapters.crewai_adapter import CrewAIGovernanceAdapter` |
| `from nornyx_agentic_adapters.langgraph_adapter import LangGraphGovernanceAdapter` | `from nornyx_reference_adapters.langgraph_adapter import LangGraphGovernanceAdapter` |
| `from nornyx_agentic_adapters.local_harness import ...` | `from nornyx_reference_adapters.local_harness import ...` |

`nornyx_agentic_adapters` now unambiguously means **this installed
distribution**. The rename breaks no published package: the `integrations/`
tree is excluded from the `nornyx` wheel by construction and has never been
published, so it was only ever reachable by a caller that added that directory
to `sys.path` itself. If you did that, update the module name as above.

No compatibility shim was left under the old name — republishing
`nornyx_agentic_adapters` from `integrations/` would recreate exactly the
collision this rename fixes.

## What exists today, unaffected by this package

Nornyx's existing reference adapters live in the main `nornyx` repository
under `integrations/nornyx_reference_adapters/` (added by AN-005 / ADR-0037).
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

CrewAI is supported (`nornyx_agentic_adapters.crewai_adapter`, M2-B, tool
invocation only — see README Coverage). LangGraph synchronous StateGraph nodes
are supported by `nornyx_agentic_adapters.langgraph` (M2-C).
Consumers of the existing `integrations/nornyx_reference_adapters/` reference
code for CrewAI may migrate to this package's `crewai_adapter` module now — and,
because of the rename above, the two can now coexist in one Python process.
LangGraph consumers should migrate guarded node construction to
`make_governed_node` and an occurrence-aware core recorder. The legacy
reference code remains unchanged until M2-D's separately reviewed shim
migration.
