# Nornyx Goal Mode Policy

## Purpose

Nornyx Goal Mode governs long-running AI-assisted implementation for the Nornyx language itself.

It adapts the agentic repo harness goal-mode idea into Nornyx-native terms.

## Allowed use

Use goal mode only when the task packet has:

- a clear goal;
- explicit non-goals;
- allowed and denied file scope;
- validation commands;
- evidence path;
- retry limit;
- stop rules;
- approval gates;
- model routing.

## Default stop rules

Stop immediately when:

- grammar semantics are ambiguous;
- public `.nyx` syntax would change without spec/RFC update;
- security-policy or capability semantics are affected;
- tool execution, external access, dependency install, or MCP enablement is needed but not approved;
- more than 3 fix attempts are needed;
- a change would bypass human approval, evidence, or trace requirements.

## Default approval gates

Human approval is required before:

- modifying language semantics;
- adding dependency packages;
- enabling external connectors;
- changing security model;
- changing artifact format compatibility;
- publishing packages or docs externally;
- merge or release tagging.
