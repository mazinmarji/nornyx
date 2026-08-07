# Chapter 6 — Author notes

Chapter: "Trust Zones and Boundaries" (Part II).
Snapshot basis: repository `/home/user/nornyx` at git HEAD `70d2b40`, distribution 1.11.0.

## Claims I could not verify (and what I wrote instead)

1. **Enforcement of the context taint/authority model.** This is the most important honest boundary
   in the chapter. The taint and authority model is implemented as *provenance metadata*: context
   packs carry per-file channel, taint, trust level, and authority rank, and embed three trust
   rules. But `nornyx/context_builder.py` states in the pack itself: "Authority rank is advisory
   metadata until a later enforcement goal." I wrote the callout to say exactly that, verbatim, and
   added the sentence "nothing in the current repository blocks a runtime from ignoring it." I did
   **not** claim taint enforcement anywhere.

2. **Whether zone declarations constrain a running system.** Trust zones, memberships, transitions,
   allowlists, and never-share lists are declarations validated statically, plus runtime checks in
   the cooperative authorization engine. I did not assert that a running framework is prevented
   from moving data across a zone boundary; §6.2's callout says explicitly that "what can be checked
   from them is structural" and defers the runtime claim to Chapters 10 and 11, and the
   `> **Assurance boundary.**` callout in §6.5 states the coverage limit directly.

3. **Ledger zone names and never-share categories.** `treasury-plan`, `treasury-data`,
   `payment-exec`, `audit-store`, and the never-share categories `account_credentials` / `full_pan`
   come from `design/03_case_study_bible.md` (Thread C), not from the repository. Nothing in the
   repo declares them. Figure 6.1 and Listing 6.1 are case-study material; Listing 6.1 is captioned
   "Illustrative — not drawn from the repository."
   - **Small extension flagged:** Listing 6.1's `never_share` list adds `credentials` and `secrets`
     to the bible's two categories, to illustrate §6.3's universal-prohibition argument. This is
     additive to the bible, not contradictory. If continuity editing prefers strict bible fidelity,
     drop the two extra tokens; nothing else in the chapter depends on them.

4. **"Zone classification `internal`" for `treasury-data`.** The seven classification values are
   verified from the schema; assigning `internal` to a bible zone is my modelling choice, not a
   repository fact.

5. **`AN_SENSITIVE_SHARE_BOUNDARY_MISSING`.** I read this diagnostic in
   `nornyx/governance/agentic_network.py` (~line 230) and confirmed it reports both missing
   mandatory never-share categories and sensitive categories appearing in sharing declarations. I
   chose **not** to name it in the chapter, because §6.3's argument (never-share must be non-empty)
   is carried by the schema's `nonEmptyIds` requirement, which is the cleaner citation. Logged here
   so a later editor knows the code exists if a callout wants it.

## PROPOSED-REF additions

None. All citations used (`nist-zta`, `beyondcorp`, `saltzer-schroeder`, `greshake-injection`,
`willison-injection`, `owasp-llm`, `owasp-agentic`, `hardy-confused-deputy`) are already in
`design/05_bibliography.md`.

## Repository paths I personally verified (read directly, not via fact pack)

- `/home/user/nornyx/schemas/agentic_network_v1.schema.json` — read the `trustZone` definition
  (lines ~102–133) and the `membership` definition (lines ~134–157). Confirmed: the seven
  classification enum values quoted in the chapter (`governed_local`, `internal`, `isolated`,
  `test`, `external`, `external_contract_only`, `contract_only`); that `never_share` uses the
  `nonEmptyIds` definition (`minItems: 1`) while `share_allowlist` and the gate-ref lists use the
  ordinary `ids` definition; `additionalProperties: false` on both records; and the membership
  status enum `authorized | suspended | revoked | expired` (note it differs from the identity
  status enum, which uses `active` — I checked this deliberately and used the membership wording in
  the callout).
- `/home/user/nornyx/nornyx/context_builder.py` — read lines 1–110 and 160–180. Confirmed
  `DEFAULT_TRUST_CHANNELS` and its four channels with their taints and `may_define_policy` flags
  (`repo` → `trusted_repo_file` false; `authoritative_repo` → `authoritative_repo_file` **true**;
  `user_prompt` and `external_web` → `untrusted` false); the three trust rules; and the verbatim
  pack rule quoted in the chapter, "Authority rank is advisory metadata until a later enforcement
  goal."
- `/home/user/nornyx/nornyx/governance/agentic_network.py` — read the share and gate checks:
  `AN_SHARE_CATEGORY_UNKNOWN` / `AN_SHARE_NOT_ALLOWED_SOURCE` / `AN_SHARE_NOT_ALLOWED_TARGET`
  (~lines 1590–1615), `AN_PROTOCOL_TRANSITION_NOT_ALLOWED` (~1319), and
  `AN_PROTOCOL_EGRESS_GATE_MISSING` / `AN_PROTOCOL_INGRESS_GATE_MISSING` (~1511, ~1521). The
  two-sided gate-declaration argument in §6.6 is derived from reading these two checks: the egress
  code fires when the gate is absent from the *source* zone's `egress_gate_refs` and the ingress
  code when it is absent from the *target* zone's `ingress_gate_refs`.
- `/home/user/nornyx/nornyx/agentic/authz.py` — read `_zone_crossing` and `_data_share`
  (~lines 1095–1160). Confirmed: an external destination classification with no supplied approval
  returns `DecisionEffect.APPROVAL_REQUIRED` with `DecisionCode.CROSSING_APPROVAL_REQUIRED`; an
  external crossing with **no governing gate at all** returns a deny (`ZONE_CROSSING_DENIED`), which
  is the claim in the §6.6 callout; and a data share naming any member of `SENSITIVE_CATEGORIES`
  denies with `SENSITIVE_SHARING`.

## Deliberate scope decisions

- No inline status badges; prose status wording only, per the pre-Chapter-16 rule.
- Prompt injection is treated as an authority-confusion *problem statement* here. Detection,
  filtering, and model-side mitigations are named and explicitly excluded from the guarantee
  structure rather than developed; the threat-model treatment belongs to Chapter 34.
- Thread C (Ledger) is introduced structurally only — zones, membership, separation of duties as a
  constraint. Delegation depth, escalation tiers, and evidence chains are left to Chapters 12, 31,
  and 34 as the book design assigns them.
