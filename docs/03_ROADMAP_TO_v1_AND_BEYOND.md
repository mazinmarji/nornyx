# Nornyx Roadmap to v1.0 and Beyond

## Strategic version model

This roadmap treats completed v0.1 scaffold work as the safe local foundation
for a broader agentic contract language. Earlier semantic-checker, harness,
policy, eval, and connector ideas remain valid sub-workstreams, but they are
organized under this strategic version model:

- v0.1: Safe AI-coding / agentic repo control-plane scaffold.
- v0.1.1: Cleanup and contract hardening, including mapping block validation,
  stale metadata cleanup, roadmap alignment, and PMO wording cleanup.
- v0.2: Nornyx Graph + stronger generic contract model.
- v0.3: Domain profiles.
- v0.4: Adapters for Governed Delivery Control Plane, Agentic Development Harness, GovernanceAdapter, telecom ops,
  and business ops.
- v0.5-v0.9: Reserved maturity bands for graph validation, profile conformance,
  adapter conformance, bounded execution readiness, and release-candidate
  stabilization.
- v1.0: Stable generalized agentic contract language.

v1.0 does not mean a full autonomous runtime, a replacement for LangGraph,
CrewAI, LangChain, a general-purpose programming language, a production
execution engine, or unrestricted connector runtime. It means Nornyx is stable
enough to be used as a generalized agentic contract language across multiple
agentic AI domains.

## Phase 0 — Concept freeze

Deliverables:

- name and product category;
- v0.1 language model;
- safety boundaries;
- MVP CLI;
- examples and tutorial.

## Phase 1 — v0.1 executable spec and generator

Deliverables:

- parser;
- checker;
- generator;
- context pack builder;
- evidence scaffold;
- tests;
- generated AGENTS.md/skills/policies/harness/evals.

## Phase 2 — v0.2 Nornyx Graph and stronger generic contract model

Add:

- declared node/edge model;
- generic contract blocks;
- typed schemas for blocks;
- context provenance and taint rules;
- instruction/data channel separation;
- approval-gate checking;
- budget checking;
- supply-chain manifest checking;
- better diagnostics for LLM repair.

Current local v0.2 surface: static `graph:` and `contracts:` validation for
declared nodes, edges, graph references, approval references, and budget
references. Known core graph node refs are checked when supplied. The
compatibility schema remains the default `schemas/nornyx_v0_1.schema.json`
route, and explicit schema targets now exist at
`schemas/nornyx_v0_2.schema.json` and `schemas/nornyx_v1_0.schema.json`.
This does not add graph runtime execution.

## Phase 3 — v0.3 domain profiles

Add:

- ai_coding;
- agentic_repo_harness;
- telecom_ops;
- business_ops;
- ai_governance;
- finance_ops if needed.

Current local v0.3 compatibility surface: optional authoritative v1 profile
packs in `nornyx/profiles_data/`, exact v0.3 projection, generated starter
documents for each domain profile, closed validation rules, and compatibility
tests. Profiles layer on the v0.2 static
graph/contract model and do not enable adapters, live connectors, model calls,
automatic approvals, self-modification, production deployment, or
general-purpose programming language features.

## Phase 4 — v0.4 adapters and ecosystem bridges

Add:

- Governed Delivery Control Plane adapter;
- Agentic Development Harness adapter;
- GovernanceAdapter adapter;
- telecom ops adapter;
- business ops adapter;
- MCP/A2A connector contract conformance;
- policy/eval/evidence integration tests.

Current local v0.4 surface: `adapters:` is a static extension block;
`schemas/adapter_contract.schema.json` defines contract-only adapter
metadata; `examples/nornyx_v04_adapter_contracts.nyx` covers Mission Control
OS, Agentic Development Harness, GovernanceAdapter, telecom ops, and business ops bridges; and tests
verify policy/eval/evidence bindings plus MCP/A2A connector conformance. This
does not enable live connector execution.

## Phase 5 — v0.5-v0.9 maturity bands

Reserved bands:

- v0.5 graph validation and semantic consistency hardening;
- v0.6 domain-profile conformance;
- v0.7 adapter conformance and connector-contract hardening;
- v0.8 bounded execution readiness;
- v0.9 release-candidate stabilization.

Current local v0.5 surface: static graph relation consistency checks, duplicate
and self-edge diagnostics, expanded graph reference targets, and contract
auditability warnings for approval, budget, and evidence graph coverage. This
does not add graph execution.

Current local v0.6 surface: profile conformance metadata, cross-profile
compatibility matrix, migration guidance, and v1 readiness decisions for the
v0.3 domain profile packs. This does not make profiles mandatory core concepts.

Current local v0.7 surface: static adapter conformance reports,
connector-contract conformance schemas, MCP/A2A conformance checks, and adapter
evidence reports. This does not enable live connector execution.

Current local v0.8 surface: static bounded execution readiness reports with
sandbox, capability, approval, trace, evidence, policy, and adapter-conformance
checks. This does not enable execution.

Current local v0.9 surface: release-candidate stabilization reports and
evidence checks for the maturity bands through v0.8. This does not claim v1.0
readiness, publish, tag, push, or unlock GOAL-042/GOAL-100.

Bounded execution readiness remains local, explicit, approval-gated, traced,
and evidence-backed. These bands do not enable broad autonomy, live connector
execution by default, automatic approvals, self-modification, or production
deployment.

## Phase 6 — v1.0 stable generalized agentic contract language

v1.0 acceptance criteria:

- stable graph model;
- stable contract schema;
- stable checker;
- stable profiles;
- stable adapters;
- policy/eval/evidence semantics;
- approval gates;
- artifact generation;
- safe interoperability rules.

Current local v1.0 surface: a stable-language report, schema, CLI/script check,
and evidence gate that confirm GOAL-033 through GOAL-042 are complete locally
while GOAL-100 remains locked. This stabilizes Nornyx as a generalized agentic
contract language across graph, contracts, profiles, adapters, bounded
readiness, and release-candidate evidence. It does not publish, tag, push,
change package versions, deploy, enable live connectors, call models, grant
automatic approvals, or promote regulated/enterprise extensions.

## Future proposals outside the completed governance program

The following tracks are `future_proposal_outside_current_program`, not
unfinished governance roadmap obligations:

- dedicated parser and LSP;
- package/registry system;
- MCP/A2A connector runtime;
- governed self-healing;
- eval-driven improvement loops;
- extension marketplace;
- optional native execution for selected domains;
- broader programming constructs.

GOAL-013 keeps these tracks in research status through
`docs/RFCs/RFC-0003-full-language-evolution-research.md`; promotion requires a
new scoped goal, ADR review, local validation, evidence, and human approval.
