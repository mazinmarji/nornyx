# GOAL-010 Evidence: Plugin, Connector, MCP/A2A Adapters

## Summary

GOAL-010 added a safe local connector adapter scaffold.

Implemented:

- `nornyx.connector_runtime` for plugin and connector manifest normalization,
  MCP/A2A adapter decisions, harness connector reference checks, and local
  connector reports;
- `nornyx connector-plan` CLI command;
- harness-run integration that writes `connector_report.json`, records connector
  summary in `run_manifest.json`, and adds connector planning to the trace
  bundle;
- `schemas/connector_manifest.schema.json`;
- regression tests for MCP manifest planning, unsafe live target blocking,
  undeclared harness connector blocking, experimental plugin-scoped connectors,
  CLI report writing, and harness manifest integration.

## Validation

Commands run:

```bash
python -m ruff check nornyx\connector_runtime.py nornyx\harness_runtime.py nornyx\cli.py tests\test_connector_runtime.py tests\test_harness_runtime.py
python -m pytest tests\test_connector_runtime.py tests\test_harness_runtime.py -q
python -m json.tool schemas\connector_manifest.schema.json
python -m nornyx.cli connector-plan examples\governed_delivery_control_plane.nyx --out generated\connector_report_goal_010.json
python -m nornyx.cli harness-run examples\governed_delivery_control_plane.nyx --harness DevHarness --repo . --out generated\harness_run_goal_010
python -m pytest -q
python -m nornyx.cli check examples\governed_delivery_control_plane.nyx
python -m nornyx.cli check examples\nornyx_roadmap_goals.nyx
```

Result:

- focused connector/harness tests passed: `8 passed`;
- connector schema parsed as valid JSON;
- `connector-plan` completed with status `manifest_ready` for the mission
  example because it declares no connectors;
- `harness-run` completed and wrote `connector_report.json`;
- full validation passed.

## Risk Note

This patch is manifest-only and conservative. It blocks unsupported protocols,
missing capabilities, unsafe live/write/execute modes, endpoint/command targets,
undeclared harness connector references, and A2A sensitive sharing. It does not
enable live MCP/A2A execution.

## Evidence Note

The generated GOAL-010 connector report records:

- `connectors_enabled: false`;
- `adapters_executed: false`;
- `network_used: false`;
- `commands_executed: false`;
- `credentials_loaded: false`.

## Approval

Human approval is required before merge, release, public syntax change,
dependency addition, connector enablement, or security-model change.
