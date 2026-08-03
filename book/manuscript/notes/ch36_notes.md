# Chapter 36 — Author notes

Chapter: "Audit and Evidence Packages" (Part VII).
Snapshot basis: repository `/home/user/nornyx` at git HEAD `70d2b40`, distribution 1.11.0.

## Claims I could not verify (and what I wrote instead)

1. **All Atlas-audit artifacts (Listings 36.1–36.5) are Illustrative and captioned so.**
   They are Northstar fiction with field names verified against real schemas:
   - Listing 36.1: trust-zone fields (`id`, `classification`, `allowed_transition_targets`,
     `share_allowlist`, non-empty `never_share`, `ingress_gate_refs`, `egress_gate_refs`)
     against `schemas/agentic_network_v1.schema.json` §trustZone; `external_contract_only`
     is one of the seven real classification enum values. Approval fields mirror the real
     support-network approval block shape.
   - Listing 36.2: lock fields against `schemas/agentic_network_lock_v1.schema.json` and a
     lock I built live (see below); the caption discloses the abridgment (profile/modules/
     block_schemas/protocol_declarations/evidence_requirements elided).
   - Listing 36.3: `ApprovalAssertion` field set read directly from
     `nornyx/agentic/authz.py` (lines ~495–507): approval_ref, claimed_approver_ref,
     claimed_actor_type, role, granted, action_ref, subject_revision, issued_at,
     expires_at, evidence_refs. Note: `claimed_approver_ref` pattern in evidence events is
     the `id` pattern (`^[A-Za-z0-9][A-Za-z0-9._:-]*$`), so `user:priya.n` is
     pattern-valid.
   - Listing 36.4: event fields against `schemas/agentic_runtime_events_v1.schema.json`
     (approver {role, actor_type}, share_categories, evidence_artifact {path, sha256},
     occurrence {operation_id, occurrence_id, attempt}); the four binding fields are the
     real per-event required set.
   - The example revision `git:9f3c1a7d0b2e4f6a8c1d3e5f7a9b1c3d5e7f9a0b` is 40 hex chars
     (pattern-valid) and extends the case bible's canonical `9f3c1a7` short form. The
     bible assigns `9f3c1a7` to the Forge stale-approval scene; Chapters 11 and 13
     (already written) also use `git:9f3c1a7…` for Atlas contexts, so I followed the
     established manuscript usage for continuity.
2. **Digest values** in listings (`sha256:c41d8aa2…`, `sha256:88f0b3…`, `e3b58a1c…`) are
   fictional placeholders, always elided with `…`, never claimed to be computable.
3. **"The Atlas audit produced eleven [worksheet rows]"** — narrative fiction consistent
   with the question's clause count; not a repository fact.
4. **Producer version `0.2.0` for `crewai-adapter`** in Listing 36.4 matches the real
   adapter distribution version (fact pack 03) but the producer id string is fictional.
5. **SOC 2 connection** (§36.4) is written interpretively — structure of system
   description/criteria/tests/results and period bounding — with an explicit "nothing
   here is or substitutes for such an examination."

## Verified live during writing (commands run against the pinned repo)

- `nornyx agentic-network generate` on the support example → 10 artifacts, names as
  documented.
- `nornyx agentic-network lock … --out …` → real lock with the 16 top-level keys used in
  Listing 36.2's field selection; real `structural_checks` include four entries
  (delegation, foundation, evidence_integrity.v1, human_approval.v1 — note fact pack 02
  §4 lists only two; the live lock shows four because the composed modules add theirs; I
  used the live four in Listing 36.2).
- `load_authorizer` + `EvidenceRecorder.for_occurrences` + `record_occurrence_decision`
  → a 2-event explicit-mode stream; `nornyx agentic-network evidence-validate --strict`
  → `status: pass`, report contains `limitations` exactly as quoted and the 5-flag
  `safety` block. This validated the envelope/report shapes used throughout §36.3.
- `scripts/agentic_network_ci.py` read directly: audit-package assembly copies lock,
  eval report, both evidence reports, demo summary, artifacts tree, and writes
  `audit_manifest.json` with schema `nornyx.agentic_network_audit_package.v1` (lines
  247–268). Quoted in §36.2 and §36.6.

## PROPOSED-REF additions

None. (`merkle`, `lamport-clocks`, `in-toto`, `soc2`, `sre-book` all exist.)

## Repository paths I personally verified (read directly)

- `nornyx/agentic_evidence.py` (LIMITATIONS lines 87–92; report constructor 1078–1103).
- `nornyx/agentic/authz.py` (ApprovalAssertion dataclass; approval-check order per fact
  pack cross-check).
- `schemas/agentic_runtime_events_v1.schema.json` (read in relevant parts).
- `schemas/agentic_network_lock_v1.schema.json` via the live-built lock.
- `scripts/agentic_network_ci.py` (audit-package steps), `docs/agentic-network/11_REFERENCE_CI.md`.
- `examples/agentic_network_support/support_network.nyx` (approvals + governance_evidence).

## Deliberate scope decisions

- The seven-step chain is my formalization of the pipeline the repo's reference CI
  performs; the repo does not use the phrase "reconstruction chain."
- Step 2 (composition) is deliberately prose-only (no listing) since Ch. 35 just showed
  the effective-approval artifact; cross-referenced instead.
- Incident-response contrast confined to one Misconception box to avoid re-teaching Ch. 33.
