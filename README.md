# Nornyx

**Nornyx** is a generalized agentic contract/control-plane language for governed AI software delivery.

It is not intended to replace Python, TypeScript, Go, Rust, or Java in v0.1. The first practical purpose is to replace scattered AI-engineering control artifacts:

- `AGENTS.md`
- skills folders
- prompt packs
- context packs
- harness scripts
- eval configs
- policy docs
- evidence templates
- approval checklists

Nornyx makes these artifacts explicit, checkable, and generatable from a single `.nyx` source of truth.

## Current repository status

This repository contains the **Nornyx v1.0.0 GitHub source release**. It includes:

- A minimal working Python CLI.
- A YAML-compatible `.nyx` syntax for v0.1.
- A checker for core references and required fields.
- A generator for `AGENTS.md`, `skills/`, `harness.yaml`, `policy.yaml`, `evals.yaml`, `context.yaml`, and `evidence_contract.md`.
- A context-pack builder with provenance hashes.
- An evidence-pack scaffold.
- Examples and tests.
- Static v0.2 graph/contract validation.
- Optional v0.3 domain profile packs.
- Contract-only v0.4 adapter bridge metadata.
- Static v0.5 graph semantic consistency diagnostics.
- Static v0.6 domain-profile conformance metadata.
- Static v0.7 adapter and connector-contract conformance reports.
- Static v0.8 bounded execution readiness reports.
- Static v0.9 release-candidate stabilization evidence.
- v1.0 stable generalized agentic contract language evidence.
- Explicit schema targets for v0.2 and v1.0, with the historical v0.1 path preserved as the compatibility default.
- v1.0.0 GitHub source release record.
- Corrected roadmap toward a stable generalized agentic contract language.

Key docs:

- [Positioning](docs/48_NORNYX_POSITIONING.md)
- [5-minute adoption](docs/49_NORNYX_5_MINUTE_ADOPTION.md)
- [Static Nornyx Graph demo](docs/50_NORNYX_GRAPH_DEMO.md)
- [Expanded Nornyx Graph demo](docs/63_NORNYX_GRAPH_DEMO_EXPANDED.md)
- [Schema version split plan](docs/51_SCHEMA_VERSION_SPLIT_PLAN.md)
- [Schema targets and examples](docs/52_SCHEMA_TARGETS_AND_EXAMPLES.md)
- [README command consistency audit](docs/53_README_COMMAND_CONSISTENCY_AUDIT.md)
- [Manifest metadata freshness](docs/54_MANIFEST_METADATA_FRESHNESS.md)
- [PMO summary noise reduction](docs/55_PMO_SUMMARY_NOISE_REDUCTION.md)
- [Manifest validation baseline refresh](docs/56_MANIFEST_VALIDATION_BASELINE_REFRESH.md)
- [v1.0.1 hygiene index refresh](docs/57_README_V101_HYGIENE_INDEX_REFRESH.md)
- [PMO next-goal label refinement](docs/58_PMO_NEXT_GOAL_LABEL_REFINEMENT.md)
- [README PMO label guidance link refresh](docs/59_README_PMO_LABEL_GUIDANCE_LINK_REFRESH.md)
- [Next strategic track after v1.0.1](docs/61_NEXT_STRATEGIC_TRACK_AFTER_V101.md)
- [v1.0 release record](docs/releases/RELEASE_RECORD_v1_0.md)

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_graph_demo.nyx
python -m nornyx.cli check examples/nornyx_graph_demo_expanded.nyx
python -m nornyx.cli schema
python -m nornyx.cli schema --version 0.2
python -m nornyx.cli schema --version 1.0
python -m nornyx.cli generate examples/governed_delivery_control_plane.nyx --out generated/governed_delivery_control_plane
python -m nornyx.cli context-build examples/governed_delivery_control_plane.nyx --repo . --out generated/context_pack.json
python -m nornyx.cli evidence-pack --out generated/evidence
python -m pytest -q
```

After the editable install, the shorter `nornyx ...` console script may also
be available in the active environment.

## Example

```yaml
nornyx: "0.1"
project:
  name: GovernedDeliveryControlPlane
  category: context_native_agentic_engineering_language

intents:
  - name: GovernedAIDelivery
    goal: "Govern AI-assisted software delivery with context, policies, evals, approvals, and evidence."

agents:
  - name: Builder
    role: "Implement small scoped patches."
    skills: [PatchBuilder, TestRepair, EvidencePack]
    policy: SafeEditPolicy

harnesses:
  - name: DevHarness
    flow:
      - agent: Builder
        action: implement
      - tool: tests
        action: run
      - evidence: DevEvidence
        action: pack
```

## Design stance

Nornyx v0.1 is an **executable AI-engineering specification layer**.

Nornyx v0.2-v1.0 roadmap target:

```text
v0.2: Nornyx Graph + stronger generic contract model.
v0.3: Optional domain profiles for ai_coding, agentic_repo_harness, telecom_ops,
      business_ops, ai_governance, and finance_ops.
v0.4: Contract-only adapter bridges for Governed Delivery Control Plane, Agentic Development Harness,
      GovernanceAdapter, telecom ops, and business ops.
v0.5-v0.9: Maturity bands for graph validation, profile conformance,
             adapter conformance, bounded execution readiness, and release-candidate stabilization.
v1.0: Stable generalized agentic contract language, released as GitHub source
      release v1.0.0.
```

v1.0.0 does not mean package publication, full autonomous runtime, a
general-purpose programming language, a production execution engine,
unrestricted connector runtime, or regulated/enterprise GOAL-100 promotion.



## Agentic repo harness integration

This updated scaffold includes a Nornyx-customized copy of common `agentic-repo-harness-template` patterns under:

```text
templates/nornyx-agentic-repo-harness/
docs/goals/
docs/agent/
.agents/skills/
scripts/agent/
```

The integration keeps the original strategic lesson: Nornyx should not replace Codex, Claude Code, Cursor, GitHub Copilot, CI/CD, or human review. Nornyx should compile, check, generate, and govern the control artifacts those execution surfaces follow.

## Phases as goals

Nornyx development is now represented as goal-led phases. Each phase has a goal packet in `docs/goals/` and a machine-readable example in `examples/nornyx_roadmap_goals.nyx`.

Use:

```bash
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
python -m nornyx.cli goal-plan examples/nornyx_roadmap_goals.nyx --out generated/nornyx_goal_plan
```

This lets every compiler/runtime phase become a bounded implementation goal with scope, non-goals, validation gates, evidence path, model routing, approval gates, and stop rules.

## Legal and safety note

The name **Nornyx** is a provisional working brand pending formal legal clearance. This repository is a safe scaffold and does not implement autonomous system modification, production deployment, destructive tool use, credential handling, or arbitrary command execution.
