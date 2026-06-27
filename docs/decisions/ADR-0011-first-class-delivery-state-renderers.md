# ADR-0011 — First-Class Delivery State and Renderers

## Status

Proposed

## Context

Nornyx includes goal state, evidence, risks, completion, approvals, and next actions. During development, this was initially surfaced through the Developer PMO Portal.

That portal is useful, but the deeper language concept should not be tied to a PMO-specific UI.

The real language concept is:

```text
first-class delivery state
```

Delivery state should be renderable into multiple human and machine interfaces:

```text
Developer PMO Portal
terminal/shell dashboard
Markdown report
JSON API
CI summary
GitHub PR summary
IDE panel
management report
evidence pack
```

## Decision

Nornyx will treat delivery state as a normalized model.

Renderers are views over that model.

```text
.nyx source / generated status JSON
→ normalized delivery state
→ render targets
```

The Developer PMO Portal is one renderer, not the core abstraction.

## Core delivery-state fields

A Nornyx goal/delivery block should support:

```text
id
title
status
completion_pct
completed
pending
risks
evidence
related_prs
next_goal
approval_state
trace_refs
```

Only the first set is required initially. Approval and trace fields can remain optional until the runtime matures.

## Initial render targets

The first safe render targets are:

```text
shell
markdown
json
```

These are read-only and do not trigger actions.

## Boundary

Renderers must not execute work.

Renderers may display state, summarize state, and export state.

Renderers must not:

```text
call LLMs
invoke MCP/A2A tools
run shell commands
write to production systems
modify GitHub automatically
approve goals
change policy
```

## Rationale

This keeps the language clean:

```text
delivery_state = core language/control-plane model
Developer PMO Portal = optional renderer
shell dashboard = optional renderer
Markdown report = optional renderer
CI summary = optional renderer
IDE panel = future renderer
```

## Consequences

Positive:

- avoids overfitting Nornyx to the PMO Portal;
- makes Nornyx usable in terminal, CI, IDE, and management contexts;
- gives LLMs a compact, structured state object;
- reduces duplicated status reporting.

Trade-off:

- renderer contracts must stay stable;
- status consistency must be tested;
- generated state must remain source-of-truth aligned.

## Operating rule

```text
Nornyx owns the state model.
Renderers own presentation only.
```
