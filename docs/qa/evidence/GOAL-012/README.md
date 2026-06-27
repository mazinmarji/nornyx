# GOAL-012 Evidence: Stable Control-Plane Release

## Summary

GOAL-012 added a local release-readiness gate for the Nornyx v1.0 release
candidate.

Implemented:

- `nornyx.release_readiness` for release candidate checks, PMO consistency,
  core goal/evidence coverage, validation commands, no-go conditions, and
  approval state;
- `nornyx release-check` CLI command;
- `scripts/release/check_release_readiness.py`;
- `docs/releases/RELEASE_CANDIDATE_v1_0.md`;
- regression tests for readiness status, approval handling, missing-doc
  blockers, and CLI report writing.

## Validation

Commands run:

```bash
python -m ruff check nornyx\release_readiness.py nornyx\cli.py scripts\release\check_release_readiness.py tests\test_release_readiness.py
python -m pytest tests\test_release_readiness.py tests\test_dev_acceleration_overlay.py -q
python scripts\release\check_release_readiness.py
python -m nornyx.cli release-check --out generated\release_readiness_goal_012.json
python -m pytest -q
python -m nornyx.cli check examples\governed_delivery_control_plane.nyx
python -m nornyx.cli check examples\nornyx_roadmap_goals.nyx
```

Result:

- focused release tests passed: `10 passed`;
- release-readiness script completed;
- release-check completed with `release_candidate_ready_pending_approval`;
- full validation passed.

## Risk Note

This patch does not publish, tag, push, merge, announce, change package version,
enable connectors, load credentials, or deploy. It records a local release
candidate and blocks release action until human approval is explicit.

## Evidence Note

The generated GOAL-012 release report records:

- `blocked: 0`;
- `requires_human_approval: 1`;
- `published: false`;
- `tag_created: false`;
- `pushed_to_remote: false`;
- `package_version_changed: false`;
- `connectors_enabled: false`;
- `network_used: false`.

## Approval

Human approval is required before merge, release tag, public announcement,
package version change, dependency addition, connector enablement, or
security-model change.
