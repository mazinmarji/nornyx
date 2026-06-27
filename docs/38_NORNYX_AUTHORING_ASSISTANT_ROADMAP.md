# Nornyx Authoring Assistant Roadmap

## Purpose

The Nornyx Authoring Assistant helps users create `.nyx` source without manually writing every block.

It is not the language core. It is an authoring layer over the language.

## Target experience

```text
User answers guided questions
→ system drafts .nyx
→ user sees formatted readable preview
→ Nornyx explains the draft
→ Nornyx checks the draft
→ user approves, rejects, or modifies
→ accepted .nyx becomes source of truth
```

## Why this matters

Manual `.nyx` authoring can be tedious because users may need to define:

```text
project
goals
context
agents
policies
harnesses
evals
evidence
approval
handover
delivery state
```

A guided authoring experience makes Nornyx usable by developers, product owners, architects, operations teams, security reviewers, PMO users, enterprise stakeholders, and LLM agents.

## Authoring modes

### 1. CLI wizard

Future command:

```powershell
nornyx author new --profile ai_coding
```

Questions:

```text
Project name?
Primary goal?
Who are the users?
What files are allowed?
What files are denied?
What tests must pass?
What evidence is required?
Who approves?
What decisions are still open?
```

### 2. UI / portal wizard

A simple local UI can show:

```text
left: guided input form
middle: generated .nyx
right: explanation / validation / approval panel
```

Actions:

```text
generate draft
explain
check
format
approve
reject
modify
export
```

### 3. LLM-assisted drafting

The LLM receives:

```text
Nornyx mini-spec
allowed blocks
examples
project/product input
constraints
unknown-handling rule
```

The LLM returns:

```text
draft .nyx
assumptions
open questions
decision_needed items
```

The checker remains authoritative.

### 4. Repair loop

```text
LLM drafts .nyx
→ nornyx check reports errors
→ LLM repairs only reported errors
→ nornyx fmt normalizes
→ nornyx explain renders readable review
→ human approves
```

### 5. Future small Nornyx-specialized model

A future optional model could support:

```text
.nyx drafting
.nyx repair
block completion
migration
example generation
triage candidate writing
human-readable explanation
```

This remains optional. Nornyx must still work with normal LLMs using spec/examples/checker feedback.

## Guardrails

The authoring assistant must not:

```text
make product decisions silently
invent missing requirements
approve its own output
write production config
call external tools by default
bypass nornyx check
bypass human approval
```

## Promotion gates

Any move from roadmap to implementation must include:

```text
stable parser/checker diagnostics
explicit capability design before live LLM, portal, connector, or repo-write actions
recorded evidence for drafts, checker output, assumptions, and approvals
human approval before authored .nyx becomes authoritative
```

## Final principle

```text
Make .nyx easy to create, but never make unchecked drafts authoritative.
```
