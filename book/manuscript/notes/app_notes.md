# Appendix Writer Notes (Appendices A–G)

Author: appendix writer, audited at repository revision `70d2b40ad792`, distribution 1.11.0.
Everything asserted in Appendices A–G was verified against the fact packs
(`book/factpack/01–04`), the repository source, or a live `nornyx` command run. This file lists
what could **not** be verified (and what was written instead), verification methods, and residual
caveats per appendix.

## Live verification performed for these appendices

- `nornyx --help` plus `--help` for every subcommand and sub-subcommand (full flag surface in
  Appendix B was read from the installed CLI, not from docs).
- `nornyx check` on every bundled `.nyx` example (results recorded; six bundled files fail check —
  intentionally per their extension status — and are not presented as passing anywhere).
- `nornyx check examples/agentic_network_support/support_network.nyx` fails at the current date
  (`AN_APPROVAL_EXPIRED`, `APPROVAL_EXPIRED`, 4× `EVIDENCE_STALE`) and passes with
  `--as-of 2026-07-17T00:00:00Z`. Reported honestly in Appendix E.5 as the expiry machinery working.
- `nornyx agentic-network generate` on the support contract: `"artifact_count": 10`, artifact names
  as listed in Appendix B.7.
- Illustrative contracts (Atlas, Forge, Ledger, workspace pair) written under
  `/tmp/nyxbook/` and validated: Atlas exit 0; Forge exit 0 plus `generate` + `drift` pass, and
  drift exit 1 after a one-character edit to generated `policy.yaml`; Ledger exit 0 with two
  `UNKNOWN_TOP_LEVEL_BLOCK` warnings unprofiled, exit 1 with 19 diagnostics / 14 distinct codes
  under `profile: agentic_network` (codes listed verbatim in Appendix E.10); workspace-check
  drift report with `missing: ["require human_approval_before_merge"]` exactly as printed in E.11.
- `nornyx package validate` on `register_existing.nyx` (pass) and `invalid_ai_tool_approver.nyx`
  (exit 1, `INVALID_APPROVER_EXECUTION_SURFACE`, message quoted verbatim in E.6).
- `nornyx profiles list --json` and `nornyx modules list --json` (13 profiles, 7 modules, module
  dependency chain quoted in B.6).
- Python surfaces read from the installed package: `nornyx.__all__` (6 names),
  `nornyx.governance.__all__` (34 names), `nornyx.agentic.__all__` (46 names), plus
  `inspect.signature` on `load_authorizer`, `EvaluationContext`, `ApprovalAssertion`,
  `RuntimeOccurrence`, `Decision`, and all `EvidenceRecorder` methods.
- Diagnostic code inventories extracted by `grep` over `nornyx/` for each namespace
  (`PACK_*` 42, `RULE_*` 9, `GOVERNANCE_*` 5, `APPROVAL_*` 47, `EVIDENCE_*` 16, `SOD_*` 20,
  `EXCEPTION_*` 23, `CHANGE_*` 25, `ARCH_*` 28, `AN_LOCK_*` 18, `AN_EVT_*` 50, `AN_ARTIFACT_*` 6,
  AN static ~160). Counts stated in Appendix C match these extractions.
- Schema properties (closed/open, `$id`, schema-identifier constants, required fields, item
  bounds) read programmatically from all 42 files under `schemas/`; every file confirmed listed in
  Appendix D (mechanical diff against `ls schemas/` — zero missing).

## Could not verify / deliberately not asserted

1. **PyPI live state.** Whether `nornyx` 1.11.0 or `nornyx-agentic-adapters` 0.2.0 are actually
   live on the package index cannot be established from the repository. Appendices avoid any "on
   PyPI" claim; B.11 says "separate distribution … 0.2.0" (repo fact) only.
2. **Trademark/naming.** No formal clearance exists; nothing in the appendices implies one.
3. **Exit codes for internal commands.** The 0/1/2 contract is documented only for governance
   surfaces (`docs/GOVERNANCE_CLI_AND_API.md`). For internal commands, exit behaviour in Appendix
   B tables was read from the `cmd_*` handlers in `nornyx/cli.py` (return statements verified per
   handler), and those rows are marked Internal rather than Documented. I did not execute every
   failure path of every command.
4. **Per-code exit attribution in Appendix C.** For large families (AN static, `SOD_*`,
   `EXCEPTION_*`, `CHANGE_*`, `ARCH_*`) the "error, exit 1" attribution follows the family's
   documented level and the governance exit contract; I did not trigger each code individually.
   Fact pack 01's caveat about `nornyx/governance/structural.py` line numbers applies — no line
   numbers into that module are cited in the appendices.
5. **`AN_DELEGATION_*`/`AN_HANDOFF_*` generated gate codes.** `AN_DELEGATION_GATE_REQUIRED`,
   `AN_DELEGATION_APPROVAL_REQUIRED`, `AN_DELEGATION_EVIDENCE_REQUIRED` were observed live in the
   Ledger check output; the handoff-prefixed variants (`AN_HANDOFF_APPROVAL_REQUIRED`,
   `AN_HANDOFF_EGRESS_GATE_MISSING`, etc.) were verified as f-string compositions at
   `nornyx/governance/agentic_delegation.py:255-355` with the `AN_HANDOFF` prefix bound at lines
   1260/1269, but not each observed in a live run. Appendix C labels them "generated prefixes".
6. **Adapter-side test names.** All test names cited in Appendix F were verified by grep of
   `adapters/nornyx-agentic-adapters/tests/` (`def test_...` lines). The tests were not executed
   (per writer instructions: no `pip install`; extras not installed here).
7. **Benchmark numbers.** No measured benchmark/demo figures (scenario counts, event counts) are
   quoted in the appendices — fact pack 03 notes stale README rows, so those numbers were left to
   the chapters that can carry the caveat.
8. **Module count wording.** Following fact pack 01 §16, appendices say "seven modules — the six
   frozen foundational ones plus the agentic-network module" (B.6), never "six modules".
9. **`AN_APPROVAL_NOT_YET_VALID` / `AN_VALIDATION_TIME_REQUIRED`** were dropped from the C.6
   approval-record representative list during trimming; both exist in
   `nornyx/governance/agentic_network.py` (verified by grep) and the row is labelled
   representative, so no accuracy loss.

## Per-appendix caveats

- **A (3,607 words).** Slightly over the 3,500 aim; the agentic-network record-type table is the
  irreducible bulk. Field lists in Table A.2 are explicitly framed as "fields the toolchain reads,
  not an exhaustive permitted set" because block interiors are open. The `on:` string-key nuance,
  the `require`-bucketing trap, and the advisory-authority limitation are all stated with sources.
- **B (3,342 words).** Stability markers (Documented / Internal / Research) are my editorial
  classification built from `docs/GOVERNANCE_CLI_AND_API.md`, `docs/public-boundary-policy.md`
  (explicitly noted as content-, not API-, policy), fact pack 04 §5, and `docs/02_ARCHITECTURE.md`.
  "`nornyx governance analyze` does not exist" is quoted per instruction.
- **C (4,062 words).** Over the aim even after two trim passes; the appendix is table-dominated
  and further cuts would drop real codes. Coverage statement at the top says exactly which
  families are complete (`PACK_*`, `RULE_*`, `GOVERNANCE_*`, `EVIDENCE_*`, `AN_LOCK_*`,
  `AN_ARTIFACT_*`, `AN_EVT_*`, command-level) and which are sampled (`APPROVAL_*`, `SOD_*`,
  `EXCEPTION_*`, `CHANGE_*`, `ARCH_*`, AN static families).
- **D (2,710 words).** All 42 schema files covered (mechanically verified). "Primary consumers"
  were established by grepping each schema filename/identifier across `nornyx/**/*.py` and
  `nornyx/profiles_data/*.yaml`; for `product_lifecycle_extension` and `requirement_triage_matrix`
  the consumer is named from the module whose docstring claims it (no direct filename reference in
  code — schema-shape validation is inline).
- **E (2,585 words).** 11 examples: 7 bundled (delivery control plane; org-policy ref pair;
  release guardrails; email triage; support network; governed-package registration; architecture
  governance) + 4 illustrative (Atlas, Forge, Ledger fragment, Charter workspace manifest). Every
  illustrative one was checked under /tmp and its results — including the intentional Ledger
  failure — are reported in the text. All bundled quotes re-verified against current file line
  numbers (release_guardrails 55-61; register_existing 41-75; support_network 211-219/326-332).
- **F (2,970 words).** 53 checkbox rows across 9 tables. The "five tests per wrapped surface"
  grouping is my editorial synthesis of the adapter test suites and ADR-0040 claim eligibility —
  the repository does not itself publish a numbered five-test list; every row cites a real test
  name or document. The `CoverageInventory` export gap (no published artifact) is stated per fact
  pack 03 §14.6.
- **G (3,572 words).** 101 checkbox rows across 9 sections plus the eight-questions table. All
  mechanism claims trace to fact packs; **(residual)** markers flag limitations the repository
  itself documents (advisory authority rank, lock regeneration, producer honesty, no approver
  authentication). The eight questions are quoted from the book design verbatim as question stems.

## Style compliance notes

- Appendices are reference-style by design (permitted for appendices); no opening scenario /
  review questions / exercises skeleton, no figures. Tables and listings are numbered per
  appendix (`Table A.1`, `Listing E.3`, …) with bold caption paragraphs.
- No index spans were added (`<span class="ix">`): the existing appendices H and J contain none,
  and the writer-instruction index quota is stated per *chapter*. Flagging for the editor in case
  appendices should carry index terms too.
- No `[@key]` citations used: appendices cite repository paths directly, consistent with
  Appendix J's practice. No PROPOSED-REF entries needed.
- Abbreviations expanded at first use per file (SPI, MCP, A2A, PDP-adjacent terms avoided where
  not needed).
- Internal/experimental surfaces marked per instruction (Appendix B markers; Appendix D "local"
  namespace note; M2-D shim consistently described as merged, unpackaged, unreleased).

## Repository paths personally verified (principal ones)

`nornyx/cli.py` (subcommand tree, handlers, exit paths, `_resolve_as_of`), `nornyx/checker.py`
(block sets, relation rules, diagnostics, version check), `nornyx/parser.py` (`ref` resolution,
safe loader), `nornyx/policy_runtime.py` (rule normalisation, deny matcher, capability defaults),
`nornyx/context_builder.py` (trust channels, advisory-rank string), `nornyx/path_security.py`,
`nornyx/generator.py`, `nornyx/repo_drift.py`, `nornyx/workspace.py`, `nornyx/governed_package.py`
+ `nornyx/package_scanner.py` (code inventories), `nornyx/agentic/authz.py` (enums, signatures,
SPI version, approval order), `nornyx/agentic_evidence.py` + `nornyx/agentic_artifacts.py` (code
inventories), `nornyx/governance/agentic_network.py` + `agentic_delegation.py` (AN static codes,
gate-prefix composition), `nornyx/governance/approvals.py` (core denied actor types),
`nornyx/profiles_data/*` (catalog, module block schemas), all 42 files in `schemas/`,
`adapters/nornyx-agentic-adapters/` (pyproject, `__init__`, `enforcement.py`, `binding.py`,
`coverage.py`, `metadata.py`, `crewai_adapter.py`, `langgraph.py`, README, tests),
`docs/GOVERNANCE_CLI_AND_API.md`, `docs/public-boundary-policy.md`,
`docs/decisions/ADR-0040-governance-assurance-tiers.md`, `examples/` (all quoted contracts with
line numbers), `nornyx/examples/` (org pair, release guardrails).
