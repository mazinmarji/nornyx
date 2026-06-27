# Nornyx v1.0 Release Notes

## Status

Nornyx v1.0.0 is published as a GitHub source release:
`https://github.com/mazinmarji/nornyx/releases/tag/v1.0.0`.

This is a source release for the stable generalized agentic contract/control-
plane language. It is not package publication, production deployment, live
connector execution, automatic approval, self-modification, or regulated/
enterprise GOAL-100 promotion.

## Release Theme

Nornyx v1.0 stabilizes the repository as a generalized agentic contract
language for governed AI/software delivery control artifacts.

## Included Scope

- frozen v0.1 control-plane scaffold;
- v0.1.1 cleanup and contract hardening;
- v0.2 static graph and generic contract model;
- v0.3 optional domain profiles;
- v0.4 contract-only adapter bridges;
- v0.5 graph validation diagnostics;
- v0.6 profile conformance metadata;
- v0.7 adapter and connector-contract conformance;
- v0.8 bounded execution readiness reports;
- v0.9 release-candidate stabilization evidence;
- v1.0 stable generalized contract-language evidence;
- GOAL-043 local release metadata preparation;
- GOAL-044 release-prep GitHub merge;
- GOAL-045 v1.0.0 tag and GitHub release;
- GOAL-046 post-release PMO/evidence record.

## Safety Boundary

This release is a stable contract-language milestone. It is not:

- a full autonomous runtime;
- a general-purpose programming language;
- a production execution engine;
- live MCP/A2A connector execution;
- automatic approval or self-modification;
- regulated/enterprise GOAL-100 promotion.

## Release Gates

The v1.0.0 GitHub source release was created after approved release gates:

```bash
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
python -m nornyx.cli check examples/nornyx_v04_adapter_contracts.nyx
python -m nornyx.cli release-check --approved
python scripts/release/check_rc_stabilization.py --approved
python scripts/release/check_stable_language.py --approved
python scripts/dev/audit_pmo_status.py
```

Package publication, deployment, live connector execution, and GOAL-100 remain
separate approval-gated work.
