# Standards Mapping and Enterprise Assurance

## Status

Strategic priority **P1** under the post-v1.0 reweighting in
[`docs/03_ROADMAP_TO_v1_AND_BEYOND.md`](03_ROADMAP_TO_v1_AND_BEYOND.md)
(milestone M4).

The first-wave mapping is complete and recorded by closed
[issue #47](https://github.com/mazinmarji/nornyx/issues/47). The current tracked
implementation unit is
[issue #81](https://github.com/mazinmarji/nornyx/issues/81), which owns the
machine-readable representation and deterministic validator for the already
published first-wave mapping.

Issue #81 is an **integrity-hygiene unit for existing first-wave material**. It
must not add a new framework, promote second- or future-wave content, create a
second assurance/coverage status ontology, or turn the mapping into a customer
GRC/control-tower product. The mapping records compose the existing Nornyx
claim types, control-surface labels, explicit MAP/NC relationships and the
assurance-tier/surface-scope boundary from ADR-0040. Structural diagnostics
such as stale, contradictory, invalid or overclaiming describe validator
findings; they are not compliance or assurance states.

Source/clause grounding formerly tracked by #82, and second-wave framework
expansion formerly tracked by #83, are **backlog-only**. They are not active
implementation issues. Their scope remains in
`docs/backlog/nornyx-standards-mapping-roadmap.yaml` and should be promoted to a
fresh scoped issue only when source access, a concrete use case, and an actual
implementation window exist.

Issue-governance rule for this workstream:

> Keep GitHub Issues for active or near-active executable work. Keep deferred
> roadmap candidates in the repository backlog until they are explicitly
> promoted.

Framework **expansion** remains sequenced after M5's adoption work
([`66_M5_A2_EXTERNAL_ADOPTION_SOLICITATION.md`](66_M5_A2_EXTERNAL_ADOPTION_SOLICITATION.md)),
so a new mapping can reference observed adoption behavior rather than internal
claims alone. Integrity hygiene on the already-delivered first wave — schema,
local validation, edition provenance and stale/overclaim detection — does not
promote a new framework and does not by itself satisfy or bypass M5.

**First wave delivered:**
[`68_STANDARDS_MAPPING_FIRST_WAVE.md`](68_STANDARDS_MAPPING_FIRST_WAVE.md) maps
observable Nornyx control capabilities to control *themes* for the backlog's
first-wave frameworks, with every row labelled by control surface and an
explicit non-coverage table. It is theme-level: clause/control identifiers are
recorded as non-coverage rather than invented, because standard text is not in
this repository and must not be reproduced without rights. Framework
edition/version provenance is a separate public-fact field and may be recorded
without reproducing standard text. Second-wave and future-wave frameworks remain
unimplemented and backlog-gated.

## Objective

Create a versioned, machine-checkable standards-mapping layer that maps
external framework requirements to Nornyx controls, evidence, approvals,
evals, gaps, and assurance boundaries.

Enterprises adopting governed agentic delivery are asked "how does this align
with our framework obligations?" A deterministic mapping from framework
requirements to concrete Nornyx contract elements lets a `.nyx` contract
answer that question with evidence instead of prose — while staying inside
Nornyx's honesty boundary: Nornyx validates declared contracts and supplied
evidence, not unverifiable runtime truth.

## Mapping waves

### First wave — complete at theme level

- NIST AI RMF;
- OWASP Top 10 for LLM Applications / OWASP GenAI;
- ISO/IEC 42001;
- explicit gap/non-coverage reporting.

### First-wave integrity substrate — issue #81

Issue #81 is bounded to the existing first wave:

- closed, versioned machine-readable schema;
- deterministic local-only validator;
- machine-readable MAP/NC records;
- generated documentation-class human-readable reports;
- existing claim type and control-surface fields;
- ADR-0040 assurance-tier and surface-scope fields where applicable;
- framework edition/version provenance;
- a small human-maintained local registry of known current editions and
  publication dates;
- deterministic comparison of mapping edition to registry edition;
- stale, contradictory, non-coverage-inconsistent and overclaiming fixtures.

The registry is updated only through ordinary governed repository change. The
validator performs no live discovery or network retrieval. `STALE` is a
validator diagnostic produced when a mapping's recorded edition differs from
the local registry; it is not an assurance or compliance status.

### Deferred clause/source grounding

Backlog-only until authoritative source access and citation rights are
available. Clause/control identifiers must never be invented, and licensed
standard text must not be reproduced without rights.

This deferred scope does **not** include recording public provenance facts such
as a framework name, edition/version or publication date for an existing
first-wave mapping. Those fields are required for deterministic stale-edition
detection and do not imply clause-level grounding.

### Second wave — backlog only

- ISO/IEC 23894;
- NIST SSDF;
- ISO/IEC 27001/27002 relationships relevant to Nornyx;
- SLSA;
- OpenTelemetry GenAI trace-conformance mapping.

### Future wave — adoption/use-case gated

- EU AI Act, subject to legal review;
- SOC 2 evidence-support mapping;
- COBIT;
- ITIL;
- TOGAF.

## Acceptance criteria

- every first-wave mapping records its framework edition/version provenance;
- clause/control source identifiers are required only when separately grounded
  under an authorized source-grounding unit and must never be invented;
- every mapping names the Nornyx control, evidence, eval, approval, or gap it
  maps to;
- partial or bounded support cannot be reported as full coverage;
- reports say **supports**, **maps**, or **operationalizes** — never
  certifies, complies, or guarantees;
- the explicit non-coverage half remains first-class;
- deterministic local validation only;
- no customer-specific overall coverage or assurance verdict is computed.

## Non-goals

- no certification;
- no legal advice;
- no audit opinion;
- no claim that Nornyx proves runtime truth;
- no copyrighted standard text reproduction;
- no live network retrieval;
- no automatic approval;
- no customer-specific compliance/coverage score;
- no GRC/control-tower workflow;
- no new framework under the first-wave integrity unit.

## Relationship to assurance tiers

Mappings must respect the assurance-tier boundaries in
[`docs/decisions/ADR-0040-governance-assurance-tiers.md`](decisions/ADR-0040-governance-assurance-tiers.md):
a mapping can state which tier of assurance a Nornyx control provides for a
framework requirement, and must never present a Tier 1/Tier 2 control as a
higher-assurance claim.
