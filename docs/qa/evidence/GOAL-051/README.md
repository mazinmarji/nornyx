# GOAL-051 Evidence - Schema Version Split Implementation

## Changed Files

- `schemas/nornyx_v0_1.schema.json`
- `schemas/nornyx_v0_2.schema.json`
- `schemas/nornyx_v1_0.schema.json`
- `nornyx/schema_model.py`
- `nornyx/cli.py`
- `tests/test_schema_model.py`
- `docs/goals/goal-051-schema-version-split-implementation.md`
- `docs/qa/evidence/GOAL-051/README.md`
- `docs/qa/evidence/GOAL-051/changed_files.txt`
- `docs/qa/evidence/GOAL-051/risk_note.md`
- `docs/qa/evidence/GOAL-051/handoff.md`
- `docs/qa/evidence/GOAL-051/test_output.txt`
- `README.md`
- `manifest.json`
- `docs/pmo/status/current_status.json`

## Result

GOAL-051 adds explicit versioned schema targets and a schema registry while preserving the compatibility default.

## Validation

See `test_output.txt`.

## Risk Note

See `risk_note.md`.

## Approval Note

Approval remains required before removing compatibility aliases, changing default schema behavior, publishing, deploying, enabling live connectors, or unlocking GOAL-100.
