# Chapter 22 notes — Designing an Adapter Boundary

## Claims I could not verify (and what I wrote instead)

1. **"Most defective integrations are a case of one owner taking on another's job"** — an authorial generalization, not a repository fact. Phrased as an observation about integrations generally, with no Nornyx attribution and no badge.
2. **Latency characteristics** ("one local evaluation plus event construction per call") — no benchmark timing was quoted; the repository's benchmark labels its timing figures a local microbenchmark, so I kept the latency row of Table 22.2 qualitative (no numbers) and made no performance claim.
3. **CrewAI executor retry count** — the CrewAI adapter test comments say the executor "may retry a failed tool call internally"; the exact count (3) appears only in benchmark docs. In ch22 I wrote "may retry a failing tool internally" without a count.
4. **"A process that cannot govern should not start"** — design rationale inferred from the placement of `check_spi_version` at import time (`__init__.py:34`); the repository does not state this sentence verbatim. Presented as interpretation, not quotation.

## Deliberate scoping decisions

- The CrewAI/LangGraph post-action observation asymmetry (LangGraph records `runtime_failed` on action exception; the CrewAI governed `_run` records nothing when the action raises) is stated with line cites (`langgraph.py:254-262`, `crewai_adapter.py:243-262`). I verified this by reading both `_run`/`governed_node` bodies: the CrewAI `_run` has no try/except around `enforce`. Fact pack 03 §2.4 corroborates ("If the action itself raises, no `tool_invoked` is recorded").
- The coverage-inventory "declaration, not attestation" limitation follows fact pack 03 §14.6 (no in-repo pipeline exports `as_dict()` as a published artifact).
- Fact pack 03 §14.4 warns not to attribute version-range enforcement to `AdapterMetadata`; ch22 attributes enforcement only to the submodule import-time checks and `check_spi_version`.

## PROPOSED-REF

None.

## Repository paths personally verified (read at snapshot `70d2b40`)

- `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/enforcement.py` (full; Listing 22.2 verbatim from lines 28-65)
- `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/binding.py` (full; Listing 22.1 verbatim from lines 19-36; module docstring lines 1-9)
- `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/coverage.py` (full)
- `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/metadata.py`, `errors.py`, `_compat.py`, `__init__.py` (full)
- `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/crewai_adapter.py` (full; Listing 22.3 from lines 55, 89-105; identity mapping 186-208; `_run` 221-262; factory 265-327)
- `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/langgraph.py` (lines 226-275 read directly; failure/interrupt handling verified)
- `adapters/nornyx-agentic-adapters/tests/test_enforcement.py` (full, 8 tests, lines 61-211)
- `adapters/nornyx-agentic-adapters/tests/test_crewai_adapter.py` (large excerpts: 1-210, 255-375, 489-718)
- `adapters/nornyx-agentic-adapters/docs/COMPATIBILITY.md` (lines 60-80: breaking-change classification of the enforce() ordering)
- `adapters/nornyx-agentic-adapters/README.md` (lines 1-205: coverage, assurance boundary, versioning; note the known truncated sentence at ~180, flagged in fact pack 03 §14.3 — I did not quote it)
- `examples/crewai_governance_benchmark/README.md` and `variant_governed.py` (denial-as-tool-result disclosure)
- Verified by grep over `src/`: no `load_authorizer`, `open(`, `read_text`, `Path(` (supports the no-file-I/O claim; matches fact pack T18)
- Verified by execution: `python -c "import nornyx, nornyx.agentic as a; ..."` → nornyx 1.11.0, SPI_VERSION "1.2"; imported `nornyx_agentic_adapters` from the source tree (base package imports without any framework installed)
