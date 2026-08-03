# Chapter 14 notes — "Bypass, Coverage, and Negative Controls"

## Status

Draft complete. Prose word count 5,518 by the counting method used across this manuscript (front
matter and fenced code blocks excluded; HTML tags stripped but figure node labels, figcaptions,
table cells, and callout labels retained). Body-paragraph text alone is comfortably inside the
3,800–5,500 band; the measured figure is pushed up by Table 14.1, Table 14.2, and three long
figcaptions. If a hard 5,500 cap is applied to the measured number, the cheapest cut is the fourth
row of Table 14.2 (≈70 words), whose teaching point is duplicated by Section 14.4's framework-pin
paragraph.

Structure: 2 figures (14.1 HTML `flow-col` with dashed bypass arrows and an untrusted-styled
endpoint; 14.2 HTML `fig-table`), 2 tables, 2 listings, 14 index spans, 1 `Case study — Gateway`
callout. Two figures is the low end of the style guide's 2–5 range; the material that would
otherwise be a third figure is carried by Table 14.1 (the real coverage inventory) and Table 14.2
(the overclaim rewrites), both of which are more legible as tables than as schematics. The task
message required a bypass/threat figure with dashed ungoverned paths: that is Figure 14.1.
Callouts used: Opening scenario, Learning objectives, Prerequisites, Key idea, Misconception,
Case study — Gateway, Assurance boundary, Design checkpoint.

Status wording: no inline badges are used anywhere in this chapter (Part III, pre-Chapter-16 rule).
Nornyx behavior is written as "as implemented at the snapshot", "declared", or "the repository's
own …"; the mandatory-gateway path in Figure 14.1 and its caption is written as "an architectural
extension beyond the current repository".

## Repository paths I personally read and verified during drafting

These were opened and read directly (not taken from the fact packs):

1. `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/coverage.py` — read in full.
   Source of Listing 14.1 (verbatim, with two method bodies elided as `...`), of the three-value
   `SurfaceStatus` enum, of the `CoverageInventory` docstring wording quoted in the Listing 14.1
   caption ("Never implies whole-application coverage (ADR-0040)…"), of the module docstring
   sentence quoted in Section 14.2 ("unsupported and unwrapped surfaces are named, not hidden, and
   the inventory never implies whole-application coverage"), and of the `__post_init__`
   canonicalization behavior described in the caption.
2. `adapters/nornyx-agentic-adapters/tests/test_crewai_adapter.py` — read the region around the
   bypass test. Listing 14.2 is verbatim, including the docstring and both inline comments. The
   test name `test_bypass_calling_the_raw_action_directly_skips_enforcement_entirely` is copied
   exactly.
3. `examples/crewai_governance_benchmark/README.md` — read the scenario matrix and the sections
   around it. Source of the S15 sentence quoted in Section 14.6 ("S15 executes under governance on
   purpose — enforcement is cooperative, and a tool that never enters the adapter is never
   evaluated") and of the "are controls, not wins" phrase.
4. `.github/workflows/ci.yml` — read the `adapter-crewai-native` job region (used mainly in
   Chapter 15, but it confirms the exact framework pin `1.15.4` asserted in Section 14.4).

## Claims taken from the fact packs rather than verified by me directly

All are supported by fact pack 03 with paths; I did not open the underlying files.

1. **Table 14.1, the six-entry CrewAI coverage inventory** — fact pack 03 §2.2, citing
   `crewai_adapter.py:118-183`. I abridged each `reason` string rather than quoting it verbatim,
   and softened "Crew.kickoff()'s native ReAct executor" to "native executor" in the table cell to
   avoid asserting an internal architecture term I had not read in source.
2. **The LangGraph adapter's five surfaces, including `graph_topology` as the sole `unwrapped`
   entry** — fact pack 03 §5.3, citing `langgraph.py:82-125`. This is the load-bearing example for
   the three-state argument in Section 14.2, so I flag that it is fact-pack-sourced.
3. **`test_async_arun_fails_closed_and_records_nothing`, `test_coverage_never_claims_unnamed_
   surfaces`, `test_coverage_inventory_declares_only_tool_invocation_wrapped`** — fact pack 03
   §§2.2, 4. Test names are copied exactly from the fact pack; only the first is named in the
   chapter body.
4. **Import-time framework pin enforcement** (wrong version → configuration error) — fact pack 03
   §1.2, citing `crewai_adapter.py:66-105` and `langgraph.py:45-69`. I wrote "raises a configuration
   error" rather than naming `AdapterConfigurationError`, since I had not read the raise site.
5. **The COMPATIBILITY.md rationale sentence** quoted in Section 14.4 ("name the only version of
   each framework this package has been tested against. A wider range is not claimed until new test
   evidence supports it") — fact pack 03 §1.1 cites both `README.md:177-180` and
   `COMPATIBILITY.md:38-43`; I attributed it to "the package's own documentation" without naming a
   file.
6. **The evaluate → record → execute ordering** referenced in Section 14.5's denial-test paragraph
   — fact pack 03 §3, `enforcement.py:28-65`.
7. **ADR-0040's "the word 'guarantee' is deliberately avoided" sentence**, paraphrased in Section
   14.7 — fact pack 04 §10(d), citing
   `docs/decisions/ADR-0040-governance-assurance-tiers.md`. I paraphrased rather than quoted and
   attributed it to "the repository's own decision records" without giving the ADR number, because
   fact pack 04 §12(1) warns that ADR numbers collide across two directories.

## Claims I could NOT verify, and what I wrote instead

1. **Whether the coverage inventory is exported as a published artifact anywhere in the toolchain.**
   Fact pack 03 §14(6) states explicitly that `CoverageInventory.as_dict()` is JSON-serializable but
   that no in-repo pipeline writes it to a report file; it is asserted in tests and in the CI wheel
   smoke. I therefore wrote that `as_dict` sorts its output "which is what makes the inventory
   diffable in a pipeline" — a statement about the property, not about an existing pipeline — and I
   avoided any sentence implying that a coverage report is published or consumed downstream.
2. **The exact wording of the "assurance boundary" section of the adapter README** referenced in the
   Assurance boundary callout. Fact pack 03 §2.3 summarizes it (`README.md:133-150`); I wrote the
   callout in my own words and did not present any of it as a quotation.
3. **Whether any other framework adapter in the ecosystem uses a three-state coverage model.** No
   source; I made no comparative claim, and Section 14.2 attributes the three-state taxonomy to the
   Nornyx adapters only.
4. **The claim in Table 14.2, row 3, about evidence completeness.** The rewrite text ("It does not
   prove that the records are complete or that the events described occurred") paraphrases the
   validator's embedded limitation text (fact pack 02 §5.2). I did not open
   `nornyx/agentic_evidence.py`, so I kept it as a rewritten claim inside an illustrative table
   rather than as a repository quotation.
5. **Framework ecosystem facts about CrewAI 1.15.4 and LangGraph 1.2.2** (release dates, upstream
   API stability). Fact pack 03 §14(7) flags these as unverified. The chapter makes claims only
   about what the repository pins and tests, never about the frameworks themselves.

## PROPOSED-REF

None. All five Further-reading keys (`schneider-enforceable`, `saltzer-schroeder`,
`swebok-testing`, `owasp-agentic`, `nornyx-repo`) and the two inline uses are from
`05_bibliography.md`.

## Continuity and cross-reference checks

- Thread D (Gateway) advanced per `03_case_study_bible.md`: the chapter adds path 3 (bypass) to the
  four-path comparison, keeps path 4 (external gateway PEP) as extension/guidance, and points
  forward to Chapter 26. It does not re-introduce the thread beyond one clause.
- Forward references used: Chapter 15 (benchmark method, five-test rule), Chapter 22 (adapter
  boundary), Chapter 26 (external enforcement providers). Backward: 1, 2 (drift taxonomy), 3
  (eight questions), 10, 11, 13.
- Terminology checked against the style guide's canonical list: "coverage inventory",
  "wrapped / unsupported / unwrapped surface", "cooperative enforcement", "assurance tier",
  "fail-closed", "claim register" (used in Ch. 34, not here), "evidence" never "proof".
- The word "proof" appears once, in "proves" applied to tests, never to supplied evidence.

## Editorial flags

- Section 14.6's argument depends on the reader accepting that a test with no product-code coverage
  is valuable. If a reviewer finds this unpersuasive, the fix is to strengthen the second paragraph
  ("what changes if it is removed") rather than to cut the section; the whole chapter's thesis lands
  there.
- Figure 14.1 uses `arr dashed` for the ungoverned arrows and `node untrusted` for ungoverned
  endpoints, per `04_visual_language.md`. It also uses `node authority` for the external gateway,
  which is the double-border/authoritative convention — appropriate since the gateway is the
  mandatory enforcement point, but worth a check that the build renders `node authority` (the
  visual-language document names `layer authority` explicitly and `class="authority"` generally).
