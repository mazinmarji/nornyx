# Compatibility matrix

| `nornyx-agentic-adapters` | `nornyx` (SPI) | SPI version | CrewAI | LangGraph | Python |
| --- | --- | --- | --- | --- | --- |
| 0.1.x | `>=1.8,<2` | 1.0 | `==1.15.4` | `==1.2.2` | 3.10–3.13 |

## Reading this table

- **`nornyx-agentic-adapters` version** follows its own independent SemVer,
  separate from `nornyx`'s.
- **`nornyx` (SPI)** is the core-package version range this adapter release
  depends on. `SPI_VERSION` (a separate, integration-contract version) is
  checked at import time — this package supports SPI major version `1`; an
  incompatible major version raises `UnsupportedSPIVersionError` immediately.
- **CrewAI / LangGraph** columns name the *exact, only tested version* of each
  framework, not a range. Framework version pins in this package are
  intentionally narrow: only the version actually exercised by this
  repository's test suite is declared supported. A wider range is not claimed
  until new test evidence justifies it — widening a pin without new tests
  would be a compatibility regression risk, not a convenience.
- **CrewAI (M2-B) is implemented; LangGraph (M2-C) is not yet** (see the
  README's Status table). The CrewAI column above is live: `[crewai]`
  installs `nornyx_agentic_adapters.crewai_adapter`, which wraps **synchronous**
  tool invocation only (see the README's Coverage note) — agent invocation,
  task invocation, delegation, handoff, and **asynchronous tool invocation
  (`arun`/`_arun`)** are declared `unsupported`, not silently omitted. Async is
  not governed: the adapter does not override `_arun`, so CrewAI's async path
  raises `NotImplementedError` and the wrapped action never runs. The LangGraph
  column describes what the *future* `[langgraph]` extra will support once M2-C
  lands, recorded here now so the compatibility contract is fixed before
  implementation.
- **The CrewAI pin is enforced at import time, not just declared.** Importing
  the CrewAI submodule fails closed on any unsupported configuration: a missing
  CrewAI distribution raises `MissingOptionalDependencyError`; an installed but
  non-`1.15.4` version — or missing/malformed version metadata — raises
  `AdapterConfigurationError`; only `crewai==1.15.4` imports and operates.

## Minor-compatible vs. breaking changes

Following the same rule ADR-0039 applies to the core SPI:

- **Minor-compatible**: widening a framework's tested version range with new
  evidence; adding a new optional field to a public dataclass; adding a new
  `SurfaceStatus` value; adding a new framework-specific submodule.
- **Breaking**: narrowing a supported range; removing or renaming a public
  type/field; changing the meaning of an existing `SurfaceStatus` value;
  changing `enforce()`'s evaluate → record → execute ordering guarantee.
