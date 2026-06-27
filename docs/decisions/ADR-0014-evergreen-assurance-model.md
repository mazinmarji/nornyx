# ADR-0014 — Evergreen Assurance Model

## Status

Proposed

## Context

AI platforms, agent tools, protocols, model capabilities, IDE integrations, and prompt/agent techniques are changing rapidly.

Nornyx must not become obsolete by hard-coding the current tool landscape.

Nornyx must also not chase every new trend directly, because that would make the language unstable and bloated.

## Decision

Nornyx will use an **Evergreen Assurance Model**.

The model separates:

```text
stable kernel
fast-moving extensions
tool/vendor adapters
compatibility matrix
conformance tests
migration/deprecation policy
security advisory model
pattern lifecycle
maturity levels
```

## Stable kernel

The core Nornyx language should remain small and slow-changing:

```text
project
goal
intent
context
agent
policy
harness
eval
evidence
approval
trace
budget
delivery_state
```

## Extension/adaptation edge

Fast-moving concepts should enter through extensions and adapters:

```text
MCP
A2A
OpenTelemetry GenAI
VS Code / LSP
Tree-sitter
GitHub Actions
Claude/Codex/Copilot/Cursor profiles
company portal adapters
self-healing extensions
agentic pattern profiles
```

## Compatibility promise

A Nornyx project should be able to ask:

```text
Is my repo compatible with this Nornyx version?
Are my extensions supported?
Are any fields deprecated?
Are any generated artifacts drifting?
Are any security advisories relevant?
```

## Maturity promise

Nornyx should make adoption gradual:

```text
Level 0 — ad hoc AI usage
Level 1 — generated instructions
Level 2 — checked context/policy/evidence
Level 3 — harness/eval/trace runtime
Level 4 — governed connectors and approvals
Level 5 — controlled self-healing/improvement
```

## Safety

Evergreen checks are local/read-only.

They must not:

```text
call LLMs
invoke MCP/A2A tools
access secrets
write to GitHub automatically
deploy
approve work
run autonomous repairs
```

## Consequences

Positive:

- makes Nornyx future-resistant;
- gives enterprises confidence;
- allows fast innovation without unstable core changes;
- makes extensions testable and governable;
- prevents tool/vendor lock-in.

Trade-off:

- extensions must carry metadata, compatibility, and tests;
- unsupported innovations remain experimental until promoted.
