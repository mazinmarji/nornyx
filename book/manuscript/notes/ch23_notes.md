# Chapter 23 notes — CrewAI Integration

## Execution status of listings (CrewAI not installed in the writing environment)

- **Listing 23.1** (`_GovernedTool._run`): verbatim (abridged) from `crewai_adapter.py:211-262`. Not executed (module import requires the `crewai` extra); captioned accordingly via the abridgement note and test citations.
- **Listing 23.2**: verbatim from `examples/agentic_network.nyx:123-132,143-156`.
- **Listing 23.3**: NOT executed; captioned "Verified against source signatures … not executed for this book: CrewAI is not installed in the writing environment", with the adapter's own native end-to-end test (`tests/test_crewai_adapter.py:531-590`) cited as the executed counterpart, and the contract-fixture extension (`:82-89`) named. The file name `atlas_network.nyx` is explained in the caption as standing for Listing 23.2's contract plus a crewai framework binding.
- **Listing 23.4**: EXECUTED and observed. I ran the installed core (`nornyx` 1.11.0, SPI 1.2) plus the adapter package's framework-neutral modules (`sys.path` to `adapters/nornyx-agentic-adapters/src`; base package imports without CrewAI) against `examples/agentic_network.nyx`, building the authorizer exactly as the adapter test fixtures do (`compose_document_governance` + `build_agentic_network_lock` + `Authorizer`, `tests/test_crewai_adapter.py:92-95`). Observed: allowed enforce → action once; denied enforce → `AdapterDenied` with `CAPABILITY_DENIED` and the quoted reason string; event types `['capability_requested','capability_allowed','tool_invoked','capability_requested','capability_denied']`; `recorder.validate()` status `pass`, zero diagnostics. The digests in the listing (`sha256:85a5617…`, `sha256:0ddcafe9…`) are the real observed contract/lock digests from that run. The caption states that the CrewAI layer above this was not re-run.
- **Listing 23.5**: verbatim from `crewai_adapter.py:118-143` (first two inventory entries, elided tail marked `...`).

## Claims I could not verify (and what I wrote instead)

1. **CrewAI ecosystem description (§23.1)** — crews/agents/tasks/tools, sequential/hierarchical process, ReAct-style executor loop, `allow_delegation`: written neutrally from [@crewai-docs] and the repository's own usage of the pinned framework (test files construct `Agent(role, goal, backstory, llm, allow_delegation=…)`, `Task(..., tools=[...])`, `Crew(..., process=Process.sequential)`, and a `DeterministicLLM` that scripts Action/Final-Answer turns). I did not verify CrewAI's documentation text itself; §23.1 closes by scoping all claims to what the repo pins and tests (1.15.4).
2. **"Twelve classes of ungoverned effect"** — my count of the benchmark's prevented/denied scenario outcomes (S03–S13, S17 → 12 distinct codes) from the scenario matrix in `examples/crewai_governance_benchmark/README.md:73-103`. The benchmark itself never sums scenarios; I count *classes listed*, not a score, and say "per scenario … catalogue".
3. **Known doc-lag not repeated**: the benchmark README's stale rows (SPI "1.0", adapter "0.1.0", "not on PyPI" — fact pack 03 §14.1) are not quoted in the chapter; where the chapter quotes the benchmark README it uses only passages that are not affected (A/B design, ledger method, S15/S18, findings, snapshot caveat). PyPI publication status is not asserted anywhere in the chapter.
4. **Benchmark test count** (46 vs 47, fact pack 03 §14.2) — not mentioned in the chapter.

## Deliberate scoping decisions

- The bypass test is quoted in full in Chapter 14 (Listing 14.2); per the no-re-teach rule ch23 cites it (`tests/test_crewai_adapter.py:506-527`), quotes only its docstring line, and adds the integration-claim reading.
- Framework-native coworker delegation (unsupported) vs. Nornyx-declared delegation flowing into evidence (`delegation_ref`, tests `:342,:394,:421,:451`; benchmark finding F2) are explicitly distinguished in §23.4 to prevent a claim-register conflation.
- The `_arun` behavior is attributed to the *inherited* `BaseTool._arun` raising `NotImplementedError` — the adapter's own docstring/inventory wording — not to any adapter code.

## PROPOSED-REF

None.

## Repository paths personally verified (read at snapshot `70d2b40`)

- `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/crewai_adapter.py` (full: docstring 11-28; pin check 55-105; METADATA 109-116; COVERAGE_INVENTORY 118-183; identity 186-208; `_run` 211-262; `make_governed_tool` 265-327)
- `adapters/nornyx-agentic-adapters/tests/test_crewai_adapter.py` (fixtures 75-152; DeterministicLLM 155-205; direct enforcement 263-340; delegation 342-451; blank binding 489; bypass 506-527; native kickoff allow 531-591; native kickoff deny 593-655; async 659-715)
- `adapters/nornyx-agentic-adapters/README.md` (coverage note 68-96; structured args 84-96; assurance boundary 133-150)
- `examples/agentic_network.nyx` (capabilities 123-141; agent_identities 143-169; approvals 67-80)
- `schemas/agentic_capabilities_v1.schema.json` (description string; closed capability shape)
- `examples/crewai_governance_benchmark/README.md` (1-160: design, ledger method, scenario matrix, S15/S18, outputs, findings, snapshot caveat)
- `examples/crewai_governance_benchmark/variant_governed.py` (1-60: the two disclosed integration choices)
- `nornyx/agentic/authz.py` (`load_authorizer` 1166+; `EvidenceRecorder.__init__` 1240-1275; recorder method names 1439-1664)
- `.github/workflows/ci.yml` facts taken from fact pack 03 §11 (benchmark job lines 293-416; zero-skip gates) — spot-checked job names only, not re-read line by line
- Executed probe: scratchpad `ch23_probe.py` (source of Listing 23.4's observed output)
