# AN-001 — Agentic Network Governance Foundation

Status: **merged and technically closed.** The three P1 implementation findings
raised after acceptance commit `b707e2a3325f981c0e7a34cef07a0950bb4c98a5` are
remediated in audited implementation commit
`1a2d26f14b77cded7a0ab765afa77215b2ddf0b6`: composed-module approval authority
is authoritative, canonical approval and contract-review evidence is typed, and
exact revisions are content-addressed. AN-001 is merged into `main` via merge
commit `5956ba815cf31f904afe86d52582af221f2e739c`, which preserves the audited
head verbatim (main's tree equals the audited tree `bc8cabd…`). Exact-head CI
run `29663747419` and post-merge CI run `29675442562` both passed. The three
original review threads are resolved. Release, publication, deployment, and
runtime enablement remain separate decisions outside this merge.

The first independent audit returned `NO_GO`; the corrected second independent
audit closed AN-AUD-001 through AN-AUD-012 and withdrew AN-AUD2-001; the final
independent audit returned `GO` on the audited head. Human acceptance of
ADR-0033 and the compatibility migrations remains recorded.

## Scope Inventory

- Optional v1-only profile: `agentic_network` 0.1.0.
- Thin module: `agentic_network_governance` 0.1.0, directly depending only on
  `human_approval`.
- Closed blocks: `agentic_network`, `agent_identities`, and `capabilities`.
- Fixed check: `agentic_network_foundation.v1`.
- Deterministic starter and executable local example.
- Additive compatibility lineage from 12/6 to 13/7.

## Frozen Boundary

AN-001 is a static contract and checker addition. It adds no stable core
concept, top-level language block, public Python export, runtime authentication,
identity issuance, transport, endpoint, command, credential, framework
execution, delegation, handoff, export, network lock, runtime event, release,
publication, or deployment behavior.

## Evidence

- Decision: `docs/decisions/ADR-0033-agentic-network-governance-profile.md`.
- Profile/module resources: `nornyx/profiles_data/`.
- Root and bundled schemas: `schemas/` and `nornyx/schemas/`.
- Structural implementation: `nornyx/governance/agentic_network.py`.
- Example: `examples/agentic_network.nyx`.
- Tests: `tests/test_agentic_network_governance.py`.
- Compatibility proof: `tests/fixtures/governance_compatibility/manifest.json`.

## Completed Gates

1. Exact-head hosted CI run `29663747419` and focused verification for the P1
   remediation: completed and passed.
2. The three original review threads were reassessed against the audited head,
   replied to, and resolved.
3. AN-001 was merged into `main` via merge commit
   `5956ba815cf31f904afe86d52582af221f2e739c`; post-merge CI run `29675442562`
   passed.

Outstanding and deliberately separate from this merge: release, tag,
publication, deployment, and runtime enablement remain separate decisions and
have not occurred.
