# Nornyx Executive Overview

Nornyx is a vendor-neutral governance contract language for AI software
delivery that defines deterministic controls and authorization semantics,
binds decisions and supplied evidence to governed revisions, and preserves
that governance meaning across supported integrations.

## The problem

AI-assisted and agentic software delivery scatters its governance across
`AGENTS.md` files, prompt and context packs, policy documents, eval configs,
approval checklists, and evidence templates. Those artifacts drift apart, are
not checked against each other, and are not bound to any revision — so when it
matters, nobody can show which rules applied, what an agent was allowed to do,
who approved it, or whether the evidence supplied afterward matches the
governance that was actually in force.

## What Nornyx does

Nornyx gives that governance a single reviewed entry point: the `.nyx`
contract. Where the contract selects policy references, profiles, or modules,
Nornyx resolves those governed inputs deterministically; authorization and
evidence validation also use the applicable lock/revision and explicit
evaluation inputs. On that basis Nornyx provides:

- **Deterministic contract checking** — parse and semantically check
  YAML-compatible `.nyx` contracts covering intent, context, agents, skills,
  policies, evals, approvals, evidence, budgets, traces, and graph
  relationships.
- **Deterministic derived artifacts** — generate the control artifacts
  external tools consume (`AGENTS.md`, policy/eval/harness/context files,
  evidence scaffolds) from the contract, with drift and workspace checks that
  fail loudly when generated output diverges from the contract.
- **Authorization semantics** — a framework-neutral authorization SPI
  producing deterministic decisions with normalized reason codes from
  explicit supported inputs; approval assertions identified as non-human are
  rejected, and claimant identity/authentication remains external.
- **Revision and lock binding** — content-addressed locks bind artifacts,
  approvals, and evidence to the exact governed revision.
- **Supplied-evidence validation** — validate supplied runtime-event evidence
  and external tool reports against the declared semantics and locked
  revision.
- **Governed packages** — treat folders, repos, plugins, agent kits, and MCP
  bundles as inert inputs: inventory, hash, risk-surface, and evidence-bind
  them without executing them.
- **Optional agentic-network governance** — the `agentic_network` profile
  declares a bounded agent network (identities, capabilities, trust zones,
  gates, delegations, handoffs) and validates supplied runtime events against
  that network's lock.

## Responsibility boundary

Nornyx validates governed contracts and supplied evidence against declared
semantics and governed revisions. It does not execute agents or workflows,
deploy software, perform live enforcement, authenticate identities or
approvers, or prove that supplied runtime events actually occurred. External
adapters, policy engines, runtimes, and platform controls execute and enforce;
Nornyx defines the governance meaning they must preserve and validates the
evidence they supply against it.

## Capability maturity

- **Shipped:** `.nyx` parsing and semantic checking, deterministic derived
  artifact generation, context packs and evidence scaffolds, drift and
  workspace checks, schema inspection, declarative governance composition,
  the governance CLI/API, governed-package controls, agentic authorization
  SPI 1.2, agentic-network locks, and runtime-event validation 1.1.
- **Optional profile:** `agentic_network` and the supported profile/module
  surfaces.
- **Limited / experimental:** the scoped OpenID AuthZEN capability-evaluation
  interoperability surface, the narrow published runtime-adapter coverage,
  cooperative higher-assurance claims, theme-level standards mappings, and
  the first-party external-adoption pilot.
- **Roadmap:** the roadmap (linked below) includes both durable shipped
  capabilities and future/adoption-gated work; roadmap inclusion alone does
  not indicate current availability.

## Where to go next

- [Documentation map](README.md) — what is authoritative, supporting, and
  historical.
- [Architecture](02_ARCHITECTURE.md) — the current architecture.
- [Positioning](48_NORNYX_POSITIONING.md) — detailed positioning and
  non-goals.
- [Roadmap priorities](65_ROADMAP_REWEIGHTING_EVIDENCE_ADOPTION.md) — current
  P0–P3 priorities and promotion gates.
