# Evals and Guardrails

Nornyx separates three concepts:

- Tests: deterministic software correctness.
- Evals: AI behavior quality.
- Guardrails: runtime safety validation.

## Eval example

```yaml
evals:
  - name: EmailTriageEval
    metrics:
      - accuracy >= 0.92
      - pii_leakage == 0
      - false_critical_rate <= 0.03
```

## Future guardrail example

```yaml
guardrails:
  - name: SafeOutput
    validate:
      - output_schema
      - no_secrets
      - no_pii_leakage
      - confidence >= 0.75
```

## Local guardrail handling

The current local runtime does not execute guardrail validators. It records
declared guardrails as pending evidence and uses their presence to decide
whether model or connector steps are even eligible for planning. External model
or connector use remains blocked unless a declared capability and a no-secrets,
no-PII, or schema guardrail are both present.

## Eval integrity

Nornyx should prevent eval gaming using:

- holdout datasets;
- adversarial rotations;
- contamination checks;
- metric-gaming alerts;
- human review when eval score improves while incidents worsen.

## Local eval runner v0.1

GOAL-009 adds a local eval report runner:

```bash
python -m nornyx.cli eval-run examples/governed_delivery_control_plane.nyx --eval RegressionEval --out generated/eval_report.json
```

The runner:

- parses metric declarations such as `accuracy >= 0.92` and bare boolean
  metrics such as `no_secret_exposure`;
- optionally reads a local JSON results file with observed metric values;
- records pending evidence when observed values are absent;
- hashes declared local train/holdout datasets and records line counts;
- blocks train/holdout line overlap as an integrity failure;
- warns when holdout, contamination, adversarial rotation, or regression
  baseline metadata is absent;
- does not call models, tools, connectors, networks, or external datasets.

This is an eval evidence scaffold. It is not a production model-evaluation
service and it does not promote any new public `.nyx` syntax.
