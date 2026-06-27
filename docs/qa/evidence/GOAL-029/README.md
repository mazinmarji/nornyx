# GOAL-029 Evidence — Developer PMO Portal Git Status and Vision Map Refresh

## Summary

Adds the requested Developer PMO Portal refresh using the uploaded repo as source of truth.

## Added / changed

```text
apps/nornyx-dev-pmo-portal/server.py
apps/nornyx-dev-pmo-portal/app.js
apps/nornyx-dev-pmo-portal/styles.css
apps/nornyx-dev-pmo-portal/README.md
tests/test_nornyx_dev_pmo_portal_git_status.py
tests/test_nornyx_dev_pmo_portal_goal_packets.py
docs/goals/goal-029-developer-pmo-portal-git-vision-refresh.md
docs/qa/evidence/GOAL-029/changed_files.txt
docs/qa/evidence/GOAL-029/test_output.txt
docs/qa/evidence/GOAL-029/risk_note.md
docs/qa/evidence/GOAL-029/handoff.md
docs/qa/evidence/GOAL-029/kpi_status.json
```

## Capability

```text
PMO boxes
local Git branch/commit/dirty/ahead/behind status
optional remote GitHub branch SHA/status
inspiring vision map from vision_map.maps
goal/work cards
15-second refresh
read-only KPI panel
```

## Safety

```text
local-only by default
read-only git CLI
no shell=True
no UI command execution
no GitHub token
no LLM calls
no production writes
```

## Validation

```powershell
python -m pytest -q tests/test_nornyx_dev_pmo_portal_git_status.py
python apps\nornyx-dev-pmo-portal\server.py --enable-all
```

## Evidence note

GOAL-029 now includes a read-only local KPI endpoint and panel. The browser
verification loaded the local portal, confirmed the Git panel, KPI panel, vision
map, and GOAL-029 card render, and confirmed no horizontal overflow on the
checked viewport.

## Risk note

Risk is medium because the portal displays Git and PMO state that could be
mistaken for a control surface. Implementation risk is low because the portal
uses read-only local JSON, deterministic KPI helpers, and allowlisted Git
commands only.

## Approval requirement

Human approval is required before GitHub push/PR, merge, public hosting,
GitHub-token integration, UI command execution, write actions, production
deployment, external connectors, or LLM calls.
