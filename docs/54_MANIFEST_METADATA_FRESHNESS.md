# Manifest Metadata Freshness

GOAL-055 clarifies which `manifest.json` metadata is current and which metadata is historical.

## Current Metadata

The current manifest should identify:

- the active v1.0.0 GitHub source-release status;
- the current command surface;
- the latest local validation result;
- the latest completed PMO goal.

Current validation is recorded in `manifest.json` under `current_validation`.

## Historical Metadata

Earlier build-provenance fields (ZIP consolidation/recheck records) were removed
from `manifest.json` ahead of the public release. They were internal assembly
notes, not part of the current test baseline.

## Boundary

This is metadata cleanup only. It does not change package metadata, publish packages, deploy software, execute runtime work, enable live connectors, change schema routing, grant approvals, or unlock GOAL-100.
