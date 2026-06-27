# Nornyx v1.0 Release Record

## Release

- Version: `v1.0.0`
- GitHub release: `https://github.com/mazinmarji/nornyx/releases/tag/v1.0.0`
- Tag: `v1.0.0`
- Target commit: `ba568241b95489e5a5a3e6522041e33eff12cf97`
- Published at: `2026-06-03T10:33:15Z`
- Release notes: `docs/releases/RELEASE_NOTES_v1_0.md`

## Validation

Before release:

- `python -m pytest -q` passed;
- `python -m nornyx.cli release-check --approved` passed with no blockers;
- `python scripts/release/check_rc_stabilization.py --approved` passed with no blockers;
- `python scripts/release/check_stable_language.py --approved` passed with no blockers;
- `python scripts/dev/audit_pmo_status.py` passed.

After release:

- GitHub release exists and is not draft or prerelease;
- local `main` is clean and aligned with `origin/main`;
- GOAL-100 remains locked.

## Boundary

The v1.0 GitHub release is a public source release for the stable generalized
agentic contract language. It does not publish a Python package, deploy
software, enable live connector execution, or promote GOAL-100.
