# Nornyx Governance Program Release Candidate

## Candidate

- Package version: `1.5.2`
- Baseline main: `95952226999327458c6fea81cb32d82539bcae5b`
- Candidate commit: `2189bb3e2941fb35ee46680dfe8ded2f9c8b6088`
- Branch: `codex/complete-governance-program`
- Pull request: `https://github.com/mazinmarji/nornyx/pull/30`
- Status: ready for human release review
- Independent audit: `GO`

## Included Program

The candidate adds six bounded governance modules, the shared change model,
the optional architecture-governance profile, evidence import/validation,
profile/module/governance CLI inspection, the public evidence API, all 12
profile GSA mappings, compatibility/security assurance, and final placement
decisions for every accepted candidate.

The stable Nornyx core remains unchanged. Packs are local, data-only,
deterministic, monotonic, and unable to execute tools, access networks, grant
approval, deploy, publish, or remediate.

## Release Gates

| Gate | Result |
|---|---|
| Windows full suite | `522 passed, 10 skipped` |
| Linux CI | run `29260631031`, `532 passed` |
| Ruff | pass |
| Public boundary | pass |
| Diff check | pass |
| Governed examples | pass |
| Governed-package examples | pass |
| Build | source and wheel pass |
| Twine | source and wheel pass |
| Installed wheel | 12 profiles, 6 modules, network false, pass |
| PR review threads | none |
| Independent audit | `GO` |

Approval-gated reruns report release readiness at 9 passed, RC stabilization
at 15 passed, and stable-language validation at 24 passed, with zero warnings,
blockers, or remaining approval requirements.

## Residual Maintenance

- Convert setuptools license metadata to SPDX form before 2027-02-18.
- Upgrade GitHub action majors that still target Node 20 when supported.

Both are Low, nonblocking maintenance observations in report 22.

## Approval Record

Human release-candidate approval: **recorded**.

- Date: 2026-07-13
- Approved candidate: `2189bb3e2941fb35ee46680dfe8ded2f9c8b6088`
- Scope: readiness for human release review only
- Source: explicit approval in the authoritative Codex task

This candidate does not authorize merging PR #30, tagging, PyPI publication,
deployment, promotion, or any operational action. Those actions require an
explicit human decision after review of the ADRs, schemas, module semantics,
compatibility evidence, security report, and final audit.
