# Issue #81 hygiene scope checklist

This checklist accompanies
`ISSUE_81_HYGIENE_SCOPE_PROPOSAL.md`.

**Proposal only. It authorizes no implementation and does not change the live
issue #81 scope.** Current Nornyx roadmap, backlog, `docs/64`, `docs/68`, and the
live GitHub issue remain controlling until a separately authorized Nornyx change
updates the relevant governing surfaces consistently.

Proposed bounded slice:

- [x] Existing first-wave frameworks only: NIST AI RMF, OWASP GenAI / Top 10 for LLM Applications, ISO/IEC 42001.
- [x] Edition/version provenance separated conceptually from clause/control/source grounding.
- [x] Human-maintained local current-edition registry model proposed.
- [x] No live network retrieval.
- [x] Existing claim types and control-surface vocabulary retained.
- [x] ADR-0040 assurance tier/surface metadata retained as the assurance dimension.
- [x] No customer-specific coverage state or compliance score.
- [x] No new framework proposed.
- [x] No private downstream platform, repository, product, or organization-specific governance names are required by the proposal.

Authority and consistency gates:

- [ ] A separate Nornyx authorization activates the bounded slice; this proposal does not.
- [ ] `docs/64`, `docs/68`, roadmap, backlog, and issue #81 are reconciled together so edition/version provenance is not active in one surface and deferred in another.
- [ ] Live issue #81 body is updated only as part of that authorized, consistent Nornyx change.
- [ ] Required Nornyx CI/checks pass on the exact activation-aligned head.
- [ ] Independent review closes any claim-boundary or public-boundary finding before merge.

Until those gates close, this branch is review material only.
