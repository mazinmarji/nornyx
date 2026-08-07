# Chapter 2 notes — "The Governance Gap"

## Status

Draft complete. Prose word count 5,442 (excludes fenced blocks and HTML figures; includes tables and
captions). This is above the 3,800–5,000 band in my task message but within the 3,800–5,500 band in
`06_writer_instructions.md`. Three trimming passes were applied. The remaining length is carried by
required content: four drift types each needing a precise definition *and* a distinct worked example,
four independent axes against alignment/prompts/guardrails, and the bounded telecom analogy with its
four stated breaking points. Flagging for the editor in case a hard 5,000 cap applies — the cheapest
further cut would be Table 2.3, whose content is fully carried by the prose of Section 2.4 (≈200 words).

Structure: 3 figures (2.1 DOT, 2.2 HTML flow-col, 2.3 HTML layers), 3 tables, 1 listing, 24 index
spans, 1 `Case study — Forge` callout, callouts used: Key idea, Misconception, Design checkpoint.

## Nornyx-specific claims made, and their support

Only one passage in this chapter asserts Nornyx-related behavior (Section 2.3, framework-adapter
drift). All of it is stated in prose status form ("as implemented at the snapshot" equivalents),
not with inline badges, per the style guide's pre-Chapter-16 rule.

1. Reference framework adapters pin frameworks to exact versions, CrewAI `==1.15.4` and LangGraph
   `==1.2.2`, and refuse to operate against other versions.
   Verified directly at `adapters/nornyx-agentic-adapters/pyproject.toml:27-28` and
   `adapters/nornyx-agentic-adapters/docs/COMPATIBILITY.md:5-6,59-61`.
2. The stated rationale that "a wider range is not claimed until new test evidence supports it" —
   verified at `adapters/nornyx-agentic-adapters/docs/COMPATIBILITY.md:38-43` (fact pack 03 §1.1
   also cites `README.md:177-180`). I paraphrased rather than quoted.
3. A machine-readable coverage inventory marks each framework surface `wrapped`, `unwrapped`, or
   `unsupported`. Verified directly by reading
   `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/crewai_adapter.py`
   (`COVERAGE_INVENTORY`, six `SurfaceCoverage` entries; `tool_invocation` = WRAPPED,
   `async_tool_invocation` = UNSUPPORTED with the reason that `_arun` is not overridden).
   The third status, `unwrapped`, is used by the LangGraph adapter's `graph_topology` entry
   (fact pack 03 §5.3) — I did not open that file, so I kept the sentence at the level of "the
   adapters publish an inventory naming each surface as one of three statuses" rather than
   attributing a specific status to a specific surface.

The asynchronous-tool-path example in the framework-adapter drift subsection is written as a generic
scenario ("a wrapper that overrides a framework's synchronous tool-execution method"), deliberately
*not* attributed to any product, because in the real adapter the async path fails closed
(`BaseTool._arun` raises `NotImplementedError`, so the action never executes) rather than executing
ungoverned. Attributing the silent-execution failure mode to Nornyx's adapter would have been false.
The generic version is the one that teaches the drift type.

## Claims I could NOT verify (and what I wrote instead)

- **"Most agentic enforcement today is cooperative."** (Section 2.5, analogy-breaks paragraph.)
  No survey source in the bibliography supports a population claim. Written as a scoped statement
  about the mechanism class rather than a measured proportion, and immediately grounded in the
  concrete cooperative case (an in-process wrapper the calling code can decline to use).
- **Whether relaxed branch protection and unfiltered release branches are the *most common* control
  drift instances.** No source. Written without any frequency claim.
- **The pairwise-interoperation history of early VoIP appliances.** `3gpp-ims` and `gsma-volte` cover
  the IMS target architecture, not the pre-IMS appliance market. The pre-IMS description is written
  as uncited background framing and the citation is attached only to the IMS decomposition itself.
  If the editor wants the "before" state sourced, a reference would be needed — see PROPOSED-REF
  below.
- **Guardrail failure behavior ("usually fail-open").** No bibliography source. Softened to "typically
  fails open when uncertain" and given a stated engineering reason (blocking on uncertainty destroys
  usability), so it reads as an argument about the category's incentives rather than a measurement.
- The 99.5% / 99.7% detection rates in Section 2.4 and Review question 4 are explicitly hypothetical
  figures used in an argument, not attributed to any product.

## PROPOSED-REF

- `PROPOSED-REF:` a source for the pre-IMS standalone-softswitch/appliance era (e.g. an ITU or
  operator-architecture retrospective) if the editor wants the "before" half of the telecom analogy
  cited rather than treated as background. Not required for the argument as written — the cited
  material is only the IMS decomposition.

## Repository paths I personally verified for this chapter

- `/home/user/nornyx/adapters/nornyx-agentic-adapters/pyproject.toml` (lines 27–28, framework extras)
- `/home/user/nornyx/adapters/nornyx-agentic-adapters/docs/COMPATIBILITY.md` (lines 3–6, 59–61)
- `/home/user/nornyx/adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/crewai_adapter.py`
  (adapter metadata block and `COVERAGE_INVENTORY`)
- `/home/user/nornyx/nornyx/repo_drift.py` (module docstring lines 1–9, `REPORT_SCHEMA`) — read to
  confirm the AGENTS.md-only-diff motivation before deciding *not* to use it in this chapter, since
  the drift gate is Nornyx machinery and Chapter 2 must state the problem before the mechanism.
- `/home/user/nornyx/nornyx/generator.py` (lines 1–36, LF-newline `_write`, sorted artifact hashes) —
  same reason; consulted, not cited here.

## Continuity notes for later writers

- The Forge incident here is dated to a Tuesday merge, with the March branch-protection relaxation,
  the June `release/2.4` branch, and the April tool-logging wrapper that stopped recording after a
  June framework upgrade. Chapters 9, 15, 29, 30 should treat these as established facts.
- The Risk & Audit chief's rejected sixth control ("a pre-merge script asking Forge to self-certify")
  is available as a callback in Chapter 30.
- Repository restructure `src/auth/` → `services/auth/` is now canonical for `northstar/payments-api`.
- The four drift-type names and definitions in Table 2.2 are the book's definitions; Chapters 8, 14,
  21, 25 should use them without redefinition.
- I used numbered `##` sections (2.1–2.6) matching Chapter 8's convention rather than Chapter 1's
  unnumbered sections. If the editor standardizes on Chapter 1's style, these three chapters need
  section numbers stripped and Chapter 8 likewise.
