# Compiler MVP Plan

## v0.1 implementation

Already scaffolded in this repo:

- YAML-compatible parser;
- semantic checker;
- artifact generator;
- context pack builder;
- evidence pack scaffold;
- tests.

## Next implementation slices

### Slice 1 — schemas

Add typed schemas for every top-level block.

### Slice 2 — diagnostics

Produce machine-readable diagnostics optimized for LLM repair.

### Slice 3 — custom parser

Replace YAML dependency with a Nornyx parser after semantics stabilize.

### Slice 4 — harness runner

Add a safe execution runtime with adapter interfaces. Do not add arbitrary shell execution by default.

### Slice 5 — policy runtime

Add capability checks, approval gates, and connector policies.

### Slice 6 — LSP

Add syntax highlighting, validation, autocomplete, and go-to-definition.

## Design rule

Do not build a native binary compiler until Nornyx proves value as an AI-engineering control plane.
