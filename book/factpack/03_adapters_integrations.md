# FACT PACK 03 — Framework Adapters and Runtime Integrations

Audited at git HEAD `70d2b40` (merge of PR #56, "feat/m2d-legacy-compatibility-shim"), core package `nornyx` 1.11.0 (`/home/user/nornyx/pyproject.toml:7`), repo date context 2026-08-03. All paths are relative to `/home/user/nornyx` unless absolute. Status labels used throughout: **IMPLEMENTED** (code + tests exist in-repo), **GUIDANCE/ROADMAP** (documented intent, no enforcing code), **NON-GOAL** (explicitly declared out of scope).

---

## 1. The `nornyx-agentic-adapters` package (adapters/nornyx-agentic-adapters/)

### 1.1 Identity and metadata

| Fact | Evidence |
|---|---|
| Distribution name `nornyx-agentic-adapters`, version **0.2.0** | `adapters/nornyx-agentic-adapters/pyproject.toml:6-7` |
| Description: "Framework adapters (CrewAI, LangGraph) for the Nornyx nornyx.agentic authorization SPI" | `pyproject.toml:8` |
| Development Status :: **3 - Alpha**; Python 3.10–3.13 | `pyproject.toml:15,19-22` |
| Core dependency: `nornyx>=1.10,<2` | `pyproject.toml:24` |
| Optional extras: `crewai = ["crewai==1.15.4"]`, `langgraph = ["langgraph==1.2.2"]` — **exact `==` pins, verified** | `pyproject.toml:26-28` |
| Dev extra pins `ruff>=0.16.0,<0.17` with an explicit `[tool.ruff.lint] select = ["E4","E7","E9","F"]` (reproducibility fix for ADR-0039 M2-B audit finding F1) | `pyproject.toml:29-32,49-57` |
| Independent SemVer from core `nornyx`; package `__version__ = "0.2.0"` | `src/nornyx_agentic_adapters/__init__.py:32`; README "Versioning" §, `README.md:164-175` |
| Own CHANGELOG; 0.2.0 released **2026-07-30** as "the first published adapter release" | `adapters/nornyx-agentic-adapters/CHANGELOG.md:9,93-94` |

Compatibility matrix (verbatim source of the version claims), `adapters/nornyx-agentic-adapters/docs/COMPATIBILITY.md:3-6`:

```
| `nornyx-agentic-adapters` | `nornyx` (SPI) | SPI version | CrewAI | LangGraph | Python |
| 0.1.x | `>=1.8,<2`  | 1.0                        | `==1.15.4` | Not implemented | 3.10–3.13 |
| 0.2.x | `>=1.10,<2` | 1.x (tested with 1.1 and 1.2) | `==1.15.4` | `==1.2.2`   | 3.10–3.13 |
```

The pins are declared "intentionally narrow: they name the only version of each framework this package has been tested against. A wider range is not claimed until new test evidence supports it" (`README.md:177-180`; same rationale `COMPATIBILITY.md:38-43`).

### 1.2 Package layout and public API — IMPLEMENTED

Layout (`find` over `adapters/nornyx-agentic-adapters/`):

```
src/nornyx_agentic_adapters/
  __init__.py        # public contract exports; SPI-major check at import time
  _compat.py         # check_spi_version, require_extra, error types
  metadata.py        # AdapterMetadata (frozen dataclass)
  binding.py         # SurfaceBinding, validate_binding
  coverage.py        # CoverageInventory, SurfaceCoverage, SurfaceStatus
  enforcement.py     # enforce() — the evaluate/record/execute boundary
  errors.py          # AdapterDenied, AdapterConfigurationError
  crewai_adapter.py  # M2-B CrewAI adapter (requires [crewai] extra)
  langgraph.py       # M2-C LangGraph adapter (requires [langgraph] extra)
tests/  (14 test modules, see §10)
docs/MIGRATION.md, docs/COMPATIBILITY.md
scripts/test_wheel_install.py
pyproject.toml, README.md, CHANGELOG.md, LICENSE
```

Public `__all__` of the base package: `AdapterMetadata`, `CoverageInventory`, `SurfaceCoverage`, `SurfaceStatus`, `enforce`, `AdapterDenied`, `AdapterConfigurationError`, `UnsupportedSPIVersionError`, `MissingOptionalDependencyError`, `require_extra`, `SurfaceBinding`, `validate_binding` (`src/nornyx_agentic_adapters/__init__.py:36-50`).

- The **base package imports no agent framework** — framework code is confined to extras-gated submodules (`__init__.py:3-8`); enforced by tests `tests/test_import_boundary.py:9,29,42` (base import with no framework; core never imports the adapter package; no module-level framework import in source).
- **SPI major-version gate at import time**: `check_spi_version(_agentic.SPI_VERSION)` runs on package import (`__init__.py:34`); `SUPPORTED_SPI_MAJOR = 1`, non-1 major raises `UnsupportedSPIVersionError` (`_compat.py:8,16-34`). Core `SPI_VERSION = "1.2"` (`nornyx/agentic/authz.py:66`).
- **Framework pins enforced at import time, not just declared**: `crewai_adapter` fails closed via `_check_crewai_version(_installed_crewai_version())` at module import (`crewai_adapter.py:55,66-105`); `langgraph` does the same for `1.2.2` (`langgraph.py:37,45-69`). Missing distribution → `MissingOptionalDependencyError` (`_compat.py:37-54`); installed-but-wrong version or malformed metadata → `AdapterConfigurationError`. Tests: `tests/test_crewai_adapter.py:951-990`, `tests/test_crewai_adapter_missing_dependency.py:23`, `tests/test_langgraph_adapter_missing_dependency.py:13`.

### 1.3 Milestone status (per README status table, `README.md:19-25`)

| Component | Status |
|---|---|
| M2-A public contract (`AdapterMetadata`, `CoverageInventory`, `SurfaceBinding`, `enforce`) | Available |
| M2-B CrewAI adapter | Available — **tool invocation only** |
| M2-C LangGraph adapter | Available — **synchronous StateGraph nodes only** |
| M2-D legacy compatibility shim | Complete — deprecated facade over SPI 1.2 `Authorizer.state`; requires Nornyx 1.11.0; **unpackaged, outside this distribution** |

---

## 2. CrewAI adapter — exact coverage boundary

### 2.1 The wrapped surface — IMPLEMENTED

The **only** wrapped CrewAI surface is: subclassing `crewai.tools.BaseTool` and overriding the **synchronous** `_run`, reached through `Crew.kickoff()`'s native ReAct executor. This is stated in the module docstring (`src/nornyx_agentic_adapters/crewai_adapter.py:11-22`) and in the README coverage note (`README.md:68-82`).

Verbatim — the governed-tool wrapper, `crewai_adapter.py:211-262`:

```python
class _GovernedTool(BaseTool):  # type: ignore[misc, valid-type]
    """A ``BaseTool`` whose ``_run`` enforces one declared (identity,
    capability) binding before running the adapter-owned action, exactly once.
    ...
    """

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        binding: SurfaceBinding = self._nornyx_binding
        authorizer: Authorizer = self._nornyx_authorizer
        context: EvaluationContext = self._nornyx_context
        recorder: EvidenceRecorder = self._nornyx_recorder
        mission_id: str = self._nornyx_mission_id
        action: Callable[..., Any] = self._nornyx_action

        request = CapabilityRequest(
            identity_ref=binding.identity_ref, capability_ref=binding.capability_ref
        )
        authorizing: list[str] = []

        def capture(decision: Decision) -> None:
            if decision.allowed:
                authorizing.extend(
                    item.ref for item in decision.basis if item.kind == "delegation"
                )

        result = enforce(
            authorizer,
            request,
            context=context,
            recorder=recorder,
            mission_id=mission_id,
            action=lambda: action(*args, **kwargs),
            on_decision=capture,
        )
        recorder.record_observation(
            "tool_invoked",
            mission_id=mission_id,
            actor_ref=binding.identity_ref,
            capability_ref=binding.capability_ref,
            delegation_ref=authorizing[0] if authorizing else None,
        )
        return result
```

Construction — `make_governed_tool` (`crewai_adapter.py:265-327`): validates the binding (`validate_binding(binding)`, line 309), validates the optional `args_schema` is a pydantic `BaseModel` subclass else raises `AdapterConfigurationError` (lines 310-316), constructs `_GovernedTool(name=..., description=..., [args_schema=...])`, then attaches the live SPI objects **out-of-band** via `object.__setattr__` so they never appear in the tool's pydantic schema or serialized arguments (lines 321-326; documented at 294-305). "This is NOT arbitrary CrewAI-tool wrapping: it constructs a governed tool from an explicit `action` and (optional) `args_schema`" (lines 306-307).

Identity mapping: `agent_identity_key(agent)` extracts `agent.role` (fails closed on blank/absent role, `crewai_adapter.py:186-198`); `resolve_identity(authorizer, agent)` is a "thin pass-through to `Authorizer.resolve_identity`" (`crewai_adapter.py:201-208`), where unknown/ambiguous keys raise `IdentityResolutionError` (core: `nornyx/agentic/authz.py:790-800`).

### 2.2 What is NOT covered — IMPLEMENTED (declared, machine-readable)

`crewai_adapter.COVERAGE_INVENTORY` (`crewai_adapter.py:118-183`) declares six surfaces; exactly one is `WRAPPED`:

| Surface | Status | Declared reason (abridged) |
|---|---|---|
| `tool_invocation` | **wrapped** | sync `BaseTool._run` override via `Crew.kickoff()`'s native ReAct executor; "Covers the sync `_run` path only" |
| `async_tool_invocation` | **unsupported** | adapter "does NOT override `_arun`"; inherited `BaseTool._arun` raises `NotImplementedError`, "the wrapped action never executes and no `tool_invoked` observation is recorded" |
| `agent_invocation` | unsupported | "No public, stable CrewAI hook fires on agent invocation distinct from tool-level interception" |
| `task_invocation` | unsupported | same rationale |
| `delegation` | unsupported | "CrewAI's coworker delegation is implemented via its own internally generated tools; wrapping it would depend on undocumented CrewAI internals" |
| `handoff` | unsupported | "CrewAI has no distinct handoff concept or public hook separate from delegation" |

Async fail-closed behavior is **tested against real CrewAI**: `test_async_arun_fails_closed_and_records_nothing` (`tests/test_crewai_adapter.py:690`), plus `test_coverage_inventory_declares_async_tool_invocation_unsupported` (line 659) and `test_coverage_inventory_declares_only_tool_invocation_wrapped` (line 215).

### 2.3 Bypass reality — IMPLEMENTED (tested), and a declared NON-GOAL to prevent

"Bypassing the adapter — calling the underlying action directly instead of through the governed tool — bypasses enforcement entirely" (`README.md:80-82`). This is not just prose: `test_bypass_calling_the_raw_action_directly_skips_enforcement_entirely` (`tests/test_crewai_adapter.py:506`) and benchmark scenario S15 (§7) exercise it. The Assurance boundary section (`README.md:133-150`, referencing ADR-0040 `docs/decisions/ADR-0040-governance-assurance-tiers.md`) states the package provides "**cooperative Tier 2** authorization over **declared, wrapped surfaces only**": no gateway/sandbox/mandatory interception; no agent or approver authentication; evidence is "contract-state binding only, not runtime proof"; Tier 3 independent runtime assurance is something "Nornyx neither provides nor verifies".

### 2.4 Failure/exception handling

- DENY / APPROVAL_REQUIRED → `enforce` raises `AdapterDenied` carrying the core `Decision` unmodified; the action is never invoked (`enforcement.py:46-47,63-64`; `errors.py:17-29`; tests `tests/test_enforcement.py:78,94`).
- Unexpected errors from `authorizer.evaluate` or `recorder.record_decision` propagate **before** `action` is reached — fail-closed (`enforcement.py:5-8`; tests `tests/test_enforcement.py:111,196`).
- The `tool_invoked` observation is recorded **only after** `action` actually returns (`crewai_adapter.py:252-261`; contract in `enforcement.py:41-44`). If the action itself raises, no `tool_invoked` is recorded (benchmark scenario S14 proves 0 completions, §7).
- Delegated capabilities: the ALLOW decision's `basis` items of `kind == "delegation"` are captured via the `on_decision` hook and carried into `tool_invoked` as `delegation_ref` — never taken from caller-controlled tool arguments (`crewai_adapter.py:233-251,286-292`; regression fix for benchmark finding F2, adapter `CHANGELOG.md:30-42`; tests at `tests/test_crewai_adapter.py:342,394,421,451`).

---

## 3. The `enforce()` evaluate → record → execute sequence — IMPLEMENTED

Verbatim, `src/nornyx_agentic_adapters/enforcement.py:28-65` (the single enforcement boundary):

```python
def enforce(
    authorizer: Authorizer,
    request: AuthorizationRequest,
    *,
    context: EvaluationContext,
    recorder: EvidenceRecorder,
    mission_id: str,
    action: Callable[[], T],
    on_decision: Callable[[Decision], None] | None = None,
) -> T:
    ...
    decision = authorizer.evaluate(request, context=context)
    recorder.record_decision(decision, mission_id=mission_id)
    if on_decision is not None:
        on_decision(decision)
    if not decision.allowed:
        raise AdapterDenied(decision)
    return action()
```

Ordering guarantees (docstring, `enforcement.py:38-57`): decision intents are recorded before the wrapped callable runs; on ALLOW the action runs exactly once; `on_decision` is an observation hook only — invoked after recording, before any branch, on DENY as well as ALLOW; an exception from it fails closed before the action. Changing "enforce()'s evaluate → record → execute ordering guarantee" is classified a **breaking** change (`docs/COMPATIBILITY.md:70-72`). Tests: `tests/test_enforcement.py` (8 tests, lines 61-196). `tests/test_no_network.py:48,64` proves `enforce` and the contract types perform no network I/O.

## 4. Coverage inventory mechanism — IMPLEMENTED

Yes, there is a machine-readable coverage inventory. `src/nornyx_agentic_adapters/coverage.py:18-73`:

```python
class SurfaceStatus(Enum):
    WRAPPED = "wrapped"
    UNSUPPORTED = "unsupported"
    UNWRAPPED = "unwrapped"

@dataclass(frozen=True)
class SurfaceCoverage:
    surface: str
    framework: str
    status: SurfaceStatus
    reason: str = ""

@dataclass(frozen=True)
class CoverageInventory:
    entries: tuple[SurfaceCoverage, ...]
    ...
    def wrapped(self) -> tuple[SurfaceCoverage, ...]: ...
    def as_dict(self) -> dict:
        """Deterministic, JSON-serializable representation (sorted for reproducibility)."""
```

Module docstring ties it to ADR-0040: "Tier 2 claim eligibility requires a declared coverage inventory naming which surfaces are wrapped... unsupported and unwrapped surfaces are named, not hidden, and the inventory never implies whole-application coverage" (`coverage.py:1-8`). Entries are canonicalized to a fresh tuple at construction so retained-list mutation cannot alter it (`coverage.py:39-56`). Tests: `tests/test_coverage.py` (12 tests, lines 29-123, incl. `test_coverage_never_claims_unnamed_surfaces`, line 78).

`SurfaceBinding` (`binding.py:19-27`) is the closed declarative mapping `(surface, identity_ref, capability_ref)`; `validate_binding` fails closed on any blank field (`binding.py:29-37`). Bindings are "built from an adapter's own static configuration, never from raw framework arguments (commands, paths, URLs, tool payloads)" (`binding.py:1-9`; `README.md:196-199`). `AdapterMetadata` (`metadata.py:8-25`) declares adapter name/version, SPI version, framework name and `framework_version_range`, `nornyx_version_range`.

---

## 5. LangGraph adapter — occurrence-aware sync node coverage

### 5.1 The wrapped surface — IMPLEMENTED

`src/nornyx_agentic_adapters/langgraph.py` (ADR-0039 M2-C on the runtime-events 1.1 contract of ADR-0042, `docs/decisions/ADR-0042-runtime-occurrence-semantics.md`). "The adapter consumes only LangGraph's public `Runtime.execution_info`. It maps a governed node surface to a logical operation, the public task id to an occurrence, and the public one-based node attempt to a Nornyx attempt" (`langgraph.py:3-7`).

Wrapping a node (public API, README example `README.md:99-119`):

```python
recorder = EvidenceRecorder.for_occurrences(authorizer, context, producer_id="my-graph")
governed_node = make_governed_node(
    binding=SurfaceBinding(surface="node.read", identity_ref="identity.reader",
                           capability_ref="read_governed_context"),
    authorizer=authorizer, context=context, recorder=recorder,
    mission_id="GOAL-001", action=read_node,
)
builder.add_node("read", governed_node)
```

Core mechanics of `make_governed_node` (`langgraph.py:144-275`):

- Construction fails closed on: invalid binding; non-callable action; **coroutine action** (`inspect.iscoroutinefunction` → `AdapterConfigurationError("M2-C supports synchronous LangGraph node actions only.")`, lines 164-167); a recorder that is not occurrence-aware (probe at lines 168-179).
- Per-invocation, the returned `governed_node(state, runtime)` requires `runtime.execution_info` with a non-empty `task_id` string and integer `node_attempt >= 1`, else `AdapterConfigurationError` before any evaluation (lines 184-199).
- Occurrence identity: `RuntimeOccurrence(binding.surface, task_id, base + node_attempt)` (lines 221-224) — operation = the declared surface, occurrence = LangGraph `task_id`, attempt = framework attempt offset by a cumulative `base`.
- **Resume offset**: on `node_attempt == 1` the base is `recorder.max_recorded_attempt(...)` — i.e., the validated cumulative recorder prefix — so after a checkpoint resume (where LangGraph resets `node_attempt` to 1) attempts continue monotonically instead of colliding (lines 201-219; docstring lines 6-8). A thread-locked `attempt_bases` cache keyed on `(mission_id, surface, task_id)` supports concurrent parallel branches (lines 181-182, 201-219).
- Enforcement sequence: `authorizer.evaluate` → `recorder.record_occurrence_decision(decision, mission_id=..., occurrence=...)` → on non-ALLOW raise `AdapterDenied` (lines 235-242) → run `action(state)`.
- **Interrupts are control flow, not failure**: `except GraphBubbleUp: ... raise` re-raises LangGraph bubble-up exceptions (interrupts, parent commands) without recording `runtime_failed`, leaving an incomplete attempt (lines 246-253). A normal exception records a `runtime_failed` occurrence observation then re-raises (lines 254-262). Success records an `agent_invoked` occurrence observation (lines 264-270).

### 5.2 Occurrence semantics — tested behaviors

`tests/test_langgraph_adapter.py` runs against **real `langgraph==1.2.2`** objects (`StateGraph`, `InMemorySaver`, `RetryPolicy`, `interrupt`, `Command` — imports at lines 13-16):

| Behavior | Test (`tests/test_langgraph_adapter.py`) |
|---|---|
| Metadata/coverage closed | `test_metadata_and_coverage_are_closed` :85 |
| Explicit occurrence-aware recorder required | `test_node_requires_explicit_recorder` :102 |
| Missing `execution_info` fails before action | `test_missing_execution_info_fails_before_action` :120 |
| Success uses public task identity | `test_sync_node_success_uses_public_task_identity` :128 |
| Denial never calls action | `test_policy_denial_never_calls_action` :147 |
| Native retry = one occurrence, three attempts | `test_native_retry_maps_to_one_occurrence_and_three_attempts` :171 |
| Loop visits = distinct occurrences | `test_native_loop_creates_distinct_occurrences` :199 |
| Parallel branches = distinct occurrences | `test_native_parallel_branches_have_distinct_occurrences` :229 |
| Interrupt+resume offsets reset attempt counter (attempts {1,2}, one occurrence, no `runtime_failed`, stream validates) | `test_interrupt_resume_offsets_reset_node_attempt` :262-283 |
| Declared identity resolution | `test_declared_langgraph_identity_resolution` :286 |

### 5.3 What is NOT covered — declared inventory

`langgraph.COVERAGE_INVENTORY` (`langgraph.py:82-125`):

| Surface | Status | Reason (abridged) |
|---|---|---|
| `sync_node_invocation` | **wrapped** | authorized through public `Runtime.execution_info`, "including native retry, loop, parallel-branch, interrupt, and checkpoint-resume behavior" |
| `async_node_invocation` | unsupported | "M2-C supplies no asynchronous node wrapper." |
| `graph_topology` | **unwrapped** | "The caller owns StateGraph construction and must wrap each governed node explicitly." |
| `remote_or_distributed_execution` | unsupported | "No remote service or distributed executor is attested." |
| `subgraph_and_tool_node_internals` | unsupported | "Subgraphs and prebuilt ToolNode internals are not implicitly intercepted; their callable surfaces require separate wrappers." |

Note `graph_topology` uses the third status, `unwrapped` (caller-owned), distinct from `unsupported` — the only use of that status in the repo.

---

## 6. Adapter conformance (schemas + docs 41/44) — a DIFFERENT "adapter" concept

Important disambiguation for the book: `schemas/adapter_contract.schema.json` and `schemas/adapter_conformance_report.schema.json` govern **contract-level "adapter" declarations inside `.nyx` documents** (the v0.4/v0.7 language bands) — *not* the Python framework adapters of §§2-5. The two share the word "adapter" only.

- **Adapter contract** (`schemas/adapter_contract.schema.json`, "Nornyx v0.4 Adapter Contract"): a declaration with required `name`, `kind` (enum: `governed_delivery_control_plane`, `agentic_development_harness`, `governance_adapter`, `telecom_ops`, `business_ops` — lines 24-31), `target_profile`, **`execution_mode: contract_only` (const)**, **`live_connector_execution: false` (const)** (lines 37-42), `connector_refs`/`policy_refs`/`eval_refs`/`evidence_refs`, optional `connector_conformance` (protocols limited to `mcp`/`a2a`, `approval_required: true` const, lines 78-98), and mandatory `non_goals` drawn from a closed enum ("live connector execution", "production deployment", "unrestricted adapter execution", "credential loading", "network calls", "automatic approvals", lines 99-112). Doc: `docs/41_NORNYX_ADAPTER_CONTRACTS_v0_4.md` ("Adapters are contract bridges... They are not live connector runtimes, production deployment systems, model callers, credential loaders, or automatic approval mechanisms", lines 5-9; non-goals lines 65-77).
- **Conformance report** (`schemas/adapter_conformance_report.schema.json`, "Nornyx v0.7 Adapter Conformance Report"): `schema: nornyx.adapter_conformance.v0.7` (const), `mode: static_adapter_connector_contract_conformance` (const), overall `status` in {`blocked`, `requires_human_approval`, `conformant`, `conformant_with_warnings`} (lines 8-15), a `summary` count block, a **`safety` block of all-`false` consts** (`connectors_enabled`, `adapters_executed`, `network_used`, `commands_executed`, `credentials_loaded`, `adapter_contracts_executed`, `live_connector_execution_allowed`, plus `default_execution_mode: "disabled"`, lines 31-54), per-adapter entries each with `execution_mode: contract_only`, `live_connector_execution: false`, `execution: "not_executed"` (consts, lines 59-66) and decision rows `{status, code, reason}`, and an embedded `connector_report`.
- **Generator**: `nornyx.connector_runtime.build_adapter_conformance_report(doc)` (`nornyx/connector_runtime.py:769-801`) and `write_adapter_conformance_report` (`connector_runtime.py:811-815`); also consumed by `nornyx/bounded_execution.py:150`. Doc: `docs/44_NORNYX_ADAPTER_CONFORMANCE_v0_7.md` (report contents lines 9-21; "does not open networks, load credentials, execute commands, call models, execute adapters, or grant approvals", lines 54-57; non-goals lines 59-72).
- **Tests that generate/verify conformance reports**: `tests/test_v07_adapter_conformance.py` — builds a report from `examples/nornyx_v04_adapter_contracts.nyx` and asserts 5 adapters, status `requires_human_approval`, all safety flags false, and the decision-code set (`ADAPTER_EXECUTION_MODE_CONTRACT_ONLY` ... `ADAPTER_NON_GOALS_COMPLETE`, lines 20-51); asserts a deliberately unsafe adapter contract is `blocked` with the mirrored `*_UNSAFE`/`*_UNKNOWN` codes (lines 54-111); writes and re-reads a report file (lines 114-121); asserts the schemas themselves are contract-only (lines 124-133). Also `tests/test_v04_adapter_contracts.py`.

**What "conformance" means here**: purely *static, declaration-level* checking that adapter contracts declare safe modes, referenced artifacts exist, and non-goals are complete — with schema-level proof that nothing was executed. It does not test the Python framework adapters. The framework adapters' analogous artifact is the `CoverageInventory` (§4), and their behavioral conformance is established by the test suites of §10, not by this report. There is **no** conformance-report generator for `nornyx-agentic-adapters` itself (verified by absence: no reference to `adapter_conformance` under `adapters/`).

---

## 7. CrewAI governance benchmark — examples/crewai_governance_benchmark/

An offline, deterministic A/B benchmark on the **supported** adapter stack. README: "One customer-support and financial-remediation workflow is run twice: Variant A — an ordinary CrewAI application. Variant B — the *same* agents, tasks, model, inputs, business rules, and business callables, with each tool built by the supported Nornyx CrewAI adapter" (`examples/crewai_governance_benchmark/README.md:7-14`). Entry point: `python examples/crewai_governance_benchmark/benchmark.py --out benchmark_out` (README:16-18); "Exits non-zero unless every clause of the benchmark contract holds **and** the complete evidence stream validates... the verdict is `GO` or `NO_GO`" (README:20-22).

**Side-effect ledger method** (README:59-71): every business tool writes to a side-effect ledger and every governance decision is stamped on the *same* monotonic clock (`ledger.py`), making checkable: (a) denied scenario ⇒ attempts and completions exactly zero, allowed ⇒ exactly one; (b) the k-th business-callable entry must be preceded by a k-th recorded decision (defeats decision reuse); (c) an authorized action that then fails produces zero completions and no `tool_invoked`.

**Scenario matrix** — 19 scenarios, five stages, "reported separately and never summed" (README:73-103). Prevented/denied outcomes include `CAPABILITY_UNKNOWN` (S03), `CAPABILITY_DENIED` (S04), `IDENTITY_UNKNOWN` (S05), `CROSSING_APPROVAL_REQUIRED` (S06), `APPROVAL_NON_HUMAN` (S07, AI-generated approval), `APPROVAL_ACTION_MISMATCH` (S08), `APPROVAL_STALE` (S09), `SENSITIVE_SHARING` (S10), `ZONE_CROSSING_DENIED` (S11), `LOCK_STALE` (S12), `REQUEST_MALFORMED` (S13), `REVISION_MISMATCH` (S17). Controls: **S15 deliberate unwrapped-tool bypass runs in both variants** ("S15 and S18 are controls, not wins... a tool that never enters the adapter is never evaluated", README:99-103); S18 is an application rule refused in both arms. S14 shows CrewAI's internal 3-retry each gets independent authorization (`REVIEWER_QUICKSTART.md:307-309`). S16 is valid bounded delegation.

**Governed variant integration** (`variant_governed.py:1-40`): the CrewAI tool delegates into the adapter's own governed `_run`; two disclosed choices: one fresh mission id per invocation (because the recorder has no monotonic component, repeated identical decisions would trip `AN_EVT_REPLAY`), and `AdapterDenied` is caught at the CrewAI boundary and returned as text ("an agent framework needs a tool result rather than an unhandled exception. The business callable is unreachable either way — the side-effect ledger is what proves it").

**Findings** (`FINDINGS.md:1-20`; README:119-137): building the benchmark surfaced three real defects against base `d4026a1` (`nornyx` 1.8.0/SPI 1.0, adapters 0.1.0) — F1 (a correctly refused non-human approval produced an unvalidatable stream; fixed in `nornyx/agentic_evidence.py`), F2 (delegated capability's `tool_invoked` omitted `delegation_ref`; fixed in the adapter, §2.4), F3 (the legacy `integrations/` tree claimed the import name `nornyx_agentic_adapters`; fixed by renaming to `nornyx_reference_adapters`). "None of them ever affected an enforcement result... What they blocked was a clean *evidence* claim."

**Outputs** (README:105-117): `benchmark.json`, `benchmark.md`, `dashboard.html` (self-contained, no CDN), `environment.json`, per-variant results with full ledger timeline, `nornyx_runtime_events.json`, `nornyx_evidence_report.json`, `validation_manifest.json` with `candidate_digest` and `deterministic_outputs_digest`. A recorded run is committed under `results/` ("a snapshot of one run, not a continuously verified claim", README:139-156). `REVIEWER_QUICKSTART.md` gives clean-env install, self-verification recipes (zero-side-effect check, ledger read, evidence/digest verification, offline-guard proof, per-scenario reruns) and the epistemics list ("Identity resolution is binding, not authentication"; "Validating evidence proves structure and binding, not truth", lines 313-323).

**Tests + CI**: `tests/test_crewai_governance_benchmark.py` (47 `def test`s; quickstart line 287 says "46 tests, zero skips"), run by the dedicated `crewai-governance-benchmark` CI job which also runs the benchmark itself and fails on any skip/non-GO (§11).

### 7b. examples/crewai_nornyx_comparison/ — the older legacy-stack A/B

"CrewAI × Nornyx 1.7.0" (`examples/crewai_nornyx_comparison/README.md:1-18`): same A/B shape but targeting **Nornyx 1.7.0 and the legacy kernel**, with real `Agent`/`Task`/`Crew`/`BaseLLM`/`BaseTool`/`Crew.kickoff()`; denial proved by a side-effect ledger; S12 (stale lock) and S14 (bypass) labeled `initialization` and `bypass` controls (README:40-48). Preserved unchanged as regression coverage; the governance benchmark "is its successor on the supported stack, not a replacement for its regression coverage" (`crewai_governance_benchmark/README.md:50-54`). Run by CI job `native-frameworks` via `compare.py`, `ci_check_artifacts.py`, and `verify_published_nornyx.py` (installs published Nornyx 1.7.0 from PyPI) (`.github/workflows/ci.yml:481-495`); tests: `tests/test_crewai_nornyx_comparison.py` (14 tests).

### 7c. examples/agentic_network_support/run_demo.py — LangGraph/CrewAI reference demo

"AN-006 canonical demonstration: the Governed Customer Support Network. Runs the same Nornyx contract through both reference adapters (CrewAI-shaped and LangGraph) with a deterministic local harness: fake model, inert tools, temporary local files only, no API keys, no sockets" (`run_demo.py:1-14`). It imports the **legacy** `nornyx_reference_adapters` (kernel, both adapters, `local_harness` fakes; lines 47-60), pins `AS_OF = "2026-07-17T00:00:00Z"`, and demonstrates blocked scenarios (`_blocked` helper asserting `GovernanceViolation` codes, lines 72-80) plus evidence validation. The root README quotes the full CLI pipeline around it (`README.md:210-218`) and states: "The same contract governs the legacy offline reference adapters and the separately distributed `nornyx-agentic-adapters` package" (`README.md:219-220`). Tests: `tests/test_agentic_support_example.py` (15 tests).

---

## 8. Legacy reference adapters vs. the distributed package; the M2-D shim

### 8.1 The two adapter trees

| | `integrations/nornyx_reference_adapters/` | `adapters/nornyx-agentic-adapters/` |
|---|---|---|
| Origin | AN-005 / ADR-0037 reference integrations | ADR-0039 M2-A/B/C/D supported package |
| Packaging | **Unpackaged** — "not part of the `nornyx` wheel" (`integrations/README.md:3-4`); "ships in neither the core wheel nor `nornyx-agentic-adapters`" (`governance_kernel.py:20-21`) | Its own PyPI distribution `nornyx-agentic-adapters` 0.2.0 with a dedicated release workflow (`.github/workflows/adapters-release.yml`) |
| Import name | `nornyx_reference_adapters` (renamed from `nornyx_agentic_adapters` to fix collision F3; "No compatibility shim was left under the old name", `docs/MIGRATION.md:10-34`) | `nornyx_agentic_adapters` — "now unambiguously means this installed distribution" (`MIGRATION.md:26-27`) |
| Status | **Deprecated** — construction emits one `DeprecationWarning` naming the replacements (`integrations/README.md:15-22`; `MIGRATION.md:177-189`) | Supported (Alpha) |
| API style | `GovernanceKernel` + `CrewAIGovernanceAdapter.guarded_task` / `LangGraphGovernanceAdapter.guard_node`, `AN_ADAPTER_*` string diagnostics via `GovernanceViolation` | `SurfaceBinding` + `enforce` + `make_governed_tool` / `make_governed_node`, typed `AdapterDenied` carrying the core `Decision` |
| Occurrence semantics | Never explicit: runtime-events 1.0 exact envelope, or 1.1 `occurrence_mode: legacy`; "The shim never invents occurrence identities" (`docs/COMPATIBILITY.md:19-24`; `MIGRATION.md:164-175`) | Explicit occurrence recording (LangGraph adapter, SPI 1.1) |

Contents of `integrations/nornyx_reference_adapters/`: `governance_kernel.py` (947 lines), `crewai_adapter.py` (86), `langgraph_adapter.py` (99), `local_harness.py` (43 — deterministic fake model + inert tools), `__init__.py`. `crewai`/`langgraph` are imported lazily and only if user-installed; the enforcement paths are testable without either framework (`integrations/README.md:39-44`).

### 8.2 The M2-D legacy compatibility shim — IMPLEMENTED (git HEAD)

Git evidence: commits `1eb67b1` "Implement M2-D legacy compatibility shim", `789bf21` "Remediate M2-D against public Authorizer state SPI 1.2", `a63f8ca` "Reject malformed legacy approval assertions before evidence recording", `19a4387` "Clarify legacy approval source semantics", merged at HEAD `70d2b40` (git log). Root `CHANGELOG.md` `[Unreleased]` section, lines 9-44.

What it is: M2-D **rewrites the internals of the legacy `GovernanceKernel`** into "a deprecated compatibility facade over the supported Nornyx agentic SPI" (`governance_kernel.py:1`). Key properties (all from `governance_kernel.py:8-27` and `CHANGELOG.md:11-29`):

- **Single source of authority**: one `Authorizer` is constructed (or via `load_authorizer`), and its public **SPI 1.2 `Authorizer.state` (`AuthorizerState`)** "is the only source for every legacy compatibility projection... The shim never reads Authorizer private attributes, never retains caller-supplied contract/composition/lock structures as a second source of truth, and never re-reads, re-composes, re-authorizes, or re-verifies policy after the Authorizer has been constructed." Legacy `document`/`composition`/`lock_payload`/`network` surfaces are "non-authoritative read-only projections."
- Therefore the shim **requires Nornyx 1.11.0 (SPI 1.2) or newer** — but "this does **not** raise the adapter distribution's own `nornyx>=1.10,<2` floor" (`docs/COMPATIBILITY.md:10-16`).
- **Not packaged**: "still unpackaged and outside this distribution" (`adapters/.../README.md:25`); "It is not part of the adapter distribution and **does not widen the CrewAI or LangGraph coverage declared here**" (`COMPATIBILITY.md:15-16`). Because the adapter README changed wheel metadata, the M2-D diff is classed release-classification C, "any later adapter publication requires separate authorization" (`CHANGELOG.md:38-44`).
- Complete legacy→SPI method map: `MIGRATION.md:51-66` (e.g. `check_capability` → `CapabilityRequest` → one `evaluate` → `record_decision`; `events_payload()` → `EvidenceRecorder.stream()`). Diagnostic map: SPI `DecisionCode`s → stable `AN_ADAPTER_*` codes (`MIGRATION.md:145-162`) — "compatibility codes only... not new public SPI guarantees."
- Legacy guard enforcement path, verbatim `governance_kernel.py:618-660` (`_execute_tool_callable`, used by both `guarded_task` at `crewai_adapter.py:78-84` and `guard_node` at `langgraph_adapter.py:62`): "Authorize once, execute once, then record success or runtime failure" — authorize via `CapabilityRequest`; on exception record `runtime_failed` and re-raise; on success record `tool_invoked` (with `delegation_ref` read from `decision.basis`); no success event for a denied or failed callable (`MIGRATION.md:68-72`).
- **Approval-field compatibility** (`MIGRATION.md:74-143`): `require_human_approval` treats `role`/`actor_type` as caller-supplied structural requirements validated at the boundary against the runtime-events schema (`^[A-Za-z0-9][A-Za-z0-9._:-]*$`, ≤128 chars; closed actor_type enum mirrored at `governance_kernel.py:146-158`) — malformed input raises `AN_ADAPTER_REQUEST_MALFORMED` **before** the Authorizer is consulted or the recorder advances ("Malformed input on this path can never poison the evidence stream"). The `record_zone_crossing` compatibility path may construct a "cooperative claimed-human assertion" from authoritative policy state — explicitly "**not proof that a human approved the crossing**."
- Deprecation/retention (`MIGRATION.md:177-189`): one `DeprecationWarning` per normal load path; retained for ≥1 published Nornyx minor release after M2-D; removal requires four conditions including "a separate owner-authorized removal decision."
- Unsupported by the shim (`MIGRATION.md:191-197`): occurrence-explicit retries/resume, async CrewAI/LangGraph interception, remote/distributed execution, framework-wide coverage, identity/approver authentication, Tier-3 attestation.
- Tests: `tests/test_legacy_governance_shim.py` — "ADR-0039 M2-D compatibility and baseline-closure corpus", **32 tests**, importing both the legacy tree and the adapter source tree (file header, lines 1-60).

Core SPI 1.2 anchor: `AuthorizerState` (`nornyx/agentic/authz.py:642-706` — detached deep-frozen document/composition/lock plus `contract_digest`/`network_lock_digest`) and `Authorizer.state` property (`authz.py:774-786` — validation/composition/lock verification "guaranteed only for an Authorizer obtained through `load_authorizer`"). Published in 1.11.0 (`CHANGELOG.md:46-60`); tests `tests/test_agentic_authorizer_state.py` (17 tests).

### 8.3 SPI usage from the adapter side — verified

The supported adapter package **performs no filesystem I/O and never loads or re-reads contracts**: grep of `src/nornyx_agentic_adapters/` finds no `load_authorizer`, `open(`, `read_text`, or `Path(` (verified by search, this audit). Adapters receive an already-constructed `Authorizer`, `EvaluationContext`, and `EvidenceRecorder` as explicit parameters (`crewai_adapter.py:265-275`; `langgraph.py:144-151`) and consume only: `Authorizer.evaluate`, `Authorizer.resolve_identity`, `Decision`/`DecisionBasis`, `CapabilityRequest`, `EvidenceRecorder.record_decision` / `record_observation` / `record_occurrence_decision` / `record_occurrence_observation` / `max_recorded_attempt` / `for_occurrences`, `RuntimeOccurrence`, `SPI_VERSION`. The supported adapters do **not** use `Authorizer.state` at all — "SPI 1.2 adds the framework-neutral `Authorizer.state` construction snapshot; it changes no adapter authorization or occurrence behavior" (`adapters/.../README.md:160-162`). Only the M2-D shim consumes `Authorizer.state` (§8.2). Request normalization is confined to declarative `SurfaceBinding` fields plus framework-public metadata (`agent.role`, node key, `task_id`, `node_attempt`); raw framework arguments never form bindings (`binding.py:1-9`).

---

## 9. integrations/, extensions/, apps/ — what's actually there

- **integrations/**: exactly `README.md` + `nornyx_reference_adapters/` (5 files, §8.1). Nothing else.
- **extensions/**: three YAML descriptors, each `status: planned` — `mcp.yaml` (MCP connector blocks; safety defaults `read_only_first`, `explicit_user_consent`, `trace_every_tool_call`, `deny_untrusted_write_tools`), `a2a.yaml` (peer-agent contracts; `share_summaries_not_private_memory`, `require_trust_level`, `preserve_handoff_trace`), `opentelemetry-genai.yaml` (trace/span/metric export; redact-by-default). **ROADMAP/GUIDANCE only — no runtime code** (`extensions/mcp.yaml:1-2`, `extensions/a2a.yaml:1-2`, `extensions/opentelemetry-genai.yaml:1-2`).
- **apps/**: exactly one app, `apps/nornyx-dev-pmo-portal/` (`server.py`, `index.html`, `app.js`, `styles.css`, `README.md`) — "A lightweight local-only PMO portal dedicated to Nornyx language development" serving PMO status from `docs/pmo/status/current_status.json`, read-only allowlisted git commands, local KPI metrics, and a vision map; default host 127.0.0.1; "No LLM calls. No UI shell execution. No external connectors. No secrets required" (`apps/nornyx-dev-pmo-portal/README.md:1-13,52-78`). IMPLEMENTED as a local dev tool; not a governance runtime and not packaged.

---

## 10. Test inventory (adapters and integrations)

### 10.1 Adapter package tests (`adapters/nornyx-agentic-adapters/tests/`)

| File | Focus (selected named tests) |
|---|---|
| `test_enforcement.py` (8) | ALLOW exactly-once; DENY/APPROVAL_REQUIRED never invoke action; evaluate/record errors fail closed; `on_decision` semantics (lines 61-196) |
| `test_crewai_adapter.py` (28) | metadata/coverage closure; identity mapping; allow runs action exactly once + records `tool_invoked` (:263); deny raises `AdapterDenied`, zero side effects (:303); delegation-ref carried from decision, not args (:342,:394,:421); expired delegation denies (:451); blank-binding fail-closed (:489); **bypass test** (:506); **native `Crew.kickoff()` end-to-end allow/deny with sockets+subprocess forbidden** (:531,:593); async `_arun` fails closed, records nothing (:690); structured `args_schema` matrix (:736-:888); import-time version pin (:951-:979) |
| `test_crewai_adapter_missing_dependency.py` (1) | precise `MissingOptionalDependencyError` without crewai (:23) |
| `test_langgraph_adapter.py` (10) | occurrence corpus, §5.2 |
| `test_langgraph_adapter_missing_dependency.py` (1) | precise diagnostic without langgraph (:13) |
| `test_coverage.py` (12), `test_binding.py` (3), `test_metadata.py` (2), `test_errors.py` (3), `test_compat.py` (5) | contract-type semantics |
| `test_import_boundary.py` (3) | base import w/o frameworks; core never imports adapters; no module-level framework import |
| `test_no_network.py` (2) | enforce and type construction perform no network I/O |
| `test_version_consistency.py` (2) | `__version__` matches pyproject; CHANGELOG mentions release |

The framework tests use `pytest.importorskip("crewai")` / `pytest.importorskip("langgraph")` (`test_crewai_adapter.py:33` docstring lines 9-13; `test_langgraph_adapter.py:11`), so they skip in the extras-free matrix — and the dedicated CI jobs then **forbid those skips** (§11).

### 10.2 Root-repo integration tests (`tests/`)

- `test_agentic_crewai_native.py` — 11 tests, native CrewAI against the **legacy** reference kernel: kickoff+evidence, undeclared capability denied, delegated crew execution, escalation rejected, handoff without authority grant, human approval accepted / AI approval rejected, trust-zone and sensitive-sharing rejection, stale controls fail closed, missing hook fails closed (lines 229-595).
- `test_agentic_integrations.py` — 22 tests, "AN-005 tests: CrewAI and LangGraph reference adapters over one contract" (header line 1).
- `test_legacy_governance_shim.py` — 32 tests, M2-D corpus (§8.2).
- `test_crewai_governance_benchmark.py` — 47 `def test`s (benchmark artifacts, no-private-API, no-absolute-paths, dashboard self-containment, manifest digests).
- `test_crewai_nornyx_comparison.py` — 14 tests (legacy-stack A/B).
- `test_agentic_support_example.py` — 15 tests (run_demo).
- `test_v04_adapter_contracts.py`, `test_v07_adapter_conformance.py` — contract-level adapter conformance (§6).
- Supporting core suites: `test_agentic_authz.py`, `test_agentic_occurrence_semantics.py`, `test_agentic_authorizer_state.py` (17), `test_agentic_network_evidence.py`, `test_agentic_facade_surface.py`.

---

## 11. CI — real frameworks, not stubs

`.github/workflows/ci.yml` (on push/PR to main). Jobs:

| Job | Python | What it installs / runs |
|---|---|---|
| `test` | **matrix 3.10/3.11/3.12/3.13** | core `pip install -e ".[dev]"`; full pytest; build + twine check; installed-wheel no-network smoke; example contract check (lines 16-56) |
| `adapter-foundation` | matrix 3.10-3.13 | builds the **core wheel from the same candidate commit** ("never from PyPI", comment lines 59-63), installs adapter `-e ".[dev]"` (no framework extras), ruff, full adapter pytest, adapter wheel build + twine + no-network wheel smoke (lines 58-115) |
| `adapter-crewai-native` | 3.13 | installs `.[crewai,dev]` — **real `crewai==1.15.4`** ("not a mock", comment lines 118-120); asserts installed version; runs the CrewAI test files with `--junitxml` and a deterministic **zero-skips gate** ("Fail closed if ANY focused CrewAI test skipped", lines 149-163); then installs the built adapter **wheel** with the `[crewai]` extra into a fresh venv, patches `socket` to block network, and smokes allow/deny governed tools **from outside all source roots** (lines 164-246) |
| `adapter-langgraph-native` | 3.13 | installs `.[langgraph,dev]` — **real `langgraph==1.2.2`**; asserts version; runs LangGraph tests with the same zero-skips XML gate; wheel smoke `--with-langgraph` (lines 248-291) |
| `crewai-governance-benchmark` | 3.13 | candidate core wheel + candidate adapter with `[crewai]`; verifies the exact toolchain; **runs the benchmark offline**; asserts benchmark.json contract checks all pass, verdict `GO`, evidence validation `pass`, zero diagnostics; runs the benchmark test suite with a zero-skips/zero-failures gate; uploads artifacts (lines 293-416) |
| `quality` | 3.13 | ruff, public-boundary check, compatibility-migrations check, `scripts/agentic_network_ci.py` (lines 418-443) |
| `native-frameworks` | 3.13 | core + **real `crewai==1.15.4` and `langgraph==1.2.2`** installed by pip (line 464); runs `test_agentic_crewai_native.py`, `test_agentic_integrations.py`, `test_crewai_nornyx_comparison.py`; runs the legacy A/B `compare.py` + artifact machine-check; runs `verify_published_nornyx.py` which installs **published Nornyx 1.7.0 from PyPI** in isolation (lines 445-495) |
| `windows` | windows-latest, 3.13 | core suite + wheel smoke on Windows (lines 497-527) |

CrewAI telemetry is disabled in every framework job (`CREWAI_DISABLE_TELEMETRY`, `OTEL_SDK_DISABLED`, `CREWAI_TRACING_ENABLED=false`, `CREWAI_TESTING=true`, e.g. lines 152-157).

**Conclusion: CI tests the adapters against the real pinned frameworks (CrewAI 1.15.4, LangGraph 1.2.2), with explicit machine-checked "no silent skip" gates and installed-wheel smokes; the deterministic part is the LLM (a scripted offline `BaseLLM`), never the framework objects.** The test doubles that do exist (e.g. `_Allow`/`_Deny` authorizers in the wheel smoke, ci.yml:205-218; `DeterministicLLM`) stub the *policy engine or model*, not CrewAI/LangGraph.

Release path: `.github/workflows/adapters-release.yml` — separate cadence, PyPI Trusted Publishing (OIDC, no stored token); publishing requires tag `adapters-vX.Y.Z` exactly equal to the adapter `pyproject.toml` version at the tagged commit, else fails closed; tests run with `.[dev,crewai,langgraph]` (lines 1-60, 61-85).

---

## 12. Additional textbook-quotable excerpts

**A coverage-inventory declaration** (CrewAI, `crewai_adapter.py:118-143`, first two entries):

```python
COVERAGE_INVENTORY = CoverageInventory(
    entries=(
        SurfaceCoverage(
            surface="tool_invocation",
            framework=FRAMEWORK,
            status=SurfaceStatus.WRAPPED,
            reason=(
                "Synchronous tool execution wrapped via a "
                "crewai.tools.BaseTool._run override, reached through "
                "Crew.kickoff()'s native ReAct executor. Covers the sync "
                "_run path only; see async_tool_invocation for the async path."
            ),
        ),
        SurfaceCoverage(
            surface="async_tool_invocation",
            framework=FRAMEWORK,
            status=SurfaceStatus.UNSUPPORTED,
            reason=(
                "M2-B overrides only the synchronous BaseTool._run and does NOT "
                "override _arun. ..."
            ),
        ),
        ...
```

**LangGraph interrupt handling** (`langgraph.py:244-262`):

```python
        try:
            result = action(state)
        except GraphBubbleUp:
            # LangGraph bubble-up exceptions (including interrupts and parent
            # commands) are control flow, not execution failure. Drop the
            # in-process base so a resumed/re-entered node offsets from the
            # now-validated incomplete prefix when node_attempt restarts at 1.
            with attempt_lock:
                attempt_bases.pop(cache_key, None)
            raise
        except Exception:
            recorder.record_occurrence_observation(
                "runtime_failed",
                mission_id=mission_id,
                occurrence=occurrence,
                actor_ref=binding.identity_ref,
                capability_ref=binding.capability_ref,
            )
            raise
```

**A conformance-report fragment** (schema-shaped, from `schemas/adapter_conformance_report.schema.json:6-54` and the generator `nornyx/connector_runtime.py:789-801`):

```json
{
  "schema": "nornyx.adapter_conformance.v0.7",
  "mode": "static_adapter_connector_contract_conformance",
  "status": "requires_human_approval",
  "summary": {"adapters": 5, "connectors": 2, "blocked": 0, "...": "..."},
  "safety": {
    "connectors_enabled": false, "adapters_executed": false,
    "network_used": false, "commands_executed": false,
    "credentials_loaded": false, "default_execution_mode": "disabled",
    "adapter_contracts_executed": false,
    "live_connector_execution_allowed": false
  },
  "adapters": [{"name": "...", "kind": "governance_adapter",
                "execution_mode": "contract_only",
                "live_connector_execution": false,
                "execution": "not_executed",
                "decisions": [{"status": "ready",
                               "code": "ADAPTER_EXECUTION_MODE_CONTRACT_ONLY",
                               "reason": "..."}]}],
  "connector_report": {}
}
```

**Native end-to-end evidence assertion** (real `Crew.kickoff()`, `tests/test_crewai_adapter.py:580-590`):

```python
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
    result = crew.kickoff()
    ...
    events = recorder.stream()["events"]
    assert [event["event_type"] for event in events] == [
        "capability_requested",
        "capability_allowed",
        "tool_invoked",
    ]
    report = recorder.validate()
    assert report["status"] == "pass"
```

---

## 13. Traceability rows

| # | Claim | Evidence | Status |
|---|---|---|---|
| T1 | `nornyx-agentic-adapters` is a separate distribution, v0.2.0, Alpha, depending on `nornyx>=1.10,<2` | `adapters/nornyx-agentic-adapters/pyproject.toml:6-7,15,24` | IMPLEMENTED |
| T2 | CrewAI pinned exactly `==1.15.4`; LangGraph exactly `==1.2.2`; declared as extras | `pyproject.toml:27-28`; `docs/COMPATIBILITY.md:6` | IMPLEMENTED |
| T3 | Framework pins enforced at import time (wrong version → `AdapterConfigurationError`; missing → `MissingOptionalDependencyError`) | `crewai_adapter.py:66-105`; `langgraph.py:45-69`; tests `test_crewai_adapter.py:951-979` | IMPLEMENTED (code+tests) |
| T4 | SPI major 1 asserted at package import; mismatch raises `UnsupportedSPIVersionError` | `__init__.py:34`; `_compat.py:16-34`; `tests/test_compat.py:15-43` | IMPLEMENTED |
| T5 | CrewAI coverage = sync `BaseTool._run` via `Crew.kickoff()` only; async/agent/task/delegation/handoff declared `unsupported` in a machine-readable inventory | `crewai_adapter.py:118-183`; `README.md:68-82`; tests :215,:659 | IMPLEMENTED |
| T6 | Async `_arun` is fail-closed: inherited `NotImplementedError`, action never runs, nothing recorded | `crewai_adapter.py:14-18,131-143`; test :690 | IMPLEMENTED |
| T7 | `enforce()` = evaluate → record decision → (ALLOW only) execute exactly once; non-ALLOW raises `AdapterDenied`; internal errors fail closed | `enforcement.py:28-65`; `tests/test_enforcement.py:61-196` | IMPLEMENTED |
| T8 | Post-action `tool_invoked` recorded only after the action returns; delegation_ref taken from decision basis, never caller args | `crewai_adapter.py:233-261`; tests :342,:421; adapter `CHANGELOG.md:30-42` | IMPLEMENTED |
| T9 | LangGraph coverage = synchronous StateGraph nodes only; occurrence = public `task_id`, attempt = `node_attempt` + validated recorder prefix; retry/loop/parallel/interrupt/resume all tested against real langgraph 1.2.2 | `langgraph.py:144-275`; `tests/test_langgraph_adapter.py:171-283` | IMPLEMENTED |
| T10 | LangGraph interrupts propagate as incomplete attempts, not `runtime_failed` | `langgraph.py:246-253`; test :262 | IMPLEMENTED |
| T11 | Async nodes, remote/distributed execution, subgraph/ToolNode internals unsupported; graph topology `unwrapped` (caller-owned) | `langgraph.py:94-124` | IMPLEMENTED (declared) + NON-GOAL (for this milestone) |
| T12 | Bypassing an adapter bypasses enforcement; Tier 2 cooperative, declared surfaces only; no authentication; no Tier 3 attestation | `README.md:133-150`; `tests/test_crewai_adapter.py:506`; benchmark S15 | IMPLEMENTED (tested control) + NON-GOAL (mandatory interception) |
| T13 | docs 41/44 "adapter conformance" is static, contract-only conformance of `.nyx` adapter declarations — reports prove nothing was executed | schemas `adapter_contract.schema.json:37-42`, `adapter_conformance_report.schema.json:31-54`; `nornyx/connector_runtime.py:769-801`; `tests/test_v07_adapter_conformance.py` | IMPLEMENTED |
| T14 | Live connector execution, credential loading, network calls, automatic approvals are contract-level NON-GOALS | `docs/41...md:65-77`; `docs/44...md:59-72`; schema consts | NON-GOAL |
| T15 | Legacy reference adapters live at `integrations/nornyx_reference_adapters/`, unpackaged, deprecated, renamed from the colliding `nornyx_agentic_adapters` name | `integrations/README.md:3-22`; `docs/MIGRATION.md:10-34`; FINDINGS F3 | IMPLEMENTED |
| T16 | M2-D shim: `GovernanceKernel` reimplemented over public SPI 1.2 `Authorizer.state`; no second read/composition/verification; requires Nornyx ≥1.11.0; unpackaged; widens no coverage | `governance_kernel.py:1-27`; `CHANGELOG.md:11-44`; `COMPATIBILITY.md:8-16`; `tests/test_legacy_governance_shim.py` (32 tests) | IMPLEMENTED |
| T17 | Malformed legacy approval assertions rejected at the boundary before evaluation or recorder mutation | `MIGRATION.md:88-102`; `governance_kernel.py:132-158`; commit `a63f8ca` | IMPLEMENTED |
| T18 | Supported adapters do no file I/O, never load/re-read contracts, and do not use `Authorizer.state`; they consume an injected Authorizer/context/recorder | absence verified by grep over `src/`; `crewai_adapter.py:265-275`; `README.md:160-162` | IMPLEMENTED (verified absence) |
| T19 | The A/B benchmark proves prevention via a side-effect ledger (denied ⇒ 0 attempts/completions; kth decision precedes kth attempt; failed-after-allow ⇒ 0 completions), verdict GO/NO_GO, offline | benchmark `README.md:59-71,16-22`; `ledger.py`; CI job lines 293-416 | IMPLEMENTED |
| T20 | Benchmark controls: S15 bypass runs in both variants; S18 app-rule refusal credited to neither | benchmark `README.md:99-103`; `REVIEWER_QUICKSTART.md:310-312` | IMPLEMENTED |
| T21 | Benchmark surfaced 3 defects (F1 evidence validator, F2 delegation_ref, F3 name collision), all fixed + regression-tested; none changed an enforcement result | `FINDINGS.md:1-20`; benchmark `README.md:119-137` | IMPLEMENTED |
| T22 | CI runs adapter tests against real pinned CrewAI/LangGraph with zero-skip gates and fresh-env installed-wheel smokes; core matrix covers Python 3.10-3.13 + Windows | `.github/workflows/ci.yml:117-291,445-495,497-527` | IMPLEMENTED |
| T23 | Adapter PyPI publishing is tag-bound (`adapters-vX.Y.Z` must equal pyproject version) via OIDC trusted publishing | `.github/workflows/adapters-release.yml:1-19,61-85` | IMPLEMENTED |
| T24 | extensions/ (MCP, A2A, OTel-GenAI) are `status: planned` descriptors only | `extensions/*.yaml` line 2 of each | ROADMAP |
| T25 | apps/ contains exactly one app: the local-only read-only Dev PMO portal | `apps/nornyx-dev-pmo-portal/README.md:1-13,70-78` | IMPLEMENTED (dev tool) |
| T26 | Evidence is cooperative Tier 2: contract-state binding, not runtime proof; validation "proves structure and binding, not truth" | `README.md:143-147`; `REVIEWER_QUICKSTART.md:320-323`; `integrations/README.md:31-37` | GUIDANCE (documented boundary) |

## 14. Unverified or ambiguous

1. **Stale benchmark README rows**: `examples/crewai_governance_benchmark/README.md:43-44` still says "SPI_VERSION == \"1.0\"" and "`nornyx-agentic-adapters` 0.1.0", and README.md:56-57 says the adapter package "is not" on PyPI — while `REVIEWER_QUICKSTART.md:44-49` (updated, cf. commit `6ee29e4` "Update benchmark SPI expectation") says "Nornyx 1.11.0 (SPI 1.2) and `nornyx-agentic-adapters` 0.2.0 are published on PyPI." The quickstart and adapter CHANGELOG ("first published adapter release, 0.2.0", `CHANGELOG.md:93-94`) appear current; the benchmark README table describes the originally audited revision. Actual PyPI presence was not verified from this offline audit.
2. **Benchmark test count**: `REVIEWER_QUICKSTART.md:287` claims "46 tests, zero skips"; `grep -c "def test" tests/test_crewai_governance_benchmark.py` returns 47. Likely one doc-lag or a non-collected helper; not resolved here.
3. **README typo**: `adapters/.../README.md:180-181` contains a truncated sentence ("The CrewAI pin is enforced at import time, not merely declared. Importing / Both framework submodules enforce..."). Cosmetic; the substantive claim is verified in code (T3).
4. **`AdapterMetadata.framework_version_range` is documentation, not enforcement**: the dataclass itself enforces nothing (`metadata.py:12-17`); enforcement lives in each submodule's import-time check. Book text should not attribute enforcement to `AdapterMetadata`.
5. **Adapter conformance reports vs. framework adapters**: no artifact links the §6 conformance-report machinery to the `nornyx-agentic-adapters` package; treating one as evidence about the other would be an error (verified absence of any `adapter_conformance` reference under `adapters/`).
6. **`CoverageInventory.as_dict()` is JSON-serializable but no in-repo pipeline exports it as a published artifact** — the inventory is asserted in tests and the CI wheel smoke (ci.yml:241-243), not written to a report file.
7. **CrewAI "1.15.4" as an ecosystem fact** (release dates, upstream API stability) is outside this repo and was not externally verified; all claims here are about what this repo pins and tests.
