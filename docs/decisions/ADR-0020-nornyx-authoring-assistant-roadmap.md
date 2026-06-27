# ADR-0020 — Nornyx Authoring Assistant Roadmap

## Status

Proposed

## Context

Writing `.nyx` source manually can become tedious for developers, product owners, operations teams, and other non-language experts.

Nornyx should simplify AI-native engineering, not force every user to hand-write structured language files.

The preferred authoring experience is:

```text
human/product/engineering input
→ guided CLI or UI portal
→ LLM-assisted .nyx draft
→ formatted preview
→ human review/modify/approve
→ nornyx check/fmt/explain
→ accepted .nyx becomes source of truth
```

Later, Nornyx may support a small specialized model or fine-tuned model optimized for Nornyx authoring and repair.

## Decision

Nornyx will define an Authoring Assistant Roadmap.

This is roadmap/backlog material, not immediate v0.1 core.

The roadmap includes:

```text
interactive CLI authoring wizard
simple UI/portal authoring flow
LLM authoring pack
.nyx preview renderer
approval/rejection/modification workflow
repair loop using nornyx check errors
optional future small Nornyx-specialized model
```

## Safety rule

```text
LLM may draft .nyx.
Nornyx must check it.
Human must approve authoritative .nyx.
Unknowns must become assumptions, open questions, or decision-needed items.
Live actions require explicit capability design and evidence gates.
```

## Non-goals now

Do not add live LLM calls, fine-tuning pipeline, model hosting, portal implementation, authentication, database, automatic approval, automatic repo writes, or production integration.

## Consequences

This lowers the barrier to writing `.nyx`, gives normal users a practical authoring path, and keeps Nornyx aligned with its mission to reduce friction. Actual portal/model implementation remains future work.
