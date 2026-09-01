# The `.nyx` Format and Nornyx Conformance Claims

**Authoritative** for what makes a document a Nornyx governance contract, and
for what each Nornyx conformance claim requires. Decision record:
[ADR-0045](decisions/ADR-0045-project-identity-conformance-and-provenance.md).
For who may use the project's *name*, see [`../TRADEMARKS.md`](../TRADEMARKS.md).
For whether an artifact came from this project, see
[`PROVENANCE_AND_RELEASE_VERIFICATION.md`](PROVENANCE_AND_RELEASE_VERIFICATION.md).

## 1. `.nyx` is canonical by definition, not by restriction

`.nyx` is the canonical file extension for Nornyx governance contracts.

That is a statement about what this project's own format is called. It is
explicitly **not** a claim that anyone else is forbidden to name a file `.nyx`.
Nornyx asserts no legal monopoly over a file extension, and the parser does not
gate on the extension — `nornyx check` will read a contract whatever it is
named, and that will not change.

The useful definition runs the other way around:

> A document is a **Nornyx governance contract** when it validates against a
> published Nornyx language/schema target and honors that target's canonical
> semantics.

Note what that does *not* say. It does not say the document declares its own
language/schema version. It cannot — the in-document `nornyx:` marker is a
different axis entirely, and [§2](#2-which-version-axis-scopes-conformance)
sets out why conflating the two would misdescribe every contract in the
repository.

Under that definition, a fork is free to mint `.abc` and change whatever it
likes. What it cannot accurately do is call a format with divergent semantics a
Nornyx contract. The claim is what is checkable; the filename never was.

## 2. Which version axis scopes conformance

Nornyx moves several version axes independently, and a conformance claim that
names the wrong one is unfalsifiable. The two that matter here:

| Axis | Value | Where it is recorded | Set by |
| --- | --- | --- | --- |
| **In-document version marker** | `"0.1"` or `"0.2"` | the `nornyx:` key inside the contract | the contract author |
| **Language/schema version** | `1.0` | `manifest.json` (`language_version`), `nornyx schema --version` | this project |

**A contract does not declare its language/schema version.** The v1.0 schema
accepts `nornyx: "0.1"` and `nornyx: "0.2"` and nothing else — writing
`nornyx: "1.0"` is not how a document targets 1.0, and yields the
`UNKNOWN_VERSION` warning. The flagship example
`examples/governed_delivery_control_plane.nyx` begins `nornyx: "0.1"`
while the current language/schema version is 1.0. Both statements are true at
once, and any claim vocabulary that cannot express that is wrong.

What 1.0 stabilizes is the concept set, not the marker. The marker is a
compatibility signal; the **schema target the validator applies** — `compat`,
`0.1`, `0.2`, or `1.0`, chosen by the consumer, not by the document —
is what selects the semantics a conformance claim can be checked against. An
unrecognized marker is a warning rather than an error, so the document still
checks; conformance therefore cannot rest on the marker.

```
Nornyx contract
      ↓  in-document marker ("0.1"/"0.2") — a compatibility signal
      ↓  schema target applied by the consumer (compat/0.1/0.2/1.0)
canonical .nyx representation
      ↓  canonicalization (nornyx.agentic_artifacts._canonical_contract_view)
canonical semantics
      ↓  deterministic validation
Nornyx conformance
```

A **Nornyx conformance claim is scoped by the named language/schema target and
that target's canonical semantics** — not by the in-document marker, and not by
a branding field.

Scope, not identity. The target is chosen by the consumer, and the same `.nyx`
document may legitimately be evaluated against more than one supported target,
so a target cannot be what makes the document what it is. Three concepts stay
separate, and this document is careful never to let one stand in for another:

```
governed content identity   →  canonical representation, contract_digest()
                               a property of the document itself

conformance scope           →  named schema target + that target's canonical
                               semantics; selected by the consumer

official origin             →  detached provenance / attestation
                               a property of the artifact, never of the contract
```

The first of those is why identity metadata stays out of the language.
`contract_digest()` canonicalizes the whole parsed document, so any branding
block an author adopted would change that contract's governed digest and every
lock bound to it. Nornyx therefore does not put identity metadata in the
contract language, and will not. Metadata that changes a governed digest is not
metadata; it is a breaking change wearing a badge.

Where machine-readable **project and format** identity does live today —
distinct from both the governed-content identity above and the conformance
scope, and unchanged by this document:

| Surface | Identifier | Example |
| --- | --- | --- |
| JSON Schema `$id` | `https://nornyx.dev/schemas/<name>.schema.json` | `.../agentic_network_lock_v1.schema.json` |
| Payload discriminator | `nornyx.<name>.v<n>` | `nornyx.agentic_network_lock.v1` |
| Lower-status extension schemas | `nornyx.local.<name>` | extension/roadmap declaration schemas |
| Package metadata | distribution `nornyx` on PyPI | `manifest.json`, `pyproject.toml` |
| Format versions | `LOCK_FORMAT_VERSION`, `GENERATION_FORMAT_VERSION`, `RUNTIME_EVENTS_SCHEMA_VERSION` | `nornyx/agentic_artifacts.py` |

Schema `$id` tokens are permanent: a breaking change mints a new `_v2` id
rather than rewriting `_v1` in place (see [VERSIONING.md](VERSIONING.md)). A
stored lock or evidence record therefore always means what it meant when it was
produced.

### A note on the `nornyx.dev` namespace

Schema `$id` values are **opaque identifiers, not fetch targets**. Nornyx never
dereferences them: `nornyx/governance/schemas.py` loads every schema from
packaged local resources via `importlib.resources` and registers it in a local
`referencing.Registry` keyed by `$id`. No network access is involved in schema
resolution, and none will be added.

As of 2026-09-01 the `nornyx.dev` domain does not resolve in public DNS. This is
not a vulnerability in Nornyx — nothing in Nornyx fetches it — but consumers
should not build a resolver assumption on these URLs, and third-party tooling
that *does* dereference `$id` values should be configured with a local copy of
the packaged schemas rather than a network fetch. Acquiring the domain is
tracked as an external action in
[ADR-0045](decisions/ADR-0045-project-identity-conformance-and-provenance.md).

## 3. The conformance claim vocabulary

Four claims. Deliberately few, because every additional term is another thing a
reader can misunderstand and another thing nobody verifies.

Each claim states its requirement, who may assert it, how it is verified, and —
importantly — what it does not mean.

---

### `Nornyx-compatible`

**Requirement.** Consumes or produces `.nyx` contracts, or Nornyx-schema
artifacts, without necessarily implementing the full language.

**Who may assert.** Anyone, by self-assessment.

**Verification.** Self-declared. The claim is weak by construction, and is the
right claim for editors, viewers, linters, importers, and CI wrappers.

**Does not mean.** That the full language is implemented; that semantics match;
that Nornyx has reviewed anything.

---

### `Nornyx-conformant` (scoped)

**Requirement.** Implements the canonical semantics of a **named Nornyx
language/schema target** for a **named scope**, and produces the same
accept/reject decisions as the specification for that scope. The claim must
name both, e.g. *"Nornyx-conformant for language/schema target 1.0, contract
validation."*

The claimant names the target; the document does not. A claim that cites the
in-document `nornyx:` marker instead ("conformant for 0.1") names the wrong
axis and is not a claim this vocabulary defines — nor is an unscoped
"Nornyx-conformant", because nobody can check it.

**Who may assert.** Anyone, by self-assessment, provided the evidence below
exists and is published alongside the claim.

**Verification.** Deterministic and reproducible by a third party:

- validation against the packaged schema for the named target
  (`nornyx schema --version 1.0`, `schemas/nornyx_v1_0.schema.json`);
- agreement with the canonicalization and digest semantics in
  `nornyx.agentic_artifacts` where the scope covers locks or digests;
- the repository's own deterministic corpora, run against the implementation —
  see [§4](#4-what-is-executable-today).

**Does not mean.** Endorsement, certification, official origin, or that any
runtime enforced anything. It also does not imply an assurance tier: see
[ADR-0040](decisions/ADR-0040-governance-assurance-tiers.md), which is a
separate axis entirely.

---

### `Nornyx implementation`

**Requirement.** An implementation of Nornyx semantics — the reference
implementation in this repository, or an independent one.

**Who may assert.** Anyone. Independent implementations are an explicit goal of
the project, not a threat to it.

**Verification.** Same as `Nornyx-conformant` where a conformance claim is also
made. On its own the term is descriptive.

**Does not mean.** Official origin. An independent implementation is a Nornyx
implementation and is not an official Nornyx release; both facts hold at once.

---

### `Official Nornyx release`

**Requirement.** Published by this project.

**Who may assert.** This project only.

**Verification.** By provenance, not by declaration — see
[`PROVENANCE_AND_RELEASE_VERIFICATION.md`](PROVENANCE_AND_RELEASE_VERIFICATION.md).
A field asserting `official: true` is an unverified string and carries no
weight.

**Does not mean.** Conformance, correctness, or fitness for any purpose. An
official release can carry a bug; the MIT warranty disclaimer applies in full.

---

### There is no `certified` claim

The project operates **no certification authority**, issues no certification
marks, and runs no conformance-review process. No claim in this vocabulary
means "certified by Nornyx", and no one — including this project — should write
that phrase, because there is nothing behind it. If a certification programme is
ever established, it will be recorded in an ADR with a named authority, a
defined process, and an appeal path before any mark is issued.

## 4. What is executable today

Conformance is worth defining only if it can be checked. Honest inventory of
what a third party can run right now, without any Nornyx-operated service:

| Corpus | What it establishes | How to run |
| --- | --- | --- |
| The repository test suite (`pytest`) | Reference-implementation behaviour across the language, checker, generators, governance, locks, and evidence | `pytest` |
| Packaged schemas | Structural validity for a named language/schema version | `nornyx schema --version 1.0` |
| Runtime adapter conformance kit (ADR-0043) | Observed runtime behaviour of an installed adapter against named framework versions; emits `nornyx.agentic_runtime_conformance.v1` | `python -m nornyx_agentic_adapters.conformance` |
| Governance compatibility corpus | That governed outputs did not change class (byte-identical / canonical-LF / semantically equivalent / intentional migration) | `pytest tests/test_governance_compatibility_corpus.py` |
| Static adapter/connector contract report | Declared adapter and connector contract shape, with execution disabled; emits `nornyx.adapter_conformance.v0.7` | `nornyx.connector_runtime` |

Two boundaries on that table, stated plainly:

- **These corpora were built to test the reference implementation, not to
  certify third parties.** They are reusable as a conformance basis and are
  offered as one, but a purpose-built, independently runnable language
  conformance suite with a versioned corpus revision does not exist yet. It is
  future work, and until it exists a `Nornyx-conformant` claim rests on the
  claimant publishing its evidence, not on a Nornyx-issued result.
- **The adapter conformance report is not a language conformance report.** It
  answers a different question — cooperative Tier 2 runtime behaviour of
  declared wrapped surfaces — and neither substitutes for the other.

### The reporting discipline any conformance evidence must follow

Where a conformance run emits a machine-readable record, the existing repository
convention applies (see `nornyx.agentic_runtime_conformance.v1` and the
three-valued exit codes in the conformance CLI):

- distinguish **pass**, **fail**, and **unavailable/not-representable** — a run
  that could not complete must never exit `0`;
- never leave a partially written report for a consumer to read as
  authoritative;
- record the exact versions the run observed, not the versions it hoped for;
- separate **declared** coverage from **tested** coverage, so an untested
  surface cannot hide inside a passing total;
- name limitations and non-goals explicitly.

A self-declared string is never equivalent to a tested property, in any record
this project defines.

The same rule is applied to this repository's own claims:
`tests/test_identity_claims_boundary.py` scans a named list of primary
claim surfaces — the root policy and entry documents plus the authoritative
product and identity documents — rather than all documentation. The
registered-trademark symbol is checked across every tracked Markdown file; the
narrower unsupported-claim checks are scoped, and historical planning records
and the edition-pinned textbook are deliberately out of scope.

## 5. Ecosystem registration: what is available, and what is not

An extension becomes an ecosystem format partly through registration in places
other tools consult. Separated by what is actually available today. **No
external registration has been submitted, and none should be submitted without
explicit authorization from the repository owner.**

**Immediately feasible, low cost**

- **Editor language registration.** A VS Code language contribution
  (`.nyx` to a Nornyx language id) with syntax highlighting. The repository
  already ships `nornyx complete`, `nornyx symbols`, and
  `nornyx lsp-diagnostics`, so the tooling side largely exists; no editor
  extension package does.
- **GitHub Linguist.** Linguist requires evidence of real-world use — a
  meaningful number of public repositories using the extension — before
  accepting a new language. Worth revisiting once external adoption exists;
  submitting early wastes a maintainer's review and ours.
- **`.gitattributes` / editorconfig guidance** for downstream repositories
  adopting `.nyx`.

**Possible future standardization**

- **A media type.** A vendor-tree type such as `application/vnd.nornyx+yaml`
  can be registered with IANA without standards-track approval, but it should
  wait until something actually transports `.nyx` over a protocol that needs
  content negotiation. Registering a media type nothing sends is bookkeeping,
  not adoption.
- **Schema registry publication**, if a registry emerges whose identifiers do
  not conflict with the permanence rule for existing `$id` tokens.

**Not appropriate**

- **IANA standards-track registration** — there is no standards-track
  specification, and filing one would misrepresent the project's stage.
- **Claiming a reserved extension.** File extensions are not a registrable
  namespace. There is no authority to register `.nyx` with, and describing
  one as "reserved" would be false.

## 6. Why this is the shape it is

The strategic objective is that `.nyx` becomes an ecosystem format with several
implementations, not a filename used by one Python package. That objective is
better served by a specification others can implement than by a codebase others
cannot rename.

So:

- Independent implementations are welcome and are the point.
- Conformance is defined semantically and checked deterministically.
- Official origin is proven cryptographically and separately.
- Nothing here requires contacting a **Nornyx-operated** service to parse,
  check, generate, lock, or verify anything. That is the actual property, and
  it is a constraint on this design rather than an aspiration. It is not the
  same as offline operation: obtaining an artifact and its attestation
  normally means reaching a package index or forge. What must never be
  required is a service *this project* controls.

The failure mode this document is written against is not someone forking the
code. It is someone shipping divergent semantics under the Nornyx name and
nobody being able to tell.
