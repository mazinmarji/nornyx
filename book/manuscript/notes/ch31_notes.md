# Chapter 31 notes — Multi-Agent Governance

## Claims I could NOT fully verify (and what I wrote instead)

1. **Ledger declarations are fictional.** All Treasury/Ledger identities, capabilities
   (`case.decompose`, `analyze.exposure`, `payment.draft`, `payment.approve`,
   `approval.assemble`, `evidence.record`, `bank.submit`), zones, gates, and the amount tiers
   are the case bible's illustration, not repository content. Everywhere they appear, the text
   or caption marks them illustrative and pairs them with the real bundled example
   (`examples/agentic_network_support/support_network.nyx`), whose exact record counts are
   stated in Table 31.2 and were verified live.
2. **"Evaluated, recorded, and executed at most once" (Section 31.7).** Supported by fact pack
   02 §6.4 quoting `CHANGELOG.md` ("authorize once, execute the protected callable exactly once
   only on ALLOW…"). I did not independently execute the adapters; phrased as a property of the
   wrapped surface and kept general.
3. **Figure 31.3 (sequence diagram) is illustrative** for Ledger; the event types, per-type
   required fields, and decision bases (`membership`/`delegation`) are the real closed sets per
   fact pack 02 §5/§6 and the live-recorded stream, but this particular five-actor sequence was
   not produced from the repository. Listing 31.3 (real, two-identity) is the verified anchor.
4. **Approval-escalation-by-amount is structural, not numeric.** I verified the engine "never
   parses raw shell commands, file paths, URLs, or tool arguments" (module docstring,
   `nornyx/agentic/authz.py`) and wrote the threshold as three distinct capabilities/gates with
   the band selection explicitly relocated to the adapter and flagged as trusted. No claim that
   Nornyx compares amounts.
5. **Table 31.3 gateway/credential-separation rows** are **[extension]** by design (case bible
   requirement); no repository mechanism claimed.

## PROPOSED-REF

None.

## Repository paths personally verified

- `examples/agentic_network_support/support_network.nyx` — parsed with PyYAML; counted records:
  4 agent_identities, 8 capabilities, 2 trust_zones, 4 memberships, 3 network_gates,
  1 protocol_target, 1 delegation, 1 handoff, 4 relations, 0 revocations. Quoted the
  delegation block (lines ~405–425) verbatim in Listing 31.2; read handoff, relations,
  approval, zones, memberships, capabilities sections directly.
- Live run: `nornyx check` (1.11.0) on a modified copy with `current_depth: 1` →
  `AN_DELEGATION_DEPTH_EXCEEDED` + `AN_DELEGATION_DEPTH_INVALID`, exit 1 (messages quoted
  verbatim in §31.4 prose).
- Live run: modified copy with an appended chained delegation under `onward_delegation: denied`
  → the four diagnostics in Listing 31.1 (`AN_DELEGATION_DEPTH_POLICY_EXCEEDED` ×2 with both
  messages, `AN_DELEGATOR_CAPABILITY_MISSING`, `AN_ONWARD_DELEGATION_DENIED`), exit 1.
  Transcript reproduced verbatim.
- Live run: `nornyx agentic-network generate` → `"artifact_count": 10` with the ten artifact
  names; `lock` → lock digest; `lock-check` after appending a newline to
  `trust_zone_map.json` → `AN_LOCK_ARTIFACT_MISMATCH`, exit 1.
- Live run: recorded a 6-event explicit-mode stream via
  `nornyx.agentic.EvidenceRecorder.for_occurrences` + `record_occurrence_decision` /
  `record_occurrence_observation` against `load_authorizer(...)`; validated with
  `evidence-validate --strict` → pass, exit 0 (Listing 31.3 excerpts are from this stream).
- `nornyx/governance/agentic_delegation.py` — read lines ~600–870 (depth checks at 613–621,
  765–772, 810–817, 849–856) and the `AN_HANDOFF_AUTHORITY_ESCALATION` diagnostic at
  1111–1119, whose message ends "a handoff cannot grant authority." (quoted).
- `nornyx/agentic/authz.py` — read `EvidenceRecorder` (lines 1214–1310), recorder method list;
  module docstring "declared Nornyx concepts only" claim.
- Report limitations lines quoted in §31.6 confirmed in a live `--out` report:
  "Validated evidence proves conformance of supplied records only." etc.
- Sensitive categories `{secrets, credentials, tokens, private_memory}` — fact pack 02 §2.4
  (`nornyx/governance/agentic_network.py:12`) plus their literal appearance in the example's
  `never_share` lists (read directly).
- Identity constants `authority: non_human` / `can_approve: false` — read in the example;
  schema consts per fact pack 02 §2.2.
- Residual-risk sentence "Adapter enforcement is cooperative; bypassing the adapter bypasses
  the hook" — fact pack 02 §10 quoting `docs/agentic-network/08_SECURITY_BOUNDARIES.md`.
