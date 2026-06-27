# GOAL-032 Evidence — Zero-Friction Adoption Pack

## Summary

Adds the first practical adoption ramp for Nornyx Lite.

## Added

```text
docs/ADRs/ADR-0021-zero-friction-adoption-ramp.md
docs/39_NORNYX_ZERO_FRICTION_ADOPTION_PACK.md
docs/backlog/nornyx-zero-friction-adoption-pack.yaml
nornyx/adoption.py
nornyx/cli.py
nornyx/dev_quality.py
scripts/dev/check_adoption_pack.py
tests/test_zero_friction_adoption.py
docs/goals/goal-032-zero-friction-adoption-pack.md
docs/qa/evidence/GOAL-032/changed_files.txt
docs/qa/evidence/GOAL-032/test_output.txt
docs/qa/evidence/GOAL-032/risk_note.md
docs/qa/evidence/GOAL-032/handoff.md
docs/qa/evidence/GOAL-032/adoption_validation.json
```

## Safety

Local deterministic helpers only.

No LLM calls, connector calls, network access, GitHub writes, production writes, or automatic approval.

## Validation

```powershell
python -m pytest -q tests/test_zero_friction_adoption.py
python scripts\dev\check_adoption_pack.py
python -m nornyx.cli adopt status --repo .
```

## Evidence note

The adoption check now validates a Lite `.nyx` draft on a temporary clean
downstream repo and verifies the generated draft passes the current checker.
It also confirms `init-lite` refuses to overwrite an existing file unless
`--force` is explicitly used.

## Risk note

Risk is medium because adoption tooling can accidentally become onboarding
automation or scope expansion. Implementation risk is low because this remains
local deterministic status, draft generation, validation, and tests only.

## Approval requirement

Human approval is required before GitHub push/PR, merge, release, live LLM
calls, portal wizard implementation, fine-tuned model pipeline, automatic
remote Git writes, automatic approval, production enforcement, or public
installer/onboarding automation.
