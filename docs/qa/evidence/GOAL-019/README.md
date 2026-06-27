# GOAL-019 Evidence — AI Pattern Lifecycle

## Summary

Adds a small optional AI Pattern Lifecycle extension to help Nornyx convert prompt tricks, agent workflows, repo ideas, and tool rituals into evidence-backed engineering patterns.

## Added

```text
docs/decisions/ADR-0013-from-ai-folklore-to-engineering-patterns.md
docs/31_AI_PATTERN_LIFECYCLE.md
schemas/pattern_lifecycle.schema.json
examples/nornyx_pattern_lifecycle.nyx
nornyx/patterns.py
tests/test_pattern_lifecycle.py
```

## Safety

This is validation and documentation only.

No LLM calls, external connectors, shell execution, credentials, GitHub writes, approvals, deploys, or autonomous actions are added.

## Validation

```text
python -m pytest -q tests/test_pattern_lifecycle.py
```
