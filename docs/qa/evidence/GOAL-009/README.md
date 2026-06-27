# GOAL-009 Evidence: Eval Runner and Eval Integrity

## Summary

GOAL-009 added a safe local eval runner scaffold.

Implemented:

- `nornyx.eval_runtime` for metric parsing, local results comparison, dataset
  hashing, holdout checks, and train/holdout overlap detection;
- `nornyx eval-run` CLI command;
- harness-run integration that writes `eval_report.json`, records eval summary
  in `run_manifest.json`, and adds eval status to the trace bundle;
- regression tests for metric parsing, pending metric evidence, successful
  local metric evaluation, train/holdout overlap blocking, CLI output, and
  harness manifest integration.

## Validation

Commands run:

```bash
python -m ruff check nornyx\eval_runtime.py nornyx\harness_runtime.py nornyx\cli.py tests\test_eval_runtime.py tests\test_harness_runtime.py
python -m pytest tests\test_eval_runtime.py tests\test_harness_runtime.py -q
python -m nornyx.cli eval-run examples\governed_delivery_control_plane.nyx --eval RegressionEval --out generated\eval_report_goal_009.json
python -m nornyx.cli harness-run examples\governed_delivery_control_plane.nyx --harness DevHarness --repo . --out generated\harness_run_goal_009
python -m pytest -q
python -m nornyx.cli check examples\governed_delivery_control_plane.nyx
python -m nornyx.cli check examples\nornyx_roadmap_goals.nyx
```

Result:

- focused eval/harness tests passed: `8 passed`;
- `eval-run` completed with status `pending_evidence`;
- `harness-run` completed and wrote `eval_report.json`;
- full validation passed.

## Risk Note

The runner is conservative and local. Existing evals without observed metrics
now produce pending metric evidence; evals without holdout, contamination,
adversarial rotation, or baseline metadata produce integrity warnings. Actual
dataset overlap is blocked.

## Evidence Note

The generated GOAL-009 eval report records:

- `models_called: false`;
- `tools_executed: false`;
- `external_connectors_used: false`;
- `network_used: false`;
- three pending metrics for `RegressionEval`;
- four integrity warnings because the existing example has no holdout,
  contamination, adversarial rotation, or regression baseline metadata.

## Approval

Human approval is required before merge, release, public syntax change,
dependency addition, connector enablement, or security-model change.
