# Issue #81 first-wave integrity-hygiene scope proposal

**Proposal only. This document authorizes nothing and does not change issue #81's current scope.**

This document records a product-neutral design option for a bounded first-wave
standards-mapping integrity-hygiene slice. Current Nornyx canon remains
controlling unless a later, explicitly authorized Nornyx change updates the
governing planning surfaces consistently.

Until such an authorized Nornyx change exists:

- `docs/64_STANDARDS_MAPPING_AND_ENTERPRISE_ASSURANCE.md` remains controlling as written on `main`;
- `docs/68_STANDARDS_MAPPING_FIRST_WAVE.md` remains controlling as written on `main`;
- `docs/03_ROADMAP_TO_v1_AND_BEYOND.md` remains controlling as written on `main`;
- `docs/backlog/nornyx-standards-mapping-roadmap.yaml` remains controlling as written on `main`;
- the live GitHub issue #81 body must not be changed on the basis of this proposal;
- no implementation work is authorized by this document.

## Proposed bounded scope

If separately authorized through normal Nornyx governance, the slice would apply
only to first-wave material that already exists:

- NIST AI RMF;
- OWASP GenAI / Top 10 for LLM Applications;
- ISO/IEC 42001;
- existing `MAP-*` and `NC-*` rows.

The proposed hygiene work would be limited to:

1. a closed, versioned machine-readable representation of existing first-wave `MAP-*` / `NC-*` records;
2. deterministic local-only validation;
3. existing Nornyx claim type and control-surface fields;
4. ADR-0040 assurance-tier and surface-scope metadata where applicable;
5. framework edition/version provenance as public provenance facts;
6. a small human-maintained local registry of known framework editions/publication dates;
7. deterministic comparison of a mapping's recorded edition to that local registry;
8. structural diagnostics for stale, contradictory, invalid, non-coverage-inconsistent, and overclaiming records;
9. a generated documentation-class human-readable report.

`STALE` would be a validator diagnostic only. It would not be a compliance,
assurance, applicability, or customer-coverage state.

The validator would perform **no live network retrieval** and would not discover
new framework editions. The intended sequence would be:

external observation → human review → governed registry update → deterministic local comparison → stale diagnostic where applicable.

## Proposed edition/version split

If this bounded slice is separately authorized, framework edition/version
provenance would move into the hygiene slice because stale-edition detection
cannot work without it.

This is distinct from clause/control/source grounding.

Still deferred unless separately authorized:

- numbered clause/control mappings;
- source/control identifiers requiring authoritative source access or licensing;
- copyrighted standards text;
- licensed control content;
- legal applicability interpretation;
- conformity/certification conclusions.

Because current roadmap/backlog records group version grounding together with
source/clause grounding, any activation of this proposal must update all affected
Nornyx planning surfaces in the same governed change so the repository does not
carry contradictory instructions.

At minimum that later authorized change would reconcile:

- `docs/64_STANDARDS_MAPPING_AND_ENTERPRISE_ASSURANCE.md`;
- `docs/68_STANDARDS_MAPPING_FIRST_WAVE.md`;
- `docs/03_ROADMAP_TO_v1_AND_BEYOND.md` where it describes version identifiers as non-coverage;
- `docs/backlog/nornyx-standards-mapping-roadmap.yaml` where source/version grounding is deferred;
- the live GitHub issue #81 body.

## Proposed claim model

Do not create a new generic standards-coverage ontology.

The machine-readable representation should compose existing semantics:

- mapping/non-coverage id;
- framework + edition/version provenance;
- Nornyx capability/semantic;
- Nornyx claim type;
- Nornyx control surface;
- ADR-0040 assurance tier/scope where applicable;
- evidence/check reference;
- explicit claim boundary;
- residual/non-coverage relationship;
- provenance/review metadata.

Structural validator diagnostics may include terms such as stale, invalid,
contradictory, or overclaim. They are not compliance states.

The earlier issue #81 candidate status list (`implemented`, `partial`,
`external_dependency`, `not_applicable`, `gap`) must not become a second
canonical assurance/coverage model if the slice is authorized.

## Explicitly outside this proposal

Even if the bounded slice is later authorized, this proposal does not include:

- any new framework;
- second-wave or future-wave framework expansion;
- clause-level mapping;
- copyrighted-standard ingestion;
- live standards retrieval or feeds;
- automatic remapping when a framework changes;
- legal/applicability determination;
- customer-specific framework state;
- coverage/compliance percentages;
- a GRC/control-tower product;
- downstream platform-specific standards product work;
- runtime enforcement, PDP/PEP, identity, or inventory work;
- certification, attestation, audit opinion, or legal-compliance claims.

## Activation gate

No item above becomes active scope from this proposal.

Activation requires a separately authorized Nornyx change that:

1. preserves the public product-neutral boundary;
2. updates the relevant roadmap, backlog, standards-mapping docs, and live issue together so they do not conflict;
3. passes the required Nornyx CI/checks;
4. receives the independent review required by repository governance before merge.

This proposal exists only so the possible public-Nornyx shape can be reviewed
without silently converting a design option into active implementation scope.
