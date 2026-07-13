# 15 - Current Implementation Inventory

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

## Closure Matrix Before Implementation

| Surface | State at 1.5.2 | Evidence | Program action |
|---|---|---|---|
| v1 profile/module schemas | Implemented, but stale draft comments remain | root and bundled schemas; schema tests | activate wording; add bounded fields |
| Local pack loader | Implemented | `nornyx/governance/loader.py` | preserve; extend schema checks only |
| Symlink/path trust boundary | Implemented after 1.5.2 hotfix | CLI and loader ancestor-symlink tests | retain Linux coverage |
| Registry and precedence | Implemented for builtin/project/explicit; org registration exists only as API | registry/runtime tests | document exact tiers; no network tier |
| Deterministic locks | Implemented | lock and composition tests | preserve byte stability |
| Rule evaluator | Implemented | normative fixture and adversarial tests | keep closed; do not add expressions |
| Approval normalization | Implemented and source-retained revalidation is fail closed | approval matrix and forged-source tests | reuse as sole model |
| Built-in profiles | 11 authoritative packaged v1 YAML packs | catalog, starter goldens, public API tests | map justified modules |
| Built-in modules | Absent | catalog has an empty module list | implement approved modules |
| Required block/evidence/approval semantics | Composed but advisory unless a rule happens to enforce them | 1.5.0 changelog and runtime | enforce through block schemas and fixed checks for selected modules |
| Structural relational checks | Absent | no structural-check catalog | implement bounded reviewed checks |
| Extension block schemas | Absent | module model has metadata/rules only | implement ADR-0028 |
| Shared change model | Partial and governed-package-local | governed-package schema/validator | create one additive schema and delegate |
| Change lifecycle and staleness | Absent | no transition/revision checks | implement in `change_control` |
| Exception model | Absent | planning semantics only | implement one non-core model |
| Governance evidence model | Partial: scanner records and old evidence scaffold are separate | scanner and `evidence.py` | add one revision-bound normalized contract; preserve old scaffold API |
| Architecture governance | Absent | design document only | module, profile, schemas, importer, example |
| Supply-chain placement | Partial inside governed packages/scanner | scanner and package evidence importers | GSA and final ADR; do not duplicate scanners |
| Data-protection placement | Absent as composed governance | profile policy text only | GSA before module decision |
| Lifecycle placement | Fragmented across existing object-specific models | lifecycle extension docs/tooling | GSA; avoid competing lifecycle fields |
| Release placement | Existing local release-readiness tooling, no governance module | release readiness runtime/tests | GSA and reconcile, not parallelize |
| Incident placement | Existing extension blocks/advisory docs, no composed module | checker extension list and incident docs | GSA before module decision |
| GSA method | Planned/advisory | planning document 09 | complete method and dogfood; tooling only if justified |
| Module CLI | Absent | only `profiles` commands exist | add only list/inspect/validate |
| Governance explain/matrix CLI | Partial via `profiles resolve` | CLI and composition output | add only if needed for provenance/mapping |
| Evidence validation CLI | Absent | package import is scanner-specific | add bounded local validation |
| Public API stability | Runtime exports are broad and undocumented | `nornyx/governance/__init__.py` | mark intentional contracts; keep signatures |
| Compatibility corpus | Partial | profile goldens and generated drift fixtures | add examples, CLI, locks, manifests, projections |
| Security assurance | Strong pack/rule baseline; new surfaces untested | runtime adversarial suite | extend for schemas/evidence/exceptions |
| Planning/status documentation | Contradictory: PR 1/deferred language remains after runtime shipped | planning docs 01-14 and ADR statuses | reconcile to actual state |

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
3. Add the shared change schema and `change_control`; reconcile governed
   packages without changing the minimum compatibility tier.
4. Add architecture schemas, evidence importer, module, profile, starter, and
   examples.
5. Complete GSA and ADR decisions for every later candidate.
6. Implement only GSA-approved later modules.
7. Map every profile to justified modules and record rejected alternatives.
8. Complete CLI/API hardening, compatibility corpus, security suite, wheel and
   cross-platform assurance.
9. Reconcile all planning/status documents, produce reports 16-21, and run an
   independent requirement-by-requirement audit in report 22.

Every stage must be green before the next stage. A Critical or High finding,
core revision, compatibility break, arbitrary expression requirement, external
execution requirement, or unbound evidence requirement stops the program.

