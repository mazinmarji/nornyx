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

- `nornyx_reference_adapters/governance_kernel.py` — deprecated compatibility
  shim preserving the historical reference API and `AN_ADAPTER_*` diagnostics
  while delegating decisions to the public SPI 1.1 `Authorizer` and evidence
  construction to `EvidenceRecorder`. Construction emits `DeprecationWarning`;
  new integrations should use `nornyx-agentic-adapters` and `nornyx.agentic`.
- `nornyx_reference_adapters/crewai_adapter.py` — CrewAI mapping + task guard.
- `nornyx_reference_adapters/langgraph_adapter.py` — LangGraph node guard and
  governed `StateGraph` builder.
- `nornyx_reference_adapters/local_harness.py` — deterministic fake model and
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

The compatibility shim itself imports only `nornyx.agentic`; neither framework
enters the core package or wheel. It follows the supplied lock's runtime-events
version (exact 1.0 envelope or 1.1 `legacy` mode), and it does not infer the
explicit occurrence metadata used by the supported LangGraph adapter. See
`adapters/nornyx-agentic-adapters/docs/MIGRATION.md` for the complete method,
error, deprecation, retention, and unsupported-surface mapping.
