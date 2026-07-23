# Changelog

All notable changes to `nornyx-agentic-adapters` are recorded here. This
package versions independently of the `nornyx` core package — see
[docs/COMPATIBILITY.md](docs/COMPATIBILITY.md).

## [Unreleased]

### Added

- ADR-0039 M2-B — a supported CrewAI adapter (`nornyx_agentic_adapters.crewai_adapter`,
  requires the `crewai` extra): `agent_identity_key`, `resolve_identity`,
  `make_governed_tool`, `METADATA`, `COVERAGE_INVENTORY`. Wraps CrewAI's only
  verified public extension point — subclassing `crewai.tools.BaseTool` and
  overriding `_run` — reached through `Crew.kickoff()`'s native executor.
  Agent invocation, task invocation, delegation, and handoff are declared
  `unsupported` in the coverage inventory rather than wrapped through
  undocumented CrewAI internals. Tested against real, pinned `crewai==1.15.4`
  objects (deterministic offline LLM, no network/subprocess).
- ADR-0039 M2-A — the adapter package foundation: `AdapterMetadata`,
  `CoverageInventory`/`SurfaceCoverage`/`SurfaceStatus`, `SurfaceBinding`/
  `validate_binding`, `enforce()`, `AdapterDenied`, `AdapterConfigurationError`,
  `UnsupportedSPIVersionError`, `MissingOptionalDependencyError`.
  Depends on `nornyx>=1.8,<2` and checks the installed
  `nornyx.agentic.SPI_VERSION` at import time. Ships no LangGraph
  implementation yet — see `docs/MIGRATION.md` for the planned sequence.
  Not yet released to PyPI; version remains a 0.1.0 candidate pending its own
  release gate (a separate, subsequently authorized milestone).
