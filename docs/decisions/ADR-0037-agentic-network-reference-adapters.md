# ADR-0037 — Optional Cross-Framework Reference Adapters (AN-005)

- Status: Proposed (implementation authorized by the owner's AN-completion goal;
  human review remains the final closure authority)
- Date: 2026-07-19
- Decision owner: human repository owner

## Context

One Nornyx agentic-network contract must be shown governing at least two
external execution environments (CrewAI and LangGraph) without moving
framework execution into stable Nornyx core and without making heavy
frameworks mandatory dependencies.

## Decision

Add a top-level `integrations/` directory that is **not** part of the
`nornyx` wheel (packaging includes `nornyx*` only). Layering:

```text
Layer 1 — Nornyx contract, generated governance controls, and network lock
Layer 2 — Optional adapter enforcement hooks (integrations/)
Layer 3 — External framework runtime or the bundled deterministic harness
```

Structure:

- `integrations/nornyx_agentic_adapters/governance_kernel.py` — shared,
  framework-free enforcement kernel: loads local generated controls, verifies
  the network lock digest against the contract, maps runtime identities to
  declared identities, checks capability ownership, validates delegation and
  handoff requests, enforces trust-zone declarations, requires externally
  supplied human approval records, rejects AI-produced approval, and emits
  standardized `nornyx.agentic_runtime_events.v1` events bound to the exact
  contract digest and lock digest. Fails closed on stale controls, stale
  locks, or a missing hook.
- `integrations/nornyx_agentic_adapters/crewai_adapter.py` — maps CrewAI
  agents/tasks onto the kernel; imports `crewai` lazily and only if installed.
- `integrations/nornyx_agentic_adapters/langgraph_adapter.py` — wraps
  LangGraph node callables with kernel enforcement; imports `langgraph`
  lazily and only if installed.
- `integrations/nornyx_agentic_adapters/local_harness.py` — deterministic
  fake-model, inert-tool harness used by default demonstrations and tests.

Adapters never authenticate, discover services, store secrets, contact
production systems, grant approvals, reconfigure the contract, or modify
policy, and the documentation states that adapter enforcement cannot cover
every framework escape path.

## Rejected alternatives

- `nornyx/integrations/` subpackage — rejected: it would ship framework
  coupling inside the wheel and grow the stable import surface.
- Mandatory or extras-declared framework dependencies — rejected: default
  install must stay lightweight; extras would still change package metadata
  during a version-frozen program.
- One adapter only — rejected: portability across two frameworks is the
  product claim under test.

## Compatibility / packaging effect

No wheel content change from this phase except tests and docs; `nornyx`
package imports no framework. CI/dev may install frameworks; tests that need
framework-native objects skip with a recorded reason when the framework is
absent, and the deterministic harness always exercises the full enforcement
path.

## Security boundaries

Local files only; no credentials, endpoints, sockets, production writes, or
real external tools in tests and default examples; evidence binding uses the
canonical contract digest and lock digest; AI approval is rejected
structurally by producer type.

## Public API / CLI effect

None. Adapters consume documented CLI outputs and importable (non-stable)
helpers `nornyx.agentic_artifacts` / `nornyx.agentic_evidence`.

## Determinism requirements

Default demonstrations use the deterministic harness: identical inputs yield
identical emitted event streams (except caller-supplied timestamps, which the
harness fixes to declared constants), so evidence validation is reproducible.

## Human authority

Approval records consumed by adapters must be supplied externally by humans;
the adapters only verify shape, producer type, role, revision binding, and
expiry via Nornyx validation.

## Non-goals

Being a runtime, agent platform, auth layer, service registry, or transport.

## Test obligations

Same-contract portability across both adapters; identity mapping; capability
allow/deny; delegation valid/escalation; handoff valid/unauthorized; missing
hook; identity mismatch; stale control; stale lock; wrong contract digest;
evidence emission + validation; human approval requirement; AI approval
rejection; sensitive-data rejection; no credential requirement; no unmocked
network; no automatic approval; framework-native object test when the
framework is installed (skip-marked otherwise).

## Migration implications

None; additive directory.

## Residual risks

A framework caller can bypass the adapter entirely; enforcement is
cooperative at the adapter boundary and the final authority is Nornyx
validation of the emitted evidence against the lock. Framework APIs drift;
adapters pin no versions and degrade to skips, not false confidence.
