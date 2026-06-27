# GOAL-005 Evidence — Context Provenance and Trust Boundaries

## Summary

GOAL-005 adds explicit provenance, taint, channel separation, and authority
ordering to context pack generation. Context packs now identify repo file
source URIs, hashes, channel, trust level, authority rank, and whether a source
may define policy.

## Changed files

```text
docs/06_CONTEXT_ENGINEERING.md
docs/pmo/status/current_status.json
docs/qa/evidence/GOAL-005/README.md
examples/governed_delivery_control_plane.nyx
nornyx/context_builder.py
tests/test_context_provenance.py
```

## Validation

```powershell
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
python -m nornyx.cli context-build examples/governed_delivery_control_plane.nyx --repo . --out generated/context_pack_goal_005.json
```

Initial validation on 2026-05-31:

```text
python -m pytest -q
109 passed in 3.27s

python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
Nornyx check passed

python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
Nornyx check passed

python -m nornyx.cli context-build examples/governed_delivery_control_plane.nyx --repo . --out generated/context_pack_goal_005.json
Context pack written to generated\context_pack_goal_005.json with 182 entries
```

Generated context pack spot check:

```text
schema: nornyx.context_pack.v0.1
authority_order:
- docs/01_LANGUAGE_SPEC_v0_1.md
- docs/05_SECURITY_MODEL.md
- docs/agent/SAFE_COMMANDS.md
- tests/**/*.py

docs/01_LANGUAGE_SPEC_v0_1.md:
  channel: authoritative_repo
  trust_level: authoritative
  authority_rank: 1
  may_define_policy: true
```

## Risk

Medium. Context trust metadata is security-relevant and future enforcement may
depend on it. This patch records trust boundaries but does not execute context,
grant tool permissions, add external retrieval, bypass approvals, or implement
runtime policy enforcement.

## Approval

No external approval is required for this local-only scoped metadata patch.
Human approval is still required before any merge/release/public syntax change,
dependency addition, connector enablement, or security-model change.
