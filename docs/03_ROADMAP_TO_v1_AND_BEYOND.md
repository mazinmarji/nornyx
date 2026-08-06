# Nornyx Roadmap to v1.0 and Beyond

## Strategic version model

This roadmap treats completed v0.1 scaffold work as the safe local foundation
for a broader agentic contract language. Earlier semantic-checker, harness,
policy, eval, and connector ideas remain valid sub-workstreams, but they are
organized under this strategic version model:

- v0.1: Safe AI-coding / agentic repo control-plane scaffold.
- v0.1.1: Cleanup and contract hardening, including mapping block validation,
  stale metadata cleanup, roadmap alignment, and PMO wording cleanup.
- v0.2: Nornyx Graph + stronger generic contract model.
- v0.3: Domain profiles.
- v0.4: Adapters for Governed Delivery Control Plane, Agentic Development Harness, GovernanceAdapter, telecom ops,
  and business ops.
- v0.5-v0.9: Reserved maturity bands for graph validation, profile conformance,
  adapter conformance, bounded execution readiness, and release-candidate
  stabilization.
- v1.0: Stable generalized agentic contract language.

v1.0 does not mean a full autonomous runtime, a replacement for LangGraph,
CrewAI, LangChain, a general-purpose programming language, a production
execution engine, or unrestricted connector runtime. It means Nornyx is stable
enough to be used as a generalized agentic contract language across multiple
agentic AI domains.

## Strategic reweighting after v1.0 stabilization

The next roadmap phase is not "complete every future proposal." The next phase
is to protect and productize the durable governance/evidence core, then let
adoption determine which ecosystem features graduate.

Nornyx's durable value is where it provides independent, deterministic,
evidence-bound governance for agentic systems: evidence and attestation, locks
and drift detection, contract revision binding, approval integrity,
runtime-event validation, and conformance schemas and reports. Lower-
defensibility work — additional framework adapters, a full LSP, a registry, a
marketplace, native execution, self-healing, a live connector runtime — is
gated behind adoption evidence and explicit ADR approval rather than treated as
a default obligation.

Roadmap items are weighted by the following priority model. Existing roadmap,
backlog, and tooling documents are reconciled against it; the normalized
strategy note lives in
[`docs/65_ROADMAP_REWEIGHTING_EVIDENCE_ADOPTION.md`](65_ROADMAP_REWEIGHTING_EVIDENCE_ADOPTION.md).

### Priority model

- **P0 — Durable core (must continue):** evidence integrity, attestation,
  deterministic locks, drift detection, contract revision binding, approval
  integrity, runtime-event validation, conformance schemas/reports, honest
  assurance-tier boundaries, exact package/provenance examples.
- **P1 — Adoption and enterprise assurance:** standards mapping, external pilot
  consumption, the 5-minute adoption path, conformance showcase examples,
  published-distribution proof, a migration path from scattered
  AGENTS.md/policies/evals to `.nyx`, reviewer quickstarts.
- **P2 — Adoption helpers and focused profiles:** authoring assistant CLI, LLM
  authoring pack, formatted approval preview, checker-driven repair loop,
  handover model; telecom/PMO/business profiles only if contract-only and tied
  to a concrete pilot or user demand.
- **P3 — Adoption-gated ecosystem work:** full LSP, Tree-sitter grammar,
  package/profile registry, extension marketplace, additional framework
  adapters, broad connector integrations, richer editor tooling.
- **needs_review / defer:** native execution, governed self-healing, live
  connector runtime, automatic approval, autonomous production actions,
  legal/contract execution claims — anything that would turn Nornyx into a
  runtime competitor.

Reweighting reclassifies; it does not erase. Existing roadmap history stays in
place and lower-priority items are marked P3, candidate,
future_proposal, needs_review, historical_only, or superseded as appropriate.

## Phase 0 — Concept freeze

Deliverables:

- name and product category;
- v0.1 language model;
- safety boundaries;
- MVP CLI;
- examples and tutorial.

## Phase 1 — v0.1 executable spec and generator

Deliverables:

- parser;
- checker;
- generator;
- context pack builder;
- evidence scaffold;
- tests;
- generated AGENTS.md/skills/policies/harness/evals.

## Phase 2 — v0.2 Nornyx Graph and stronger generic contract model

Add:

- declared node/edge model;
- generic contract blocks;
- typed schemas for blocks;
- context provenance and taint rules;
- instruction/data channel separation;
- approval-gate checking;
- budget checking;
- supply-chain manifest checking;
- better diagnostics for LLM repair.

Current local v0.2 surface: static `graph:` and `contracts:` validation for
declared nodes, edges, graph references, approval references, and budget
references. Known core graph node refs are checked when supplied. The
compatibility schema remains the default `schemas/nornyx_v0_1.schema.json`
route, and explicit schema targets now exist at
`schemas/nornyx_v0_2.schema.json` and `schemas/nornyx_v1_0.schema.json`.
This does not add graph runtime execution.

## Phase 3 — v0.3 domain profiles

Add:

- ai_coding;
- agentic_repo_harness;
- telecom_ops;
- business_ops;
- ai_governance;
- finance_ops if needed.

Current local v0.3 compatibility surface: optional authoritative v1 profile
packs in `nornyx/profiles_data/`, exact v0.3 projection, generated starter
documents for each domain profile, closed validation rules, and compatibility
tests. Profiles layer on the v0.2 static
graph/contract model and do not enable adapters, live connectors, model calls,
automatic approvals, self-modification, production deployment, or
general-purpose programming language features.

## Phase 4 — v0.4 adapters and ecosystem bridges

Add:

- Governed Delivery Control Plane adapter;
- Agentic Development Harness adapter;
- GovernanceAdapter adapter;
- telecom ops adapter;
- business ops adapter;
- MCP/A2A connector contract conformance;
- policy/eval/evidence integration tests.

Current local v0.4 surface: `adapters:` is a static extension block;
`schemas/adapter_contract.schema.json` defines contract-only adapter
metadata; `examples/nornyx_v04_adapter_contracts.nyx` covers governed delivery
control plane, agentic development harness, governance adapter, telecom ops, and business ops bridges; and tests
verify policy/eval/evidence bindings plus MCP/A2A connector conformance. This
does not enable live connector execution.

## Phase 5 — v0.5-v0.9 maturity bands

Reserved bands:

- v0.5 graph validation and semantic consistency hardening;
- v0.6 domain-profile conformance;
- v0.7 adapter conformance and connector-contract hardening;
- v0.8 bounded execution readiness;
- v0.9 release-candidate stabilization.

Current local v0.5 surface: static graph relation consistency checks, duplicate
and self-edge diagnostics, expanded graph reference targets, and contract
auditability warnings for approval, budget, and evidence graph coverage. This
does not add graph execution.

Current local v0.6 surface: profile conformance metadata, cross-profile
compatibility matrix, migration guidance, and v1 readiness decisions for the
v0.3 domain profile packs. This does not make profiles mandatory core concepts.

Current local v0.7 surface: static adapter conformance reports,
connector-contract conformance schemas, MCP/A2A conformance checks, and adapter
evidence reports. This does not enable live connector execution.

Current local v0.8 surface: static bounded execution readiness reports with
sandbox, capability, approval, trace, evidence, policy, and adapter-conformance
checks. This does not enable execution.

Current local v0.9 surface: release-candidate stabilization reports and
evidence checks for the maturity bands through v0.8. This does not claim v1.0
readiness, publish, tag, push, or unlock GOAL-042/GOAL-100.

Bounded execution readiness remains local, explicit, approval-gated, traced,
and evidence-backed. These bands do not enable broad autonomy, live connector
execution by default, automatic approvals, self-modification, or production
deployment.

## Phase 6 — v1.0 stable generalized agentic contract language

v1.0 acceptance criteria:

- stable graph model;
- stable contract schema;
- stable checker;
- stable profiles;
- stable adapters;
- policy/eval/evidence semantics;
- approval gates;
- artifact generation;
- safe interoperability rules.

Current local v1.0 surface: a stable-language report, schema, CLI/script check,
and evidence gate that confirm GOAL-033 through GOAL-042 are complete locally
while GOAL-100 remains locked. This stabilizes Nornyx as a generalized agentic
contract language across graph, contracts, profiles, adapters, bounded
readiness, and release-candidate evidence. It does not publish, tag, push,
change package versions, deploy, enable live connectors, call models, grant
automatic approvals, or promote regulated/enterprise extensions.

## Post-v1.0 strategic milestone sequence

After local v1.0 stabilization, the recommended strategic sequence weights the
durable core and adoption ahead of ecosystem expansion. Each milestone is
static, validation-first, and bounded by the existing safety model.

### M3 — Evidence and Attestation Productization

- Objective: make deterministic evidence, locks, drift detection, contract
  revision binding, runtime-event validation, conformance reports, and
  installed-artifact proof the visible product center.
- Deliverables: evidence/attestation overview doc, conformance report examples,
  pip-only distribution conformance showcase, exact-revision audit examples,
  claim-boundary wording, deterministic report format guidance.
- Non-goals: no new framework adapter by default, no runtime-truth overclaim,
  no Tier 3 claim.
- Promotion gate: deliverables validated locally with recorded evidence.

### M4 — Standards Mapping and Enterprise Assurance

- Objective: a versioned, machine-checkable standards-mapping layer that maps
  external framework requirements to Nornyx controls, evidence, approvals,
  evals, gaps, and assurance boundaries. See
  [`docs/64_STANDARDS_MAPPING_AND_ENTERPRISE_ASSURANCE.md`](64_STANDARDS_MAPPING_AND_ENTERPRISE_ASSURANCE.md).
- First wave: NIST AI RMF; OWASP Top 10 for LLM Applications / OWASP GenAI;
  ISO/IEC 42001 using identifiers and original summaries only; a gap report.
- Non-goals: no certification, no legal advice, no copyrighted standard text
  reproduction, no claim of compliance.
- Promotion gate: mappings cite framework version/source and name the Nornyx
  control/evidence/eval/approval/gap; deterministic local validation only.

### M5 — External Adoption and Pilot Validation

- Objective: prove external users can adopt Nornyx without maintainer
  hand-holding.
- Deliverables: 5-minute adoption path, external reviewer quickstart, one
  external repo pilot or reproducible pilot package, migration guide from
  scattered governance artifacts to `.nyx`, issue templates for external
  feedback, adoption success criteria.
- Non-goals: no large new features before adoption evidence, no speculative
  marketplace.
- Promotion gate: at least one external adoption signal recorded as evidence.
- **M5-A-1 — reproducible pilot package: complete.**
  `examples/external_adoption_pilot` installs the published
  `nornyx-agentic-adapters` with its CrewAI extra from PyPI into a clean
  environment and runs one action three ways — ungoverned, governed and
  authorized, governed and unauthorized — with a machine-readable adoption
  record and a seven-class failure taxonomy. Verified on every push by the
  `external-adoption-pilot` CI job through the standalone,
  outside-the-checkout path. This also closes ADR-0039's *External pilot
  consumption* checklist row, which is now recorded there as executed by
  M5-A-1 rather than tracked independently.
- **M5-A-2a — external solicitation pack: complete.**
  [`66_M5_A2_EXTERNAL_ADOPTION_SOLICITATION.md`](66_M5_A2_EXTERNAL_ADOPTION_SOLICITATION.md)
  adds the five-minute external path, the reviewer quickstart, falsifiable
  success criteria, and three issue templates
  (`external-adoption-result`, `external-adoption-failure`,
  `external-contract-pilot`). It creates the machinery for an external signal;
  it does not constitute one.
- **M5-A-3 — checkable migration example: complete.**
  `examples/agents_migration_example/` lands a bounded migration of a subset of
  the root `AGENTS.md`: a `.nyx` contract that passes `nornyx check`, paired
  with a machine-readable residual list of guidance that deliberately stays
  outside `.nyx`. Both halves are tested — the residual list structurally, so
  CI cannot validate only the mapped controls. It is an evidence example, not
  a feature expansion, and claims no full `AGENTS.md` conversion.
- **M5-A-4 — unknown policy-rule diagnostic: complete.** `nornyx check` now
  emits an `UNKNOWN_POLICY_RULE` warning for a `policies.deny` name outside the
  evaluated rule-name vocabulary, and `nornyx check --strict` fails on one.
  Default behaviour is unchanged and non-breaking; strict is opt-in, and
  strict-as-default is deferred to a future version-policy decision. The
  diagnostic is scoped to rule-name vocabulary and makes no claim about whether
  an in-vocabulary rule matches a given flow. Existing rule matching is
  untouched.
- **M5-A-2b — migration guide: complete.**
  [`67_M5_A2B_MIGRATION_GUIDE_AGENTS_POLICIES_EVALS.md`](67_M5_A2B_MIGRATION_GUIDE_AGENTS_POLICIES_EVALS.md)
  documents how to separate governed decisions from guidance, context,
  conventions, and external evidence. Framed by a read-only grounding pass
  whose decisive finding was that `policies.deny` accepts free-text rule names
  it never evaluates — so the guide leads with that silent-failure warning,
  keeps the authorization SPI and harness policy evaluation separate
  throughout, and requires a residual list. It does not claim `AGENTS.md` can
  be replaced.
- The promotion gate is unchanged and is **not** met by M5-A-1 or M5-A-2a.
  First-party CI can supply the reproducible thing an external adopter would
  run, and M5-A-2a can supply the machinery to report it, but neither can
  supply the signal itself. The gate stays closed until at least one external
  user reports a result from outside the maintainer flow. A gate this project
  could satisfy by itself would measure its diligence, not its adoption.

### M6 — Authoring and Human Approval UX

- Objective: make `.nyx` easier to draft and review while keeping the checker
  and human approval authoritative.
- Deliverables: LLM authoring pack, templates, checker-driven repair protocol,
  formatted approval preview, CLI wizard if diagnostics are stable enough.
- Non-goals: no automatic approval, no live LLM calls by default, no model
  hosting, no automatic repo writes.
- Promotion gate: the authoring-assistant promotion gates in
  `docs/backlog/nornyx-authoring-assistant-roadmap.yaml`.

### M7 — Standards-Based Ecosystem Interop

- Objective: prefer standard event formats, conformance boundaries, MCP/A2A
  contract conformance, OPA/Cedar-style policy export or mapping, and thin
  framework-neutral adapters over a bespoke adapter treadmill.
- Deliverables: interop boundary ADR, compile-to-standard feasibility notes,
  event-schema alignment, thin adapter guidelines.
- Non-goals: no broad connector runtime, no framework ownership, no
  whole-application coverage claim.
- Promotion gate: standards conformance demonstrated before any runtime-shaped
  interop work is considered.

### M8 — Adoption-Gated Tooling and Registry

- Objective: promote LSP, Tree-sitter, registry, package/profile ecosystem, and
  marketplace work only after adoption creates evidence of need.
- Promotion gates: repeated user requests; at least one external pilot blocked
  by missing tooling; stable schema/formatter/checker; a maintenance owner
  identified.

### M9 — Reviewed Future Runtime Research

- Objective: keep native execution, self-healing, and live connector runtime in
  research status unless separately approved.
- Promotion gates: new ADR, threat model, bounded execution proof,
  approval/evidence design, failure-mode tests, human approval.

## Future proposals outside the completed governance program

The following tracks are `future_proposal_outside_current_program`, not
unfinished governance roadmap obligations. They are adoption-gated, not default
commitments; each carries a strategic status and a graduation rule:

- dedicated parser and LSP — P3; only after user adoption creates editor
  friction;
- package/registry system — P3; only after reusable profile/package demand
  exists;
- MCP/A2A connector runtime — needs_review; prefer standards conformance and
  compile-to-standard before any runtime ownership;
- governed self-healing — needs_review; requires an explicit safety ADR plus
  approval/evidence gates;
- eval-driven improvement loops — candidate; only if bounded, evidence-backed,
  and human-approved;
- extension marketplace — P3/future; requires ecosystem adoption first;
- optional native execution for selected domains — needs_review/defer; risks
  changing the Nornyx identity;
- broader programming constructs — needs_review/defer; must not turn Nornyx
  into a general-purpose language.

GOAL-013 keeps these tracks in research status through
`docs/RFCs/RFC-0003-full-language-evolution-research.md`; promotion requires a
new scoped goal, ADR review, local validation, evidence, and human approval.
