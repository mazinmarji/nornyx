# Chapter 39 — Author notes

Chapter: "Capstone: Designing the Complete Northstar System" (Part VIII).
Snapshot basis: repository `/home/user/nornyx` at git HEAD `70d2b40`, distribution 1.11.0.
All transcripts referenced were produced live in `/tmp/northstar` against the installed
`nornyx` 1.11.0 CLI; the built capstone workspace (contracts, manifest, lock, evidence)
is the shared basis for Chapters 39 and 40.

## Claims I could not verify (and what I wrote instead)

1. **`audit-store` as a trust zone.** The case-study bible lists four Ledger zones including
   `audit-store` (append-only). The built network contract declares three in-network zones
   (`zone.treasury_plan`, `zone.treasury_data`, `zone.payment_exec`); nothing in the
   agentic-network schema models an append-only store. I wrote that `audit-store` "is realized
   not as a network trust zone but as the evidence store itself, whose append-only property is
   a storage control **[guidance]**" — an explicit design decision rather than a fake feature.
   Similarly the bible's `audit-recorder` agent is presented as "realized as the
   evidence-recorder producer identity, not an agent" (Table 39.1 row).
2. **Zone naming.** The bible's canonical zone names use hyphens (`treasury-plan`); the built
   contract uses ids `zone.treasury_plan` etc. (the schema id pattern permits both). §39.4
   states the mapping explicitly ("encoded as ids `zone.treasury_plan`…") so prose and
   transcripts cannot be read as contradicting each other.
3. **Retention periods (7 years / 1 year)** in §39.6 are invented organizational figures,
   explicitly marked **[guidance]** with "no schema enforces a clock." No Nornyx retention
   mechanism exists; verified by absence in fact packs.
4. **Branch protection as Tier 3** (Forge merge row) is an argument about a GitHub platform
   control, not about Nornyx; marked as an "existing independent control" with the binding
   half labelled **[guidance]**. Northstar's GitHub conventions come from the bible.
5. **Escalation threshold (€50,000).** The engine has no amount semantics; §39.5–39.6 present
   thresholds as application-level capability selection ("enforced by the application code that
   classifies the case into a capability — a Tier 2 cooperative fact"), patterned on the real
   `propose_refund_under_limit` / `escalate_high_value_refund` split in
   `examples/agentic_network_support/support_network.nyx`. The €61,250 example amount is mine.
6. **Claim-register format** (Table 39.3, Listing 39.2) is the book's own design (introduced
   Ch. 13), captioned "Illustrative" where listed; every diagnostic/evidence item named inside
   entries is real and exercised in Ch. 40.
7. **Listing 39.1** is captioned "Built for this capstone in the shape of …" — the org-policies
   file and manifest are my constructions patterned on `nornyx/examples/org_policies.nyx` and
   the manifest format in `docs/USE_IN_YOUR_REPO.md:101–111`; rule strings are the canonical
   ones from `examples/governed_delivery_control_plane.nyx:62–69`. Both were actually checked
   (`nornyx check` pass; `workspace-check` pass/drift transcripts).

## Verified live (commands run for this chapter)

- `nornyx check` pass on `atlas/atlas.nyx`, `payments-api/forge.nyx`,
  `treasury-ledger/ledger.nyx` (the latter with `--as-of 2026-08-03T00:00:00Z`).
- Policy `ref` across sibling directories resolves offline and compiles to inline rules
  (generated `policy.yaml` shows the five canonical baseline rules).
- `nornyx workspace-check --manifest nornyx.workspace.yaml` → `"status": "pass"`, exit 0;
  after inlining-and-dropping `deny secrets_to_llm` in forge.nyx → repo-local `nornyx check`
  green, workspace status `drift` with `"missing": ["deny secrets_to_llm"]`, exit 1
  (the Charter callout's transcript, reproduced in Ch. 40).
- Ledger authoring diagnostics observed live: `AN_APPROVAL_DECLARED_ROLE_UNAUTHORIZED`,
  `AN_APPROVAL_MODULE_ROLE_OMITTED`, `AN_APPROVAL_ACCOUNTABLE_AUTHORITY_MISMATCH`,
  `AN_APPROVAL_ACTION_MISSING`, `AN_DELEGATION_*` gate/approval errors — basis for §39.6's
  module-authority lesson. Module role set verified against
  `nornyx/profiles_data/module_agentic_network_governance.yaml` (roles, `expires_after: P7D`).
- Lock `records` census (4 identities / 7 capabilities / 3 zones / 4 memberships / 2 gates /
  1 protocol target / 1 delegation / 1 handoff / 4 relations / 0 revocations) from the
  live-built `nornyx.agentic_network.lock`.

## Repository paths personally verified

- `nornyx/workspace.py` (module docstring, `check_workspace` statuses ok/missing/drift/
  contract_missing/synced, exit codes), `nornyx/parser.py:111–177` (ref semantics),
  `nornyx/examples/org_policies.nyx`, `nornyx/examples/governed_service.nyx`,
  `docs/CASE_STUDY_multi_repo_governance.md` (no cross-repo policy-ref by design),
  `docs/USE_IN_YOUR_REPO.md` (manifest format).
- `examples/agentic_network_support/support_network.nyx` (pattern for Ledger contract;
  capability/zone/approval shapes), `schemas/agentic_network_v1.schema.json` (non-empty
  `never_share`, closed schema), `schemas/agent_identities_v1.schema.json:74–75`
  (`authority` const `non_human`, `can_approve` const `false`),
  `schemas/agentic_capabilities_v1.schema.json` (required fields incl. `required_*_refs`).
- `nornyx/profiles_data/module_agentic_network_governance.yaml` (approval requirement,
  role authority, dependencies on `human_approval`).
- `examples/governed_delivery_control_plane.nyx` (rule strings, constitution, harness shape).
- `schemas/governance_exception_v1.schema.json` existence (exception record shape cited in
  the Charter callout).

## PROPOSED-REF

None. All citations use existing keys (`c4model`, `clark-wilson`, `saltzer-schroeder`,
`nist-ai-rmf`, `slsa`).

## Other editorial notes

- Word count by the build's table/code-stripping counter is ~4.3k; raw count including the
  three large tables and four listings exceeds 5k. The capstone brief allows 5,000–6,500;
  if the build counts stripped prose only, the chapter is at the low edge — flagging for the
  editor rather than padding.
- The DOT system-context figure uses only sanctioned node attributes; the `[extension]`
  gateway is dashed + double-bordered (untrusted-position + would-be-authoritative), stated
  in the caption.
