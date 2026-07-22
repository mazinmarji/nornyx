# ADR-0040 — Governance Assurance Tiers and Claim Boundaries

- Status: Proposed (design only; execution is a separate, owner-authorized milestone)
- Date: 2026-07-22
- Decision owner: human repository owner
- Relates to: ADR-0032 (verifiable effective approvals), ADR-0035 (network
  artifacts and lock), ADR-0036 (agentic runtime event evidence), ADR-0037
  (reference adapters — cooperative enforcement boundary), ADR-0039 (agentic
  integration SDK)

## Context

Nornyx already distinguishes, informally and correctly, between what it
*declares*, what its cooperative adapters *enforce*, and what only an external
system can *independently assure* (see
`docs/agentic-network/10_BEFORE_AFTER_AND_POSITIONING.md`). That distinction is
not labeled anywhere in reports, artifacts, or examples. Without an explicit
label, every future feature is free to imply a stronger assurance than it
delivers — the exact overclaiming risk called out in the backlog review.

The word "guarantee" is deliberately avoided: Tier 1 does not guarantee runtime
behavior, and Tier 3 is not delivered by Nornyx alone. These are **assurance
tiers with claim boundaries**, not product guarantees.

Three facts from the current codebase set the boundaries this ADR must encode:

1. **Declarative controls are design-time.** `.nyx` contracts, deterministic
   generated artifacts, static checks, and revision-bound approvals
   (ADR-0032/0035) are evaluated *without executing the agentic workflow*. They
   constrain declarations, not runtime behavior. The approval source hash is a
   consistency binding, not a cryptographic signature.
2. **Adapter enforcement is cooperative.** ADR-0037's reference adapters wrap
   declared surfaces and evaluate the contract in the execution path, but
   bypassing the adapter bypasses the hook. Enforcement covers only declared,
   wrapped surfaces and cannot prove that no undeclared surface exists.
3. **Independent runtime assurance is not supplied by Nornyx alone.** The
   runtime-events schema (`schemas/agentic_runtime_events_v1.schema.json`)
   permits `producer: external_runtime` and requires each event to bind
   `network_id`, `contract_digest`, `network_lock_digest`, and
   `subject_revision`; Nornyx cross-checks these **contract-state binding**
   fields against validated state and emits deterministic diagnostics on
   mismatch. Accepting an event proves only conformance of the supplied record —
   not that the event is true. Nornyx does **not** authenticate the producer,
   does **not** verify `signature_ref` (only its identifier shape is validated),
   does **not** semantically verify that `input_digest` or `output_digest`
   corresponds to the actual runtime input or output payload, does **not**
   observe or monitor the runtime, and does **not** attest that any policy was
   deployed. The verified property is contract-state binding; runtime-payload
   truth is not established. Independent assurance therefore requires an external
   enforcement/attestation system plus future Nornyx work.

## Decision

Adopt a three-tier **assurance** model. Every Nornyx assurance claim — in
reports, artifacts, docs, and examples — must be labeled with the tier it
belongs to and its declared surface scope; ordinary factual or descriptive
statements do not need tier labels. Each tier below fixes its **evidence
basis**, its **claim eligibility** (when the tier may be asserted), its
**limitations**, and the **claims it prohibits**.

Tier 1 is the declarative foundation for all assurance claims. Tier 2 and Tier 3
represent different runtime-assurance paths. Tier 3 may incorporate Tier 2
cooperative enforcement, but it does not require a Nornyx adapter where an
independent external system enforces and evidences the claimed surfaces.
Assurance remains scoped to the claims and surfaces supported by the evidence.

**Scope of a tier claim.** Assurance tiers apply to a specific claim, evidence
package, and declared set of execution surfaces — not automatically to an entire
application, deployment, framework, or Nornyx release. A system may contain
surfaces at different tiers. Evidence satisfying a higher tier for one surface
does not upgrade other surfaces. A system-wide tier may be claimed only when
every surface within the explicitly stated scope satisfies that tier's
eligibility criteria.

### Tier 1 — Declarative governance

- **What it is.** The `.nyx` contract plus deterministic generated controls,
  static governance checks, and revision-bound human approval, evaluated at
  design time without executing the agentic workflow.
- **Evidence basis.** `contract_digest`; byte-stable generated artifacts;
  deterministic checker diagnostics with stable codes; verifiable effective
  approvals with replayable composition and tamper detection (ADR-0032);
  network-lock drift detection via `lock-check` (ADR-0035).
- **Claim eligibility (all required).** Valid contract; deterministic check
  pass; valid lock where a lock is required; **all applicable approval
  requirements satisfied and verified**; an exact bound subject revision.
- **Limitations.** Authorizes and validates *declarations only*. It proves
  nothing about runtime behavior: a contract can be correct and fully approved
  and still be violated at runtime if nothing enforces it. It is only as
  complete as what was declared. The approval hash is a consistency binding, not
  a signature.
- **Prohibited claims.** MUST NOT say Nornyx "prevents", "blocks at runtime", or
  "enforces" agent behavior; MUST NOT present a passing contract as evidence
  that agents behaved correctly. Tier 1 is a design-time assurance only.

### Tier 2 — Integrated cooperative enforcement over declared surfaces

- **What it is.** The reference adapters (ADR-0037) wrap declared surfaces
  (tasks, tools, handoffs) and evaluate the contract in the execution path;
  a denial blocks the wrapped call; runtime events are emitted and bound to the
  approved revision.
- **Evidence basis.** Adapter-level allow/deny scenarios with stable diagnostic
  codes (e.g. `AN_ADAPTER_APPROVAL_NON_HUMAN`,
  `AN_ADAPTER_CAPABILITY_DENIED`); runtime events whose schema *requires*
  `network_id` + `contract_digest` + `network_lock_digest` + `subject_revision`,
  cross-checked against validated state with deterministic diagnostics on
  mismatch; `lock-check` drift detection.
- **Claim eligibility (Tier 1 plus all of).** Supported adapter/SPI version;
  declared enforcement surfaces (a coverage inventory naming which surfaces are
  wrapped); deny-path validation (at least one allow control and one deny
  control succeed on a declared wrapped surface); required runtime events
  present; successful digest/revision binding. Applies **only to the wrapped
  surfaces named in the inventory**, not to the application as a whole.
- **Limitations.** Enforcement is **cooperative** — bypassing the adapter
  bypasses enforcement, and a total bypass **may leave no Nornyx-generated
  trace**. It covers **only declared, wrapped surfaces** and cannot prove that
  no undeclared surface exists. The adapter does not authenticate agents, manage
  secrets, or contact production systems, and the event producer is
  self-declared.
- **Prohibited claims.** MUST NOT claim tamper-proof, mandatory, or independent
  enforcement; MUST NOT claim complete coverage of all agent actions; MUST NOT
  imply a gateway or sandbox; MUST NOT claim a whole application is Tier 2
  because some surfaces are wrapped. Every Tier 2 claim must carry the qualifier
  "cooperative, declared surfaces only."

### Tier 3 — Independent runtime assurance (not supplied by Nornyx alone)

- **What it is.** An *external* enforcement/attestation system (gateway, IAM,
  policy engine, sandbox) performs enforcement and produces independently-owned
  evidence that binds back to the approved `.nyx` revision. Nornyx's role is to
  define the contract, accept `external_runtime`-producer evidence, and validate
  its binding — not to be the enforcer.
- **Current Nornyx-side affordances.** The schema permits
  `producer: external_runtime`, requires the contract-state binding fields
  (`network_id`, `contract_digest`, `network_lock_digest`, `subject_revision`),
  and permits `signature_ref`. These affordances allow externally produced
  evidence to be represented, schema-validated, and checked against declared
  contract state and applicable event semantics; they do **not** establish
  independent assurance.
- **Required external evidence basis.** Authenticated producer identity;
  cryptographically verified attestation; protected evidence capture;
  deployment-policy binding; independently controlled logging; and demonstrated
  coverage of the claimed surfaces.
- **Claim eligibility.** Tier 1 for the same contract, revision, and claimed
  surfaces, plus the full **required external evidence basis** above. Where a
  Nornyx cooperative adapter is part of the claimed architecture, the applicable
  Tier 2 eligibility criteria must also be satisfied. An independently enforced
  surface may qualify without a Nornyx adapter only when the external system
  establishes enforcement, contract binding, protected evidence capture, and
  coverage for that surface.
- **Limitations (today).** Nornyx does **not** authenticate the producer, verify
  `signature_ref`, semantically verify that `input_digest` / `output_digest`
  corresponds to the actual runtime payload, establish a protected capture path,
  prove evidence completeness, observe the runtime, or prove the producer is
  independent of the decision-maker. Tier 3 is therefore a **declared boundary
  and set of integration affordances, not a delivered assurance**; reaching it
  requires external systems plus future work (signed evidence, compile
  attestation).
- **Prohibited claims.** `producer.type: external_runtime` and the presence of
  `signature_ref` MUST NEVER, on their own, qualify evidence as Tier 3 — they
  are producer-supplied metadata that Nornyx checks structurally and against
  declared contract state, not proof that the producer's account of runtime
  reality is true. MUST NOT claim Nornyx *provides* independent runtime
  assurance; MUST NOT present `external_runtime` evidence as verified, signed, or
  independence-proven; MUST NOT claim attestation of deployment. Any Tier 3 claim
  must name the external system that actually enforces and must establish that
  system's independence out-of-band.

### What Nornyx alone can establish

Current Nornyx can establish **Tier 1** for qualifying evidence packages and
demonstrates mechanisms that **contribute to Tier 2**. **Nornyx 1.7.0 does not
yet qualify as a supported Tier 2 integration** because ADR-0039's stable SPI
and distributable adapter package are not implemented, and no standardized
coverage inventory is emitted or verified. Nornyx **cannot award Tier 3** —
that requires an external enforcement/attestation system that Nornyx neither
provides nor verifies.

### Claim-eligibility summary

| Tier | Minimum claim eligibility (scoped to the stated surfaces) |
| --- | --- |
| **Tier 1** | Valid contract; deterministic check pass; valid lock where required; all applicable approval requirements satisfied and verified; exact subject revision |
| **Tier 2** | Tier 1 + supported adapter/SPI version; declared enforcement surfaces (coverage inventory); deny-path validation (≥1 allow + ≥1 deny on a wrapped surface); required events present; successful digest/revision binding |
| **Tier 3** | Tier 1 + full required external evidence basis for the claimed surfaces (authenticated producer identity; verified attestation; protected capture; deployment-policy binding; independent logging; demonstrated coverage). Where a Nornyx cooperative adapter participates, applicable Tier 2 criteria also apply. None of the independent evidence basis is provided or verified by Nornyx alone |

### Labeling rule

Reports and generated artifacts that make an assurance statement should carry an
explicit tier label **and its declared surface scope**. Introducing the
machine-readable label surface (e.g. an `assurance_tier` field or a report
section) is a **follow-on implementation milestone**, not part of this ADR. This
ADR fixes the vocabulary, the per-tier claim boundaries, the eligibility
criteria, and the scoping rule so that later work has a fixed reference.

## Consequences

- **Positive.** Every current and future capability gets an explicit assurance
  boundary scoped to its surfaces; overclaiming (including coverage inflation)
  becomes a reviewable eligibility violation rather than a matter of tone; the
  Tier 2→3 gap makes the value of external enforcement and signed evidence
  legible on the roadmap.
- **Cost.** Existing docs/reports must be audited for tier consistency, and new
  features must declare a tier, its scope, and meet its eligibility. Accepted —
  cheaper than retracting an overclaim.
- **Non-goals.** This ADR does not add enforcement, does not change the schema,
  and does not itself emit tier labels; it defines the model those follow-ons
  must honor.

## Alternatives considered

- **Two tiers (declarative vs. enforced).** Rejected: it collapses cooperative
  adapter enforcement and genuinely-independent assurance into one bucket, which
  is precisely the conflation this ADR exists to prevent.
- **Keeping the word "guarantee".** Rejected: "guarantee tier" can itself be
  read as a product guarantee, reintroducing the ambiguity the ADR removes.
- **Application-level (not surface-scoped) tiers.** Rejected: it invites
  coverage inflation, letting one wrapped surface imply a whole-system claim.
- **Making Tier 3 strictly cumulative on the Tier 2 adapter path.** Rejected: an
  independently enforced surface (gateway, workload identity, Cedar/OPA decision
  point, infrastructure routing) can establish stronger, independent coverage
  without the cooperative adapter; forcing a Nornyx adapter would mandate
  redundant enforcement and conflict with Nornyx's vendor-neutral control-plane
  positioning.
- **Marketing-only wording guidance, no ADR.** Rejected: wording drifts; a
  labeled model tied to evidence basis and eligibility is enforceable in review.

## Execution checklist (follow-on milestone, not this ADR)

1. Audit `docs/agentic-network/*` and generated reports; annotate each assurance
   statement with its tier and surface scope; fix any statement that exceeds its
   tier, scope, or eligibility.
2. Design the machine-readable label surface (report field / section) in a
   separate ADR or implementation goal.
3. Revisit Tier 3 limitations when signed evidence and compile attestation land
   — those move specific claims from "prohibited" to "permitted with named
   external system."
