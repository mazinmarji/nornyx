# 20 - Security Assurance Report

## Current-State Addendum — 2026-07-17

PR #30 was subsequently merged and its governance-program release line reached
package 1.6.2. Statements below that PR #30 remained draft are retained as
historical exact-commit evidence, not current branch status. AN-001 is a new
candidate change and requires its own exact-head CI and independent audit.

The first independent AN-001 audit returned `NO_GO` and identified validation
gaps in revision binding, effective authorization, gate applicability, human
approval evidence, sharing allowlists, delegation, scope resolution,
revocation representation, duplicate-key parsing, documentation, and test
adequacy. The uncommitted remediation candidate adds fail-closed enforcement
and behavior-oriented regressions for those findings. This paragraph records
remediation scope, not security assurance or independent acceptance.

Installed-wheel no-network observation, complete local validation, hosted
exact-head CI, Linux real-symlink coverage, and a second independent audit
remain explicit gates. No merge, release, publication, deployment, or runtime
authority is inferred from implementation or local test results.

Status: **historical security evidence plus containing-commit residual
remediation; external final-head verification required.**

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

## Security Invariants

| Boundary | Current enforcement |
|---|---|
| Filesystem | lexical remote/device rejection; independent trust root; unresolved ancestor inspection before existence, resolution, discovery, or reads; containment and bounded strict input |
| Pack identity and locks | one profile/module namespace; collision-safe construction; strict UTF-8/JSON/schema/set/hash verification; all lock failures use governance exit 2 |
| Approval authority | source-derived canonical identity; string-only authority metadata; intrinsic non-human rejection; intersecting eligibility; exact revision/scope/expiry; bounded verifiable composition |
| Evidence | local contained artifacts; hash, revision, freshness, dependency and passing-chain verification; stale/forged references fail closed |
| Structural governance | SOD actors are non-empty human identities joined to changes, evidence and gates; high-risk self-approval fails; exception interval, overlap, expiry, closure and renewal rules fail closed |
| Schema safety | reviewed local schemas only; bounded keyword subset; complete local-reference target/cycle checks; no remote schemas or pack-supplied validators |
| Execution | governance inspection has no network, subprocess, connector, dynamic Python, automatic approval, deployment, publication or remediation surface |
| Packaging | installation clears network configuration and uses only the local wheel with `--no-index`/`--no-deps`; a separately self-tested product observer rejects network-family construction, TCP, UDP, `sendto`, conditional `sendmsg`, DNS and `create_connection`, while product `network_used` derives from an uncontaminated attempt log |

## Adversarial Coverage

The AUD suites exercise dangling/live symlinks, inaccessible and wrong-type
components, UNC/device strings without filesystem probes, cross-kind identity
permutations, forged locks, duplicate keys, malformed encodings, forged
normalized/effective approvals, authority coercion, revision conflicts,
high-risk role smuggling, SOD overlap, stale/forged evidence, exception renewal
and overlap, schema reference cycles, governed-package differential behavior,
public API consumers, checkout conversion, installed resources, and CLI
text/JSON exit codes. Residual coverage adds the complete DOS-device alias
matrix across governed-package/scanner sources, outputs, embedded evidence and
discovered artifacts, plus executable network-observer tests for low-level DNS
and cached socket-method bypasses. Those corrections are bound to `1319613`
and require external final-head validation with this record.

## Residual Risk and Authorization

Hashes bind bytes, not truth or author intent. Human identity authentication,
evidence quality, dependency maintenance, and final release authorization
remain external responsibilities. Prompt-like prose remains inert data.

The historical thread-aware query for PR #30 returned zero review threads, and
the PR remains draft. Historical run `29373272295` succeeded on `3a0e840` but
does not validate the containing commit. External exact-head CI and independent
audit must bind that commit before this assurance may be treated as current.
No merge, tag, release, publication, or deployment is authorized.
