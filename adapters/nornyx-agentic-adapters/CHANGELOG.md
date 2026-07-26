# Changelog

All notable changes to `nornyx-agentic-adapters` are recorded here. This
package versions independently of the `nornyx` core package — see
[docs/COMPATIBILITY.md](docs/COMPATIBILITY.md).

## [Unreleased]

### Fixed

- **A delegated capability's `tool_invoked` observation now carries the
  authorizing delegation** (benchmark finding F2). When an identity held a
  capability only by delegation, the decision was correctly ALLOW and
  `capability_allowed` correctly carried `delegation_ref`, but the CrewAI
  adapter's post-success observation dropped it — so the evidence validator's
  possession check failed closed and reported a capability the actor does not
  hold. Delegation and validatable evidence were therefore mutually exclusive on
  the supported CrewAI path. `_GovernedTool._run` now reads
  `DecisionBasis(kind="delegation")` off the authorizing decision and passes
  `delegation_ref` to `record_observation`. The reference comes from the
  decision, never from the tool's caller-controlled arguments, and is absent when
  the capability is held directly. Exactly-once execution and fail-closed denial
  are unchanged.

### Added

- `enforce()` accepts an optional `on_decision` observation hook, called with the
  authoritative `Decision` after its intents are recorded and before any branch
  on the outcome. It lets an adapter read a decision's public `basis` without
  re-evaluating the request or reaching into internals. It cannot change the
  outcome; it runs on DENY as well as ALLOW; and an exception raised from it
  propagates before `action` is reached, so the boundary still fails closed.
  Omitting it is exactly the previous behavior.
- ADR-0039 M2-B — a supported CrewAI adapter (`nornyx_agentic_adapters.crewai_adapter`,
  requires the `crewai` extra): `agent_identity_key`, `resolve_identity`,
  `make_governed_tool`, `METADATA`, `COVERAGE_INVENTORY`. Wraps CrewAI's only
  verified public extension point — subclassing `crewai.tools.BaseTool` and
  overriding the **synchronous** `_run` — reached through `Crew.kickoff()`'s
  native executor. Agent invocation, task invocation, delegation, handoff, and
  **asynchronous tool invocation (`arun`/`_arun`)** are declared `unsupported`
  in the coverage inventory rather than wrapped through undocumented CrewAI
  internals. Tested against real, pinned `crewai==1.15.4` objects (deterministic
  offline LLM, no network/subprocess).
- `make_governed_tool` accepts an optional CrewAI-compatible pydantic
  `args_schema`, so governed tools may expose typed/structured arguments;
  validated arguments reach the wrapped `action` only after an ALLOW decision
  and never bypass authorization. Omitting it preserves the no-argument
  default. An invalid schema fails closed at construction with
  `AdapterConfigurationError`.
- The CrewAI submodule now enforces its `==1.15.4` compatibility pin at import
  time via installed-distribution metadata: an unsupported installed version, or
  missing/malformed version metadata, fails closed with
  `AdapterConfigurationError` (a missing distribution still raises
  `MissingOptionalDependencyError`).

### Changed

- Closed ADR-0039 M2-B audit findings: an explicit, reproducible Ruff lint
  contract (bounded `ruff>=0.16.0,<0.17` dev pin plus an explicit
  `[tool.ruff.lint] select`, so `ruff check .` no longer depends on Ruff's
  evolving defaults — audit F1); the coverage inventory and docs now classify
  async tool invocation as unsupported (F2); structured `args_schema` support
  (F3); import-time CrewAI version enforcement (F4); and the CrewAI CI job now
  forbids silent test skips and additionally installs the built adapter **wheel**
  (with the `[crewai]` extra) in a fresh environment to import the CrewAI module
  and run allowed/denied governed-tool smokes from outside all source roots (F5).
- ADR-0039 M2-A — the adapter package foundation: `AdapterMetadata`,
  `CoverageInventory`/`SurfaceCoverage`/`SurfaceStatus`, `SurfaceBinding`/
  `validate_binding`, `enforce()`, `AdapterDenied`, `AdapterConfigurationError`,
  `UnsupportedSPIVersionError`, `MissingOptionalDependencyError`.
  Depends on `nornyx>=1.8,<2` and checks the installed
  `nornyx.agentic.SPI_VERSION` at import time. Ships no LangGraph
  implementation yet — see `docs/MIGRATION.md` for the planned sequence.
  Not yet released to PyPI; version remains a 0.1.0 candidate pending its own
  release gate (a separate, subsequently authorized milestone).
