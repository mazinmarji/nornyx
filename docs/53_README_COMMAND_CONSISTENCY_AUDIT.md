# README Command Consistency Audit

GOAL-054 checks that public README commands align with the local validation path.

## Finding

The README quick start previously used the `nornyx` console script while the repo manifest and validation evidence used `python -m nornyx.cli`.

The console script is declared in `pyproject.toml`, but it may not be on `PATH` until a user completes an editable install in the active environment. The module form works directly from the repo checkout and matches the validation commands.

## Decision

Use `python -m nornyx.cli ...` in README command blocks for first-use reliability.

The console script remains valid after install:

```bash
nornyx check examples/governed_delivery_control_plane.nyx
```

But the public quick start now favors:

```bash
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
```

## Scope

This is command documentation alignment only. It does not change CLI behavior, parser behavior, checker behavior, schema routing, runtime execution, package publication, deployment, live connectors, automatic approvals, or GOAL-100.
