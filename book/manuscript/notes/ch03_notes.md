# Chapter 3 notes — "What Governance Can and Cannot Guarantee"

## Status

Draft complete. Prose word count 5,043 (excludes fenced blocks and HTML figures; includes tables and
captions) — at the top of the 3,800–5,000 band. Structure: 3 figures (3.1 layers, 3.2 tiers, 3.3
flow-col), 2 tables, 1 listing, 19 index spans. Callouts used: Key idea, Assurance boundary,
Misconception, Design checkpoint. No `Case study` callout: the case-study strategy assigns Chapter 3
no thread, so the chapter uses Northstar the organization (Risk & Audit reviewing a supplier package)
without advancing Atlas, Forge, Ledger, Gateway, or Charter.

## The eight questions — deviation to flag

The book design states question 3 as "What evidence proves it?" I wrote it as **"What evidence
supports it?"** because the style guide's terminology rule is explicit that "evidence" is never called
"proof" for supplied evidence, and Chapter 3 is the chapter that teaches exactly that distinction.
Using "proves" in the numbered display would have contradicted the chapter's own argument three
paragraphs later. All other seven questions follow the design's wording, except question 7, where the
design's "Which assurance tier does the claim support?" is rendered as "What level of independence
does the claim rest on?" with an explicit forward pointer to Chapter 4's preview and Chapter 13's
formalization — because tiers are not defined until Chapter 4 and Chapter 3 must not use undefined
vocabulary in its own recurring frame. If the editor prefers the design's literal wording, both
substitutions are one-line changes; the numbering is unaffected.

## Nornyx-specific claims made, and their support

One passage only: the `Assurance boundary` callout in Section 3.3, written in prose status form
("as implemented at the snapshot"), not with inline badges.

1. "Validated evidence proves conformance of supplied records only", "Hash validity proves content
   binding, not event truth", "Nornyx does not observe, operate, or monitor the runtime" — verified
   **verbatim** by reading `nornyx/agentic_evidence.py`, the `LIMITATIONS` tuple (lines 87–91). I
   paraphrased in running prose rather than block-quoting.
2. Embedded in every report: fact pack 02 §5.2 states `limitations` is a report field
   (`nornyx.agentic_evidence_report.v1`). I did not open the report-construction code, so I wrote
   "embeds the limitation in every report it produces" on the fact pack's authority rather than
   naming line numbers.
3. Residual risks — "evidence is supplied, not observed: omission and fabrication are outside the
   proof surface", "a cooperative producer can falsely claim a new occurrence", "structural signature
   references are not cryptographic verification; no signature verification is claimed" — verified by
   reading `docs/agentic-network/08_SECURITY_BOUNDARIES.md` (lines 39, 41, 43, 45).

Deliberate care point: because the repository states that **no signature verification is claimed**,
the worked example in Section 3.3 is framed as a general analysis of a signed record ("Illustrative —
the field names follow the shape of records used later in this book, but this instance is constructed
for analysis"), and the callout separately records that Nornyx treats `signature_ref` as a structural
reference only. The chapter never implies that the toolchain verifies signatures.

## Claims I could NOT verify (and what I wrote instead)

- **The supplier package in the opening scenario.** Entirely fictional (Northstar universe). It is
  written to be shape-accurate against the runtime-events model rather than to be a real artifact.
- **Listing 3.1 field names.** These follow the shape of the real runtime-events schema
  (`event_id`, `event_type`, `mission_id`, `sequence`, `actor_ref`, `capability_ref`, `timestamp`,
  `contract_digest`, `policy_decision`, `approval_ref`, `approver{role,actor_type}`, `output_digest`,
  `signature_ref`, `producer{type,id}` — all real field names per fact pack 02 §5.1), but the record
  is constructed and the digests are elided. Captioned "Illustrative" accordingly. I did **not**
  include `network_id`, `network_lock_digest`, or `subject_revision`, which the real schema requires
  per event; the listing is therefore not a valid instance and must not be read as one. This is
  stated in the caption as "constructed for analysis."
- **`identity.refund_agent` / `issue_refund` / `TreasuryOfficer`.** These are shaped after the
  repository's support-network example but are not canonical Northstar case-bible names, because
  Chapter 3 has no assigned thread. Ledger (Thread C) uses `payment.draft` / `payment.approve` and a
  treasury officer approver; if the editor wants convergence, this example could be renamed to
  Ledger vocabulary, but that would pull Thread C forward from Chapter 6.
- **Whether a signature "deters fabrication in an organization with consequences."** An argument, not
  a measured claim; written as a reasoned assertion with its mechanism stated, not as evidence.

## PROPOSED-REF

None. Every citation used (`schneider-enforceable`, `clark-wilson`, `merkle`, `in-toto`,
`nist-ai-rmf`) is in the canonical bibliography and is used for the claim it actually supports:
`schneider-enforceable` for what a runtime monitor can enforce at all, `merkle` for what hash-based
binding asserts, `in-toto` for another discipline's separation of attestation from truth.

## Repository paths I personally verified for this chapter

- `/home/user/nornyx/nornyx/agentic_evidence.py` (lines 85–92, the `LIMITATIONS` tuple)
- `/home/user/nornyx/docs/agentic-network/08_SECURITY_BOUNDARIES.md` (residual-risk lines 39–45)

Consulted via fact packs rather than opened directly (and therefore stated at fact-pack granularity,
without line numbers, in the chapter): `schemas/agentic_runtime_events_v1.schema.json` field set;
`nornyx.agentic_evidence_report.v1` report fields.

## Continuity notes for later writers

- The eight questions are now formally introduced with the numbering above; Chapters 5 onward should
  refer to them by number ("question 5", "question 8") without restating the list.
- Fail-open/fail-closed is introduced conceptually only. The three consequences in Section 3.6
  (availability becomes a security property; fail-closed costs work stoppage; failure behavior must
  be injection-tested) are handed forward to Chapters 10, 33, and 15 respectively.
- Section 3.7's four classes of honest guarantee (artifacts / decisions / structure / process) are a
  useful skeleton for Chapter 13's tier mapping and Chapter 39's claim register.
- The audit lead is unnamed and can be given a name by whoever writes Chapter 36 first.
