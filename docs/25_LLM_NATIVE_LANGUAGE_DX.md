# LLM-Native Developer Experience

## Principle

Nornyx should be pleasant for humans and structurally reliable for LLMs.

## Requirements

1. Deterministic formatting.
2. Small, explicit vocabulary.
3. Machine-checkable references.
4. Clear authority order.
5. Context budget awareness.
6. Explicit allowed and denied actions.
7. Repairable compiler diagnostics.
8. Generated agent packets.
9. Safe defaults.
10. Evidence-producing workflows.

## New v0.2 CLI behavior introduced by this overlay

### `nornyx init`

Creates a starter `.nyx` file from a profile.

### `nornyx doctor`

Checks local repo readiness.

```bash
nornyx doctor
nornyx doctor --json
```

### `nornyx fmt`

Canonical YAML-compatible formatter for v0.1.

### `nornyx explain`

Explains project shape or a specific symbol.

### `nornyx profiles`

Lists built-in starter profiles.

## Stable first authoring loop

The v0.1 DX loop is intentionally small:

```bash
nornyx profiles
nornyx init --profile ai_coding --name Demo --out generated/demo_project.nyx --force
nornyx check generated/demo_project.nyx
nornyx fmt generated/demo_project.nyx --check
nornyx explain generated/demo_project.nyx
nornyx doctor
```

This loop is local-only. It does not call models, execute harness flows, enable
connectors, load secrets, or deploy software.

## Local editor metadata

GOAL-011 adds JSON editor metadata commands for syntax highlighting,
diagnostics, completion, symbols, and formatting integration:

- `nornyx editor-manifest`;
- `nornyx syntax`;
- `nornyx lsp-diagnostics`;
- `nornyx complete`;
- `nornyx symbols`.

These commands are local scaffolds for editor extensions. They do not start a
language server, call models, use connectors, or mutate files unless the
existing `fmt --write` command is invoked explicitly.

## LLM-agent design rules

### Good Nornyx block

```yaml
agent:
  name: Builder
  input: TaskSpec
  output: PatchDiff
  allowed_paths:
    - src/**
    - tests/**
  denied_paths:
    - .env
    - secrets/**
```

### Weak Nornyx block

```yaml
agent:
  name: Builder
  role: do good coding
```

The first is checkable. The second is vague.

## Token economy

Nornyx should reduce tokens by generating compact, scoped execution packets:

```text
Goal + authoritative context + agent role + policy + gates + evidence
```

instead of dumping the full repo into every conversation.
