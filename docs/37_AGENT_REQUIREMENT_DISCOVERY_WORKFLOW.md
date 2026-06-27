# Agent Requirement Discovery Workflow

## Purpose

This workflow tells Codex, Claude, and other coding agents what to do when they discover new gaps or requirements while implementing Nornyx.

The goal is:

```text
capture useful discoveries
avoid scope creep
continue assigned work
route future ideas through triage
```

## Rule

```text
Do not implement newly discovered scope automatically.
Record it as a triage candidate.
```

## Flow

```text
Agent works on assigned GOAL
→ agent discovers gap / requirement / future idea
→ agent checks whether it blocks current goal
→ agent writes triage candidate
→ local validator checks candidate format
→ human/architect reviews later
→ accepted candidates move into triage matrix/backlog
```

## Candidate directory

```text
docs/backlog/triage-candidates/
```

## Candidate file naming

```text
TC-YYYYMMDD-001-short-title.yaml
```

Example:

```text
TC-20260601-001-parser-error-recovery.yaml
```

## Classifications

Use only:

```text
core_now
near_core_candidate
extension_backlog
profile_specific
outside_nornyx
rejected
```

## Blocking rule

If the candidate blocks current acceptance:

```yaml
blocks_current_goal: true
recommended_action: "Stop and request human/architect decision before continuing."
```

If not blocking:

```yaml
blocks_current_goal: false
recommended_action: "Record for later review; continue assigned task."
```

## Required fields

```text
id
title
concept
source_task
discovered_by
description
classification
rationale
recommended_action
blocks_current_goal
risk
evidence
owner
status
```

## Agent behavior

### Good behavior

```text
The parser goal revealed a missing error taxonomy. I recorded TC-... as near_core_candidate and continued because it does not block this patch.
```

### Bad behavior

```text
The parser goal revealed a future LSP need, so I implemented LSP support inside this patch.
```

## Promotion process

A triage candidate can become:

```text
matrix update
backlog item
future goal
profile concept
rejected item
outside-Nornyx boundary note
```

Only a human/architect should promote it.

## Validation

```powershell
python scripts\dev\check_triage_candidates.py
python -m pytest -q tests/test_triage_candidates.py
```

## Relationship to Requirement Triage Matrix

The triage candidate workflow is the intake path.

The Requirement Triage Matrix is the accepted classification control.

```text
triage candidate → review → matrix/backlog update
```

If `concept` already exists in the matrix, the candidate classification must
match the matrix category. If the concept is new, the candidate remains
proposed and requires human/architect review before any matrix or backlog
promotion.
