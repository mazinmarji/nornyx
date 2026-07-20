# LangGraph Integration Guide

The LangGraph reference adapter lives in
`integrations/nornyx_agentic_adapters/langgraph_adapter.py` and is
deliberately **not** part of the `nornyx` wheel. `langgraph` is imported only
inside `build_governed_graph`; `guard_node` wrappers themselves are
framework-free.

## Identity mapping

```yaml
framework_bindings:
  - {framework: langgraph, agent_key: support_coordinator}
```

Node keys map to exactly one declared identity; unbound keys fail closed.

## Usage

```python
from nornyx_agentic_adapters.governance_kernel import GovernanceKernel
from nornyx_agentic_adapters.langgraph_adapter import LangGraphGovernanceAdapter

kernel = GovernanceKernel.from_local_controls(
    "examples/agentic_network_support/support_network.nyx",
    "nornyx.agentic_network.lock",
    framework="langgraph",
    as_of="2026-07-17T00:00:00Z",
)
adapter = LangGraphGovernanceAdapter(kernel)
graph = adapter.build_governed_graph(
    {
        "read": ("support_coordinator", "read_sanitized_request", read_node),
        "propose": ("refund_agent", "propose_refund_under_limit", propose_node),
    },
    [("START", "read"), ("read", "propose"), ("propose", "END")],
    mission_id="GOAL-SUPPORT-001",
)
result = graph.invoke({"request": "duplicate $12 charge"})
kernel.write_events("langgraph_events.json")
```

Every node execution is preceded by a capability check against the declared
identity (delegations included) and emits standardized evidence. A denied
node raises `GovernanceViolation` and stops the graph — fail closed, not
fail open.

## Portability claim

The same contract, lock, and kernel semantics govern the CrewAI adapter: the
demo (`examples/agentic_network_support/run_demo.py`) runs both frameworks
from one contract and validates both evidence streams against the same lock.

## Boundaries

LangGraph code that does not pass through `guard_node` runs ungoverned; the
final authority is `nornyx agentic-network evidence-validate`.
