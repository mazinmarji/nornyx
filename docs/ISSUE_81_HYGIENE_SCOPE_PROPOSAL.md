# Issue #81 first-wave integrity-hygiene scope proposal

**Proposal only. This document authorizes nothing and does not change issue #81's current scope.**

This proposal records the Nornyx-side shape of the bounded first-wave standards-mapping integrity-hygiene slice that Arsoryn is considering through the separate FD-026 decision package.

Until FD-026 is independently reviewed and explicitly ratified by the founder:

- `docs/64_STANDARDS_MAPPING_AND_ENTERPRISE_ASSURANCE.md` remains controlling as written on `main`;
- `docs/68_STANDARDS_MAPPING_FIRST_WAVE.md` remains controlling as written on `main`;
- `docs/03_ROADMAP_TO_v1_AND_BEYOND.md` remains controlling as written on `main`;
- `docs/backlog/nornyx-standards-mapping-roadmap.yaml` remains controlling as written on `main`;
- the live GitHub issue #81 body must not be changed on the basis of this proposal;
- no implementation work is authorized by this document.

## Proposed scope if FD-026 is later ratified

The bounded slice would apply only to first-wave material that already exists:

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

`STALE` would be a validator diagnostic only. It would not be a compliance, assurance, applicability, or customer-coverage state.

The validator would perform **no live network retrieval** and would not discover new framework editions. The intended sequence would be:

external observation → human review → governed registry update → deterministic local comparison → stale diagnostic where applicable.

## Proposed edition/version split

If FD-026 is ratified, framework edition/version provenance would move into the bounded hygiene slice because stale-edition detection cannot work without it.

This is distinct from clause/control/source grounding.

Still deferred unless separately authorized:

- numbered clause/control mappings;
- source/control identifiers requiring authoritative source access or licensing;
- copyrighted standards text;
- licensed control content;
- legal applicability interpretation;
- conformity/certification conclusions.

Because current roadmap/backlog records group version grounding together with source/clause grounding, ratification must update all affected Nornyx planning surfaces in the same governed change so the repository does not carry contradictory instructions.

At minimum that ratification change would reconcile:

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

Structural validator diagnostics may include terms such as stale, invalid, contradictory, or overclaim. They are not compliance states.

The earlier issue #81 candidate status list (`implemented`, `partial`, `external_dependency`, `not_applicable`, `gap`) must not become a second canonical assurance/coverage model if the slice is authorized.

## Explicitly outside this proposal

Even if FD-026 is later ratified, the proposed bounded slice would not authorize:

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
- MCO or Nornyx Enterprise standards product work;
- runtime enforcement, PDP/PEP, identity, or inventory work;
- certification, attestation, audit opinion, or legal-compliance claims.

## Ratification gate

No item above becomes active scope until:

1. the Arsoryn FD-026 decision package receives exact-head independent review;
2. blocking findings are closed;
3. the founder explicitly ratifies the reviewed package;
4. the resulting authority-bearing Arsoryn ratification tranche is itself reviewed and merged under Arsoryn governance;
5. Nornyx then receives its own consistent ratification-aligned documentation/issue change under normal Nornyx governance.

This proposal exists only so the Nornyx-side consequences can be reviewed before authority is granted.
