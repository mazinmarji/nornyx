---
appendix: J
title: "Appendix J — Repository Traceability Matrix"
---

# Appendix J — Repository Traceability Matrix

Every material claim this book makes about Nornyx behavior is listed here with the repository
evidence that supports it and a status. Paths are relative to the repository root at the audited
revision `70d2b40ad79293209b43bdaa375f20badf63bdd7`; line numbers were accurate at that revision
and should be treated as locators rather than permanent addresses. Status values are
**implemented** (present in code, with test coverage unless noted), **guidance** (documented target
or stated limitation, not a code mechanism), **roadmap** (planned, not present), and **non-goal**
(explicitly declined). The final section lists claims that could not be verified and are therefore
not asserted anywhere in the book.

## J.1 Versions, packaging, and boundaries

| Claim | Evidence | Status | Chapter |
|---|---|---|---|
| Distribution 1.11.0; language/schema 1.0; axes independent | `pyproject.toml:7`; `manifest.json:4-5`; `docs/VERSIONING.md:6-22` | implemented | 16 |
| Contracts declare `nornyx: "0.1"`/`"0.2"` even under the 1.0 schema | `schemas/nornyx_v1_0.schema.json:17,22-29`; `nornyx/checker.py:599-609` | implemented | 16, 17 |
| Supported Python 3.10–3.13; dependencies PyYAML, jsonschema, referencing | `pyproject.toml:10,27`; `README.md:31` | implemented | 16 |
| MIT licence, 2026, Mazin Marji and Nornyx Contributors | `LICENSE` | implemented | 16 |
| Adapter distribution `nornyx-agentic-adapters` 0.2.0, Alpha, `nornyx>=1.10,<2` | `adapters/nornyx-agentic-adapters/pyproject.toml:6-7,15,24` | implemented | 22, 25 |
| Public Python API is `nornyx.governance.__all__` plus six top-level names; deprecation policy of two minor releases and six months | `docs/GOVERNANCE_CLI_AND_API.md:66-92`; `nornyx/__init__.py` | implemented (policy) | 19, App. B |
| Not a runtime, orchestrator, identity provider, secrets manager, deployment engine, or live protocol runtime | `docs/48_NORNYX_POSITIONING.md:17-25`; `README.md:239-241`; `docs/agentic-network/00_OVERVIEW.md` | non-goal | 16, 26, 38 |
| No arbitrary shell execution, credential storage, production deployment, or self-modification | `manifest.json:32-38`; `README.md:239-241` | non-goal | 16, 38 |
| Modules named "runtime" build plans and reports; they do not execute agents, tools, or models | `docs/02_ARCHITECTURE.md:16-19`; module docstrings | non-goal (documented) | 16, 21 |
| First publication to the package index occurred at 1.6.2; 1.6.0 and 1.6.1 were never published | `CHANGELOG.md:274-276,283-285` | implemented (history) | 16 |
| Release 1.6.0 remediated an independent no-go audit (AUD-001 through AUD-022) | `CHANGELOG.md:288-348` | implemented (history) | 16 |
| Name is a provisional working brand with no legal clearance claimed | `README.md:241` | guidance | 16 |

## J.2 Language, checker, and generated artifacts

| Claim | Evidence | Status | Chapter |
|---|---|---|---|
| Fifteen core top-level blocks plus eleven deferred extension blocks | `nornyx/checker.py:32-62`; `schemas/nornyx_v1_0.schema.json:21-149` | implemented | 17, App. A |
| Top-level schemas closed (`additionalProperties: false`); block interiors open | `schemas/nornyx_v1_0.schema.json:20`; `nornyx_v0_1.schema.json:10` | implemented | 17 |
| Unknown top-level blocks produce warnings, not errors | `nornyx/checker.py:828-839` | implemented | 17 |
| Diagnostic codes are upper-snake-case strings; there is no numeric code scheme | `nornyx/errors.py:4-22`; `nornyx/checker.py` | implemented | 21, App. C |
| Parser rejects duplicate keys; `on`/`off`/`yes`/`no` remain strings | `nornyx/parser.py:24-61`; `tests/test_parser_on_key_regression.py` | implemented | 17, 34 |
| Lexical rejection of remote, UNC, and device paths before filesystem access | `nornyx/path_security.py:15-52`; `nornyx/parser.py:70-71` | implemented | 34 |
| Rule verbs are `deny` and `require`; unrecognized rules default into `require` | `nornyx/policy_runtime.py:83-108` | implemented | 7, 17, 28 |
| Deny matching keys on production, secret, destructive, connector, and self-modification tokens | `nornyx/policy_runtime.py:185-203` | implemented | 17, 28 |
| Capabilities deny by default; approval required by default | `nornyx/policy_runtime.py:111-137,278-357`; `docs/05_SECURITY_MODEL.md:29-43` | implemented | 17 |
| Policy `ref` resolves `<path>#<PolicyName>` offline and fails closed, compiling to inline rules | `nornyx/parser.py:111-177`; `tests/test_policy_ref.py` | implemented | 8, 32 |
| Generator emits `AGENTS.md`, `skills/`, six YAML artifacts, task packets, evidence contract, and a hashed generation manifest | `nornyx/generator.py:76-182` | implemented | 21 |
| Generation determinism: line-feed newlines, sorted paths and hashes, no timestamps | `nornyx/generator.py:11-36`; `CHANGELOG.md:683-685` | implemented | 8, 21 |
| `nornyx drift` compares the full artifact set by digest | `nornyx/repo_drift.py:1-92`; `tests/test_repo_drift.py`; `CHANGELOG.md:613-618` | implemented | 21, 29 |
| Twenty-three typed graph relations with source and target kind checking | `nornyx/checker.py:144-168,425-450` | implemented | 17 |
| Context packs record per-file digests and taint channels | `nornyx/context_builder.py:9-174`; `tests/test_context_provenance.py` | implemented | 6, 21 |
| Context authority rank is advisory metadata, not an enforcement mechanism | `nornyx/context_builder.py:170` | implemented (stated limit) | 6, 21 |
| `--as-of` fails closed with `AS_OF_INVALID` and never falls back to the live clock | `nornyx/cli.py:133-161`; `CHANGELOG.md:95-102` | implemented | 18, App. C |
| Exit codes 0, 1, 2, with lock and parse failures returning 2 | `docs/GOVERNANCE_CLI_AND_API.md:42-53` | implemented | 21, App. B |

## J.3 Composition, profiles, and approvals

| Claim | Evidence | Status | Chapter |
|---|---|---|---|
| Composition is dependency-ordered, monotonic, and provenance-stamped per element | `nornyx/governance/composition.py:30-45,262-275` | implemented | 8, 18 |
| Thirteen built-in profiles and seven governance modules | `nornyx/profiles_data/catalog.json` | implemented | 18 |
| Profiles lock is timestamp-free with content digests; mismatch exits 2 | `schemas/profiles_lock_v1.schema.json`; `nornyx/cli.py:1136-1147` | implemented | 18 |
| Effective governance emitted as the closed `nornyx.effective_governance.v2` document | `schemas/effective_governance_v2.schema.json`; `docs/GOVERNANCE_CLI_AND_API.md:110-115` | implemented | 8, 18 |
| Workspace manifest declares canonical policies and members; `--write` syncs surgically without inventing policies | `nornyx/workspace.py:1-17,99-215,218-299`; `tests/test_workspace.py` | implemented | 32 |
| The workspace layer exists because both repositories' own gates produced a false green | `docs/CASE_STUDY_multi_repo_governance.md:28-45` | implemented (history) | 32 |
| Cross-repository policy references are a deliberate non-goal | `docs/CASE_STUDY_multi_repo_governance.md:58-61` | non-goal | 32 |
| Artificial intelligence systems, tools, models, and connectors cannot hold approval authority | `nornyx/governance/approvals.py:34-59,426-433,494-499`; `nornyx/agentic/authz.py:1042` | implemented | 9 |
| Refused non-human approvals remain valid evidence (grant-only scoping) | `CHANGELOG.md:138-149` | implemented | 9, 20 |
| Exception lifecycle with expiry, manual re-approval, and closure evidence fails closed | `schemas/governance_exception_v1.schema.json`; `CHANGELOG.md:309-321` | implemented | 9 |

## J.4 Agentic network, locks, and evidence

| Claim | Evidence | Status | Chapter |
|---|---|---|---|
| The `agentic_network` block schema is closed and requires trust zones, memberships, protocol targets, gates, and revocations | `schemas/agentic_network_v1.schema.json:8-17,63` | implemented | 31 |
| Subject revisions must be immutable (`git:` hex or `sha256:`) | `schemas/agentic_network_v1.schema.json:77-82`; `nornyx/agentic/authz.py:70` | implemented | 12, 18 |
| Trust zones require a non-empty never-share list; seven classifications | `schemas/agentic_network_v1.schema.json:102-133` | implemented | 6, 31 |
| Identities carry `authority: non_human` and `can_approve: false` as schema constants | `schemas/agent_identities_v1.schema.json:74-75` | implemented | 5, 9 |
| The non-human approval invariant is re-enforced in code | `nornyx/governance/agentic_network.py:1036-1042` | implemented | 9 |
| Sensitive categories are secrets, credentials, tokens, and private memory, from a single source | `nornyx/governance/agentic_network.py:12` | implemented | 6, 31 |
| Sensitive sharing is denied at engine, static-check, evidence, and adapter layers | `nornyx/agentic/authz.py:1152-1155`; `agentic_evidence.py:688`; `agentic_delegation.py:630,1128` | implemented | 31 |
| Protocol targets permit only `mcp` and `a2a`, with contract-only execution mode | `schemas/agentic_network_v1.schema.json:179-182` | implemented | 27 |
| Generation fails closed on forbidden fields and values (endpoints, credentials, commands, addresses) | `nornyx/agentic_artifacts.py:78-121,265-296` | implemented | 21, 27, 34 |
| Generation emits exactly ten artifacts and is byte-deterministic across runs | `nornyx/agentic_artifacts.py:40,66-76`; verified live | implemented (verified) | 21 |
| Lock format 1.0 binds contract digest, revision, packs, schemas, checks, evidence schema version, record digests, and artifact hashes | `schemas/agentic_network_lock_v1.schema.json:7-28`; `nornyx/agentic_artifacts.py:685-774` | implemented | 18 |
| Lock verification produces a family of `AN_LOCK_*` diagnostics | `nornyx/agentic_artifacts.py:916-1028` | implemented | 18, App. C |
| A lock binds bytes, not producers; a hostile local writer can regenerate a consistent lock | `docs/agentic-network/07_NETWORK_LOCK.md`; `schemas/agentic_network_lock_v1.schema.json:5` | guidance (stated limit) | 12, 18, 34 |
| Runtime events support three envelopes: 1.0, 1.1 legacy, and 1.1 explicit | `schemas/agentic_runtime_events_v1.schema.json:6-10,148-194` | implemented | 20 |
| The event type enumeration is closed at eighteen types | `schemas/agentic_runtime_events_v1.schema.json:101-110` | implemented | 20 |
| Every event binds network identifier, contract digest, lock digest, and subject revision | `nornyx/agentic_evidence.py:360,445-448` | implemented | 20 |
| Ordering checks cover contiguous sequences, timestamps, dependencies, and paired transitions | `nornyx/agentic_evidence.py:800-1014` | implemented | 12, 20 |
| Replay fingerprints exclude event identifier and sequence, and timestamp in explicit mode | `nornyx/agentic_evidence.py:391-419` | implemented | 12, 20 |
| Retry after success is rejected; attempts must be contiguous from one | `nornyx/agentic_evidence.py:935,1060` | implemented | 20 |
| Evidence artifact paths must remain under the events directory and match their digests | `nornyx/agentic_evidence.py:746-781` | implemented | 20, 34 |
| Validated evidence proves conformance of supplied records, not event truth | `nornyx/agentic_evidence.py:88-92`; `docs/agentic-network/06_RUNTIME_EVIDENCE.md` | implemented + guidance | 3, 11, 13, 20 |
| Resume validates the prior stream and produces cumulative, not differential, evidence | `nornyx/agentic_evidence.py` (recorder resume); `docs/agentic-network/06_RUNTIME_EVIDENCE.md` | implemented | 20, 24 |
| `evidence-validate` returns non-zero only under `--strict` | `nornyx/cli.py:883,1620-1631` | implemented | 20, 29 |

## J.5 Authorization interface and adapters

| Claim | Evidence | Status | Chapter |
|---|---|---|---|
| Interface history 1.0 (Nornyx 1.8.0) to 1.1 (1.10.0) to 1.2 (1.11.0); current constant is 1.2 | `nornyx/agentic/authz.py:66`; `CHANGELOG.md` | implemented | 19 |
| Decision outcomes are allow, deny, and approval-required | `nornyx/agentic/authz.py:399-402,1110-1118` | implemented | 7, 19 |
| `load_authorizer` validates, composes, and verifies the lock; direct construction provides no assurance | `nornyx/agentic/authz.py:405-410,774,1166-1210` | implemented | 19 |
| Authorizer state exposes detached frozen views whose mutation cannot affect decisions | `nornyx/agentic/authz.py:641-711` | implemented | 19 |
| Approval evaluation order: revision, binding, action scope, non-human refusal, role, evidence, expiry | `nornyx/agentic/authz.py:1012-1072` | implemented | 9, 19 |
| Framework pins are exact (`crewai==1.15.4`, `langgraph==1.2.2`) and enforced at import | `adapters/.../pyproject.toml:27-28`; `crewai_adapter.py:66-105`; `langgraph.py:45-69` | implemented | 22, 25 |
| Interface major version is asserted at adapter package import | `adapters/.../__init__.py:34`; `_compat.py:16-34` | implemented | 22 |
| CrewAI coverage is the synchronous `BaseTool._run` path; agent, task, delegation, and handoff surfaces are declared unsupported | `crewai_adapter.py:118-183` | implemented | 23, 25 |
| The asynchronous tool path fails closed and records nothing | `crewai_adapter.py:14-18,131-143` | implemented | 23 |
| The protected sequence evaluates once, records, executes only on allow, and records the outcome | `enforcement.py:28-65`; `tests/test_enforcement.py:61-196` | implemented | 22 |
| LangGraph coverage is synchronous state-graph nodes with occurrence and attempt identity from public runtime information | `langgraph.py:144-275`; `tests/test_langgraph_adapter.py:171-283` | implemented | 24 |
| Graph interrupts propagate as incomplete attempts rather than runtime failures | `langgraph.py:246-253` | implemented | 24 |
| Graph topology is declared unwrapped because it is caller-owned | `langgraph.py:94-124` | implemented | 24, 25 |
| Bypassing an adapter bypasses enforcement; there is a test demonstrating it | `tests/test_crewai_adapter.py:506`; adapter `README.md:133-150` | implemented | 14, 23 |
| Supported adapters perform no file input or output and never re-read contracts | verified by absence; `crewai_adapter.py:265-275` | implemented | 22 |
| The legacy compatibility shim is a read-only facade over authorizer state, unpackaged, widening no coverage | `integrations/nornyx_reference_adapters/governance_kernel.py:1-27`; `pyproject.toml:48` | implemented (unpackaged) | 19, 25 |
| Static adapter-declaration conformance reports carry an all-false safety block | `nornyx/connector_runtime.py:769-801`; `schemas/adapter_conformance_report.schema.json:31-54` | implemented | 25 |
| The governance benchmark demonstrates prevention with a monotonic side-effect ledger and declares its non-wins | benchmark `README.md:59-71,99-103`; `ledger.py` | implemented | 15, 23 |
| The benchmark surfaced three defects, all fixed with regression tests | benchmark `FINDINGS.md:1-20` | implemented | 15 |

## J.6 Packages, workspace, and delivery gates

| Claim | Evidence | Status | Chapter |
|---|---|---|---|
| Package scanning is deterministic, local, network-free, and never executes payloads | `nornyx/package_scanner.py:1153-1159,1192-1198` | implemented | 27 |
| Detectors cover hooks, protocol definitions, secrets, endpoints, dangerous commands, scripts, and claim mismatches | `nornyx/package_scanner.py:33-116,489-728` | implemented | 27, 34 |
| Secret-like values are always redacted and never stored raw | `nornyx/package_scanner.py:234-241,376-419` | implemented | 27 |
| Exactly two external evidence importers exist, and neither executes its tool | `nornyx/cli.py:305`; `nornyx/package_scanner.py:817-820,901-904` | implemented | 11, 27 |
| Nornyx must not claim that a scanned package is safe | `docs/governed-package-profile.md:38,146-148`; `nornyx/package_scanner.py:983` | non-goal (explicit) | 27 |
| Continuous integration fails closed on skipped framework tests and forbids network access in wheel smoke tests | `.github/workflows/ci.yml:263-275,300-358`; `tests/test_wheel_network_guard.py` | implemented | 15, 29 |
| Adapter tests run against the real pinned frameworks; the core matrix covers Python 3.10–3.13 and Windows | `.github/workflows/ci.yml:117-291,445-527` | implemented | 25, 29 |
| Publishing uses trusted publishing with no stored token and a fail-closed tag-format gate | `.github/workflows/release.yml:672-736`; `RELEASING.md:2-6` | implemented | 29 |
| Seven version locations are equality-enforced by tests | `RELEASING.md:10-24`; `tests/test_documentation_consistency.py` | implemented | 29 |
| The repository has no self-governing contract at its root; self-governance is indirect | filesystem search; `.github/workflows/ci.yml:167-168` | implemented (indirect) | 29 |
| The assurance-tier framing forbids overclaiming and is marked design-only | `docs/decisions/ADR-0040-governance-assurance-tiers.md` | guidance | 13 |
| Approximately 1,046 test functions across 86 files | `tests/` | implemented (approximate) | 15 |
| Guardrails, memory, connectors, incident response, containment, and supply-chain surfaces are planned | `docs/04_AI_ENGINEERING_REQUIREMENTS_MATRIX.md` | roadmap | 38 |
| Protocol and telemetry extension descriptors carry planned status only | `extensions/*.yaml` | roadmap | 27 |
| A full model-native language, executing harness runtime, editor server, registry, and studio are future targets | `docs/16_FINAL_LANGUAGE_TARGET.md`; `docs/RFCs/RFC-0003` | roadmap | 16, 38 |

## J.7 Claims not verified, and therefore not made

The following could not be established from the repository at the audited revision. The book does
not assert any of them.

Whether distribution 1.11.0 is live on the public package index: the repository's manifest records
1.10.0 as published, and publication is a separate authorized action outside the repository.
Behavior of the framework adapters against any framework version other than the exact pins: the
pins fail closed at import, so untested versions are refused rather than degraded. Any performance,
latency, throughput, or scale characteristic: the repository contains no benchmark of that kind,
and the book makes no quantitative performance claim. Behavior in a live deployment: no deployment
was observed, and every operational scenario in the book is presented as design reasoning or as a
fictional case study.

Three internal inconsistencies were noted and are not relied upon: a documentation statement that
the module catalogue was frozen at six modules while seven ship; a profile-count statement that
predates the addition of the agentic-network profile; and a benchmark README that names an older
interface version than the one it exercises. Where the code and the documentation disagree, this
book follows the code and says so.
