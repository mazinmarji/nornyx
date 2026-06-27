# GOAL-008 Evidence: Policy, Guardrail, and Capability Enforcement

## Summary

GOAL-008 added local, read-only policy enforcement for harness planning.

Implemented:

- `nornyx.policy_runtime` for policy rule normalization, capability decisions,
  guardrail declarations, and harness policy reports;
- `nornyx policy-check` CLI command;
- harness-run integration that writes `policy_report.json`, records policy
  summary in `run_manifest.json`, and links policy artifacts into evidence;
- default-deny behavior for undeclared tool, connector, and model capabilities;
- guardrail requirement for planned model or connector use;
- regression coverage for capability allow/deny, model guardrail blocking, CLI
  report writing, and harness manifest integration.

## Validation

Commands run:

```bash
python -m ruff check nornyx\policy_runtime.py nornyx\harness_runtime.py nornyx\cli.py tests\test_policy_runtime.py tests\test_harness_runtime.py
python -m pytest tests\test_policy_runtime.py tests\test_harness_runtime.py -q
python -m nornyx.cli policy-check examples\governed_delivery_control_plane.nyx --harness DevHarness --out generated\policy_report_goal_008.json
python -m nornyx.cli harness-run examples\governed_delivery_control_plane.nyx --harness DevHarness --repo . --out generated\harness_run_goal_008
python -m pytest -q
python -m nornyx.cli check examples\governed_delivery_control_plane.nyx
python -m nornyx.cli check examples\nornyx_roadmap_goals.nyx
```

Result:

- focused policy/harness tests passed: `8 passed`;
- `policy-check` completed and reported one blocked undeclared tool capability;
- `harness-run` completed with status `planned_with_policy_blocks`;
- full validation passed.

## Risk Note

This patch is intentionally conservative. Existing harnesses that mention tools,
models, or connectors without explicit capabilities will now surface policy
blocks in local reports. The runtime still does not execute agents, tools,
connectors, models, arbitrary commands, repairs, or approvals.

## Evidence Note

The generated GOAL-008 policy report records:

- `default_capability_mode: deny_unless_declared`;
- `tools_executed: false`;
- `models_called: false`;
- `connectors_enabled: false`;
- one blocked `tool: tests` step in `examples/governed_delivery_control_plane.nyx` because
  no matching capability is declared.

## Approval

Human approval is required before merge, release, public syntax change,
dependency addition, connector enablement, or security-model change.
