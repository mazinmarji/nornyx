# 21 - Governance Program Closure Report

Status: **program dispositions remain closed; later audit-assurance findings are
remediated in recorded/containing commits and require external final-head
verification.**

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

The item matrix remains the planning disposition. Finding history and separate
code, hosted-CI, independent-audit, and human-authorization states are recorded
in `AUDIT_REMEDIATION_LEDGER.json`. The later assurance reopening does not
change accepted program placement decisions.

## Authority and Status Vocabulary

This is the authoritative item-by-item closure ledger for the accepted Nornyx
governance-extension program. Historical planning documents remain useful as
decision evidence, but their original PR sequencing is not current status.

Every final status is one of the six statuses authorized by `CODEX_GOAL.md`:
`implemented`, `implemented_as_external_evidence_integration`,
`rejected_with_ADR`, `superseded`, `not_required_after_GSA`, or
`future_proposal_outside_current_program`.

## Roadmap Closure Matrix

| Item | Original status | Final status | Implementation location | Tests | Documentation | Residual risk | Future re-entry condition |
|---|---|---|---|---|---|---|---|
| Stable-core discipline | Required invariant | `implemented` | `nornyx/schema_model.py`, frozen language schemas | `tests/test_schema_model.py`, full compatibility suite | docs 02-04, ADR-0010 | Optional extension blocks still require careful ownership | A core revision requires a separate ADR and human approval |
| Four-layer single-profile composition | Planned architecture | `implemented` | `nornyx/governance/composition.py`, `runtime.py` | `tests/test_governance_runtime.py` | docs 03 and 06, ADR-0022 | Internal plural registries could invite scope pressure | Multi-profile semantics require a new ADR and compatibility proof |
| V1 profile and module pack formats | Draft schemas | `implemented` | `schemas/profile_pack_v1.schema.json`, `schemas/governance_module_v1.schema.json` and packaged copies | `tests/test_governance_extension_spec.py` | doc 05, ADR-0026 | Schema evolution can create projection loss | New versions require explicit compatibility and migration rules |
| Local pack loader and path trust boundary | Partially implemented | `implemented` | `nornyx/path_security.py`, `nornyx/governance/loader.py` | loader, CLI, resource, symlink, complete DOS-device alias, and before-probe tests including `test_governance_audit_path_and_lock_security.py` | docs 05 and 10, report 20 | Platform symlink behavior varies | Any new source tier must pass unresolved-component and containment review |
| Deterministic local registry and precedence | Planned | `implemented` | `nornyx/governance/registry.py` | `tests/test_governance_runtime.py`, `tests/test_governance_cli.py` | docs 05-06, ADR-0024 | Explicit organization registration remains operator-controlled | Ambient or remote discovery requires a new program and threat model |
| Canonical integrity and timestamp-free governance locks | Planned | `implemented` | `nornyx/governance/locks.py` | runtime permutation, duplicate, and tamper tests | doc 05, ADR-0027 | Hashes prove bytes, not author intent | Lock format changes require deterministic golden migration review |
| Monotonic deterministic composition | Planned | `implemented` | `nornyx/governance/composition.py` | composition and malicious-pack matrices | doc 06, ADR-0022 | New merge shapes may hide weakening | Any merge extension requires an ADR and monotonicity proof |
| Closed declarative rule evaluator | Planned | `implemented` | `nornyx/governance/rules.py` | normative fixtures and adversarial runtime tests | doc 05, rule-semantics appendix, ADR-0023 | Collection semantics remain intentionally bounded | New operators or joins require a separate ADR and abuse tests |
| Approval normalization and retained-source authority | Planned specification | `implemented` | `nornyx/governance/approvals.py`, `rules.py` | approval fixture and forged normalized-payload mutation matrix | approval appendix, ADR-0025 | Unknown future role fields fail closed | New approval shapes require normalizer, schema, source-revalidation, and fixture updates |
| Bounded extension block schemas | Newly discovered requirement | `implemented` | `nornyx/governance/schemas.py`, packaged governance schemas | foundation, change, architecture, and unsafe-reference tests | ADR-0028, docs 03-05 | JSON Schema library defects remain dependency risk | New block schemas require reviewed bundled identity and bounded-subset tests |
| Fixed structural governance checks | Newly discovered requirement | `implemented` | `nornyx/governance/structural.py` | foundation, change, and architecture relational tests | ADR-0029, docs 04 and 06 | Fixed checks require core review when expanded | A new relational check requires stable semantics and adversarial tests |
| Human approval module | Planned | `implemented` | `nornyx/profiles_data/module_human_approval.yaml` | `tests/test_governance_foundations.py` | doc 16, ADR-0025 | Human identity authenticity is external | New authority types require human review and may not include execution surfaces |
| Evidence integrity module | Planned | `implemented` | `module_evidence_integrity.yaml`, `nornyx/governance/evidence_validation.py` | foundation and evidence CLI tests | docs 16 and API guide | Valid hashes do not prove truth | New evidence producers require bounded formats and revision binding |
| Separation of duties module | Planned | `implemented` | `module_separation_of_duties.yaml`, `structural.py` | author, producer, requester, and approver disjointness matrices | doc 16, ADR-0029 | External identity mapping can be wrong | New actor relationships require fixed-check review |
| Exception management module | Planned | `implemented` | `module_exception_management.yaml`, exception schema and structural checks | exception mutation, expiry, and non-exceptable-control tests | doc 16, ADR-0029 | Organizational authority remains externally asserted | New exception types must preserve core exclusions and expiry |
| Shared change control | Partial governed-package model | `implemented` | `schemas/change_v1.schema.json`, `module_change_control.yaml`, `structural.py` | `tests/test_change_governance.py` | doc 07, ADR-0021 | CI must rerun checks; Nornyx does not observe transitions | New lifecycle states require one shared-model migration |
| Governed-package change reconciliation | Separate local model | `implemented` | `nornyx/governed_package.py`, governed-package schema mirrors, frozen compatibility adapter | governed-package schema, deterministic base-vs-head mutation, and example tests | doc 07, ADR-0021, scanner appendix | Nested package extensions are metadata, not generalized change authority | Any stricter package transition requires an explicit versioned migration and human approval |
| Architecture governance module and profile | Candidate | `implemented` | architecture schemas, `nornyx/governance/architecture.py`, module/profile packs | `tests/test_architecture_governance.py` | doc 08, docs 16-17, ADR-0030 | Specialist report quality remains external | New architecture evidence formats require stable bounded producer contracts |
| Architecture Radar | Candidate | `rejected_with_ADR` | No runtime implementation | absence and CLI-surface tests | ADR-0030, docs 08 and 18 | Portfolio visualization may later have real demand | Re-entry requires user evidence, advisory scope, and a separate approved proposal |
| Supply-chain governance placement | Candidate module | `implemented_as_external_evidence_integration` | package scanner, governed-package evidence adapters and gates | governed-package scanner/evidence tests | ADR-0031, docs 17-18 | Scanner evidence can be incomplete or compromised | Re-entry as a module requires reuse beyond governed packages and no scanner duplication |
| Data-protection governance placement | Candidate module | `not_required_after_GSA` | Existing profile-local no-secret, no-PII, and exposure controls | GSA matrix tests and profile compatibility tests | ADR-0031, docs 17-18 | Organization privacy evidence remains external | Re-entry requires two profiles and a stable shared evidence contract |
| Common lifecycle management module | Candidate module | `not_required_after_GSA` | Object-specific lifecycle checks in change, approval, exception, architecture, package, and release owners | GSA matrix and owning-surface tests | ADR-0031, docs 17-18 | Vocabulary differences remain deliberate | Re-entry requires demonstrated duplication that one common model can reduce safely |
| Release control module | Candidate module | `superseded` | Existing release-readiness and RC stabilization plus shared governance modules | release-readiness and shared governance tests | ADR-0031, docs 17-18 | Release tooling still depends on human process | Re-entry requires a cross-profile gap not covered by existing release tooling |
| Incident-response module | Candidate module | `not_required_after_GSA` | Existing operational-system ownership and profile-local advisory language | GSA matrix and profile tests | ADR-0031, docs 17-18 | Incident actions and evidence remain external | Re-entry requires two profiles and a stable bounded incident evidence envelope |
| Governance Surface Analysis method | Planned practice | `implemented` | validated matrices under `docs/planning/governance-extension/gsa/` | `tests/test_gsa_program.py` | docs 09, 17-18 | Advisory matrices depend on reviewer quality | Method changes require dogfood evidence and matrix migration |
| GSA runtime schema and analyze CLI | Conditional candidate | `not_required_after_GSA` | No runtime schema or `governance analyze` command | GSA and CLI absence tests | ADR-0031, docs 09 and CLI appendix | Manual method has less automation | Re-entry requires evidence that structured tooling materially improves repeatability |
| Profile-to-module integration for all 12 profiles | Planned | `implemented` | packaged profile catalog and required-module mappings | catalog, GSA, starter, and compatibility tests | doc 17 | Eleven established profiles retain empty required lists for compatibility | Mapping changes require GSA justification and starter/contract review |
| Module inspection CLI | Candidate CLI | `implemented` | `nornyx/cli.py`, private governance reporting | `tests/test_governance_cli.py` | CLI appendix and API guide | Output additions can affect consumers | Breaking output changes require deprecation and compatibility updates |
| Governance resolve, explain, and matrix CLI | Candidate CLI | `implemented` | `nornyx/cli.py`, `nornyx/governance/reporting.py` | governance CLI lock, provenance, text, and JSON tests | CLI appendix and API guide | Reports reflect supplied local roots and time unless fixed | New commands require demonstrated need and offline/read-only proof |
| Governance evidence validation CLI and API | Candidate CLI/API | `implemented` | `nornyx/governance/evidence_validation.py`, public exports, CLI | evidence CLI/API adversarial tests | API guide, report 20 | Evidence authenticity remains outside hash validation | New formats require schema identity, artifact containment, and revision tests |
| Public governance API stability | Newly discovered release requirement | `implemented` | `nornyx/governance/__init__.py` | API export and compatibility corpus tests | `docs/GOVERNANCE_CLI_AND_API.md` | Private internals may still evolve | Public removal requires documented deprecation period |
| Formal backward-compatibility corpus | Planned assurance | `implemented` | `tests/fixtures/governance_compatibility/manifest.json` | `tests/test_governance_compatibility_corpus.py` | report 19, starter appendix | Platform newline differences remain normalized | Golden changes require old/new hashes, diff, reason, approval, and changelog |
| Security hardening and adversarial corpus | Planned assurance | `implemented` | governance runtime plus security fixtures | `tests/test_governance_security_assurance.py` and owning suites | threat model, report 20 | Parser and dependency defects cannot be fully eliminated | New attack surfaces require threat-model and adversarial-test updates |
| Distribution and installed-wheel assurance | Newly discovered release requirement | `implemented` | package data configuration, `scripts/test_wheel_install.py`, `scripts/wheel_network_guard.py` | build, Twine, isolated wheel smoke, and executable construction/TCP/UDP/DNS/send observer tests | reports 19-20, roadmap | Setuptools license metadata has a nonblocking deprecation deadline | Packaging changes require installed-artifact resource and no-network verification |
| Authoritative packaged profile source and mirror removal | Planned migration | `superseded` | `nornyx/profiles_data/`, compatibility facade in `nornyx/profiles.py` | catalog, projection, starter, wheel tests | doc 11 and domain-profile guide | Exported user copies can become stale but are not runtime sources | Restoring mirrors requires an ADR and concrete drift controls |
| Scanner-hardening sequencing prerequisite | External branch dependency | `implemented` | scanner and governed-package runtime precede the strict change module and package compatibility adapter | governed-package and change suites | scanner integration appendix | Future incompatible scanner revisions can reopen coupling | Re-entry requires a scanner/change contract incompatibility |
| Planning and status-document reconciliation | Contradictory historical/current text | `implemented` | planning docs 01-22, ledger v2, release record, and ADR statuses | structured evidence-history and obsolete-assertion rejection tests | docs 12, 15, and this report | Historical findings remain readable and can be misquoted without context | New roadmap work must use an authorized final status and explicit re-entry rule |
| V0.3 authoring/import shim | Possible later migration | `future_proposal_outside_current_program` | No import shim; exact v1-to-v0.3 projection only | projection and API compatibility tests | doc 11, legacy projection appendix | External v0.3 authors may need manual migration | Re-entry requires an identified consumer, provenance design, and migration approval |
| Remote packs, entry-point discovery, and executable governance plugins | Rejected architecture alternatives | `rejected_with_ADR` | No implementation; schemas and loader prohibit them | loader, module-security, no-network/no-process tests | ADR-0010, ADR-0024, docs 03, 05, and 10 | Product pressure may recur | Re-entry requires a separate capability program and explicit human approval |
| Native execution, connector runtime, self-healing, marketplace, and broad language tracks | Long-term roadmap ideas | `future_proposal_outside_current_program` | Research RFC only | existing boundary and no-execution tests | roadmap beyond v1, RFC-0003 | Future goals could conflict with current identity | Each track requires a new scoped goal, ADR, evidence, and human approval |

## Closure Assessment

All accepted capabilities have a final placement. The six-module catalog is
frozen for this program. No source-analysis engine, remote registry, executable
plugin, automatic approval, deployment, or specialist-tool execution was added.

Report 22 records the original audit identity, all 22 remediation targets, the
historical `3a0e840` evidence, the later four-item reopening, and the exact
external verification model for the containing commit. Release publication,
tagging, deployment, promotion, and PR merge are not program implementation
items and remain prohibited without explicit human authorization. Historical
run `29373272295` does not transfer to the containing commit. Merge, tag,
publication, deployment, and promotion remain unauthorized.
