# Observability and Evidence

Nornyx should make AI work observable and auditable.

## Trace events

Capture:

- context loaded;
- prompt/model call;
- tool call;
- memory read/write;
- policy decision;
- guardrail result;
- approval event;
- file change;
- test/eval result;
- evidence creation.

## Evidence packs

A delivery evidence pack should include:

- patch.diff;
- changed_files.zip;
- test report;
- eval report;
- security report;
- risk update;
- approval log;
- trace digest;
- generated artifact manifest.

## v0.3 local runtime format

GOAL-007 adds local structured outputs that are compatible with later
OpenTelemetry integration without exporting telemetry:

- `trace_bundle.json` with local span-like events;
- `trace_digest.json` with a SHA-256 digest over the event list;
- `policy_report.json` with local policy, guardrail, and capability decisions;
- `eval_report.json` with local metric and eval-integrity decisions;
- `connector_report.json` with local plugin and connector adapter decisions;
- `evidence/evidence_manifest.json` with artifact hashes and runtime artifact references.

The trace event shape includes:

- `trace_id`;
- `span_id`;
- `parent_span_id`;
- `name`;
- `kind`;
- `start_time_unix_nano`;
- `end_time_unix_nano`;
- `attributes`;
- `status`.

No exporter, network path, model call, connector, or external observability
service is enabled by this runtime.

## Enterprise target

Nornyx evidence should be usable by engineering leads, security teams, PMO, auditors, and release managers.
