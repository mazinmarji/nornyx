# GOAL-035 Evidence: v0.3 Domain Profiles

## Summary

GOAL-035 is completed locally. Nornyx now has optional v0.3 domain profile
packs for:

- `ai_coding`;
- `agentic_repo_harness`;
- `telecom_ops`;
- `business_ops`;
- `ai_governance`;
- `finance_ops`.

The packs layer on the v0.2 static graph/contract surface. They are metadata
and starter-document guidance only; they do not add adapters, live connectors,
model calls, automatic approvals, self-modification, production deployment, or
general-purpose programming language features.

## Evidence

- `nornyx/profiles.py`
- `profiles/*.yaml`
- `schemas/domain_profile_pack.schema.json`
- `tests/test_cli_dx.py`
- `docs/40_NORNYX_DOMAIN_PROFILES_v0_3.md`
- `docs/01_LANGUAGE_SPEC_v0_1.md`
- `docs/03_ROADMAP_TO_v1_AND_BEYOND.md`
- `docs/24_EASY_INSTALL_USE_ADAPT_INTEGRATE.md`
- `docs/pmo/status/current_status.json`

## Validation

See `test_output.txt`.

## Risk note

See `risk_note.md`.

## Handoff

See `handoff.md`.
