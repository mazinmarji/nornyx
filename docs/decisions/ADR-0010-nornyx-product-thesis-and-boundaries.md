# ADR-0010 — Nornyx Product Thesis and Boundary Discipline

## Status

Proposed

## Context

Nornyx is being designed as a future AI-native/context-native/agentic engineering language.

During design work, many useful concepts emerged:

- context engineering;
- harness engineering;
- agents;
- skills;
- policies;
- evals;
- approvals;
- evidence;
- PMO visibility;
- MCP/A2A interoperability;
- self-healing;
- recursive improvement;
- developer experience;
- repo harness integration.

The risk is that Nornyx becomes another pile of files, configs, docs, skills, prompts, and portals instead of reducing the existing pile.

## Decision

Nornyx should be developed as:

```text
A context-native agentic engineering language and control plane.
```

Nornyx should not be developed first as:

```text
A replacement for Python, TypeScript, Rust, Go, Java, IDEs, CI/CD, or agent platforms.
```

The product thesis is:

```text
One .nyx source should declare and govern the AI engineering contract:
intent, context, agents, tools, policies, harnesses, evals, approvals, traces, PMO status, and evidence.
```

Nornyx is valuable only if it reduces duplicated operational knowledge across:

```text
AGENTS.md
CLAUDE.md
Copilot instructions
Cursor rules
skills folders
prompt files
agent configs
MCP configs
policy YAML
eval configs
harness scripts
evidence templates
PMO status JSON
handoff docs
GitHub Actions
```

## Boundary rules

### 1. Do not add a feature unless it replaces or governs existing complexity

A new Nornyx feature must satisfy at least one:

```text
removes duplicated repo instructions
turns manual AI-engineering rules into checked artifacts
generates standard downstream files
validates drift or inconsistency
improves safety, evidence, or approval discipline
improves install/use/adapt/integrate experience
```

### 2. Prefer generators over new proprietary runtime behavior

Early Nornyx should generate standard artifacts:

```text
AGENTS.md
CLAUDE.md
skills/
context.yaml
policy.yaml
evals.yaml
GitHub Actions
PMO status
evidence packs
handoff docs
```

Do not trap users inside a private runtime when standard repo artifacts are enough.

### 3. Keep the language core small

The core language should remain understandable:

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
```

Advanced concepts should be extensions or profiles, not mandatory beginner syntax.

### 4. Keep risky behavior out of the default path

Default Nornyx must not include:

```text
live LLM calls
credential handling
production deploys
automatic GitHub writes
live MCP/A2A tool execution
autonomous self-modification
unapproved self-healing
```

These may exist later only behind explicit policy, capability, approval, sandbox, trace, and evidence gates.

### 5. Treat Developer PMO Portal as visibility, not control authority

The PMO portal should show status, goals, evidence, and risks.

It must not become a production control panel or hidden execution surface.

### 6. Require a direct line from feature to adoption

A feature is not ready unless it improves one of:

```text
easy to learn
easy to install
easy to use
easy to adapt
easy to integrate
easy to audit
easy for LLMs to follow
```

## Acceptance tests for future additions

Before adding new Nornyx repo content, ask:

```text
Does this reduce the existing AI-development pile?
Does it avoid duplicating what another file already says?
Can it be generated from .nyx later?
Can it be checked by nornyx check/doctor/audit?
Is it safe by default?
Is it useful to both humans and models?
```

If the answer is no, do not add it.

## Consequences

Positive:

- protects Nornyx from scope creep;
- keeps the repo useful and learnable;
- anchors the product thesis;
- preserves the distinction between language, runtime, portal, and harness;
- keeps development aligned with the goal of reducing existing piles.

Trade-off:

- some interesting future concepts will remain deferred until a real use case or acceptance gate justifies them.

## Final operating principle

```text
Nornyx should not become the pile.
Nornyx should govern, reduce, generate, and validate the pile.
```
