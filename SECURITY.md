# Security Policy

Nornyx is designed as a governance-first AI engineering control plane.

## v0.1 safety boundaries

The current scaffold intentionally avoids:

- arbitrary shell execution;
- live LLM calls;
- live MCP/A2A connector execution;
- production deployment;
- credential storage;
- self-modifying code;
- external network calls.

## Security principles

1. Untrusted context may inform an agent, but must never define policy or authority.
2. Tool calls must be declared through capabilities.
3. High-impact actions require explicit approval gates.
4. Evidence is required for code changes, policy decisions, and deployment gates.
5. Self-healing and self-improvement are proposal-and-gate workflows, not free mutation.
6. Connector servers and skill packages must be signed or explicitly trusted.
7. Every agent action must have identity, trace, budget, and authority boundaries.

## Vulnerability reporting

This scaffold is not a released product. Report issues through repository issues once hosted.
