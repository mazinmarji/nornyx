# ADR-0043 — M2-E runtime adapter conformance

- Status: Accepted (implementation candidate; release remains owner-controlled)
- Date: 2026-08-03
- Decision owner: human repository owner
- Relates to: ADR-0036, ADR-0039, ADR-0040, ADR-0041, ADR-0042

## Context

ADR-0039 milestones M2-A through M2-D delivered the supported adapter package
`nornyx-agentic-adapters`: a framework-neutral enforcement boundary
(`enforce()`), a CrewAI submodule, a LangGraph submodule, and a legacy
compatibility shim. Every framework submodule *declares* what it governs
through a `CoverageInventory` of `SurfaceCoverage` entries marked `wrapped`,
`unsupported`, or `unwrapped`.

That declaration is currently unverified at runtime. A `CoverageInventory`
entry is a string in a dataclass. Nothing executes the named framework path and
checks that the adapter actually evaluated one authorization, actually withheld
execution on denial, or actually recorded schema-valid evidence in the right
order. The declaration and the behavior can drift silently, and the drift would
surface only as a false Tier 2 claim.

The repository already contains a *static* adapter conformance artifact —
`nornyx.adapter_conformance.v0.7` (`docs/44_NORNYX_ADAPTER_CONFORMANCE_v0_7.md`,
`nornyx.connector_runtime.build_adapter_conformance_report()`,
`schemas/adapter_conformance_report.schema.json`). It validates declared
adapter/connector *contract shape* with execution explicitly disabled. It is a
statement about a document, not about a running adapter. It answers a different
question and must keep answering it.

The gap M2-E closes is therefore narrow and specific: **execute the real
supported adapter paths under the exact declared framework versions, observe
what actually happens, and emit reproducible machine-checkable evidence that
the declared coverage matches observed behavior.**

## Decision

Add an executable runtime adapter-conformance kit to the
`nornyx-agentic-adapters` distribution, as a new subpackage
`nornyx_agentic_adapters.conformance`.

### Distinct identity — v0.7 is not repurposed

M2-E introduces a new, independently versioned report identity:

- schema id: `nornyx.agentic_runtime_conformance.v1`
- schema version: `1.0`

`nornyx.adapter_conformance.v0.7` keeps its exact current meaning, schema,
producer function, and callers. M2-E does not read it, extend it, alias it, or
change it. The two are related only by subject matter:

| | `nornyx.adapter_conformance.v0.7` | `nornyx.agentic_runtime_conformance.v1` |
|---|---|---|
| Question | Is the declared adapter/connector contract well-formed? | Does the installed adapter behave as its coverage inventory declares? |
| Execution | Explicitly disabled | Required — real framework execution |
| Produced by | `nornyx` core (`connector_runtime`) | `nornyx-agentic-adapters` |
| Subject | A document | An installed adapter build + exact framework version |

M2-E is implemented entirely inside the adapter distribution. It requires **no
core change and no SPI change**: every primitive it needs (`Authorizer`,
`EvidenceRecorder`, `RuntimeOccurrence`, `validate()`) is already public. Option
2 (an additive static↔runtime bridge) and option 3 (a core change) from the
milestone brief were both rejected as unnecessary; see *Rejected alternatives*.

### Claim boundary

The conformance kit is bound by ADR-0040 Tier 2 and states so in every report:

- **Cooperative Tier 2, declared wrapped surfaces only.**
- Conformance is behavior observed under the exact declared adapter, framework,
  Nornyx, SPI, and Python versions recorded in the report — nothing else.
- Conformance does not authenticate agents or approvers.
- Conformance does not prove a recorded runtime event is true; it proves the
  event stream is schema-valid and consistently bound.
- Conformance does not prevent bypass. Bypass remains possible and is reported
  as an explicit negative control that is *outside* declared coverage — never
  as a path that was "prevented".
- Conformance never implies whole-application coverage.
- Conformance enables no live connector, no external network, no model, and
  no external execution. A guarded run permits loopback; see the accepted
  limitations below.
- Conformance establishes no Tier 3 assurance.

A conformance result can never convert an `unsupported` or `unwrapped` surface
into a `wrapped` one. Unsupported surfaces are executed only to demonstrate that
they fail closed, and are reported as unsupported.

### Public API (frozen)

Exported from `nornyx_agentic_adapters.conformance`:

- Constants: `CONFORMANCE_SCHEMA_ID`, `CONFORMANCE_SCHEMA_VERSION`,
  `ASSURANCE_TIER`, `LIMITATIONS`, `NON_GOALS`.
- Enums: `CaseClassification` (`governed`, `unsupported_surface`,
  `bypass_control`, `distribution_boundary`); `CaseOutcome` (`pass`, `fail`,
  `not_representable`); `RunOutcome` (`pass`, `fail`); `SuiteOutcome` (`pass`,
  `fail`, `unavailable`); `ExecutionPath` (`native`, `direct`, `boundary`);
  `EventOrder` (`recorded`, `normalized`); `EvidenceValidation` (`pass`,
  `fail`, `not_applicable`).
- Frozen dataclasses: `CountCheck`, `OccurrenceSummary`, `CaseResult`,
  `SuiteResult`, `RunSafety`, `ConformanceReport`.
- Functions: `run_conformance()`, `available_suites()`, `validate_report()`,
  `load_report_schema()`, `serialize()`, `write_report()`.

`CaseOutcome.not_representable` is deliberately a third state, neither a pass
nor a skip. It records a case that **cannot exist** on the surface it names —
the surface structurally cannot reach the outcome — and it must cross-reference
the case that does prove the behavior. Without a distinct state, such a gap
would have to be either silently omitted (hiding it) or reported as a skip
(implying it was environmental and might pass elsewhere).

The report schema is bundled as package data and validated by
`validate_report()`, which is strict: `additionalProperties: false` throughout,
closed enums for every status, and required version fields.

Entry point: `python -m nornyx_agentic_adapters.conformance`. Exit codes are
`0` (every required case conformed), `1` (observed nonconformance), `2`
(invalid configuration or usage). The command opens no external network, loads
no credentials, calls no external model, and executes no connector; a guarded
run permits loopback (see the accepted limitations).

A run fails when a case fails, when a required framework is unavailable, when
the selection produced no case at all — it verified nothing — or when the run's
guard blocked an outbound connection or a process spawn. The guard raises into
the case that made the call, but that raise alone cannot be relied on: a
framework executor may swallow it, and CrewAI's ReAct loop treats a tool error
as recoverable. The two blocked counts are reported separately, because a
blocked local process spawn is not an outbound attempt and one number would
misdescribe whichever it was not.

### Determinism rules

The report must be byte-identical across repeated runs on one platform and free
of environment-specific noise. Three concrete hazards are handled explicitly,
each discovered by measurement rather than assumed:

1. **LangGraph task ids are process-random.** `Runtime.execution_info.task_id`
   differs on every process. Raw occurrence ids are therefore *never* placed in
   the report. Only determinism-safe derived facts are reported: the count of
   distinct occurrence ids, the sorted set of attempt numbers, and whether any
   occurrence identity collided.
2. **CrewAI's native executor may retry a failed tool call internally.** The
   number of authorization evaluations on the native denial path is therefore
   framework-controlled, not adapter-controlled. Counts are reported as a
   `CountCheck` carrying an explicit assertion kind — `exact` (observed value
   recorded) or `at_least` (observed value omitted, with a stated reason) — so
   the report never presents a framework-controlled number as a stable
   adapter guarantee.
3. **Wall time, absolute paths, and environment.** The kit uses the contract's
   bound `decision_at`, never a wall clock; it emits no filesystem path; and it
   sorts every collection with a stable key.

### Self-contained execution

The kit ships its own governance contract fixture as package data. It resolves
that fixture through `importlib.resources` against its own package, never
through a repository-relative path. This is what allows conformance to run from
an installed wheel outside every source root — the property that makes the
result meaningful for a consumer rather than only for this monorepo.

### Supported surfaces exercised

Runtime cases execute the real supported paths only:

- Framework-neutral: `enforce()` — allow, deny, approval-required,
  evaluate-error, recorder-error, `on_decision`-error, action-error.
- CrewAI: the synchronous `BaseTool._run` path reached through native
  `Crew.kickoff()` ReAct execution, driven by a deterministic offline LLM.
- LangGraph: synchronous `StateGraph` node execution through real
  `graph.invoke()`, including native retry, loop, parallel branches, interrupt,
  and checkpoint resume.

No surface is wrapped merely to satisfy a conformance case. M2-E adds no
LangGraph async or durable-resume capability, no graph topology ownership, no
subgraph or ToolNode interception, and no CrewAI agent, task, delegation, or
handoff coverage. These stay declared `unsupported`/`unwrapped` and are tested
only for honest fail-closed behavior.

### One behavioral correction

Conformance design surfaced a real inconsistency: on a wrapped CrewAI tool
whose action raises, the adapter recorded *no* observation at all, while the
LangGraph adapter records `runtime_failed` on the equivalent path. M2-E records
`runtime_failed` exactly once on the CrewAI failure path before re-raising.
This is additive evidence on a path that previously produced none; it weakens
no existing claim, and it makes the two supported adapters state failure the
same way.

## Rejected alternatives

- **Extend `nornyx.adapter_conformance.v0.7`.** Rejected: v0.7 means "validated
  with execution disabled". Overloading that identifier with runtime execution
  results would silently change the meaning of an existing published schema and
  of every consumer already reading it.
- **Add a core framework-neutral conformance primitive.** Rejected: nothing was
  missing. The core already exposes every primitive required, so a core change
  would have widened the core's public surface and its compatibility
  obligations for no capability gain.
- **Put the conformance kit in the test suite only.** Rejected: a consumer
  cannot run the repository's tests against their installed wheel. The
  milestone's value is a result a consumer can reproduce, which requires
  shipping the kit.
- **Report raw framework identifiers (task ids, timestamps).** Rejected:
  measured to be nondeterministic, and reproducibility is a stated requirement.

## Accepted limitations

Independent assurance raised these and they are accepted deliberately rather
than fixed, because fixing them would cost more than the risk they carry:

- **Suites evaluate every case before `--case` filtering is applied.** A
  filtered run therefore still executes the whole suite. This is a runtime cost,
  not a correctness problem: filtering removes results, it never invents them.
  Restructuring each suite around a case-id table is deferred.
- **A framework suite that fails to *import* is reported `unavailable`, the
  same outcome as a missing extra.** A genuine API drift is therefore
  distinguishable only by its stated reason. CI passes `--require` for both
  frameworks, and requiring a framework that was not selected is now an error,
  so an unavailable suite cannot pass silently there.
- **Importing the CrewAI suite sets three telemetry environment variables.**
  This is required to keep CrewAI offline and deterministic, and it must happen
  before the framework is first imported.
- **Whether the conformance job blocks a merge is branch-protection
  configuration**, which lives outside this repository's files. The job fails
  the workflow on a nonconforming case; making it a required check is an owner
  action.
- **The distribution suite runs outside the outbound guard.** It spawns a
  clean interpreter on purpose, to check the import boundary in a process that
  has imported nothing. Giving the guard an escape hatch for that child would
  have handed out a fully unguarded process, so the suite is excluded instead
  and `safety.guarded_suites` names exactly which suites were covered.
  Framework suite *modules* are also imported before the guard is installed, so
  a framework's own import-time behavior is outside the guarded window; only
  its case execution is covered.
- **The guard permits loopback.** `connect`, `create_connection` and
  `getaddrinfo` all allow `127.0.0.1`/`::1`/`localhost`, because a framework's
  local telemetry stack reaches loopback through more than one of them and
  blocking it would fail a run for something that never leaves the machine. A
  guarded run can therefore reach a service already listening on loopback. On
  the `create_connection` path the `connect` check still applies after
  resolution, so a `localhost` that resolved to an external address is blocked
  there; a raw `socket.connect("localhost", ...)` is resolved inside the OS
  call and gets no second Python-level check.
- **`OccurrenceSummary.collided` detects one specific shape**: two *different*
  logical operations recorded under one occurrence id. The per-case
  `distinct_occurrences` assertions cover the concrete collision scenarios; the
  field's description now states exactly what it detects.

## Consequences and non-goals

- The adapter distribution gains a new public subpackage, a bundled report
  schema, and a bundled contract fixture. The base package still imports no
  agent framework; framework suites remain behind their existing extras.
- `nornyx>=1.10,<2` is unchanged. The dependency floor is not raised.
- Framework pins (`crewai==1.15.4`, `langgraph==1.2.2`) are unchanged.
- The report format is versioned; `CONFORMANCE_SCHEMA_VERSION` is pinned by
  tests and changes only under the repository's versioning policy.
- Release classification is a minor, additive adapter feature. This ADR
  authorizes implementation only. No tag, no GitHub Release, and no package
  publication is part of it.
- A green conformance report is evidence about declared wrapped surfaces under
  exact pinned versions. It is not a security guarantee, not an attestation,
  and not a substitute for independent (Tier 3) runtime assurance.
