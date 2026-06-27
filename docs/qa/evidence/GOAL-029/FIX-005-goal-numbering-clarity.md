# FIX-005 — Goal Numbering Clarity

## Issue

The PMO portal merged curated PMO blocks with goal packet files using title
normalization only. When a tracked goal packet used a different title variant,
the portal could show an extra packet-only card for the same `GOAL-XXX`.

The roadmap also intentionally skips some goal numbers, which made the board
look like it had missing or repeated work.

## Fix

- Added canonical `GOAL-XXX` extraction in the portal.
- Hid packet-only cards when their `GOAL-XXX` is already tracked by PMO.
- Added a compact goal numbering audit card showing skipped numbers, tracked
  packet files hidden from the board, and duplicate packet IDs.

## Safety

Display-only local portal fix. No PMO status mutation, no GitHub calls, no
remote writes, no command execution from the UI.
