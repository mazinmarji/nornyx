# AN-001 — Agentic Network Governance Foundation

Status: three P1 implementation findings raised after acceptance commit
`b707e2a3325f981c0e7a34cef07a0950bb4c98a5` are remediated in the local
candidate. Composed-module approval authority is authoritative, canonical
approval and contract-review evidence is typed, and exact revisions are
content-addressed. Local validation passed; the prior CI success applies to the
superseded acceptance head, and new exact-head CI is required. Merge
authorization remains withdrawn pending review-thread closure and separate
human authorization.

The first independent audit returned `NO_GO`; the corrected second independent
audit closed AN-AUD-001 through AN-AUD-012 and withdrew AN-AUD2-001. Human
acceptance of ADR-0033 and the compatibility migrations remains recorded.

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

## Remaining Gates

1. Run exact-head hosted CI and focused verification for the P1 remediation.
2. Reassess the three unresolved review threads against that exact head.
3. Preserve separate authorization for merge; any release remains a
   separate decision.
