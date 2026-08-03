# Chapter 35 — Author notes

Chapter: "Mapping Controls to Standards" (Part VII).
Snapshot basis: repository `/home/user/nornyx` at git HEAD `70d2b40`, distribution 1.11.0.

## Claims I could not verify (and what I wrote instead)

1. **Standard-clause content.** Statements about NIST AI RMF functions, SSDF practice
   identifiers (PO.1, PS.1–PS.3, PW.7–PW.8), ISO/IEC 42001/23894/27001 clause families,
   SLSA's build track, zero-trust tenets, OWASP LLM/agentic risk names, and EU AI Act
   obligations are written at the level of the cited published documents from general
   knowledge of those documents; the chapter deliberately paraphrases rather than quotes
   and cites the bibliography keys. I dropped an initially drafted SSDF **RV.1** row
   (vulnerability response mapped to the no-go audit) during a length trim, retaining the
   supplier-practice point in Ch. 16's territory. EU AI Act statements are held to the
   framing the task message required: "described at the level of the published regulation
   and explicitly not as legal advice"; the chapter states this twice and Table 35.4's
   caveats repeat that scope/classification/sufficiency are legal determinations.
2. **No compliance claim.** Audited the chapter for verbs: no row or sentence asserts
   certification, conformity, satisfaction of an obligation, or legal sufficiency. The
   worked example's claim sentence is deliberately about a decision-engine property, not
   about Article 14.
3. **Listing 35.3** ("the row as an auditor would receive it") is captioned Illustrative;
   the artifacts it *names* are real and were produced live (see below).
4. **"Two rows have no implemented realization"** (Table 35.2 caption) — my own analysis
   of the table, not a repository statement.
5. **Figure 35.2 diagnostics** — `APPROVAL_NON_HUMAN`, `APPROVAL_ROLE_INVALID`,
   `APPROVAL_REVISION_MISMATCH`, `AN_APPROVAL_HUMAN_REQUIRED` verified in fact packs 01/02
   (engine order at `nornyx/agentic/authz.py:1012–1072`; static check at
   `nornyx/governance/agentic_network.py:646–657`). Evidence rule name
   "`approval_granted` requires actor_type human" verified (AN_EVT_APPROVAL_NON_HUMAN,
   `nornyx/agentic_evidence.py:724–745`).

## Verified live during writing (commands run against the pinned repo)

- `nornyx governance explain examples/agentic_network_support/support_network.nyx
  --as-of 2026-07-17T00:00:00Z --json` — Listing 35.2 is a genuine abridgment of this
  output (fields removed, none altered, except: I removed `denied_execution_surfaces`,
  `invalidation_conditions`, `requirements` decision row, `revision_binding: null`,
  `expires_at: null`, `resolution`, and the retained `sources[0].approval` body for
  length; the source hash `sha256:602ad00a…` is the real value).
- Listing 35.1 is verbatim from `examples/agentic_network_support/support_network.nyx`
  lines 104–118 (approvals block).

## PROPOSED-REF additions

None. All keys used exist in `design/05_bibliography.md`.

## Repository paths I personally verified (read directly)

- `examples/agentic_network_support/support_network.nyx` (approvals block, project block).
- `docs/decisions/ADR-0040-governance-assurance-tiers.md` (read in full — tier scoping,
  prohibited claims, "cannot award Tier 3").
- `nornyx/agentic_evidence.py` lines 80–100 and 1070–1103 (LIMITATIONS tuple, report
  fields including `limitations` and `safety`).
- `schemas/agentic_runtime_events_v1.schema.json` (event required fields, approver enum).
- Live `governance explain` output as above.

## Deliberate scope decisions

- Mapping direction (control → standard) is the chapter's organizing argument; the
  seven-field row anatomy (Table 35.1) is my synthesis, not from any standard.
- Three mapping tables + Table 35.1 = four tables, each with a caveats column, per brief.
- Word count kept near the upper bound because the brief requires nine standards families
  plus a worked example; tables carry the breadth so prose can carry the argument.
