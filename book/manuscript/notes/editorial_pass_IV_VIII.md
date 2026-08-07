# Editorial Verification Pass — Parts IV–VIII (ch16–ch41)

Stage 5 editorial pass, 2026-08-04. Scope: `ch16`–`ch41`, plus `ch11` (one item, mandated
de-collision) and `app_e_example_policies.md` (continuity only). Binding references:
`design/01_book_design.md`, `02_style_guide.md`, `03_case_study_bible.md`,
`04_visual_language.md`, `05_bibliography.md`, and the canonical decisions of
`notes/editorial_pass_I_III.md` §1.

All checks were run mechanically (scripted scans over every chapter in range) plus a full
read of all twenty-six chapters. Where a Nornyx behavior claim could not be confirmed from
`book/factpack/*.md`, it was verified directly against the repository source at the pinned
snapshot (`70d2b40`) rather than guessed; the handful of such verifications are listed in
§5. Edits were surgical; no technical claim, chapter scope, or teaching content was
shortened.

---

## 1. THE DE-COLLISION (mandated decision, now executed)

`9f3c1a7` is now **exclusively** the Forge stale-approval revision (Thread B). Confirmed
remaining occurrences after this pass: ch09 (4), ch29 (1), ch30 (5), ch37 (1), ch40 (1,
injection F2) — all Forge merge-lane contexts. Re-keys performed:

| Object | Old | New | Files (occurrences) |
|---|---|---|---|
| Atlas research-network contract revision, short form | `git:9f3c1a7…` | `git:4e7d21a…` | ch11 (1), ch36 (2) |
| Atlas contract revision, full form | `git:9f3c1a7d0b2e4f6a8c1d3e5f7a9b1c3d5e7f9a0b` | `git:4e7d21ad0b2e4f6a8c1d3e5f7a9b1c3d5e7f9a0b` | ch36 (4) |
| LangGraph occurrence id (ch24 worked example + Fig 24.2) | `task-9f3c1a7` | `task-3c88a1e` | ch24 (9) |
| Capstone Ledger network subject revision, full form | `git:9f3c1a7e0b4d2c8f6a1b3d5e7f9a0c2e4b6d8f01` | `git:b5e91c4e0b4d2c8f6a1b3d5e7f9a0c2e4b6d8f01` | ch40 (1) |
| Capstone Ledger revision, short form | `git:9f3c1a7…` / `git:9f3c1a7...` | `git:b5e91c4…` / `git:b5e91c4...` | ch39 (1, Listing 39.2), ch40 (3: Fig 40.2, §40.5 reconstruction, closing Assurance boundary), ch41 (1, §41.4) |
| App. E Ledger fragment revision (Listing E.10) | `git:9f3c1a70000000000000000000000000deadbeef` | `git:3b7a9d10000000000000000000000000deadbeef` | app_e (1) |

Rationale for the two identifiers this pass had to mint: ch39–41 and app_e used
`9f3c1a7`-prefixed strings for the **Ledger** contract revision — a second and third
non-Forge reuse of the reserved prefix that the previous pass's flag did not enumerate
(three distinct 40-hex strings shared the `9f3c1a7` prefix across the book). The capstone
Ledger revision is now `b5e91c4` (one full 40-hex form, used everywhere the full form
appears); the standalone App. E fragment, a *different* illustrative network, keeps its
own filler-style revision `3b7a9d1…deadbeef` so the short form `b5e91c4` remains
unambiguous. **The bible should absorb**: `4e7d21a` (Atlas contract revision),
`b5e91c4` (capstone Ledger subject revision), `task-3c88a1e` (ch24 occurrence id).
All three new 40-hex strings validated as exactly 40 lowercase hex.

## 2. Change classes with counts

| # | Class | Fixes applied | Files touched |
|---|---|---|---|
| 1 | De-collision and revision continuity (table above) | 23 identifier edits | ch11, ch24, ch36, ch39, ch40, ch41, app_e |
| 2 | Continuity vs bible/canon (other): Atlas partner-share approval name unified to canonical `partner_disclosure_approval` (was `PartnerShareApproval` in ch17/app_e, `partner_share_authority` in ch36); Thread C submission capability unified to the capstone's `payment.submit` (ch31 had `bank.submit`); `treasury-data` never-share restored to the exact two-entry list with the four global sensitive categories stated as toolchain-enforced, not zone-declared (ch31 §31.2 + Fig 31.1, ch39 §39.4 + Fig 39.2); NS-LEDGER-003 evidence mechanism corrected to `SENSITIVE_SHARING` **and** `SHARE_NOT_ALLOWED` (the former covers only the four global categories, not `account_credentials`/`full_pan`) | 25 edits | ch17 (3), ch31 (9), ch36 (8), ch39 (3), app_e (1), plus the NS-LEDGER-003 cell |
| 3 | Eight-questions wording (canonical ch03 §3.4 forms): Q3 "What evidence **supports** it" fixed in ch17, ch18, ch23 (bold restatement), ch35, ch36, ch37 (procurement questionnaire); Q5/Q6 exact forms restored in ch35; Q7 "What level of independence does the claim rest on?" restored in ch23, ch35, ch37 (was "Which assurance tier does the claim support?" / "Which tier") | 11 label corrections | ch17, ch18, ch23, ch35, ch36, ch37 |
| 4 | Evidence-never-"proof" (style guide): ch20 misconception "It is proof of four narrower things" → "It establishes four narrower things". All other "proof/proves" instances verified legitimate (quoted repository limitation strings, the sanctioned term *proof boundary*, refuted overclaims, "proof sketch" about code) | 1 edit | ch20 |
| 5 | Factual accuracy vs source: ch21 forbidden-key segment count "twenty-six" → "twenty-seven" (verified: 27 entries in `_FORBIDDEN_KEY_SEGMENTS`, matching ch34's verbatim Listing 34.1) | 1 edit | ch21 |
| 6 | Numbering & markup — items lacking any numbered body-text reference: referencing phrases added for Table 26.1, Figure 27.2, and Listings 17.4, 18.4, 18.5, 18.6, 21.2, 28.4, 32.2, 36.1, 36.2, 36.3, 36.4, 40.1, 40.2, 40.5, 40.6 | 17 references added | ch17, ch18, ch21, ch26, ch27, ch28, ch32, ch36, ch40 |
| 7 | Abbreviation expansion at first use per chapter: SPI (ch16 table, ch23, ch25, ch30, ch39, ch40), CI (ch17, ch23, ch27, ch30, ch31, ch32, ch33, ch37, ch39, ch40), IAM (ch16, ch37, ch39, ch41), PEP (ch25, ch40 expanded; ch20 figure column de-abbreviated to "enforcement point"), AAA (ch19), MCP (ch40), LLM (ch34) | 26 edits | 16 files |
| 8 | Index spans (style guide 10–25 per chapter; ch27/28/29/30 were at 9/5/6/1): definitional-site spans added — ch27 +2, ch28 +5, ch29 +5, ch30 +10. All chapters in range now hold 11–19 well-formed single-line spans | 22 spans added | ch27, ch28, ch29, ch30 |

Total: ~126 discrete edits across 26 files (118 changed lines per `git diff --stat`).
Chapters requiring no edits: ch22, ch38. All scripted verifications re-run clean after
editing.

## 3. Verified clean (no fixes needed)

- **Continuity (check A).** Verified consistent across ch16–41 and against the bible plus
  the I–III canonical additions: Forge `northstar.engineering`/`forge`, the `9f3c1a7`
  24-hour/`revision_change` merge-approval scene (ch29, ch30, ch37, ch40-F2); Ledger
  namespace `northstar.treasury`, zones `treasury-plan`/`treasury-data`/`payment-exec`/
  `audit-store`, mission `CASE-4471` reused correctly in ch24, delegation
  `analyze.exposure` depth 1/expiring/onward-denied, no identity holding both
  `payment.draft` and `payment.approve` (ch31, ch39: `payment.approve` and
  `payment.submit` held by no agent); Atlas capability strings and denied surfaces
  (ch39 Table 39.1); Gateway benchmark non-wins S15/S18 (ch23, ch25); support-network
  `git:feedfacefeed…` (ch19, ch26, ch35 — matches the repo example); €50,000 escalation
  threshold and EUR throughout; CrewAI `==1.15.4` / LangGraph `==1.2.2` pins everywhere.
- **Capstone [extension] discipline (check A, capstone clause).** Verified: the gateway
  and the five-level hierarchy engine appear in ch39–41 only as dashed diagram elements,
  *target* tiers, residual-dependency cells, and `not_claimed` lists; no register row's
  current tier, no gate, and no transcript depends on either; ch39's deletion test is
  stated and holds. The capstone does not resolve Thread E's [extension] machinery as
  implemented.
- **Status discipline (check B).** Badges begin at ch16 §16.1 as designed and every
  Nornyx capability statement in range carries an appropriate badge or an explicit
  labelled qualifier. Highest-risk chapters re-checked line by line: ch26 (projection and
  every enforcement-provider capability [extension]/[guidance]; Listing 26.2 captioned
  "Illustrative — not drawn from the repository"), ch27 (documentation-MCP pattern
  [guidance], connector descriptors' target capability roadmap, scanner/declaration
  surfaces [implemented] and source-verified), ch32 (hierarchy engine [extension] with
  the cross-repo-ref non-goal correctly attributed), ch37 (stage-5 enforcement points
  [extension]; platform bindings labelled), ch39–41 (Tier 3 rows restated one tier lower
  for the present; trace projection, projection compilers, authenticated producers all
  [extension]). Illustrative artifacts are consistently captioned as such with real field
  shapes attributed to schemas.
- **Cross-references (check D).** All "Chapter N" references in range verified against
  the book design's structure; all cross-chapter Figure/Table/Listing references
  (~40) and all "Section N.M" references resolve to real captions/headings; all
  Prerequisites callouts cite only earlier chapters and describe them accurately.
- **Numbering & markup (check E).** Figures, tables, and listings sequential per chapter
  with no gaps or duplicates; captions match the style guide's exact forms; every DOT
  figure carries its required `// fig=` comment with matching numbers; all `[@key]`
  citations in ch16–41 + app_e resolve to `05_bibliography.md` (zero invalid keys);
  callout labels are only the sanctioned set with correct thread names; all ix spans
  single-line and balanced.
- **Repetition (check F).** Tier definitions, proof boundary, PDP/PEP, and the coverage
  taxonomy are used with cross-references after their home chapters, not re-taught:
  ch20 §20.7's proof-boundary treatment is that chapter's assigned deep instance (the
  embedded-limitations mechanism) and anchors to Chapter 11; ch26 §26.1 compresses Tier 3
  eligibility to one paragraph citing Chapter 13; ch22/ch24/ch25 cite Chapter 14's
  taxonomy rather than redefining it; ch28/ch30 explicitly decline to restate Chapter 9's
  approval semantics. No trims warranted.
- **Voice (check G).** Part VIII reads as one author and, after the Ledger revision
  re-key and the class-2 harmonizations, contradicts no earlier chapter's details;
  thread recaps stay at one sentence per the bible's continuity rules. Telecom analogy
  appears only in its three sanctioned Part IV–VII chapters (ch26 §26.6, ch32 §32.2,
  ch37 §37.6), each stating where it stops.
- **House style (check C).** No marketing adjectives found (the one "robustness" is the
  EU AI Act's own obligation language); "the reader" usage within allowance; `.nyx`
  files called "contract" throughout.

## 4. New canonical additions from Parts IV–VIII (bible should absorb)

Later work (appendices, instructor guide, any revision of ch01–15) must treat these as
binding, in addition to §1's identifiers:

- Atlas partner-share approval canonical name: `partner_disclosure_approval`
  (ch07 origin; now used in ch17, ch36, app_e). ch36 adds evidence/gate names
  `partner_share_review` / `gate.partner_share_review`, zones `zone.research_internal`
  and `zone.partner_channel`, mission `GOAL-RESEARCH-014`, brief `brief-2026-03-14`.
- Thread C submission capability: `payment.submit` (ch31, ch39–41), submission-service
  pattern of ch31 §31.7; capstone network id `network.treasury_exceptions`, mission
  `GOAL-LEDGER-001`, €61,250 worked case, capstone lock digest `sha256:44f0cfb0…`,
  contract digest `sha256:70119e93…`.
- Forge capstone lanes (ch29 proposal/merge/release), initiator-to-SOD-author mapping
  (ch30), claim-register ids NS-ORG-001/002, NS-ATLAS-001/002, NS-FORGE-001/002,
  NS-LEDGER-001/002/003, NS-PKG-001 (ch39–40), exception `EXC-TREASURY-MIG-2026-04`
  (ch32).

## 5. Source verifications performed (fact-pack gaps closed, no edits needed)

Diagnostic codes and quotes cited in chapters but absent from the fact packs were
verified against the repository at the snapshot: `POLICY_DENY_MATCHED`
(`nornyx/policy_runtime.py`), `PACK_LOCK_REQUIRED` (`nornyx/governance/composition.py`),
`CONNECTOR_LIVE_TARGET_DECLARED` (`nornyx/connector_runtime.py`),
`AN_IDENTITY_BINDING_DUPLICATE`, `AN_EVIDENCE_UNKNOWN`, `AN_CONTRACT_REVIEW_MISSING`
(`nornyx/governance/agentic_network.py`), `AN_DELEGATOR_CAPABILITY_MISSING`
(`nornyx/governance/agentic_delegation.py`), `EXCEPTION_CORE_CONTROL_FORBIDDEN`,
`EXCEPTION_CLOSURE_EVIDENCE_MISSING`, `SOD_EVIDENCE_PRODUCER_SOLE_APPROVER`,
`APPROVAL_DECLARATION_REQUIRED` (`nornyx/governance/structural.py`), `RULE_PATH_MISSING`
(`nornyx/governance/rules.py`), `GOVERNANCE_REQUIRED_BLOCK_MISSING`
(`nornyx/governance/runtime.py`); ch16's schema-permanence quotation (verbatim at
`docs/VERSIONING.md:54`); ch18's module dependency chain
change_control → exception_management → separation_of_duties → human_approval →
evidence_integrity (module pack YAMLs); the 27-segment forbidden-key set
(`nornyx/agentic_artifacts.py`).

## 6. Flagged, not fixed (Stage-6 decisions or out-of-scope)

1. **Ledger escalation: ch31 vs the capstone.** ch31 Table 31.1 requires a treasury
   officer **and** a risk officer above €50,000; the capstone (ch39 §39.6, ch40
   Fig 40.2) restructures escalation as a handoff plus a single
   `network_governance_owner` approval for the €61,250 crossing, driven by the composed
   module's fixed role authority (ch40 Listing 40.1). Both are labelled illustrative and
   the capstone explains its structure, but the dual-control requirement of ch31 is not
   visibly carried or visibly waived. Recommend either a clause in ch39 §39.6 recording
   how the second officer's review travels (e.g., in the approval package's required
   evidence) or a bible ruling that the capstone supersedes Table 31.1's bands.
2. **Two Thread C network ids.** App. E's fragment uses `network.ledger_exceptions`;
   the capstone uses `network.treasury_exceptions`. Both are illustrative and now carry
   distinct revisions; harmless, but a single id would be tidier if App. E is revised.
3. **Sub-namespaces.** ch39 Table 39.1 uses `northstar.treasury.plan/.data/.exec/
   .approval` — an extension of the canonical `northstar.treasury`, treated as
   compatible. Bible could record the convention.
4. **ch16 CI first use** occurs inside a verbatim README quotation (cannot be expanded
   in-quote); the first free-prose expansion is in the Gateway case study. Tolerated,
   consistent with the I–III pass's handling of quoted strings. Similarly ch40's
   Table 40.1 F7 cell ("Hook/MCP/…") precedes the prose MCP expansion — compressed
   table cell tolerated.
5. **ch22 cites `tests/test_enforcement.py:61-211`** where fact pack 03 records 61–196.
   Trivial line-range discrepancy in a citation tail; verify once against the file if a
   final line-number sweep is done.
6. **ch40 F2 wording** ties the Forge force-push scene's engine denial to Listing 40.4,
   which was produced against the Ledger contract; the demonstration is of the same
   engine check, but a pedantic reviewer may trip on the cross-thread illustration.
7. **ch18 lock digests and similar transcript constants** (e.g. `sha256:fe71adc9…`,
   `sha256:95a5aa7…`, workspace transcripts) are presented as observed output and were
   not re-executed by this pass; formats and behaviors were verified against fact packs
   and source, but a Stage-7 transcript re-run remains worthwhile where exact digests
   are printed.
8. **Previous-pass flag items 2–3** (ch03 supplier vocabulary; ch06 four-vs-five agent
   count) remain open and outside this range.
