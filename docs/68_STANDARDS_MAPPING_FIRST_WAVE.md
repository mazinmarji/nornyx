# Standards Mapping First Wave

Tracked by [mazinmarji/nornyx#47](https://github.com/mazinmarji/nornyx/issues/47).
Planning surface: [`64_STANDARDS_MAPPING_AND_ENTERPRISE_ASSURANCE.md`](64_STANDARDS_MAPPING_AND_ENTERPRISE_ASSURANCE.md)
and [`backlog/nornyx-standards-mapping-roadmap.yaml`](backlog/nornyx-standards-mapping-roadmap.yaml).

First-wave frameworks, taken from the backlog rather than chosen here:
**NIST AI RMF**, **OWASP Top 10 for LLM Applications / OWASP GenAI**,
**ISO/IEC 42001**.

## Read This First: Mapping Is Not Certification

This document maps **observable Nornyx control capabilities** to control
*themes*. It is **not** a certification, **not** an attestation, **not** an
audit opinion, and **not** evidence that any external organisation has adopted
or validated Nornyx.

A standards mapping has the same failure mode as a migration guide: **it
overstates coverage unless the unmapped set is explicit.** So this document
ships both halves — [mapped capabilities](#mapped-control-capabilities) and
[explicit non-coverage](#explicit-non-coverage-rows). A mapping with no
non-coverage rows should be treated the same way as a migration with an empty
residual list: as a signal that something was over-claimed.

The governing sentence for this wave:

> **M5-A-4 closes the rule-name gap, not the flow-outcome gap.**

So `policies.deny` may be cited as a *declared, vocabulary-checked* control
surface. It must **not** be cited as runtime interception or as guaranteed
prevention.

### Theme-level, deliberately

This wave maps to **control themes**, not to numbered clauses. Clause-level
mapping needs the standards' own identifiers and versions, which are not
present in this repository, and the backlog forbids reproducing standard text.
Inventing clause identifiers would be exactly the kind of unfalsifiable claim
this document exists to avoid.

That is a knowing divergence from one backlog acceptance criterion (*"every
mapping has a framework version and source identifier"*). It is recorded as
[NC-12](#explicit-non-coverage-rows) rather than quietly skipped.

## Evidence Baseline

Everything below is **first-party evidence**. It is produced by this
repository's own CI. **It does not prove external adoption.**

| Artifact | What it establishes |
| --- | --- |
| `adapter-conformance` CI job | The runtime conformance kit runs the declared wrapped surfaces at pinned framework versions |
| `pip-only-example` CI job | The published wheel is obtainable from PyPI with verified provenance; bundled resources resolve outside any checkout |
| `external-adoption-pilot` CI job | Governed vs ungoverned behaviour on one action, from installed packages, outside any checkout |
| M5-A-1 `examples/external_adoption_pilot/` | Ungoverned executes; authorized executes; unauthorized executes zero times across framework retries |
| M5-A-2a `docs/66_…` + 3 issue templates | A reporting path exists for an external result |
| M5-A-2b `docs/67_…` | Migration is separation, not replacement; two enforcement surfaces named |
| M5-A-3 `examples/agents_migration_example/` | A validated contract *and* a structurally tested residual list |
| M5-A-4 `UNKNOWN_POLICY_RULE` | Unknown deny-rule names warn by default and fail under `--strict` |

## Control Surface Labels

Every mapped row is labelled by surface. These are **not** interchangeable, and
flattening them into a generic "control" label is what turns a mapping into
marketing.

| Label | Meaning |
| --- | --- |
| `authorization-spi` | `nornyx.agentic.Authorizer` — runtime decisions |
| `harness-policy` | `policies.deny/require` over declared flow steps |
| `evidence` | `evidence.required` declarations and checks |
| `approval` | `approvals.required_for` boundaries |
| `eval-threshold` | `evals.metrics` with threshold expressions |
| `lock-drift-conformance` | Locks, digests, drift and conformance checks |
| `docs-guidance` | Context and residual guidance |
| `example-only` | A demonstrated scenario |

## Claim Boundaries by Surface

| Surface | What may be claimed |
| --- | --- |
| `authorization-spi` | Runtime authorization decision; capability allowed/denied; evidence-bound where demonstrated |
| `harness-policy` | Declared-flow, vocabulary-checked policy control — **not** runtime interception |
| `evidence` | Required evidence declaration/check — **not** proof the external event happened unless the evidence is bound |
| `approval` | Approval boundary declaration/check — **not** proof of human approval unless paired with approval evidence |
| `eval-threshold` | Metric/threshold check over observed results — **not** general behavioural assurance |
| `lock-drift-conformance` | Deterministic artifact/integration consistency checks where implemented |
| `docs-guidance` | Context or residual guidance — **not** enforceable control |
| `example-only` | Demonstrated scenario — **not** a generalised platform guarantee |

## Mapped Control Capabilities

Claim types: `implemented`, `checked`, `evidence-bound`, `declared`,
`example-only`, `documentation-only`. The unqualified word "covered" is
deliberately not used.

| mapping_id | Control theme | Framework theme reference | Nornyx capability | Surface | Claim type |
| --- | --- | --- | --- | --- | --- |
| MAP-01 | Identity and role declaration | NIST AI RMF (govern/map); ISO/IEC 42001 (roles and responsibilities) | `agents`, `identities` with declared capability holdings | `authorization-spi` | `declared` |
| MAP-02 | Capability authorization | OWASP GenAI (excessive agency); NIST AI RMF (manage) | `Authorizer.evaluate` returning allow/deny per request | `authorization-spi` | `implemented` |
| MAP-03 | Least privilege / deny unless declared | OWASP GenAI (excessive agency); ISO/IEC 42001 (operational controls) | `deny_unless_declared` default; prohibition by omission | `authorization-spi` | `implemented` |
| MAP-04 | Approval boundaries | ISO/IEC 42001 (management responsibility); NIST AI RMF (govern) | `approvals.required_for` | `approval` | `declared` |
| MAP-05 | Evidence requirements | NIST AI RMF (measure/manage); ISO/IEC 42001 (documented information) | `evidence.required` | `evidence` | `checked` |
| MAP-06 | Evaluation thresholds | NIST AI RMF (measure) | `evals.metrics` with threshold expressions | `eval-threshold` | `checked` |
| MAP-07 | Policy-rule vocabulary integrity | ISO/IEC 42001 (control effectiveness) | `UNKNOWN_POLICY_RULE` diagnostic; `nornyx check --strict` | `harness-policy` | `implemented` |
| MAP-08 | Declared-flow policy constraints | OWASP GenAI (insecure plugin/tool design) | `policies.deny/require` over declared harness steps | `harness-policy` | `declared` |
| MAP-09 | Artifact integrity and drift | NIST AI RMF (manage); ISO/IEC 42001 (change control) | Contract digests, agentic-network lock, drift checks | `lock-drift-conformance` | `checked` |
| MAP-10 | Adapter runtime conformance | NIST AI RMF (measure); OWASP GenAI (supply chain) | `nornyx.agentic_runtime_conformance.v1` report at pinned versions | `lock-drift-conformance` | `evidence-bound` |
| MAP-11 | Distribution provenance | OWASP GenAI (supply chain) | Pip-only example: index-bound install, wheel-only, SHA-256 from pip's report | `lock-drift-conformance` | `evidence-bound` |
| MAP-12 | Governed vs ungoverned demonstration | OWASP GenAI (excessive agency); NIST AI RMF (measure) | External adoption pilot A/B/C | `example-only` | `example-only` |
| MAP-13 | External feedback path | NIST AI RMF (govern — external input) | Three issue templates; adoption record schema | `docs-guidance` | `documentation-only` |
| MAP-14 | Non-coverage discipline | ISO/IEC 42001 (documented limitations) | Tested residual list in the migration example | `docs-guidance` | `checked` |

### Evidence and claim boundaries

| mapping_id | Evidence artifact | Verification | Claim boundary and caveat |
| --- | --- | --- | --- |
| MAP-01 | `examples/agents_migration_example/agents_migration_example.nyx` | `nornyx check … --strict` | Declaration only. Identities are contract statements, **not** authenticated principals |
| MAP-02 | `examples/external_adoption_pilot/` adoption record | `external-adoption-pilot` CI job | Decides declared wrapped surfaces. ADR-0040 Tier 2, cooperative |
| MAP-03 | `nornyx/policy_runtime.py` capability lookup | `tests/test_policy_runtime.py` | Applies to declared capability paths; a path that never calls the wrapper is ungoverned |
| MAP-04 | `approvals.required_for` in the migration example | `nornyx check --strict` | Declares the boundary. **Not** proof a human approved anything unless paired with approval evidence |
| MAP-05 | `evidence.required` blocks | `nornyx check`; `tests/test_agents_migration_example.py` | Checks that required evidence is declared/present. **Not** proof the external event occurred unless bound |
| MAP-06 | `nornyx/eval_runtime.py` metric parsing | `tests/test_eval_runtime.py` | Threshold comparison over observed metrics. **Not** general behavioural assurance |
| MAP-07 | `nornyx/checker.py` `UNKNOWN_POLICY_RULE` | `tests/test_unknown_policy_rule_diagnostic.py` | Rule-**name** vocabulary only. Says nothing about whether a known name matches a given flow |
| MAP-08 | `policies` blocks; `_matches_deny_rule` | `tests/test_policy_runtime.py` | Static check over declared step text. **Not** runtime interception, **not** DLP, **not** deployment control |
| MAP-09 | Lock/digest artifacts; migration fixtures | `tests/test_governance_compatibility_corpus.py` | Consistency of declared artifacts. Not a statement about live systems |
| MAP-10 | `runtime-conformance-report.json` | `adapter-conformance` CI job | Declared wrapped surfaces at exact pinned versions. No Tier 3 claim |
| MAP-11 | `pip-only-audit.json` | `pip-only-example` CI job | Provenance of the published artifact. Hashes are per-build, not reproducible across builds |
| MAP-12 | Adoption record `governance_delta` | `external-adoption-pilot` CI job | One action, one contract, one framework. **Not** whole-application coverage |
| MAP-13 | `.github/ISSUE_TEMPLATE/external-adoption-*.yml` | Templates present on `main` | A path to receive evidence. **No** external report has been received |
| MAP-14 | `residual_guidance.yaml` | `tests/test_agents_migration_example.py` | Structural check that limitations are recorded, not that they are complete |

## Explicit Non-Coverage Rows

Part of the deliverable, not an appendix.

| noncoverage_id | Theme | What is **not** claimed | Why not | Closest current artifact | Future option |
| --- | --- | --- | --- | --- | --- |
| NC-01 | External adoption | That any external user has run, reported, or adopted Nornyx | No external signal recorded; first-party CI cannot supply one | M5-A-2a reporting templates | An external report moves M5's gate |
| NC-02 | Certification / attestation | Any certification, attestation, audit opinion, or statement of conformity | Out of scope by backlog non-goals; requires an accredited body | This mapping | Independent assessment, not a repo change |
| NC-03 | Harness policy interception | That `policies.deny` intercepts real operations | It is a static check over declared step text | MAP-08 | Route the decision through the authorization SPI |
| NC-04 | Guaranteed prevention | That unsafe behaviour is prevented in general | Tier 2 cooperative; bypass outside wrapped paths is possible and demonstrated | MAP-02, MAP-12 | Tier 3 work, not planned here |
| NC-05 | Free-text policy enforcement | That an arbitrary policy sentence becomes an enforced rule | Only a small rule-name vocabulary is evaluated | MAP-07 | Widening the vocabulary is separate runtime work |
| NC-06 | Rule firing against a flow | That an in-vocabulary rule matches any particular flow | Requires flow analysis nothing here performs | MAP-07 | Flow-aware analysis, unscoped |
| NC-07 | Automatic approval | That approvals can be granted automatically | Explicit non-goal across the repository | MAP-04 | None — deliberate |
| NC-08 | Live connector / runtime governance | Governance of live connectors or external runtimes | Not implemented; conformance runs offline | MAP-10 | Separate implementation with its own review |
| NC-09 | Legal / organisational compliance | That an organisation is compliant with any law or framework | Legal determination, not a software property | This mapping | Legal review, outside this repository |
| NC-10 | Replacing source governance docs | That `.nyx` replaces `AGENTS.md`, policy docs, or eval configs | Migration is separation, not replacement | MAP-14 | None — deliberate |
| NC-11 | Non-promptfoo eval formats | Support for OpenAI Evals, DeepEval, ragas, or others | No repo artifact demonstrates one | MAP-06 | Add an example first, then map |
| NC-12 | Clause-level mapping | Mapping to numbered clauses, versions, or source identifiers | Standards text is not in this repo and must not be reproduced | This theme-level table | A future wave with licensed access and review |

## How to Read the Mapping

1. **Read the surface label first.** `authorization-spi` and `harness-policy`
   are not comparable strengths.
2. **Read the claim type second.** `declared` means the contract states it;
   `checked` means something validates it; `evidence-bound` means an artifact
   ties it to an observed run; `example-only` means one demonstrated scenario.
3. **Read the claim boundary third.** It is where the row stops being true.
4. **Then read the non-coverage table.** A reader who skips it has read half
   the document.

A row does not become stronger by being cited elsewhere.

## What Requires External Evidence

- Any statement that Nornyx has been adopted, validated, or found useful by
  someone outside the maintainer flow (NC-01).
- Any statement about behaviour on contracts, frameworks, or applications not
  represented in this repository (NC-12, MAP-12).

## What Requires Future Runtime Work

- Widening the evaluated policy-rule vocabulary (NC-05).
- Flow-aware analysis of whether a rule matches a declared flow (NC-06).
- Live connector or external runtime governance (NC-08).
- Any Tier 3 assurance claim (NC-04).

## What Requires Future Standards Review

- Clause-level and version-level mapping with source identifiers (NC-12).
- Second-wave frameworks from the backlog: ISO/IEC 23894, NIST SSDF, SLSA,
  OpenTelemetry GenAI trace conformance.
- Future wave: EU AI Act (subject to legal review), SOC 2 evidence-support
  mapping, COBIT, ITIL, TOGAF.

## M5 Gate Status

- M5-A-1 through M5-A-4: complete.
- **M5 promotion gate: not met.** No external adoption signal has been
  recorded, and nothing in this document changes that. This mapping is
  first-party evidence about capabilities, not evidence of adoption.

## Non-Goals

No certification. No attestation. No audit opinion. No legal advice. No claim
that Nornyx proves runtime truth. No reproduction of standard text. No live
network retrieval. No automatic approval. No external adoption claim. No
runtime, schema, public API, `policy_runtime`, or adapter change. No version
bump, tag, GitHub Release, or PyPI publish.
