# Nornyx Agentic-Network Reference Adapters (optional)

This directory is **not** part of the `nornyx` wheel. It contains the AN-005
reference integrations (ADR-0037) proving that one Nornyx agentic-network
contract can govern more than one external execution environment.

```text
Layer 1 — Nornyx contract, generated governance controls, and network lock
Layer 2 — Optional adapter enforcement hooks (this directory)
Layer 3 — External framework runtime or the bundled deterministic harness
```

## Contents

- `nornyx_agentic_adapters/governance_kernel.py` — framework-free enforcement
  kernel: loads local controls, verifies the agentic-network lock before use,
  maps framework agent keys to declared identities, checks capability
  ownership (including declared delegations), validates delegation and
  handoff requests, enforces trust-zone and sensitive-sharing declarations,
  verifies externally supplied **human** approval records (AI approval is
  rejected), and emits `nornyx.agentic_runtime_events.v1` evidence bound to
  the exact contract digest and lock digest.
- `nornyx_agentic_adapters/crewai_adapter.py` — CrewAI mapping + task guard.
- `nornyx_agentic_adapters/langgraph_adapter.py` — LangGraph node guard and
  governed `StateGraph` builder.
- `nornyx_agentic_adapters/local_harness.py` — deterministic fake model and
  inert tools for safe, offline, reproducible demonstrations.

## Boundaries

The adapters never authenticate agents, discover services, store secrets,
connect to production systems, grant approvals, reconfigure the contract, or
modify governance policy. Enforcement is cooperative at the adapter boundary:
**adapter enforcement cannot cover every framework escape path** — a caller
that bypasses the adapter bypasses the hook. The final authority is Nornyx
validation of the emitted evidence against the exact contract, lock, and
revision (`nornyx agentic-network evidence-validate`).

## Dependencies

Nothing here is a Nornyx runtime dependency. `crewai` and `langgraph` are
imported lazily and only if you installed them yourself; every enforcement
path is also exercised with the bundled deterministic harness, so the
demonstrations and tests run offline without either framework.
