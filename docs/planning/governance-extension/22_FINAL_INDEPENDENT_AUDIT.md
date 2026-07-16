# 22 - Exact-Head Independent Audit Record

Status: **historical audit and residual-remediation handoff; no in-tree record
self-assigns a final candidate SHA or verdict.**

## Audit Evidence History

- Repository: `mazinmarji/nornyx`; pull request: `#30`.
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

Any earlier positive audit language is historical, superseded, and valid only
for the exact commit to which it was originally bound. It is not current
evidence for this containing commit.

## Required Evidence

The independent auditor must inspect the complete base-to-head diff and the
machine-readable `AUDIT_REMEDIATION_LEDGER.json`, reproduce all 22 original
findings, search adjacent bypass variants, inspect packaged resources, and run
or verify:

```text
python -m pytest -q
python -m ruff check .
python scripts/check-public-boundary.py --repo .
python scripts/check_compatibility_migrations.py
python -m build
python -m twine check dist/*
git diff --check 95952226999327458c6fea81cb32d82539bcae5b...HEAD
```

The audit must separately cover real Linux symlinks, the compatibility corpus,
governed examples and packages, installed-wheel resources/no-network behavior,
12 built-in profiles, 6 built-in modules, public API stability, and thread-aware
GitHub review state.

## Residual Remediation Evidence Boundary

`AUD-011-R1` extends the central host-independent device classifier to
`CONIN$`, `CONOUT$`, and superscript COM/LPT aliases, including case,
extensions, ADS suffixes, nested components, mixed separators, and trailing
dots/spaces. Before-probe tests cover parser, loaders, discovery, locks,
evidence, architecture, governed-package/scanner source and output boundaries,
embedded adapter reports, discovered artifacts, and CLI consumers.

`AUD-021-R1` replaces source-string assurance with a reusable executable guard.
Its self-test records and rejects network-family construction, TCP connect,
`connect_ex`, UDP `sendto`, conditional `sendmsg`, DNS, and
`create_connection`; low-level/legacy DNS aliases and cached socket descriptors
are audit-hook denied. Self-test and product logs are separate.

`AUD-017-R1` is implemented by the containing documentation commit using this
historical/external evidence model. `PRMETA-001` remains prepared but must not
be published unless a fresh external audit returns exactly `GO`.

## Verdict Boundary

This in-tree record does not self-authorize a verdict. The fresh auditor must
resolve the actual PR head externally, verify hosted CI is bound to that exact
SHA, independently recheck AUD-001 through AUD-022 and all four reopened items,
and publish the verdict outside this self-referential commit record. Human merge
and release authorization remain separate in every case.
