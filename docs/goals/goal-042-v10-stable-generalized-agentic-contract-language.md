# GOAL-042: v1.0 stable generalized agentic contract language

## Phase

v1.0

## Goal

Stabilize Nornyx as a generalized agentic contract language with stable graph
model, contract schema, checker, profiles, adapters, policy/eval/evidence
semantics, approval gates, artifact generation, and safe interoperability rules.

## Non-goals

- Do not claim full autonomous runtime.
- Do not replace LangGraph, CrewAI, LangChain, Codex, Claude Code, MCP, A2A, or OPA.
- Do not become a general-purpose programming language.
- Do not enable unrestricted connector runtime.

## Scope

- `docs/`
- `schemas/`
- `examples/`
- `nornyx/`
- `tests/`
- `scripts/`

## Validation

```bash
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
```

## Evidence

`docs/qa/evidence/GOAL-042/`

## Result

Completed locally as a stable-language certification surface:

- added local stable-language report builder;
- added `stable-language-check` CLI command and release script;
- added `schemas/stable_language_report.schema.json`;
- documented the v1.0 stable generalized contract-language boundary;
- updated PMO status while keeping GOAL-100 locked.

This does not publish, tag, push, change package versions, deploy, enable live
connectors, call models, grant approvals, self-modify, or promote GOAL-100.

## Approval

Human approval is mandatory before v1.0 release.

## Stop rules

Stop if v1.0 is framed as production execution, broad autonomy, unrestricted
connectors, self-modification, or a general-purpose language.
