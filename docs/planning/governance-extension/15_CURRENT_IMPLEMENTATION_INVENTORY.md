# 15 - Current Implementation Inventory

Status: **containing-commit implementation inventory with historical evidence
anchors and an external final-head verification requirement.**

## Audit Evidence History

- Audited base: `95952226999327458c6fea81cb32d82539bcae5b`.
- Original NO-GO candidate: `35ee69359599af7887f6b9b58ae0a4cd06a48d25`.
- Main remediation implementation anchor:
  `81899aaac5e54781dfe9c8002f557a874854c8b8`.
- Historical exact-head CI candidate:
  `3a0e840c3229dbf58959df1e3a161318bffd94ac`; this is not the final approved
  candidate.
- Historical hosted CI run: `29373272295`, conclusion `success`.
- Historical Windows evidence on the `81899aa`/`3a0e840` lineage:
  `913 passed, 45 skipped`.
- Historical Linux evidence bound to `3a0e840` and run `29373272295`:
  `958 passed, zero skipped`.
- Historical wheel evidence: `12 profiles`, `6 modules`,
  `network_attempts=[]`, `network_used=false`.
- A later independent audit of `3a0e840` returned historical `NO-GO` and
  reopened `AUD-011-R1`, `AUD-017-R1`, `AUD-021-R1`, and `PRMETA-001`.
- Residual path and network remediation is anchored at
  `1319613697b0e94d177ebe2c879f73107c366c7e`; documentation reconciliation is
  implemented in the commit containing this record, whose SHA is intentionally
  not embedded.
- External final-head verification must resolve the containing commit from Git
  and GitHub, run hosted CI on that exact head, and bind a fresh independent
  audit to the same head.
- Human authorization is not granted. PR #30 remains draft; merge, release,
  tagging, publication, and deployment remain unauthorized.

## Baseline

This inventory reconciles the governance plan against commit
`95952226999327458c6fea81cb32d82539bcae5b` (Nornyx 1.5.2). The program branch
starts from that commit. At reconciliation time the clean baseline produced:

- `python -m pytest -q`: 400 passed, 6 skipped;
- `python -m ruff check .`: pass;
- public-boundary scan: pass;
- both primary `.nyx` examples: pass;
- governed-package basic validation: pass;
- `git diff --check`: pass.

The six local skips are platform/optional-environment cases. Linux CI is the
authority for real symlink behavior.

## Historical Baseline Matrix Before Implementation

This table records the 1.5.2 starting point. It is not the current program
status; the authoritative final dispositions are in report 21.

| Surface | State at 1.5.2 | Evidence | Program action |
|---|---|---|---|
| v1 profile/module schemas | Implemented, but stale draft comments remain | root and bundled schemas; schema tests | activate wording; add bounded fields |
| Local pack loader | Implemented | `nornyx/governance/loader.py` | preserve; extend schema checks only |
| Symlink/path trust boundary | Implemented after 1.5.2 hotfix | CLI and loader ancestor-symlink tests | retain Linux coverage |
| Registry and precedence | Implemented for builtin/project/explicit; org registration exists only as API | registry/runtime tests | document exact tiers; no network tier |
| Deterministic locks | Implemented | lock and composition tests | preserve byte stability |
| Rule evaluator | Implemented | normative fixture and adversarial tests | keep closed; do not add expressions |
| Approval normalization | Implemented and source-retained revalidation is fail closed | approval matrix and forged-source tests | reuse as sole model |
| Built-in profiles | 11 authoritative packaged v1 YAML packs | catalog, starter goldens, public API tests | map justified modules and add the approved architecture profile |
| Built-in modules | Absent | catalog has an empty module list | implement approved modules |
| Required block/evidence/approval semantics | Composed but advisory unless a rule happens to enforce them | 1.5.0 changelog and runtime | enforce through block schemas and fixed checks for selected modules |
| Structural relational checks | Absent | no structural-check catalog | implement bounded reviewed checks |
| Extension block schemas | Absent | module model has metadata/rules only | implement ADR-0028 |
| Shared change model | Partial and governed-package-local | governed-package schema/validator | create one additive schema and delegate |
| Change lifecycle and staleness | Absent | no transition/revision checks | implement in `change_control` |
| Exception model | Absent | planning semantics only | implement one non-core model |
| Governance evidence model | Partial: scanner records and old evidence scaffold are separate | scanner and `evidence.py` | add one revision-bound normalized contract; preserve old scaffold API |
| Architecture governance | Implemented in Stage D | module, optional profile, declaration/evidence/report schemas, neutral-envelope importer, starter, executable example, adversarial tests | retain boundary; Architecture Radar rejected by ADR-0030 |
| Supply-chain placement | `implemented_as_external_evidence_integration` | scanner, governed-package gates, and package evidence importers | retained in its existing owner; no duplicate module |
| Data-protection placement | `not_required_after_GSA` | profile-local no-secrets/no-PII/model-exposure controls | organizational privacy evidence remains external until a stable shared contract exists |
| Lifecycle placement | `not_required_after_GSA` | object-specific change, approval, exception, architecture, package, and release states | no competing common state machine |
| Release placement | `superseded` | local release-readiness/stabilization runtime plus shared governance modules | no parallel release module |
| Incident placement | `not_required_after_GSA` | operational systems and existing advisory profile language | re-entry requires two profiles and a stable evidence envelope |
| GSA method | Implemented as documented method and validated advisory matrices | docs 09, 17-18, `gsa/*.yaml`, ADR-0031, tests | no runtime schema or CLI justified |
| Module CLI | Implemented | `modules list/inspect/validate`, text/JSON tests | local inspection only; no execution or network |
| Governance explain/matrix CLI | Implemented | `governance resolve/explain/matrix`, lock/provenance tests | read-only resolution; `governance analyze` is not implemented |
| Evidence validation CLI | Implemented | `evidence validate`, public validator, adversarial path/hash tests | bounded local evidence sets only |
| Public API stability | Implemented and documented | `nornyx/governance/__init__.py`, `docs/GOVERNANCE_CLI_AND_API.md` | signatures preserved; private reporting internals not exported; deprecation floor recorded |
| Compatibility corpus | Implemented | formal manifest, all starters/examples, CLI, generated drift, locks, manifests, projections | release-gated hashes and approved migration metadata |
| Security assurance | Implemented for current surfaces | original runtime suite plus CLI/evidence/confusable/removal/revision/no-execution adversarial tests; report 20 | Linux CI remains authority for real symlinks |
| Planning/status documentation | Contradictory: PR 1/deferred language remained after runtime shipped | planning docs 01-14 and ADR statuses | reconciled in Stage I; report 21 is authoritative |

## Preserved Boundaries

The program adds no stable core concept. New domain blocks are optional module
surfaces validated after pack resolution. Packs remain inert YAML. Nornyx does
not fetch packs, execute tools, inspect source code, load credentials, approve,
deploy, publish, remediate, or activate connectors.

The existing profile API, governed-package minimum `changes[].id/type`, starter
goldens, profile projection, lock format, manifest promises, and contracts that
do not select governance modules remain compatibility anchors.

## Exact Implementation Sequence

1. Add bounded block-schema bindings and fixed structural-check declarations.
2. Implement and test human approval, evidence integrity, separation of duties,
   and exception management modules.
3. Add the strict shared change schema and `change_control`; reconcile governed
   packages through their frozen 1.x compatibility projection.
4. Add architecture schemas, evidence importer, module, profile, starter, and
   examples.
5. Complete GSA and ADR decisions for every later candidate.
6. Implement only GSA-approved later modules.
7. Map every profile to justified modules and record rejected alternatives.
8. Complete CLI/API hardening, compatibility corpus, security suite, wheel and
   cross-platform assurance.
9. Reconcile all planning/status documents, produce reports 16-22, and run an
   independent requirement-by-requirement audit in report 22.

Every stage must be green before the next stage. A Critical or High finding,
core revision, compatibility break, arbitrary expression requirement, external
execution requirement, or unbound evidence requirement stops the program.

## Current Implementation State

Stages A through I are implemented. Stage I reconciles the documentation,
closure matrix, and candidate evidence. The branch contains six reusable
modules, the shared change model, the governed-package compatibility adapter,
the optional `architecture_governance` profile, bounded architecture evidence
import, complete GSA decisions, and a compatibility-preserving mapping for
every profile. No later specialist module passed the proliferation gate.
CLI/API, compatibility, security, build, and installed-wheel assurance are
implemented. The initial 1.5.2 matrix above remains the historical baseline.
Report 21 is the authoritative item-by-item program status record. The main
AUD-001 through AUD-022 implementation anchor is `81899aa`; a later audit of
`3a0e840` reopened the four residual items listed above. Their code remediation
is anchored exactly, while this document's correction is identified by its
containing commit and requires external exact-head CI and audit verification.
Human approval and every operational release action remain unauthorized.
