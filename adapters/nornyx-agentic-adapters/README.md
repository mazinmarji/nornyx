# nornyx-agentic-adapters

Supported framework adapters for the Nornyx [`nornyx.agentic`](https://github.com/mazinmarji/nornyx/blob/main/docs/decisions/ADR-0039-agentic-integration-sdk.md)
authorization SPI. This package is where framework-specific interception,
argument normalization, and executor wrapping live — the core `nornyx` package
(`SPI_VERSION == "1.0"`, published from Nornyx 1.8.0) contains no agent
framework and implements no framework glue.

## Status

**This is the M2-A foundation release.** It ships the public contract —
adapter metadata, a coverage-inventory type, the declarative-binding
primitive, and the `enforce()` evaluate/record/execute boundary — that
framework-specific adapters build on. **It does not yet contain a CrewAI or
LangGraph implementation.** Those land in separate, subsequent releases
(ADR-0039 M2-B and M2-C).

| Component | Status |
| --- | --- |
| Public contract (`AdapterMetadata`, `CoverageInventory`, `SurfaceBinding`, `enforce`) | Available |
| CrewAI adapter (`nornyx_agentic_adapters.crewai`) | Pending |
| LangGraph adapter (`nornyx_agentic_adapters.langgraph`) | Pending |
| Legacy `integrations/` compatibility shim | Pending (existing reference kernel unaffected by this package) |

## Install

```bash
pip install nornyx-agentic-adapters
```

Framework extras (**not yet functional** — see Status above; installing them
now only pulls in the pinned framework package, since no framework-specific
adapter module exists yet in this release):

```bash
pip install "nornyx-agentic-adapters[crewai]"
pip install "nornyx-agentic-adapters[langgraph]"
```

Requires Python 3.10–3.13 and `nornyx>=1.8,<2`.

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

## Versioning

`nornyx-agentic-adapters` has its own independent SemVer, separate from the
`nornyx` core package's version. It declares the `nornyx.agentic.SPI_VERSION`
major version it supports and asserts compatibility at import time — an
incompatible core SPI major version raises `UnsupportedSPIVersionError`
immediately, rather than failing later with a confusing error.

| This package | `nornyx` | SPI | CrewAI | LangGraph | Python |
| --- | --- | --- | --- | --- | --- |
| 0.1.x | >=1.8,<2 | 1.0 | 1.15.4 (only tested version) | 1.2.2 (only tested version) | 3.10–3.13 |

Framework version pins are intentionally narrow: they name the only version
of each framework this package has been tested against. A wider range is not
claimed until new test evidence supports it.

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

See [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) for the full compatibility
matrix and [`docs/MIGRATION.md`](docs/MIGRATION.md) for the planned migration
path from the existing `integrations/` reference kernel.
