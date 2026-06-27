# GOAL-055 - Manifest Metadata Freshness Cleanup

## Status

Completed locally and prepared for GitHub merge.

## Goal

Refresh `manifest.json` so current validation and historical ZIP verification metadata are clearly separated.

## Scope

- Add current validation metadata to `manifest.json`.
- Move old ZIP-era verification details under an explicitly historical section.
- Update stale roadmap/schema wording in the manifest.
- Add manifest metadata regression tests.
- Update PMO and evidence.

## Non-Goals

- No package version changes.
- No package publication.
- No runtime execution.
- No live connector execution.
- No parser/checker/schema behavior changes.
- No deployment.
- No GOAL-100 promotion.

## Validation

- `python -m pytest -q`
- `python -m pytest tests/test_manifest_metadata.py -q`
- `python -m json.tool manifest.json`
- `python -m nornyx.cli release-check --approved`
- `python scripts/release/check_stable_language.py --approved`
- `python scripts/dev/audit_pmo_status.py`
- `git diff --check`

## Evidence

- `docs/54_MANIFEST_METADATA_FRESHNESS.md`
- `docs/qa/evidence/GOAL-055/README.md`
- `docs/qa/evidence/GOAL-055/test_output.txt`

## Approval

Required before package publication, deployment, runtime execution, live connectors, or GOAL-100 promotion.
