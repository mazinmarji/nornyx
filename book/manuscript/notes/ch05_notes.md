# Chapter 5 — Author notes

Chapter: "Identity, Capabilities, and Authority" (Part II).
Snapshot basis: repository `/home/user/nornyx` at git HEAD `70d2b40`, distribution 1.11.0.

## Claims I could not verify (and what I wrote instead)

1. **Unicode/identifier-confusability handling in identity comparison.** An early draft included a
   sentence asserting that a governance layer must declare the normal form under which it compares
   identifiers, and gestured at Nornyx's NFKC case-folding collision check
   (`AN_NORMALIZATION_COLLISION`). I verified the diagnostic exists
   (`nornyx/governance/agentic_delegation.py:166` per fact pack 02 §2.5), but Chapter 8 already
   owns that material and treats it as a canonicalization topic. **Removed the sentence entirely**
   rather than duplicate Chapter 8 or state a half-verified version.

2. **Framework-name resolution failure behavior.** I wrote that resolution failure "is a structural
   error, not a policy outcome" and "must fail closed rather than fall back to a default identity."
   The Nornyx-specific half is supported: `Authorizer.resolve_identity` raises
   `IdentityResolutionError` with codes `IDENTITY_UNKNOWN` / `IDENTITY_AMBIGUOUS`, and the source
   comment states resolution errors are "not a policy decision" (`nornyx/agentic/authz.py:788,453`,
   fact pack 02 §6.2). The general normative claim is my own design argument and is written as
   general-principles prose, not as a Nornyx claim.

3. **`max_delegation_depth` default when a capability omits it.** The delegation checker falls back
   to a constant named `DEFAULT_MAX_DELEGATION_DEPTH` (`nornyx/governance/agentic_delegation.py`,
   near line 600). I did **not** read the constant's value and therefore **did not state a default
   depth number anywhere**. The callout says only that a delegation whose `max_depth` exceeds what
   the capability permits raises `AN_DELEGATION_DEPTH_POLICY_EXCEEDED`, which I read directly.

4. **"Depth 2" in Figure 5.2.** The figure's depth bound of 2 is illustrative and framed as such
   (generic `identity.coordinator` / `identity.specialist` names, not case-bible names). The schema
   range 1–8 for `max_depth` and 0–8 for `current_depth` is verified; the specific value 2 is not a
   repository fact.

5. **Whether Atlas's capabilities are "low risk, no gate" in any shipped contract.** These come from
   the case-study bible (`design/03_case_study_bible.md`, Thread A), not from the repository. No
   Nornyx contract in the repo declares Atlas. The chapter never implies otherwise: Atlas material
   appears only in `> **Case study — Atlas.**` and in a listing captioned "Illustrative — not drawn
   from the repository."

## PROPOSED-REF additions

None. Every citation used (`saltzer-schroeder`, `lampson-protection`, `miller-ocap`,
`hardy-confused-deputy`, `rbac-nist`, `greshake-injection`) is already in
`design/05_bibliography.md`.

## Repository paths I personally verified (read directly, not via fact pack)

- `/home/user/nornyx/schemas/agent_identities_v1.schema.json` — read in full. Confirmed the closed
  identity record, the required-field list quoted in the chapter (`namespace`, `subject`,
  `identity_class`, `framework_bindings`, `capability_refs`, `status`, `valid_from`, `expires_at`,
  `revocation_refs`), `framework_bindings` `maxItems: 32` with `uniqueItems: true`, the status enum
  `active | suspended | revoked | expired`, and the two constants `"authority": {"const":
  "non_human"}` and `"can_approve": {"const": false}`.
- `/home/user/nornyx/schemas/agentic_capabilities_v1.schema.json` — read in full. Confirmed the
  required set (`name`, `actions`, `risk`, `scope_type`, `scope_refs`, `delegable`,
  `required_gate_refs`, `required_approval_refs`, `required_evidence_refs`), the risk enum
  `low | medium | high | critical`, `scope_type` as `{"const": "context"}`, `max_delegation_depth`
  bounded 1–8, `additionalProperties: false`, and the description sentence quoted verbatim in the
  chapter: "A declaration is not a runtime token, authority grant, command, script, credential, or
  approval."
- `/home/user/nornyx/schemas/agentic_network_v1.schema.json` — read the `delegation` definition
  (lines ~313–361). Confirmed the required-field list quoted in the callout, `max_depth` 1–8,
  `current_depth` 0–8, and `onward_delegation` restricted to `denied | allowed_with_policy`.
- `/home/user/nornyx/nornyx/governance/agentic_delegation.py` — read the attenuation and chaining
  checks (lines ~556–640, ~745–830, ~1095–1135). Confirmed by reading the code, not the fact pack:
  `AN_CAPABILITY_NOT_DELEGABLE`; `AN_DELEGATION_ACTION_ESCALATION` fires when delegated `actions`
  are not a non-empty subset of the capability's `actions`; `AN_DELEGATION_SCOPE_ESCALATION`
  likewise for `scope_refs`; `AN_DELEGATION_DEPTH_POLICY_EXCEEDED` for exceeding both the
  capability policy depth and the parent's `max_depth`; `AN_ONWARD_DELEGATION_DENIED` when the
  parent is not `allowed_with_policy`; and the chained-delegation subset re-checks. Also read the
  handoff check and confirmed the message string quoted verbatim in the chapter: "a handoff cannot
  grant authority" (`AN_HANDOFF_AUTHORITY_ESCALATION`, ~line 1113).
- `/home/user/nornyx/nornyx/agentic/authz.py` — read the module docstring (lines 1–26), the
  `DecisionEffect` / `DecisionCode` enums (lines ~399–443), and `_known_effective` / `_capability`
  (lines ~925–962). Used in Chapter 5 for the claim that identity effectiveness at `decision_at` is
  a distinct check (`PARTY_INEFFECTIVE`) and that capability allowance is basis-tagged as either
  `membership` or `delegation`.

## Deliberate scope decisions

- No inline status badges. Prose equivalents used throughout ("as implemented at the snapshot"),
  per the style guide's pre-Chapter-16 rule.
- Chapter 5 deliberately does **not** introduce trust zones beyond the single word "membership" in
  Figure 5.1 (forward-referenced to Chapter 6), does not teach approvals (Chapter 9), and does not
  teach composition (Chapter 8).
- The delegation-chain figure uses generic identity names rather than Thread C (Ledger) names,
  because Chapter 6 is where the bible introduces Ledger and Chapter 31 is where its delegation
  limits are worked out. Advancing Ledger here would have pre-empted both.
