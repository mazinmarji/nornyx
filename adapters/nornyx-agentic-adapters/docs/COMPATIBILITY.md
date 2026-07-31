# Compatibility matrix

| `nornyx-agentic-adapters` | `nornyx` (SPI) | SPI version | CrewAI | LangGraph | Python |
| --- | --- | --- | --- | --- | --- |
| 0.1.x | `>=1.8,<2` | 1.0 | `==1.15.4` | Not implemented | 3.10–3.13 |
| 0.2.x | `>=1.10,<2` | 1.x (tested with 1.1 and 1.2) | `==1.15.4` | `==1.2.2` | 3.10–3.13 |

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
- **CrewAI (M2-B) and LangGraph (M2-C) are implemented** (see the README's
  Status table). The CrewAI column above is live: `[crewai]`
  installs `nornyx_agentic_adapters.crewai_adapter`, which wraps **synchronous**
  tool invocation only (see the README's Coverage note) — agent invocation,
  task invocation, delegation, handoff, and **asynchronous tool invocation
  (`arun`/`_arun`)** are declared `unsupported`, not silently omitted. Async is
  not governed: the adapter does not override `_arun`, so CrewAI's async path
  raises `NotImplementedError` and the wrapped action never runs. `[langgraph]`
  provides synchronous StateGraph node wrapping with native retry, loop,
  parallel, interrupt, and checkpoint-resume coverage. Async and remote
  LangGraph execution remain unsupported.
- **Framework pins are enforced at import time, not just declared.** Importing
  either framework submodule fails closed on an unsupported installed version.
  For CrewAI, a missing
  CrewAI distribution raises `MissingOptionalDependencyError`; an installed but
  non-`1.15.4` version — or missing/malformed version metadata — raises
  `AdapterConfigurationError`; only `crewai==1.15.4` imports and operates.
  LangGraph follows the same rule and requires exactly `langgraph==1.2.2`.

## Minor-compatible vs. breaking changes

Following the same rule ADR-0039 applies to the core SPI:

- **Minor-compatible**: widening a framework's tested version range with new
  evidence; adding a new optional field to a public dataclass; adding a new
  `SurfaceStatus` value; adding a new framework-specific submodule.
- **Breaking**: narrowing a supported range; removing or renaming a public
  type/field; changing the meaning of an existing `SurfaceStatus` value;
  changing `enforce()`'s evaluate → record → execute ordering guarantee.

## `EvidenceRecorder` integrity (ADR-0041)

`EvidenceRecorder.record_decision`/`record_observation` now validate
`mission_id`, `event_type`, and `producer_id`/`producer_version`/
`producer_type` against their published builtin annotations. Exact supported
builtins remain unchanged; subclasses of supported `str`, `int`, `float`,
`dict`, `list`, and `tuple` types are accepted and immediately canonicalized
through explicitly invoked base-type operations. Only exact plain builtins
enter recorder state, tuple values normalize to exact lists, and
string-subclass mapping keys normalize to exact strings without executing
subclass overrides. An arbitrary non-`dict` `Mapping` used as
`DecisionEventIntent.fields` is the explicit callback boundary: its protocol
is invoked once outside the recorder lock to create a detached snapshot, and
the source object is never retained. `set`/`frozenset`, non-finite numbers,
non-string keys, unsupported objects, excessive nesting, self-reference, and
canonical-key collisions fail closed before recorder mutation.

This preserves existing recorder call signatures. SPI 1.1 adds explicit
occurrence and validated-resume APIs without changing the major compatibility
boundary. Every value the adapters pass to the recorder is an exact builtin.
`EvidenceRecorder` is also internally lock-protected and safe to share across
threads. See
`docs/decisions/ADR-0041-evidence-recorder-integrity-and-serialization.md`
in the core repository for the full rationale.

## Authorizer state (SPI 1.2)

SPI 1.2 adds `Authorizer.state` and `AuthorizerState`. This is an additive
read-only capability within the supported SPI major: compatibility shims and
evidence validators can consume detached views of the already loaded contract,
effective governance composition, and verified lock without private attributes
or a second filesystem read. It changes no request, decision, recorder,
runtime-events schema, occurrence, or replay behavior. Adapter 0.2.x continues
to accept SPI major 1.
