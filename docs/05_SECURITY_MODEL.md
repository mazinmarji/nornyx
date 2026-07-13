# Nornyx Security Model

## Core assumptions

AI agents may make mistakes. They may also receive poisoned context. Therefore Nornyx should constrain agents by design.

## Security layers

1. Constitution: non-negotiable system principles.
2. Authority: who or what can approve actions.
3. Policy: rules for allowed/denied behavior.
4. Capability: explicit access to tools, files, models, networks, deploys.
5. Guardrail: runtime input/output validation.
6. Context taint: untrusted content cannot override trusted instruction.
7. Trace: every meaningful action is recorded.
8. Evidence: every completed workflow must prove what happened.
9. Containment: stop conditions, budgets, kill switch.

## Required security constraints

- untrusted context cannot define policy;
- untrusted context cannot request privileged tool use;
- secrets cannot be passed to external models;
- dependency additions require supply-chain check;
- production mutations require approval;
- self-modification requires approval;
- recursive loops must have bounded depth and cost.

## Local policy runtime v0.1

GOAL-008 introduces a local policy report for harness planning. It is a
read-only decision manifest, not an execution engine.

- tool, connector, and model steps default to denied unless a matching
  `capabilities` declaration exists;
- declared capabilities require human approval unless `approval_required: false`
  is explicit;
- connector and model steps require an explicit no-secrets, no-PII, or schema
  guardrail before they can be planned as allowed;
- policy deny rules can block matching agent actions;
- policy require rules and declared guardrails are recorded as pending evidence;
- the runtime records decisions but does not execute agents, tools, connectors,
  models, repairs, arbitrary commands, or approvals.

## Local connector adapter boundary v0.1

GOAL-010 introduces MCP/A2A connector manifest planning. It validates connector
and plugin metadata, but keeps adapter execution disabled.

- connector manifests must declare MCP or A2A protocol and at least one
  capability;
- unsafe default modes such as live, write, execute, or full access are blocked;
- endpoint or command metadata is recorded as a blocked live target;
- A2A manifests must not share sensitive categories such as secrets,
  credentials, tokens, or private memory;
- candidate/stable plugin manifests require conformance entries;
- connector use remains subject to policy capability checks, human approval,
  trace, and evidence gates before any future live enablement.

## Local adapter contract boundary v0.4

GOAL-036 introduces contract-only adapter bridge metadata. Adapter contracts
must declare safe connector conformance, policy references, eval references,
and evidence references.

- adapter `execution_mode` must remain `contract_only`;
- `live_connector_execution` must be `false`;
- connector manifests remain disabled by default and approval-gated;
- adapter contracts must not include credential loading, network calls,
  production deployment, automatic approvals, or unrestricted execution.

## Adapter conformance boundary v0.7

GOAL-039 adds adapter conformance reports. These reports are evidence artifacts,
not execution plans.

- adapter conformance reports must keep `connectors_enabled: false`;
- adapter conformance reports must keep `adapters_executed: false`;
- live connector execution remains disallowed;
- endpoint, command, credential, network, and automatic approval behavior remain
  outside the contract-validation scope.

## Bounded execution readiness boundary v0.8

GOAL-040 adds readiness checks for bounded execution as a
`future_proposal_outside_current_program`. Readiness is not execution.

- network and credentials must remain disabled;
- production deployment must remain disabled;
- shell behavior must be disabled or explicitly allowlisted;
- approval, trace, and evidence contracts are required;
- readiness reports do not grant approvals, execute tools, call models, open
  networks, load credentials, run adapters, or deploy.
