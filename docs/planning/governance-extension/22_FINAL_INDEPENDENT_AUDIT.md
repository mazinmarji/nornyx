# 22 - Final Independent Governance Audit

## Audit Identity

This report is the independent adversarial audit of the governance-extension
program at commit `16f8eb350e61966d37000f34b8ebdd720aa741af`, based on main
commit `95952226999327458c6fea81cb32d82539bcae5b`. The audited delivery is
draft PR #30 on `codex/complete-governance-program`.

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

No corrected finding remains open. No Critical finding was observed.

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
| Test adequacy | local `522 passed, 10 skipped`; Linux `531 passed` | pass |
| Security | report 20, static execution-boundary search, adversarial tests | pass |
| Review state | PR #30 thread-aware query | pass; no comments, reviews, or threads |
| Residual risk | reviewed below | accepted Low maintenance only |

## Validation Evidence

- `python -m pytest -q`: `522 passed, 10 skipped` on Windows.
- GitHub Actions CI run `29259022794`: `531 passed` on Linux, bundled example
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

The implementation is technically release-ready. Human release approval is
not recorded by this audit. No merge, tag, package publication, deployment, or
promotion is authorized by this report.

## Verdict

`GO`
