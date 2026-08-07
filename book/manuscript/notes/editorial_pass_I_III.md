# Editorial Verification Pass — Parts I–III (ch01–ch15)

Stage 5 editorial pass, 2026-08-03. Scope: `ch01`–`ch15` only. Binding references:
`design/01_book_design.md`, `02_style_guide.md`, `03_case_study_bible.md`,
`04_visual_language.md`, `05_bibliography.md`.

All checks below were run mechanically (scripted scans over every chapter) plus a full
read of all fifteen chapters. Edits were surgical; no technical claim, chapter scope, or
word count was materially changed.

---

## 1. Canonical decisions (BINDING on later chapters)

### 1.1 The eight questions — canonical wording (Chapter 3, §3.4)

Chapter 3's phrasing is canonical and deliberately deviates from the book-design sketch in
two places (Q3 uses "supports", not "proves"; Q7 avoids the term "assurance tier"):

1. **What exactly is guaranteed?**
2. **Which component enforces it?**
3. **What evidence supports it?** (never "proves" — supplied evidence supports, it does not prove)
4. **What assumptions are required?**
5. **How can it be bypassed?**
6. **What happens when the enforcing component fails?**
7. **What level of independence does the claim rest on?**
8. **What remains unproven?**

Later chapters referring to individual questions must use this wording. Chapter 13's
Table 13.1 was brought into line (four row labels corrected — see §3 below). Chapter 15's
quotation of Q6 already matched.

### 1.2 Case-study facts decided in this pass

- **`treasury-data` never-share list (Thread C / Ledger)** — canonical per the bible:
  `[account_credentials, full_pan]`. Chapter 6 had silently extended it with
  `credentials, secrets`; those entries were removed from Listing 6.1 and Figure 6.2 was
  re-keyed to `account_credentials`. Rationale: the four global sensitive categories
  (`secrets`, `credentials`, `tokens`, `private_memory`) are enforced by the toolchain
  code regardless of zone declarations (stated in ch06 §6.3's Nornyx-in-practice callout),
  so the zone-level list stays exactly as the bible declares it. Later chapters (12, 31,
  34) must use the two-entry list for the declared zone and may cite the four global
  categories as toolchain-level protection.
- **`9f3c1a7` is reserved for Thread B (Forge)** — it is the head-commit revision of the
  Forge stale-approval scene (ch09) and the merge-approval revision cited by ch29. Two
  collisions inside my range were removed:
  - ch03's supplier-package scenario now uses contract revision **`7a41c9e`** (3 places).
  - ch04 Listing 4.1 (a Forge described request) now uses policy revision **`c81d2f4`**,
    mission `m-2026-06-18-002`, sequence 4 — previously it duplicated ch03's mission id /
    sequence and reused `9f3c1a7` as a *policy* revision, conflating policy revision with
    subject commit.
  - ch13 Listing 13.1 (support-network contract) now uses **`git:feedfacefeed…`**,
    matching the support-network example's canonical subject revision as shown in ch09
    Listing 9.1 and ch12 Listing 12.1 (`git:feedface…`).
- **Atlas contract revision** — ch11 binds Atlas's research-network contract to
  `git:9f3c1a7…`, and **ch36 depends on this** (uses the full form
  `git:9f3c1a7d0b2e4f6a8c1d3e5f7a9b1c3d5e7f9a0b` throughout its worked audit). This
  ALSO collides with the bible's Forge reservation, but I did **not** change it, because
  fixing it properly requires editing ch36, which is outside this pass's range. **Flagged
  for a global decision** (see §9). Until then: `9f3c1a7` (bare, 7-hex) = Forge commit;
  `git:9f3c1a7d0b2…` (full form) = Atlas contract revision.
- **New thread details introduced by Parts I–III that later chapters may rely on**
  (additions, not contradictions — now canonical):
  - Thread A: Atlas identity record fields per ch05 Listing 5.1 (`identity_class:
    local_agent`, `valid 2026-02-01 → 2026-12-01`, bindings `crewai:atlas`,
    `contract_fixture:atlas`).
  - Thread B: Forge identity `northstar.engineering/forge`; merge capability `repo.merge`;
    24-hour approval expiry with `revision_change` invalidation (ch09).
  - Thread C: agent namespace `northstar.treasury`; zone `vendor-portal` (external,
    ingress-only content) added by ch06; analyst capabilities `treasury.read_exposure`,
    `treasury.compute_exposure`; membership id `membership.analyst.treasury-data`,
    valid 2026-03-01 → 2026-09-01; egress gate `gate.exposure_release`; the two
    €50,000 records / occurrence `adj.1`–`adj.2` scene in ch12 (mission `CASE-4471`).
  - Thread D: refund approval threshold **€500** (ch14 opening); the four-path comparison
    (native / wrapped / bypass / gateway) fixed by ch13 Fig 13.2 and ch14 Fig 14.1;
    benchmark scenario names S15, S18 as declared non-wins (ch15).
  - Thread A policy: `partner_disclosure_approval` is the named approval for the
    partner-share `approval_required` outcome (ch07 Listing 7.1).
  - Exception register: `EXC-PAY-014` for incident INC-2291 (ch09 Listing 9.2).
- **Tier short names** — canonical per style guide: Tier 1 design-time / Tier 2
  cooperative runtime / Tier 3 independent enforcement. Ch13's figure and table labels
  "Tier 3 — Independent" normalized to "Tier 3 — Independent enforcement".

---

## 2. Change classes with counts

| # | Class | Fixes applied | Files touched |
|---|---|---|---|
| 1 | Continuity vs case bible (never-share list, SHA collisions, mission-id collision) | 8 edits | ch03 (3), ch04 (1 listing), ch06 (2), ch13 (1) |
| 2 | Terminology (tier labels, decision-domain hyphenation, evidence-not-proof) | 5 edits | ch04 (2), ch11 (1), ch13 (2) |
| 3 | Eight-question wording alignment | 4 row labels + 1 row's cells rewritten | ch13 Table 13.1 |
| 4 | Cross-references | 0 wrong numbers found (all ~120 "Chapter N" references verified against the part/chapter structure; all Prerequisites lists cite only earlier chapters and match their content) | — |
| 5 | Numbering & markup (missing body references to figures/tables/listings) | 7 references added | ch08 (Table 8.1), ch12 (Fig 12.3, Listing 12.2), ch13 (Fig 13.1, Listing 13.1), ch15 (Fig 15.1, Fig 15.3) |
| 6 | Repetition/transitions (proof-boundary anchor) | 1 anchor sentence added | ch11 §11.4 |
| 7 | Status discipline (Nornyx statements without prose status qualifier) | 5 qualifiers added | ch15 §§15.4–15.5 |
| 8 | House style (marketing adjective, abbreviation expansion at first use) | 8 edits | ch04 (RBAC/ABAC), ch06 (LLM), ch08 (CI), ch09 (RBAC), ch10 (IAM, AAA, "most robust"), ch12 (CI), ch13 (CI) |

Total: 38 discrete edits across 11 chapter files (ch01, ch02, ch05, ch07, ch14 required
no changes). All verifications re-run clean after editing.

## 3. Detail per class

### Continuity (class 1)
- ch06 Listing 6.1: `never_share: [account_credentials, full_pan, credentials, secrets]`
  → `[account_credentials, full_pan]` (bible canonical; see decision 1.2).
- ch06 Figure 6.2: injected-instruction denial re-keyed from `credentials` to
  `account_credentials` (matches both the zone's declared list and the scene's own text,
  "email the account credentials").
- ch03: supplier scenario revision `9f3c1a7` → `7a41c9e` (3 occurrences).
- ch04 Listing 4.1: mission/sequence/revision de-collided (see 1.2).
- ch13 Listing 13.1: support-network revision `git:9f3c1a7` → `git:feedfacefeed…`.
- Verified consistent throughout: all Thread A capability strings
  (`research.search_approved`, `research.summarize`, `research.file_internal`,
  denied `publish_external`, `purchase.*`), zone names (`research-internal`,
  `public-web`, `treasury-plan`, `treasury-data`, `payment-exec`, `audit-store`),
  Ledger role split (`payment.draft` vs `payment.approve`), amounts (EUR throughout,
  €50,000 escalation), `northstar/payments-api`, `northstar-governance`, protected paths
  (`auth/`, `crypto/`, CI workflows), maker–checker phrasing, CrewAI `==1.15.4` /
  LangGraph `==1.2.2` pins.

### Terminology (class 2)
- Canonical "independent (mandatory) enforcement" appears at first substantive use in
  ch02 §2.5 and ch10 §10.3; "authoritative" is glossed exactly once, at its first
  enforcement-sense use (ch04 §4.4: "also called authoritative or mandatory
  enforcement"). No stray "authoritative enforcement" elsewhere (other uses of
  "authoritative" are the unrelated senses: authoritative representation/artifact).
- `.nyx` documents are called "contract" everywhere; no "script"/"config" misuse found.
- "Evidence" is never called "proof" for supplied evidence. One violation fixed (ch11
  opening scenario "Retrieving proof" → "Retrieving the evidence"). Remaining "proves"
  instances are legitimate: quoted repository limitation strings ("proves conformance of
  supplied records only"), ch03's category-error example (mentioned to be refuted), and
  ch14's overclaim table (left column is the overclaim being corrected).
- PDP/PEP expanded at first use in every chapter that uses the abbreviations (ch04, ch05,
  ch06, ch07, ch10, ch14 verified).
- ch04 Fig 4.2: "approval required" → "approval-required" (matches ch07's canonical
  three-valued decision domain).

### Eight questions (class 3)
Ch13 Table 13.1 row labels corrected: "What is guaranteed?" → "What exactly is
guaranteed?"; "What evidence proves it?" → "What evidence supports it?"; "How is it
bypassed?" → "How can it be bypassed?"; "What if the enforcing component fails?" → "What
happens when the enforcing component fails?"; "Which claims does it support?" → "What
level of independence does the claim rest on?" (cells reworded to answer independence
while preserving the per-tier claim sentences).

### Cross-references (class 4)
All "Chapter N" references in ch01–ch15 verified against the book design's structure,
including thread-return pointers (A → 5, 7, 10, 11, 20, 36; B → 2, 9, 15, 29, 30;
C → 12, 31, 34; D → 22–25, 26, 14; E → 32, 37) and topical pointers (28 authoring
friction, 33 degraded operation, 39 claim register). No wrong numbers. Prerequisites
lists all point backwards and accurately describe the cited chapters. (ch07's and ch11's
prerequisite callouts each contain one clearly-marked *forward* pointer — "Chapter 10 is
about who obeys it", "Chapter 12 develops the integrity machinery" — which are scope
notes, not prerequisites; left as-is.)

### Numbering and markup (class 5)
- Figures/tables/listings: all numbered `<ch>.<n>` sequentially from 1; no gaps or
  duplicates in any chapter. Seven items lacked any body-text reference; a referencing
  sentence was added for each (list in §2 table). All captions match the style guide's
  exact forms (`**Listing X.Y — Title.** caption`, `**Table X.Y — Title.** caption`,
  `<figcaption><b>Figure X.Y — Title.</b> caption`); DOT figures all carry the required
  `// fig=` comment with matching numbers.
- All `<span class="ix" ...>` spans: single-line, well-formed, balanced; 12–24 per
  chapter (within the 10–25 target).
- Callout labels: only the sanctioned set appears (incl. `Case study — <Thread>` with
  correct thread names).
- Citations: every `[@key]` in ch01–ch15 resolves to `05_bibliography.md`. (An early scan
  false-positived on line-wrapped multi-key citations; the corrected whole-file scan
  confirms zero invalid keys, so nothing was replaced or removed.)

### Repetition and transitions (class 6)
- The proof boundary is established in ch03 (§3.3 + Assurance boundary) and thereafter
  *used* with cross-references rather than re-derived: ch12 already anchors to "Chapter
  11's omission problem"; ch13 §13.3 already compresses it to a clause plus references to
  Chapters 11 and 12. The one section developing it at length, ch11 §11.4, is that
  chapter's assigned deep treatment per the book design (producers and trust) — not
  redundant — but it opened without acknowledging ch03; one anchor sentence added. No
  trimming beyond that was warranted; nothing rises to the near-identical restatement the
  Stage 1 diagnosis found in the old draft.
- Tier definitions appear exactly twice by design (ch04 preview — assigned by the book
  design — and ch13 formalization); ch10/ch14 use without redefining. Drift types are
  defined once (ch02) and referenced elsewhere. PDP/PEP defined once (ch04); ch10 §10.1
  re-expands per the per-chapter abbreviation rule and explicitly says "Chapter 4
  introduced these names."
- Chapter openings: every chapter from ch02 onward connects to prior material through its
  opening scenario (continuing threads) and/or its Prerequisites callout; none starts
  cold.

### Status discipline (class 7)
- No inline badges (`**[implemented]**` etc.) in ch01–ch15 (they correctly begin at
  ch16). All "Nornyx in practice" and "Assurance boundary" callouts carry prose status
  wording ("as implemented at the snapshot", "in the repository at the book's snapshot",
  "an architectural extension beyond the current repository"). Five bare Nornyx behavior
  statements in ch15 §§15.4–15.5 lacked a qualifier; qualifiers added.
- Extension-status material is correctly framed: ch08/ch13/ch14 label the hierarchy
  engine and the mandatory-gateway path "an architectural extension beyond the current
  repository" at point of use.

### House style (class 8)
- "most robust" (praise) removed from ch10 §10.2 ("oldest and most widely deployed").
  ch05's "more powerful than its source" retained (descriptive: authority strength, not
  praise). No other marketing adjectives found.
- "the reader": at most 4 uses per chapter (ch13), within the ~1-per-2-pages allowance;
  no edits needed.
- Abbreviations expanded at first use per chapter: RBAC/ABAC (ch04 table, ch09), LLM
  (ch06), CI (ch08, ch12, ch13), IAM (ch10), AAA (ch10). HTTP left unexpanded in a ch04
  table cell (assumed-background per the book design; ch10 expands it where it is
  load-bearing).
- Telecom analogy appears only in its two sanctioned Part I–III chapters (ch02 §2.5,
  ch10 §10.6), each with explicit limits stated.

---

## 9. Flagged, not fixed (requires decisions or edits outside ch01–ch15)

1. **`9f3c1a7` overload across threads.** The bible reserves `9f3c1a7` for the Forge
   stale-approval scene, but ch11 (in range) and ch36 (out of range) bind Atlas's
   research-network contract to `git:9f3c1a7…` / `git:9f3c1a7d0b2e4f6a8c1d3e5f7a9b1c3d5e7f9a0b`.
   Changing ch11 alone would orphan ch36's worked audit, so both were left consistent
   with each other. Recommend a Stage-6 decision: either amend the bible to record the
   Atlas contract revision explicitly, or re-key ch11 + ch36 together to a distinct SHA.
   ch24 also uses `task-9f3c1a7` as a LangGraph occurrence id — a third, unrelated reuse
   worth normalizing at the same time.
2. **ch03 supplier scenario uses the `TreasuryOfficer` role and a refund agent** — echoes
   Thread C/D vocabulary inside an anonymous-vendor demonstration. Deliberate
   foreshadowing or coincidence; harmless, but if Stage 6 wants the supplier package
   fully generic, rename the role there.
3. **ch06 "four agents divide the work" vs Figure 6.1's five agent nodes** — the
   audit-recorder is not one of the four who "divide the work" but is drawn in the zone
   figure and counted in its caption ("all five agents"). Internally explicable; noted in
   case a reviewer trips on it.
4. **Thread-detail additions now canonical** (see §1.2 list): later-chapter writers must
   treat ch05/ch06/ch07/ch09/ch12/ch14 additions (identity fields, vendor-portal zone,
   membership validity windows, `partner_disclosure_approval`, €500 refund threshold,
   `EXC-PAY-014`) as binding, or the bible should be updated to absorb them.
5. **ch16+ not in scope**: `**[implemented]**` badges begin at ch16 as designed; not
   audited in this pass.
