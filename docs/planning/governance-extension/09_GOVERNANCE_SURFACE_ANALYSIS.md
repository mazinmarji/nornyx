# 09 — Governance Surface Analysis (GSA) Method

Status: implemented documented method with validated advisory matrices; runtime
tooling is `not_required_after_GSA`.

A repeatable, documented method for deciding what Nornyx should govern and
where each control belongs. Inspired by STPA-style control analysis; it is a
**prioritization method, not a mathematical proof of completeness**.

## The 16 steps

1. **System boundary** — what is inside/outside the governed system; name the
   repos, artifacts, environments explicitly.
2. **Governed-object inventory** — enumerate objects (contracts, packages,
   changes, architecture elements, evidence artifacts, approvals, packs).
3. **Unacceptable losses** — e.g., "unreviewed change reaches production",
   "secret committed", "approval forged by a tool".
4. **Hazards / failure conditions** — states that enable losses.
5. **Lifecycle analysis** — create → modify → approve → release → retire for
   each object class.
6. **Actors and accountable owners** — humans and roles; every object gets an
   owner or is flagged.
7. **Authorities and delegations** — who may approve what; delegation depth
   and revocation.
8. **Actions / control actions** — what actors can do to objects.
9. **Trust boundaries** — where untrusted input enters (pack sources, package
   payloads, external evidence, README claims).
10. **Feedback paths** — how the governor learns state changed (drift gate,
    CI re-check, evidence freshness).
11. **Evidence paths** — what proves each control acted; format, producer,
    integrity binding.
12. **Unsafe/inadequate control actions** — for each control action: not
    provided / provided wrongly / wrong time / stopped too soon.
13. **Derived governance constraints** — one constraint per unsafe action.
14. **Containment and rollback** — blast-radius limits, reversibility class,
    rollback evidence.
15. **Exceptions and expiry** — legitimate relaxations, their authority,
    compensating controls, expiry.
16. **Placement decision** — each constraint lands in exactly one of:
    Core / Reusable module / Optional profile / Adapter (evidence importer) /
    External enforcement tool / Human-organizational process.
    Default bias: external tool for anything requiring code analysis or
    execution; module for cross-domain declarative constraints; profile for
    domain vocabulary; core only for universal, never-relaxable invariants.

## Governance-completeness matrix

Per governed object class, answer (matrix rows are the brief's questions):
What is governed? Why? Who owns it? Who may act? What is allowed? What is
denied? What requires approval? What proves compliance? How is stale/false
evidence detected? How is drift detected? How is failure contained? When does
authority expire? How is the object retired?

Deliverable format: one YAML matrix per profile in adjacent advisory docs,
never embedded as enforceable pack data. Stage E found no need for a
`nornyx.gsa_report.v1` schema or CLI; ADR-0031 records that runtime tooling is
`not_required_after_GSA`.

## Prioritization model (auditable, ordinal)

Score each candidate constraint 1–3 on: Impact, Likelihood, Autonomy (how
much AI/automation acts without a human), Irreversibility, Trust-boundary
exposure, Existing-control gap. Priority = documented tuple (not a summed
scalar — summing hides which factor drove the ranking). Sort
lexicographically by (Impact, Irreversibility, Trust exposure, Gap,
Likelihood, Autonomy); publish the tuple next to each decision so reviewers
can dispute individual factors. Explicitly: this ranks work, it does not prove
coverage.

## Dogfood requirement

Stage E applied the method to Nornyx itself, including the pack system as a new
trust-boundary crossing, and recorded contracts, packs, modules, governed
packages, external evidence, generated artifacts, approvals, exceptions,
changes, architecture, and release decisions in doc 18. The doc 10 threat
model remains the step-12 output for the pack system. All twelve profile
matrices are under `gsa/` and validated as advisory documents by tests.
