# 19 - Backward Compatibility Report

Status: **remediated locally and ready for an exact-head independent audit.**

This report applies to the candidate selected by the checked-out `HEAD`, based
on `95952226999327458c6fea81cb32d82539bcae5b`. The audited failing candidate
was `35ee69359599af7887f6b9b58ae0a4cd06a48d25`; its earlier compatibility
claims are historical and are not reused as evidence.
The remediated implementation through Stage 6 is
`6c0732c1be916a802e20bffce6eabf4bd7309703`.

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
accepted. A hosted Linux CI run for this local head is not claimed: PR #30 is
still at the old remote head because pushing is outside this remediation's
authorization. Hosted CI is pending. Local Windows and Ubuntu/WSL results are
recorded in report 22.
