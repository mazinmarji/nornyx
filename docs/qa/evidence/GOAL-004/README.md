# GOAL-004 Evidence — Formal Grammar and Schema Model

## Summary

GOAL-004 introduces a formal model layer for Nornyx while preserving the
YAML-compatible v0.1 migration path. The patch adds an EBNF-style grammar
summary, a JSON Schema document for the frozen v0.1 block surface, a small
schema model module, and a CLI inspection command.

## Changed files

```text
docs/RFCs/RFC-0002-formal-grammar-and-schema-model.md
docs/pmo/status/current_status.json
docs/qa/evidence/GOAL-004/README.md
nornyx/cli.py
nornyx/schema_model.py
schemas/nornyx_v0_1.schema.json
tests/test_schema_model.py
```

## Validation

```powershell
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
python -m nornyx.cli schema
python -m nornyx.cli schema --format grammar
```

Final validation on 2026-05-31:

```text
python -m pytest -q
107 passed in 2.42s

python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
Nornyx check passed

python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
Nornyx check passed

python -m nornyx.cli schema
returned schema summary with no issues

python -m nornyx.cli schema --format grammar
printed the v0.1 formal grammar summary
```

## Risk

Medium. This adds a formal model that future tooling may rely on, but it is
descriptive and compatible with existing YAML-based `.nyx` files. It does not
replace the parser, add dependencies, enable connectors, execute artifacts,
bypass approvals, or change security semantics.

## Approval

No external approval is required for this local-only scoped model patch. Human
approval is still required before any merge/release/public syntax change,
dependency addition, connector enablement, or security-model change.
