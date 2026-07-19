# CrewAI Integration Guide

The CrewAI reference adapter lives in
`integrations/nornyx_agentic_adapters/crewai_adapter.py` and is deliberately
**not** part of the `nornyx` wheel. It imports `crewai` lazily and only if
you installed it yourself; every enforcement path also works with duck-typed
agents exposing a `role` attribute, so the demonstration runs offline.

## Identity mapping

Each governed agent identity declares a binding:

```yaml
framework_bindings:
  - {framework: crewai, agent_key: refund_agent}
```

The adapter maps `agent.role` → `agent_key` → exactly one declared identity.
Unbound or ambiguous keys fail closed with `AN_ADAPTER_IDENTITY_UNKNOWN`.

## Usage

```python
from nornyx_agentic_adapters.governance_kernel import GovernanceKernel
from nornyx_agentic_adapters.crewai_adapter import CrewAIGovernanceAdapter

kernel = GovernanceKernel.from_local_controls(
    "examples/agentic_network_support/support_network.nyx",
    "nornyx.agentic_network.lock",
    framework="crewai",
    as_of="2026-07-17T00:00:00Z",
)
adapter = CrewAIGovernanceAdapter(kernel)
task = adapter.guarded_task(
    agent,                      # a crewai.Agent or any object with .role
    "propose_refund_under_limit",
    do_the_work,                # your callable
    mission_id="GOAL-SUPPORT-001",
)
result = task()
kernel.write_events("crewai_events.json")
```

`from_local_controls` fully validates the contract and verifies the network
lock before any enforcement; stale controls fail closed with
`AN_ADAPTER_LOCK_STALE`. `guarded_task` checks capability ownership
(including declared delegations) before the work runs and emits
`capability_requested` / `capability_allowed` / `tool_invoked` evidence bound
to the exact contract and lock digests. Denials raise `GovernanceViolation`
and emit `capability_denied` or `policy_violation`.

## Human approval

```python
kernel.require_human_approval(
    {"role": "network_governance_owner", "actor_type": "human", "granted": True},
    mission_id="GOAL-SUPPORT-001",
    actor_ref=kernel.resolve_identity("escalation_agent"),
)
```

The record is supplied externally — the adapter never grants approval.
Records with a non-human `actor_type` are rejected
(`AN_ADAPTER_APPROVAL_NON_HUMAN`) and recorded as policy violations.

## Boundaries

The adapter cannot cover every CrewAI escape path — CrewAI code that bypasses
the guard runs ungoverned. Validate the emitted evidence with
`nornyx agentic-network evidence-validate` as the final authority.
