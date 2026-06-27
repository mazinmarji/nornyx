# Nornyx Developer PMO Portal

## Purpose

The Nornyx Developer PMO Portal is a local control-room view for Nornyx language development. It tracks the roadmap as goal-led delivery:

```text
Nornyx roadmap → phases → goals → validation gates → evidence → approval → next goal
```

## Why this exists

The pattern is adapted from the AlpacaPilot AI Developer PMO Portal, where an internal portal reads a committed PMO status JSON through a gated developer endpoint. For Nornyx, the same idea is used to make language development visible and governed without adding a production service.

## Files

```text
apps/nornyx-dev-pmo-portal/
  index.html
  app.js
  styles.css
  server.py
  README.md

docs/pmo/status/current_status.json
scripts/pmo/generate_nornyx_pmo_status.py
scripts/agent/run-nornyx-pmo-portal.sh
scripts/agent/run-nornyx-pmo-portal.ps1
tests/test_dev_pmo_status_contract.py
```

## Run

```bash
ENABLE_DEV_PMO_API=true python apps/nornyx-dev-pmo-portal/server.py
```

Open:

```text
http://127.0.0.1:5174
```

## Regenerate status JSON

```bash
python scripts/pmo/generate_nornyx_pmo_status.py
```

## Safety rules

- Local developer use only.
- API disabled unless `ENABLE_DEV_PMO_API=true`.
- No LLM calls.
- No external connectors.
- No shell execution from browser.
- No secrets or credentials.
- No production deployment path.

## Acceptance

```bash
python -m pytest -q tests/test_dev_pmo_status_contract.py
ENABLE_DEV_PMO_API=true python apps/nornyx-dev-pmo-portal/server.py
```
