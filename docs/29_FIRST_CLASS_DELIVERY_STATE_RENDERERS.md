# First-Class Delivery State Renderers

## Purpose

Nornyx should support first-class delivery state that can render into different interfaces.

This document defines the initial read-only renderer model.

## Flow

```text
docs/pmo/status/current_status.json
or generated .nyx delivery state
→ normalized delivery state
→ shell / markdown / json / portal / CI / IDE
```

## Why this matters

The PMO Portal is useful, but the language should be broader than a portal.

A developer may want:

```text
nornyx render shell
```

A CI workflow may want:

```text
nornyx render markdown --out $GITHUB_STEP_SUMMARY
```

A portal may want:

```text
nornyx render json
```

An IDE may want:

```text
nornyx render json --compact
```

## Initial safe implementation

This overlay adds pure read-only helpers:

```text
nornyx/renderers.py
scripts/dev/render_delivery_state.py
tests/test_delivery_state_renderers.py
```

## Example shell output

```text
Nornyx — baseline_partial
Next: GOAL-001 Freeze v0.1 specification

GOAL-014 — Distinct Language Developer Experience
  status: partial
  completion: 75%
  completed: 3
  pending: 2
  evidence: 4
  next: GOAL-014A
```

## Example command

```powershell
python scripts/dev/render_delivery_state.py --format shell
python scripts/dev/render_delivery_state.py --format markdown
python scripts/dev/render_delivery_state.py --format json
```

## Safety

Renderers are presentation-only.

They do not run agents, call models, call tools, modify files, deploy, approve, or self-heal.
