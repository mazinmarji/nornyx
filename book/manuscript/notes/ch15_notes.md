# Chapter 15 notes — "Testing Governance Claims"

## Status

Draft complete. Prose word count 5,511 by the manuscript's counting method (front matter and fenced
code blocks excluded; HTML tags stripped, figure labels/figcaptions/table cells retained). Body
paragraphs alone are inside the band; the measured number is inflated by Table 15.1, the two
`fig-table` figures, and three long figcaptions. If a hard cap on the measured number is applied,
the cheapest cut is the third-property paragraph at the end of Section 15.5 (≈120 words), which is
genuinely additional but not load-bearing for the chapter's argument.

Structure: 3 figures (15.1 HTML `flow-col`, 15.2 HTML `layers`, 15.3 HTML `fig-table`), 1 table,
3 listings, 14 index spans, 1 `Case study — Forge` callout. Callouts used: Opening scenario,
Learning objectives, Prerequisites, Key idea, Design checkpoint, Case study — Forge, Assurance
boundary.

The governance continuous-integration flow figure required by the task message is Figure 15.2.

Status wording: no inline badges (Part III, pre-Chapter-16 rule). Repository behavior is written as
"as implemented at the snapshot", "the repository's answer", "the Nornyx toolchain", etc.

## Repository paths I personally read and verified during drafting

1. `.github/workflows/ci.yml` — read the `adapter-crewai-native` job in full. Listing 15.3 is
   verbatim from that job, including the two-line inline comment ("Fail closed if ANY focused CrewAI
   test skipped (e.g. crewai silently absent): deterministic skip check, not a printed version
   string.") and the JUnit-XML parsing one-liner. The three "load-bearing details" in the Listing
   15.3 caption — version asserted not printed, verdict parsed from the XML report, gate fails on a
   zero test count — are all readable in the quoted lines (`sys.exit(1 if (skipped or not tests)
   else 0)`).
2. `examples/crewai_governance_benchmark/README.md` — read the "How prevention is proved" section
   and the full 19-row scenario matrix. Sources for: the three side-effect-ledger properties in
   Section 15.7 (paraphrased closely, including the "k-th entry … preceded by a k-th recorded
   decision" formulation and the "even though a naive 'decision before first execution' test would
   pass" gloss); the five stages named in Section 15.7 (load, binding, runtime, bypass, application
   — read off the Stage column); the "S15 and S18 are controls, not wins" rule and the S15
   justification quoted in Section 15.7; and the three findings F1/F2/F3 with the scoping sentence
   ("None of them ever affected an enforcement result … What they blocked was a clean *evidence*
   claim"), which I paraphrased rather than block-quoted.
3. `docs/agentic-network/11_REFERENCE_CI.md` — read in full. Source for the six bands of Figure
   15.2, in particular step 5 ("regenerate and byte-compare (generated-artifact drift gate)"),
   steps 11 (`evidence-validate --strict` for both streams) and 13 (audit-package assembly), and
   the statement that the job needs no secrets.
4. `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/coverage.py` and
   `.../tests/test_crewai_adapter.py` — read for Chapter 14; they underpin this chapter's
   references to the coverage inventory and the bypass test.

## Claims taken from the fact packs rather than verified by me directly

1. **Listing 15.1** (the native `Crew.kickoff()` end-to-end evidence assertion) — quoted from fact
   pack 03 §12, which cites `adapters/nornyx-agentic-adapters/tests/test_crewai_adapter.py:580-590`.
   I read a different region of that file directly but not this one. Flagged because it is a
   verbatim listing; a copy-editor should re-verify it against the file before typesetting.
2. **`enforce()` ordering and fail-closed behavior** (evaluate → record → execute; errors from
   evaluation or recording propagate before the action) — fact pack 03 §3 and §2.4, citing
   `enforcement.py:28-65` and `tests/test_enforcement.py:111,196`. Used in Section 15.2 (test 3) and
   Section 15.4 (break the decision path).
3. **`--as-of` fail-closed behavior** (`AS_OF_INVALID`, exit 2, never a silent fallback to the live
   clock) — fact pack 01 §3 and traceability row, citing `nornyx/cli.py:133-161` and
   `CHANGELOG.md:95-102`. Used in Section 15.4 and Review question 4.
4. **Distinct exit code for lock/parse failures** — fact pack 01 §5, citing
   `docs/GOVERNANCE_CLI_AND_API.md:42-53`. I wrote "a distinct exit code" rather than naming the
   number, since the precise code is a Chapter 21/Appendix B concern.
5. **"The engine reads no wall-clock time"; `EvaluationContext.decision_at` governs all temporal
   semantics** — fact pack 02 §6.4, citing the `authz.py` module docstring lines 17-19. Central to
   Section 15.5's determinism property, so flagged.
6. **Composition monotonicity mechanisms** (ordered-union merge, conflicting scalar fields raise,
   core-denied actor types unioned back into every composition) — fact pack 01 §6.2 and §7.2,
   citing `nornyx/governance/composition.py:48-120` and `approvals.py:806-816`. I described the
   three mechanisms without naming `PACK_MONOTONICITY_CONFLICT`, since Chapter 8 owns that code.
7. **The engine authorizes declared concepts only and never parses raw shell commands, file paths,
   URLs, or tool arguments; adapters build bindings from static configuration, not framework
   arguments** — fact pack 02 §6.4 and fact pack 03 §4, citing the `authz.py` docstring and
   `binding.py:1-9`. Used in Section 15.5's third property.
8. **Real-framework CI jobs, same-commit wheel builds, fresh-environment smokes from outside all
   source roots, and the deterministic-LLM substitution** — fact pack 03 §11. I read the CrewAI job
   directly; the LangGraph job, the `adapter-foundation` wheel-from-same-commit behavior, and the
   "the deterministic part is the LLM, never the framework objects" conclusion are fact-pack-sourced.

## Claims I could NOT verify, and what I wrote instead

1. **The exact number of tests in the benchmark's own test module.** Fact pack 03 §14(2) records a
   contradiction: `REVIEWER_QUICKSTART.md:287` says "46 tests, zero skips" while a `def test` count
   returns 47. I therefore give **no** test count anywhere in the chapter and refer only to "the
   benchmark test suite" and "its own contract".
2. **Whether the repository uses the term "conformance suite" for its framework-adapter tests.** It
   does not; fact pack 03 §6 warns that "adapter conformance" in the repository means static,
   declaration-level checking of `.nyx` adapter blocks, a different artifact. Section 15.3 states
   this disambiguation explicitly and says that the coverage inventory plus behavioral test suite is
   what plays the conformance role — deliberately avoiding the category error the fact pack flags
   (§14(5)).
3. **Whether a governance test suite anywhere in the repository is organized by the five-test rule.**
   It is not; the five-test rule is my synthesis from Chapter 14's categories plus the repository's
   observable test structure. Section 15.2 presents it as a general obligation, not as a repository
   feature, and Table 15.1 is not attributed to any source.
4. **Listing 15.2 (the two property-based tests).** Explicitly captioned "Illustrative — not drawn
   from the repository." The repository has no property-based testing framework in use that I
   verified; the listing uses a generic `@given` decorator and undefined generators deliberately,
   as a shape rather than as runnable code.
5. **Whether the recorder continues or halts when it raises** (Section 15.4, "break the evidence
   path"). I could not establish the deployment-level answer, so the text poses it as two questions
   whose right answers depend on tier, rather than asserting a behavior.
6. **The pipeline behavior described in the Forge case study** (a second workflow that publishes a
   release candidate without consulting the policy artifacts). Entirely fictional, inside the
   Northstar case-study universe, and consistent with the bible's Thread B (fail-closed merge lane).
   No repository claim is made.
7. **PyPI/publication state.** Not referenced anywhere in this chapter; fact packs 01 §16 and 03
   §14(1) flag it as unverifiable offline.

## PROPOSED-REF

None. Further-reading keys used: `swebok-testing`, `schneider-enforceable`, `clark-wilson`,
`reproducible-builds`, `sre-book` — all from `05_bibliography.md`. No inline citations appear in the
body, which is appropriate for a chapter whose evidence is repository code rather than literature;
the Further-reading section carries the sourcing.

## Continuity and cross-reference checks

- Thread B (Forge) advanced per the bible: the testing scene is Chapter 15's assignment. The callout
  produces three findings (missing failure test, missing bypass test, failure-injection finding on
  an unrelated workflow) and explicitly changes no code — consistent with Chapter 2's drift
  narrative and setting up Chapters 29 and 30 without pre-empting them.
- Forward references: Chapter 22 (adapter binding discipline), Chapter 29 (CI/CD pipeline design).
  Backward: 3, 7, 8, 9, 13, 14. Chapter 14 is cited five times; each citation is a one-clause recap,
  never a re-teach.
- Section 15.6's "silent weakening, transplanted from policy composition into the assurance
  pipeline" deliberately reuses Chapter 8's term. Confirmed that Chapter 8 defines it
  (`ch08_composition_provenance.md` §8.3), so no re-definition is given here.
- The benchmark is treated as *method*, not as evidence about the reader's system; the Assurance
  boundary callout states the limit, echoing the repository's own "a snapshot of one run, not a
  continuously verified claim" (fact pack 03 §7).

## Editorial flags

- Figure 15.2's six bands are my organization, not the repository's. The caption says the reference
  workflow "instantiates every band", which is supportable from
  `docs/agentic-network/11_REFERENCE_CI.md` step by step, but the *banding* is editorial. A reviewer
  may want the caption to say so more plainly.
- Figure 15.3 is a synthetic ledger interleaving illustrating the benchmark's checkable properties.
  It is not a transcript of a real run. If the build's `fig-table` styling does not distinguish it
  from a data table, consider adding "Illustrative" to the caption.
