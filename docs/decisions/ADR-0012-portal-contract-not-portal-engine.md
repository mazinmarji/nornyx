# ADR-0012 — Portal Contract, Not Portal Engine

## Status

Proposed

## Context

Nornyx is gaining first-class delivery state and renderers. The Developer PMO Portal showed that humans benefit from seeing goal state, risks, evidence, and next actions in a dashboard.

However, there is a risk that Nornyx becomes a full portal platform instead of a language/control plane.

## Decision

Nornyx will support an optional **Portal Contract Extension**.

Nornyx will not include a full portal engine in the language core.

The extension defines:

```text
role views
dashboard sections
state sources
render targets
integration targets
safety boundaries
```

It does not define:

```text
React application code
authentication system
database backend
enterprise SSO
ticketing workflow engine
production operations console
```

## Core principle

```text
Nornyx should be portal-ready, not portal-heavy.
```

## Relationship to language core

Core Nornyx owns:

```text
delivery_state
goal_state
evidence_state
risk_state
approval_state
trace_state
```

The optional Portal Contract Extension maps that state into human-facing views:

```text
Developer view
Architect view
PMO view
Security view
Executive view
Release view
```

## Safety

The portal contract is declarative and read-only.

Portal contracts must not:

```text
execute shell commands
call LLMs
call MCP/A2A tools
write to production systems
approve goals
merge PRs
change policy
expose secrets
```

## Rationale

This keeps Nornyx useful for developers who want to build a Governed Delivery Control Plane-style portal, while preventing the language from being overloaded with application-framework responsibilities.

## Consequences

Positive:

- makes Nornyx easier to connect to portals, shells, IDEs, and company dashboards;
- preserves clean separation between state model and UI;
- helps developers build control-plane project portals faster;
- avoids turning Nornyx into another large portal framework.

Trade-off:

- portal implementations must be built separately;
- adapter-specific details remain outside the core language.
