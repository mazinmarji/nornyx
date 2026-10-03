# Standards Mapping and Enterprise Assurance

## Status

Strategic priority **P1** under the post-v1.0 reweighting in
[`docs/03_ROADMAP_TO_v1_AND_BEYOND.md`](03_ROADMAP_TO_v1_AND_BEYOND.md)
(milestone M4).

The first-wave mapping is complete and recorded by closed
[issue #47](https://github.com/mazinmarji/nornyx/issues/47). The current active
implementation unit is
[issue #81](https://github.com/mazinmarji/nornyx/issues/81), which owns the
machine-readable mapping schema and deterministic validator.

Source/version and clause grounding formerly tracked by #82, and second-wave
framework expansion formerly tracked by #83, are **backlog-only**. They are not
active implementation issues. Their scope remains in
`docs/backlog/nornyx-standards-mapping-roadmap.yaml` and should be promoted to a
fresh scoped issue only when source access, a concrete use case, and an actual
implementation window exist.

Issue-governance rule for this workstream:

> Keep GitHub Issues for active or near-active executable work. Keep deferred
> roadmap candidates in the repository backlog until they are explicitly
> promoted.

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
frameworks remain unimplemented and backlog-gated.

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

### First wave — complete at theme level

- NIST AI RMF;
- OWASP Top 10 for LLM Applications / OWASP GenAI;
- ISO/IEC 42001;
- explicit gap/non-coverage reporting.

### Active P1 implementation

Issue #81:

- closed, versioned machine-readable schema;
- deterministic local-only validator;
- machine-readable mapping records;
- generated human-readable reports;
- stale, contradictory, partial, and overclaiming fixtures.

### Deferred source/version grounding

Backlog-only until authoritative source/version access and citation rights are
available. Clause/control identifiers must never be invented, and licensed
standard text must not be reproduced without rights.

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

- every grounded mapping cites the framework version and source identifier;
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
