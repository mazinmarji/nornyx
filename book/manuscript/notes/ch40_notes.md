# Chapter 40 — Author notes

Chapter: "Capstone: Implementation, Verification, and Assurance Review" (Part VIII).
Snapshot basis: repository `/home/user/nornyx` at git HEAD `70d2b40`, distribution 1.11.0.
Every transcript in the chapter was produced live in `/tmp/northstar` (the Ch. 39 build)
unless the text says "repository-tested." Key digests appearing in the chapter are the real
ones from the build: contract digest `sha256:70119e9361c0…`, lock digest
`sha256:44f0cfb0928b…`, subject revision `git:9f3c1a7e0b4d2c8f6a1b3d5e7f9a0c2e4b6d8f01`.

## Claims I could not verify (and what I wrote instead)

1. **F5 (unsupported async call) was NOT executed here** — CrewAI/LangGraph are not installed
   in this environment. The chapter says so three times (§40.2, F5, Table 40.1 caption) and
   rests the row on (a) the machine-readable coverage inventory
   (`crewai_adapter.py:118–183`) and (b) the repository test
   `test_async_arun_fails_closed_and_records_nothing` (`tests/test_crewai_adapter.py:690`,
   run in CI against real `crewai==1.15.4` with a zero-skip gate). The
   `MissingOptionalDependencyError` transcripts shown ARE live output.
2. **`make_governed_tool` / `make_governed_node` described, not executed.** §40.2 describes
   their behavior from the source (paths cited) and the fact packs; the executed object is
   `enforce()` plus `SurfaceBinding`/`validate_binding`/`AdapterDenied` from the real
   `nornyx_agentic_adapters` 0.2.0 source tree (imported via its `src/` layout — the package
   is not pip-installed here; behavior identical, noted for reproducers).
3. **Listing 40.3's recorder** is legacy occurrence mode (default `EvidenceRecorder`
   constructor; `enforce()` uses `record_decision`), while §40.3's 19-event baseline uses
   `for_occurrences` explicit mode. Both validated `pass`. The chapter does not claim
   `enforce()` records explicit occurrences.
4. **Reconstruction time "eleven minutes"** in §40.5 is narrative color for the fictional
   review, not a measurement; flagged here since it could read as one.
5. **F2's static-layer code `AN_REVISION_MISMATCH`** is cited from fact pack 02
   (`nornyx/governance/agentic_network.py:640`) and named only as "the same boundary exists
   statically"; the codes I personally triggered for F2 are `APPROVAL_REVISION_MISMATCH`
   (engine), `AN_APPROVAL_EXPIRED` + `EVIDENCE_STALE` (`--as-of` past expiry, exit 1) and
   `AS_OF_INVALID` (malformed `--as-of`, exit 2).
6. **F8's second diagnostic**: the traversal path also fails JSON-schema validation, producing
   a verbose `AN_EVT_SCHEMA_INVALID` alongside `AN_EVT_ARTIFACT_MISSING`; the chapter says
   "alongside a schema rejection of the traversal-shaped path" without quoting the (very long)
   schema error. Both were observed live.
7. **Table 40.2 NS-FORGE-001 row**: the branch-protection audit log is platform-owned and
   was not (cannot be) exercised in this build; marked **[guidance]** in the row.

## Failure-injection transcript inventory (all live unless noted)

- **F1**: edited committed `payments-api/.nornyx/policy.yaml` (removed one deny). Regenerated
  `AGENTS.md` byte-identical (diff clean) — reproducing the historical under-checking defect
  (`docs/CASE_STUDY_multi_repo_governance.md`, Bug 2). `nornyx drift` JSON: all `ok` except
  `policy.yaml` `changed`; exit 1.
- **F2**: engine denial `APPROVAL_REVISION_MISMATCH` with reason string quoted verbatim from
  output (matches `nornyx/agentic/authz.py:1030–1035`); `--as-of 2026-08-11` →
  `AN_APPROVAL_EXPIRED`, `EVIDENCE_STALE`, exit 1; `--as-of "2026-08-03 09:00"` →
  `AS_OF_INVALID`, exit 2.
- **F3**: duplicated `{crewai, planner}` binding → `AN_IDENTITY_BINDING_DUPLICATE` (error,
  exit 1); `load_authorizer` on that contract → `AuthorizerLoadError` code `CONTRACT_INVALID`;
  on healthy contract `resolve_identity("crewai","rogue_agent")` and `("autogen","planner")`
  → `IdentityResolutionError` `IDENTITY_UNKNOWN`. (`IDENTITY_AMBIGUOUS` is cited from
  `nornyx/agentic/authz.py:790–800` / fact pack 02, not triggered — a duplicate binding cannot
  reach resolution because the contract fails validation first; the chapter's wording "a
  genuinely ambiguous key would raise" is conditional for this reason.)
- **F4**: duplicated `capability_allowed` with new event_id/sequence/timestamp →
  `AN_EVT_REPLAY` ("Event content replays an earlier event."), strict exit 1. Report
  `limitations` and `safety` blocks captured; limitations quoted verbatim in §40.5's
  reconstruction discussion.
- **F6**: direct call transcript real; ledger method modeled on
  `examples/crewai_governance_benchmark` (README §"side-effect ledger", scenario S15).
- **F7**: hostile bundle authored for this build (README claims vs postinstall hook,
  `curl … | sh` in setup.js, MCP filesystem server at "/"). Live scan output:
  `risk_tier: critical`, 10 findings, `package_payload_executed: false`; report excerpts
  quoted from the generated `hook_risk_review.md`, `command_risk_report.md`,
  `mcp_risk_review.md`, `claim_vs_evidence_report.md`. The scoped permitted claim sentence is
  printed by `nornyx/package_scanner.py:983`.
- **F8**: valid `evidence_artifact` (correct relative path + sha256) → `pass`; path rewritten
  to `../northstar-governance/org_policies.nyx` → `AN_EVT_ARTIFACT_MISSING` with message
  quoted verbatim.

## Repository paths personally verified

- `nornyx/agentic/authz.py` — request dataclasses (460–560), `_approval` order (1012–1072),
  `EvidenceRecorder` (1214–1396), `record_occurrence_*`/`stream`/`validate` (1506–1690),
  `DecisionEffect`/codes; SPI_VERSION 1.2.
- `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/` — `__init__.py` (`__all__`,
  0.2.0), `enforcement.py` (enforce sequence), `binding.py`, `coverage.py`,
  `crewai_adapter.py` (governed `_run`, COVERAGE_INVENTORY), `langgraph.py`
  (make_governed_node, coroutine rejection, attempt offsetting).
- `nornyx/agentic_artifacts.py` (artifact set, lock build/verify codes),
  `nornyx/agentic_evidence.py` (replay fingerprint comment 391–396, artifact containment
  746–781, LIMITATIONS 88–92), `nornyx/repo_drift.py`, `nornyx/workspace.py`,
  `nornyx/package_scanner.py` (detectors, redaction, permitted-claim string),
  `scripts/agentic_network_ci.py` existence + `docs/agentic-network/11_REFERENCE_CI.md`.
- Live lock-check failure corpus (not all shown in chapter): semantic contract edit →
  `AN_LOCK_SOURCE_STALE` + `AN_LOCK_RECORD_MISMATCH` (trust_zones) +
  `AN_LOCK_ARTIFACT_MISMATCH` ×10, exit 1.

## PROPOSED-REF

None. Citations: `swebok-testing`, `schneider-enforceable`, `in-toto`, `merkle`,
`nornyx-repo`.

## Other editorial notes

- The chapter has 6 listings, 2 tables, 1 figure (sequence) plus the two unnumbered inline
  transcript blocks folded into Listing contexts; if the build requires every fenced block
  numbered, the two short blocks in §40.2 (MissingOptionalDependencyError) and F6 can be
  merged into their surrounding listings' captions.
- Stripped-prose word count ~4.5k; raw count with transcripts/tables well above 5k (same
  counting caveat as Ch. 39; flagged for the editor).
