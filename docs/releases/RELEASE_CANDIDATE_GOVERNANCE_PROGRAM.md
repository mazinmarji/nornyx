# Nornyx Governance Program Candidate Record

## Record Identity

- Package version: `1.5.2`
- Branch: `codex/complete-governance-program`
- PR: `https://github.com/mazinmarji/nornyx/pull/30`
- PR state: draft

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

This is a historical candidate-evidence and prepared-metadata record, not a
release approval. It deliberately does not name the containing commit as the
final approved candidate.

## Included Program

The candidate contains six bounded data-only governance modules, twelve
profiles, one shared generalized change model with a governed-package 1.5.2
compatibility adapter, local evidence validation, deterministic composition
and locks, governance inspection CLIs, a stable public API, architecture
evidence integration, GSA dispositions, and the AUD-001 through AUD-022
security/compatibility corrections.

It adds no remote registry, executable pack/plugin surface, arbitrary policy
evaluator, external-tool invocation, network loading, automatic approval,
publication, deployment, or autonomous remediation.

## Gate State

| Gate | State |
|---|---|
| Main AUD-001 through AUD-022 remediation | anchored at `81899aa` |
| Compatibility migration proof | five migrations passed |
| Fresh `core.autocrlf=true` checkout | passed locally |
| Historical full Windows suite | `913 passed, 45 skipped` |
| Historical exact-head Linux suite | run `29373272295`: `958 passed, zero skipped` |
| Historical build, Twine, wheel and bundled example | passed on `3a0e840` |
| Historical installed-wheel result | 12 profiles, 6 modules, `network_attempts=[]`, `network_used=false` |
| Residual path/network code remediation | implemented in `1319613` |
| Residual documentation remediation | implemented in the containing commit |
| External final-head hosted CI | required for the resolved containing commit |
| External independent exact-head audit | required after green hosted CI |
| PR metadata replacement | prepared below; not published |
| Human candidate approval | not recorded |

## Prepared PR Description

The following template is preparation evidence only. It must not be published
until every placeholder is replaced from externally verified exact-head
evidence and the fresh independent audit verdict is `GO`.

```markdown
## Scope and exact identity

Completes the accepted Nornyx governance-extension program from audited base
`95952226999327458c6fea81cb32d82539bcae5b`.

- Main AUD-001 through AUD-022 remediation anchor:
  `81899aaac5e54781dfe9c8002f557a874854c8b8`
- Final exact PR head: `{{FINAL_HEAD}}`
- Final exact-head hosted CI run: `{{FINAL_CI_RUN_ID}}`
- Independent audit verdict: `{{FINAL_AUDIT_VERDICT}}`

## Remediation

AUD-001 through AUD-022 were remediated and independently revalidated. The
later audit of `3a0e840c3229dbf58959df1e3a161318bffd94ac` reopened four
residual items, now closed on the final exact head:

- AUD-011-R1: complete host-independent Windows DOS-device alias rejection
  before filesystem access.
- AUD-017-R1: historical, non-self-referential committed assurance records.
- AUD-021-R1: executable construction/TCP/UDP/DNS/send network-observer
  assurance with separate self-test and product logs.
- PRMETA-001: exact final evidence replaces obsolete metadata.

The compatibility corpus contains five verified migrations and one separately
recorded additive architecture starter.

## Validation

- Windows: `{{FINAL_WINDOWS_RESULT}}`
- Linux exact-head suite: `{{FINAL_LINUX_RESULT}}`
- Hosted workflow run `{{FINAL_CI_RUN_ID}}`: success on `{{FINAL_HEAD}}`
- Exact-candidate checkout and identity assertion: passed
- Candidate-aware diff from
  `95952226999327458c6fea81cb32d82539bcae5b`: passed
- Ruff and public-boundary checks: passed locally
- Source and wheel builds: passed
- Twine checks: passed
- Installed-wheel smoke: 12 profiles, 6 modules,
  `network_attempts=[]`, `network_used=false`
- Compatibility migration verifier: five migrations passed
- Additive architecture starter: separately recorded
- Bundled example: passed
- Fresh independent exact-head audit: `{{FINAL_AUDIT_VERDICT}}`

## Authorization boundary

PR #30 remains draft. This evidence grants no human approval and does not
authorize merge, readiness transition, auto-merge, release, tagging,
publication, deployment, or promotion.
```

## Authorization Boundary

PR #30 remains draft. Merge, release, tag, publication, and deployment are not
authorized. Any earlier candidate approval was invalidated by the blocking
review and does not transfer to the externally resolved final head.
