# Nornyx Governance Program Candidate Record

## Candidate

- Package version: `1.5.2`
- Baseline: `95952226999327458c6fea81cb32d82539bcae5b`
- Audited failing head: `35ee69359599af7887f6b9b58ae0a4cd06a48d25`
- Remediated implementation through Stage 6:
  `6c0732c1be916a802e20bffce6eabf4bd7309703`
- Final local candidate: clean checked-out `HEAD` containing this record
- Branch: `codex/complete-governance-program`
- PR: `https://github.com/mazinmarji/nornyx/pull/30`
- PR state: draft

This is a candidate evidence record, not a release approval. The old remote PR
head and its `NO-GO` remain visible until a separately authorized push. No
current-head hosted CI result is claimed.

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
| Focused AUD-001 through AUD-022 suites | passed locally |
| Compatibility migration proof | five migrations passed |
| Fresh `core.autocrlf=true` checkout | passed locally |
| Build and installed-wheel no-network smoke | passed locally |
| Full Windows suite | `913 passed, 45 skipped` |
| Real Linux filesystem suite | Ubuntu/WSL native clone: `958 passed` |
| Hosted Linux CI for exact local head | pending authorized push; not run |
| GitHub review threads | zero |
| Fresh independent exact-head audit | pending |
| Human candidate approval | not recorded |

## Authorization Boundary

PR #30 remains draft. Merge, release, tag, publication, and deployment are not
authorized. The earlier approval of candidate `2189bb3` was invalidated by the
blocking review and does not transfer to this candidate.
