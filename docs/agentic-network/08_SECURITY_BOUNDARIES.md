# Security Boundaries

## Non-negotiable invariants

- `.nyx` remains the authoritative contract; agentic-network concepts stay
  profile/module-owned extensions of the unchanged twelve stable-core
  concepts.
- Governance packs are data-only; loading is local-only and deterministic;
  composition is monotonic.
- AI systems, tools, models, agents, connectors, and execution surfaces
  cannot approve. High-impact approval remains human, revision-bound,
  expiring, invalidatable, and revocable.
- Untrusted content cannot define policy or grant authority.
- `secrets`, `credentials`, `tokens`, and `private_memory` are never
  shareable across prohibited boundaries — in zones, protocol targets,
  delegations, handoffs, relations, adapter calls, and runtime events.
- Everything fails closed on malformed, unknown, ambiguous, contradictory,
  stale, expired, revoked, replayed, or forged input.

## Threat model and mitigations (selection)

| Threat | Mitigation |
| --- | --- |
| Malicious pack / contract, duplicate YAML keys | bounded loaders, duplicate-key rejection, content-hash verification, closed schemas |
| Hidden credential / endpoint / command fields | `additionalProperties: false` schemas plus generation-time field and value scanning (`AN_ARTIFACT_FORBIDDEN_*`) |
| Unicode/casing identifier collision | `AN_NORMALIZATION_COLLISION` (NFKC casefold) |
| Path traversal, symlink escape, device or remote path | existing loader path hardening reused by every AN input/output |
| Mutable revision, hash/schema/lock/evidence substitution | content-addressed revisions, lock field-by-field verification, per-event digest binding |
| Replay, ordering manipulation, dependency omission | closed ordering model: unique contiguous sequences, dependency precedence, content-replay rejection |
| Expired/revoked identity or delegation, capability or scope escalation, onward-delegation bypass | AN-002 static checks + AN-004 timestamp-effective re-checks |
| Handoff used as delegation | `AN_HANDOFF_AUTHORITY_ESCALATION`: targets must already hold or validly receive every required capability |
| Approval-role spoofing, AI-generated approval | composed-module role authority, producer/actor-type checks, adapter policy-violation events |
| Framework identity mismatch, missing adapter hook, stale controls | exact one-binding resolution, `AN_ADAPTER_HOOK_MISSING`, lock verification before any enforcement |
| Evidence from another contract/network | per-event contract/lock/network/revision binding |

## Residual risks (stated, not hidden)

- Evidence is supplied, not observed: omission and fabrication are outside
  Nornyx's proof surface.
- Adapter enforcement is cooperative; bypassing the adapter bypasses the
  hook.
- Structural signature references are not cryptographic verification; no
  signature verification is claimed.
- The lock binds bytes, not producers; repository review remains the control
  for unauthorized regeneration.
