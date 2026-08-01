# nornyx-agentic-adapters

Supported framework adapters for the Nornyx [`nornyx.agentic`](https://github.com/mazinmarji/nornyx/blob/main/docs/decisions/ADR-0039-agentic-integration-sdk.md)
authorization SPI. This package is where framework-specific interception,
argument normalization, and executor wrapping live — the core `nornyx` package
(`SPI_VERSION == "1.2"` as published in Nornyx 1.11.0; Nornyx 1.10.0 published
SPI 1.1) contains no agent framework and implements no framework glue.

## Status

**M2-A (foundation), M2-B (CrewAI), and M2-C (LangGraph) have landed.** M2-A ships the public
contract — adapter metadata, a coverage-inventory type, the
declarative-binding primitive, and the `enforce()` evaluate/record/execute
boundary — that framework-specific adapters build on. M2-B adds a supported
CrewAI adapter on top of it. M2-C adds occurrence-aware synchronous LangGraph
node governance on the runtime-events 1.1 contract defined by ADR-0042.

| Component | Status |
| --- | --- |
| Public contract (`AdapterMetadata`, `CoverageInventory`, `SurfaceBinding`, `enforce`) | Available |
| CrewAI adapter (`nornyx_agentic_adapters.crewai_adapter`) | Available — tool invocation only, see Coverage below |
| LangGraph adapter (`nornyx_agentic_adapters.langgraph`) | Available — synchronous StateGraph nodes only, see Coverage below |
| Legacy `integrations/` import-name collision | Resolved — the reference kernel is now `nornyx_reference_adapters`, so this distribution owns `nornyx_agentic_adapters` unambiguously ([MIGRATION.md](docs/MIGRATION.md)) |
| Legacy `integrations/` behavioural compatibility shim | Pending (ADR-0039 M2-D; the existing reference kernel's own logic is unaffected by this package) |

## Install

```bash
pip install nornyx-agentic-adapters
```

Framework extras:

```bash
pip install "nornyx-agentic-adapters[crewai]"    # CrewAI adapter — available
pip install "nornyx-agentic-adapters[langgraph]" # LangGraph adapter — available; exact 1.2.2 pin
```

Requires Python 3.10–3.13 and `nornyx>=1.10,<2`.

## CrewAI adapter

```python
from nornyx_agentic_adapters import SurfaceBinding
from nornyx_agentic_adapters.crewai_adapter import make_governed_tool, resolve_identity

identity_ref = resolve_identity(authorizer, agent)  # maps agent.role -> a declared Nornyx identity

tool = make_governed_tool(
    name="governed_reader",
    description="Read governed context.",
    binding=SurfaceBinding(
        surface="tool:governed_reader",
        identity_ref=identity_ref,
        capability_ref="read_governed_context",
    ),
    authorizer=authorizer,
    context=context,
    recorder=recorder,
    mission_id=mission_id,
    action=lambda: "the tool's real work",
)
# Attach `tool` to a crewai.Task like any other BaseTool; the wrapped action
# never runs unless the SPI evaluates ALLOW for the declared binding.
```

**Coverage (cooperative Tier 2 — declared, wrapped surfaces only):** the only
verified CrewAI extension point is subclassing `crewai.tools.BaseTool` and
overriding the **synchronous** `_run`, reached through `Crew.kickoff()`'s
native executor. Coverage is the sync `_run` path only. **Asynchronous tool
execution (`arun`/`_arun`) is not a governed surface:** this adapter does not
override `_arun`, so CrewAI's async path hits the inherited
`BaseTool._arun`, which raises `NotImplementedError` — the wrapped action never
runs and no observation is recorded. It is declared `async_tool_invocation` /
`unsupported` in `crewai_adapter.COVERAGE_INVENTORY`; do not assume synchronous
tool coverage extends to async execution. Agent invocation, task invocation,
delegation, and handoff likewise have no verified, stable public CrewAI hook
distinct from tool-level interception and are declared `unsupported` rather than
wrapped through undocumented internals. Bypassing the adapter — calling the
underlying action directly instead of through the governed tool — bypasses
enforcement entirely; see Assurance boundary below.

**Structured tool arguments.** `make_governed_tool` accepts an optional
`args_schema` (a CrewAI-compatible pydantic `BaseModel` subclass) describing the
tool's inputs. When supplied it is exposed to CrewAI so the executor validates
and passes structured arguments through the governed `_run` — validated
arguments reach `action` only after an ALLOW decision, never bypassing
authorization; DENY/APPROVAL_REQUIRED still prevent execution regardless of
valid input. Omit it for a no-argument governed tool (unchanged default). The
schema describes tool inputs only and never carries the authorizer, recorder,
or binding. An `args_schema` that is not a pydantic `BaseModel` subclass fails
closed at construction with `AdapterConfigurationError`. This is not arbitrary
CrewAI-tool wrapping: the API constructs a governed tool from an explicit
`action` and optional `args_schema`.

## LangGraph adapter

```python
from nornyx.agentic import EvidenceRecorder
from nornyx_agentic_adapters import SurfaceBinding
from nornyx_agentic_adapters.langgraph import make_governed_node

recorder = EvidenceRecorder.for_occurrences(
    authorizer, context, producer_id="my-graph"
)
governed_node = make_governed_node(
    binding=SurfaceBinding(
        surface="node.read",
        identity_ref="identity.reader",
        capability_ref="read_governed_context",
    ),
    authorizer=authorizer,
    context=context,
    recorder=recorder,
    mission_id="GOAL-001",
    action=read_node,
)
builder.add_node("read", governed_node)
```

The adapter maps public LangGraph `task_id` and `node_attempt` metadata to
Nornyx occurrence and attempt identity. It supports native retry, loop visits,
parallel branches, interrupt, and checkpoint resume. A normal exception records
`runtime_failed`; LangGraph interrupt control flow remains an incomplete attempt
and is not misreported as failure. Resume uses the validated cumulative recorder
prefix to offset LangGraph's reset attempt counter.

Coverage is synchronous StateGraph node invocation only. Async nodes,
remote/distributed execution, graph-topology ownership, and implicit subgraph or
ToolNode interception are declared unsupported or unwrapped.

## Assurance boundary (ADR-0040)

This package provides **cooperative Tier 2** authorization over **declared,
wrapped surfaces only**:

- Bypassing an adapter bypasses enforcement — there is no gateway, sandbox, or
  mandatory interception.
- A `CoverageInventory` names exactly which surfaces an adapter wraps; it
  never implies whole-application coverage.
- Adapters do not authenticate agents or approvers.
- Adapters do not attest that a recorded runtime event is *true* — evidence is
  contract-state binding only, not runtime proof.
- Nothing here establishes Tier 3 (independent runtime assurance); that
  requires an external enforcement/attestation system Nornyx neither provides
  nor verifies.

Every Tier 2 claim about this package should carry the qualifier
"cooperative, declared surfaces only."

`EvidenceRecorder` (core, `nornyx.agentic`) is internally lock-protected.
Supported builtin subclasses remain accepted for public compatibility and are
immediately canonicalized to exact plain builtins without invoking subclass
overrides; only those detached exact values can influence recorder state or
evidence output. Arbitrary non-`dict` `Mapping` fields remain an explicit
callback boundary outside the recorder lock — see ADR-0041 and
`docs/COMPATIBILITY.md`. These adapters already pass exact builtins, so their
legacy CrewAI evidence output remains compatible. Occurrence-aware recording is
an additive SPI 1.1 capability used by the LangGraph adapter. SPI 1.2 adds the
framework-neutral `Authorizer.state` construction snapshot; it changes no
adapter authorization or occurrence behavior.

## Versioning

`nornyx-agentic-adapters` has its own independent SemVer, separate from the
`nornyx` core package's version. It declares the `nornyx.agentic.SPI_VERSION`
major version it supports and asserts compatibility at import time — an
incompatible core SPI major version raises `UnsupportedSPIVersionError`
immediately, rather than failing later with a confusing error.

| This package | `nornyx` | SPI | CrewAI | LangGraph | Python |
| --- | --- | --- | --- | --- | --- |
| 0.1.x | >=1.8,<2 | 1.0 | 1.15.4 | Not implemented | 3.10–3.13 |
| 0.2.x | >=1.10,<2 | 1.1 | 1.15.4 (only tested version) | 1.2.2 (only tested version) | 3.10–3.13 |

Framework version pins are intentionally narrow: they name the only version
of each framework this package has been tested against. A wider range is not
claimed until new test evidence supports it. The CrewAI pin is **enforced at
import time**, not merely declared. Importing
Both framework submodules enforce their exact installed distribution version.
For example, `nornyx_agentic_adapters.crewai_adapter` distinguishes three cases:

- **CrewAI missing** — raises `MissingOptionalDependencyError` naming the
  `pip install nornyx-agentic-adapters[crewai]` remedy.
- **CrewAI installed but not the supported version** (or missing/malformed
  version metadata) — raises `AdapterConfigurationError` immediately, naming the
  installed version and the required `crewai==1.15.4`; it never runs against an
  untested CrewAI.
- **CrewAI == 1.15.4** — imports and operates normally.

## Design

- `AdapterMetadata` — declares one adapter's name/version, supported SPI
  major version, and tested framework/nornyx ranges.
- `SurfaceBinding` / `validate_binding` — a closed, adapter-declared mapping
  from one framework surface to a Nornyx identity and capability. Built from
  an adapter's own static configuration, never from raw framework arguments
  (commands, paths, URLs, tool payloads).
- `CoverageInventory` / `SurfaceCoverage` / `SurfaceStatus` — a deterministic,
  closed record of every surface an adapter declares, tagged `wrapped`,
  `unsupported`, or `unwrapped`.
- `enforce(authorizer, request, *, context, recorder, mission_id, action)` —
  the single enforcement boundary: evaluates `request` against the core
  `Authorizer`, records the decision's event intents, and only on `ALLOW`
  invokes `action` and returns its result. On `DENY`/`APPROVAL_REQUIRED` (or
  any unexpected error), `action` is never invoked and the call fails closed.
- `AdapterDenied` — raised by `enforce()` on a non-`ALLOW` decision; carries
  the core `Decision` unmodified.
- `AdapterConfigurationError` — raised for a malformed or incomplete
  adapter-owned declarative mapping.
- `langgraph.make_governed_node(...)` — occurrence-aware synchronous node
  enforcement using public LangGraph execution metadata only.

See [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) for the full compatibility
matrix and [`docs/MIGRATION.md`](docs/MIGRATION.md) for the planned migration
path from the existing `integrations/` reference kernel.
