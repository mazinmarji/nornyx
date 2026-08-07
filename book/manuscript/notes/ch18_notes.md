# Chapter 18 — Author notes

Snapshot basis: `/home/user/nornyx` at `70d2b40`, distribution 1.11.0. Every transcript in the
chapter was produced by running the installed `nornyx` CLI against copies of repository examples
placed under `/tmp/nyxbook/charter2/` and `/tmp/nyxbook/an/agentic_network_support/`. No repository
file was modified.

## Claims I could NOT fully verify (and what I wrote instead)

1. **How a *document-accurate* profiles lock is produced from the CLI.** `nornyx profiles resolve
   <name> --lock` takes a **profile name**, not a contract path, and locks only the packs that
   `compose_governance(profile_identity=name)` resolves — with no `project.modules` selection. When
   I generated a lock that way and then ran `nornyx check` on a module-selecting contract, the run
   failed with `PACK_LOCK_SET_MISMATCH` listing all five composed modules as "missing". To obtain a
   lock matching the document I had to compose through the public Python API
   (`compose_document_governance(doc, registry=…)` then `lock_for_packs([*comp.modules,
   comp.profile])` then `write_lock(...)`). The chapter therefore captions Listing 18.2 as produced
   "by composing … and writing the lock through the public governance API" and does **not** claim a
   single CLI command produces a document-accurate lock. **This is a real usability gap worth
   flagging to the editors**: readers following Exercise 3 will hit it. I chose not to editorialize
   about it in the chapter body beyond the accurate caption, but a footnote or an appendix-B entry
   may be warranted.

2. **`PACK_LOCK_REQUIRED` for organization-tier packs.** Verified by reading
   `nornyx/governance/composition.py:275–283` (the raise is unconditional when any selected pack has
   `provenance.source_tier == "org"` and no lock is supplied). I did **not** exercise it live,
   because doing so requires authoring an org-tier pack. The chapter states the rule without a
   transcript.

3. **`AN_LOCK_REVISION_MUTABLE`, `AN_LOCK_ARTIFACT_MISSING`, `AN_LOCK_ARTIFACT_UNEXPECTED`,
   `AN_LOCK_PROFILE_MISMATCH`, `AN_LOCK_MODULE_MISMATCH`, `AN_LOCK_SCHEMA_MISMATCH`,
   `AN_LOCK_CHECKS_MISMATCH`, `AN_LOCK_PROTOCOL_MISMATCH`, `AN_LOCK_APPROVAL_MISMATCH`,
   `AN_LOCK_EVIDENCE_MISMATCH`, `AN_LOCK_FORMAT_MISMATCH`, `AN_LOCK_MALFORMED`.** These are listed
   as a family from `docs/agentic-network/07_NETWORK_LOCK.md` and fact pack 02 §4; I observed only
   `AN_LOCK_ARTIFACT_MISMATCH`, `AN_LOCK_RECORD_MISMATCH`, and `AN_LOCK_SOURCE_STALE` live. The
   chapter enumerates the family and quotes transcripts only for the three I reproduced.

4. **"Test coverage" behind **[implemented]** badges.** I ran no part of the test suite. The badge
   definition set in Chapter 16 rests on the fact packs' per-behaviour test maps.

5. **Module catalogue wording.** Fact pack 01 §16 notes the tension between ADR-0031's "frozen at
   six" and the shipped seven modules. I wrote "Seven ship as built-ins" with a parenthetical
   explaining the foundational six plus the later agentic-network module, per the fact pack's own
   recommended wording. I verified the seven module files and their dependency edges directly.

6. **Whether `nornyx check`'s exit-1-on-lock-mismatch is intentional.** I verified the behaviour
   (Listing 18.3) and read `cmd_check` in `nornyx/cli.py` (lines 163–210), which folds governance
   diagnostics into the general error list and returns 1 whenever `has_errors` is true. The
   documented exit-code contract in `docs/GOVERNANCE_CLI_AND_API.md` reserves 2 for lock failures
   but is scoped to the *governance inspection surface* (`modules`, `governance`, `evidence`), which
   `check` is not. I described the difference factually and drew a CI lesson from it rather than
   calling it a defect.

## PROPOSED-REF additions

None. Citations used: `merkle`, `reproducible-builds`, `in-toto`, `sigstore`, `slsa`, `nist-scrm` —
all existing keys.

## Repository paths I personally read

- `nornyx/profiles_data/module_evidence_integrity.yaml` (read in full; Listing 18.1)
- All seven `nornyx/profiles_data/module_*.yaml` (parsed to extract the dependency and conflict
  graph quoted in §18.2)
- `nornyx/profiles_data/catalog.json` (via `nornyx profiles list` / `nornyx modules list`)
- `nornyx/governance/composition.py` — lines 20–30 (`MAX_COMPOSED_RULES = 2000`,
  `MAX_COMPOSED_BLOCK_SCHEMAS = 64`, `MAX_COMPOSED_STRUCTURAL_CHECKS = 64`), lines 60–180
  (`PACK_MONOTONICITY_CONFLICT` sites), lines 262–300 (`compose_governance`: dependency ordering,
  `PACK_DECLARED_CONFLICT`, `PACK_LOCK_REQUIRED`, `[*modules, profile]` ordering, `verify_lock`)
- `nornyx/cli.py` — `cmd_check` (163–215), `cmd_profiles` incl. the `resolve --lock` path
- `schemas/profiles_lock_v1.schema.json` (read in full; the `$comment` quoted in §18.3)
- `schemas/effective_governance_v2.schema.json` (title and the fifteen required keys)
- `schemas/governance_evidence_v1.schema.json` (read in full; the required record fields listed in
  §18.1)
- `docs/GOVERNANCE_CLI_AND_API.md` lines 1–120 (command table, discovery order, lock bounds
  512 KiB / strict UTF-8 / duplicate-key rejection, exit-code table, deprecation policy)
- `docs/agentic-network/07_NETWORK_LOCK.md` (read in full; the nine bound classes, the
  lock-check detection list, and the verbatim "What the lock is not" paragraph)
- `docs/agentic-network/00_OVERVIEW.md` ("Honest limits")
- `examples/governance_foundations.nyx` (read in full; the Charter base contract)
- `examples/agentic_network_support/support_network.nyx` (trust zones, delegations, handoffs,
  approval block; edited only in the `/tmp` copy)
- `examples/agentic_network.nyx` (governance-evidence block shape)

## Commands executed (all under `/tmp/nyxbook/`)

Profiles/composition:
- `nornyx profiles list --json`, `nornyx modules list --json`
- `nornyx init --name NorthstarCharter --profile regulated --out charter.nyx`, then adding three
  modules → `nornyx governance resolve charter.nyx --json` → `status: fail` with
  `GOVERNANCE_REQUIRED_BLOCK_MISSING` ×3, `RULE_PATH_MISSING` ×2, and eight `APPROVAL_*`
  diagnostics. (Used to establish that module selection imposes real obligations; not quoted
  verbatim in the chapter to keep the listing count within budget.)
- Copied `examples/governance_foundations.nyx` + `examples/governance_evidence/` →
  `nornyx check charter.nyx` → passed, exit 0, with module-contributed top-level blocks suppressed
- Composed via the public API and wrote `nornyx.profiles.lock` (six entries: `minimal` +
  `evidence_integrity`, `human_approval`, `separation_of_duties`, `exception_management`,
  `change_control`) — confirms dependency-order composition from one declared module
- Tampered one `content_hash` → `nornyx governance resolve` → `PACK_LOCK_MISMATCH`, **exit 2**;
  `nornyx check` → same code as an error plus four re-surfaced `UNKNOWN_TOP_LEVEL_BLOCK` warnings,
  **exit 1** (Listing 18.3)
- Stale-lock case → `PACK_LOCK_SET_MISMATCH`, exit 2

Agentic network:
- `nornyx check support_network.nyx --as-of 2026-07-17T00:00:00Z` → passed
- `nornyx agentic-network generate … --out gen --as-of 2026-07-17T00:00:00Z` → `artifact_count: 10`
  with the exact filename list quoted in Listing 18.5
- Regenerated into `gen2` (same `--as-of`) and `gen3` (`--as-of 2026-07-20T09:31:44Z`); `diff -r`
  clean against `gen` in both cases; `grep -c` confirmed zero `generated_at`/`timestamp` occurrences
  in all ten artifacts
- `nornyx agentic-network generate … --as-of 2026-08-03T00:00:00Z` → `AN_APPROVAL_EXPIRED`,
  four `EVIDENCE_STALE`, `APPROVAL_EXPIRED`, exit 1 (Listing 18.4, verbatim)
- `nornyx agentic-network lock …` → `lock_digest: sha256:fe71adc9…`, `artifact_count: 10`;
  `lock-check` → `status: pass`, empty diagnostics (Listing 18.5)
- Tamper 1 (edited `never_share` inside `gen/trust_zone_map.json`) → single
  `AN_LOCK_ARTIFACT_MISMATCH`, exit 1
- Tamper 1b (weakened `never_share` in the *contract*) → the static check fires first with
  `AN_SENSITIVE_SHARE_BOUNDARY_MISSING`, before lock verification. Not used in the chapter, but it
  is why I chose a governance-neutral string edit for Tamper 2.
- Tamper 2 (changed one delegation `purpose` string) → ten `AN_LOCK_ARTIFACT_MISMATCH`, one
  `AN_LOCK_RECORD_MISMATCH` (`records.delegations`), one `AN_LOCK_SOURCE_STALE`, exit 1
  (Listing 18.6)
- Tamper 3 (regenerate + re-lock over the edited contract) → both `lock` and `lock-check` pass with
  a **new** digest `sha256:95a5aa79…` (Listing 18.7) — the demonstration of the hostile-local-writer
  limit

## Editorial notes

- The chapter's central analytical move (integrity ≠ authenticity ≠ authorization, Table 18.1) is
  original framing built on the repository's own verbatim disclaimer; the disclaimer is quoted
  exactly and attributed to `docs/agentic-network/07_NETWORK_LOCK.md` and the lock schema
  description.
- Review question 1 asks the reader to derive the `architecture_conformance` closure; the correct
  answer from the verified dependency graph is six modules in the order `evidence_integrity`,
  `human_approval`, `separation_of_duties`, `exception_management`, `change_control`,
  `architecture_conformance`.
- Chapter 8 is the conceptual owner of composition; this chapter cross-references rather than
  re-deriving merge/override/narrow, monotonicity, and canonicalizer versioning.
- The five-level inheritance engine is labelled an architectural extension and deferred to
  Chapter 32, per the case-study bible's instruction not to resolve Thread E's extension machinery
  as if it shipped.
