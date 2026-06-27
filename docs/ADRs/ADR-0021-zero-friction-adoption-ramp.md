# ADR-0021 — Zero-Friction Adoption Ramp

## Status

Proposed

## Context

Nornyx becomes valuable when it governs AI-assisted development through goals, context, policy, harnesses, evidence, and delivery state.

The adoption risk is that new users may see this as too much upfront work.

A new user should not need to understand the full language before getting value.

## Decision

Nornyx will support a **Zero-Friction Adoption Ramp**.

The ramp starts with a lightweight, generated setup and gradually reveals stronger governance only when the repo needs it.

```text
observe → lite → standard → team → regulated → enterprise
```

The first user experience should be:

```text
run one command
get a minimal .nyx draft
get safe AI-coding instructions
get a fast quality command
continue development
```

## Core rule

```text
Start with generated minimum structure.
Do not require users to understand the whole language upfront.
Show value in five minutes.
Progressively reveal governance only when complexity increases.
```

## What belongs now

Add a small local adoption helper that can:

```text
detect repo signals
suggest an adoption level
generate a minimal Nornyx Lite .nyx draft
write the draft safely without overwriting by default
print an adoption status summary
validate the Lite draft on a clean downstream repo shape
```

## What does not belong now

Do not add:

```text
live LLM calls
portal wizard implementation
fine-tuned model pipeline
automatic GitHub writes
automatic approval
auto-enforced production gates
large onboarding framework
authoring assistant portal wizard
```

## Consequences

Positive:

- lower first-use friction;
- easier Codex/Claude onboarding;
- faster visible win;
- safer path from ad hoc AI coding into governed delivery;
- improved adoption likelihood.

Trade-off:

- Lite mode gives less governance than full Nornyx;
- users must be guided to upgrade when project complexity grows.
