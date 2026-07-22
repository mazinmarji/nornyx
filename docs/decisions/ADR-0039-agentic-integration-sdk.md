# ADR-0039 — Agentic Integration SDK: `nornyx.agentic` authorization SPI and distributable adapters

- Status: Proposed (design only; execution is a separate, owner-authorized milestone)
- Date: 2026-07-20
- Revised: 2026-07-22 (pilot-derived authorization-SPI correction, with the Step-3
  independent-audit findings F1–F8 and their binding refinements resolved;
  supersedes the original "re-export-only facade / kernel stays in adapters"
  decision)
- Decision owner: human repository owner
- Relates to: ADR-0032 (verifiable effective approvals), ADR-0037 (AN-005
  reference adapters, deliberately unpackaged), ADR-0040 (governance assurance
  tiers — this SPI is a **Tier 2, cooperative** boundary), and the external
  OpenHands governance pilot (external-adopter requirement that drove this
  revision)

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

**(b) A framework-neutral authorization engine** — lives in the submodule
`nornyx.agentic.authz` and is re-exported through `nornyx.agentic`. The shapes
below are **frozen** by the Step-3 independent API-design audit; the subsections
that follow fix the lifecycle, revision binding, temporal semantics, event
phases, evidence recorder, and code taxonomy.

```python
# nornyx.agentic.authz  (re-exported via nornyx.agentic)
SPI_VERSION = "1.0"

def load_authorizer(contract_path, lock_path, *, validation_as_of: str) -> "Authorizer":
    """Load, validate (as of validation_as_of), and lock-verify one local
    contract. Fail-closed; raises with an AuthorizerLoadCode."""

@dataclass(frozen=True)
class EvaluationContext:
    decision_at: str                   # evaluation instant for ALL temporal semantics
    observed_subject_revision: str     # MANDATORY; must equal the contract's subject_revision

# Discriminated request union — each variant carries ONLY its valid fields.
CapabilityRequest(identity_ref: str, capability_ref: str)
DelegationRequest(delegation_id: str)
HandoffRequest(handoff_id: str)
ApprovalRequest(identity_ref: str, approval: "ApprovalAssertion")
ZoneCrossingRequest(identity_ref: str, source_zone: str, target_zone: str, approval: "ApprovalAssertion | None" = None)
DataShareRequest(identity_ref: str, target_ref: str, categories: tuple[str, ...], source_zone: str, target_zone: str)
AuthorizationRequest = (
    CapabilityRequest | DelegationRequest | HandoffRequest
    | ApprovalRequest | ZoneCrossingRequest | DataShareRequest
)

@dataclass(frozen=True)
class ApprovalAssertion:                # typed; never a raw Mapping
    approval_ref: str
    claimed_approver_ref: str
    claimed_actor_type: str
    role: str
    granted: bool
    action_ref: str
    subject_revision: str
    issued_at: str | None = None
    expires_at: str | None = None
    evidence_refs: tuple[str, ...] = ()

@dataclass(frozen=True)
class DecisionBasis:                    # provenance via DECLARED ids only (stable)
    kind: str                          # "membership"|"delegation"|"capability"|"approval"|"zone"|"share"|"binding"
    ref: str                           # declared element id
    detail: str = ""

@dataclass(frozen=True)
class DecisionEventIntent:
    event_type: str                    # a decision-phase event type only (see "Event phases")
    fields: Mapping[str, Any]          # NO timestamp/sequence/producer/digests — the recorder stamps those

@dataclass(frozen=True)
class Decision:
    effect: DecisionEffect             # ALLOW | DENY | APPROVAL_REQUIRED
    code: DecisionCode                 # ALWAYS present, including ALLOWED
    reason: str
    basis: tuple[DecisionBasis, ...]
    event_intents: tuple[DecisionEventIntent, ...]

class Authorizer(Protocol):
    contract_digest: str
    network_lock_digest: str
    subject_revision: str              # the contract's bound agentic_network.subject_revision
    def resolve_identity(self, framework: str, agent_key: str) -> str: ...  # raises IdentityResolutionError
    def evaluate(self, request: AuthorizationRequest, *, context: EvaluationContext) -> Decision: ...
```

**Lifecycle.** The loaded `Authorizer` is **immutable, synchronous,
deterministic, reusable, and safe for concurrent evaluation**; it performs **no
I/O after load** and **reads no wall-clock time** during evaluation or evidence
recording. It holds no clock, event list, or per-mission counters (that state
lives in the evidence recorder). Identity is resolved separately by
`resolve_identity(framework, agent_key)`, which raises `IdentityResolutionError`
(carrying an `IdentityResolutionCode`) — not a `Decision`. Malformed or
incomplete requests fail closed with `DecisionCode.REQUEST_MALFORMED`.

**Revision binding — two independent, always-exact checks.**
- *Runtime target binding.* `context.observed_subject_revision` **must exactly
  equal** the loaded contract's `agentic_network.subject_revision`. Any mismatch
  is **always** `DENY` / `REVISION_MISMATCH` — never conditional on any approval
  flag. (This mirrors the existing runtime validator, which treats an event
  revision different from the contract revision as `AN_EVT_REVISION_MISMATCH`; it
  permits no weaker non-exact runtime binding.)
- *Approval binding.* When the composed `EffectiveApproval` declares a
  `revision_binding`, the `ApprovalAssertion.subject_revision` **must exactly
  match it**; otherwise `DENY` / `APPROVAL_REVISION_MISMATCH`. A mismatched bound
  approval is never allowed-with-basis.
- *Canonical revision syntax* (no branch names, abbreviated SHAs, or implicit
  normalization aliases): `git:<40-lowercase-hex>`, `git:<64-lowercase-hex>`, or
  `sha256:<64-lowercase-hex>`.

**Temporal semantics.** `validation_as_of` governs deterministic document/load
validation at `load_authorizer`. `context.decision_at` governs **all** temporal
action semantics at evaluation: identity validity, membership validity,
delegation validity, revocations, and approval issuance/expiry/invalidation. The
two are distinct arguments and must not be conflated; the authorizer reads no
wall-clock time.

**Approvals.** A typed `ApprovalAssertion` (never a raw mapping). Nornyx validates
it for **consistency** against the composed `EffectiveApproval` (denied actor
types, eligible roles, `revision_binding`, expiry/invalidation evaluated at
`decision_at`, and `granted`). Nornyx does **not authenticate** the claimed
approver; stronger authenticity requires trusted caller-supplied source context
or external attestation, as established by ADR-0032. This is a consistency
binding, not a signature (ADR-0040 Tier-2 boundary).

**Decisions.** `evaluate` returns **decision-event intents only** and **never**
any post-action observation; a pre-execution authorization must never assert that
an action occurred. Every `Decision` carries a `DecisionCode`, including
`ALLOWED` (never `None`). `APPROVAL_REQUIRED` is a distinct effect from an
ordinary `DENY`. `DecisionBasis` expresses provenance using **declared element
ids only**, exposing no unstable internals.

**No argument interpretation.** The engine authorizes *declared Nornyx concepts*
only. It never parses raw shell commands, file paths, URLs, or tool arguments —
argument→concept normalization is the adapter's job.

**Surface scope.** A `Decision` governs exactly **one request and its declared
surface**. It never establishes whole-application coverage or assurance
(ADR-0040).

#### Event phases (frozen)

The authorizer may return **only decision-event intents**. An adapter triggers
**observation** recording only **after** the represented occurrence has actually
happened.

- **Decision-event intents:** `capability_requested`, `capability_allowed`,
  `capability_denied`, `delegation_requested`, `delegation_accepted`,
  `delegation_rejected`, `approval_requested`, `approval_granted`,
  `approval_rejected`, `policy_violation`.
- **Post-action observations:** `agent_invoked`, `tool_invoked`,
  `handoff_initiated`, `handoff_completed`, `trust_zone_crossed`, `data_shared`,
  `identity_revoked`, `runtime_failed`.

`handoff_initiated` is an **observation**: it asserts that initiation occurred,
not merely that it was authorized.

#### Evidence recorder (core mechanism, in `nornyx.agentic.authz`, re-exported)

A **core** recorder — not per-adapter — turns intents (and adapter-supplied
observations) into a schema-valid `nornyx.agentic_runtime_events.v1` stream. It:

- assigns event ids and **mission-local sequence numbers**;
- stamps **producer** metadata;
- stamps the loaded **contract and lock digests**;
- stamps the **already-verified observed subject revision**;
- validates the **closed event field set**;
- produces a schema-valid events envelope (via `validate_runtime_events`).

It provides **deterministic construction and consistency binding only.** It does
**not** authenticate the adapter, attest that the occurrence happened, or make an
event *true* — the schema validates supplied-record conformance, not runtime
truth (ADR-0040 Tier 2). A cooperative adapter can still fabricate an
observation; the recorder does not prevent that.

#### Code taxonomy (frozen — three enums)

```python
class AuthorizerLoadCode(Enum):        # raised by load_authorizer
    CONTRACT_INVALID; PROFILE_MISSING; LOCK_INVALID; LOCK_STALE

class IdentityResolutionCode(Enum):    # raised by resolve_identity (IdentityResolutionError)
    IDENTITY_UNKNOWN; IDENTITY_AMBIGUOUS

class DecisionCode(Enum):              # returned by evaluate (every Decision, incl. allow)
    ALLOWED
    CAPABILITY_UNKNOWN; CAPABILITY_DENIED
    DELEGATION_UNKNOWN; DELEGATION_INACTIVE
    HANDOFF_UNKNOWN; HANDOFF_AUTHORITY
    APPROVAL_REQUIRED; APPROVAL_NON_HUMAN; APPROVAL_ROLE_INVALID
    APPROVAL_NOT_GRANTED; APPROVAL_STALE; APPROVAL_REVISION_MISMATCH
    ZONE_CROSSING_DENIED; CROSSING_APPROVAL_REQUIRED
    SENSITIVE_SHARING; SHARE_NOT_ALLOWED
    REVISION_MISMATCH; REQUEST_MALFORMED
```

Identity-resolution outcomes live in `IdentityResolutionCode` (not
`DecisionCode`) because `resolve_identity` raises before `evaluate` is called.

### 2. `nornyx-agentic-adapters` — the distributable package (framework glue only)

One separately published package (own SemVer, `nornyx>=1.8,<2`, extras
`[crewai]` / `[langgraph]`) that depends **only** on `nornyx.agentic`. It owns
everything framework-specific:

- framework **action interception** and **executor wrapping**;
- **argument normalization** — mapping a framework action (an OpenHands
  terminal command / file path / MCP call, a CrewAI task, a LangGraph node) to a
  declared Nornyx concept (identity + capability / zone / category), i.e.
  building a typed `AuthorizationRequest`;
- **triggering** the core evidence recorder — recording decision intents from a
  `Decision`, and recording observations **only after** the real action has
  happened; it never re-implements binding;
- framework **version compatibility**.

Core `nornyx` never imports CrewAI/LangGraph/OpenHands; the packaging guard
(`tests/test_agentic_integrations.py::test_default_install_does_not_package_integrations`)
is preserved and extended to the authorization engine.

### 3. The `GovernanceKernel` is the seed, not the API

The existing `integrations/.../governance_kernel.py` logic is **migrated into
core** behind the `Authorizer` protocol (return a `Decision` rather than raising;
return event *intents* rather than emitting; drop the internal clock/counters;
read time only from `decision_at`). The in-tree kernel remains as a **temporary
adapter compatibility shim** for **at least one published minor release**; its
removal must **not** occur before the following minor release and **only after**
completed migration documentation and compatibility tests. Its legacy
`AN_ADAPTER_*` codes stay **in that shim** (with a documented `AN_ADAPTER_*` ⇄
`DecisionCode` mapping) and are **not** promoted into the new public
`nornyx.agentic` namespace — they were never a public SPI.

### 4. Versioning, surface guards & compatibility

`SPI_VERSION` is the integration-contract version, independent of the package
version. Adapters declare the SPI range they support and assert it at import. A
facade **surface-freeze test** pins `nornyx.agentic.__all__` (and the typed
protocol names); an **import-boundary test** in the adapter package proves it
imports only `nornyx.agentic`.

**Compatibility.** Requests and decisions are **in-process** SPI objects governed
by `SPI_VERSION`; the **only serialized contract** is the runtime-events stream
(`nornyx.agentic_runtime_events.v1`). Minor-compatible: a new request variant, a
new *optional* field, or a new decision-code member. Breaking: removing or
renaming a variant/field, making an optional field required, or changing the
meaning of an existing code. The surface-freeze and import-boundary tests enforce
this.

### 5. Compatibility matrix (published in the adapter README + CI)

| adapters | nornyx SPI | CrewAI | LangGraph | Python |
| --- | --- | --- | --- | --- |
| 0.1.x | 1.0 (nornyx 1.8–1.x) | test lowest+highest | test lowest+highest | 3.10–3.13 |

## Consequences

- **Positive.** External adopters get a **stable, typed authorization API**, not
  a set of internal names; Nornyx contract semantics live in Nornyx, not in a
  framework distribution; core stays framework-free; the adapter package versions
  on its own cadence; the decision/observation split makes evidence honest (no
  pre-execution "it happened" claims); the typed approval assertion, mandatory
  observed-revision, and `decision_at` close the provenance, binding, and
  temporal gaps the pilot found.
- **Cost.** A larger core surface to maintain (the authorization protocol and the
  evidence-recorder mechanism, not just re-exports) and a multi-step migration of
  the reference adapters through the shim. Accepted — the alternative ships
  Nornyx's core policy semantics inside an adapter wheel.
- **Assurance boundary (ADR-0040).** This SPI is **Tier 2, cooperative**:
  bypassing the adapter bypasses enforcement; the engine authorizes declared,
  wrapped surfaces only; it does not authenticate agents or approvers, execute
  tools, or assert runtime-event truth; a `Decision` is scoped to one declared
  surface and never upgrades the whole application. It never, on its own,
  establishes Tier 3.

## Non-goals

The `nornyx.agentic` authorization engine does **not**:

- interpret raw framework paths, shell commands, URLs, or tool arguments
  (argument→concept normalization is the adapter's job; deep argument semantics
  are a separate, deferred concern);
- read wall-clock time during evaluation or recording (all temporal semantics use
  `decision_at`);
- import any agent framework, execute tools, or run a workflow;
- authenticate approvers, grant approvals, or issue identities;
- attest that an observation occurred, or claim that any runtime event is *true*
  (evidence is contract-state binding only);
- imply whole-application coverage from a single-surface decision;
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
  Rejected: a pre-execution decision must never assert that an action occurred;
  intents + a separate recorder keep evidence truthful.
- **Condition runtime revision binding on approval `exact_revision_required`.**
  Rejected: the runtime target binding is always exact and unconditional
  (`REVISION_MISMATCH`), independent of any approval flag; a mismatched bound
  approval is a separate, also-unconditional `APPROVAL_REVISION_MISMATCH`.
- **Promote `AN_ADAPTER_*` as public aliases.** Rejected: those codes were never
  a public SPI; they remain behind the adapter shim with a documented mapping.
- **Two packages (`nornyx-crewai` / `nornyx-langgraph`).** Deferred: the adapters
  share one kernel; revisit only if the frameworks diverge enough to justify it.

## Migration plan

1. Land `nornyx/agentic/` (re-exports + `SPI_VERSION` + surface-freeze test) in a
   `nornyx` minor release (≥1.8).
2. Migrate the `GovernanceKernel` decision logic into the core `Authorizer`
   (return `Decision`; intents not events; immutable; time from `decision_at`);
   add the typed `ApprovalAssertion`, `EvaluationContext`, the core evidence
   recorder, and the three code enums.
3. Stand up `nornyx-agentic-adapters` (framework extras + argument normalization +
   recorder triggering + import-boundary test + matrix CI), depending only on
   `nornyx.agentic`.
4. Keep the in-tree `integrations/` kernel as a deprecated compat shim for **at
   least one published minor release** (retaining `AN_ADAPTER_*` with the mapping
   table); removal not before the following minor release and only after
   completed migration documentation and compatibility tests. Update AN-005/AN-006
   docs and `run_demo.py` to the new SPI; re-baseline example evidence fixtures
   affected by the stricter approval and observed-revision checks.
5. Ship a pip-only example that runs without cloning `nornyx`.

## Execution checklist (follow-on milestone, not this ADR)

1. **Independent API-design audit** — completed; findings F1–F8 and their binding
   refinements are folded into §1(b) above.
2. Facade re-exports + `SPI_VERSION` + surface-freeze test.
3. Core `Authorizer` (migrate kernel; return `Decision`/intents; immutable; time
   from `decision_at`) + typed `ApprovalAssertion` + `EvaluationContext` + core
   evidence recorder + `AuthorizerLoadCode` / `IdentityResolutionCode` /
   `DecisionCode`.
4. `nornyx-agentic-adapters` package (extras, normalization, recorder triggering,
   import-boundary test, matrix CI); deprecate the in-repo kernel to a shim with
   the `AN_ADAPTER_*` ⇄ `DecisionCode` mapping.
5. Pip-only example; external pilot consumes the SPI.
