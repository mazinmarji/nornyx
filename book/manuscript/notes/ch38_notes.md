# Chapter 38 — Author notes

Chapter: "Limitations, Open Problems, and Research Directions" (Part VII).
Snapshot basis: repository `/home/user/nornyx` at git HEAD `70d2b40`, distribution 1.11.0.

## Claims I could not verify (and what I wrote instead)

1. **Opening scenario** contains no new case scene per the brief: it is a synthesis
   moment (merging the five existing thread registers). "Thirty-one entries" is fiction.
2. **Schneider's theorem** (§38.3): stated as "execution monitors enforce precisely the
   safety properties — violations detectable on a finite prefix of one execution — and
   cannot enforce liveness or cross-execution properties." This is the standard reading
   of [@schneider-enforceable]; the application to taint/information-flow ("fall outside
   the enforceable class in general") follows the same paper's discussion and matches
   Ch. 7's earlier treatment (see ch07_notes). The review-question classification answers
   are derivable from that statement.
3. **Happened-before age**: an early draft said "sixty years"; Lamport 1978 is 48 years
   before the book's 2026 present. Corrected in the final text to "nearly half a century
   old" (§38.3) and "decades-old" (Further reading).
4. **Object-capability claims** (§38.3): "a component holds exactly the capabilities
   passed to it, no ambient authority, attenuation as default" is the standard summary of
   [@miller-ocap]. "Current agent frameworks pass ambient credentials through environment
   variables" is a general industry observation, not a claim about CrewAI/LangGraph
   specifically or about the repository.
5. **Falsification list** (§38.4): each mechanical falsifier negates a verified
   repository claim: parser duplicate-key rejection (fact pack 01 §2.7), deterministic
   generation (verified live in fact pack 02), per-record lock digests (schema),
   evaluate-record-execute as a declared breaking-change boundary
   (`adapters/…/docs/COMPATIBILITY.md:70-72`, fact pack 03 §3), closed ordering model and
   AN_EVT_ATTEMPT_AFTER_SUCCESS (fact pack 02 §5.2), four-layer non-human approval
   refusal (fact pack 02 §7). The empirical "framing falsifier" is explicitly labeled a
   wager with no existing data.
6. **"Nine scattered places"** (§38.1 opening) — rhetorical count of limitation-statement
   locations (README, overview, security-boundaries doc, lock schema, lock doc, evidence
   doc, LIMITATIONS tuple, ADR-0040, adapter README); approximately right but not audited
   to exactly nine; phrased as rhetoric, not inventory.
7. **Ch. 37 cross-reference numbers** (nineteen-day latency, staff-engineer memo) reused
   from my own Ch. 37 fiction for continuity.

## Repository facts relied on (with sources)

- LIMITATIONS tuple quoted verbatim — `nornyx/agentic_evidence.py:87-92` (read directly;
  also reproduced in a live validation report I generated).
- Residual-risk sentences: "Adapter enforcement is cooperative; bypassing the adapter
  bypasses the hook"; "Evidence is supplied, not observed: omission and fabrication are
  outside Nornyx's proof surface"; "A cooperative producer can falsely claim a new
  occurrence…"; "The lock binds bytes, not producers" — `docs/agentic-network/
  08_SECURITY_BOUNDARIES.md` (fact pack 02 §10, quoted verbatim there).
- Non-goal list ("not a runtime control plane, policy proxy, agent orchestrator,
  observability backend, … identity provider, secrets manager, MCP runtime, A2A runtime,
  or deployment system") — `docs/agentic-network/00_OVERVIEW.md` (fact pack 02 §1).
- M2-D shim unpackaged/[Unreleased]/requires 1.11.0 — `integrations/nornyx_reference_
  adapters/governance_kernel.py:1-27`, `CHANGELOG.md` Unreleased (fact packs 02 §6.6,
  03 §8.2).
- Adapters 0.2.0 / Alpha / exact pins — fact pack 03 §1.1.
- Two-verb language: `normalize_policy_rules` recognizes only deny/require prefixes,
  other rules bucketed into require; five deny substring families; require → 
  `pending_evidence`, never executed — `nornyx/policy_runtime.py:83-108, 185-203,
  271-274`; `docs/05_SECURITY_MODEL.md:41-42` (fact pack 01 §2.5; also personally
  verified for Ch. 7 per ch07_notes — I re-checked the fact-pack citations only).
- "Differential chunks and multi-producer merging are not supported"; "does not solve
  distributed causality, cannot prove events across systems happened in the claimed
  order" — `docs/agentic-network/06_RUNTIME_EVIDENCE.md` (fact pack 02 §5).
- Authority rank advisory — `nornyx/context_builder.py:170` (fact pack 01 §2.4).
- "Identity resolution is binding, not authentication" — benchmark
  `REVIEWER_QUICKSTART.md` (fact pack 03 §7).
- No performance/adoption/enterprise/cost claims —
  `docs/agentic-network/10_BEFORE_AFTER_AND_POSITIONING.md` (fact pack 02 §1).
- `execution_mode: contract_only` / `live_connector_execution: false` schema constants —
  `schemas/agentic_network_v1.schema.json:181-182`.

## PROPOSED-REF additions

None. Brief-required citations (schneider-enforceable, lamport-clocks, in-toto,
miller-ocap) all exist; added saltzer-schroeder and sigstore from the bibliography.

## Repository paths I personally verified (read directly)

- `nornyx/agentic_evidence.py` (LIMITATIONS block and report constructor).
- `docs/decisions/ADR-0040-governance-assurance-tiers.md` (full read).
- `schemas/agentic_runtime_events_v1.schema.json` (envelope/oneOf structure).
- Live runs: generate → lock → SPI evaluate/record → evidence-validate --strict (pass),
  confirming the report's `limitations` and `safety` fields as described.

## Deliberate scope decisions

- No Case-study callout: Ch. 38 is not assigned to any thread in the book design, and
  the brief says "no new case scenes; synthesize the threads" — synthesis happens in the
  opening scenario and §38.5.
- One figure (DOT problems map) + one consolidated limitations table; the chapter is
  prose-heavy by design ("real seriousness rather than hedging").
- §38.4 (falsifying the book's own claims) is the brief's required section; the split
  into mechanical vs. framing falsifiers is mine.
