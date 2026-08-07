# Chapter 24 notes — "LangGraph Integration"

## Status

Draft complete. Prose word count 5,150 by the counting method used across this manuscript
(front matter and fenced code blocks excluded, HTML tags stripped; figure node labels,
figcaptions, table cells, and callout labels retained). Raw file word count 5,546.

Structure: 3 figures (24.1 HTML `fig-table` — occurrence-identity sources, the occurrence-identity
figure required by the task message; 24.2 HTML `seq` — the required interrupt/resume sequence
figure; 24.3 DOT — the Ledger analyst graph), 2 tables, 4 listings (24.1 verbatim source, 24.2
verbatim source, 24.3 illustrative Python, 24.4 illustrative JSON), 14 index spans. Callouts:
Opening scenario, Learning objectives, Prerequisites, Key idea, Case study — Gateway,
Misconception, Assurance boundary. Inline badges used per the Ch. 16 rule.

Honest-captioning requirement (LangGraph not installed in the authoring environment): Listings
24.3 and 24.4 are captioned "Illustrative … not executed for this book" / "Illustrative and
abridged", with each structural claim tied to a source or test line range. Listings 24.1 and 24.2
are verbatim repository excerpts and captioned as such. Nothing framework-executing was run here.

## Repository paths I personally read and verified during drafting

1. `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/langgraph.py` — read in full.
   Source of Listings 24.1 (lines 201-229, verbatim with one message elided) and 24.2 (lines
   244-262, verbatim), the coverage inventory of Table 24.2 (lines 82-125), the construction
   checks (161-179), invocation validation (184-199), the inline enforce sequence (231-242),
   the success observation and cache eviction (264-273), the module docstring, and the exact
   error message "M2-C supports synchronous LangGraph node actions only."
2. `adapters/nornyx-agentic-adapters/tests/test_langgraph_adapter.py` — read in full. Source of
   every test name in Table 24.1 and the cited assertion ranges (102-117, 120-125, 171-192,
   199-221, 229-259, 262-283, 286-303); confirmed real `StateGraph`, `InMemorySaver`,
   `RetryPolicy`, `interrupt`, `Command`, `ExecutionInfo`, `Runtime` imports (lines 13-16) and
   the `ExecutionInfo(checkpoint_id, checkpoint_ns, task_id, node_attempt)` construction shape
   used to justify Listing 24.3's captioned verification claim.
3. `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/binding.py` — read in full
   (SurfaceBinding fields, validate_binding fail-closed, module docstring on never deriving
   bindings from framework arguments).
4. `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/enforcement.py` — read in full
   (basis for the statement that the LangGraph path reimplements the evaluate–record–execute
   sequence inline rather than calling `enforce()`; confirmed `enforce()` records via
   mission-scoped `record_decision`).
5. `nornyx/agentic/authz.py` — read `RuntimeOccurrence` (468-493 incl. `_RUNTIME_ID_RE` at 71),
   `record_occurrence_decision` (1506-1539), `record_occurrence_observation` (1557-1582),
   `max_recorded_attempt` (1584-1613), `_capability` (937-962, source of the two-intent decision
   shape and `delegation_ref` stamping cited in the Listing 24.4 caption), and the `def` line of
   `resume` (1305).
6. `docs/agentic-network/03_LANGGRAPH_GUIDE.md` — read in full (identity/occurrence mapping table,
   resume usage, enforcement-behavior paragraph, coverage boundary).
7. `adapters/nornyx-agentic-adapters/docs/COMPATIBILITY.md` — read in full.
8. `adapters/nornyx-agentic-adapters/README.md` — read the LangGraph and Assurance-boundary
   sections.
9. `.github/workflows/ci.yml` — read the `adapter-langgraph-native` job (248-291).

## Claims taken from the fact packs rather than verified directly

1. `EvidenceRecorder.resume()` internals (revalidates complete prior stream, producer/schema/
   occurrence-mode match, decision-instant ordering, sequence-counter restoration, "differential
   chunks and multi-producer merging are not supported") — fact pack 02 §5.4, citing
   `authz.py:1304-1396` and `docs/agentic-network/06_RUNTIME_EVIDENCE.md`. I verified only the
   `def` line; the behavioral description in Section 24.5 follows the fact pack.
2. `for_occurrences` requiring a 1.1 lock — fact pack 02 §5.4 (`authz.py:1277-1302`).
3. Success/failure terminal event sets referenced from Chapter 12 — fact pack 02 §5.2.
4. Occurrence-mode envelope variants — fact pack 02 §5.1/5.3.

## Claims I could NOT verify, and what I wrote instead

1. **LangGraph's general execution model** (Section 24.1: state graphs, conditional edges, retry
   policies, parallel scheduling, checkpointers, interrupts, public execution metadata). The
   framework is not installed and its docs were not fetched. I kept the description to what the
   adapter source, its tests, and the repository's LangGraph guide demonstrably rely on, and
   cited [@langgraph-docs] for the framework's own account. No claims about LangGraph features
   the repository does not exercise.
2. **Canonical identity ref for Thread C's analyst.** The case-study bible gives the capability
   string `analyze.exposure` and agent names, but no identity-ref spelling. I coined
   `identity.ledger.analyst` following the repository's `identity.<name>` convention
   (e.g. `identity.researcher.local`, `identity.support_coordinator`). Flagged for the Thread C
   chapters (31, 34) to reuse the same spelling.
3. **Sample task identifiers** (`task-9f3c1a7`, `task-4b8e2d0`) in Listing 24.4 and Figure 24.2
   are invented, styled per the bible's `9f3c…` SHA convention; real LangGraph task ids are
   opaque strings (the tests use `"task-with-hyphens"` etc.). The listing is captioned
   illustrative.
4. **Listing 24.4's exact event interleaving.** The sequence numbers and event ordering are my
   composition from verified parts (decision-intent pairs from `_capability`; observations from
   the adapter; occurrence/attempt patterns from the retry/loop tests). No single repository
   artifact contains this exact stream; the caption says so.
5. **Whether `RetryPolicy(retry_on=TimeoutError)` is a valid argument form** — the adapter test
   uses `retry_on=ValueError` with `initial_interval=0`; I mirrored the form with a different
   exception type in illustrative Listing 24.3 and dropped `initial_interval` (cosmetic). Not
   executed.

## PROPOSED-REF

None. Further-reading keys used: `langgraph-docs`, `nornyx-repo`, `lamport-clocks`,
`anthropic-agents`, `schneider-enforceable` — all in `05_bibliography.md`.

## Continuity and cross-reference checks

- Thread D (Gateway) advanced with two claim-register rows; Thread C (Ledger) material used for
  the worked example is consistent with the bible (agent `analyst`, capability
  `analyze.exposure`, zone `treasury-data`, mission `CASE-4471` matching Ch. 12's usage,
  delegation planner→analyst).
- References: back to Chapters 12, 13, 14, 15, 16, 19, 20, 22, 23; forward to Chapters 25, 26,
  31, 34. Chapters 22–23 are referenced by number only (written in parallel), with no claims
  about their internal section numbering.
- Terminology per style guide: occurrence/attempt/mission/operation, wrapped/unsupported/
  unwrapped, fail-closed, cooperative enforcement, "evidence" never "proof" for supplied
  evidence.

## Editorial flags

- Figure 24.2 (seq) puts explanatory text in message labels; if the build's `msg` renderer
  truncates long labels, shorten to keyword form — the caption carries the argument.
- Section 24.2's paragraph on `enforce()` not being on the LangGraph path is a
  reader-expectation correction; Chapter 22's author should confirm they describe `enforce()` as
  the CrewAI-path boundary so the two chapters do not contradict.
- The exercise answers assume `AN_EVT_REPLAY` (exercise 3) — taught in Chapter 12, not re-named
  here.
