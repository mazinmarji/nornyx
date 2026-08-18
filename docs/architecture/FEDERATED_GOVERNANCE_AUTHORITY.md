# Federated Governance Authority

## Status

Architectural doctrine and future-compatibility constraint. This document does not create a current implementation milestone, regulatory claim, certification claim, or runtime enforcement responsibility.

## Principle

Nornyx assumes that governance authority may originate from multiple independently controlled scopes, including organizational, sectoral, jurisdictional, national, regional, and international sources.

Nornyx does **not** constitute, replace, or impersonate those authorities. Its role is to provide a neutral, portable, deterministic, machine-verifiable representation of governance requirements and the evidence needed to reason about their composition.

The durable architectural objective is to preserve the ability to represent and verify governance that is:

- hierarchical;
- federated;
- jurisdictional;
- externally owned;
- provenance-bound;
- time-bounded;
- conflict-aware;
- evidence-producing.

## Authority remains external

A Nornyx contract may describe requirements derived from an external authority, but the existence of that contract does not make Nornyx the source of the authority.

Examples of possible authority sources include:

- an organization or board;
- a business unit or delegated approver;
- a sector regulator;
- a national authority;
- a regional regulatory regime;
- an international agreement or standards-based governance source.

Nornyx must preserve the distinction between:

1. **authority source** — who or what legitimately issued the requirement;
2. **governance representation** — how that requirement is encoded or referenced;
3. **resolution** — how applicable requirements are composed, compared, or surfaced;
4. **enforcement** — what an external policy enforcement point or runtime actually blocks or permits;
5. **evidence** — what proves which requirement, revision, decision, and enforcement path were involved.

## Future-compatible concepts

The language and surrounding schemas should avoid design choices that would prevent later support for concepts such as:

- `authority` — issuer or governing source;
- `jurisdiction` — geographic or legal scope;
- `scope` — organization, sector, workload, agent, action, resource, or other bounded applicability;
- `provenance` — origin and derivation of a rule or governance artifact;
- `precedence` — explicit ordering or higher-authority relationship;
- `delegation` — bounded transfer of authority;
- `effective_from` / `expires_at` — temporal applicability;
- `supersedes` — replacement of an earlier revision;
- `conflict` — incompatible applicable requirements;
- `evidence_requirement` — evidence required to support a governance decision or compliance assertion.

This list is architectural vocabulary, not a promise that each field or construct will be added to the current language.

## Composition model

A future governed action may be subject to several simultaneously applicable governance sources, for example:

```text
International / standards-based requirement
                  +
Regional requirement
                  +
National requirement
                  +
Sector requirement
                  +
Organizational policy
                  +
Application / mission contract
                  =
Resolved governance context for the action
```

A correct system must not silently convert lower-level permission into higher-level authority. Where applicable requirements conflict, the result should be explicit, attributable, and evidence-bound rather than guessed.

## Federated, not centralized

This doctrine does not imply a universal Nornyx server or a centralized global policy authority.

A preferred long-term model is federated:

```text
External governance sources
        |
        v
representation / import / mapping
        |
        v
Nornyx contract + provenance
        |
        v
bounded resolution / validation
        |
        v
external PEPs / runtimes / platforms
        |
        v
evidence
```

Governance issuers retain ownership of their authority. Nornyx provides common semantics and evidence boundaries.

## Non-goals

This doctrine does not mean that Nornyx currently:

- interprets law;
- determines legal jurisdiction;
- certifies compliance;
- publishes sovereign policy packs;
- operates a regulator feed;
- resolves every cross-border legal conflict;
- verifies that a claimed regulator artifact is authentic unless an explicit verification mechanism exists;
- performs runtime enforcement;
- replaces OPA, Cedar, IAM, API gateways, cloud controls, or other policy enforcement points.

## Adoption-gated research directions

The following are intentionally future research areas and require explicit evidence and ADR approval before becoming implementation commitments:

- jurisdiction-aware governance composition;
- signed external authority artifacts;
- national or regional governance profiles;
- regulator or standards-body policy interchange;
- cross-jurisdiction conflict reporting;
- machine-readable governance feeds;
- portable evidence for externally issued governance requirements.

Candidate shorthand such as `NX-UAE`, `NX-EU`, or similar jurisdiction-specific profiles must not be treated as current products, supported specifications, or official mappings unless separately designed, sourced, reviewed, and approved.

## Architectural constraint

> Governance authority is externally owned and may be hierarchical, federated, and jurisdictional. Nornyx should make applicable governance representable, composable, portable, provenance-bound, machine-verifiable, and evidentiary without becoming the governing authority itself.

This principle should guide future interoperability and standards work while preserving the current Nornyx boundary as a contract, validation, and evidence layer rather than an execution runtime.
