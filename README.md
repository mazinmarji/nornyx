# Nornyx

[![PyPI](https://img.shields.io/pypi/v/nornyx.svg)](https://pypi.org/project/nornyx/)
[![Python](https://img.shields.io/pypi/pyversions/nornyx.svg)](https://pypi.org/project/nornyx/)
[![CI](https://github.com/mazinmarji/nornyx/actions/workflows/ci.yml/badge.svg)](https://github.com/mazinmarji/nornyx/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**A generalized agentic contract/control-plane language for governed AI software delivery.**

```bash
pip install nornyx
```

Your AI-engineering rules live scattered across `AGENTS.md`, a skills folder, prompt/context packs, a harness script, an eval config, policy docs, evidence templates, and approval checklists — and they **drift** out of sync. Nornyx makes them one **checked source of truth**: write a single `.nyx` file, then **generate** and **validate** all those artifacts from it.

```text
one .nyx contract  ──►  AGENTS.md · skills/ · harness.yaml · policy.yaml
                        evals.yaml · context.yaml · evidence_contract.md
```

Nornyx does **not** replace Codex, Claude Code, Cursor, Copilot, CI/CD, or human review. It compiles, checks, and generates the control artifacts those execution surfaces follow.

## Install

```bash
pip install nornyx          # from PyPI
# or pin from source:
pip install "nornyx @ git+https://github.com/mazinmarji/nornyx@main"
```

Requires Python 3.10–3.13. Runtime dependencies: **PyYAML**, **jsonschema**, and **referencing**.
The package (distribution) version is independent of the Nornyx language/schema version — see
[docs/VERSIONING.md](docs/VERSIONING.md).

## Quick start (5 minutes)

```bash
# 0. drop the bundled example contracts into ./examples/
nornyx examples

# 1. check a contract
nornyx check examples/governed_delivery_control_plane.nyx

# 2. generate the control artifacts from it
nornyx generate examples/governed_delivery_control_plane.nyx --out generated/cp

# 3. build a provenance-hashed context pack
nornyx context-build examples/governed_delivery_control_plane.nyx --repo . --out generated/context.json

# 4. inspect the schema
nornyx schema --version 1.0
```

(If you didn't install the console script, use `python -m nornyx.cli ...`.)

`nornyx generate` writes `AGENTS.md`, `skills/`, `harness.yaml`, `policy.yaml`, `evals.yaml`, `context.yaml`, and `evidence_contract.md` into the output folder — regenerate any time the `.nyx` changes, and `nornyx check` keeps them honest.

## Shell/editor completion

`nornyx complete` emits JSON completion items for `.nyx` documents. Nornyx does
not install a shell hook by default; this command is the completion data source
to wire into shell functions, editor adapters, or small helper scripts.

Top-level block suggestions:

```bash
nornyx complete --prefix con
```

Reference-aware suggestions:

```bash
nornyx complete examples/governed_delivery_control_plane.nyx --path agent.policy --prefix Safe
```

The command prints LSP-shaped objects with `label`, `kind`, `detail`, and
`insertText`, so wrappers can parse the labels and present them as candidates.

## A contract looks like this

```yaml
nornyx: "0.1"
project:
  name: GovernedDelivery

contexts:
  - name: RepoContext
    include: ["src/**/*.py", "docs/**/*.md"]
    authority: ["docs/SECURITY.md"]
    taint:                       # trust boundaries are first-class
      repo: trusted_repo_file
      user_prompt: untrusted
      external_web: untrusted

policies:
  - name: SafeEditPolicy
    rules:
      - deny secrets_to_llm
      - require tests_if_code_changed
      - require evidence_if_harness_completed

agents:
  - name: Builder
    role: "Implement small scoped patches."
    skills: [PatchBuilder, TestRepair, EvidencePack]
    policy: SafeEditPolicy

harnesses:
  - name: DevHarness
    context: RepoContext
    flow:
      - agent: Builder
        action: implement
      - tool: tests
        action: run
      - evidence: DevEvidence
        action: pack
    gate:
      - require: tests.pass
      - require: human_approval_before_merge
```

## Use it in your repo

Going from the demo to your own project is four steps:

```bash
# 1. scaffold a .nyx for your repo (pick a profile, default ai_coding)
nornyx init --name YourRepo --out nornyx.nyx

# 2. edit nornyx.nyx — your contexts, policies, agents, harness — then check it
nornyx check nornyx.nyx

# 3. generate the artifacts and put AGENTS.md where your agent reads it
nornyx generate nornyx.nyx --out .nornyx/
cp .nornyx/AGENTS.md AGENTS.md          # the file Claude Code / Cursor / Copilot read

# 4. commit nornyx.nyx (the source) and the artifacts you use
```

**Keep them from drifting.** Commit the generated directory and add a check that
it still matches the contract — in CI or a pre-commit hook:

```bash
nornyx drift nornyx.nyx --out .nornyx   # nonzero exit if ANY artifact drifts
```

`nornyx drift` compares every generated artifact by hash (not just `AGENTS.md`),
so a change to `policy.yaml` is caught too. Across **many repos**, declare your
org policy once in a workspace manifest and verify each repo matches it:

```bash
nornyx workspace-check --manifest nornyx.workspace.yaml
```

Now the `.nyx` is the single source of truth: edit it, regenerate, and the check
fails loudly if any artifact drifts. Full walkthrough:
[docs/USE_IN_YOUR_REPO.md](docs/USE_IN_YOUR_REPO.md).

### Reference a shared policy instead of copying it

A policy can **reference** a canonical definition rather than copy its rules, so
there is nothing to drift in the first place:

```yaml
policies:
  - name: SafeDeliveryPolicy
    ref: ../governance/nornyx.workspace.yaml#SafeDeliveryPolicy   # single source
```

`ref` is `<path>#<PolicyName>`, resolved from a local `.nyx` contract **or** a
workspace manifest. The canonical rules live in one place; edit them there and
every referencing contract is updated. `nornyx check` and `nornyx generate`
resolve the reference and inline the real rules into `policy.yaml`. See the
bundled [`org_policies.nyx`](nornyx/examples/org_policies.nyx) and
[`governed_service.nyx`](nornyx/examples/governed_service.nyx) examples.

## Govern packages as untrusted input

Governed package commands treat folders, repos, plugins, agent kits, and MCP
bundles as inert inputs. The scanner inventories files, hashes contents, detects
risk surfaces, redacts secret-like values, and emits evidence reports:

```bash
nornyx package scan ./some-package --out dist/package-scan
nornyx package radar ./some-package --out dist/radar_report.json
nornyx package register ./some-package --contract examples/governed_package/register_existing.nyx --out dist/registered-package
```

External evidence can be imported from existing reports without making those
tools mandatory:

```bash
nornyx package evidence import syft syft-report.json --out dist/external-evidence
nornyx package evidence import gitleaks gitleaks-report.json --out dist/external-evidence
```

Nornyx does not install, execute, start MCP servers, activate hooks, upload data,
approve, or claim a package is safe. It can say that a package was inventoried,
risk-surfaced, evidence-bound, hash-locked, and approval-gated.

## Govern an agent network across frameworks

The optional `agentic_network` profile lets one contract declare a bounded
agent network — identities, capabilities, trust zones, gates, delegations,
handoffs, relations, and revocations — then compiles deterministic control
artifacts, binds them in a content-addressed lock, and validates supplied
runtime-event evidence against that exact revision:

```bash
nornyx check examples/agentic_network_support/support_network.nyx
nornyx agentic-network generate examples/agentic_network_support/support_network.nyx --out generated/agentic_network --as-of 2026-07-17T00:00:00Z
nornyx agentic-network lock examples/agentic_network_support/support_network.nyx --artifacts generated/agentic_network --as-of 2026-07-17T00:00:00Z
nornyx agentic-network lock-check examples/agentic_network_support/support_network.nyx --artifacts generated/agentic_network --as-of 2026-07-17T00:00:00Z
python examples/agentic_network_support/run_demo.py --out demo_out
nornyx agentic-network evidence-validate examples/agentic_network_support/support_network.nyx --events demo_out/langgraph_events.json --lock demo_out/nornyx.agentic_network.lock --as-of 2026-07-17T00:00:00Z --strict
```

The same contract governs the CrewAI and LangGraph reference adapters
(`integrations/`, not packaged); AI identities can never approve; sensitive
categories are never shareable; and the demo runs offline with fake data.
Nornyx validates declarations and supplied local evidence — it is not an
agent runtime, MCP runtime, or A2A runtime, and it does not attest runtime
truth. Start with
[docs/agentic-network/00_OVERVIEW.md](docs/agentic-network/00_OVERVIEW.md).

## Why Nornyx

- **One source of truth** for agent/skill/harness/policy/eval/evidence artifacts — no more drift.
- **Context trust model:** mark which context is `trusted` vs `untrusted` so untrusted input can't define policy, and deny `secrets_to_llm` at the contract level.
- **Generators + a checker:** turn `.nyx` into the files your tools read, and verify references and required fields.
- **Generated-artifact drift gate:** catch when regenerated output diverges from a committed baseline.
- **YAML-compatible syntax** — no new parser to learn.

## Scope and safety

Nornyx is an **executable specification layer**, not a runtime. It does **not** implement autonomous system modification, production deployment, destructive tool use, credential handling, or arbitrary command execution. The name *Nornyx* is a provisional working brand (no formal legal clearance claimed).

## Learn more

- [Agentic-network governance overview](docs/agentic-network/00_OVERVIEW.md) · [end-to-end tutorial](docs/agentic-network/01_TUTORIAL.md)
- [Positioning](docs/48_NORNYX_POSITIONING.md)
- [5-minute adoption](docs/49_NORNYX_5_MINUTE_ADOPTION.md)
- [Governed Package Profile](docs/governed-package-profile.md)
- [Public boundary policy](docs/public-boundary-policy.md)
- [Nornyx Graph demo](docs/50_NORNYX_GRAPH_DEMO.md) · [expanded](docs/63_NORNYX_GRAPH_DEMO_EXPANDED.md)
- [Schema targets and examples](docs/52_SCHEMA_TARGETS_AND_EXAMPLES.md)
- Roadmap toward a stable generalized contract language: see [`docs/03_ROADMAP_TO_v1_AND_BEYOND.md`](docs/03_ROADMAP_TO_v1_AND_BEYOND.md).

## Development

```bash
git clone https://github.com/mazinmarji/nornyx && cd nornyx
pip install -e ".[dev]"
python -m pytest -q
```

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Mazin Marji and Nornyx Contributors.
