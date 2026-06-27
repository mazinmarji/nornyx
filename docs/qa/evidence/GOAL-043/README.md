# GOAL-043 Evidence

## Goal

Prepare v1.0 release metadata and release notes locally after GOAL-042, without
tagging, publishing, creating a GitHub release, pushing, or unlocking GOAL-100.

## Summary

- `pyproject.toml` and `nornyx/__init__.py` now record `1.0.0`.
- `manifest.json` records local release-prep status.
- `docs/releases/RELEASE_NOTES_v1_0.md` records the future release notes.
- `docs/releases/RELEASE_CANDIDATE_v1_0.md` clarifies that metadata is prepared
  while public release actions remain blocked.
- PMO records GOAL-043 completed locally and GOAL-100 locked.

## Boundary

This evidence does not authorize or perform tag creation, package publication,
GitHub release creation, remote push, public announcement, production
deployment, live connector execution, automatic approvals, self-modification,
or GOAL-100 promotion.

## Validation

See `test_output.txt`.
