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
- **This 0.1.x release ships no framework-specific adapter module yet** (see
  the README's Status table) — the CrewAI/LangGraph columns above describe
  what the *future* `[crewai]`/`[langgraph]` extras will support once M2-B/C
  land, recorded here now so the compatibility contract is fixed before
  implementation.

## Minor-compatible vs. breaking changes

Following the same rule ADR-0039 applies to the core SPI:

- **Minor-compatible**: widening a framework's tested version range with new
  evidence; adding a new optional field to a public dataclass; adding a new
  `SurfaceStatus` value; adding a new framework-specific submodule.
- **Breaking**: narrowing a supported range; removing or renaming a public
  type/field; changing the meaning of an existing `SurfaceStatus` value;
  changing `enforce()`'s evaluate → record → execute ordering guarantee.
