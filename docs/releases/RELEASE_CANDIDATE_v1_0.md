# Nornyx v1.0 Release Candidate

## Status

Local release-preparation candidate. Package metadata is prepared for `1.0.0`,
but no release tag, package publication, remote push, connector enablement,
GitHub release, or public announcement is performed by this document.

## Candidate Scope

The candidate release represents the stable local contract-language scaffold:

- frozen v0.1 block surface;
- v0.1.1 cleanup and contract hardening;
- v0.2 static graph and generic contract model;
- v0.3 optional domain profile packs;
- v0.4 contract-only adapter bridges;
- v0.5 static graph semantic validation;
- v0.6 domain-profile conformance metadata;
- v0.7 adapter and connector-contract conformance;
- v0.8 bounded execution readiness;
- v0.9 release-candidate stabilization evidence;
- v1.0 stable generalized contract-language evidence;
- parser/checker diagnostics;
- deterministic artifact generation and goal packets;
- formal grammar/schema model;
- context provenance and trust boundaries;
- safe local harness runtime;
- evidence and trace runtime;
- policy, guardrail, and capability reports;
- eval runner and integrity checks;
- plugin/connector adapter manifests;
- local editor tooling metadata.

## Required Local Validation

```bash
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
python -m nornyx.cli check examples/nornyx_v04_adapter_contracts.nyx
python -m nornyx.cli release-check --out generated/release_readiness_goal_012.json
python scripts/release/check_rc_stabilization.py
python scripts/release/check_stable_language.py
```

## No-Release Conditions

- failing tests;
- inconsistent PMO status;
- missing evidence;
- unapproved release tag, public announcement, package publication, or merge;
- secret exposure;
- live connector execution;
- production deployment behavior.

## Approval

Human release approval is mandatory before tagging, publishing, pushing release
branches, creating a GitHub release, or announcing v1.0 publicly.

GOAL-042 may be completed locally as the v1.0 stable-language evidence gate.
GOAL-043 prepares local v1.0 release metadata and release notes. Public v1.0
release remains blocked until separate human release approval is recorded.
GOAL-100 remains locked until post-v1.0 enterprise maturity is separately
approved.
