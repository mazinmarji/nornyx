# GOAL-007 Evidence — Evidence and Trace Runtime

## Summary

GOAL-007 adds structured local evidence and trace output compatible with later
OpenTelemetry integration. Harness runs now write a trace bundle, trace digest,
and evidence manifest with artifact hashes and runtime artifact references.

No telemetry exporter, network path, model call, connector, credential access,
or external observability service is enabled.

## Changed files

```text
docs/11_OBSERVABILITY_EVIDENCE.md
docs/pmo/status/current_status.json
docs/qa/evidence/GOAL-007/README.md
nornyx/evidence.py
nornyx/harness_runtime.py
nornyx/trace_runtime.py
tests/test_evidence_trace_runtime.py
tests/test_harness_runtime.py
```

## Validation

```powershell
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
python -m nornyx.cli harness-run examples/governed_delivery_control_plane.nyx --harness DevHarness --repo . --out generated/harness_run_goal_007
```

Final validation on 2026-05-31:

```text
python -m pytest -q
115 passed in 3.98s

python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
Nornyx check passed

python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
Nornyx check passed

python -m nornyx.cli harness-run examples/governed_delivery_control_plane.nyx --harness DevHarness --repo . --out generated/harness_run_goal_007
Harness run manifest written to generated\harness_run_goal_007\run_manifest.json

python -m ruff check nornyx\trace_runtime.py nornyx\evidence.py nornyx\harness_runtime.py tests\test_evidence_trace_runtime.py tests\test_harness_runtime.py
All checks passed!
```

Trace/evidence spot check:

```text
trace bundle schema: nornyx.trace_bundle.v0.1
event_count: 11
opentelemetry compatibility: local-json-shape-no-exporter
trace digest algorithm: sha256
evidence manifest trace digest: present
```

## Risk

Medium to high. Evidence and trace outputs are audit-sensitive. This patch only
writes local structured artifacts and hashes; it does not export telemetry,
grant approvals, execute runtime tools, enable connectors, call models, or
change security enforcement.

## Approval

No external approval is required for this local-only evidence/trace runtime
patch. Human approval is still required before any merge/release/public syntax
change, dependency addition, connector enablement, telemetry exporter, security
model change, or runtime execution capability.
