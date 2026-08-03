# FACT PACK 02 — Agentic-Network Profile, Evidence, Locks, and Authorization SPI

Audited at repository `/home/user/nornyx`, git HEAD `70d2b40` ("Merge pull request #56 … feat/m2d-legacy-compatibility-shim"), package version 1.11.0 (`CHANGELOG.md` `[1.11.0] - 2026-08-01`). All paths are relative to the repository root unless absolute. Status labels: **IMPLEMENTED** (code + tests exist), **GUIDANCE/ROADMAP** (documentation only), **NON-GOAL** (explicitly declared out of scope).

Verification performed live during this audit (not just read): `nornyx agentic-network generate` and `lock` were run on `examples/agentic_network_support/support_network.nyx` (10 artifacts, lock built, second generation byte-identical via `diff -r`), and an explicit-mode 1.1 event stream was produced via `EvidenceRecorder.for_occurrences` and validated `pass`.

---

## 1. Document set: docs/agentic-network/00–12

All thirteen files exist under `docs/agentic-network/` (00_OVERVIEW.md 64 lines … 12_AUTHORIZATION_SPI.md 60 lines).

| Doc | Normative content |
| --- | --- |
| `00_OVERVIEW.md` | Positions Nornyx as "a design-time governance compiler, deterministic control-artifact generator, and revision-bound evidence validator." Enumerates non-goals verbatim: "not a runtime control plane, policy proxy, agent orchestrator, observability backend, Promptfoo or LangSmith replacement, identity provider, secrets manager, MCP runtime, A2A runtime, or deployment system." Capability table AN-001…AN-006 maps surfaces (`nornyx check`, `agentic-network generate/lock/lock-check`, `evidence-validate`, adapters, product proof). "Honest limits" section: validated evidence proves conformance of supplied records only; hashes prove content binding not truth; adapter enforcement cannot cover every escape path; "Nornyx never operates, observes, or monitors the running network, and it never grants approvals." |
| `01_TUTORIAL.md` | Eight-step offline end-to-end flow on `examples/agentic_network_support/support_network.nyx`: check → governance explain → generate ("Ten canonical, timestamp-free JSON declarations … Rerunning produces byte-identical output") → lock/lock-check (`AN_LOCK_SOURCE_STALE` on any edit) → eval-import/eval-run → `run_demo.py` → evidence-validate (both streams, `--strict`) → reference CI (`scripts/agentic_network_ci.py`). |
| `02_CREWAI_GUIDE.md` | CrewAI reference adapter at `integrations/nornyx_reference_adapters/crewai_adapter.py`, "deliberately **not** part of the `nornyx` wheel"; duck-typed `role` mapping via `framework_bindings`; fail-closed `AN_ADAPTER_IDENTITY_UNKNOWN`, `AN_ADAPTER_LOCK_STALE`, `AN_ADAPTER_APPROVAL_NON_HUMAN`; "the adapter never grants approval"; final authority is evidence-validate. References the A/B example `examples/crewai_nornyx_comparison/`. |
| `03_LANGGRAPH_GUIDE.md` | Supported M2-C adapter distributed separately: `pip install "nornyx-agentic-adapters[langgraph]"`; compatibility "Nornyx core `>=1.10,<2`, agentic SPI major 1 (including SPI 1.2), and LangGraph `==1.2.2`". Maps `SurfaceBinding.surface`→operation, `ExecutionInfo.task_id`→occurrence, `ExecutionInfo.node_attempt`→attempt; adapter offsets LangGraph's attempt reset after checkpoint resume so the Nornyx attempt stays contiguous. Denial raises `AdapterDenied`; node exception records `runtime_failed`; interrupt is propagated without `runtime_failed`. Coverage boundary: synchronous StateGraph nodes via explicit `make_governed_node` only; async, distributed, implicit interception unsupported; "cooperative Tier 2 evidence". |
| `04_EXTERNAL_EVAL_EVIDENCE.md` | Nornyx "does not run" eval tools. `eval-import promptfoo` binds normalized output to report SHA-256 and subject revision (`EVAL_IMPORT_ERROR` on mismatch); `eval-run` hashes datasets/holdouts, checks overlap, evaluates thresholds. Approval is revision-bound (`revision_binding.exact: true`) and expiring (`expires_after: P7D` in prose; the example uses absolute `expires_at`). Honest limit: "It cannot verify that the evaluation was actually run, that the metrics are honest, or that the dataset was appropriate." |
| `05_PROTOCOL_DECLARATIONS.md` | `generate` emits `a2a_declaration.json` and `mcp_capability_declaration.json`: "**declarations, not runtimes**." Contents: identity/capability labels with scopes, expected message classes, contract/schema/version identifiers, required approvals and evidence, trust-zone restrictions, denied sensitive categories (`credentials`, `private_memory`, `secrets`, `tokens`), and the mandatory pair `execution_mode: contract_only` / `live_connector_execution: false`. Never contains: "URLs, IP addresses, hostnames, ports, commands, executable code, credentials, tokens, keys, secrets, active sessions, runtime-discovery data, transport activation, deployment instructions, or approval-granting fields" — enforced by `AN_ARTIFACT_FORBIDDEN_FIELD` / `AN_ARTIFACT_FORBIDDEN_VALUE`. |
| `06_RUNTIME_EVIDENCE.md` | See §5 below (full detail). Closed 18-type event set; every event binds `network_id`, `contract_digest`, `network_lock_digest`, `subject_revision`; ordering proves "local sequence consistency of the supplied stream" only; 1.0 vs 1.1 legacy vs 1.1 explicit modes; recorder/resume semantics. Proof boundary: "A runtime can omit or fabricate events; validation proves conformance of what was supplied against the exact contract revision, nothing more." |
| `07_NETWORK_LOCK.md` | See §4 below. Lock binds contract digest, network id + immutable revision, profile/module identities+hashes, block schemas, structural checks, runtime-events schema version, protocol declaration versions, per-record digests, approval/evidence requirement references, artifact SHA-256s. "The lock contains no secrets and attests contract/artifact binding only. … A hostile local writer can regenerate a consistent lock — detecting unauthorized regeneration is a repository control (git history and human review), not a lock property." |
| `08_SECURITY_BOUNDARIES.md` | See §10 below (quoted). |
| `09_TROUBLESHOOTING.md` | Symptom table for `AN_DELEGATION_FORBIDDEN`, `AN_DELEGATION_GOVERNANCE_MISSING`, `AN_DELEGATOR_MEMBERSHIP_REQUIRED`, `AN_HANDOFF_AUTHORITY_ESCALATION`, `AN_APPROVAL_ACTION_MISSING`, `AN_LOCK_SOURCE_STALE`, `AN_LOCK_ARTIFACT_UNEXPECTED`, `AN_EVT_SEQUENCE_GAP`, `AN_EVT_CAPABILITY_NOT_HELD`, `AN_EVT_LOCK_STALE`, `AN_EVT_SCHEMA_LOCK_MISMATCH`, `AN_EVT_ATTEMPT_GAP`, `AN_EVT_ATTEMPT_AFTER_SUCCESS`, `AN_ADAPTER_IDENTITY_UNKNOWN`, `AN_ADAPTER_LOCK_STALE`, `EVAL_IMPORT_ERROR`, `GOVERNANCE_BLOCK_SCHEMA_INVALID`. Timing rule: "every timing decision uses the explicit `--as-of` offset timestamp (or now, in `nornyx check`)." |
| `10_BEFORE_AFTER_AND_POSITIONING.md` | Product-question comparison (Git/CI/Promptfoo/frameworks each competent; the gap is "the **governance contract tying those surfaces together**"). Measured table from `run_demo.py` + CI: 2 frameworks, 10 artifacts, 4 identities / 8 capabilities / 2 trust zones, 10 allowed scenarios, 11 blocked (5 adapter + 6 static), 34 CrewAI-path and 14 LangGraph events validated, 4/4 eval thresholds, "Network attempts / external commands during validation: 0 / 0 (observed by tests)". "no performance, adoption, enterprise, or cost claims are made." |
| `11_REFERENCE_CI.md` | `scripts/agentic_network_ci.py`: 14 steps (optional `--wheel` clean-venv install, check, resolve, generate, regenerate+byte-compare drift gate, lock+lock-check, eval-import, eval-run --strict, CrewAI path, LangGraph path, evidence-validate --strict × 2, governance explain, audit-package assembly, nonzero exit on failure). Copy-paste GitHub Actions job; "The job needs no secrets." |
| `12_AUTHORIZATION_SPI.md` | See §6 below. SPI 1.2 additive `Authorizer.state` (`AuthorizerState`): `state.document` (detached plain dict/list), `state.composition` (detached public `CompositionResult`), `state.lock_payload`, `state.contract_digest`, `state.network_lock_digest`. Views are detached copies; retained graph recursively frozen; state access "performs no file read, governance composition, lock verification, network access, or framework import." `Authorizer(...)` constructor "does not itself read, validate, compose, or verify files" — assurance requires `load_authorizer(...)`. "This is a read-only SPI capability." |

Status: all thirteen docs are GUIDANCE describing IMPLEMENTED behavior; every code cited in them was located in code (see traceability rows).

---

## 2. The declaration model (schemas + enforcement)

### 2.1 `agentic_network` block — `schemas/agentic_network_v1.schema.json` (470 lines)

- Top level (`required`, lines 8–17): `schema` (const `nornyx.agentic_network.v1`), `id`, `subject_revision`, `trust_zones`, `memberships`, `protocol_targets`, `network_gates`, `revocations`; optional `delegations`, `handoffs`, `relations`. `additionalProperties: false` (line 63) — the schema is closed.
- `subject_revision` pattern (lines 77–82): `^(?:git:(?:[0-9a-f]{40}|[0-9a-f]{64})|sha256:[0-9a-f]{64})$` — immutable content-addressed revisions only (no branch names).
- **Trust zone** (`$defs/trustZone`, lines 102–133): required `id`, `classification` (enum: `governed_local`, `internal`, `isolated`, `test`, `external`, `external_contract_only`, `contract_only`), `allowed_transition_targets`, `share_allowlist`, `never_share` (**non-empty** ids — a zone must declare at least one never-share category), `ingress_gate_refs`, `egress_gate_refs`. Closed.
- **Membership** (lines 134–157): `id`, `identity_ref`, `trust_zone_ref`, `capability_refs`, `status` (enum `authorized|suspended|revoked|expired`), `valid_from`, `expires_at`, `revocation_refs`. Closed.
- **Protocol target** (lines 158–195): `protocol` enum **`mcp` | `a2a` only** (line 179), `version`, `execution_mode` **const `contract_only`** (line 181), `live_connector_execution` **const `false`** (line 182), `identity_refs`, `source_membership_refs`, `source_zone_ref`, `capability_refs`, `trust_zone_ref`, `share`, `never_share` (non-empty), `required_gate_refs`, `required_approval_refs`, `required_evidence_refs`. Closed — no endpoint/credential field can even be expressed.
- **Network gate** (lines 196–217): `action_classes` (non-empty), `source_zone_refs`, `target_zone_refs`, `required_policy_refs`, `required_approval_refs`, `required_evidence_refs`.
- **Revocation** (lines 218–247): `target` is a `oneOf` over 7 closed target kinds: `agent_identity`, `membership`, `capability_assignment` (with `principal_type` `agent_identity|membership`), `protocol_target`, `approval_record`, `delegation`, `handoff` (lines 248–312); plus `effective_at`, `reason`, `required_approval_refs`, `required_evidence_refs`.
- **Delegation** (lines 313–361): `delegator_ref`, `delegate_ref`, `capability_ref`, `purpose`, `actions` (non-empty), `scope_refs` (non-empty), `status` (`active|suspended|revoked|expired`), `valid_from`/`expires_at`, `max_depth` (int 1–8), `current_depth` (0–8), `onward_delegation` enum **`denied` | `allowed_with_policy`**, optional `parent_delegation_ref`, source/target zone refs, required gate/policy/approval/evidence refs, `revocation_refs`.
- **Handoff** (lines 362–416): `from_identity_ref`, `to_identity_ref`, `purpose`, `mission_ref`, `from_zone_ref`, `to_zone_ref`, `required_capability_refs` (non-empty), `delegation_refs`, `shared_context`, `never_share` (non-empty), `status` enum `initiated|accepted|completed|rejected|expired|revoked|superseded`, optional `superseded_by_ref`, validity interval, gate/approval/evidence refs, `revocation_refs`.
- **Relation** (lines 417–468): endpoints typed over 10 kinds (`agent_identity`, `capability`, `trust_zone`, `membership`, `protocol_target`, `delegation`, `handoff`, `approval`, `revocation`, `human_role`); `type` enum of 11 verbs: `identifies`, `owns`, `advertises_capability`, `delegates_to`, `hands_off_to`, `communicates_with`, `crosses_trust_zone`, `shares_with`, `requires_approval_from`, `revokes`, `observed_by`; optional `delegation_ref`/`handoff_ref`/`protocol_target_ref`/`share_categories`/`description`.
- Bounded collections everywhere (e.g., `trust_zones` maxItems 256, `memberships`/`delegations`/`handoffs` 1024, `relations` 2048).

### 2.2 Agent identities — `schemas/agent_identities_v1.schema.json` (80 lines)

Array (max 1024) of closed identity objects, all fields required (lines 40–54): `id`, `role_ref` (links to a stable-core agent), `identity_class` (`local_agent|external_agent|service_agent|test_agent`), `namespace`, `subject`, `framework_bindings` (max 32 unique `{framework, agent_key}` pairs, lines 29–37), `capability_refs`, `status` (`active|suspended|revoked|expired`), `valid_from`, `expires_at`, `revocation_refs`, and the two constitutional constants: **`authority` const `non_human`** (line 74) and **`can_approve` const `false`** (line 75). The schema makes an approving AI identity unrepresentable; code additionally enforces it (see §7).

### 2.3 Capabilities — `schemas/agentic_capabilities_v1.schema.json` (58 lines)

Array (max 1024) of closed capability objects: `name`, `actions` (non-empty), `risk` (`low|medium|high|critical`, line 46), `scope_type` **const `context`** (line 47 — scope is always a declared context), `scope_refs` (non-empty), `delegable` (boolean), optional `max_delegation_depth` (1–8, line 50), `required_gate_refs`, `required_approval_refs`, `required_evidence_refs`. Description (line 5): "A declaration is not a runtime token, authority grant, command, script, credential, or approval."

### 2.4 Rejected fields and forbidden content

- Every block schema sets `additionalProperties: false` (troubleshooting entry `GOVERNANCE_BLOCK_SCHEMA_INVALID`: "The schemas are closed by design; extra fields (including credential-like ones) are rejected", `docs/agentic-network/09_TROUBLESHOOTING.md`).
- Generation-time scanning (`nornyx/agentic_artifacts.py` lines 78–116): `_FORBIDDEN_KEY_SEGMENTS` = {`apikey`, `bearer`, `cmd`, `command`, `commands`, `credential`, `credentials`, `endpoint`, `endpoints`, `host`, `hostname`, `hosts`, `ip`, `password`, `passwords`, `port`, `ports`, `secret`, `secrets`, `session`, `sessions`, `shell`, `token`, `tokens`, `uri`, `url`, `urls`}; `_FORBIDDEN_KEY_PAIRS` = {("api","key"), ("key","material"), ("private","key"), ("access","key")}; plus IPv4-literal value detection (`_IPV4_RE`, line 116). Violations fail closed via `AN_ARTIFACT_FORBIDDEN_FIELD` (line 270) / `AN_ARTIFACT_FORBIDDEN_VALUE` (lines 286, 293) in `_scan_forbidden` (line 265).
- Sensitive categories: `SENSITIVE_CATEGORIES = frozenset({"secrets", "credentials", "tokens", "private_memory"})` — **defined once** at `nornyx/governance/agentic_network.py:12` and imported by `nornyx/agentic_evidence.py` (line 30) and `nornyx/agentic/authz.py` (line 59). `EXTERNAL_ZONE_CLASSIFICATIONS = frozenset({"external", "external_contract_only", "contract_only"})` at `nornyx/governance/agentic_network.py:13` (duplicated literal at `nornyx/agentic_evidence.py:45`).

### 2.5 The `nornyx/agentic/` package (enumerated)

`nornyx/agentic/` contains exactly two modules: `__init__.py` (125 lines — curated re-exports + authz exports, docstring "the supported agentic integration SPI (ADR-0039)") and `authz.py` (1,667+ lines, the authorization engine). The wider agentic implementation lives in `nornyx/agentic_artifacts.py` (1,040 lines — generation + lock), `nornyx/agentic_evidence.py` (1,103 lines — evidence validation), `nornyx/governance/agentic_network.py` (1,665 lines — `agentic_network_foundation.v1` static check), and `nornyx/governance/agentic_delegation.py` (1,676 lines — `agentic_network_delegation.v1` static check). Status: IMPLEMENTED.

Static check diagnostics (selection with code locations): non-human approval invariant `AN_NON_HUMAN_APPROVAL_INVALID` ("Agent identities must remain non-human and cannot approve", `nornyx/governance/agentic_network.py:1036–1042`); `AN_APPROVAL_HUMAN_REQUIRED` ("must be produced by an authorized human", same file lines 646–657); `AN_SENSITIVE_SHARE_BOUNDARY_MISSING` (line ~230); delegation checks `AN_SELF_DELEGATION`, `AN_CAPABILITY_NOT_DELEGABLE`, `AN_DELEGATION_ACTION_ESCALATION`, `AN_DELEGATION_SCOPE_ESCALATION`, `AN_DELEGATION_SENSITIVE_SHARING`, `AN_DELEGATION_DEPTH_*`, `AN_ONWARD_DELEGATION_DENIED`, `AN_DELEGATION_CHAIN_CYCLE`, `AN_DELEGATOR_MEMBERSHIP_REQUIRED` (`nornyx/governance/agentic_delegation.py` lines 556–898); handoff checks `AN_HANDOFF_AUTHORITY_ESCALATION` (line 1113), `AN_HANDOFF_SENSITIVE_SHARING` (line 1128); protocol-target checks `AN_PROTOCOL_*` (`nornyx/governance/agentic_network.py` lines 1319–1569, incl. `AN_PROTOCOL_TRANSITION_NOT_ALLOWED`, `AN_PROTOCOL_EGRESS_GATE_MISSING`, `AN_PROTOCOL_INGRESS_GATE_MISSING`, `AN_PROTOCOL_APPROVAL_REQUIRED`); share checks `AN_SHARE_NOT_ALLOWED_SOURCE`/`_TARGET` (lines 1602–1610); Unicode collision `AN_NORMALIZATION_COLLISION` (NFKC casefold, `agentic_delegation.py:166`).

---

## 3. Generation — `nornyx agentic-network generate`

- CLI: `nornyx agentic-network generate FILE [--out DIR] [--as-of TS] [--json]` (`nornyx/cli.py` lines 1588–1596); default out dir `generated/agentic_network` (`DEFAULT_ARTIFACT_DIR`, `nornyx/agentic_artifacts.py:38`). Handler `cmd_agentic_network_generate` (`nornyx/cli.py:765–782`).
- **Exactly 10 artifacts** = 9 declarations (`ARTIFACT_NAMES`, `nornyx/agentic_artifacts.py:66–76`): `network_manifest.json`, `identity_manifest.json`, `capability_matrix.json`, `trust_zone_map.json`, `delegation_policy_bundle.json`, `handoff_manifest.json`, `runtime_evidence_contract.json`, `a2a_declaration.json`, `mcp_capability_declaration.json` — plus `agentic_generation_manifest.json` (`GENERATION_MANIFEST_NAME`, line 40). Verified live: generate on the support contract reported `"artifact_count": 10` with those names.
- **Determinism**: canonical JSON rendering (`_canonical_bytes`/`_rendered_bytes`, lines 142–158), keyed-record sorting (`_sorted_collection`, line 222), timestamp-free content ("Ten canonical, timestamp-free JSON declarations", `docs/agentic-network/01_TUTORIAL.md`). Verified live: two runs of `generate` produced byte-identical directories (`diff -r` clean).
- **`--as-of` semantics**: `--as-of` supplies the governance-evaluation instant used to validate the contract before generation; if omitted, "now" is used: `as_of = getattr(args, "as_of", None) or datetime.now(timezone.utc).isoformat()` (`nornyx/cli.py:728`, inside `_agentic_document_and_composition`). The artifacts themselves contain no timestamps, so `--as-of` affects only whether validation passes, not artifact bytes. Malformed/naive `--as-of` fails closed with `AS_OF_INVALID` (CHANGELOG 1.9.0).
- Generation requires a resolved governance profile; otherwise `AN_ARTIFACT_PROFILE_MISSING` (`nornyx/cli.py:756–761`). Missing `agentic_network` block: `AN_ARTIFACT_NETWORK_MISSING` (`nornyx/agentic_artifacts.py:303`).

Status: IMPLEMENTED (tests: `tests/test_agentic_network_artifacts.py`, 25 test functions, 558 lines).

---

## 4. The network lock

Schema: `schemas/agentic_network_lock_v1.schema.json` (188 lines). Schema id `nornyx.agentic_network_lock.v1`; **`lock_format_version` const `"1.0"`** and **`generation_format_version` const `"1.0"`** (lines 27–28). Default filename `nornyx.agentic_network.lock` (`DEFAULT_LOCK_NAME`, `nornyx/agentic_artifacts.py:39`). Closed (`additionalProperties: false`, line 149).

The lock binds (required fields, schema lines 7–24; construction in `_build_agentic_network_lock`, `nornyx/agentic_artifacts.py:685–774`):

1. `source_contract_digest` — sha256 of the canonical governed-content view of the parsed contract (`contract_digest`, line 246; stable under formatting/reordering per `docs/agentic-network/07_NETWORK_LOCK.md`);
2. `network_id` and `subject_revision` — the revision must be immutable content-addressed or lock build fails `AN_LOCK_REVISION_MUTABLE` (lines 705–713);
3. `profile` and `modules` — pack id/name/version/`content_hash` entries (schema `$defs/packEntry`, lines 163–173). Verified live for the support example: profile `nornyx.builtin.agentic_network` 0.1.0; modules include `agentic_network_governance` 0.2.0 and `evidence_integrity` 1.0.0;
4. `block_schemas` (block → schema_id) and `structural_checks` — verified live: `agentic_network_delegation.v1`, `agentic_network_foundation.v1`;
5. `runtime_events_schema` — `{id: nornyx.agentic_runtime_events.v1, version: "1.0"|"1.1"}` (schema lines 62–70). New locks default to 1.1 (`RUNTIME_EVENTS_SCHEMA_VERSION = "1.1"`, `nornyx/agentic_artifacts.py:43`; `build_agentic_network_lock` line 674–682). Historical 1.0 locks are reconstructed and verified against their declared version via the private `_build_agentic_network_lock(..., runtime_events_schema_version=...)` path (docstring lines 691–695; CHANGELOG 1.10.0);
6. `protocol_declarations` — id/protocol/version_label/`execution_mode: contract_only` per protocol target (lines 732–743);
7. `records` — a sorted `{id, digest}` list per collection: `agent_identities`, `capabilities` (keyed by `name`), `trust_zones`, `memberships`, `network_gates`, `protocol_targets`, `delegations`, `handoffs`, `relations`, `revocations` (lines 744–759; schema lines 86–113);
8. `approval_requirements` and `evidence_requirements` — sorted reference ids from the composition (lines 760–767);
9. `artifacts` — `{path, sha256}` for every generated artifact (lines 768–771); artifact paths are basenames only (schema pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`, line 136 — no directory separators).

**Lock verification** (`verify_agentic_network_lock`, `nornyx/agentic_artifacts.py:887+`) compares field-by-field with dedicated codes (lines 916–1028): `AN_LOCK_NETWORK_MISMATCH`, `AN_LOCK_REVISION_MISMATCH`, `AN_LOCK_SOURCE_STALE` (contract digest), `AN_LOCK_PROFILE_MISMATCH`, `AN_LOCK_MODULE_MISMATCH`, `AN_LOCK_SCHEMA_MISMATCH` (block schemas and runtime-events schema), `AN_LOCK_CHECKS_MISMATCH`, `AN_LOCK_PROTOCOL_MISMATCH`, `AN_LOCK_APPROVAL_MISMATCH`, `AN_LOCK_EVIDENCE_MISMATCH`, `AN_LOCK_FORMAT_MISMATCH`, `AN_LOCK_RECORD_MISMATCH` (per-record digests), `AN_LOCK_ARTIFACT_MISMATCH`/`AN_LOCK_ARTIFACT_MISSING`/`AN_LOCK_ARTIFACT_UNEXPECTED` (on-disk artifact hashes vs. lock), plus `AN_LOCK_MALFORMED` on load (lines 847–870) and `AN_LOCK_REVISION_MUTABLE`. CLI: `lock` (writes only if verification of freshly built payload vs. artifacts passes, `nornyx/cli.py:785–816`) and `lock-check` (report schema `nornyx.agentic_network_lock_check.v1`, exit 1 on any diagnostic, lines 819–842).

**What the lock does NOT prove** (verbatim, `docs/agentic-network/07_NETWORK_LOCK.md`): "It never attests that runtime behavior complied, who produced the bytes, or that the content is true. A hostile local writer can regenerate a consistent lock — detecting unauthorized regeneration is a repository control (git history and human review), not a lock property." Same claim in the lock schema description (`schemas/agentic_network_lock_v1.schema.json:5`): "The lock proves reviewed-content binding only; it never attests runtime behavior, producer identity, or truth, and it grants no approval."

Status: IMPLEMENTED (tests incl. `tests/test_agentic_network_artifacts.py`, `tests/test_governance_audit_path_and_lock_security.py` — 49 test functions, 1,523 lines).

---

## 5. Runtime evidence

### 5.1 Schema — `schemas/agentic_runtime_events_v1.schema.json` (197 lines)

Schema id stays `nornyx.agentic_runtime_events.v1` across versions. Top level is a `oneOf` over three envelopes (lines 6–10):

- `envelopeV10` (lines 157–168): `schema_version` const `"1.0"`, events use `eventLegacy` (an event **must not** carry `occurrence`, lines 148–151).
- `envelopeV11Legacy` (lines 169–181): `schema_version` `"1.1"` + required `occurrence_mode: "legacy"`, same legacy event shape.
- `envelopeV11Explicit` (lines 182–194): `occurrence_mode: "explicit"`, every event **requires** `occurrence` (`eventExplicit`, lines 152–156).

Envelope fields: `schema`, `schema_version`, (`occurrence_mode` in 1.1), `network_id`, `producer` (`type` enum `framework_adapter|synthetic_harness|external_runtime`, lines 42–51), `events` (max 10,000). Per-event required fields (lines 94–98): `event_id`, `event_type`, `mission_id`, `sequence` (1–1,000,000), `actor_ref`, `timestamp`, `network_id`, `contract_digest`, `network_lock_digest`, `subject_revision`, `producer`. Optional per-event: `target_ref`, `capability_ref`, `delegation_ref`, `handoff_ref`, `source_zone_ref`, `target_zone_ref`, `policy_decision` (`allow|deny`), `approval_ref`, `approver` (`role` + `actor_type` enum `human, ai_tool, execution_surface, autonomous_agent, model, connector, generated_output`, lines 52–62), `share_categories`, `input_digest`, `output_digest`, `evidence_artifact` (`{path, sha256}`, lines 63–81), `signature_ref`, `depends_on`, `occurrence` (`{operation_id, occurrence_id, attempt 1–1,000,000}`, lines 82–91).

**Event-type enum (18 closed values, lines 101–110):** `agent_invoked`, `capability_requested`, `capability_allowed`, `capability_denied`, `delegation_requested`, `delegation_accepted`, `delegation_rejected`, `handoff_initiated`, `handoff_completed`, `trust_zone_crossed`, `data_shared`, `approval_requested`, `approval_granted`, `approval_rejected`, `tool_invoked`, `policy_violation`, `identity_revoked`, `runtime_failed`. ("Anything else requires a reviewed schema revision" — `docs/agentic-network/06_RUNTIME_EVIDENCE.md`.)

### 5.2 Validation — `nornyx/agentic_evidence.py` (1,103 lines)

`validate_runtime_events(document, composition, lock_payload, events_payload, *, events_root=None)` (line 182) returns a deterministic report (`nornyx.agentic_evidence_report.v1`, line 43). Bounded input: `MAX_EVENTS_BYTES = 8 MiB` (line 44); remote/device paths rejected (`load_runtime_events`, lines 101–120).

Checks (diagnostic codes with line references):

- JSON-Schema conformance → `AN_EVT_SCHEMA_INVALID` (line 164); malformed file → `AN_EVT_MALFORMED` (120–143).
- Schema/version vs. lock: envelope `schema`+`schema_version` must equal the lock's `runtime_events_schema` → `AN_EVT_SCHEMA_LOCK_MISMATCH` (line 226). The supplied lock is itself re-verified against the contract → `AN_EVT_LOCK_STALE` (line 236).
- Envelope + per-event binding: `network_id`/`subject_revision`/`contract_digest`/`network_lock_digest` each compared against expected values → `AN_EVT_NETWORK_MISMATCH`, `AN_EVT_REVISION_MISMATCH`, `AN_EVT_CONTRACT_MISMATCH`, `AN_EVT_LOCK_MISMATCH` (lines 360, 445–448).
- Per-type required fields (`_REQUIRED_FIELDS_BY_TYPE`, lines 49–66; e.g., `capability_allowed` needs `capability_ref` + `policy_decision`) → `AN_EVT_FIELD_REQUIRED` (463); decision-value contradiction (`capability_allowed` must say `allow`) → `AN_EVT_DECISION_CONTRADICTION` (477).
- Referential + temporal effectiveness at each event's timestamp: `AN_EVT_ACTOR_UNKNOWN/REVOKED/NOT_EFFECTIVE` (488–504), `AN_EVT_TARGET_UNKNOWN/REVOKED` (514–524), `AN_EVT_CAPABILITY_UNKNOWN` (533), `AN_EVT_DELEGATION_UNKNOWN` (542), `AN_EVT_HANDOFF_UNKNOWN` (551), `AN_EVT_ZONE_UNKNOWN` (561), `AN_EVT_APPROVAL_UNKNOWN` (570).
- Authority: `AN_EVT_CAPABILITY_NOT_HELD` (586 — allowance/tool use must be backed by held or delegated capability at that timestamp), `AN_EVT_DELEGATION_ACTOR_MISMATCH/EXPIRED/REVOKED` (599–616), `AN_EVT_HANDOFF_PARTY_MISMATCH` (630).
- Zone semantics: `AN_EVT_CROSSING_NOT_DECLARED` (645), `AN_EVT_CROSSING_UNGOVERNED` (661), `AN_EVT_CROSSING_APPROVAL_MISSING` (675), `AN_EVT_SENSITIVE_SHARING` (688), `AN_EVT_SHARE_NOT_ALLOWED` (707).
- Approvals: on `approval_granted` only, the approver must be `actor_type: human` → `AN_EVT_APPROVAL_NON_HUMAN` (730), and the role must be inside the composed module authority → `AN_EVT_APPROVAL_ROLE_INVALID` (739). Comment block at lines 715–723 records the 1.9.0 fix: on `approval_rejected` the `approver` is the *claimed* approver of a refused approval and "confers nothing", so grant rules do not apply to rejections.
- Evidence artifacts: `evidence_artifact.path` resolves relative to the events file's own directory and must stay inside it (loader-hardened, code_prefix `AN_EVT`); escapes/symlinks/missing → `AN_EVT_ARTIFACT_MISSING` (753, 771); hash mismatch → `AN_EVT_ARTIFACT_HASH_MISMATCH` (781).
- **Ordering per mission**: unique contiguous sequences from 1 → `AN_EVT_SEQUENCE_GAP` (800), `AN_EVT_DUPLICATE_SEQUENCE` (425), `AN_EVT_DUPLICATE_ID` (384); non-decreasing timestamps → `AN_EVT_ORDER_INVALID` (834, 860); `depends_on` targets must exist with lower sequence → `AN_EVT_DEPENDENCY_MISSING` (845); paired transitions: `AN_EVT_TOOL_WITHOUT_ALLOWANCE` (973), `AN_EVT_ACCEPTANCE_WITHOUT_REQUEST` (990), `AN_EVT_COMPLETION_WITHOUT_INITIATION` (1002), `AN_EVT_GRANT_WITHOUT_REQUEST` (1014).
- **Replay**: content fingerprint = sha256 of the event minus transport fields. In legacy modes transport = {`event_id`, `sequence`}; in explicit mode `timestamp` is also excluded, "A producer cannot evade exact replay detection merely by restamping a duplicate with a new timestamp" (code comment, lines 391–396). Duplicate fingerprint → `AN_EVT_REPLAY` (413). Per `docs/agentic-network/06_RUNTIME_EVIDENCE.md`: "Identical semantic evidence inside one attempt is replay; identical work in a new occurrence or retry attempt is not" (occurrence identity is part of the fingerprint).
- **Explicit occurrence rules**: one operation per occurrence id → `AN_EVT_OCCURRENCE_OPERATION_MISMATCH` (901); attempts ordered → `AN_EVT_ATTEMPT_ORDER_INVALID` (918); **retry after success forbidden** → `AN_EVT_ATTEMPT_AFTER_SUCCESS` (935; success terminals: `agent_invoked`, `tool_invoked`, `handoff_completed`, `trust_zone_crossed`, `data_shared`, `identity_revoked`; failure terminals: `capability_denied`, `delegation_rejected`, `approval_rejected`, `policy_violation`, `runtime_failed` — lines 68–86); one outcome per attempt → `AN_EVT_ATTEMPT_OUTCOME_CONTRADICTION` (1028, 1044); attempts contiguous from 1 → `AN_EVT_ATTEMPT_GAP` (1060).

Report fields (lines 1078–1103): `schema`, `status` (`pass`/`fail`), the four binding digests, `events_schema`/`events_schema_version`, `event_count`, `mission_count`, `counts_by_type`, sorted `diagnostics`, `limitations`, and a `safety` block (`models_called/tools_executed/external_connectors_used/network_used/producers_executed` all `false`).

**Proof boundary, verbatim** (`LIMITATIONS`, lines 88–92, embedded in every report): "Validated evidence proves conformance of supplied records only." / "Hash validity proves content binding, not event truth." / "Nornyx does not observe, operate, or monitor the runtime." And from `docs/agentic-network/06_RUNTIME_EVIDENCE.md`: "It does **not** solve distributed causality, cannot prove events across systems happened in the claimed order, and never claims complete causal truth. A runtime can omit or fabricate events; validation proves conformance of what was supplied against the exact contract revision, nothing more."

### 5.3 1.0 vs 1.1; identity model

- **1.0**: the published Nornyx 1.9.0 shape; mission-scoped transition/replay behavior; no `occurrence_mode` allowed.
- **1.1 legacy**: adds `occurrence_mode: legacy` to the envelope, retains old event shape and mission-scoped behavior; existing `EvidenceRecorder` constructor calls emit this with a 1.1 lock (`nornyx/agentic/authz.py:1272–1274`).
- **1.1 explicit**: `occurrence_mode: explicit`; every event carries `occurrence.operation_id` / `occurrence_id` / contiguous one-based `attempt`. Identity model (`docs/agentic-network/06_RUNTIME_EVIDENCE.md`): "a mission represents the complete governed run. An operation is the stable governed surface, an occurrence is one scheduled execution or loop/parallel visit, and an attempt is one retry within that occurrence. Authorization allowances and transition state are attempt-scoped. A successful occurrence cannot be retried; intentional repeated work uses a new occurrence."
- Introduced by ADR-0042 in 1.10.0 (`CHANGELOG.md` `[1.10.0]`). The stream's version must match the lock; "a legacy stream is never silently upgraded."

### 5.4 Recording and continuation (`nornyx/agentic/authz.py`)

`EvidenceRecorder` (lines 1214–1275): binds producer (`producer_type` restricted to the schema's three values, line 1249), refuses `observed_subject_revision != authorizer.subject_revision` (1251), takes the schema version from the authorizer's lock (1261–1271), stamps timestamps from `context.decision_at` ("no wall-clock", docstring line 1220). `for_occurrences(...)` (1277–1302) requires a 1.1 lock and sets explicit mode. `resume(...)` (1304–1396): validates and deeply detaches the complete prior stream via `validate_runtime_events`; producer, schema version, and occurrence mode must match; the resumed `decision_at` must not precede any prior event timestamp (1374–1381); restores per-mission sequence counters; returns cumulative evidence. "Differential chunks and multi-producer merging are not supported" (`docs/agentic-network/06_RUNTIME_EVIDENCE.md`). `max_recorded_attempt(...)` (line 1584) supports contiguity across resumes. Recorder hardening (canonicalization of str/int/float/dict/list/tuple subclasses, transactional multi-intent commit, internal lock) is described in CHANGELOG 1.9.0 under ADR-0041.

Status: IMPLEMENTED (tests: `tests/test_agentic_network_evidence.py` 18 tests / 703 lines; `tests/test_agentic_occurrence_semantics.py` 13 tests / 383 lines).

---

## 6. Authorization SPI (`nornyx.agentic`)

### 6.1 Version history

| SPI | Nornyx release | Content |
| --- | --- | --- |
| 1.0 | 1.8.0 (2026-07-23) | ADR-0039 M1: facade, frozen export surface, immutable lock-verified `Authorizer`, typed requests, `Decision`, code taxonomies, `EvidenceRecorder`; "cooperative **Tier 2** (ADR-0040) only" (`CHANGELOG.md` `[1.8.0]`). |
| 1.1 | 1.10.0 (2026-07-30) | ADR-0042 occurrence semantics: `RuntimeOccurrence`, `for_occurrences`, `max_recorded_attempt`, `resume`; runtime-events 1.1 (`CHANGELOG.md` `[1.10.0]`). |
| 1.2 | 1.11.0 (2026-08-01) | Additive `Authorizer.state` / `AuthorizerState` construction-state capability; "Authorization, approval, evidence, occurrence, replay, runtime-events, and language semantics are unchanged" (`CHANGELOG.md` `[1.11.0]`). Current: `SPI_VERSION = "1.2"` (`nornyx/agentic/authz.py:66`). |

### 6.2 Public API surface (`nornyx/agentic/__init__.py`, `__all__` lines 75–124)

Curated re-exports: `load_nyx`, `check_document`, `has_errors`, `GovernanceError`, `GovernanceRegistry`, `compose_document_governance`, `evaluate_document_governance`, `registry_for_contract`, `contract_digest`, `agentic_network_lock_digest`, `build_agentic_network_lock`, `write_agentic_network_lock`, `load_agentic_network_lock`, `verify_agentic_network_lock`, `render_agentic_network_artifacts`, `LOCK_SCHEMA_ID`, `LOCK_FORMAT_VERSION`, `GENERATION_FORMAT_VERSION`, `RUNTIME_EVENTS_SCHEMA_ID`, `RUNTIME_EVENTS_SCHEMA_VERSION`, `validate_runtime_events`, `load_runtime_events`.

Engine names: `SPI_VERSION`, `load_authorizer`, `Authorizer`, `AuthorizerState`, `EvaluationContext`, `AuthorizationRequest` (a union type, `authz.py:548–555`), `CapabilityRequest(identity_ref, capability_ref)`, `DelegationRequest(delegation_id)`, `HandoffRequest(handoff_id)`, `ApprovalRequest(identity_ref, approval)`, `ZoneCrossingRequest(identity_ref, source_zone, target_zone, approval=None)`, `DataShareRequest(identity_ref, target_ref, categories, source_zone, target_zone)`, `ApprovalAssertion(approval_ref, claimed_approver_ref, claimed_actor_type, role, granted, action_ref, subject_revision, issued_at=None, expires_at=None, evidence_refs=())` (`authz.py:495–506`), `DecisionBasis`, `DecisionEventIntent`, `Decision(effect, code, reason, basis, event_intents)` with `.allowed` property, `DecisionEffect`, `AuthorizerLoadCode`, `IdentityResolutionCode`, `DecisionCode`, `AuthorizerLoadError`, `IdentityResolutionError`, `RuntimeOccurrence`, `EvidenceRecorder`.

Key signatures:
- `load_authorizer(contract_path, lock_path, *, validation_as_of: str) -> Authorizer` (`authz.py:1166`). Fail-closed stage mapping (docstring lines 1169–1172): contract/parse/compose failures → `CONTRACT_INVALID`; no profile → `PROFILE_MISSING`; lock read/parse → `LOCK_INVALID`; lock verification → `LOCK_STALE`.
- `Authorizer.evaluate(request, *, context: EvaluationContext) -> Decision` (`authz.py:895`). `EvaluationContext(decision_at, observed_subject_revision)` (`authz.py:461–464`); `observed_subject_revision` is MANDATORY and must exactly equal the contract's `subject_revision`, else `DecisionCode.REVISION_MISMATCH` deny with a `policy_violation` intent (lines 903–906).
- `Authorizer.resolve_identity(framework: str, agent_key: str) -> str` (`authz.py:788`), raising `IdentityResolutionError` (`IDENTITY_UNKNOWN`/`IDENTITY_AMBIGUOUS`) — resolution errors are "not a policy decision" (line 453).

### 6.3 Decision outcomes

`DecisionEffect` has **three** members (`authz.py:399–402`): `ALLOW`, `DENY`, `APPROVAL_REQUIRED`. `APPROVAL_REQUIRED` is returned by `_zone_crossing` when the destination zone classification is external and no approval assertion accompanies the request (`authz.py:1110–1118`, code `CROSSING_APPROVAL_REQUIRED`, with an `approval_requested` intent). `DecisionCode` enumerates 23 members (`authz.py:417–440`), including the ADR-0039 minor additions `APPROVAL_ACTION_MISMATCH`, `APPROVAL_EVIDENCE_MISSING`, `PARTY_INEFFECTIVE`, `ZONE_CROSSING_DENIED`, `CROSSING_APPROVAL_REQUIRED`, `SENSITIVE_SHARING`, `SHARE_NOT_ALLOWED`, `REVISION_MISMATCH`, `REQUEST_MALFORMED`.

### 6.4 Request normalization and evaluate → record → execute

Requests are typed frozen dataclasses; `_shape_ok` rejects malformed shapes before evaluation (`authz.py:868`). The engine "authorizes *declared Nornyx concepts only*. It never parses raw shell commands, file paths, URLs, or tool arguments" (module docstring, lines 13–14). Decisions carry **decision-event intents only** (frozen `PHASE_INTENT` set of 10 decision-phase event types, lines 585–598); post-action facts are separate observations (`PHASE_OBSERVATION`, 8 types, lines 599–610). The evaluate-record-execute sequence is realized in the adapters and shim: "The legacy CrewAI task and LangGraph node guards now authorize once, execute the protected callable exactly once only on ALLOW, record success after the callable, and record `runtime_failed` when it raises" (`CHANGELOG.md` Unreleased); LangGraph guide: "Each native attempt is authorized and its decision recorded before user node code runs." Capability evaluation (`_capability`, `authz.py:937–962`) allows on held capability (basis `membership`) or valid delegation at `decision_at` (basis `delegation` with `delegation_ref` stamped into the `capability_allowed` intent), else denies `CAPABILITY_DENIED`. Temporal semantics: "It reads no wall-clock time. `validation_as_of` governs load-time document validation; `EvaluationContext.decision_at` governs *all* temporal action semantics" (docstring lines 17–19).

### 6.5 `AuthorizerState` (SPI 1.2)

`AuthorizerState` (`authz.py:641–711`): frozen slots dataclass; `document` (line 695) and `lock_payload` (707) return detached plain `dict`/`list` graphs; `composition` (701) returns a detached public `CompositionResult`; `contract_digest` and `network_lock_digest` are exposed. `Authorizer.state` (property, line 774) returns "the same `AuthorizerState` instance on every access" (`docs/agentic-network/12_AUTHORIZATION_SPI.md`). Deep-freeze machinery: `_FrozenMap`/`_FrozenList`/`_deep_freeze`/`_detach_plain` (`authz.py:108–395`). Docstring caveat (lines 652–654 + doc): validation/composition/lock-verification are guaranteed **only when the Authorizer came from `load_authorizer()`** — direct `Authorizer(document, composition, lock_payload)` construction performs none of those stages.

### 6.6 M2-D legacy compatibility shim

The M2-D shim is `integrations/nornyx_reference_adapters/governance_kernel.py` ("Deprecated compatibility facade over the supported Nornyx agentic SPI", module docstring lines 1–27). Facts:

- Merged at HEAD (`70d2b40` merges `feat/m2d-legacy-compatibility-shim`; commits `1eb67b1`, `789bf21`, `a63f8ca`, `19a4387`). Listed in `CHANGELOG.md` under **[Unreleased]**, not 1.11.0.
- It converts the ADR-0037 `GovernanceKernel` into a shim over public SPI 1.2 `Authorizer` + `EvidenceRecorder`: "One `Authorizer` is constructed … and its public `Authorizer.state` … is the only source for every legacy compatibility projection"; legacy `document`/`composition`/`lock_payload`/`network` surfaces are "**non-authoritative read-only projections**"; "The shim never reads Authorizer private attributes … never re-reads, re-composes, re-authorizes, or re-verifies policy" (docstring lines 8–19).
- **NOT packaged**: "It is unpackaged: it ships in neither the core wheel nor `nornyx-agentic-adapters`" (docstring lines 21–22); `pyproject.toml` `[tool.setuptools.packages.find] include = ["nornyx*"]` (line 48) excludes `integrations/`. It "requires Nornyx **1.11.0** (SPI **1.2**) or newer"; the published `nornyx-agentic-adapters` keeps its `nornyx>=1.10,<2` floor (`CHANGELOG.md` Unreleased).
- The shim translates SPI codes into 22 stable legacy `AN_ADAPTER_*` codes (grep across `integrations/nornyx_reference_adapters/*.py`): `AN_ADAPTER_APPROVAL_NON_HUMAN`, `AN_ADAPTER_APPROVAL_NOT_GRANTED`, `AN_ADAPTER_APPROVAL_ROLE_INVALID`, `AN_ADAPTER_CAPABILITY_DENIED`, `AN_ADAPTER_CAPABILITY_UNKNOWN`, `AN_ADAPTER_CONTRACT_INVALID`, `AN_ADAPTER_CROSSING_APPROVAL_REQUIRED`, `AN_ADAPTER_DELEGATION_INACTIVE`, `AN_ADAPTER_DELEGATION_UNKNOWN`, `AN_ADAPTER_EVIDENCE_INVALID`, `AN_ADAPTER_FRAMEWORK_MISMATCH`, `AN_ADAPTER_HANDOFF_AUTHORITY`, `AN_ADAPTER_HANDOFF_UNKNOWN`, `AN_ADAPTER_HOOK_MISSING`, `AN_ADAPTER_IDENTITY_UNKNOWN`, `AN_ADAPTER_LOCK_INVALID`, `AN_ADAPTER_LOCK_STALE`, `AN_ADAPTER_PROFILE_MISSING`, `AN_ADAPTER_REQUEST_MALFORMED`, `AN_ADAPTER_SENSITIVE_SHARING`, `AN_ADAPTER_SHARE_NOT_ALLOWED`, `AN_ADAPTER_ZONE_CROSSING_DENIED`.

Status: core SPI IMPLEMENTED (tests `tests/test_agentic_authz.py` 114 tests / 2,515 lines; `tests/test_agentic_authorizer_state.py` 17 tests / 834 lines; `tests/test_agentic_facade_surface.py` 5 tests). Shim IMPLEMENTED but unpackaged repository code (tests `tests/test_agentic_integrations.py` 22 tests / 708 lines; `tests/test_agentic_crewai_native.py` 11 tests).

---

## 7. Approval semantics in the agentic profile

**Declared** (example, `examples/agentic_network_support/support_network.nyx:104–118`): the `agentic_network_authority` approval declares `required_roles: [network_governance_owner]`, `eligible_roles: [network_governance_owner, security_reviewer, architecture_reviewer]`, `denied_actor_types: [ai_tool, execution_surface, autonomous_agent, model, connector, generated_output]`, `required_evidence`, `required_for: [approve_agentic_network_contract, external_share, handoff]`, `timing: before_action`, `accountable_authority`, `revision_binding: {kind: git, revision: git:…, exact: true}`, `invalidation_conditions: [revision_change, identity_change, capability_change, trust_zone_change, membership_change]`, `expires_at`.

**Checked in three layers:**

1. *Static* (`nornyx/governance/agentic_network.py`, `AGENTIC_APPROVAL_ID = "agentic_network_authority"` line 14): declaration presence and module-role consistency (`AN_APPROVAL_DECLARATION_MISSING` 542, `AN_APPROVAL_DECLARED_ROLE_UNAUTHORIZED` 568, `AN_APPROVAL_MODULE_ROLE_OMITTED` 581, `AN_APPROVAL_ACCOUNTABLE_AUTHORITY_MISMATCH` 592, `AN_APPROVAL_DECLARATION_MODULE_CONTRADICTION` 604, `AN_APPROVAL_ACTION_MISSING` 617); revision binding (`AN_REVISION_MISMATCH` 640); evidence-record producer must be human (`AN_APPROVAL_HUMAN_REQUIRED` 653) with role inside composed authority (`AN_APPROVAL_PRODUCER_OUTSIDE_MODULE_AUTHORITY` 663, `AN_APPROVAL_ROLE_INVALID` 671); record status/revocation/expiry (`AN_APPROVAL_RECORD_INVALID` 680, `AN_APPROVAL_REVOKED` 688, `AN_APPROVAL_INTERVAL_INVALID` 702, `AN_APPROVAL_EXPIRY_EXCESSIVE` 711/749, `AN_APPROVAL_NOT_YET_VALID` 727, `AN_APPROVAL_EXPIRED` 737, `AN_VALIDATION_TIME_REQUIRED` 719). Identity invariant: `AN_NON_HUMAN_APPROVAL_INVALID` (1036–1042).
2. *Engine* (`Authorizer._approval`, `nornyx/agentic/authz.py:1012–1072`), in order: declared requirement exists (`REQUEST_MALFORMED`); **universal revision binding** — the assertion's `subject_revision` must equal the contract revision, then also the declared `revision_binding.revision` (`APPROVAL_REVISION_MISMATCH`, 1030–1035); action scope (`APPROVAL_ACTION_MISMATCH`, 1038); **non-human rejection** — `claimed_actor_type != "human"` or in `denied_actor_types` → `APPROVAL_NON_HUMAN` with message "AI systems, tools, models, and execution surfaces cannot approve." (1040–1042); role must be in `eligible_roles ∪ required_roles` (`APPROVAL_ROLE_INVALID`, 1043–1045); required evidence refs subset (`APPROVAL_EVIDENCE_MISSING`, 1046–1048); temporal validity at `decision_at` — earliest of assertion expiry, absolute expiry, `issued_at + expires_after`; future-issued fails closed (`APPROVAL_STALE`, 1053–1063); `granted` must be true (`APPROVAL_NOT_GRANTED`, 1064).
3. *Evidence* (`nornyx/agentic_evidence.py:724–745`): `approval_granted` requires human `actor_type` (`AN_EVT_APPROVAL_NON_HUMAN`) and a composed-module role (`AN_EVT_APPROVAL_ROLE_INVALID`); rules deliberately not applied to `approval_rejected`.

Adapters add `AN_ADAPTER_APPROVAL_NON_HUMAN` at the enforcement hook ("The record is supplied externally — the adapter never grants approval", `docs/agentic-network/02_CREWAI_GUIDE.md`).

---

## 8. Evidence-validate CLI

`nornyx agentic-network evidence-validate FILE --events EVENTS.json [--lock LOCK] [--as-of TS] [--out REPORT] [--strict] [--json]` (`nornyx/cli.py:1620–1631`). `--events` is required; `--lock` defaults to `nornyx.agentic_network.lock`. Handler (`cmd_agentic_network_evidence_validate`, lines 845–885): validates the contract (with `--as-of`), loads the lock and events, runs `validate_runtime_events`, optionally writes a deterministic sorted-key report to `--out`, prints `{status, event_count, mission_count, diagnostic_count}`, and **exits nonzero only when `--strict` is passed and status ≠ pass** (line 883). Exit 2 on parse errors; exit 1 on governance errors.

---

## 9. Tests (enumeration)

All under `/home/user/nornyx/tests/` (counts = `def test` occurrences):

| File | Tests | Lines | Covers |
| --- | --- | --- | --- |
| `test_agentic_authz.py` | 114 | 2,515 | Authorizer load, all six request types, decisions, approval semantics, recorder |
| `test_agentic_authorizer_state.py` | 17 | 834 | SPI 1.2 `AuthorizerState` detachment/immutability |
| `test_agentic_network_artifacts.py` | 25 | 558 | Generation determinism, forbidden fields, lock build/verify |
| `test_agentic_network_governance.py` | 63 | 1,374 | `agentic_network_foundation.v1` static checks |
| `test_agentic_network_delegation.py` | 35 | 937 | `agentic_network_delegation.v1` (delegations/handoffs/relations) |
| `test_agentic_network_evidence.py` | 18 | 703 | Runtime-event validation, binding, ordering |
| `test_agentic_occurrence_semantics.py` | 13 | 383 | ADR-0042 occurrence/retry/replay/resume corpus |
| `test_agentic_support_example.py` | 15 | 387 | AN-006 support example end-to-end |
| `test_agentic_facade_surface.py` | 5 | 102 | Frozen `nornyx.agentic` export surface |
| `test_agentic_integrations.py` | 22 | 708 | Reference adapters / M2-D shim |
| `test_agentic_crewai_native.py` | 11 | 598 | Framework-native CrewAI path |
| `test_governance_audit_path_and_lock_security.py` | 49 | 1,523 | Path hardening + lock security |

Total ≈ 387 test functions / ≈ 10,600 lines in these twelve files.

---

## 10. Security boundaries, positioning, CI (docs 08/10/11)

`docs/agentic-network/08_SECURITY_BOUNDARIES.md` — key claims, verbatim:

> "AI systems, tools, models, agents, connectors, and execution surfaces cannot approve. High-impact approval remains human, revision-bound, expiring, invalidatable, and revocable."
> "`secrets`, `credentials`, `tokens`, and `private_memory` are never shareable across prohibited boundaries — in zones, protocol targets, delegations, handoffs, relations, adapter calls, and runtime events."
> "Everything fails closed on malformed, unknown, ambiguous, contradictory, stale, expired, revoked, replayed, or forged input."

Threat table maps 12 threat rows to mitigations (closed schemas + `AN_ARTIFACT_FORBIDDEN_*`, `AN_NORMALIZATION_COLLISION` NFKC casefold, path hardening, content-addressed revisions, closed ordering model, attempt-scoped state, `AN_HANDOFF_AUTHORITY_ESCALATION`, producer/actor-type checks, `AN_ADAPTER_HOOK_MISSING`, per-event binding).

Residual risks, verbatim:

> "Evidence is supplied, not observed: omission and fabrication are outside Nornyx's proof surface."
> "A cooperative producer can falsely claim a new occurrence; occurrence validation proves structural consistency, not independent execution truth."
> "Adapter enforcement is cooperative; bypassing the adapter bypasses the hook."
> "Structural signature references are not cryptographic verification; no signature verification is claimed."
> "The lock binds bytes, not producers; repository review remains the control for unauthorized regeneration."

`10_BEFORE_AFTER_AND_POSITIONING.md`: without-Nornyx fragmentation narrative ("renaming one agent silently desynchronizes five files"); with-Nornyx list (one contract, 10 deterministic artifacts, shared identity semantics via `framework_bindings`, revision-bound approval, one evidence stream, `lock-check` drift detection, stable diagnostics, one audit package); measured table (see §1). `11_REFERENCE_CI.md`: 14-step credential-free CI with audit-package assembly and a GitHub Actions snippet.

---

## 11. Verbatim excerpts for the textbook

All from `examples/agentic_network_support/support_network.nyx` unless noted.

**Identity declaration** (lines 297–312):
```yaml
- id: identity.escalation_agent
  role_ref: EscalationAgent
  identity_class: local_agent
  namespace: support.escalation
  subject: escalation_agent
  framework_bindings:
    - {framework: contract_fixture, agent_key: escalation_agent}
    - {framework: crewai, agent_key: escalation_agent}
    - {framework: langgraph, agent_key: escalation_agent}
  capability_refs: [read_sanitized_request, escalate_high_value_refund, request_human_approval]
  status: active
  valid_from: "2026-01-01T00:00:00Z"
  expires_at: "2026-12-01T00:00:00Z"
  revocation_refs: []
  authority: non_human
  can_approve: false
```

**Capability with gate and approval requirement** (lines 211–219):
```yaml
- name: escalate_high_value_refund
  actions: [escalate_refund]
  risk: high
  scope_type: context
  scope_refs: [SupportContext]
  delegable: false
  required_gate_refs: [gate.escalation_review]
  required_approval_refs: [agentic_network_authority]
  required_evidence_refs: [agentic_network_contract_review]
```

**Trust zone with never_share** (lines 326–332):
```yaml
- id: zone.customer_channel
  classification: external_contract_only
  allowed_transition_targets: []
  share_allowlist: [customer_response, evidence_digest]
  never_share: [secrets, credentials, tokens, private_memory]
  ingress_gate_refs: [gate.customer_response]
  egress_gate_refs: []
```

**Delegation** (lines 405–425):
```yaml
delegations:
  - id: delegation.refund_proposal
    delegator_ref: identity.support_coordinator
    delegate_ref: identity.refund_agent
    capability_ref: propose_refund_under_limit
    purpose: Delegate bounded refund proposals to the refund specialist.
    actions: [propose_refund]
    scope_refs: [SupportContext]
    status: active
    valid_from: "2026-01-01T00:00:00Z"
    expires_at: "2026-12-01T00:00:00Z"
    max_depth: 1
    current_depth: 0
    onward_delegation: denied
    source_zone_ref: zone.support_internal
    target_zone_ref: zone.support_internal
    required_gate_refs: [gate.refund_review]
    required_policy_refs: [SupportGovernance]
    required_approval_refs: []
    required_evidence_refs: [agentic_network_contract_review]
    revocation_refs: []
```

**Handoff** (lines 426–444):
```yaml
handoffs:
  - id: handoff.high_value_escalation
    from_identity_ref: identity.support_coordinator
    to_identity_ref: identity.escalation_agent
    purpose: Transfer responsibility for a high-value refund case.
    mission_ref: GOAL-SUPPORT-001
    from_zone_ref: zone.support_internal
    to_zone_ref: zone.support_internal
    required_capability_refs: [escalate_high_value_refund]
    delegation_refs: []
    shared_context: [sanitized_request, classification]
    never_share: [secrets, credentials, tokens, private_memory]
    status: initiated
    valid_from: "2026-01-01T00:00:00Z"
    expires_at: "2026-12-01T00:00:00Z"
    required_gate_refs: [gate.escalation_review]
    required_approval_refs: [agentic_network_authority]
    required_evidence_refs: [agentic_network_contract_review]
    revocation_refs: []
```

**Runtime event, 1.1 explicit mode** — produced live during this audit from `examples/agentic_network.nyx` via `EvidenceRecorder.for_occurrences(...)` + `record_occurrence_decision(...)` (validated `pass`); envelope then the `capability_allowed` event:
```json
{
  "schema": "nornyx.agentic_runtime_events.v1",
  "schema_version": "1.1",
  "occurrence_mode": "explicit",
  "network_id": "network.research",
  "producer": {"type": "synthetic_harness", "id": "factpack-demo", "version": "1.0"}
}
```
```json
{
  "event_id": "GOAL-001-0002",
  "event_type": "capability_allowed",
  "mission_id": "GOAL-001",
  "sequence": 2,
  "timestamp": "2026-07-17T10:00:00Z",
  "network_id": "network.research",
  "contract_digest": "sha256:85a5617465afb0fc221f24cc57e7ae2e7d1183224806eb41c51a3d6ea27902a8",
  "network_lock_digest": "sha256:0ddcafe9060163f8b24558ba8a5198f80188ab535e93f23bef3340027cbd7aeb",
  "subject_revision": "git:0123456789abcdef0123456789abcdef01234567",
  "producer": {"type": "synthetic_harness", "id": "factpack-demo", "version": "1.0"},
  "actor_ref": "identity.researcher.local",
  "capability_ref": "read_governed_context",
  "policy_decision": "allow",
  "occurrence": {"operation_id": "node.read", "occurrence_id": "task.1", "attempt": 1}
}
```

**Lock excerpt** — built live with `nornyx agentic-network lock` on the support contract (`--as-of 2026-07-17T00:00:00Z`); abridged:
```json
{
  "schema": "nornyx.agentic_network_lock.v1",
  "lock_format_version": "1.0",
  "generation_format_version": "1.0",
  "network_id": "network.governed_support",
  "subject_revision": "git:feedfacefeedfacefeedfacefeedfacefeedface",
  "source_contract_digest": "sha256:3cdf632c08684efa2382a047b474b8f56ea4a83c5ed2f86c05918c29d0ac8eda",
  "profile": {"id": "nornyx.builtin.agentic_network", "name": "agentic_network",
              "version": "0.1.0", "content_hash": "sha256:94ab4650c2a2…"},
  "modules": [{"id": "nornyx.builtin.module.agentic_network_governance",
               "name": "agentic_network_governance", "version": "0.2.0",
               "content_hash": "sha256:bd2642620c67…"}, "…"],
  "structural_checks": ["agentic_network_delegation.v1", "agentic_network_foundation.v1"],
  "runtime_events_schema": {"id": "nornyx.agentic_runtime_events.v1", "version": "1.1"},
  "protocol_declarations": [{"id": "protocol.customer_response", "protocol": "a2a",
                             "version_label": "declared-by-project",
                             "execution_mode": "contract_only"}],
  "records": {"agent_identities": "…4 digests…", "capabilities": "…8…",
              "trust_zones": "…2…", "memberships": "…4…", "network_gates": "…3…",
              "protocol_targets": "…1…", "delegations": "…1…", "handoffs": "…1…",
              "relations": "…4…", "revocations": []},
  "approval_requirements": ["agentic_network_authority", "governance_authority"],
  "evidence_requirements": ["agentic_network_contract_review", "approval_record", "…"],
  "artifacts": [{"path": "a2a_declaration.json", "sha256": "d55d31907279…"},
                {"path": "agentic_generation_manifest.json", "sha256": "7b21b36862a7…"},
                "…8 more…"]
}
```

**run_demo.py** (`examples/agentic_network_support/run_demo.py`, 480 lines): docstring — "Runs the same Nornyx contract through both reference adapters (CrewAI-shaped and LangGraph) with a deterministic local harness: fake model, inert tools, temporary local files only, no API keys, no sockets, no external writes … Everything here is fake data." It generates artifacts + lock, runs allowed/blocked scenario matrices (`_run_crewai_scenario` line 153, `_run_langgraph_scenario` line 292, `_static_rejections` line 82), writes `{framework}_events.json`, per-framework `_evidence_report.json`, `eval_report.json`, and `demo_summary.json` (lines 414–470), asserting each deliberately blocked scenario raises `GovernanceViolation` with the expected code (`_blocked`, lines 73–79).

---

## 12. Traceability rows

| # | Claim | Evidence path | Status |
| --- | --- | --- | --- |
| 1 | `agentic_network` block schema is closed; requires trust_zones/memberships/protocol_targets/network_gates/revocations | `schemas/agentic_network_v1.schema.json:8–17,63` | IMPLEMENTED |
| 2 | Subject revisions must be `git:`-hex or `sha256:` (immutable only) | `schemas/agentic_network_v1.schema.json:77–82`; `nornyx/agentic/authz.py:70`; `nornyx/agentic_artifacts.py:705–713` | IMPLEMENTED |
| 3 | Trust zones require non-empty `never_share`; 7 classifications | `schemas/agentic_network_v1.schema.json:102–133` | IMPLEMENTED |
| 4 | Protocol targets: `mcp`/`a2a` only; `execution_mode` const `contract_only`; `live_connector_execution` const `false` | `schemas/agentic_network_v1.schema.json:179–182` | IMPLEMENTED |
| 5 | Identities: `authority` const `non_human`, `can_approve` const `false` | `schemas/agent_identities_v1.schema.json:74–75` | IMPLEMENTED |
| 6 | Non-human/can_approve invariant enforced in code | `nornyx/governance/agentic_network.py:1036–1042` (`AN_NON_HUMAN_APPROVAL_INVALID`) | IMPLEMENTED |
| 7 | Sensitive categories = {secrets, credentials, tokens, private_memory}, single source | `nornyx/governance/agentic_network.py:12`; consumed in `nornyx/agentic/authz.py:59`, `nornyx/agentic_evidence.py:30` | IMPLEMENTED |
| 8 | Sensitive sharing denied at engine, static-check, evidence, adapter layers | `authz.py:1152–1155` (`SENSITIVE_SHARING`); `agentic_delegation.py:630,1128`; `agentic_evidence.py:688`; adapters `AN_ADAPTER_SENSITIVE_SHARING` | IMPLEMENTED |
| 9 | Forbidden artifact fields (endpoint/credential/command/URL/IP) fail generation closed | `nornyx/agentic_artifacts.py:78–121,265–296` (`AN_ARTIFACT_FORBIDDEN_FIELD/_VALUE`) | IMPLEMENTED |
| 10 | `generate` emits exactly 10 artifacts (9 declarations + generation manifest) | `nornyx/agentic_artifacts.py:66–76,40`; live run output `"artifact_count": 10` | IMPLEMENTED (verified live) |
| 11 | Generation is byte-deterministic | `docs/agentic-network/01_TUTORIAL.md`; verified live via `diff -r` of two runs; drift gate in `scripts/agentic_network_ci.py` step 5 | IMPLEMENTED (verified live) |
| 12 | `--as-of` sets validation instant; defaults to now; artifacts are timestamp-free | `nornyx/cli.py:728,1594` | IMPLEMENTED |
| 13 | Lock format 1.0; binds digest/revision/packs/schemas/checks/runtime-events version/record digests/artifact hashes | `schemas/agentic_network_lock_v1.schema.json:27–28,7–24`; `nornyx/agentic_artifacts.py:685–774` | IMPLEMENTED |
| 14 | Lock-check codes incl. `AN_LOCK_SOURCE_STALE`, `AN_LOCK_ARTIFACT_UNEXPECTED` | `nornyx/agentic_artifacts.py:916–1028` | IMPLEMENTED |
| 15 | Lock does not prove producer authenticity or runtime truth | `docs/agentic-network/07_NETWORK_LOCK.md` ("What the lock is not"); `schemas/agentic_network_lock_v1.schema.json:5` | GUIDANCE (stated limitation) |
| 16 | Runtime-events: 3 envelopes (1.0 / 1.1 legacy / 1.1 explicit); explicit requires occurrence, legacy forbids it | `schemas/agentic_runtime_events_v1.schema.json:6–10,148–156,157–194` | IMPLEMENTED |
| 17 | Closed 18-event-type enum | `schemas/agentic_runtime_events_v1.schema.json:101–110`; mirrored `nornyx/agentic_artifacts.py:46–64` | IMPLEMENTED |
| 18 | Every event binds network/contract/lock/revision; mismatch codes | `nornyx/agentic_evidence.py:360,445–448`; schema lines 94–98 | IMPLEMENTED |
| 19 | Ordering: contiguous sequences, timestamps, dependencies, paired transitions | `nornyx/agentic_evidence.py:800–1014` | IMPLEMENTED |
| 20 | Replay fingerprint excludes event_id/sequence (+timestamp in explicit mode) | `nornyx/agentic_evidence.py:391–419` | IMPLEMENTED |
| 21 | Retry-after-success forbidden; attempts contiguous from 1 | `nornyx/agentic_evidence.py:935,1060` (`AN_EVT_ATTEMPT_AFTER_SUCCESS`, `AN_EVT_ATTEMPT_GAP`) | IMPLEMENTED |
| 22 | Evidence-artifact paths contained under events dir; hash-bound | `nornyx/agentic_evidence.py:746–781`; `docs/agentic-network/06_RUNTIME_EVIDENCE.md` | IMPLEMENTED |
| 23 | Proof boundary: supplied-record conformance only, not runtime truth | `nornyx/agentic_evidence.py:88–92` (LIMITATIONS, in every report); `docs/agentic-network/06_RUNTIME_EVIDENCE.md` | IMPLEMENTED + GUIDANCE |
| 24 | Report includes safety block (no models/tools/network used) | `nornyx/agentic_evidence.py:1096–1102` | IMPLEMENTED |
| 25 | SPI history 1.0 (1.8.0) → 1.1 (1.10.0) → 1.2 (1.11.0); current `SPI_VERSION = "1.2"` | `CHANGELOG.md` [1.8.0]/[1.10.0]/[1.11.0]; `nornyx/agentic/authz.py:66` | IMPLEMENTED |
| 26 | `DecisionEffect` = ALLOW / DENY / APPROVAL_REQUIRED | `nornyx/agentic/authz.py:399–402`; APPROVAL_REQUIRED produced at `authz.py:1110–1118` | IMPLEMENTED |
| 27 | `load_authorizer` validates, composes, lock-verifies; 4-code fail-closed load taxonomy | `nornyx/agentic/authz.py:1166–1210,405–410` | IMPLEMENTED |
| 28 | `AuthorizerState` detached frozen views; bare `Authorizer(...)` gives no assurance | `nornyx/agentic/authz.py:641–711,774`; `docs/agentic-network/12_AUTHORIZATION_SPI.md` | IMPLEMENTED |
| 29 | Approval engine order: revision → binding → action → non-human → role → evidence → expiry → granted | `nornyx/agentic/authz.py:1012–1072` | IMPLEMENTED |
| 30 | Non-human approval rejected at engine (`APPROVAL_NON_HUMAN`), evidence (`AN_EVT_APPROVAL_NON_HUMAN` on grants only), static (`AN_APPROVAL_HUMAN_REQUIRED`), adapter (`AN_ADAPTER_APPROVAL_NON_HUMAN`) | `authz.py:1040–1042`; `agentic_evidence.py:724–745`; `agentic_network.py:646–657`; shim | IMPLEMENTED |
| 31 | M2-D shim = deprecated `GovernanceKernel` over SPI 1.2; unpackaged (not in core wheel or adapters wheel) | `integrations/nornyx_reference_adapters/governance_kernel.py:1–27`; `pyproject.toml:48`; `CHANGELOG.md` [Unreleased] | IMPLEMENTED (unpackaged, unreleased) |
| 32 | LangGraph adapter is a separate distribution `nornyx-agentic-adapters`, LangGraph `==1.2.2` pin | `docs/agentic-network/03_LANGGRAPH_GUIDE.md`; `adapters/nornyx-agentic-adapters/` | IMPLEMENTED (separate package) |
| 33 | Evidence-validate flags: `--events` (required), `--lock`, `--as-of`, `--out`, `--strict`, `--json`; strict-only nonzero exit | `nornyx/cli.py:1620–1631,883` | IMPLEMENTED |
| 34 | ~387 tests across 12 agentic/lock/evidence test files | `tests/test_agentic_*.py`, `tests/test_governance_audit_path_and_lock_security.py` (see §9) | IMPLEMENTED |
| 35 | Nornyx is not a runtime/orchestrator/identity provider/secrets manager/MCP/A2A runtime | `docs/agentic-network/00_OVERVIEW.md`; `support_network.nyx:10–20` (`non_goals`) | NON-GOAL |
| 36 | Support example: 4 identities, 8 capabilities, 2 zones, 3 gates, 1 protocol target, 1 delegation, 1 handoff, 4 relations | `examples/agentic_network_support/support_network.nyx`; live lock `records` counts | IMPLEMENTED (verified live) |

---

## 13. Unverified or ambiguous

1. **Measured demo numbers not re-run.** The table in `docs/agentic-network/10_BEFORE_AFTER_AND_POSITIONING.md` (10 allowed / 11 blocked scenarios, 34 + 14 events, 4/4 thresholds) was not reproduced in this audit — `run_demo.py` and `scripts/agentic_network_ci.py` were read but not executed. Generation, locking, and explicit-mode recording/validation were executed and verified.
2. **`expires_after: P7D` wording.** `docs/agentic-network/04_EXTERNAL_EVAL_EVIDENCE.md` says the support approval "expires (`expires_after: P7D`)", but `support_network.nyx:118` declares an absolute `expires_at: "2026-07-24T00:00:00Z"` (7 days after the evidence `generated_at`). The engine supports both mechanisms (`authz.py:1054–1062`); the doc's field name does not literally match the example.
3. **Duplicated constant.** `EXTERNAL_ZONE_CLASSIFICATIONS` is defined both in `nornyx/governance/agentic_network.py:13` and re-declared literally in `nornyx/agentic_evidence.py:45` (identical values). Cosmetic duplication, not a behavioral divergence today.
4. **M2-D shim release status.** The shim is merged at HEAD but sits under `CHANGELOG.md` `[Unreleased]`; package version 1.11.0 predates it. Any textbook statement should say "merged, unpackaged repository code, post-1.11.0 unreleased."
5. **`nornyx-agentic-adapters` wheel not audited.** `adapters/nornyx-agentic-adapters/` exists in-repo; its published wheel contents and version (0.2.0 per CHANGELOG prose) were not independently verified here.
6. **Doc measured claim "0 / 0 network attempts (observed by tests)"** relies on the repository's own safety tests; not independently instrumented in this audit.
7. **Tutorial says "Ten canonical, timestamp-free JSON declarations"** while `ARTIFACT_NAMES` lists 9 declarations; the tenth file is `agentic_generation_manifest.json` (a manifest, not a declaration). Count of files is 10; count of *declarations* is arguably 9.
