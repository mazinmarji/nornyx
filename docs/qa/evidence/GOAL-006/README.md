# GOAL-006 Evidence — Harness Runtime MVP

## Summary

GOAL-006 adds a safe local harness runtime MVP. The runtime resolves a harness,
builds a context pack, records planned flow steps, validation gates, bounded
repair metadata, trace events, approval requirements, and an evidence scaffold.
It does not execute agents, tools, evals, repairs, shell commands, or external
connectors.

## Changed files

```text
docs/07_HARNESS_ENGINEERING.md
docs/pmo/status/current_status.json
docs/qa/evidence/GOAL-006/README.md
nornyx/cli.py
nornyx/harness_runtime.py
tests/test_harness_runtime.py
```

## Validation

```powershell
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
python -m nornyx.cli harness-run examples/governed_delivery_control_plane.nyx --harness DevHarness --repo . --out generated/harness_run_goal_006
```

Initial validation on 2026-05-31:

```text
python -m pytest -q
112 passed in 4.80s

python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
Nornyx check passed

python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
Nornyx check passed

python -m nornyx.cli harness-run examples/governed_delivery_control_plane.nyx --harness DevHarness --repo . --out generated/harness_run_goal_006
Harness run manifest written to generated\harness_run_goal_006\run_manifest.json
```

Harness manifest spot check:

```text
schema: nornyx.harness_run.v0.1
tools_executed: false
agents_executed: false
repairs_executed: false
external_connectors_used: false
arbitrary_commands_allowed: false

tests.pass: pending_evidence
security.pass: pending_evidence
human_approval_before_merge: requires_human_approval
```

Broader validation note:

```text
bash scripts/agent/run-nornyx-validation-gates.sh
failed in this Windows bash environment because `python` was not on the bash PATH.

Equivalent remaining gates were run directly with PowerShell:
python -m nornyx.cli check examples/email_triage.nyx
python -m nornyx.cli check examples/self_healing.nyx
python -m nornyx.cli generate examples/nornyx_roadmap_goals.nyx --out generated/nornyx_goal_plan
python -m nornyx.cli goal-plan examples/nornyx_roadmap_goals.nyx --out generated/nornyx_goal_plan

All four direct commands passed.
```

## Risk

Medium to high. Harness runtime is safety-sensitive, so this MVP is deliberately
manifest-only. It records gates and bounded repair metadata but does not execute
commands, run tools, call models, grant approvals, enable connectors, or mutate
production state.

## Approval

No external approval is required for this local-only manifest runtime patch.
Human approval is still required before any merge/release/public syntax change,
dependency addition, connector enablement, security-model change, or runtime
execution capability.
