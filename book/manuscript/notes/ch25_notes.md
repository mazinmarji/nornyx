# Chapter 25 notes — "Adapter Conformance and Coverage"

## Status

Draft complete. Prose word count 5,100 by the manuscript's counting method (front matter and
fenced code excluded, HTML tags stripped; table cells and figcaptions retained). Raw file word
count 5,729 — the overage relative to prose is Table 25.2 (11-row coverage taxonomy) and
Table 25.3 (the Thread D decision table), both required by the task message.

Structure: 3 figures (25.1 HTML `layers` — the required conformance-flow figure, five layers
behind a `wrapped` label; 25.2 DOT — framework release as governance event; 25.3 HTML `zones` —
distribution boundary), 3 tables (25.1 two-conformance disambiguation; 25.2 the required
coverage-taxonomy table; 25.3 the Thread D four-path decision table), 3 listings (25.1 abridged
repository excerpt; 25.2 schema-shaped report fragment; 25.3 verbatim repository excerpt),
13 index spans. Callouts: Opening scenario, Learning objectives, Prerequisites, Design
checkpoint, Misconception, Assurance boundary, Case study — Gateway.

Badge note: the task message specifies the badge **[implemented as practice]** for runtime
adapter conformance. This is a variant of the style guide's three-badge set; I used it exactly
once, in Table 25.1's status row, alongside the standard **[implemented]** for the static
report, and used only standard badges elsewhere. If the build's badge validator rejects the
variant, replace it with **[implemented]** plus the phrase "as an engineering practice" —
the table row is written so this substitution is safe.

## Repository paths I personally read and verified during drafting

1. `tests/test_v07_adapter_conformance.py` — read in full. Source of the decision-code sets
   (`ADAPTER_EXECUTION_MODE_CONTRACT_ONLY` … `ADAPTER_NON_GOALS_COMPLETE`, and the `*_UNSAFE`
   mirrors on the blocked fixture), the `requires_human_approval` status on the repository's own
   example, and the test at 124-133 that asserts the schema constants directly.
2. `schemas/adapter_conformance_report.schema.json` — read lines 1-60. Confirmed
   `schema`/`mode`/`status` consts and every `safety` field as a `const false` (plus
   `default_execution_mode: "disabled"`), the basis of Listing 25.2 and Section 25.3.
3. `docs/44_NORNYX_ADAPTER_CONFORMANCE_v0_7.md` and `docs/41_NORNYX_ADAPTER_CONTRACTS_v0_4.md` —
   read the status, report-contents, and non-goals sections.
4. `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/langgraph.py` — Listing 25.3 is
   verbatim (lines 61-69); also the import-time module-level check call.
5. `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/_compat.py` — read in full
   (SPI-major gate, `require_extra`, `MissingOptionalDependencyError`).
6. `adapters/nornyx-agentic-adapters/scripts/test_wheel_install.py` — read in full. Listing 25.1
   is abridged from its probe strings; the caption's "runtime use, not installation" scoping is
   the script's own docstring point.
7. `adapters/nornyx-agentic-adapters/tests/test_import_boundary.py` and `tests/test_no_network.py`
   — read (first ~50 lines / in full). Basis of the negative-controls paragraph.
8. `adapters/nornyx-agentic-adapters/tests/test_langgraph_adapter_missing_dependency.py` — read
   in full.
9. `adapters/nornyx-agentic-adapters/pyproject.toml` — read lines 1-40 (name, version, Alpha
   classifier, Python range, dependency range, extras, the ruff-bound comment).
10. `adapters/nornyx-agentic-adapters/docs/COMPATIBILITY.md` — read in full. Source of the
    quoted pin rationale, the minor-compatible/breaking classification, and the shim divergence
    (requires 1.11.0; does not raise the adapter floor; "does not widen the CrewAI or LangGraph
    coverage declared here").
11. `adapters/nornyx-agentic-adapters/CHANGELOG.md` — read lines 1-60 (0.2.0 dated 2026-07-30,
    F2 fix narrative).
12. `.github/workflows/ci.yml` — read the `adapter-foundation` (58-115) and
    `adapter-langgraph-native` (248-291) jobs in full, incl. the JUnit-parsing zero-skip gate
    and the candidate-commit wheel discipline; job boundaries for `adapter-crewai-native` (117),
    `crewai-governance-benchmark` (293), `native-frameworks` (445) located by grep.
13. `.github/workflows/adapters-release.yml` — read lines 1-90 (OIDC trusted publishing, the
    `adapters-vX.Y.Z` tag/version binding check that fails closed).
14. `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/coverage.py` — read in full
    (three-member enum, canonicalized entries, sorted `as_dict`).
15. `examples/crewai_governance_benchmark/variant_governed.py` — read the `adapter_surface`
    function (523-533) emitting the inventory verbatim into benchmark output.
16. `CHANGELOG.md` (root) — read the `[Unreleased]` section (M2-D distribution-boundary and
    "release classification C … separate authorization" wording).
17. Verified absence: `grep -rl adapter_conformance adapters/` returns nothing — basis for
    Table 25.1's "no artifact links them" claim (matches fact pack 03 §14(5)).

## Claims taken from the fact packs rather than verified directly

1. `build_adapter_conformance_report` / `write_adapter_conformance_report` generator location —
   fact pack 03 §6 (`nornyx/connector_runtime.py:769-801, 811-815`). I verified the import names
   in the test file but did not open `connector_runtime.py`.
2. CrewAI coverage inventory line range and six-surface content in Table 25.2 — fact pack 03
   §2.2 (`crewai_adapter.py:118-183`); first two entries also seen verbatim in the fact pack's
   §12 excerpt.
3. CrewAI bypass test location (`tests/test_crewai_adapter.py:506`) and benchmark scenario S15's
   both-arms control status — fact pack 03 §2.3 and §7 (Table 25.3 caption).
4. Adapter contract schema constants (`adapter_contract.schema.json:37-42, 99-112`) — fact pack
   03 §6; I read the *report* schema myself but took the *contract* schema line refs from the
   pack.
5. The M2-D shim's 32-test corpus — fact pack 03 §8.2.
6. `crewai-governance-benchmark` job details (offline run, GO verdict gate) — fact pack 03 §11;
   only referenced in passing.

## Claims I could NOT verify, and what I wrote instead

1. **PyPI presence of `nornyx-agentic-adapters` 0.2.0.** Fact pack 03 §14(1) flags conflicting
   in-repo statements and says actual index presence was not verified offline. The chapter
   therefore says the package "ships as" / "is published … via a release workflow" only in the
   sense of its declared release machinery, and Section 25.6's conclusions are drawn from
   metadata and workflow files, never from an index lookup.
2. **Whether CI has ever exercised the release workflow end to end** (trusted-publisher
   registration is described in the workflow's own comment as a separate owner-performed
   prerequisite). I limited the claim to what the workflow file enforces: a tag/version mismatch
   fails closed rather than publishing.
3. **Framework ecosystem facts about CrewAI 1.15.4 / LangGraph 1.2.2** (upstream stability,
   release cadence) — fact pack 03 §14(7). All drift discussion is written about the mechanism,
   not about either framework's actual history.
4. **The four-path decision table's column 4** (external enforcement) is a forward reference to
   Chapter 26 and carries **[guidance]**/**[extension]**; its row values (coverage, evidence,
   failure behavior, Tier 3 "if genuinely unbypassable") are this book's architectural analysis,
   not repository claims. The caption states column 4 "is not implemented anywhere in this
   repository."
5. **"Two months of dense releases" style claims** from Ch. 16 were not repeated; no release
   dates are asserted in this chapter except adapter 0.2.0's changelog date (2026-07-30),
   verified in item 11 above.

## PROPOSED-REF

None. Further-reading keys used: `nornyx-repo`, `swebok-testing`, `slsa`, `nist-scrm`,
`nist-ssdf` — all in `05_bibliography.md`.

## Continuity and cross-reference checks

- Thread D (Gateway) closed out per the bible: the four-path decision table (Table 25.3) is the
  thread's promised deliverable, the case-study callout adds the coverage claim-register row,
  and column 4 forwards to Chapter 26 without resolving it.
- The merged-chapter mandate from `01_book_design.md` ("Runtime Adapter Conformance" merged into
  Ch. 25 with coverage) is satisfied by Sections 25.2 (runtime practice) + 25.5 (coverage
  evolution) + 25.6 (packaging).
- References: back to Chapters 2, 13, 14, 15, 16, 19, 22, 23, 24; forward to Chapters 26, 36.
  Chapter 23 referenced by number only (parallel authoring).
- The five-test rule is referenced, not re-taught (one clause), per the no-repetition rule;
  the zero-skip gate is referenced against Ch. 15's Listing 15.3 rather than re-quoted — this
  chapter cites the *LangGraph* job's gate lines instead to avoid duplicating Ch. 15's CrewAI
  listing.

## Editorial flags

- Table 25.2's "Consumer's obligation" and "Who can change it" columns are interpretive (this
  book's reading), and the caption says so; if a reviewer wants the table strictly verbatim,
  drop the two columns and move their content into prose.
- Listing 25.2 is schema-shaped rather than a captured generator output (the generator was not
  run here); the caption says "shape drawn from" the schema and generator. If a later pass runs
  `build_adapter_conformance_report` on `examples/nornyx_v04_adapter_contracts.nyx` (read-only,
  allowed by writer instructions), the listing could be upgraded to a real capture with a
  "produced by running…" caption.
- Exercise 3 deliberately mirrors the fact pack's open observation (03 §14(6)) that no pipeline
  publishes the inventory as an artifact; the instructor guide should note that "merely make it
  more legible" is a defensible answer.
