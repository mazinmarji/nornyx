---
appendix: D
title: "Appendix D — Schema Catalogue"
---

# Appendix D — Schema Catalogue

Forty-two JSON Schema files live under `schemas/` at the audited revision `70d2b40ad792`. They are
not a uniform set: some define the contract language itself, some define the packs that extend it,
some define the reports the toolchain emits, and some define declaration shapes for surfaces that
are documented but not operational. This appendix lists every one of them, grouped by role, so that
a reader who meets a `schema:` identifier in a file can find out what produced it and where the
book explains it.

Two conventions are used throughout. **Closed** means the schema sets `additionalProperties: false`
at the level named — an unexpected field is a validation failure, which is the mechanism by which
credential-shaped fields become unrepresentable rather than merely discouraged. **Open** means
extra fields pass. The *version* column gives the schema identifier constant where the schema
declares one, since that is the string you will see inside documents and reports; where there is
none, it gives the version band from the schema title.

Schemas are bundled inside the wheel under `nornyx/schemas/` with a repository-root fallback for
source checkouts, so both paths refer to the same content.

## D.1 Contract document schemas

These validate a `.nyx` document as a whole. All three are closed at the top level and open inside
each block — the asymmetry explained in Appendix A, section A.2.

| File | Purpose | Version | Shape | Primary consumers | Chapter |
|---|---|---|---|---|---|
| `nornyx_v0_1.schema.json` | The frozen 0.1/0.2 YAML-compatible document schema; the default compatibility target for `nornyx schema` and the checker's registry | v0.1/v0.2 document | closed top level, open blocks | `nornyx/schema_model.py`; `nornyx/release_readiness.py` inventory | 17 |
| `nornyx_v0_2.schema.json` | Adds the static graph and contracts model — typed nodes, edges, and relation verbs | v0.2 static graph and contract | closed top level | `nornyx/schema_model.py` | 17 |
| `nornyx_v1_0.schema.json` | Names the stable generalised agentic contract-language surface: fifteen core blocks, eleven extension blocks, the bounded-goal object, and an embedded safety-boundary statement | v1.0 stable language | closed top level | `nornyx/schema_model.py` | 16, 17 |

**Table D.1 — Contract document schemas.** The 1.0 schema keeps the in-document markers at `"0.1"`
and `"0.2"`; it stabilises the concept set, not the version string.

## D.2 Governance pack and lock schemas

The packs that compose onto a contract, and the lock that pins which ones resolved.

| File | Purpose | Version | Shape | Primary consumers | Chapter |
|---|---|---|---|---|---|
| `profile_pack_v1.schema.json` | The active declarative profile-pack contract: twenty-six required fields including `provenance`, `integrity`, `starter_fragments`, `validation_rules`, `compatibility`, and `non_goals` | `nornyx.profile_pack.v1` | closed | `nornyx/governance/loader.py`, `schemas.py`, `approvals.py` | 18 |
| `governance_module_v1.schema.json` | The active data-only governance module contract: dependencies, conflicts, required blocks, contributed block schemas, policies, evidence and approval requirements, rules, non-goals, provenance, integrity, safety | `nornyx.governance_module.v1` | closed | `nornyx/governance/loader.py`, `schemas.py` | 18 |
| `profiles_lock_v1.schema.json` | Records `{id, version, source_tier, content_hash, path_hint}` per resolved pack. Deliberately time-free so identical resolution inputs produce byte-identical locks | `nornyx.profiles_lock.v1` | closed | `nornyx/governance/locks.py`, `schemas.py` | 18, 29 |
| `domain_profile_pack.schema.json` | The frozen v0.3 legacy pack shape, retained for backward projection from v1 packs | v0.3 domain profile pack | closed | `nornyx/governance/projection.py`; `release_readiness.py` | 18 |

**Table D.2 — Pack and lock schemas.** Thirteen built-in profiles and seven modules ship inside the
wheel; the older root-level profile mirrors were removed to prevent dual-source drift.

## D.3 Effective governance and approval schemas

Three representations of an approval coexist deliberately, and Chapter 9 explains why: the v1 view
is a compatibility shape, v2 adds the fields that make an approval verifiable, and the effective
envelope adds composed operation context and retained source lineage.

| File | Purpose | Version | Shape | Primary consumers | Chapter |
|---|---|---|---|---|---|
| `effective_governance_v2.schema.json` | The complete composed governance model emitted by `CompositionResult.to_effective_dict()`: required blocks, block schemas, structural checks, policies, evidence and approval requirements, evaluations, rules, non-goals, starter fragments, provenance, diagnostics | `nornyx.effective_governance.v2` | closed | `nornyx/governance/schemas.py`; `nornyx governance resolve` | 18 |
| `governance_approval_model_v1.schema.json` | The draft internal normalisation contract for an approval: roles, denied actor types, denied execution surfaces, required evidence, actions, timing, optional exact revision binding, resolution, normalisation diagnostics, and a preserved `source` record | `nornyx.normalized_approval.v1` | closed | `nornyx/governance/approvals.py` | 9 |
| `governance_approval_model_v2.schema.json` | The verifiable normalisation: adds required `accountable_authority`, `exact_revision_required`, relative `expires_after`, and a source binding digest | `nornyx.normalized_approval.v2` | closed | `nornyx/governance/approvals.py` | 9 |
| `effective_approval_v1.schema.json` | The composed approval envelope: adds `operation`, `decisions`, and bounded retained `sources` so that `trusted_effective_approval` can replay the composition | `nornyx.effective_approval.v1` | closed | `nornyx/governance/approvals.py` | 9, 36 |
| `separation_of_duties_v1.schema.json` | Duty-separation assignments over human identity patterns, with the `user:`, `human:`, and `person:` prefixes permitted | `nornyx.separation_of_duties.v1` | closed | `module_separation_of_duties.yaml` block schema | 9, 31 |

**Table D.3 — Approval and effective-governance schemas.** The v1 approval schema carries an
explicit draft marker in its own `$comment`; treat it as the compatibility view, not the
authoritative one.

## D.4 Evidence, exception, and change schemas

| File | Purpose | Version | Shape | Primary consumers | Chapter |
|---|---|---|---|---|---|
| `governance_evidence_v1.schema.json` | Normalised local evidence metadata: subject revision plus records naming producer, artifact, content hash, and validity. Its description is the whole epistemology in one line — "Hashes bind content; they do not prove truth." | `nornyx.governance_evidence.v1` | closed | `module_evidence_integrity.yaml`; `nornyx evidence validate` | 11, 36 |
| `governance_exception_v1.schema.json` | Closed exception (waiver) records requiring control, reason, scope, risk tier, requester, accountable owner, approving authority, compensating controls, evidence, validity window, renewal policy, closure evidence, and status | `nornyx.governance_exceptions.v1` | closed | `module_exception_management.yaml` | 9, 32 |
| `change_v1.schema.json` | The generalised change model for an explicitly selected `change_control` block; a bounded array of up to 1,000 change records | v1 shared change collection | array; **items open**, requiring only `id` and `type` | `module_change_control.yaml`, `module_separation_of_duties.yaml` | 30 |

**Table D.4 — Evidence, exception, and change schemas.** Note the asymmetry: change *records* are
deliberately open, so the structural checks — not the schema — carry the weight of change
governance.

## D.5 Agentic-network declaration schemas

The three block schemas the `agentic_network_governance` module contributes. All are closed at
every object level, which is what makes endpoints, credentials, and approving AI identities
unrepresentable rather than merely rejected.

| File | Purpose | Version | Shape | Primary consumers | Chapter |
|---|---|---|---|---|---|
| `agentic_network_v1.schema.json` | The network declaration: trust zones, memberships, protocol targets, network gates, revocations, and the optional delegations, handoffs, and relations. Defines "no runtime, endpoint, credential, authentication, transport, or execution behavior" | `nornyx.agentic_network.v1` | closed | `module_agentic_network_governance.yaml`; `nornyx/governance/agentic_network.py`, `agentic_delegation.py` | 6, 31 |
| `agent_identities_v1.schema.json` | Up to 1,024 bounded non-human identity declarations linked to role-oriented agents, each carrying `authority: non_human` and `can_approve: false` as constants | v1 agent identities | array; items closed | `module_agentic_network_governance.yaml` | 5, 31 |
| `agentic_capabilities_v1.schema.json` | Up to 1,024 static capability classes with actions, risk tier, context scope, delegability, and required gate, approval, and evidence references. "A declaration is not a runtime token, authority grant, command, script, credential, or approval." | v1 agentic capabilities | array; items closed | `module_agentic_network_governance.yaml` | 5, 31 |

**Table D.5 — Agentic-network declaration schemas.** Their bounded collection sizes are part of the
safety design: an unbounded declaration is a denial-of-service surface for any validator.

## D.6 Network lock and runtime-evidence schemas

| File | Purpose | Version | Shape | Primary consumers | Chapter |
|---|---|---|---|---|---|
| `agentic_network_lock_v1.schema.json` | Content-addressed binding of a network contract, its resolved composition, and its generated artifacts: source contract digest, network id and immutable revision, pack identities and hashes, block schemas, structural checks, runtime-events schema version, protocol declarations, per-record digests, approval and evidence requirements, and artifact hashes. Constants pin `lock_format_version` and `generation_format_version` to `"1.0"` | `nornyx.agentic_network_lock.v1` | closed | `nornyx/agentic_artifacts.py` | 12, 18 |
| `agentic_runtime_events_v1.schema.json` | The closed envelope for supplied local runtime evidence. A three-way `oneOf` over the 1.0 envelope, the 1.1 legacy envelope, and the 1.1 explicit envelope; eighteen closed event types; per-event binding of network id, contract digest, network lock digest, and subject revision; up to 10,000 events | `nornyx.agentic_runtime_events.v1`, versions 1.0 and 1.1 | closed envelopes | `nornyx/agentic_evidence.py`; `EvidenceRecorder` | 11, 12, 20 |

**Table D.6 — Lock and runtime-evidence schemas.** The lock schema's own description states its
boundary: it "proves reviewed-content binding only; it never attests runtime behavior, producer
identity, or truth, and it grants no approval."

The runtime-events schema keeps one identifier across both versions, so the *version* field, not
the identifier, distinguishes envelopes. In 1.0 an event must not carry `occurrence`; in 1.1
explicit mode every event must. A stream is never silently upgraded — its version must match the
lock's `runtime_events_schema`.

## D.7 Architecture-governance schemas

| File | Purpose | Version | Shape | Primary consumers | Chapter |
|---|---|---|---|---|---|
| `architecture_v1.schema.json` | Bounded architecture declarations — viewpoints, systems, components, modules, layers, bounded contexts, interfaces, boundaries, decisions, principles, constraints, required checks, and architecture exceptions. "Nornyx does not infer these values from source." | `nornyx.architecture.v1` | closed | `module_architecture_conformance.yaml` | 18 |
| `architecture_evidence_v1.schema.json` | Up to 500 normalised, revision-bound architecture evidence records supplied by external systems, each binding an artifact and its digest | v1 architecture evidence collection | array; items closed | `nornyx/governance/architecture.py` | 18, 36 |
| `architecture_report_v1.schema.json` | The neutral envelope a continuous-integration adapter emits for an architecture tool: check id, tool, tool version, status, subject revision, generation and expiry times, and violations. "Nornyx imports this file without executing the named tool." | `nornyx.architecture_report.v1` | closed | `nornyx/governance/architecture.py` | 18, 26 |

**Table D.7 — Architecture-governance schemas.** The division of labour recorded in ADR-0030 is
visible in the schemas themselves: Nornyx owns the envelope, the specialist tool runs outside.

## D.8 Adapter and connector contract schemas

These govern *declarations inside contracts*, not the Python framework adapters of Chapters 22–25.
The word "adapter" is shared; the concepts are not, and conflating them is a real error — nothing
in the repository links a conformance report to the `nornyx-agentic-adapters` package.

| File | Purpose | Version | Shape | Primary consumers | Chapter |
|---|---|---|---|---|---|
| `adapter_contract.schema.json` | A declared contract bridge: name, kind, target profile, constant `execution_mode: contract_only` and `live_connector_execution: false`, connector, policy, eval and evidence references, optional connector conformance, and mandatory non-goals from a closed enumeration | v0.4 adapter contract | **open** at the top level; the safety fields are constants | `nornyx/connector_runtime.py`; `nornyx/checker.py` | 25 |
| `adapter_conformance_report.schema.json` | The static conformance report: status, summary counts, a safety block of all-false constants (connectors enabled, adapters executed, network used, commands executed, credentials loaded, contracts executed, live connector execution allowed), per-adapter decisions, and an embedded connector report | `nornyx.adapter_conformance.v0.7` | closed | `nornyx/connector_runtime.py`; `nornyx/bounded_execution.py` | 25 |
| `connector_contract_conformance.schema.json` | The MCP/A2A connector conformance shape: protocols, default mode, `approval_required`, live targets allowed, sensitive sharing allowed | v0.7 connector contract conformance | closed | `nornyx/connector_runtime.py`; `release_readiness.py` | 25, 27 |
| `connector_manifest.schema.json` | A declared connector: name, protocol, capabilities | connector manifest | **open** | `nornyx/connector_runtime.py`; `release_readiness.py` | 27 |

**Table D.8 — Adapter and connector schemas.** "Conformance" here means static, declaration-level
checking with schema-level proof that nothing was executed. It says nothing about a framework
adapter's runtime behaviour.

## D.9 Governed-package schema

| File | Purpose | Version | Shape | Primary consumers | Chapter |
|---|---|---|---|---|---|
| `governed_package.schema.json` | The governed-package profile: profile marker, schema version, package id, mission, tasks, changes, evidence requirements, approval gates, risk tier, artifacts, installation policy, safety boundary, and provenance | governed package profile, schema version `"1.0"` in documents | **open** at the top level; safety enforced by validation code | `nornyx/governed_package.py`; `nornyx/checker.py`; `nornyx/cli.py` | 27 |

**Table D.9 — The governed-package schema.** Because the schema is open, the fail-closed behaviour
of the profile lives in `validate_governed_package` rather than in the schema: permissive
installation or safety flags, execution surfaces as approvers, and unreviewed scanner findings are
all rejected there.

## D.10 Readiness and release report schemas

Local report envelopes. Each is generated by an internal module and consumed by a human or a
pipeline; none authorises anything.

| File | Purpose | Version | Shape | Primary consumers | Chapter |
|---|---|---|---|---|---|
| `bounded_execution_readiness.schema.json` | The readiness report for bounded execution: mode, status, summary, sandbox description, safety block, decisions. Bounded execution itself is declared a future proposal outside the current programme | `nornyx.bounded_execution_readiness.v0.8` | open | `nornyx/bounded_execution.py`; `release_readiness.py` | 38 |
| `release_candidate_stabilization.schema.json` | The release-candidate stabilisation report: target version, status, summary, checks, required validation, safety | `nornyx.release_candidate_stabilization.v0.9` | open | `nornyx/release_readiness.py` | 29 |
| `stable_language_report.schema.json` | The 1.0 stable-language report: target version, status, checks, stable core concepts, stable v1 non-goals, required validation, safety | `nornyx.stable_language.v1.0` | open | `nornyx/release_readiness.py` | 16, 29 |

**Table D.10 — Readiness report schemas.** All three are open, which is appropriate for report
envelopes and inappropriate for anything that binds authority.

## D.11 Extension and roadmap declaration schemas

Eleven schemas define declaration shapes for the documented extension surfaces recorded in
ADR-0012 through ADR-0020. Each has a local validator module that is explicitly read-only, and none
of them is taught as a core chapter topic; they are listed for completeness and because a reader
browsing `schemas/` will meet them. Their identifiers use the `nornyx.local` namespace rather than
`nornyx.dev`, which is itself a useful signal about their status.

| File | Purpose | Shape | Primary consumer | Where the book touches it |
|---|---|---|---|---|
| `decision_boundary.schema.json` | What an AI system may and may not decide, its human owner, and the approval and evidence required | closed | `nornyx/regulated_controls.py` | 9, 38 |
| `evidence_quality.schema.json` | Declared quality expectations for a named evidence requirement | closed | `nornyx/regulated_controls.py` | 11, 38 |
| `handover_contract.schema.json` | A named transition between two states with its requirements, approval, and evidence | closed | `nornyx/handover.py` | 33, 38 |
| `ambiguity_control.schema.json` | A recorded ambiguity with kind, identifier, text, and owner | closed | `nornyx/handover.py` | 33, 38 |
| `pattern_lifecycle.schema.json` | An AI engineering pattern with problem, solution, applicability, validation, evidence, risks, failure modes, and promotion criteria | closed | `nornyx/patterns.py` | 38 |
| `portal_contract.schema.json` | A read-only portal contract: source, role views, render targets. ADR-0012 records the decision to own the contract, not a portal engine | closed | `nornyx/portal_contract.py` | 33, 38 |
| `product_lifecycle_extension.schema.json` | The product-to-operations lifecycle extension: concepts and promotion order | closed | `nornyx/product_lifecycle.py` | 38 |
| `requirement_triage_matrix.schema.json` | The requirement triage matrix: categories and next focus | closed | `nornyx/requirement_triage.py` | 38 |
| `triage_candidate.schema.json` | One agent-discovered requirement candidate with classification, rationale, recommended action, risk, evidence, owner, and status | closed | `nornyx/triage_candidates.py` | 38 |
| `authoring_assistant_roadmap.schema.json` | The authoring-assistant roadmap: capabilities, authority rules, promotion gates, blocked actions, non-goals. The validator "does not call LLMs, host models, run a portal, write .nyx, call connectors, or approve drafts" | closed | `nornyx/authoring_assistant.py`, `nornyx/dev_quality.py` | 28, 38 |
| `evergreen_assurance.schema.json` | The evergreen assurance declaration: kernel, extensions, compatibility, maturity | closed | `nornyx/evergreen.py` | 38 |

**Table D.11 — Extension and roadmap schemas.** Classify these case by case before citing them. A
schema existing is evidence that a shape was designed and validated, not that a capability was
built.

## D.12 Using the catalogue

Three practical notes close this appendix.

**Find the producer before trusting the artifact.** A file carrying `schema:
nornyx.adapter_conformance.v0.7` was produced by `build_adapter_conformance_report` from
declarations; a file carrying `nornyx.agentic_runtime_events.v1` was produced by a self-declared
runtime or recorder. Those two artifacts warrant very different levels of confidence, and only the
schema identifier tells you which you are holding.

**Check whether the level you care about is closed.** `governed_package.schema.json` and
`adapter_contract.schema.json` are open at the top level even though the profiles they support are
strict; `change_v1.schema.json` is an array of open records. In each case the strictness lives in
code, so reading the schema alone will understate what is enforced — and reading it in the other
direction, on the closed agentic-network schemas, will understate how much is enforced *by the
schema itself*.

**Watch the version axis you are actually on.** Document versions (0.1, 0.2), the language target
(1.0), pack schema versions (v1), lock formats (1.0), runtime-events versions (1.0 and 1.1), and
the distribution version (1.11.0) all move independently. Every entry in this catalogue names its
own version precisely for that reason.
