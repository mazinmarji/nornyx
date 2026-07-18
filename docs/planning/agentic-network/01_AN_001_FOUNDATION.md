# AN-001 — Agentic Network Governance Foundation

Status: remediation is implemented in candidate commit `8e939d9f69f474566b11d42fe2a989d1cf6e480c`.
The first independent audit returned `NO_GO`; the corrected second independent
audit closed AN-AUD-001 through AN-AUD-012 and withdrew AN-AUD2-001. Human
acceptance of ADR-0033 and the compatibility migrations is recorded; separate
merge authorization remains required.

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

1. Complete exact-head post-acceptance hosted CI and focused verification.
2. Preserve separate authorization for merge; any release remains a
   separate decision.
