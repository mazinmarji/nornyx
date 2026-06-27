# ADR-0019 — Agent Requirement Discovery Workflow

## Status

Proposed

## Context

Nornyx now has a Requirement Triage Matrix. That matrix classifies concepts as:

```text
core_now
near_core_candidate
extension_backlog
profile_specific
outside_nornyx
rejected
```

However, Codex, Claude, and other coding agents will not automatically use the matrix unless the repo provides an implementation workflow.

During implementation, agents may discover real gaps. The danger is that an agent may expand the current goal and start implementing new scope.

## Decision

Nornyx will add an **Agent Requirement Discovery Workflow**.

When an agent discovers a new gap or requirement during implementation, it must:

```text
record it as a triage candidate
classify it
state whether it blocks the current goal
continue current task if non-blocking
stop/escalate if blocking
avoid implementing new scope without approval
```

## Candidate location

```text
docs/backlog/triage-candidates/
```

## Candidate format

A candidate must include:

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

## Safety rule

```text
Agents may discover requirements.
Agents may record candidates.
Agents must not implement new scope unless explicitly approved.
```

## Automation level

This workflow is local validation only.

It does not add live hooks, external connectors, LLM calls, GitHub writes, or automatic approvals.

Candidate validation checks the Requirement Triage Matrix when a candidate
names an existing `concept`. Matrix mismatches are errors; unknown concepts
remain proposed candidates for human/architect review.

## Consequences

Positive:

- captures discoveries during Codex/Claude implementation;
- prevents uncontrolled scope creep;
- gives architects a reviewable backlog;
- lets quality gates validate candidate format.

Trade-off:

- candidates still need human/architect review before promotion.
