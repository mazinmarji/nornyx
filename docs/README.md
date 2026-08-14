# Nornyx Documentation Map

This page is the navigation and authority guide for the Nornyx documentation.
It identifies which documents are the current source of truth, which are
supporting material, and which are historical records preserved as evidence.

Nornyx is a vendor-neutral governance contract language for AI software
delivery that defines deterministic controls and authorization semantics,
binds decisions and supplied evidence to governed revisions, and preserves
that governance meaning across supported integrations. For that definition in
context, start with the [executive overview](00_EXECUTIVE_OVERVIEW.md) and the
[positioning document](48_NORNYX_POSITIONING.md).

## How to read authority levels

- **Authoritative** — the current source of truth for its topic. If another
  document disagrees, the authoritative document wins.
- **Supporting** — current material that elaborates an authoritative source
  without redefining it.
- **Historical record** — preserved planning, decision, program, or QA
  evidence. Historical records remain valuable evidence of how Nornyx got
  here, but they are **not** current product definitions, and their internal
  status lines reflect the time they were written.
- **Edition-pinned** — accurate as of a stated revision or edition rather than
  evergreen.

Public paths are stable by default: documents are corrected or annotated in
place. When a hygiene cycle does move or retire a document, this index and
the changelog record the change.

## 1. Start / Adopt

- [../README.md](../README.md) — the homepage: install, five-minute start,
  first contract. **Authoritative** entry point.
- [49_NORNYX_5_MINUTE_ADOPTION.md](49_NORNYX_5_MINUTE_ADOPTION.md) —
  checkout-based evaluation path.
- [USE_IN_YOUR_REPO.md](USE_IN_YOUR_REPO.md) — adopt Nornyx in your own
  repository, including drift gates.
- [67_M5_A2B_MIGRATION_GUIDE_AGENTS_POLICIES_EVALS.md](67_M5_A2B_MIGRATION_GUIDE_AGENTS_POLICIES_EVALS.md)
  — migrate scattered `AGENTS.md`, policies, and evals into a `.nyx` contract.
- [../CONTRIBUTING.md](../CONTRIBUTING.md) — contribution rules and
  development commands.

## 2. Product / Boundaries

- [00_EXECUTIVE_OVERVIEW.md](00_EXECUTIVE_OVERVIEW.md) — what Nornyx is, the
  problem it solves, and its responsibility boundary. **Authoritative.**
- [48_NORNYX_POSITIONING.md](48_NORNYX_POSITIONING.md) — the canonical
  detailed positioning: what Nornyx is, what it is not, best use cases,
  interoperability position. **Authoritative.**
- [02_ARCHITECTURE.md](02_ARCHITECTURE.md) — current architecture.
  **Authoritative.**
- [public-boundary-policy.md](public-boundary-policy.md) — what belongs in
  this public repository. **Authoritative.**
- [05_SECURITY_MODEL.md](05_SECURITY_MODEL.md) — security assumptions and
  boundaries. Supporting.
- [../SECURITY.md](../SECURITY.md) — the repository security policy.
  **Warning:** its current vulnerability-reporting instructions are stale, and
  GitHub Private Vulnerability Reporting is currently disabled for this
  repository. Do **not** post sensitive vulnerability details in public
  issues. The security policy will be corrected once a private reporting
  channel is enabled.
- [28_NORNYX_PRODUCT_THESIS_SHORT.md](28_NORNYX_PRODUCT_THESIS_SHORT.md) —
  earlier short product thesis. Historical record; the positioning document
  above is current.

## 3. Language / CLI / Reference

- [VERSIONING.md](VERSIONING.md) — the independent version axes (package
  distribution vs. language/schema). **Authoritative.**
- [GOVERNANCE_CLI_AND_API.md](GOVERNANCE_CLI_AND_API.md) — governance CLI and
  public API surface and its stability boundary. **Authoritative.**
- [52_SCHEMA_TARGETS_AND_EXAMPLES.md](52_SCHEMA_TARGETS_AND_EXAMPLES.md) —
  schema targets and examples. Supporting.
- [../schemas](../schemas) — machine-readable schemas; inspect the current
  surface with `nornyx schema --version 1.0`.
- [01_LANGUAGE_SPEC_v0_1.md](01_LANGUAGE_SPEC_v0_1.md) — the v0.1 language
  specification. Historical record: the current language/schema version is
  1.0 (see [VERSIONING.md](VERSIONING.md) and the schemas above).

## 4. Authorization & Agentic Governance

- [agentic-network/00_OVERVIEW.md](agentic-network/00_OVERVIEW.md) — entry
  point for the optional `agentic_network` profile. **Authoritative.**
- [agentic-network/01_TUTORIAL.md](agentic-network/01_TUTORIAL.md) —
  end-to-end tutorial.
- [agentic-network/12_AUTHORIZATION_SPI.md](agentic-network/12_AUTHORIZATION_SPI.md)
  — the SPI 1.2 note: the additive Authorizer construction-state capability
  (it changes no authorization or approval semantics). For the complete
  decision semantics, consult the current implementation, its tests, and
  [decisions/ADR-0039-agentic-integration-sdk.md](decisions/ADR-0039-agentic-integration-sdk.md).
- [agentic-network/08_SECURITY_BOUNDARIES.md](agentic-network/08_SECURITY_BOUNDARIES.md)
  — what the profile does and does not protect against.
- [agentic-network/02_CREWAI_GUIDE.md](agentic-network/02_CREWAI_GUIDE.md) ·
  [agentic-network/03_LANGGRAPH_GUIDE.md](agentic-network/03_LANGGRAPH_GUIDE.md)
  — the narrow published runtime-adapter coverage (limited/experimental).
- [agentic-network/05_PROTOCOL_DECLARATIONS.md](agentic-network/05_PROTOCOL_DECLARATIONS.md)
  — MCP/A2A protocol declarations (declarations only; Nornyx runs no
  connector).

## 5. Evidence & Revision Binding

- [agentic-network/06_RUNTIME_EVIDENCE.md](agentic-network/06_RUNTIME_EVIDENCE.md)
  — runtime-event evidence (1.1) and how supplied events are validated.
  **Authoritative.**
- [agentic-network/07_NETWORK_LOCK.md](agentic-network/07_NETWORK_LOCK.md) —
  content-addressed locks binding artifacts and evidence to an exact governed
  revision. **Authoritative.**
- [agentic-network/04_EXTERNAL_EVAL_EVIDENCE.md](agentic-network/04_EXTERNAL_EVAL_EVIDENCE.md)
  — importing external evaluation evidence.
- [11_OBSERVABILITY_EVIDENCE.md](11_OBSERVABILITY_EVIDENCE.md) — earlier
  observability/evidence framing. Historical record; the agentic-network
  evidence documents above are current.

The claim boundary throughout: Nornyx validates governed contracts and
supplied evidence against declared semantics and governed revisions. It does
not independently attest that supplied runtime events actually occurred;
external systems remain responsible for execution and enforcement.

## 6. Governed Packages

- [governed-package-profile.md](governed-package-profile.md) — governed
  packages: scan, inventory, hash, risk-surface, and evidence-bind untrusted
  package inputs. **Authoritative.**
- [../examples/governed_package](../examples/governed_package) — worked
  governed-package example.

## 7. Interoperability & Conformance

- [69_AUTHZEN_INTEROPERABILITY.md](69_AUTHZEN_INTEROPERABILITY.md) — the
  scoped OpenID AuthZEN capability-evaluation interoperability surface.
  Limited/experimental: it is not complete AuthZEN coverage and claims no
  AARP/COAZ conformance.
- [68_STANDARDS_MAPPING_FIRST_WAVE.md](68_STANDARDS_MAPPING_FIRST_WAVE.md) —
  first-wave, theme-level standards mappings. Limited/experimental.
- [64_STANDARDS_MAPPING_AND_ENTERPRISE_ASSURANCE.md](64_STANDARDS_MAPPING_AND_ENTERPRISE_ASSURANCE.md)
  — the standards-mapping and assurance planning surface. Supporting/planning;
  standards compliance is not established by mappings.
- [agentic-network/11_REFERENCE_CI.md](agentic-network/11_REFERENCE_CI.md) —
  reference CI wiring and the adapter-conformance gate.
- [decisions/ADR-0040-governance-assurance-tiers.md](decisions/ADR-0040-governance-assurance-tiers.md)
  — the assurance-tier decision. Assurance claims stay subordinate to these
  interoperability/conformance boundaries: cooperative higher-assurance claims
  are limited, and Tier-3 assurance is not provided.
- [32_NORNYX_EVERGREEN_ASSURANCE.md](32_NORNYX_EVERGREEN_ASSURANCE.md) —
  earlier assurance model. Historical record.

## 8. Examples / Adoption Evidence

- [../examples](../examples) — the contract and example corpus.
- [../examples/crewai_governance_benchmark/README.md](../examples/crewai_governance_benchmark/README.md)
  — governance A/B benchmark
  ([reviewer quickstart](../examples/crewai_governance_benchmark/REVIEWER_QUICKSTART.md)).
- [../examples/external_adoption_pilot/README.md](../examples/external_adoption_pilot/README.md)
  — the first-party external-adoption pilot (limited/experimental: first-party,
  not independent adoption).
- [../examples/agentic_network_support](../examples/agentic_network_support) —
  agentic-network demo used by the tutorial.
- [50_NORNYX_GRAPH_DEMO.md](50_NORNYX_GRAPH_DEMO.md) ·
  [63_NORNYX_GRAPH_DEMO_EXPANDED.md](63_NORNYX_GRAPH_DEMO_EXPANDED.md) —
  static Nornyx Graph demos.
- [66_M5_A2_EXTERNAL_ADOPTION_SOLICITATION.md](66_M5_A2_EXTERNAL_ADOPTION_SOLICITATION.md)
  — reviewer-facing adoption pack.
- [CASE_STUDY_multi_repo_governance.md](CASE_STUDY_multi_repo_governance.md) —
  multi-repo governance case study.

## 9. Roadmap / Decisions / Releases

- [65_ROADMAP_REWEIGHTING_EVIDENCE_ADOPTION.md](65_ROADMAP_REWEIGHTING_EVIDENCE_ADOPTION.md)
  — current roadmap priorities (P0–P3) and promotion gates. **Authoritative.**
  The roadmap includes both durable shipped capabilities and
  future/adoption-gated work; roadmap inclusion alone does not indicate
  current availability.
- [03_ROADMAP_TO_v1_AND_BEYOND.md](03_ROADMAP_TO_v1_AND_BEYOND.md) — the
  strategic roadmap carrying the M3–M9 milestone sequence.

### Decision records (ADRs and RFCs)

- [decisions](decisions) — the single ADR home: the early ADR-0001 and
  ADR-0021 records (relocated from the former `docs/ADRs/` directory) plus
  ADR-0010 through ADR-0044.

One historical numbering collision persists inside the home: both
`decisions/ADR-0021-zero-friction-adoption-ramp.md` (early series) and
`decisions/ADR-0021-change-governance-as-a-module.md` exist. **Cite an
ambiguous ADR by its full filename and title, never by number alone.** ADRs
are historical decision records: a status recorded as `Proposed` stays as
written and is not silently promoted because later work overlaps it.

- [RFCs](RFCs) — RFC-0001 and RFC-0002 are historical records;
  [RFCs/RFC-0003-full-language-evolution-research.md](RFCs/RFC-0003-full-language-evolution-research.md)
  is a research-only track, not a committed direction.

### Releases

- [../CHANGELOG.md](../CHANGELOG.md) — the change record for every release.
  **Authoritative.** (Per-version root release-note files were consolidated
  into it; historical per-version notes also remain on the corresponding
  GitHub releases.)
- [../RELEASING.md](../RELEASING.md) — release procedure (maintainer).
- [releases](releases) — the v1.0 release records and the governance-program
  candidate record. Historical.

## 10. Textbook

- [../book/manuscript](../book/manuscript) — the development-edition Nornyx
  textbook manuscript. Public educational material: its factual assertions may
  be edition- or SHA-pinned rather than evergreen, so where the textbook and
  the current authoritative documents disagree, the authoritative documents
  win.
- [../book/factpack](../book/factpack) — the revision-pinned fact packs the
  manuscript's claims are checked against. Edition-pinned.
- [../book/design](../book/design) · [../book/tools](../book/tools) —
  editorial apparatus (maintainer material).

## 11. Maintainer / Historical Records

These are project records, not user documentation. They are preserved as
evidence; their internal status lines are historical.

- [../AGENTS.md](../AGENTS.md) — repository agent instructions (maintainer,
  current).
- [planning/governance-extension/CODEX_GOAL.md](planning/governance-extension/CODEX_GOAL.md)
  — the completed governance-program execution record, filed with the
  program's other records. Closed historical program, not a current
  instruction.
- [goals](goals) — goal packets for the development program. Historical
  records.
- [planning](planning) — planning surfaces (agentic-network,
  governance-extension). Historical/maintainer records.
- [qa](qa) — QA evidence trees. Historical evidence.
- [pmo](pmo) · [metrics](metrics) · [backlog](backlog) ·
  [templates](templates) · [tooling](tooling) · [agent](agent) — program
  management, metrics, backlog, template, tooling, and agent-workflow records
  (maintainer/historical; the tooling roadmap is adoption-gated).
- [../REPLACEMENT_BASELINE_README.md](../REPLACEMENT_BASELINE_README.md) —
  historical baseline record.
- [12_COMPILER_MVP_PLAN.md](12_COMPILER_MVP_PLAN.md),
  [16_FINAL_LANGUAGE_TARGET.md](16_FINAL_LANGUAGE_TARGET.md), and the other
  numbered planning/execution notes not listed above — historical program
  records from earlier development stages.
