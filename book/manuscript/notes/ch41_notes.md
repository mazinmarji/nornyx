# Chapter 41 — Author notes

Chapter: "Lessons, Trade-offs, and Future Architecture" (Part VIII).
Snapshot basis: repository `/home/user/nornyx` at git HEAD `70d2b40`, distribution 1.11.0.

## Claims I could not verify (and what I wrote instead)

1. **All cost figures are fictional accounting.** "Two engineer-weeks," "sixty percent,"
   "a day or two," "an engineer-day per quarter," and the lapsed-approval-over-a-holiday
   anecdote are the fictional Northstar team's ledger. §41.2 opens with "Where a number
   appears, it is the capstone team's own accounting — illustrative of magnitude, not a
   benchmark," and the closing Assurance boundary repeats that the figures are "one team's
   accounting." The *mechanisms* generating each cost are all real and verified
   (module-authority diagnostics, `P7D` expiry, `==1.15.4`/`==1.2.2` import-time pins,
   exit-code gates).
2. **The `P7D` lapse anecdote** is consistent with the module's real `expires_after: P7D`
   (`nornyx/profiles_data/module_agentic_network_governance.yaml`) and the engine's
   earliest-applicable-expiry logic (`authz.py:1053–1063`), but the holiday story is
   narrative.
3. **§41.4 and §41.5 are entirely [extension]/design** — gateway, projection compiler,
   authenticated producers, hierarchy engine, evidence interchange. Each is explicitly
   badged, and the one repository anchor used is real: the evidence schema's
   `external_runtime` producer type and `signature_ref` field exist while the docs state the
   affordance "confers no Tier-3 assurance" (recorder docstring, `authz.py:1229–1230`;
   `docs/agentic-network/08_SECURITY_BOUNDARIES.md` residual-risk list). The three
   "claims Northstar cannot currently write" are marked as what would *become possible*.
4. **The Charter refusal callout** attributes to the toolchain's maintainers the decision to
   decline a cross-repo language feature — verified verbatim in
   `docs/CASE_STUDY_multi_repo_governance.md` ("Deliberately **not** done: a language-level
   `policy-ref`…"). The Northstar side (owner/reasoning/revisit condition documented) is
   fictional practice.
5. **Trajectory claims** ("moving toward boring, contractual infrastructure") are the
   author's synthesis, cited to framing sources (`nist-ai-rmf`, `slsa`) rather than asserted
   as fact about the industry.
6. **Overgovernance symptoms** (§41.3) are engineering judgment, not measured phenomena;
   the Assurance boundary says "the exemption tests are engineering judgment, not
   measurements."

## Repository facts relied on (verified)

- Fail-closed inventory in §41.1 ("undeclared capabilities deny; unresolvable identities
  refuse to load; malformed timestamps exit 2; stale lock stops the authorizer; missing
  framework dependency raises at import") — each verified live in the Ch. 40 build or
  against `nornyx/policy_runtime.py` (deny-unless-declared), `nornyx/cli.py` (AS_OF_INVALID
  exit 2), `authz.py` (load stages), `_compat.py`/adapter import gates.
- Proof-boundary strings embedded in every validation report — `nornyx/agentic_evidence.py:
  88–92`, observed in live reports.
- Unrepresentable danger states — `schemas/agent_identities_v1.schema.json:74–75`;
  non-empty `never_share` in `schemas/agentic_network_v1.schema.json`.
- Exact pins enforced at import — `adapters/.../pyproject.toml:26–28`,
  `crewai_adapter.py:66–105`, `langgraph.py:45–69` (per fact pack 03; import-time
  `MissingOptionalDependencyError` observed live).

## PROPOSED-REF

None. Citations: `nist-ai-rmf`, `in-toto`, `sigstore`, `otel`, `sre-book`,
`saltzer-schroeder`, `opa`, `cedar`, `slsa`.

## Other editorial notes

- One figure (Figure 41.1, fig-table schematic) per the brief's "one synthesis figure."
- Length target for this chapter is 3,000–4,000 words; stripped-prose count ~3.1k, raw
  ~3.6k — within range.
- The chapter deliberately contains no new transcripts; every evidentiary reference points
  back to Ch. 40's numbered artifacts to avoid duplicating claims.
