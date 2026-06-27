# FIX-004: Show Packet-Only Goals in PMO Portal

## Issue

The Developer PMO Portal displayed only curated `status.blocks` from
`docs/pmo/status/current_status.json`. Because the frontend returned those
blocks immediately, it ignored goal packet files collected by the API under
`docs/goals/`.

## Fix

- Added lightweight goal packet metadata in the PMO server.
- Updated the frontend to merge curated PMO blocks with untracked goal packet
  files.
- Untracked packets now render as `packet_only` cards with 0% completion and a
  note that they are not yet tracked in the PMO ledger.
- Existing PMO block semantics remain unchanged.

## Validation

Commands run:

```bash
python -m pytest tests\test_nornyx_dev_pmo_portal_git_status.py tests\test_nornyx_dev_pmo_portal_goal_packets.py tests\test_nornyx_dev_pmo_portal_favicon.py -q
python -m ruff check tests\test_nornyx_dev_pmo_portal_git_status.py tests\test_nornyx_dev_pmo_portal_goal_packets.py apps\nornyx-dev-pmo-portal\server.py
```

Result:

- focused portal tests passed: `10 passed`;
- Ruff passed.

## Evidence Note

The patched API now exposes parsed goal packet metadata such as `GOAL-012:
Stable control-plane release`, and the frontend no longer short-circuits when
curated PMO blocks exist.

## Risk Note

Packet-only cards are deliberately shown as untracked and 0% complete, so the
portal does not imply PMO progress for goals that are not yet curated in
`current_status.json`.
