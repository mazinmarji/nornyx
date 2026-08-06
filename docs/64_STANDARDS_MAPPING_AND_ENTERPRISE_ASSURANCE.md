# Standards Mapping and Enterprise Assurance

## Status

Proposed. Strategic priority **P1** under the post-v1.0 reweighting in
[`docs/03_ROADMAP_TO_v1_AND_BEYOND.md`](03_ROADMAP_TO_v1_AND_BEYOND.md)
(milestone M4). Tracked by the existing implementation issue
[mazinmarji/nornyx#47](https://github.com/mazinmarji/nornyx/issues/47); this
document and `docs/backlog/nornyx-standards-mapping-roadmap.yaml` are the
planning surface, not a duplicate tracker.

Sequenced after M5's adoption work
([`66_M5_A2_EXTERNAL_ADOPTION_SOLICITATION.md`](66_M5_A2_EXTERNAL_ADOPTION_SOLICITATION.md)),
so a mapping can reference observed adoption behavior rather than internal
claims alone.

**First wave delivered:**
[`68_STANDARDS_MAPPING_FIRST_WAVE.md`](68_STANDARDS_MAPPING_FIRST_WAVE.md) maps
observable Nornyx control capabilities to control *themes* for the backlog's
first-wave frameworks, with every row labelled by control surface and an
explicit non-coverage table. It is theme-level: clause and version identifiers
are recorded as non-coverage rather than invented, because standard text is not
in this repository and must not be reproduced. Second-wave and future-wave
frameworks in this document remain unimplemented.

## Objective

Create a versioned, machine-checkable standards-mapping layer that maps
external framework requirements to Nornyx controls, evidence, approvals,
evals, gaps, and assurance boundaries.

Enterprises adopting governed agentic delivery are asked "how does this align
with our framework obligations?" A deterministic mapping from framework
requirement identifiers to concrete Nornyx contract elements lets a `.nyx`
contract answer that question with evidence instead of prose — while staying
inside Nornyx's honesty boundary: Nornyx validates declared contracts and
supplied evidence, not unverifiable runtime truth.

## Mapping waves

### First wave

- NIST AI RMF;
- OWASP Top 10 for LLM Applications / OWASP GenAI;
- ISO/IEC 42001, using identifiers and original summaries only;
- a gap report for requirements Nornyx does not address.

### Second wave

- ISO/IEC 23894;
- NIST SSDF;
- SLSA;
- OpenTelemetry GenAI trace-conformance mapping.

### Future wave

- EU AI Act, subject to legal review;
- SOC 2 evidence-support mapping;
- COBIT;
- ITIL;
- TOGAF.

## Acceptance criteria

- every mapping cites the framework version and source identifier;
- every mapping names the Nornyx control, evidence, eval, approval, or gap it
  maps to;
- partial coverage cannot be reported as full coverage;
- reports say **supports**, **maps**, or **operationalizes** — never
  certifies, complies, or guarantees;
- deterministic local validation only.

## Non-goals

- no certification;
- no legal advice;
- no audit opinion;
- no claim that Nornyx proves runtime truth;
- no copyrighted standard text reproduction;
- no live network retrieval;
- no automatic approval.

## Relationship to assurance tiers

Mappings must respect the assurance-tier boundaries in
[`docs/decisions/ADR-0040-governance-assurance-tiers.md`](decisions/ADR-0040-governance-assurance-tiers.md):
a mapping can state which tier of assurance a Nornyx control provides for a
framework requirement, and must never present a Tier 1/Tier 2 control as a
higher-assurance claim.
