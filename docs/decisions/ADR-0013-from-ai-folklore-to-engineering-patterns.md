# ADR-0013 — From AI Folklore to Engineering Patterns

## Status

Proposed

## Context

Current AI development is full of scattered advice:

```text
use this prompt
use this Claude command
use this repo
use this agent workflow
use this skills folder
use this MCP trick
use this context trick
```

This discovery phase is useful, but it does not scale as engineering. It creates fragile folklore, duplicated repo patterns, unclear evidence, and tool-specific rituals.

Nornyx should not become another pile of tricks. It should turn useful discoveries into explicit, testable, versioned patterns.

## Decision

Nornyx will introduce an optional **AI Pattern Lifecycle** concept.

The lifecycle turns an idea into a governed engineering asset:

```text
idea / trick / workflow
→ experimental_pattern
→ evaluated_pattern
→ candidate_profile
→ stable_profile
→ deprecated_pattern when obsolete
```

Patterns can cover:

```text
prompt technique
context strategy
agent workflow
harness design
eval method
evidence convention
tool integration pattern
portal/rendering pattern
```

A pattern may be promoted only when it has:

```text
clear scope
non-goals
applicability conditions
validation commands
eval evidence
failure modes
risk notes
version
owner
```

## Nornyx principle

```text
Innovation remains open.
Promotion requires evidence.
```

## What belongs in Nornyx

Nornyx should define:

```text
pattern metadata
pattern status
applicability
validation
evidence
risk
promotion criteria
deprecation criteria
```

## What does not belong in Nornyx

Nornyx should not become:

```text
a social media trick catalog
a prompt marketplace
a repo-ranking site
a hidden agent-ritual notebook
an untested pattern dump
```

## Safety

The pattern lifecycle is declarative.

It must not:

```text
call LLMs
invoke external tools
run shell commands
connect to MCP/A2A
modify GitHub
approve work
change policy automatically
```

## Consequences

Positive:

- reduces chasing unverified tricks;
- makes useful ideas reusable;
- gives teams a way to compare patterns;
- makes innovation evidence-backed;
- prevents Nornyx from becoming folklore.

Trade-off:

- pattern authors must write evidence and scope;
- not every useful trick deserves promotion.

## Operating rule

```text
A trick becomes a Nornyx pattern only after it has scope, tests/evals, evidence, and known failure modes.
```
