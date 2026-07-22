# ADR-0039 — Agentic Integration SDK: `nornyx.agentic` authorization SPI and distributable adapters

- Status: Proposed (design only; execution is a separate, owner-authorized milestone)
- Date: 2026-07-20
- Revised: 2026-07-22 (pilot-derived authorization-SPI correction; supersedes the
  original "re-export-only facade / kernel stays in adapters" decision)
- Decision owner: human repository owner
- Relates to: ADR-0037 (AN-005 reference adapters, deliberately unpackaged),
  ADR-0040 (governance assurance tiers — this SPI is a **Tier 2, cooperative**
  boundary), and the external OpenHands governance pilot (external-adopter
  requirement that drove this revision)

## Context

AN-005 (ADR-0037) shipped CrewAI and LangGraph reference adapters under
`integrations/nornyx_agentic_adapters/`. They are **excluded from the wheel** —
correct, to keep heavy frameworks out of stable core — but they reach directly
into Nornyx internals (`nornyx.agentic_artifacts`, `nornyx.checker`,
`nornyx.governance`, `nornyx.parser`, `nornyx.agentic_evidence`). Two problems
follow: the integrations are **not distributable** (a `pip install nornyx` user
must clone and manipulate `sys.path`), and there is **no supported boundary** —
adapters depend on Nornyx's internal module layout, so refactors silently break
them.

**What the external pilot validation added (2026-07-22).** A read-only validation
of an external adopter's requirement against `origin/main`
(`81ce49a7e3fdeb721ac96b4992cc175882a885d5`) established two facts that change
this ADR's decision:

1. The **per-action authorization logic already exists and is already
   framework-neutral** — `integrations/nornyx_agentic_adapters/governance_kernel.py`
   (`GovernanceKernel`) imports Nornyx modules only (no CrewAI/LangGraph),
   loads + lock-verifies a contract, resolves identities, and decides
   capability/delegation/handoff/approval/zone/data-share with a deterministic
   code set. It is an **implementation seed, not a public API.**
2. A **re-export-only facade is insufficient** for an external adopter. Adopters
   do not need Nornyx's internal function names; they need a **stable, typed
   authorization protocol** with a supported request/decision shape, approval
   assertion, and code taxonomy. Those are precisely the parts that do **not**
   exist yet and that a curated re-export cannot provide.

The original decision (a facade that "adds no new behavior" while the kernel
stays in the adapter package) therefore places **Nornyx contract semantics** —
the authorization engine — in a **framework adapter distribution**. That is the
wrong home: the engine is Nornyx, not framework glue.

## Decision

Introduce a **supported `nornyx.agentic` SPI** (part of core `nornyx`, shipped in
the wheel) that exposes **both** curated re-exports **and a framework-neutral
authorization engine**, and keep framework-specific behavior in a **separately
versioned, separately published** package `nornyx-agentic-adapters`.

The authorization engine belongs in the facade **because it implements Nornyx
contract semantics** (identities, capabilities, delegations, handoffs, approvals,
trust zones, data-sharing categories, and revision binding). It is not framework
behavior, and it imports no framework.

### 1. `nornyx/agentic/` — the supported SPI (two parts)

**(a) Curated re-exports** — one stable import path for names that already exist
in their home modules (`load_nyx`; `check_document`, `has_errors`;
`contract_digest`, `agentic_network_lock_digest`, `load/verify/build/write_agentic_network_lock`,
lock/schema constants; `validate_runtime_events`, `load_runtime_events`;
`registry_for_contract`, `compose_document_governance`, `GovernanceError`). A
surface-freeze test pins the exported set.

**(b) A framework-neutral authorization engine** — a small, typed, supported
protocol (illustrative signatures; final shapes fixed during the independent API
review that precedes implementation):

```python
# nornyx.agentic
SPI_VERSION = "1.0"

def load_authorizer(contract_path, lock_path, *, as_of: str) -> "Authorizer":
    """Load, validate, and lock-verify one local contract. Fail-closed;
    raises with an AuthorizerLoadCode on invalid/stale contract or lock."""

@dataclass(frozen=True)
class EvaluationContext:
    as_of: str                        # decision time (ISO-8601)
    observed_subject_revision: str    # MANDATORY — the external target's revision

# Discriminated request union — each variant carries ONLY fields valid for it.
AuthorizationRequest = (
    CapabilityRequest | DelegationRequest | HandoffRequest
    | ApprovalRequest | ZoneCrossingRequest | DataShareRequest
)

@dataclass(frozen=True)
class ApprovalAssertion:              # typed; never a raw Mapping
    claimed_actor_type: str; role: str; approval_ref: str
    action_or_scope: str; subject_revision: str
    issued_at: str | None = None; expires_at: str | None = None
    evidence_refs: tuple[str, ...] = ()

@dataclass(frozen=True)
class Decision:
    effect: DecisionEffect            # ALLOW | DENY | APPROVAL_REQUIRED
    code: DecisionCode                # ALWAYS present, including ALLOWED
    reason: str
    basis: tuple[DecisionBasis, ...]  # provenance of the outcome
    event_intents: tuple[DecisionEventIntent, ...]  # decision events only

class Authorizer(Protocol):
    contract_digest: str
    network_lock_digest: str
    def resolve_identity(self, framework: str, agent_key: str) -> str: ...
    def evaluate(self, request: AuthorizationRequest, *, context: EvaluationContext) -> Decision: ...
```

Design principles the SPI must honor:

- **Immutable & thread-safe.** The `Authorizer` holds no clock, no event list,
  and no per-mission counters. (The seed kernel is stateful through all three;
  that state moves to a separate evidence recorder.)
- **Discriminated requests.** No option-heavy request object; each operation is
  its own type carrying only valid fields. Identity is resolved by a separate
  `resolve_identity(framework, agent_key)` call, not a boolean flag.
- **Mandatory bound context.** `EvaluationContext.observed_subject_revision` is
  **required** — the engine governs an external subject whose revision is
  observed at runtime, not the contract's own declared revision.
- **Typed approval assertion.** Approvals are a typed `ApprovalAssertion`, not a
  raw mapping. Nornyx checks its **consistency** against the composed
  `EffectiveApproval` (denied actor types, eligible roles, revision binding /
  exact-revision requirement, expiry, invalidation). Nornyx does **not**
  authenticate the approver (a consistency binding, not a signature — ADR-0040
  Tier-2 boundary).
- **Decision intents, not finalized events.** `evaluate` returns
  **decision-event intents only** (`capability_requested`,
  `capability_allowed`/`_denied`, `approval_*`). It **must not** return
  `tool_invoked` or any post-execution observation. Adapters record execution
  observations **only after the tool actually runs** — otherwise a pre-execution
  authorization could assert that a tool was invoked when it was not.
- **Separate load-error and decision taxonomies.** `AuthorizerLoadCode`
  (contract invalid / profile missing / lock invalid / lock stale) is distinct
  from `DecisionCode` (allowed, capability denied, approval required, revision
  mismatch, zone crossing denied, …). Every `Decision` carries a code, including
  `ALLOWED` (never `None`).
- **Fail-closed.** Malformed or incomplete requests deny
  (`DecisionCode.REQUEST_MALFORMED`); they never allow by default.
- **No argument interpretation.** The engine authorizes *declared Nornyx
  concepts*. It never parses raw shell commands, file paths, URLs, or tool
  arguments.

### 2. `nornyx-agentic-adapters` — the distributable package (framework glue only)

One separately published package (own SemVer, `nornyx>=1.8,<2`, extras
`[crewai]` / `[langgraph]`) that depends **only** on `nornyx.agentic`. It owns
everything framework-specific:

- framework **action interception** and **executor wrapping**;
- **argument normalization** — mapping a framework action (an OpenHands
  terminal command / file path / MCP call, a CrewAI task, a LangGraph node) to a
  declared Nornyx concept (identity + capability / zone / category), i.e.
  building a typed `AuthorizationRequest`;
- an **evidence recorder** that stamps decision-event intents (and post-execution
  observations) with timestamp / sequence / producer and validates them via
  `validate_runtime_events`;
- framework **version compatibility**.

Core `nornyx` never imports CrewAI/LangGraph/OpenHands; the packaging guard
(`tests/test_agentic_integrations.py::test_default_install_does_not_package_integrations`)
is preserved and extended to the authorization engine.

### 3. The `GovernanceKernel` is the seed, not the API

The existing `integrations/.../governance_kernel.py` logic is **migrated into
core** behind the `Authorizer` protocol (return a `Decision` rather than raising;
return event *intents* rather than emitting; drop internal clock/counters). The
in-tree kernel remains for **one release** as a **temporary adapter
compatibility shim**. Its legacy `AN_ADAPTER_*` codes stay **in that shim** and
are **not** promoted into the new public `nornyx.agentic` namespace — they were
never a public SPI.

### 4. Versioning & surface guards

`SPI_VERSION` is the integration-contract version, independent of the package
version. Adapters declare the SPI range they support and assert it at import. A
facade **surface-freeze test** pins `nornyx.agentic.__all__` (and the typed
protocol names); an **import-boundary test** in the adapter package proves it
imports only `nornyx.agentic`.

### 5. Compatibility matrix (published in the adapter README + CI)

| adapters | nornyx SPI | CrewAI | LangGraph | Python |
| --- | --- | --- | --- | --- |
| 0.1.x | 1.0 (nornyx 1.8–1.x) | test lowest+highest | test lowest+highest | 3.10–3.13 |

## Consequences

- **Positive.** External adopters get a **stable, typed authorization API**, not
  a set of internal names; Nornyx contract semantics live in Nornyx, not in a
  framework distribution; core stays framework-free; the adapter package versions
  on its own cadence; the decision/observation split makes evidence honest
  (no pre-execution "invoked" claims); the typed approval assertion and mandatory
  observed-revision close the provenance and binding gaps the pilot found.
- **Cost.** A larger core surface to maintain (the authorization protocol, not
  just re-exports) and a one-release migration of the reference adapters through
  the shim. Accepted — the alternative ships Nornyx's core policy semantics
  inside an adapter wheel.
- **Assurance boundary (ADR-0040).** This SPI is **Tier 2, cooperative**:
  bypassing the adapter bypasses enforcement; the engine authorizes declared,
  wrapped surfaces only; it does not authenticate agents or approvers, execute
  tools, or assert runtime-event truth. It never, on its own, establishes Tier 3.

## Non-goals

The `nornyx.agentic` authorization engine does **not**:

- interpret raw framework paths, shell commands, URLs, or tool arguments
  (argument→concept normalization is the adapter's job; deep argument semantics
  are a separate, deferred concern);
- import any agent framework, execute tools, or run a workflow;
- authenticate approvers, grant approvals, or issue identities;
- claim that any runtime event is *true* (evidence is contract-state binding
  only);
- provide Tier 3 independent runtime assurance (ADR-0040).

## Alternatives considered

- **Keep the re-export-only facade; leave the kernel in the adapter package.**
  Rejected: it places Nornyx contract semantics in a framework distribution and
  gives external adopters no stable authorization API — the exact gap the pilot
  surfaced.
- **Publish the option-heavy `evaluate_action(registry, action)` shape.**
  Rejected: it permits invalid field combinations, forces runtime validation of
  fields static types should exclude, and passes a `GovernanceRegistry` (a pack
  registry) where a loaded, lock-verified contract is required.
- **Return finalized events (including `tool_invoked`) from `evaluate`.**
  Rejected: a pre-execution decision must never assert that a tool ran; intents +
  a separate recorder keep evidence truthful.
- **Promote `AN_ADAPTER_*` as public aliases.** Rejected: those codes were never
  a public SPI; they remain behind the adapter shim.
- **Two packages (`nornyx-crewai` / `nornyx-langgraph`).** Deferred: the adapters
  share one kernel; revisit only if the frameworks diverge enough to justify it.

## Migration plan

1. Land `nornyx/agentic/` (re-exports + `SPI_VERSION` + surface-freeze test) in a
   `nornyx` minor release (≥1.8).
2. Migrate the `GovernanceKernel` decision logic into the core `Authorizer`
   (return `Decision`; intents not events; immutable); add the typed
   `ApprovalAssertion`, `EvaluationContext`, and split code taxonomies.
3. Stand up `nornyx-agentic-adapters` (framework extras + argument normalization +
   evidence recorder + import-boundary test + matrix CI), depending only on
   `nornyx.agentic`.
4. Keep the in-tree `integrations/` kernel one release as a deprecated compat
   shim (retaining `AN_ADAPTER_*`); update AN-005/AN-006 docs and `run_demo.py`
   to the new SPI; re-baseline example evidence fixtures affected by the stricter
   approval and observed-revision checks.
5. Ship a pip-only example that runs without cloning `nornyx`.

## Execution checklist (follow-on milestone, not this ADR)

1. **Independent API-design audit** of the protocol in §1(b) *before* any code
   (the next milestone after this ADR).
2. Facade re-exports + `SPI_VERSION` + surface-freeze test.
3. Core `Authorizer` (migrate kernel; return `Decision`/intents; immutable) +
   typed `ApprovalAssertion` + `EvaluationContext` + `AuthorizerLoadCode`/
   `DecisionCode`.
4. `nornyx-agentic-adapters` package (extras, normalization, evidence recorder,
   import-boundary test, matrix CI); deprecate the in-repo kernel to a shim.
5. Pip-only example; external pilot consumes the SPI.
