# 19 - Backward Compatibility Report

Status: **historical compatibility evidence plus containing-commit residual
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

## Compatibility Contract

The machine-readable corpus is
`tests/fixtures/governance_compatibility/manifest.json`. It pins:

- all established starters and the one additive architecture starter;
- all top-level and governed-package examples;
- generated drift artifacts, locks, legacy projections, CLI output and exit
  codes;
- the base-compatible public dataclass constructor and v1 serializer surface;
- source and packaged schema behavior; and
- five intentional migrations with immutable before/after artifacts.

Each migration proof binds the complete manifest record, old and new raw
SHA-256 hashes, exact deterministic JSON-pointer operations or unified text
diff, reason, human-request metadata, and changelog marker. The verifier also
checks closed artifact inventory, ordered chains, and the current terminal
output. `python scripts/check_compatibility_migrations.py` is the executable
entry point.

## Results

| Surface | Result |
|---|---|
| Eleven established profile starters | byte-identical |
| Architecture-governance starter | additive, recorded separately |
| Governed-package 1.5.2 change domain | preserved by compatibility adapter |
| Public 1.x constructor prefixes/defaults | preserved |
| Public v1 serializers | preserved; v2/verifiable output is explicit |
| CLI semantic corpus | pinned, including five exact migrations |
| Raw hash-bound artifacts | protected by `.gitattributes` and real `core.autocrlf=true` clone test |
| Installed wheel downstream consumer | passes with 12 profiles and 6 modules |

The explain migrations are a two-step chain: declared revision/expiry fields,
then bounded verifiable effective-approval provenance. The SOD module-list and
matrix changes are recorded independently. The architecture example migration
contains one producer-identity line change preserving evidence/approval
separation.

## Release Boundary

Security hardening intentionally rejects malformed and untrusted inputs that
were never supported authority. No unapproved supported-input narrowing was
accepted. Run `29373272295` is historical evidence for `3a0e840` only and does
not transfer to the containing commit. Compatibility closure for the containing
commit must be established by external exact-head CI and a fresh independent
audit. No human or operational authorization is implied.
