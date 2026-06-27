# Codex Task Packet

## Goal ID

`GOAL-XXX`

## Objective

State the smallest deliverable.

## Allowed files

```text
nornyx/
tests/
docs/goals/
docs/qa/evidence/
```

## Denied files

```text
.env
secrets/**
production-data/**
node_modules/**
generated/**
```

## Required validation

```powershell
python -m pytest -q <focused tests>
python scripts\dev\run_quality.py --profile fast
```

## Evidence required

```text
changed files
test output
risk note
handoff note
```

## Stop rules

```text
same test fails twice
scope expansion required
blocked decision discovered
denied path touched
secret/credential risk found
```

## Triage candidate rule

If a new useful but non-blocking requirement is found, create a candidate in:

```text
docs/backlog/triage-candidates/
```

Do not implement it unless it is explicitly part of this task.
