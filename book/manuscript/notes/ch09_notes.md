# Chapter 9 — Author notes

Chapter: "Approvals, Exceptions, and Human Accountability" (Part II).

## Repository paths personally verified (read directly, not only via fact packs)

- `/home/user/nornyx/nornyx/agentic/authz.py` — `_approval` (lines ~1012–1072): full check order,
  refusal codes, the `rejected()` helper emitting `approval_requested` + `approval_rejected`
  intents, earliest-applicable-expiry computation, future-issued fail-closed, `granted` checked
  last. Also `ApprovalAssertion` fields (~495–506), `_known_effective` / `PARTY_INEFFECTIVE`
  (~925–935), `load_authorizer` fail-closed taxonomy (~1166–1210), and the module docstring's
  boundary statement ("authenticates no approver", "reads no wall-clock time").
- `/home/user/nornyx/nornyx/governance/approvals.py` — `CORE_DENIED_ACTOR_TYPES` and the source
  comment "These categories are intrinsically unable to hold approval authority. Packs and
  documents cannot redeclare them as human actors." (lines 34–43); `is_non_human_authority`
  (44–59, 95–101); `APPROVAL_CORE_DENIED_ACTOR_ELIGIBLE` (~420–436); the composition
  `_ordered_union(..., CORE_DENIED_ACTOR_TYPES)` that re-unions core denials on every merge
  (~806–816).
- `/home/user/nornyx/nornyx/governance/agentic_network.py` — static approval checks
  (`AN_APPROVAL_HUMAN_REQUIRED`, `AN_APPROVAL_PRODUCER_OUTSIDE_MODULE_AUTHORITY`,
  `AN_APPROVAL_ROLE_INVALID`, `AN_APPROVAL_RECORD_INVALID`, `AN_APPROVAL_REVOKED`,
  `AN_APPROVAL_INTERVAL_INVALID`, `AN_APPROVAL_EXPIRY_EXCESSIVE`, `AN_VALIDATION_TIME_REQUIRED`,
  `AN_APPROVAL_NOT_YET_VALID`, `AN_APPROVAL_EXPIRED`, `AN_REVISION_MISMATCH`), and the identity
  invariant `AN_NON_HUMAN_APPROVAL_INVALID` (~1035–1042).
- `/home/user/nornyx/nornyx/agentic_evidence.py` (~715–745) — the grant-only scoping of the
  human-approver rules, including the verbatim source comment quoted in the chapter.
- `/home/user/nornyx/nornyx/governance/structural.py` — `CORE_NON_EXCEPTABLE_CONTROLS`
  (lines 28–38, incl. `ai_approver_denial`, `no_automatic_approval`, `pack_integrity`);
  `EXCEPTION_STATUSES` (83–91); SoD checks incl. `SOD_NON_HUMAN_APPROVER`, `SOD_SELF_APPROVAL`,
  `SOD_EVIDENCE_PRODUCER_SOLE_APPROVER` (~1170–1255); exception lifecycle incl.
  `EXCEPTION_SELF_APPROVAL`, `EXCEPTION_NON_HUMAN_AUTHORITY`, `EXCEPTION_EXPIRED`,
  `GOVERNANCE_TIME_REQUIRED`, `EXCEPTION_CLOSURE_EVIDENCE_MISSING`,
  `EXCEPTION_CORE_CONTROL_FORBIDDEN` (~1590–1800).
- `/home/user/nornyx/schemas/governance_exception_v1.schema.json` — the full required field set
  quoted in Listing 9.2, `renewal_policy` and `status` enums.
- `/home/user/nornyx/schemas/agent_identities_v1.schema.json` (lines 74–75) — `authority` const
  `non_human`, `can_approve` const `false`.
- `/home/user/nornyx/examples/agentic_network_support/support_network.nyx` (lines 104–118) —
  Listing 9.1, quoted verbatim.
- `/home/user/nornyx/nornyx/profiles_data/module_human_approval.yaml` (lines ~33–57) — the
  built-in module's `expires_after: PT24H`, `exact_revision_required: true`, six denied actor
  types, `timing: before_action` (source of the "24-hour expiry" used in the Northstar examples).

## Claims I could NOT verify, and what I wrote instead

1. **Revocation propagation at the runtime engine.** The engine's revocation handling that I read
   applies to *identities* (`PARTY_INEFFECTIVE` via `revocation_refs`), and the static checker has
   `AN_APPROVAL_REVOKED` for a revoked approval *record*. I did not find a runtime code path that
   consumes a revocation of an approval assertion mid-flight. The chapter therefore presents
   revocation as a general design requirement (Section 9.3, Table 9.1) with a Northstar example,
   and does not attribute an approval-revocation runtime mechanism to the repository. The only
   Nornyx-attributed revocation statement is the static `AN_APPROVAL_REVOKED` behavior, which I
   read in `agentic_network.py`.
2. **Approval interface requirements (Table 9.2).** No repository artifact defines an approval
   *interface*. The table is captioned "Illustrative synthesis, not drawn from the repository."
3. **Exception record contents (Listing 9.2).** Field *names* and enums are real
   (`governance_exception_v1.schema.json`); the values (`EXC-PAY-014`, the Northstar people and
   controls) are fictional. Captioned as illustrative values over the real required field set.
4. **Approval fatigue arithmetic.** The four-hour/eight-minute figures in Exercise 3 are
   pedagogical parameters, not measurements from any source, and are framed as assumptions.
5. **Legal framing.** ISO/IEC 42001 and the EU AI Act are cited as *interpretive* observations
   about how such regimes are constructed. The chapter states explicitly that this is not a
   compliance claim, per style-guide rule 5.
6. **Chapter cross-references.** Forward references to Chapters 13, 15, 29, 30, and 36 follow the
   book design's chapter list and case-study assignments; those chapters do not exist yet, so the
   content they are promised to carry is taken from `01_book_design.md` and
   `03_case_study_bible.md` rather than from written text.

## PROPOSED-REF additions

None. All citations used ([@rbac-nist], [@clark-wilson], [@iso-42001], [@nist-ai-rmf],
[@eu-ai-act], [@sre-book], [@saltzer-schroeder]) are existing keys in `05_bibliography.md`.

## Continuity decisions

- The stale-approval revision is `9f3c1a7`, per the case bible. I deliberately did not invent a
  second commit hash for the force-pushed head; the text says only "the head is now a different
  revision", which avoids adding a non-canonical SHA to the universe.
- Northstar's 24-hour approval expiry is used consistently in Sections 9.3 and the Forge callout,
  matching the built-in `module_human_approval.yaml` `expires_after: PT24H`.
- Per the writer instructions, no inline status badges appear (Chapter 9 precedes Chapter 16);
  Nornyx status is expressed in prose as "as implemented at the snapshot" / "in the repository at
  the book's snapshot".
