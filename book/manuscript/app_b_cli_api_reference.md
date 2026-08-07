---
appendix: B
title: "Appendix B — Command-Line and Interface Reference"
---

# Appendix B — Command-Line and Interface Reference

This appendix records the command-line and programmatic surfaces of Nornyx at the audited revision
`70d2b40ad792` (distribution 1.11.0, agentic integration service-provider interface (SPI) 1.2,
adapter distribution `nornyx-agentic-adapters` 0.2.0). It is a lookup reference; Chapters 19, 21,
22, and 29 teach the surfaces in context.

Everything below was read from the installed command-line interface (`nornyx --help` and each
subcommand's help) and from the repository source. Where a surface has no published stability
contract, the entry says so explicitly rather than implying one.

## B.1 How to read the stability markers

Three markers appear in the tables.

**Documented.** The surface appears in `docs/GOVERNANCE_CLI_AND_API.md` with a stated result and a
stated exit-code contract, or in a released ADR that defines it as supported. Public behaviour is
not removed without a changelog deprecation notice lasting at least two package minor releases and
six months.

**Internal.** The command exists and is tested, but its implementing module is outside the declared
public Python surface and no equivalent stability promise is documented for it. Fact pack 04
classifies the underlying modules this way, and the architecture document is blunt about the naming:
modules whose names include `runtime`, `adapter`, or `connector` do so "for historical reasons" and
do not turn Nornyx into an execution engine.

**Research/experimental.** The command produces a report about an explicitly non-approved surface.
`language-evolution` is the clearest case: RFC-0003 states that it "does not approve public syntax,
parser behavior, checker semantics, runtime execution".

One further boundary is easy to misread. `docs/public-boundary-policy.md` governs **content**
neutrality — no private downstream product, repository, or customer names anywhere in the public
repository — and says nothing about application programming interface stability. Do not cite it as
a stability policy.

## B.2 The exit-code contract

The governance commands publish a three-value contract, and the rest of the command set follows the
same shape in practice.

| Code | Meaning |
|---|---|
| `0` | Valid, or no governance selected |
| `1` | Invalid pack, governance diagnostic, invalid evidence, or unresolved identity |
| `2` | Contract parse failure, or governance lock path/encoding/JSON/schema/set/hash/semantic validation failure |

**Table B.1 — Documented exit codes.** From `docs/GOVERNANCE_CLI_AND_API.md`. The key asymmetry
for pipeline design: a *lock* failure is a 2, not a 1, so a build step that only tests for exit 1
will treat a stale lock as an unclassified crash.

Two behaviours deserve separate emphasis because they are easy to get wrong in continuous
integration. First, `--as-of` fails closed: a malformed or timezone-naive timestamp produces the
diagnostic `AS_OF_INVALID` and exit 2, and never falls back to the live clock. Second,
`agentic-network evidence-validate` exits nonzero on a failing report **only** when `--strict` is
passed; without it, a failing validation still prints its status and exits 0.

## B.3 Authoring and validation

| Command | Purpose | Key flags | Exit behaviour | Marker |
|---|---|---|---|---|
| `nornyx check <file>` | Validate a contract, including composed profile and module governance | `--as-of` | 0 pass; 1 on any error diagnostic; 2 on parse failure or invalid `--as-of` | Documented |
| `nornyx init --name <n>` | Create a starter contract from a built-in profile | `--profile` **xor** `--profile-path`, `--out`, `--force` | 0; 1 on `INIT_ERROR` | Documented |
| `nornyx fmt <file>` | Canonical formatter for 0.1 documents | `--write`, `--check` | 0; 1 when `--check` finds unformatted input | Internal |
| `nornyx explain <file> [symbol]` | Human-readable explanation of a contract or one symbol | `--json` | 0; 2 on parse failure | Internal |
| `nornyx schema` | Inspect the schema model | `--format json\|grammar`, `--version compat\|0.1\|0.2\|1.0` | 0 | Documented |
| `nornyx examples` | Copy the bundled example contracts | `--out` | 0; 1 on `NO_EXAMPLES` | Internal |
| `nornyx doctor` | Local repository readiness diagnosis | `--repo`, `--json` | 0 when ready; 1 otherwise | Internal |
| `nornyx adopt status` | Inspect a repository and suggest a first adoption step | `--repo` | 0 | Internal |
| `nornyx adopt init-lite --project <p>` | Generate a minimal draft contract | `--repo`, `--out`, `--force` | 0; 1 on `FILE_EXISTS` | Internal |

**Table B.2 — Authoring and validation commands.** `--profile` accepts the thirteen built-in
profile names: `minimal`, `standard`, `ai_coding`, `regulated`, `legacy_upgrade`,
`nornyx_language`, `agentic_repo_harness`, `telecom_ops`, `business_ops`, `ai_governance`,
`finance_ops`, `architecture_governance`, `agentic_network`.

## B.4 Generation, drift, and cross-repository consistency

| Command | Purpose | Key flags | Exit behaviour | Marker |
|---|---|---|---|---|
| `nornyx generate <file>` | Emit the deterministic artifact set from one contract | `--out` (default `generated`) | 0; 1 when the contract has errors | Documented |
| `nornyx drift <file>` | Full-output drift gate: regenerate and compare every artifact by digest | `--out`, `--json` | 0 when status is `pass`; 1 on any drift | Documented |
| `nornyx workspace-check` | Verify member contracts against a workspace manifest's canonical policies | `--manifest`, `--write`, `--quiet`, `--json` | 0 on `pass` or `synced`; 1 on drift; 2 on `WORKSPACE_ERROR` | Documented |
| `nornyx goal-plan <file>` | Emit a bounded goal plan | `--out` | 0; 1 when the contract has errors | Internal |
| `nornyx context-build <file>` | Build a context pack with provenance hashes | `--repo`, `--out`, `--include-content` | 0 | Internal |
| `nornyx evidence-pack` | Create an evidence-pack scaffold | `--out` | 0 | Internal |

**Table B.3 — Generation and consistency commands.** `workspace-check --write` returning 0 with
status `synced` means divergence was rewritten on disk; a pipeline that runs it in write mode is
not a gate, it is a fixer.

`nornyx generate` writes `AGENTS.md`, one `README.md` per skill under `skills/`, the six block
dumps `context.yaml`, `harness.yaml`, `policy.yaml`, `evals.yaml`, `trace.yaml`, and `goals.yaml`,
an `evidence_contract.md`, per-goal task packets and a goal ledger when goals exist, and
`nornyx_generation_manifest.json` carrying a SHA-256 for every artifact. Output is byte-stable:
line-feed newlines are forced, artifact paths and hash lists are sorted, and no timestamps are
written. The README's shorthand list of generated artifacts is incomplete; the generator is the
ground truth.

## B.5 Local decision and planning reports

Every command in this group produces a report. None of them executes an agent, a tool, a model, or
a connector.

| Command | Purpose | Key flags | Exit behaviour | Marker |
|---|---|---|---|---|
| `nornyx policy-check <file>` | Evaluate local policy, guardrail, and capability decisions | `--harness`, `--out` | 0; 1 on error | Internal |
| `nornyx harness-run <file>` | Plan a safe local harness-run manifest | `--harness`, `--repo`, `--out`, `--include-content` | 0; 1 on error | Internal |
| `nornyx eval-run <file>` | Create a local eval report with dataset-integrity checks | `--eval`, `--results`, `--repo`, `--out`, `--strict` | 0; 1 with `--strict` on failed or blocked evals | Internal |
| `nornyx eval-import promptfoo <report>` | Normalise an external eval report and bind it to a declared eval | `--eval-name` (required), `--subject-revision`, `--out` | 0; 1 on `EVAL_IMPORT_ERROR` or `UNSUPPORTED_EVAL_TOOL` | Internal |
| `nornyx connector-plan <file>` | Create a safe local connector/adapter manifest | `--out`, `--strict` | 0; 1 with `--strict` on blocked plans | Internal |
| `nornyx release-check` | Local release-readiness report | `--repo`, `--target-version`, `--approved`, `--out`, `--strict` | 0; 1 with `--strict` on blocking errors | Internal |
| `nornyx stable-language-check` | Local 1.0 stable-language report | same as `release-check` | same | Internal |
| `nornyx language-evolution` | Local language-evolution research report | `--repo`, `--out`, `--strict` | 0; 1 with `--strict` | Research |

**Table B.4 — Report-producing commands.** `harness-run` is named for the concept it plans, not
for an action it takes: the help text says "Plan a safe local harness run manifest". `eval-import`
accepts exactly one tool name, `promptfoo`.

## B.6 Governance inspection

These are the surfaces `docs/GOVERNANCE_CLI_AND_API.md` defines as the documented governance
inspection layer: local, read-only, and data-only. They do not fetch packs, execute tools, analyse
source, write locks, grant approval, deploy, publish, remediate, or activate connectors.

| Command | Purpose | Key flags | Exit behaviour |
|---|---|---|---|
| `nornyx profiles list` | Built-in and project-local profiles with version, status, and source tier | `--json` | 0 |
| `nornyx profiles inspect <name>` | Full validated profile declaration with provenance and content hash | `--json` | 0; 1 on unresolved identity |
| `nornyx profiles validate <path>` | Bounded validation of one local pack | `--json` | 0; 1 on `PACK_*` diagnostics |
| `nornyx profiles resolve <name>` | Resolve one profile; optionally write `nornyx.profiles.lock` | `--lock`, `--json` | 0; 2 on lock mismatch |
| `nornyx profiles compatibility <names...>` | Analyse declared compatibility across profiles | `--json` | 0 |
| `nornyx modules list` | Available modules with versions, dependency ids, source tiers, hashes | `--json` | 0 |
| `nornyx modules inspect <name>` | Full validated module declaration | `--json` | 0; 1 on unresolved identity |
| `nornyx modules validate <path>` | Bounded validation of one local module pack | `--json` | 0; 1 (a profile pack here fails `PACK_KIND_MISMATCH`) |
| `nornyx governance resolve <file>` | Complete effective model, provenance trace, lock state, controls, evidence, approvals, exceptions, matrix, diagnostics | `--as-of`, `--json` | 0/1/2 per Table B.1 |
| `nornyx governance explain <file>` | Concise effective controls and requirements | `--as-of`, `--json` | 0/1/2 |
| `nornyx governance matrix <file>` | One row per contributing pack | `--as-of`, `--json` | 0/1/2 |
| `nornyx evidence validate <path>` | Schema, artifact-hash, revision, dependency, and freshness validation for one governance evidence set | `--as-of`, `--json` | 0/1/2 |

**Table B.5 — The documented governance inspection surface.** Resolution output uses
`nornyx.governance_inspection.v1`; matrix output uses `nornyx.governance_matrix.v1`. Governance
commands verify `nornyx.profiles.lock` when present and never create or rewrite it.

There is no `nornyx governance analyze`. The documentation states this explicitly, and ADR-0031
recorded runtime analysis tooling as not required. Do not write it into a runbook.

Seven governance modules ship: `evidence_integrity`, `human_approval`, `separation_of_duties`,
`exception_management`, `change_control`, `architecture_conformance`, and
`agentic_network_governance`. The first six are the frozen foundational set; the seventh was added
later under the agentic-network track. Modules resolve in dependency order —
`evidence_integrity` has no dependencies, `human_approval` depends on it,
`separation_of_duties` on `human_approval`, and so on — with the profile layered last.

## B.7 Agentic-network artifacts, locks, and evidence

| Command | Purpose | Key flags | Exit behaviour |
|---|---|---|---|
| `nornyx agentic-network generate <file>` | Emit the ten deterministic declaration artifacts | `--out` (default `generated/agentic_network`), `--as-of`, `--json` | 0; 1 on governance error; 2 on parse failure |
| `nornyx agentic-network lock <file>` | Build and write the content-addressed network lock | `--artifacts`, `--out`, `--as-of`, `--json` | 0; 1 when verification of the fresh payload against artifacts fails; 2 on parse failure |
| `nornyx agentic-network lock-check <file>` | Verify an existing lock against the current contract and artifacts | `--lock`, `--artifacts`, `--as-of`, `--json` | 0; 1 on any diagnostic; 2 on parse failure |
| `nornyx agentic-network evidence-validate <file> --events <e>` | Validate supplied local runtime-event evidence against the lock | `--events` (required), `--lock`, `--as-of`, `--out`, `--strict`, `--json` | 0 unless `--strict` and status is not `pass`; 1 on governance error; 2 on parse failure |

**Table B.6 — The agentic-network command group.** Verified live during preparation of this
appendix: `generate` on the bundled support contract reported `"artifact_count": 10` and wrote
`a2a_declaration.json`, `agentic_generation_manifest.json`, `capability_matrix.json`,
`delegation_policy_bundle.json`, `handoff_manifest.json`, `identity_manifest.json`,
`mcp_capability_declaration.json`, `network_manifest.json`, `runtime_evidence_contract.json`, and
`trust_zone_map.json`.

The default lock filename is `nornyx.agentic_network.lock`. Generation requires a resolved
governance profile; otherwise it fails with `AN_ARTIFACT_PROFILE_MISSING`. The artifacts contain no
timestamps, so `--as-of` affects whether validation passes, never the artifact bytes.

## B.8 Governed packages

| Command | Purpose | Key flags | Exit behaviour |
|---|---|---|---|
| `nornyx package scan <src>` | Deterministic local scan of an untrusted artifact directory | `--out`, `--package-id` | 0; 1 on `PACKAGE_SCAN_ERROR` |
| `nornyx package generate <file>` | Generate an inert governed package from a contract | `--out` | 0; 1 on `PACKAGE_GENERATE_ERROR` |
| `nornyx package validate <path>` | Validate a contract, manifest, or generated directory | `--json` | 0; 1 on validation diagnostics or `PACKAGE_VALIDATE_ERROR` |
| `nornyx package register <src>` | Inventory, scan, and hash-lock an existing artifact directory | `--contract`, `--out` | 0; 1 on `PACKAGE_REGISTER_ERROR` |
| `nornyx package radar <src>` | Propose governed-package candidates from a folder | `--out`, `--suggest-contract` | 0; 1 on `PACKAGE_RADAR_ERROR` |
| `nornyx package evidence import <tool> <report>` | Normalise an external evidence report | `--out` | 0; 1 on `UNSUPPORTED_EVIDENCE_TOOL` or `EVIDENCE_IMPORT_ERROR` |

**Table B.7 — Governed-package commands.** Exactly two evidence importers exist: `syft` and
`gitleaks`. Any other tool name exits 1 with `UNSUPPORTED_EVIDENCE_TOOL`.

The scanner never executes the scanned payload. Every scan prints
`"package_payload_executed": false` alongside the risk tier, hooks are not activated, and declared
Model Context Protocol (MCP) servers are not started. Secret-like matches are rewritten to
`REDACTED_SECRET_LIKE_VALUE` and the report asserts
`safety_boundary.raw_secret_values_stored: false`. The permitted claim is narrow: a package may be
described as inventoried, risk-surfaced, evidence-bound, hash-locked, and approval-gated — never as
safe. `radar` output is advisory and carries `proposal_only: true`; its confidence figures are
fixed constants, not a calibrated model.

## B.9 Editor and language-server tooling

`nornyx editor-manifest`, `nornyx syntax`, `nornyx lsp-diagnostics <file>`, `nornyx complete [file]
--path --prefix`, and `nornyx symbols <file>` emit editor-integration payloads to files (each takes
`--out`). They are **internal**: there is no live language-server process, only the JSON shapes an
editor integration would consume. `symbols` exits 2 on a parse failure; the others exit 0.

## B.10 The Python interface

Two public surfaces are declared, and it is worth stating the difference precisely.

**The governance surface.** `nornyx.governance.__all__` is the intentional public governance
application programming interface: thirty-four names covering result types (`CompositionResult`,
`NormalizedApproval`, `EffectiveApproval`, `GovernanceDiagnostic`, `ProfilePack`,
`GovernanceModule`, `ProfileLock`, `LockEntry`, `Rule`, `StarterFragment`,
`GovernanceBlockSchema`, `ProjectionResult`), the registry (`GovernanceRegistry`,
`registry_for_contract`, `registry_for_directory`), composition (`compose_governance`,
`compose_document_governance`, `evaluate_document_governance`), rules (`evaluate_rule`,
`evaluate_rules`), approvals (`normalize_approval`, `trusted_normalized_approval`,
`trusted_effective_approval`), locks (`load_lock`, `write_lock`, `verify_lock`, `lock_for_packs`),
evidence (`validate_governance_evidence_file`, `import_architecture_evidence`), pack loading
(`load_local_pack`, `load_pack_bytes`), projection (`project_profile_to_v03`), the change-scope
hash (`change_scope_hash`), and the error type `GovernanceError`. Callable signatures and
serialised `to_dict()` shapes are stable for the 1.x line unless deprecated first. Loader, schema,
structural-check, and reporting internals outside `__all__` are private.

The top-level package exports six further names, all governed-package: `GovernedPackage`,
`GovernedPackageGenerator`, `GovernedPackageValidator`, `generate_governed_package`,
`validate_governed_package`, and `scan_package`.

**The agentic integration SPI.** `nornyx.agentic` is the supported agentic integration SPI defined
by ADR-0039, currently version 1.2 (`SPI_VERSION`). It re-exports forty-six names. The governance
documentation's statement that the agentic-network work adds "no new public Python export" refers
to the governance package; the SPI is declared separately through its own ADR and changelog entries.

### Constructing an authorizer

```python
from nornyx.agentic import load_authorizer, EvaluationContext, CapabilityRequest

authorizer = load_authorizer(
    "support_network.nyx",
    "nornyx.agentic_network.lock",
    validation_as_of="2026-07-17T00:00:00Z",
)
context = EvaluationContext(
    decision_at="2026-07-17T10:00:00Z",
    observed_subject_revision="git:feedfacefeedfacefeedfacefeedfacefeedface",
)
decision = authorizer.evaluate(
    CapabilityRequest(identity_ref="identity.refund_agent",
                      capability_ref="produce_customer_safe_response"),
    context=context,
)
```

**Listing B.1 — The construction and evaluation path.** Signatures from
`nornyx/agentic/authz.py:1166` and `authz.py:895`.

`load_authorizer(contract_path, lock_path, *, validation_as_of)` is the only construction path that
performs validation, composition, and lock verification. Its failures map to four fail-closed
codes: contract parse or composition failure to `CONTRACT_INVALID`, an unresolved profile to
`PROFILE_MISSING`, a lock read or parse failure to `LOCK_INVALID`, and a failed lock verification
to `LOCK_STALE`. Constructing an `Authorizer` directly performs none of those stages — a
distinction that matters because `Authorizer.state` looks identical either way.

`EvaluationContext` has two mandatory fields. `decision_at` governs *all* temporal action
semantics; `validation_as_of` governs only load-time document validation. The engine reads no
wall-clock time. `observed_subject_revision` must exactly equal the contract's `subject_revision`,
or every request denies with `REVISION_MISMATCH` and a `policy_violation` intent.

Six request types are accepted: `CapabilityRequest(identity_ref, capability_ref)`,
`DelegationRequest(delegation_id)`, `HandoffRequest(handoff_id)`,
`ApprovalRequest(identity_ref, approval)`,
`ZoneCrossingRequest(identity_ref, source_zone, target_zone, approval=None)`, and
`DataShareRequest(identity_ref, target_ref, categories, source_zone, target_zone)`. Approvals are
carried by `ApprovalAssertion(approval_ref, claimed_approver_ref, claimed_actor_type, role,
granted, action_ref, subject_revision, issued_at=None, expires_at=None, evidence_refs=())`.

`Authorizer.resolve_identity(framework, agent_key)` maps a framework-level key to a declared
identity and raises `IdentityResolutionError` with `IDENTITY_UNKNOWN` or `IDENTITY_AMBIGUOUS`.
Resolution failure is deliberately *not* a policy decision.

### Authorizer state

`Authorizer.state` returns the same frozen `AuthorizerState` instance on every access, exposing
`document` and `lock_payload` as detached plain dictionary and list graphs, `composition` as a
detached public `CompositionResult`, and the two digests `contract_digest` and
`network_lock_digest`. State access performs no file read, governance composition, lock
verification, network access, or framework import. It is a read-only capability, added additively
in SPI 1.2.

### Decision outcomes

`DecisionEffect` has three members: `ALLOW`, `DENY`, and `APPROVAL_REQUIRED`. The third is
returned when a zone crossing targets an externally classified destination and no approval
assertion accompanies the request (code `CROSSING_APPROVAL_REQUIRED`, with an `approval_requested`
intent). Treating `APPROVAL_REQUIRED` as a denial loses the distinction between "not permitted" and
"permitted once a human accepts it".

`DecisionCode` enumerates twenty-three members: `ALLOWED`, `CAPABILITY_UNKNOWN`,
`CAPABILITY_DENIED`, `DELEGATION_UNKNOWN`, `DELEGATION_INACTIVE`, `HANDOFF_UNKNOWN`,
`HANDOFF_AUTHORITY`, `APPROVAL_REQUIRED`, `APPROVAL_NON_HUMAN`, `APPROVAL_ROLE_INVALID`,
`APPROVAL_NOT_GRANTED`, `APPROVAL_STALE`, `APPROVAL_REVISION_MISMATCH`,
`APPROVAL_ACTION_MISMATCH`, `APPROVAL_EVIDENCE_MISSING`, `PARTY_INEFFECTIVE`,
`ZONE_CROSSING_DENIED`, `CROSSING_APPROVAL_REQUIRED`, `SENSITIVE_SHARING`, `SHARE_NOT_ALLOWED`,
`REVISION_MISMATCH`, and `REQUEST_MALFORMED`. A `Decision` carries `effect`, `code`, `reason`, a
`basis` tuple of `DecisionBasis(kind, ref, detail)` records, and an `event_intents` tuple; the
`.allowed` property is true only for `ALLOW`.

### The evidence recorder

```python
recorder = EvidenceRecorder(authorizer, context, producer_id="my-adapter")
recorder.record_decision(decision, mission_id="GOAL-001")
recorder.record_observation("tool_invoked", mission_id="GOAL-001",
                            actor_ref="identity.refund_agent")
report = recorder.validate()          # -> {"status": "pass", ...}
stream = recorder.stream()            # -> the runtime-events envelope
```

**Listing B.2 — Recording a decision and its post-action observation.** Method signatures from
`nornyx/agentic/authz.py:1214-1400`.

The constructor takes `(authorizer, context, *, producer_id, producer_version="1.0",
producer_type="framework_adapter")`; `producer_type` is restricted to the schema's three values
(`framework_adapter`, `synthetic_harness`, `external_runtime`). The recorder refuses an
`observed_subject_revision` that differs from the authorizer's, takes its schema version from the
authorizer's lock, and stamps timestamps from `context.decision_at` — it reads no wall clock.

Three construction modes matter. The plain constructor emits runtime events 1.0, or 1.1 in legacy
occurrence mode against a 1.1 lock. `EvidenceRecorder.for_occurrences(...)` requires a 1.1 lock and
sets explicit occurrence mode, enabling `record_occurrence_decision`,
`record_occurrence_observation`, and `max_recorded_attempt(mission_id, operation_id,
occurrence_id)`. `EvidenceRecorder.resume(authorizer, context, prior_stream, ...)` validates and
deeply detaches a complete prior stream, requires matching producer, schema version, and occurrence
mode, refuses a `decision_at` that precedes any prior event timestamp, restores per-mission
sequence counters, and returns cumulative evidence. Differential chunks and multi-producer merging
are not supported.

## B.11 The adapter distribution

`nornyx-agentic-adapters` 0.2.0 is a separate distribution with its own semantic versioning,
classified Development Status 3 (Alpha), depending on `nornyx>=1.10,<2`. Its base package imports
no agent framework; framework code lives in extras-gated submodules.

The public surface of the base package is twelve names plus `__version__`: `AdapterMetadata`,
`CoverageInventory`, `SurfaceCoverage`, `SurfaceStatus`, `enforce`, `AdapterDenied`,
`AdapterConfigurationError`, `UnsupportedSPIVersionError`, `MissingOptionalDependencyError`,
`require_extra`, `SurfaceBinding`, and `validate_binding`.

```python
def enforce(authorizer, request, *, context, recorder, mission_id, action,
            on_decision=None):
    decision = authorizer.evaluate(request, context=context)
    recorder.record_decision(decision, mission_id=mission_id)
    if on_decision is not None:
        on_decision(decision)
    if not decision.allowed:
        raise AdapterDenied(decision)
    return action()
```

**Listing B.3 — The single enforcement boundary.** From
`adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/enforcement.py:28-65`. The
evaluate-then-record-then-execute ordering is a compatibility guarantee: changing it is classified
a breaking change.

`SurfaceBinding(surface, identity_ref, capability_ref)` is the closed declarative mapping;
`validate_binding` fails closed on any blank field. Bindings are built from an adapter's static
configuration, never from raw framework arguments. `SurfaceStatus` has three members — `WRAPPED`,
`UNSUPPORTED`, and `UNWRAPPED` — and `CoverageInventory.as_dict()` produces a deterministic,
sorted, JSON-serialisable record. `AdapterMetadata` declares name, version, SPI version, framework
name, and version ranges; it enforces nothing itself, and should never be cited as the enforcement
mechanism. The actual pin enforcement is an import-time check inside each framework submodule.

Two framework submodules ship. `nornyx_agentic_adapters.crewai_adapter` exports `COVERAGE_INVENTORY`,
`FRAMEWORK`, `METADATA`, `agent_identity_key`, `make_governed_tool`, and `resolve_identity`; it
requires `crewai==1.15.4`. `nornyx_agentic_adapters.langgraph` exports `COVERAGE_INVENTORY`,
`FRAMEWORK`, `METADATA`, `make_governed_node`, `node_identity_key`, and `resolve_identity`; it
requires `langgraph==1.2.2`. Both check the installed distribution version at module import: a
missing framework raises `MissingOptionalDependencyError` naming the extras install, and an
installed-but-wrong version raises `AdapterConfigurationError` naming both versions. The base
package additionally asserts the core SPI major version at import, raising
`UnsupportedSPIVersionError` on a mismatch.

The supported adapters perform no filesystem input or output, never load or re-read contracts, and
do not use `Authorizer.state`. They receive an already-constructed authorizer, evaluation context,
and recorder as explicit parameters.

Finally, one surface exists that should not be mistaken for part of this distribution. The M2-D
legacy compatibility shim at `integrations/nornyx_reference_adapters/governance_kernel.py`
re-implements the deprecated `GovernanceKernel` over the public SPI 1.2. It is merged at the
audited revision but sits under the changelog's unreleased section, requires Nornyx 1.11.0, and is
**unpackaged**: it ships in neither the core wheel nor the adapter wheel, and it widens no declared
coverage. Its twenty-two `AN_ADAPTER_*` codes are compatibility translations, not public SPI
guarantees.
