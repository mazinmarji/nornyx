# Changelog

All notable changes to `nornyx-agentic-adapters` are recorded here. This
package versions independently of the `nornyx` core package — see
[docs/COMPATIBILITY.md](docs/COMPATIBILITY.md).

## [Unreleased]

### Added

- ADR-0043 M2-E: `nornyx_agentic_adapters.conformance`, an executable runtime
  adapter-conformance kit. Runs the real supported adapter paths under the
  exact declared framework versions and emits a deterministic report
  identified by `nornyx.agentic_runtime_conformance.v1` (format version 1.0),
  validated against a schema bundled in this distribution. Public surface:
  `run_conformance`, `available_suites`, `validate_report`,
  `load_report_schema`, `serialize`, `write_report`, and the typed result
  model. Entry point: `python -m nornyx_agentic_adapters.conformance`, exiting
  `0` conformant, `1` nonconformant or a required framework unavailable, `2`
  invalid configuration or internal error.
- First-party suites for the framework-neutral `enforce()` boundary, the
  CrewAI synchronous tool surface driven through native `Crew.kickoff()`, the
  LangGraph synchronous node surface driven through native `graph.invoke()`
  (retry, loop, parallel, interrupt, checkpoint resume), the
  distribution/import boundary, coverage-inventory integrity, evidence
  validity, and bypass negative controls.
- The distribution now ships package data: the report schema and a governance
  contract fixture, resolved through `importlib.resources`, so conformance
  runs from an installed wheel outside every source root.

### Changed

- `crewai_adapter.make_governed_tool` records a `runtime_failed` observation
  exactly once when an authorized action raises, before re-raising. Previously
  that path recorded nothing, while the LangGraph adapter recorded
  `runtime_failed` on the equivalent path. `enforce()` invokes the action only
  on ALLOW, so a denial can never produce this event.
- `jsonschema>=4.21` is now a direct dependency: the conformance kit imports it
  to validate its own report. It was already guaranteed transitively by
  `nornyx`, and the `nornyx>=1.10,<2` floor is unchanged.
- Documentation: the README's SPI column now reads `1.x (tested with 1.1 and
  1.2)`, matching `docs/COMPATIBILITY.md` and the import-time check, which
  asserts the SPI *major* only. A truncated sentence about import-time pin
  enforcement is repaired.

### Assurance remediations

Independent review of the candidate found three claim-integrity defects in the
kit, all fixed before this entry:

- The CrewAI denial case asserted only that evidence validation *failed*, while
  its reported detail named a specific cause it never observed. Any unrelated
  evidence regression on that path would have produced the same reassuring
  prose. Cases now record the validator's actual diagnostic codes, and that
  case pins `AN_EVT_REPLAY` exactly.
- `safety.network_used` was a dataclass default pinned to `false` by the
  schema — unfalsifiable, despite a docstring claiming it was observed. A
  guard now wraps every executing suite, `network_used` is derived from its
  count of blocked outbound attempts, and a new `network_guard_active` field
  states whether a guard was in place at all.
- `decision_precedes_action` named a stronger property than it measured (it
  compares recorded events, not the action) and was vacuously `true` for cases
  that recorded nothing. Renamed to `decision_precedes_observation`, documented
  in the schema, and now absent rather than `true` when no observation exists.

Also: requiring a framework that was not selected, and selecting a case id that
matches nothing, are now errors rather than silent no-ops that could exit `0`;
an empty stream reports `not_applicable` rather than a validation `pass`; the
interrupt/resume case counts the executions it actually performed; and the
CrewAI bypass control now bypasses a real governed tool rather than a bare
counter.

### Known limitations

- On the CrewAI tool surface, a denied call retried by CrewAI's own executor
  produces repeated identical decision batches that the evidence validator
  flags as replay, because legacy-mode events carry no occurrence identity.
  Fail-closed behavior is unaffected (zero executions); the conformance report
  states `evidence_validation: fail` for that case rather than claiming a
  validating stream. See `docs/COMPATIBILITY.md`.
- `APPROVAL_REQUIRED` is not representable on the CrewAI tool surface: the
  governed tool issues a `CapabilityRequest`, and that effect is reachable in
  this core only via a zone-crossing request. The report records the case as
  `not_representable` and cross-references the framework-neutral case that
  does prove the behavior.

## [0.2.0] - 2026-07-30

### Added

- ADR-0039 M2-C: `nornyx_agentic_adapters.langgraph` supports synchronous
  StateGraph node invocation against exact `langgraph==1.2.2`. Public
  `Runtime.execution_info` maps node surfaces, task ids, and native attempts to
  runtime-events 1.1 operation/occurrence/attempt identity. Native retry,
  loops, parallel branches, interrupt, checkpoint resume, denial, failure, and
  installed-wheel behavior have dedicated tests.
- LangGraph interrupt control flow is propagated as an incomplete occurrence
  attempt rather than recorded as `runtime_failed`; resume offsets the reset
  framework attempt counter from the validated cumulative evidence prefix.

### Changed

- The adapter candidate advances to 0.2.0, requires `nornyx>=1.10,<2` / SPI
  1.1, and retains exact CrewAI 1.15.4 and LangGraph 1.2.2 pins.

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
  This foundation was initially prepared as a 0.1.0 candidate and is included
  in the first published adapter release, 0.2.0.
