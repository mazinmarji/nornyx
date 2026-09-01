# Nornyx

[![PyPI](https://img.shields.io/pypi/v/nornyx.svg)](https://pypi.org/project/nornyx/)
[![Python](https://img.shields.io/pypi/pyversions/nornyx.svg)](https://pypi.org/project/nornyx/)
[![CI](https://github.com/mazinmarji/nornyx/actions/workflows/ci.yml/badge.svg)](https://github.com/mazinmarji/nornyx/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Nornyx is a vendor-neutral governance contract language for AI software
delivery that defines deterministic controls and authorization semantics,
binds decisions and supplied evidence to governed revisions, and preserves
that governance meaning across supported integrations.**

```bash
pip install nornyx
```

## The problem it solves

Your AI-delivery governance lives scattered across `AGENTS.md`, a skills
folder, prompt/context packs, a harness script, an eval config, policy docs,
evidence templates, and approval checklists — and it **drifts** out of sync,
with no way to show afterward which rules applied, what an agent was allowed
to do, who approved it, or whether the supplied evidence matches the revision
that was approved.

Nornyx makes that governance one **checked, revision-bound source of truth**.
The `.nyx` contract is the governed entry point: where it selects policy
references, profiles, or modules, Nornyx resolves those governed inputs
deterministically, and authorization and evidence validation also use the
applicable lock/revision and explicit evaluation inputs. One mechanism
beneath that thesis is deterministic artifact generation — Nornyx can
**generate** and **validate** the control artifacts your tools already read:

```text
one .nyx contract  ──►  AGENTS.md · skills/ · harness.yaml · policy.yaml
                        evals.yaml · context.yaml · evidence_contract.md
```

Nornyx does **not** replace Codex, Claude Code, Cursor, Copilot, CI/CD, or
human review. It defines and checks the governance contract those execution
surfaces follow and generates the control artifacts they read — execution and
enforcement stay with them.

## What Nornyx provides

- **One governed source of truth** for agent/skill/harness/policy/eval/evidence
  artifacts — no more drift.
- **Deterministic authorization semantics** — a framework-neutral authorization
  SPI producing deterministic decisions with normalized reason codes from
  explicit supported inputs; approval assertions identified as non-human are
  rejected, and claimant identity/authentication remains external to Nornyx.
- **Revision and lock binding** — content-addressed locks tie artifacts,
  approvals, and evidence to the exact governed revision.
- **Supplied-evidence validation** — runtime-event evidence validated against
  the declared semantics and the locked revision.
- **Context trust model** — mark which context is `trusted` vs `untrusted` so
  untrusted input can't define policy, and deny `secrets_to_llm` at the
  contract level.
- **Generators + a checker** — turn `.nyx` into the files your tools read, and
  verify references and required fields.
- **Drift and workspace gates** — catch when regenerated output diverges from
  a committed baseline, in one repo or across many.
- **Governed packages** — inventory, hash, risk-surface, and evidence-bind
  package inputs without executing them.
- **YAML-compatible syntax** — no new parser to learn.

## Where Nornyx sits

```text
reviewed intent — the .nyx contract (governed entry point)
        |
        v
Nornyx: deterministic resolution and checks, derived control artifacts,
        locks / governed revisions
        |
        +--> (optional) Nornyx authorization SPI ──► decision
        |
        +--> (mapped) external PDP / policy engine ──► decision
        |
        v
external PEPs / runtimes / platform controls — enforcement / execution
        |
        v
supplied evidence / runtime records
        |
        +----> Nornyx validation against the governed revision
```

Not every use case involves an authorization decision. Where one does, the
Nornyx Authorizer is one supported decision path, and in mapped integrations
an external policy engine owns decision production. External PEPs, runtimes,
and platform controls own enforcement and execution; Nornyx defines the
governance meaning they must preserve and validates the evidence they supply.
It does not independently attest that supplied runtime events actually
occurred.

## Install

```bash
pip install nornyx          # from PyPI
# or pin from source:
pip install "nornyx @ git+https://github.com/mazinmarji/nornyx@v1.11.0"
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

The same contract governs the legacy offline reference adapters and the
separately distributed `nornyx-agentic-adapters` package. Runtime-events 1.1
can explicitly distinguish logical operations, repeated occurrences, retries,
parallel branches, and resumed attempts while retaining exact 1.0 evidence and
lock compatibility. The supported LangGraph 1.2.2 adapter uses this model for
synchronous StateGraph nodes; CrewAI synchronous tool coverage remains
available in the same adapter package. Approval assertions identified as
non-human are rejected; claimant identity and authentication remain external
to Nornyx. Sensitive categories are never shareable. Nornyx validates
declarations and supplied local evidence — it is not an agent runtime, MCP
runtime, or A2A runtime, and it does not attest runtime truth. Start with
[docs/agentic-network/00_OVERVIEW.md](docs/agentic-network/00_OVERVIEW.md).

## Authorization and interoperability

Nornyx ships a framework-neutral authorization SPI that produces
deterministic decisions with normalized reason codes from explicit, supported
evaluation inputs. Approval assertions identified as non-human are rejected;
claimant identity and authentication remain external to Nornyx. The complete
decision semantics live in the current implementation, its tests, and
[ADR-0039](https://github.com/mazinmarji/nornyx/blob/main/docs/decisions/ADR-0039-agentic-integration-sdk.md);
the [SPI 1.2 note](https://github.com/mazinmarji/nornyx/blob/main/docs/agentic-network/12_AUTHORIZATION_SPI.md)
documents the additive Authorizer construction-state capability.

Nornyx is designed to complement rather than replace external policy engines
and platform governance. The currently implemented external authorization
mapping is the scoped [OpenID AuthZEN capability-evaluation
surface](https://github.com/mazinmarji/nornyx/blob/main/docs/69_AUTHZEN_INTEROPERABILITY.md).
It is limited and explicitly scoped: it is not complete AuthZEN coverage, and
it does not make Nornyx a hosted policy decision point. Mappings and
projections stay subordinate to the `.nyx` source contract, a successful
mapping does not imply that an external enforcement point enforced the
result, and additional policy-engine and hyperscaler mappings remain
adoption-gated or roadmap work.

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

## Capability maturity and claim boundaries

- **Shipped:** `.nyx` parsing and semantic checking, deterministic derived
  artifact generation, context packs and evidence scaffolds, drift and
  workspace checks, schema inspection, declarative governance composition,
  the governance CLI/API, governed-package controls, agentic authorization
  SPI 1.2, agentic-network locks, runtime-event validation 1.1.
- **Optional profile:** `agentic_network` and the supported profile/module
  surfaces.
- **Limited / experimental:** the scoped AuthZEN capability-evaluation
  interoperability surface, the narrow published runtime-adapter coverage,
  cooperative higher-assurance claims, theme-level standards mappings, and
  the first-party external-adoption pilot.
- **Roadmap:** the
  [roadmap priorities](https://github.com/mazinmarji/nornyx/blob/main/docs/65_ROADMAP_REWEIGHTING_EVIDENCE_ADOPTION.md)
  include both durable shipped capabilities and future/adoption-gated work;
  roadmap inclusion alone does not indicate current availability.

The claim boundary: Nornyx validates governed contracts and supplied evidence
against declared semantics and governed revisions. It does not independently
attest unverifiable runtime truth, does not authenticate identities or
approvers, and does not perform live enforcement — external systems remain
responsible for actual execution and enforcement.

## What Nornyx is not

- Not an agent runtime or workflow engine — it does not execute agents,
  workflows, or deployments.
- Not a hosted policy decision point, an identity provider, a traffic proxy,
  or an execution sandbox.
- Not a replacement for Cedar, OPA/Rego, or hyperscaler IAM and governance
  services — Nornyx is designed to complement them and stay neutral across
  them; the currently implemented external authorization mapping is the
  scoped AuthZEN capability-evaluation surface, and additional policy-engine
  and hyperscaler mappings remain adoption-gated or roadmap work.
- Not complete AuthZEN support, not a standards-compliance claim, and not
  Tier-3 assurance.

Full non-goals and boundary rationale:
[docs/48_NORNYX_POSITIONING.md](https://github.com/mazinmarji/nornyx/blob/main/docs/48_NORNYX_POSITIONING.md).

## Scope and safety

Nornyx is an **executable specification layer**, not a runtime. It does **not** implement autonomous system modification, production deployment, destructive tool use, credential handling, or arbitrary command execution. The name *Nornyx* is a provisional working brand (no formal legal clearance claimed).

## Documentation map and learning paths

**[docs/README.md](https://github.com/mazinmarji/nornyx/blob/main/docs/README.md)**
is the documentation map: it identifies which documents are authoritative,
which are supporting, and which are historical records. Key paths:

- [Executive overview](https://github.com/mazinmarji/nornyx/blob/main/docs/00_EXECUTIVE_OVERVIEW.md) · [Positioning](https://github.com/mazinmarji/nornyx/blob/main/docs/48_NORNYX_POSITIONING.md)
- [5-minute adoption](https://github.com/mazinmarji/nornyx/blob/main/docs/49_NORNYX_5_MINUTE_ADOPTION.md) · [Use it in your repo](https://github.com/mazinmarji/nornyx/blob/main/docs/USE_IN_YOUR_REPO.md)
- [Agentic-network governance overview](https://github.com/mazinmarji/nornyx/blob/main/docs/agentic-network/00_OVERVIEW.md) · [end-to-end tutorial](https://github.com/mazinmarji/nornyx/blob/main/docs/agentic-network/01_TUTORIAL.md)
- [CrewAI governance A/B benchmark](https://github.com/mazinmarji/nornyx/blob/main/examples/crewai_governance_benchmark/README.md) — one workflow run with and without governance, with a side-effect ledger proving what was prevented ([reviewer quickstart](https://github.com/mazinmarji/nornyx/blob/main/examples/crewai_governance_benchmark/REVIEWER_QUICKSTART.md))
- [Governed Package Profile](https://github.com/mazinmarji/nornyx/blob/main/docs/governed-package-profile.md)
- [Public boundary policy](https://github.com/mazinmarji/nornyx/blob/main/docs/public-boundary-policy.md)
- [Nornyx Graph demo](https://github.com/mazinmarji/nornyx/blob/main/docs/50_NORNYX_GRAPH_DEMO.md) · [expanded](https://github.com/mazinmarji/nornyx/blob/main/docs/63_NORNYX_GRAPH_DEMO_EXPANDED.md)
- [Schema targets and examples](https://github.com/mazinmarji/nornyx/blob/main/docs/52_SCHEMA_TARGETS_AND_EXAMPLES.md)
- Roadmap: [current priorities](https://github.com/mazinmarji/nornyx/blob/main/docs/65_ROADMAP_REWEIGHTING_EVIDENCE_ADOPTION.md) · [strategic roadmap](https://github.com/mazinmarji/nornyx/blob/main/docs/03_ROADMAP_TO_v1_AND_BEYOND.md)

## Textbook

The development-edition Nornyx textbook manuscript lives in
[book/manuscript](https://github.com/mazinmarji/nornyx/tree/main/book/manuscript):
public educational material teaching the language and its governance model.
Its factual assertions may be edition- or SHA-pinned rather than evergreen —
where the textbook and the current authoritative documentation disagree, the
documentation wins.

## Development

```bash
git clone https://github.com/mazinmarji/nornyx && cd nornyx
pip install -e ".[dev]"
python -m pytest -q
```

Contribution rules: [CONTRIBUTING.md](https://github.com/mazinmarji/nornyx/blob/main/CONTRIBUTING.md).

## License and project identity

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Mazin Marji and Nornyx Contributors.
Use it, modify it, redistribute it, fork it, sell it. That is not changing.

Licensing and project identity are separate questions, and Nornyx answers them
separately:

- **[TRADEMARKS.md](TRADEMARKS.md)** — the MIT grant covers the code; it does
  not by itself grant the right to present a derivative as an official Nornyx
  release. Describing your work as based on, compatible with, or derived from
  Nornyx is welcome. No trademark registration is claimed.
- **[docs/NYX_FORMAT_AND_CONFORMANCE.md](docs/NYX_FORMAT_AND_CONFORMANCE.md)** —
  `.nyx` is Nornyx's canonical extension, but conformance is defined
  semantically, not by filename. Independent implementations of Nornyx
  semantics are a goal of the project. This document defines what each
  conformance claim requires and how to check it.
- **[docs/PROVENANCE_AND_RELEASE_VERIFICATION.md](docs/PROVENANCE_AND_RELEASE_VERIFICATION.md)**
  — how to verify that an artifact actually came from this project, and why
  official origin and conformance are independent properties. Verification
  needs no Nornyx-operated service: it reads the package index and forge, then
  checks locally.
