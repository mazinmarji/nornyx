# Nornyx Integration With Agentic Repo Harness Template

## Verdict

The `agentic-repo-harness-template` is useful and should be incorporated as a Nornyx-compatible overlay.

It should not be copied blindly as an external project template. It should be **compiled into Nornyx concepts**:

| Harness-template idea | Nornyx concept |
|---|---|
| Harness profile | `profile`, `harness`, `policy` |
| Task packet | `goal`, `task`, `contract` |
| Codex Goal Mode | `goal` + `harness` + `approval` + `stop_rules` |
| Continuous Green Loop | `harness.repair` + validation gates |
| Model routing | `budget`, `model_routing`, `risk_level` |
| MCP/private-tool safety | `connector`, `capability`, `connector_policy` |
| Agent trajectory scoring | `trace`, `eval`, `evidence` |
| PMO discipline | `evidence`, `risk`, `decision`, `approval` |
| Project retrospective | `improvement_loop`, `template_improvement_proposal` |

## Why it is needed

Nornyx is intended to become the executable source of truth for AI engineering control artifacts. The harness template already captures several operational practices that Nornyx needs:

- bounded continue-until-green execution;
- task packet discipline;
- phase/goal branch structure;
- validation gates;
- model routing;
- evidence folders;
- trajectory scoring;
- MCP/private-tool egress governance;
- human-approved delivery.

## Integration rule

Nornyx must absorb the template as a reusable pattern, not depend on it as an unmanaged folder copy.

Correct:

```text
Nornyx .nyx source
→ nornyx check
→ nornyx generate
→ AGENTS.md / CLAUDE.md / skills / harness.yaml / goals / evidence contracts
```

Incorrect:

```text
Manually edit scattered AGENTS.md, skills, prompts, scripts, policies, and task docs forever.
```

## Included customized overlay

This repo now includes:

```text
templates/nornyx-agentic-repo-harness/
docs/goals/
docs/agent/nornyx-goal-mode-policy.md
scripts/agent/run-nornyx-validation-gates.sh
scripts/agent/check-nornyx-goal-ready.sh
.agents/skills/
examples/nornyx_roadmap_goals.nyx
```

## Safety stance

The overlay is safe by default:

- no production access;
- no secret handling;
- no automatic MCP enablement;
- no destructive commands;
- no autonomous self-modification;
- no merge/deploy without human approval.
