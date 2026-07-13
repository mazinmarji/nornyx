# Nornyx Governance Program Release Candidate

## Candidate

- Package version: `1.5.2`
- Baseline main: `95952226999327458c6fea81cb32d82539bcae5b`
- Candidate commit: `16f8eb350e61966d37000f34b8ebdd720aa741af`
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
| Linux CI | run `29259022794`, `531 passed` |
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

Release-readiness, RC-stabilization, and stable-language checks report zero
blockers and intentionally remain pending human approval.

## Residual Maintenance

- Convert setuptools license metadata to SPDX form before 2027-02-18.
- Upgrade GitHub action majors that still target Node 20 when supported.

Both are Low, nonblocking maintenance observations in report 22.

## Approval Record

Human release approval: **not yet recorded**.

This candidate does not authorize merging PR #30, tagging, PyPI publication,
deployment, promotion, or any operational action. Those actions require an
explicit human decision after review of the ADRs, schemas, module semantics,
compatibility evidence, security report, and final audit.
