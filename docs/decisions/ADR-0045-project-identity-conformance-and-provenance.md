# ADR-0045 — Project Identity, Conformance Claims, and Artifact Provenance

- Status: Proposed (documentation and claim boundaries only; trademark
  registration, domain acquisition, and any certification authority are
  separate, owner-authorized actions)
- Date: 2026-09-01
- Decision owner: human repository owner
- Relates to: ADR-0027 (deterministic integrity and locking), ADR-0032
  (verifiable effective approvals), ADR-0035 (network artifacts and lock),
  ADR-0036 (agentic runtime event evidence), ADR-0040 (assurance tiers and
  claim boundaries), ADR-0043 (runtime adapter conformance)

## Context

Nornyx is MIT licensed and intends to stay MIT licensed. The license grants
broad rights to use, modify, redistribute, and rename the software, and
nothing in this ADR narrows them. A fork is a legitimate exercise of the
license, not an attack.

What the license does **not** settle is a separate question the repository
currently answers nowhere:

> When a third party says "this is Nornyx", "this is a `.nyx` contract", or
> "this is Nornyx-conformant", what — if anything — makes that statement
> checkable?

Four facts from the current codebase set the boundaries this ADR must encode.

1. **Content binding already exists; producer identity deliberately does
   not.** `contract_digest()`, the network lock, and the generation manifest
   bind governed *content* to an exact revision. `nornyx/agentic_artifacts.py`
   states the boundary in its own module docstring: the lock "never attests
   runtime behavior, producer identity, or truth." Producer identity is
   therefore a **detached** concern by existing design, not an omission to be
   corrected by adding fields to the lock.

2. **Adding identity metadata to `.nyx` source would move governed digests.**
   `contract_digest()` canonicalizes the whole parsed document. Any branding
   block an author adopted would change that contract's digest and every lock
   bound to it. Identity metadata therefore must not enter the contract
   language.

3. **A controlled identifier namespace already exists — on a domain the
   project does not demonstrably control.** Schema `$id` values use
   `https://nornyx.dev/schemas/...`; payload discriminators use dotted
   `nornyx.<name>.v<n>`; lower-status extension schemas use `nornyx.local`.
   As of 2026-09-01, `nornyx.dev` does not resolve in public DNS. Nornyx never
   dereferences these identifiers — `nornyx/governance/schemas.py` loads every
   schema from packaged local resources through `importlib.resources` and
   registers it by `$id` — so this is not a code-execution or supply-chain
   defect in Nornyx. It is an **identity** exposure: a third party who
   registered that domain could serve documents at Nornyx's canonical
   identifiers to any *other* tool that does dereference `$id`.

4. **Assurance tiers are not identity claims.** ADR-0040 governs how strongly
   a *system* is assured. It says nothing about whether a *distribution* is
   the project's own. The two axes are independent and must not be collapsed.

## Decision

Adopt a four-layer identity model. Each layer is independently verifiable, and
none of them restricts the MIT grant.

```
MIT software      — what anyone may use, modify, rename, and redistribute
Nornyx identity   — the names and marks that denote this project
.nyx semantics    — what makes a document a Nornyx governance contract
conformance       — whether an implementation honors those semantics
provenance        — whether an artifact came from this project
```

### 1. Identity is separated from licensing

The MIT grant covers copyright in the software. It does not, by itself, grant
rights to represent a derivative as an official Nornyx release or as endorsed
by the project. `TRADEMARKS.md` records the descriptive uses that are welcome
and the representations that are misleading. It is marked as requiring
independent counsel review before being treated as an enforcement instrument,
and it asserts no registration that does not exist.

### 2. `.nyx` is defined semantically, not by extension

`.nyx` is the canonical file extension for Nornyx governance contracts. Nornyx
does not, and will not, assert that others are forbidden to name files `.nyx`,
and the parser does not gate on the extension. What is defined is the
converse: a document is a **Nornyx governance contract** when it satisfies the
language/schema version it declares, under the canonical semantics this
project publishes. A fork is free to mint `.abc`; what it may not accurately
do is call a divergent format a Nornyx contract.

### 3. Conformance claims form a small controlled vocabulary

Four claim classes, each with a fixed evidence basis and a stated non-meaning.
Self-assessment is permitted and expected for the compatibility claims. The
project issues no certification and operates no certification authority, so no
claim in this vocabulary means "certified by Nornyx."

### 4. Provenance is detached, standards-based, and fails closed

Provenance rides on established ecosystem mechanisms — Trusted Publishing,
PEP 740 attestations, immutable commit SHAs, artifact digests — rather than a
Nornyx-invented cryptographic transport. Nornyx owns the *semantics* of what
is attested, not the transport.

Three properties are mandatory:

- **Removal is permitted and is not sabotage.** Stripping provenance leaves
  working MIT software. It removes the ability to *prove* project origin; it
  does not remove the ability to *run*.
- **Absence is distinguishable from failure.** "No provenance was supplied"
  and "provenance was supplied and did not verify" are different results and
  must never be reported as the same one.
- **A declaration is not proof.** A field asserting `official: true` is an
  unverified string. Only a mechanism whose verification a third party can
  independently reproduce may substantiate an origin claim.

### 5. Verification does not require a Nornyx service

Provenance is verified from an artifact plus public trust material plus a local
verifier. No Nornyx-operated endpoint is contacted at check time, at generation
time, or at runtime. This is a hard constraint: an identity mechanism that made
`.nyx` processing depend on project infrastructure would contradict the
vendor-neutral position in `docs/48_NORNYX_POSITIONING.md` and is rejected on
those grounds.

## Rejected alternatives

- **License change to restrict renaming or forking.** Contradicts the MIT
  commitment and would make the project source-available rather than open
  source.
- **Watermarking, anti-rename checks, or runtime origin enforcement.** These
  are DRM. They would break legitimate forks, cannot survive a determined
  reimplementation, and would embed a hidden runtime dependency in a project
  whose whole claim is deterministic, inspectable behavior.
- **An `identity:` or `provenance:` block in the `.nyx` language.** Moves
  governed digests (fact 2), pollutes the grammar with metadata carrying no
  semantics, and places a forgeable declaration inside the governed payload.
- **Producer identity inside the network lock.** Contradicts the lock's
  documented boundary (fact 1) and would make lock bytes vary by producer,
  destroying the byte-stability that makes locks reviewable.
- **A Nornyx-operated conformance or licensing service.** Central point of
  failure, contradicts offline verification, and converts a specification into
  infrastructure.
- **Claiming a registered trademark.** No registration is asserted because none
  is established. Using the registered-trademark symbol without registration is
  itself a misrepresentation in several jurisdictions.

## External actions this ADR does not perform

Some protections cannot be created by a commit. They are recorded here so the
boundary between "documented" and "obtained" stays visible, and so nothing in
this repository is mistaken for having achieved them. Each needs a decision
from the repository owner; the first is the only one with a live exposure
behind it.

| # | Action | Why | Owner |
| --- | --- | --- | --- |
| 1 | **Acquire `nornyx.dev`, or migrate the schema `$id` namespace.** | Every packaged schema `$id` points at a domain that did not resolve on 2026-09-01. Nornyx never dereferences them, so this is not a code defect — but a third party holding that domain could serve documents at Nornyx's canonical identifiers to any tool that *does* dereference `$id`. Acquiring the domain is cheap; the alternative is minting a non-URL namespace, which would break the permanence rule for existing `$id` tokens and is therefore the worse option. | repository owner |
| 2 | Trademark clearance search for "Nornyx". | Determines whether the name is available and whether anyone else holds conflicting rights. Must precede any registration or enforcement posture. | IP counsel |
| 3 | Decide whether to register, and in which jurisdictions and Nice classes. | Registration is not automatic and not free. Class 9 and class 42 are the usual candidates for software and SaaS, but scope should follow actual and intended use. | IP counsel + owner |
| 4 | Decide the owning entity. | An individual, a company, or a foundation. This choice affects enforceability, assignment, and what happens to the mark if the project changes hands. It is easier to decide before registration than after. | owner |
| 5 | Confirm ownership of `nornyx.org` and any other project domains. | `nornyx.org` resolves to a parking address; this repository does not record who controls it. Project-controlled domains are part of the identity surface. | owner |
| 6 | Review contributor IP hygiene. | The repository currently uses neither a CLA nor DCO sign-off. Adding one has real costs — contributor friction, and a CLA in particular can deter casual contribution — so it should follow from a decision about what the project needs, not from the fact that it sounds protective. This ADR makes no recommendation either way. | owner + counsel |
| 7 | Decide on signed tags and a signing-key policy. | Tag signing is a maintainer-key decision with a rotation and revocation burden. See the constraints in [`../PROVENANCE_AND_RELEASE_VERIFICATION.md`](../PROVENANCE_AND_RELEASE_VERIFICATION.md). | owner |

Nothing in this repository registers a trademark, establishes rights beyond
whatever actual use has already established, or substitutes for a legal
opinion.

## Consequences

- The repository gains a claim vocabulary it must itself obey. A regression
  test enforces this against Nornyx's own documentation, because a project that
  overclaims its own status cannot credibly describe anyone else's.
- Release provenance becomes an explicitly declared property of the publish
  workflow rather than an implicit default of a moving action reference.
- Domain acquisition and trademark clearance are surfaced as external actions
  with named owners. This ADR does not perform them and does not pretend to.
- Existing `.nyx` contracts, schemas, locks, digests, and generated artifacts
  are unchanged. This ADR adds no language surface and no runtime behavior.
