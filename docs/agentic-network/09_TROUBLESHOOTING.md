# Troubleshooting

| Symptom | Meaning | Fix |
| --- | --- | --- |
| `AN_DELEGATION_FORBIDDEN` | A capability declares `delegable: true` but the composed governance lacks `agentic_network_delegation.v1`. | Use the built-in `agentic_network` profile (module 0.2.0) or add the check to your module. |
| `AN_DELEGATION_GOVERNANCE_MISSING` | `delegations`/`handoffs`/`relations` present without the delegation check. | Same as above. |
| `AN_DELEGATOR_MEMBERSHIP_REQUIRED` | The delegator's authorized source-zone membership does not carry the delegated capability. | Add the capability to the membership `capability_refs`. |
| `AN_HANDOFF_AUTHORITY_ESCALATION` | The handoff target neither holds nor validly receives a required capability. | Grant it via identity+membership or a declared active delegation in `delegation_refs`. |
| `AN_APPROVAL_ACTION_MISSING` | Cross-zone or high-risk delegation/handoff exists but the approval declaration's `required_for` lacks `delegate`/`handoff`. | Add the action to `approvals[].required_for`. |
| `AN_LOCK_SOURCE_STALE` | The contract changed after the lock was written. | Re-review, regenerate (`agentic-network generate`), re-lock. |
| `AN_LOCK_ARTIFACT_UNEXPECTED` | A stray file sits in the artifacts directory. | Remove it; only locked artifacts belong there. |
| `AN_EVT_SEQUENCE_GAP` | The events file omits part of a mission stream. | Supply the complete stream; partial evidence fails closed. |
| `AN_EVT_CAPABILITY_NOT_HELD` | An `allowed`/`tool_invoked` event names a capability the actor neither holds nor receives via the event's `delegation_ref` at that timestamp. | Fix the runtime mapping, or include the delegation reference the allowance used. |
| `AN_EVT_LOCK_STALE` | The supplied lock no longer matches the contract used for validation. | Validate against the exact contract revision the evidence was produced for. |
| `AN_ADAPTER_IDENTITY_UNKNOWN` | The framework agent key maps to zero or multiple identities. | Declare exactly one `framework_bindings` entry per framework/key. |
| `AN_ADAPTER_LOCK_STALE` | Adapter refused to start on stale controls. | Regenerate and re-lock, then restart the adapter. |
| `EVAL_IMPORT_ERROR` | The external results file does not match the accepted Promptfoo shape. | Export with `promptfoo eval --output results.json`; do not hand-edit stats. |
| `GOVERNANCE_BLOCK_SCHEMA_INVALID` on new fields | A record carries a field outside the closed schema. | The schemas are closed by design; extra fields (including credential-like ones) are rejected. |

Validation-time rules: every timing decision uses the explicit `--as-of`
offset timestamp (or now, in `nornyx check`); expiry, revocation
effectiveness, and approval freshness are evaluated at that instant.
