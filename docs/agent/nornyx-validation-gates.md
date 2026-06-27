# Nornyx Validation Gates

## Baseline gates

```bash
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/email_triage.nyx
python -m nornyx.cli check examples/self_healing.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
python -m nornyx.cli generate examples/nornyx_roadmap_goals.nyx --out generated/nornyx_goal_plan
python -m nornyx.cli goal-plan examples/nornyx_roadmap_goals.nyx --out generated/nornyx_goal_plan
```

## Green definition

A Nornyx goal is green only when:

- tests pass;
- examples validate;
- generated artifacts are created;
- evidence folder exists;
- no new unsafe execution path is introduced;
- public syntax changes have RFC/ADR updates;
- risks are documented.
