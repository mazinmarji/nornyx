# GOAL-043: v1.0 public release preparation

## Phase

v1.0 release preparation

## Goal

Prepare v1.0 release metadata and release notes locally after GOAL-042 stable
contract-language completion.

## Non-goals

- Do not create a release tag.
- Do not publish a package.
- Do not create a GitHub release.
- Do not push or merge release-prep changes.
- Do not enable live connectors or production deployment.
- Do not unlock GOAL-100.

## Scope

- `pyproject.toml`
- `nornyx/__init__.py`
- `manifest.json`
- `docs/releases/`
- `docs/pmo/status/current_status.json`
- `docs/qa/evidence/GOAL-043/`
- release-readiness tests

## Result

Completed locally:

- prepared package metadata at `1.0.0`;
- added v1.0 release notes;
- clarified release-candidate notes for the prepared metadata state;
- updated PMO status and evidence while preserving approval gates.

## Validation

```bash
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
python -m nornyx.cli check examples/nornyx_v04_adapter_contracts.nyx
python -m nornyx.cli release-check
python scripts/release/check_rc_stabilization.py
python scripts/release/check_stable_language.py
python scripts/dev/audit_pmo_status.py
```

## Evidence

`docs/qa/evidence/GOAL-043/`

## Approval

Human approval was provided to prepare release metadata locally. Separate
approval remains mandatory before tag creation, package publication, GitHub
release creation, public announcement, or GOAL-100 work.
