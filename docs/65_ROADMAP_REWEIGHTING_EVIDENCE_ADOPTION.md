# Roadmap Reweighting — Evidence, Attestation, and Adoption

## Purpose

This note is the normalized strategy record for the post-v1.0 roadmap
reweighting. It states what Nornyx protects, what waits for adoption evidence,
and how items graduate. It is Nornyx-only planning surface; it does not change
package versions, releases, runtime behavior, the public API, or schemas.

## Strategic Thesis

Nornyx's durable value is where it provides independent, deterministic,
evidence-bound governance for agentic systems. As agent autonomy grows, the
questions that matter — what was this agent allowed to do, what did it do, can
that be shown afterward, and did the same approved governance meaning survive
across different enforcement products — are answered by an external, neutral,
deterministic contract/evidence/conformance layer, not by more capable models or
another proprietary runtime.

The roadmap therefore prioritizes the proof layer, semantic portability,
revision-aware change reasoning, and external adoption before ecosystem tooling
or runtime ownership.

Nornyx remains an independent, vendor-neutral governance contract language for
AI software delivery — defining deterministic controls and authorization
semantics, binding decisions and supplied evidence to governed revisions, and
preserving that governance meaning across supported integrations: a contract,
evidence, and semantic-conformance layer that integrates with external
governance platforms, policy engines, agent frameworks, CI/CD systems, gateways,
and execution runtimes without becoming those systems. Nornyx validates declared
contracts and supplied evidence — it does not attest unverifiable runtime truth.

## Durable Core (P0 — must continue)

- evidence integrity and attestation;
- deterministic locks and drift detection;
- contract revision binding;
- approval integrity (AI identities can never approve);
- runtime-event validation;
- canonical authorization semantics and stable decision/reason-code boundaries;
- conformance schemas and reports;
- honest assurance-tier boundaries;
- exact package/provenance examples;
- stable identifiers and revision-lineage primitives needed for deterministic
  comparison and external evidence correlation.

## Adoption and Interoperability Layer (P1-P2)

- standards mapping and enterprise assurance
  ([`docs/64_STANDARDS_MAPPING_AND_ENTERPRISE_ASSURANCE.md`](64_STANDARDS_MAPPING_AND_ENTERPRISE_ASSURANCE.md));
- standards-based authorization interoperability, with OpenID AuthZEN as the
  first implemented public boundary (`docs/69_AUTHZEN_INTEROPERABILITY.md`);
- semantic-equivalence conformance proving that supported mappings preserve the
  same Nornyx decision meaning from the same governed revision;
- deterministic before/after decision or semantic comparison where a generic
  Core consumer use case is demonstrated;
- feasibility and gap analysis for external policy/decision surfaces such as
  OPA/Rego, Cedar, and agent-era decision specifications, without making any of
  them a Core runtime dependency by default;
- external pilot consumption and the 5-minute adoption path;
- conformance showcase examples and published-distribution proof;
- migration path from scattered AGENTS.md/policies/evals to `.nyx`;
- reviewer quickstarts and external validation materials;
- authoring helpers: LLM authoring pack, formatted approval preview,
  checker-driven repair loop, CLI wizard, handover model;
- focused domain profiles only when contract-only and tied to a concrete pilot
  or user demand.

## Hyperscaler Neutrality Rule

Nornyx should integrate across hyperscaler and platform enforcement stacks, not
compete inside them.

Public Core may define generic mappings, projections, codecs, schemas,
conformance fixtures, revision-comparison primitives, and examples for external
policy engines, gateways, runtimes, and standards. It should not grow into an
agent gateway, traffic proxy, identity issuer, sandbox, agent registry, SIEM,
model guardrail, or hosted hyperscaler-specific control plane.

A platform-specific projection is always derived from the reviewed Nornyx
contract and remains subordinate to that source. The strategic product question
is not "can Nornyx implement the same runtime feature?" but "can Nornyx preserve,
prove, compare, and explain one governance meaning across revisions and
heterogeneous runtime/enforcement products?"

## Revision Comparison Scope

Public Nornyx may eventually expose generic primitives such as:

- deterministic comparison between two governed revisions;
- canonical decision-regression fixtures;
- stable lineage identifiers showing which revision/evidence object is being
  compared;
- generic semantic-delta reporting;
- evidence-correlation fields that let an external record identify the governed
  revision it relates to.

Those capabilities remain portable language/conformance primitives only. They do
not imply hosted operational services, environment discovery, provider-specific
orchestration, or runtime enforcement.

## Deferred / Adoption-Gated Work (P3)

- full LSP and Tree-sitter grammar;
- package/profile registry;
- extension marketplace;
- additional framework adapters;
- broad connector integrations;
- platform-specific operational connectors beyond a demonstrated adoption need;
- richer editor tooling;
- generic revision/decision diff tooling beyond what real consumers require.

## Needs Review Work (defer; separate approval required)

- native execution;
- governed self-healing;
- live connector runtime;
- hosted generic authorization service in Public Core;
- traffic interception or gateway ownership;
- identity issuance or credential brokering;
- sandbox/runtime isolation;
- automatic approval;
- autonomous production actions;
- legal/contract execution claims;
- anything that would turn Nornyx into a runtime, gateway, IAM, or hyperscaler
  infrastructure competitor.

## Promotion Gates

- **P3 → active:** repeated user requests; at least one external pilot blocked
  by the missing capability; stable schema/formatter/checker; an identified
  owner and maintenance plan.
- **needs_review → active:** a new ADR; a threat model; bounded execution
  proof; approval/evidence design; failure-mode tests; human approval.
- **new external projection → supported:** normative upstream reference; explicit
  semantic gap analysis; deterministic round-trip or decision-equivalence tests;
  exact source-revision binding where applicable; documented unsupported
  semantics; no runtime-enforcement overclaim.
- **new change-comparison primitive → supported:** demonstrated generic user need;
  deterministic inputs/outputs; exact revision binding; stable semantic meaning;
  no provider-specific runtime dependency required.
- All promotions follow the existing goal-packet model: scoped goal, tests,
  evidence, human approval.

## Non-Goals

Nornyx does not become: a full autonomous runtime, a
LangGraph/CrewAI/LangChain replacement, a general-purpose programming
language, a production execution engine, an unrestricted connector runtime, an
agent gateway, an agent registry, an IAM/identity platform, a sandbox, a
hyperscaler observability backend, a certification authority, a compliance
guarantee, a marketplace, or a framework-adapter treadmill.

## Relationship to Existing Roadmap Files

- [`docs/03_ROADMAP_TO_v1_AND_BEYOND.md`](03_ROADMAP_TO_v1_AND_BEYOND.md) —
  the strategic roadmap; carries the priority model, the reframed future
  proposals, and the M3-M9 milestone sequence.
- [`docs/69_AUTHZEN_INTEROPERABILITY.md`](69_AUTHZEN_INTEROPERABILITY.md) and
  [`docs/decisions/ADR-0044-authzen-interoperability.md`](decisions/ADR-0044-authzen-interoperability.md)
  — the first implemented standards-based authorization mapping and the pattern
  future projection/conformance work must preserve.
- [`examples/nornyx_roadmap_goals.nyx`](../examples/nornyx_roadmap_goals.nyx)
  — machine-readable mirror: `post_v1.0` strategic entries and GOAL-M3
  through GOAL-M9.
- [`docs/backlog/nornyx-authoring-assistant-roadmap.yaml`](backlog/nornyx-authoring-assistant-roadmap.yaml)
  and [`docs/38_NORNYX_AUTHORING_ASSISTANT_ROADMAP.md`](38_NORNYX_AUTHORING_ASSISTANT_ROADMAP.md)
  — authoring capabilities carry `strategic_priority` classifications.
- [`docs/backlog/nornyx-product-to-ops-lifecycle.yaml`](backlog/nornyx-product-to-ops-lifecycle.yaml),
  [`docs/backlog/nornyx-product-to-ops-lifecycle-backlog.md`](backlog/nornyx-product-to-ops-lifecycle-backlog.md),
  and [`docs/33_PRODUCT_TO_OPERATIONS_LIFECYCLE_ROADMAP.md`](33_PRODUCT_TO_OPERATIONS_LIFECYCLE_ROADMAP.md)
  — handover leads; lifecycle stays out of core.
- [`docs/tooling/26_TOOLING_ROADMAP_LSP_TREESITTER.md`](tooling/26_TOOLING_ROADMAP_LSP_TREESITTER.md)
  — LSP/Tree-sitter/registry/marketplace reframed as adoption-gated P3.
- [`docs/backlog/nornyx-standards-mapping-roadmap.yaml`](backlog/nornyx-standards-mapping-roadmap.yaml)
  — the P1 standards-mapping backlog, tracked by
  [mazinmarji/nornyx#47](https://github.com/mazinmarji/nornyx/issues/47).
- [`docs/RFCs/RFC-0003-full-language-evolution-research.md`](RFCs/RFC-0003-full-language-evolution-research.md),
  [`docs/decisions/ADR-0039-agentic-integration-sdk.md`](decisions/ADR-0039-agentic-integration-sdk.md),
  [`docs/decisions/ADR-0040-governance-assurance-tiers.md`](decisions/ADR-0040-governance-assurance-tiers.md),
  [`docs/decisions/ADR-0043-runtime-adapter-conformance.md`](decisions/ADR-0043-runtime-adapter-conformance.md),
  and [`docs/decisions/ADR-0044-authzen-interoperability.md`](decisions/ADR-0044-authzen-interoperability.md)
  — historical/decision records that constrain future work. This note supplies
  the forward-looking strategic context: future proposals stay gated, adapter
  expansion stays thin and user-driven, semantic portability, revision-aware
  comparison, and conformance evidence stay central, and Tier 2/Tier 3 claim
  boundaries stay strict.
