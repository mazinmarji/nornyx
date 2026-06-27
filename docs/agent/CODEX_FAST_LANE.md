# Codex Fast Lane for Nornyx

## Purpose

This is the default operating lane for Codex/Claude development in this repo.

## Before coding

1. Identify the active goal.
2. Read the goal file under `docs/goals/`.
3. Confirm allowed and denied paths.
4. Use the smallest coherent patch.
5. Do not expand scope automatically.

## During coding

```text
task packet
→ focused implementation
→ focused tests
→ full local quality when appropriate
→ evidence
→ handoff
```

## Required behavior

- Keep changes inside the assigned goal.
- Add or update tests with code changes.
- Record newly discovered non-blocking gaps as triage candidates under `docs/backlog/triage-candidates/`.
- Stop if a blocking requirement is discovered.
- Do not touch secrets, production data, deploy config, or unrelated portal/apps unless assigned.

## Validation

Use the smallest relevant command first, then broader checks:

```powershell
python -m pytest -q tests/<focused-test>.py
python scripts\dev\run_quality.py --profile fast
python scripts\dev\run_quality.py --profile standard
```

## Evidence

Before handoff, provide:

```text
changed files
test output
risk note
known limitations
triage candidates, if any
next recommended action
```
