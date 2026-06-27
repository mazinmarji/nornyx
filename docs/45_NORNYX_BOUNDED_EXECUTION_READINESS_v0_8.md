# Nornyx v0.8 Bounded Execution Readiness

## Status

Local v0.8 bounded execution readiness surface. This is a readiness report, not
an execution runtime. It checks whether a `.nyx` document has the contracts
needed before any future bounded execution could be considered.

## Readiness report

`nornyx.bounded_execution.build_bounded_execution_readiness_report()` produces:

- `schema: nornyx.bounded_execution_readiness.v0.8`;
- sandbox contract decisions;
- explicit capability gate decisions;
- approval-before-action checks;
- trace/evidence requirement checks;
- policy summary;
- adapter conformance summary;
- flow and repair metadata;
- safety flags proving nothing executed.

The matching schema is `schemas/bounded_execution_readiness.schema.json`.

## Required sandbox contract

The readiness layer requires:

```text
filesystem: workspace_only | read_only | disabled
network: disabled
credentials: disabled
production: disabled
shell: disabled | allowlisted
approval_required: true
trace_required: true
evidence_required: true
```

Unsafe network, credential, production, shell, or approval settings block
readiness.

## Capability and approval gates

Tool, connector, and model steps remain denied unless explicitly declared by
capabilities. Declared capabilities still require approval unless a later,
approved policy explicitly allows otherwise.

Approval gates are never auto-satisfied. The readiness report can say a document
is ready for human approval, but it cannot grant approval.

## Evidence and trace

Readiness requires trace and evidence contracts. Existing harness reports still
write local trace/evidence artifacts without executing tools, agents, connectors,
models, or arbitrary commands.

## Non-goals

v0.8 does not:

- enable broad runtime autonomy;
- execute graph edges;
- execute adapters;
- enable live connectors;
- call models;
- load credentials;
- open networks;
- run arbitrary shell commands;
- grant approvals;
- deploy software;
- self-modify.

Any future execution behavior requires a separate approved goal with explicit
sandbox, capability, approval, trace, and evidence gates.
