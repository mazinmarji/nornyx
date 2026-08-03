# Chapter 13 — Author Notes

## Claims I could NOT verify (and what I wrote instead)

1. **ADR-0040 status.** The record is marked `Status: Proposed (design only; execution is a separate,
   owner-authorized milestone)`. The chapter says this explicitly in the Section 13.2 callout: the
   vocabulary and eligibility criteria are fixed, but emitting machine-readable tier labels in reports
   is "named as a follow-on milestone rather than existing behavior." I made no claim that any Nornyx
   report currently carries an `assurance_tier` field, because the ADR's own labeling rule defers that
   surface to a follow-on implementation goal.
2. **Adapter coverage inventories.** ADR-0040 states that `nornyx-agentic-adapters` 0.2.0 "publishes
   coverage inventories plus supported CrewAI synchronous-tool and LangGraph synchronous-node
   wrappers." Fact pack 02 §13 flags the published adapters wheel as not independently audited, so
   Section 13.3 describes the wrapped surfaces generically ("a synchronous tool method in one
   framework, a synchronous graph node in another") rather than quoting inventory contents, and defers
   coverage detail to Chapters 14 and 22–25.
3. **Table 13.2 tier assignments.** These are the author's engineering judgements applied to the case
   bible's surfaces, not repository facts. In particular, "branch protection is an independent
   enforcement point" is an architectural claim about a generic repository control, not about anything
   Nornyx supplies. Similarly the Ledger banking-interface row is an argument, not a measurement.
4. **Listing 13.1 and Listing 13.2.** Both are captioned "Illustrative — not drawn from the
   repository." The revision `git:9f3c1a7` follows the case bible's shortened-SHA convention. The
   "three tool surfaces listed in the coverage inventory" is fictional case-study detail. The
   inflated line in Listing 13.1 is deliberately written as an example of a *prohibited* claim; the
   ADR's prohibited-claims lists for Tier 1 and Tier 2 are the basis for calling it inflated.
5. **Thread D's fifth path.** The external-gateway projection is labelled in-text as "an architectural
   extension beyond the current repository," per the case bible's instruction not to present Thread D's
   Tier 3 path as shipped.
6. **Table 13.1 failure-behavior row.** The fail-open/fail-closed contrast for Tier 2 is general
   design analysis (Chapter 10 material). ADR-0040 does not characterise adapter availability
   behavior, so I attributed nothing there to the repository.

## PROPOSED-REF additions

None. Citations used: [@istio], [@envoy], [@nist-zta], [@slsa], [@schneider-enforceable], [@in-toto],
[@soc2] — all canonical keys.

## Repository paths I personally verified

- `/home/user/nornyx/docs/decisions/ADR-0040-governance-assurance-tiers.md` — read in full. Everything
  in Sections 13.1–13.4 that is attributed to the repository comes from this file, verified verbatim:
  - the "assurance tiers with claim boundaries, not product guarantees" sentence, including the
    deliberate avoidance of "guarantee";
  - the three boundary facts (declarative controls are design-time; adapter enforcement is cooperative;
    independent runtime assurance is not supplied by Nornyx alone);
  - the surface-scoping rule ("Assurance tiers apply to a specific claim, evidence package, and
    declared set of execution surfaces — not automatically to an entire application …");
  - Tier 1's five conjunctive eligibility criteria and its prohibited claims (`prevents`,
    `blocks at runtime`, `enforces`);
  - Tier 2's eligibility list, the "cooperative, declared surfaces only" mandatory qualifier, and
    "a total bypass **may leave no Nornyx-generated trace**";
  - Tier 3's required external evidence basis (authenticated producer identity; verified attestation;
    protected capture; deployment-policy binding; independent logging; demonstrated coverage), the
    statement that Tier 3 need not be cumulative on the Tier 2 adapter path, the prohibition on
    treating `producer.type: external_runtime` or `signature_ref` as qualifying, and the requirement
    that a Tier 3 claim "must name the external system that actually enforces."
- `/home/user/nornyx/nornyx/agentic_evidence.py` (lines 60–95) — read for the `LIMITATIONS` sentences
  that underpin the evidence-inflation discussion in Section 13.6.

Facts taken from the fact packs without independent re-verification: the security-boundary quotation
"Adapter enforcement is cooperative; bypassing the adapter bypasses the hook"
(`docs/agentic-network/08_SECURITY_BOUNDARIES.md`, via fact pack 02 §10 and fact pack 04 §10(d)); the
ADR's characterisation as GUIDANCE / "Proposed (design only)" (fact pack 04 traceability table).
