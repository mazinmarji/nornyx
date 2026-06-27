# RFC-0003: Full Language Evolution Research

## Status

Research only. This RFC does not approve public syntax, parser behavior,
checker semantics, runtime execution, native backends, dependencies,
connectors, release actions, or security-model changes.

## Problem

Nornyx is positioned as an AI engineering control-plane language first. The
long-term language target includes richer programming constructs, typed models,
effect and capability checking, and optional native backends. Those ideas need a
research map before any feature is promoted, so the project can evolve without
turning v0.1 into a general-purpose runtime by accident.

## Current boundary

v0.1 remains YAML-compatible and centered on these stable concerns:

- intent;
- context;
- agents;
- skills;
- policies;
- harnesses;
- evals;
- traces;
- evidence;
- approvals;
- budgets;
- goals.

Deferred extension blocks stay non-runtime research or backlog surface unless a
future goal packet promotes them through tests, evidence, and approval.

## Research tracks

### Semantic core and typed block model

Question: how should current blocks become more precise without breaking v0.1
documents?

Candidate constructs:

- typed block schemas;
- named reference kinds;
- contract signatures for agents, skills, policies, harnesses, and evals;
- schema migration metadata.

Promotion gate: RFC plus checker tests proving v0.1 compatibility.

### Type and effect system

Question: which effects must be checkable before any runtime action is planned?

Candidate effects:

- capability effects;
- approval effects;
- evidence obligations;
- context taint labels;
- budget effects;
- connector boundary effects.

Promotion gate: formal effect table plus negative tests for unsafe plans.

### Workflow programming constructs

Question: which control-flow constructs are native to governed human-AI
engineering without becoming a general-purpose runtime?

Candidate constructs:

- bounded retry blocks;
- repair loops with attempt limits;
- approval branches;
- evidence checkpoints;
- failure handlers;
- eval gates.

Promotion gate: harness semantics spec plus trace/evidence compatibility tests.

### Native backend research

Question: which backends should Nornyx generate or target while preserving
existing tools as the execution surface?

Candidate backends:

- JSON schema export;
- LSP and Tree-sitter metadata;
- OpenTelemetry-compatible trace export;
- MCP/A2A connector manifests;
- policy, eval, and evidence reports;
- optional domain-specific runners after approval.

Promotion gate: backend decision record plus local-only adapter safety tests.

## Rejected for this goal

- dedicated parser rewrite;
- native binary compiler;
- live connector runtime;
- production deployment behavior;
- arbitrary shell execution;
- secret handling;
- package registry;
- public syntax announcement.

## Approval gates

Human approval is required before:

- public syntax change;
- parser or checker semantic change;
- runtime execution expansion;
- native backend implementation;
- dependency addition;
- connector enablement;
- security-model change;
- release, tag, or public announcement.

## Validation

The research contract is checked locally with:

```bash
python scripts/research/check_language_evolution.py --strict
python -m nornyx.cli language-evolution --strict --out generated/language_evolution_goal_013.json
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
```
