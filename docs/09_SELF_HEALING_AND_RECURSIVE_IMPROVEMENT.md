# Self-Healing and Recursive Improvement

Nornyx should support self-healing and self-improvement only as bounded, auditable, approval-gated workflows.

## Bad pattern

```text
Agent freely rewrites itself or production code.
```

## Correct pattern

```text
Agent proposes improvement -> checker validates -> tests/evals run -> policy checks -> human approves high-risk changes -> evidence is stored.
```

## Future blocks

```yaml
healing:
  observe: [logs, traces, metrics, failing_tests]
  diagnose_by: DiagnoseAgent
  repair_mode: propose_only
  validate: [tests, evals, policy]
  gate: [human_approval_if_production_change]
```

```yaml
improvement_loop:
  target: [prompts, skills, context_playbooks, harness_steps]
  propose_by: ResearchAgent
  require:
    - improvement_score_above_baseline
    - no_policy_regression
    - no_security_regression
```

## Non-negotiable safety rule

Self-improvement must never be allowed to weaken the constitution, bypass policy, hide evidence, erase traces, or remove approval gates.
