# LangGraph Integration Guide

The supported M2-C adapter is distributed separately from core Nornyx:

```text
pip install "nornyx-agentic-adapters[langgraph]"
```

The compatibility boundary is Nornyx core `>=1.10,<2`, agentic SPI major 1
(including SPI 1.2), and LangGraph `==1.2.2`.

## Identity and occurrence mapping

Declare LangGraph node keys through identity `framework_bindings`:

```yaml
framework_bindings:
  - {framework: langgraph, agent_key: support_coordinator}
```

The adapter uses only public `Runtime.execution_info`:

- `SurfaceBinding.surface` → logical operation;
- `ExecutionInfo.task_id` → occurrence;
- `ExecutionInfo.node_attempt` → retry attempt;
- the user-supplied mission id → the whole graph run and all resumes.

LangGraph resets `node_attempt` to one after checkpoint resume. The adapter
offsets it using the validated cumulative recorder prefix, so the resumed
Nornyx attempt remains contiguous.

## Usage

```python
from nornyx.agentic import EvidenceRecorder
from nornyx_agentic_adapters import SurfaceBinding
from nornyx_agentic_adapters.langgraph import make_governed_node, resolve_identity

identity_ref = resolve_identity(authorizer, "support_coordinator")
recorder = EvidenceRecorder.for_occurrences(
    authorizer,
    context,
    producer_id="support-graph",
)

governed_read = make_governed_node(
    binding=SurfaceBinding(
        surface="node.read",
        identity_ref=identity_ref,
        capability_ref="read_sanitized_request",
    ),
    authorizer=authorizer,
    context=context,
    recorder=recorder,
    mission_id="GOAL-SUPPORT-001",
    action=read_node,
)

builder.add_node("read", governed_read)
```

For process restart, persist the cumulative stream with the framework
checkpoint and reconstruct the recorder before resuming:

```python
recorder = EvidenceRecorder.resume(
    authorizer,
    resumed_context,
    prior_stream,
    producer_id="support-graph",
)
```

The producer identity, mission id, and lock must remain unchanged.

## Enforcement behavior

Each native attempt is authorized and its decision recorded before user node
code runs. A denial raises `AdapterDenied` and never invokes the node. A normal
node exception records `runtime_failed` and is re-raised for LangGraph retry
policy. A successful return records `agent_invoked`. LangGraph interrupt
control flow is propagated without `runtime_failed`; it leaves a valid,
incomplete attempt that the resumed execution continues as the next attempt.

Native tests cover retry, loops, parallel branches, interrupt, checkpoint
resume, policy denial, and installed-wheel import behavior.

## Coverage boundary

The supported surface is synchronous StateGraph node invocation through an
explicit `make_governed_node` wrapper. Graph construction remains caller-owned;
unwrapped nodes remain ungoverned. Async nodes, remote/distributed services,
implicit subgraph or ToolNode interception, and undocumented LangGraph
internals are unsupported. This remains cooperative Tier 2 evidence: the
adapter does not authenticate the producer or attest that supplied metadata is
true.
