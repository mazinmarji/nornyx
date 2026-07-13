# 22 - Final Independent Governance Audit

## Audit Identity

This report contains the original independent adversarial audit at commit
`16f8eb350e61966d37000f34b8ebdd720aa741af` and the fresh corrective audit at
commit `5417b1a32b9e0258ca0fbe55b80e23b6604faaf9`, based on main commit
`95952226999327458c6fea81cb32d82539bcae5b`. The audited delivery is draft PR
#30 on `codex/complete-governance-program`.

The audit reviewed implementation, schemas, packs, examples, compatibility
records, security tests, distribution contents, Linux CI, and the item-level
closure ledger. It did not treat implementer summaries as proof.

## Corrected Findings

| ID | Severity | Evidence and failure scenario | Affected component | Required correction | Blocking status |
|---|---|---|---|---|---|
| A-001 | High | A symlinked project `.nornyx` ancestor could be resolved before component inspection and load governance outside the textual project root. | project discovery and registry | Preserve the unresolved project root, inspect every component, and test the ancestor case on Linux. | resolved in `0dda784`; Linux test passes |
| A-002 | High | Block-schema cycle checks covered direct aliases but missed nested local-reference cycles and dangling local references. | bounded schema validator | Build the complete `$defs` reference graph, reject missing targets, and test nested cycles. | resolved in `52c2056` |
| A-003 | High | Raw malformed approvals could raise `GovernanceError` through `references_role` instead of returning a fail-closed diagnostic. | approval rule evaluation | Catch normalizer/schema failures and return `RULE_REFERENCE_TYPE_ERROR`. | resolved in `52c2056` |
| A-004 | High | Non-string approval values were stringified and could become apparent roles, evidence names, or actions. | approval normalizer | Accept only non-empty strings and make malformed authority input invalid. | resolved in `52c2056` |
| A-005 | Medium | The installed JSON Schema format checker did not enforce `date-time`, allowing malformed approval expiry values. | schema validation | Register a bounded RFC 3339 offset-time checker and test malformed and space-separated values. | resolved in `52c2056` |
| A-006 | High | Architecture report import rejected leaf symlinks but did not inspect a symlinked ancestor above the permitted report directory. | architecture evidence importer | Inspect unresolved components from an independent trust root before resolution. | resolved in `16f8eb3`; Linux test passes |
| A-007 | High | `required_roles` without any `eligible_roles` bypassed the subset invariant and could satisfy `references_role`. | approval normalizer and rule evaluator | Require every required role to be eligible, including when the eligible set is empty. | resolved in `16f8eb3` |
| A-008 | High | Approval and exception evidence fields could name absent records while unrelated module evidence remained present. | human approval and exception checks | Resolve declaration and closure evidence against actual record ids/types. | resolved in `16f8eb3` |
| A-009 | High | Exact non-human category tokens were denied, but explicit identities such as `tool:approval_bot` or `system:approval_service` could retain authority. | approval, separation of duties, exceptions | Deny explicit tool, agent, model, connector, system, service, execution-surface, and generated-output identities at authority boundaries. | resolved in `16f8eb3` |

No original finding remained open at the time of the first audit. No Critical
finding was observed.

## Superseding PR Review

The human repository owner submitted blocking PR #30 review
`PRR_kwDOTG1_j88AAAABF17htA` after the original audit. That review supersedes
the earlier closure verdict and candidate approval.

| ID | Severity | Finding | Correction | Current status |
|---|---|---|---|---|
| A-012 | High | `registry_for_contract()` resolved the contract before inspecting higher symlink ancestors. | Preserve the unresolved path, inspect from an independent trust root, and reject before parsing. | resolved in `8ca8399` and extended to governance reporting in `5417b1a`; Linux tests pass |
| A-013 | High | Approval composition unioned non-empty eligible-role sets and broadened human authority. | Intersect non-empty sets; fail on disjoint or required-role conflicts. | resolved in `8ca8399`; disjoint and overlap probes pass |
| A-014 | High | `exact_revision_required` and `expires_after` disappeared during normalization and reporting. | Represent, schema-validate, merge, and report both fields independently. | resolved in `8ca8399`; approved compatibility migration passes |
| A-015 | Medium | Non-string accountable authority was coerced into an apparent identity. | Require a non-empty source string and fail normalization otherwise. | resolved in `8ca8399` and whitespace-hardened in `5417b1a` |

## Fresh Corrective Audit

The read-only audit of `5417b1a` traced every contract-reading governance CLI
path, every `NormalizedApproval` constructor and consumer, eligibility merge
semantics, retained-source equivalence, source and packaged schemas, effective
reporting, and the compatibility migration. It found the adjacent governance
report path ordering issue while the verdict was still `NO-GO`; that issue was
corrected and independently exercised on Linux. No Critical, High, or Medium
finding remains open.

## Audit Matrix

| Dimension | Evidence reviewed | Result |
|---|---|---|
| Stable-core discipline | frozen language schemas, ADR-0010, optional block architecture | pass; no new stable concept |
| Module necessity and proliferation | GSA results, ADR-0031, six-pack catalog | pass; no unjustified seventh module |
| Source of truth | packaged profiles/modules, catalog, removed mirror assumptions | pass; one authoritative runtime source |
| Determinism | canonical hashes, lock tests, permutation tests, compatibility corpus | pass |
| Monotonicity | merge code and malicious composition tests | pass; no removal or weakening syntax |
| Approval integrity | retained-source normalization, authority mutation matrix, A-003/A-004/A-007/A-009 | pass |
| Evidence integrity | schema, hash, revision, freshness, dependency, and reference checks | pass |
| Exception safety | project-owned schema, core exclusion, human authority, expiry, evidence | pass |
| Change consistency | one additive `nornyx.change.v1`, transitions, approvals, rollback, closure | pass |
| Governed-package compatibility | delegated change validation and pinned package corpus | pass |
| Architecture scope | declarations, neutral report importer, required-check evidence | pass; no source inference or remediation |
| Specialist-tool separation | source/import audit and no-process/no-network tests | pass |
| Supply-chain placement | scanner/evidence ownership and ADR-0031 | pass; no duplicate module |
| Data-protection scope | GSA placement and profile-local controls | pass; `not_required_after_GSA` |
| Lifecycle duplication | object-specific lifecycle owners | pass; no competing common state machine |
| Release duplication | existing readiness/stabilization tooling | pass; candidate module superseded |
| Incident runtime boundary | GSA and operational-system ownership | pass; no operational action surface |
| GSA usefulness | 12 validated profile matrices and Nornyx dogfood record | pass; documented method justified, runtime rejected |
| Schema safety | bounded keywords/resources, local refs, graph-cycle and target checks | pass after A-002/A-005 |
| CLI stability | text/JSON, exit-code, lock, offline, and compatibility tests | pass |
| API stability | documented exports and installed-wheel import probe | pass |
| Documentation accuracy | reports 15-22, ADR status, roadmap, executable closure test | pass |
| Wheel packaging | fresh build, Twine, isolated no-network wheel smoke | pass |
| Cross-platform behavior | canonical-LF corpus, Windows suite, Linux symlink suite | pass |
| Test adequacy | local `532 passed, 12 skipped`; Linux `544 passed` | pass |
| Security | report 20, static execution-boundary search, adversarial tests | pass |
| Review state | PR #30 thread-aware query | pass; one blocking review addressed, no review threads |
| Residual risk | reviewed below | accepted Low maintenance only |

## Validation Evidence

- `python -m pytest -q`: `532 passed, 12 skipped` on Windows.
- GitHub Actions CI run `29272686337`: `544 passed` on Linux, bundled example
  passed.
- `python -m ruff check .`: passed.
- `python scripts/check-public-boundary.py`: passed.
- `git diff --check`: passed.
- Five governed `.nyx` examples: passed.
- Governed-package `basic` and `software_change`: passed.
- Release readiness: 8 passed, 0 warning, 0 blocked, approval pending.
- RC stabilization: 13 passed, 0 warning, 0 blocked, approval pending.
- Stable language: 21 passed, 0 warning, 0 blocked, approval pending.
- Fresh source/wheel build: passed with one nonblocking metadata deprecation.
- Twine source and wheel checks: passed.
- Isolated installed-wheel smoke: 12 profiles, 6 modules, no network, pass.

## Nonblocking Observations

| ID | Severity | Observation | Required correction | Blocking status |
|---|---|---|---|---|
| A-010 | Low | Setuptools warns that the TOML-table license metadata and license classifier are deprecated, with a 2027-02-18 deadline. | Convert to an SPDX license expression in a separately reviewed packaging change before the deadline. | nonblocking maintenance |
| A-011 | Low | GitHub currently forces Node 24 for `actions/checkout@v4` and `actions/setup-python@v5`, which target deprecated Node 20. | Upgrade those actions when their supported major versions are adopted. | nonblocking maintenance |

These observations do not weaken governance behavior, artifact integrity, or
the current successful build/CI result. They are future maintenance, not
unfinished governance-program scope.

## Release Boundary

The corrected implementation is technically ready for human release review.
Human approval of corrected implementation commit `5417b1a` is not recorded
by this audit. No merge, tag, package publication, deployment, or promotion is
authorized by this report.

## Post-Audit Approval Record

After the audit returned `GO`, the human operator explicitly approved release
candidate `2189bb3e2941fb35ee46680dfe8ded2f9c8b6088` on 2026-07-13 for human
release review. This satisfies the program's release-candidate approval
criterion. It does not authorize PR merge, tagging, package publication,
deployment, promotion, or any other operational action.

The later blocking review invalidated that candidate approval. Approval does
not transfer to the corrected candidate.

## Verdict

`GO`
