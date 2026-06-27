# GOAL-034 Evidence

## Goal

Implement the v0.2 Nornyx Graph and generic contract model as a static contract
surface.

## Result

Completed locally.

## Summary

- Added recognized `graph` and `contracts` top-level blocks.
- Added graph node/edge shape validation.
- Added unresolved graph edge reference diagnostics.
- Added generic contract validation for graph node references, approval
  references, and budget references.
- Extended the YAML-compatible schema and grammar summary with graph/contract
  definitions.
- Clarified that `schemas/nornyx_v0_1.schema.json` is a compatibility schema
  supporting both `0.1` and `0.2`.
- Added known core graph `ref` validation while leaving custom/domain kinds
  optional for future profiles and adapters.
- Updated the roadmap example to include a declarative graph contract.
- Preserved the safety boundary: no graph runtime, adapter, live connector,
  model call, automatic approval, or production execution was added.

## Validation

See `test_output.txt`.

## Risk

See `risk_note.md`.

## Handoff

See `handoff.md`.
