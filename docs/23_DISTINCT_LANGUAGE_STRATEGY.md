# Nornyx Distinct Language Strategy

## Positioning

Nornyx is a **context-native agentic engineering language**.

It is not positioned first as a Python, TypeScript, Go, or Rust replacement. It is the executable control plane for AI-assisted engineering: intent, context, agents, policies, harnesses, evals, approvals, traces, and evidence.

## Distinct promise

```text
Python tells machines what to execute.
Nornyx tells human-AI systems how to understand, build, verify, approve, and prove software.
```

## What makes Nornyx different

1. Intent is first-class.
2. Context has authority, provenance, trust boundaries, and token budgets.
3. Agents have contracts, roles, tools, and output expectations.
4. Harnesses are executable, not informal workflow notes.
5. Policies, guardrails, and approvals are compiler/runtime concerns.
6. Evals and evidence are native artifacts.
7. PMO visibility is built in through generated status and the Developer PMO Portal.
8. Interop is the default: Nornyx generates standard files and integrates with existing ecosystems.

## Anti-positioning

Do not claim initially:

- Nornyx replaces Python.
- Nornyx removes the need for tests.
- Nornyx makes LLMs safe by default.
- Nornyx solves all hallucination or security issues.

Claim instead:

- Nornyx makes AI-assisted engineering governable, auditable, testable, repeatable, and safer.

## Language identity pillars

| Pillar | Meaning |
|---|---|
| Intent-native | Goals and success criteria are first-class |
| Context-native | Context has authority, budget, provenance, and taint |
| Agent-native | Agents have typed roles, contracts, tools, and outputs |
| Harness-native | Workflows, retries, checks, and repairs are executable |
| Policy-native | Permissions, risks, approvals, and capabilities are checked |
| Eval-native | AI behavior quality is measurable |
| Evidence-native | Every serious change produces proof |
| Interop-native | Existing tools remain execution surfaces |
| PMO-visible | Human governance is visible in a local portal |
| Extension-ready | Future AI concepts plug in without redesign |

## Product rule

For every stakeholder, Nornyx must remove more pain than it adds.

| Stakeholder | Must feel |
|---|---|
| Developer | less boilerplate, fewer repeated prompts, better guidance |
| LLM agent | clear role, context, policy, output contract |
| Architect | enforceable architecture and scope boundaries |
| Security | permissions, trust boundaries, audit logs |
| PMO | goals, risks, evidence, status, next action |
| Enterprise | standard exports and no lock-in |

## First-class commands

Nornyx should become easy to use through a small command set:

```bash
nornyx init
nornyx doctor
nornyx check
nornyx fmt
nornyx explain
nornyx generate
nornyx context-build
nornyx goal-plan
nornyx evidence-pack
nornyx pmo serve   # future command
```

This overlay adds scaffolds for: `init`, `doctor`, `fmt`, `explain`, and `profiles`.
