# Harness Engineering in Nornyx

A harness is the controlled execution loop around AI work.

## Harness responsibilities

- load context;
- assign agent role;
- enforce policy;
- run tools;
- run tests;
- run evals;
- repair failures;
- request approval;
- collect trace;
- produce evidence.

## Example

```yaml
harnesses:
  - name: DevHarness
    context: RepoContext
    flow:
      - agent: Architect
        action: plan
      - agent: Builder
        action: implement
      - tool: tests
        action: run
      - agent: Reviewer
        action: review
      - evidence: DevEvidence
        action: pack
    repair:
      - on: test_failure
        agent: Builder
        action: repair
        max_attempts: 3
```

## v1.0 runtime contract

A harness run should produce:

- run manifest;
- context pack;
- agent prompts/contracts;
- test/eval outputs;
- policy decisions;
- trace events;
- evidence pack;
- approval log.

## v0.3 MVP runtime

The v0.3 runtime is intentionally safe and local. It plans a harness run and
writes metadata, but it does not execute agents, tools, evals, repair loops, or
external connectors.

The MVP command:

```bash
python -m nornyx.cli harness-run examples/governed_delivery_control_plane.nyx --harness DevHarness --out generated/harness_run
```

The runtime writes:

- `run_manifest.json`;
- `context_pack.json`;
- `policy_report.json`;
- `trace_bundle.json`;
- `trace_digest.json`;
- `approval_log.json`;
- an evidence scaffold.

Validation gates are recorded as pending evidence or pending human approval.
Repair loops are bounded to at most three attempts and are recorded as
`not_executed`.

GOAL-008 adds policy/capability planning to this safe local runtime. Tool,
connector, and model flow steps default to denied unless explicitly declared in
`capabilities`; connector and model steps also require a declared safety
guardrail. These checks change only the manifest status and report contents;
they do not grant execution rights.

GOAL-009 adds eval report planning to harness runs. Eval flow steps produce a
local `eval_report.json` with metric evidence status and integrity checks, but
the harness still does not execute models, tools, connectors, or eval services.

GOAL-010 adds connector adapter planning to harness runs. The runtime writes a
local `connector_report.json` that records plugin/connector manifest status and
harness connector references. Connector adapters remain disabled and
`not_executed`.
