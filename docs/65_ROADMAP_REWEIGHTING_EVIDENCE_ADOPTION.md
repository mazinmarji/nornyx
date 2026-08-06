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
that be shown afterward — are answered by an external, neutral, deterministic
contract/evidence layer, not by more capable models. The roadmap therefore
prioritizes the proof layer and external adoption before ecosystem tooling or
runtime ownership.

Nornyx remains an independent, neutral, deterministic agentic
contract/control-plane language for governed AI software delivery: a contract
and evidence layer that integrates with external governance platforms, agent
frameworks, CI/CD systems, and execution runtimes without becoming those
systems. Nornyx validates declared contracts and supplied evidence — it does
not attest unverifiable runtime truth.

## Durable Core (P0 — must continue)

- evidence integrity and attestation;
- deterministic locks and drift detection;
- contract revision binding;
- approval integrity (AI identities can never approve);
- runtime-event validation;
- conformance schemas and reports;
- honest assurance-tier boundaries;
- exact package/provenance examples.

## Adoption Layer (P1-P2)

- standards mapping and enterprise assurance
  ([`docs/64_STANDARDS_MAPPING_AND_ENTERPRISE_ASSURANCE.md`](64_STANDARDS_MAPPING_AND_ENTERPRISE_ASSURANCE.md));
- external pilot consumption and the 5-minute adoption path;
- conformance showcase examples and published-distribution proof;
- migration path from scattered AGENTS.md/policies/evals to `.nyx`;
- reviewer quickstarts and external validation materials;
- authoring helpers: LLM authoring pack, formatted approval preview,
  checker-driven repair loop, CLI wizard, handover model;
- focused domain profiles only when contract-only and tied to a concrete pilot
  or user demand.

## Deferred / Adoption-Gated Work (P3)

- full LSP and Tree-sitter grammar;
- package/profile registry;
- extension marketplace;
- additional framework adapters;
- broad connector integrations;
- richer editor tooling.

## Needs Review Work (defer; separate approval required)

- native execution;
- governed self-healing;
- live connector runtime;
- automatic approval;
- autonomous production actions;
- legal/contract execution claims;
- anything that would turn Nornyx into a runtime competitor.

## Promotion Gates

- **P3 → active:** repeated user requests; at least one external pilot blocked
  by the missing capability; stable schema/formatter/checker; an identified
  owner and maintenance plan.
- **needs_review → active:** a new ADR; a threat model; bounded execution
  proof; approval/evidence design; failure-mode tests; human approval.
- All promotions follow the existing goal-packet model: scoped goal, tests,
  evidence, human approval.

## Non-Goals

Nornyx does not become: a full autonomous runtime, a
LangGraph/CrewAI/LangChain replacement, a general-purpose programming
language, a production execution engine, an unrestricted connector runtime, a
certification authority, a compliance guarantee, a marketplace, or a
framework-adapter treadmill.

## Relationship to Existing Roadmap Files

- [`docs/03_ROADMAP_TO_v1_AND_BEYOND.md`](03_ROADMAP_TO_v1_AND_BEYOND.md) —
  the strategic roadmap; carries the priority model, the reframed future
  proposals, and the M3-M9 milestone sequence.
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
  [`docs/decisions/ADR-0043-runtime-adapter-conformance.md`](decisions/ADR-0043-runtime-adapter-conformance.md)
  — historical records; unchanged. This note supplies the forward-looking
  strategic context: future proposals stay gated, adapter expansion stays thin
  and user-driven, conformance evidence stays central, and Tier 2/Tier 3 claim
  boundaries stay strict.
