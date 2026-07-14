# 20 - Security Assurance Report

Status: **AUD-001 through AUD-022 remediated locally; external exact-head audit
and hosted Linux CI remain release gates.**

The audit baseline is `95952226999327458c6fea81cb32d82539bcae5b`; the failing
candidate is `35ee69359599af7887f6b9b58ae0a4cd06a48d25`. Evidence is taken from the
current checkout, schemas, packaged mirrors, fixtures, executable tests, built
wheel, and machine-readable remediation ledger—not the prior reports.
The remediated implementation through Stage 6 is
`6c0732c1be916a802e20bffce6eabf4bd7309703`.

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
| Packaging | installed-wheel smoke clears network configuration, uses only the local wheel with `--no-index`, denies DNS/connect calls, and derives `network_used` from the observed attempt log |

## Adversarial Coverage

The AUD suites exercise dangling/live symlinks, inaccessible and wrong-type
components, UNC/device strings without filesystem probes, cross-kind identity
permutations, forged locks, duplicate keys, malformed encodings, forged
normalized/effective approvals, authority coercion, revision conflicts,
high-risk role smuggling, SOD overlap, stale/forged evidence, exception renewal
and overlap, schema reference cycles, governed-package differential behavior,
public API consumers, checkout conversion, installed resources, and CLI
text/JSON exit codes.

## Residual Risk and Authorization

Hashes bind bytes, not truth or author intent. Human identity authentication,
evidence quality, dependency maintenance, and final release authorization
remain external responsibilities. Prompt-like prose remains inert data.

The GitHub review-thread query currently returns zero threads and PR #30 is
still draft. The remote PR head remains the failing candidate, so this report
does not claim current-head hosted CI. Hosted CI is pending. No merge, tag,
release, publication, or deployment is authorized.
