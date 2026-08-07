# Chapter 4 notes — "Core Concepts and Vocabulary"

## Status

Draft complete. Prose word count 4,773 (excludes fenced blocks and HTML figures; includes tables and
captions) — inside the 3,800–5,000 band. Structure: 3 figures (4.1 flow-col lifecycle, 4.2 seq
diagram, 4.3 zones ecosystem-positioning), 2 comparison tables, 1 listing, 19 index spans. Callouts
used: Key idea, Misconception, Design checkpoint. No `Case study` callout: Chapter 4 is assigned no
thread, and the opening scenario uses Northstar's architecture review board without advancing any of
the five threads.

The required ecosystem-positioning figure (visual-language inventory assigns it to Chapters 4 and 16)
is Figure 4.3, arranged by distance from the proposed action rather than by vendor category, so that
Chapter 16 can reuse the same bands for the system-context diagram without duplicating the layout.

## Nornyx-specific claims made

**None.** The chapter contains no assertion about Nornyx behavior at all, and says so in its
Prerequisites callout ("No Nornyx knowledge is required or used"). All twelve technology families are
described from the canonical bibliography. This is deliberate: the chapter's job is the neutral map,
and introducing the product into the comparison would compromise the neutrality the style guide
requires for named-technology comparisons.

Consequently there is nothing in this chapter needing a status label, and no fact-pack dependency.

## Assurance tiers — preview scope

Tiers are previewed only as far as Section 4.4 needs them: Tier 1 design-time, Tier 2 cooperative
runtime, Tier 3 independent enforcement, each with a one-line statement of what it claims about an
adversary. The text explicitly defers formalization to Chapter 13 and the coverage/bypass analysis
that makes a tier claim testable to Chapter 14. The Misconception box ("Tier 3 is simply Tier 2 done
properly") is the one substantive addition beyond naming, and it makes only the architectural point
that a tier is a property of position rather than code quality — no repository claim.

## Terminology deviation to flag

My task message says "cooperative vs **authoritative** enforcement". The style guide's canonical
terminology list says "cooperative enforcement · **independent (mandatory) enforcement**". I used the
canonical form as the primary term and glossed the alternative once — "also called authoritative or
mandatory enforcement" — so both vocabularies are searchable and the canonical one is the one that
propagates. If the editor prefers "authoritative" as primary, it is a single-sentence change here,
but Chapters 8 and 10 would need to match.

## Claims I could NOT verify (and what I wrote instead)

- **Maturity column values in Tables 4.1 and 4.2.** These are qualitative editorial judgments
  ("very high", "high", "moderate; fast-moving"), not measurements, and no bibliography source rates
  category maturity. They are stated as a column of a descriptive table with a caption that frames
  the whole table as "descriptive, not competitive". If the editor considers unsourced maturity
  ratings a claim-discipline risk, the column can be dropped without harming either table — the
  load-bearing columns are "unit of abstraction" and "enforcement point", which are sourced.
- **"Three of the eight have no enforcement point at all"** (Table 4.2 caption). This is an arithmetic
  reading of my own table (model safety, observability, compliance platforms), not an external claim.
  It is true of the table as written.
- **Rego and Cedar as "widely realized" instances of policy-as-code.** `opa` and `cedar` document the
  languages; neither documents adoption. Written as a statement about what the languages are, with
  the adoption word doing no work in the argument.
- **Cedar's formal analyzability.** Supported by `cedar` (the OOPSLA paper's central claim). Stated
  narrowly as "adding formal analyzability" rather than as a comparative advantage over OPA.
- **Whether an HTTP request to a payments API "carries no notion of which mission it belongs to."**
  This is a statement about the HTTP abstraction, not about any product; written as such. A specific
  gateway could of course be configured to carry such a header — the sentence's point is that the
  abstraction does not supply it, and the surrounding paragraph makes the constructive version of
  that argument (the governance layer produces the descriptions a gateway can enforce on).
- **Listing 4.1 field names.** Entirely invented for readability and captioned "Illustrative — not
  drawn from the repository; field names are chosen for readability rather than to match any
  implementation." It deliberately does *not* use real Nornyx schema field names, so that no reader
  mistakes it for a contract fragment four chapters before contracts are introduced.

## PROPOSED-REF

- `PROPOSED-REF:` a source for the "AI gateway" product category, which has no entry in the canonical
  bibliography. The row in Table 4.2 is therefore described generically (model API request routing,
  key and cost management, rate limits) and carries no citation, unlike every other row. If the
  editor wants the row sourced, a reference is needed; alternatively the row could be merged into the
  guardrails row, which is cited only by Chapter 2's argument and likewise has no primary source.
- `PROPOSED-REF:` a source for "compliance-management platforms" as a category, for the same reason.
  Currently uncited and described only by what it does. `soc2` is in the bibliography but describes
  the criteria such platforms track, not the platform category, so I did not cite it there.

## Repository paths I personally verified for this chapter

None — by design, since the chapter makes no repository claim. The design documents and bibliography
read for this chapter were `01_book_design.md`, `02_style_guide.md`, `03_case_study_bible.md`,
`04_visual_language.md`, and `05_bibliography.md`.

## Continuity notes for later writers

- Definitions established here and not to be re-derived: policy-as-code, governance-as-code, control
  as executable contract (the four elements: precise terms, evaluation procedure, failure behavior,
  evidence obligation), design-time vs runtime governance, PDP, PEP, evaluation vs enforcement,
  evidence vs assurance, cooperative vs independent enforcement, assurance tiers 1/2/3 (preview).
- Preview definitions given for agent identity, capability, trust zone, delegation, approval, each
  with an explicit forward pointer (Chapters 5, 5, 6, 5/31, 9). Those chapters should treat this as a
  one-sentence recap they may assume, and give the full definition.
- Figure 4.2's evaluate → record → execute ordering is introduced here as a *design commitment*
  (record before execute, so a crash leaves a decision without an action rather than an action
  without a decision). Chapters 20 and 22 should build on this framing; the repository's `enforce()`
  ordering guarantee is the natural place to ground it, but I did not cite it here because the
  chapter is product-neutral.
- Section 4.6's closing paragraph promises that Chapter 26 "returns to this table" to show the
  projection onto gateways, meshes, and platform policy engines. Chapter 26's author should honor
  that forward reference explicitly.
- The twelve families and their band placement in Figure 4.3 are the book's positioning baseline;
  Chapter 16 should reuse rather than re-derive them.
