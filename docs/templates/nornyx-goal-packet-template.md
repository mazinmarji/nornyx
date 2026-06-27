# GOAL-XXX — Goal Title

## Goal

Define the exact delivery target.

## Scope

List files, modules, docs, tests, and generated artifacts expected.

## Non-goals

List what must not be touched.

## Context to load

```text
docs/
examples/
tests/
nornyx/
```

## Allowed paths

```text
docs/
tests/
nornyx/
examples/
scripts/
```

## Denied paths

```text
.env
secrets/
production credentials
deployment secrets
```

## Validation

```text
python -m pytest -q
python scripts/dev/audit_pmo_status.py
```

## Evidence

```text
docs/qa/evidence/GOAL-XXX/README.md
```

## Done definition

```text
implementation complete
tests pass
PMO status updated
evidence recorded
human approval ready
```
