# Changelog

All notable changes to `nornyx-agentic-adapters` are recorded here. This
package versions independently of the `nornyx` core package — see
[docs/COMPATIBILITY.md](docs/COMPATIBILITY.md).

## [Unreleased]

### Added

- ADR-0039 M2-A — the adapter package foundation: `AdapterMetadata`,
  `CoverageInventory`/`SurfaceCoverage`/`SurfaceStatus`, `SurfaceBinding`/
  `validate_binding`, `enforce()`, `AdapterDenied`, `AdapterConfigurationError`,
  `UnsupportedSPIVersionError`, `MissingOptionalDependencyError`.
  Depends on `nornyx>=1.8,<2` and checks the installed
  `nornyx.agentic.SPI_VERSION` at import time. Ships no CrewAI or LangGraph
  implementation yet — see `docs/MIGRATION.md` for the planned sequence.
  Not yet released to PyPI; version remains a 0.1.0 candidate pending its own
  release gate (a separate, subsequently authorized milestone).
