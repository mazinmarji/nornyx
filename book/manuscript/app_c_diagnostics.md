---
appendix: C
title: "Appendix C — Diagnostic Code Guide"
---

# Appendix C — Diagnostic Code Guide

Diagnostic codes are the stable public vocabulary of a governance toolchain. A pipeline that keys on
message text breaks on the next wording change; a pipeline that keys on codes does not. This
appendix catalogues the code families present in Nornyx at the audited revision `70d2b40ad792`.

**Coverage statement.** This is a *representative* catalogue, not an exhaustive one. Some families
are large — the agentic-network static checks alone contribute more than one hundred and fifty
codes — and reproducing all of them would produce a listing rather than a guide. Every code printed
below was extracted from the repository by direct search or observed in a live command run during
preparation; where a family is sampled rather than complete, the section says so and names the file
to search. No code here is invented.

## C.1 How codes are shaped

Codes are upper-snake-case strings. **There is no numeric code scheme in the core** — nothing of the
form `NYX001` exists. Core diagnostics carry five fields: `level` (`error` or `warning`), `code`,
`message`, `path`, and `hint`.

Ten namespaces are documented as reserved: `PACK_*`, `RULE_*`, `GOVERNANCE_*`, `APPROVAL_*`,
`EVIDENCE_*`, `SOD_*`, `EXCEPTION_*`, `CHANGE_*`, `ARCH_*`, and `AN_*`. The core checker predates
that scheme and uses unprefixed structural names such as `MISSING_PROJECT_NAME`.

Some codes are *generated*, so searching the source for the exact string fails:
`MISSING_<SINGULAR>_NAME` from the singular of a list block (`MISSING_POLICY_NAME`,
`MISSING_HARNESS_NAME`, `MISSING_TRACE_NAME`, `MISSING_EVAL_NAME`); `MISSING_GOAL_<FIELD>` and
`INVALID_GOAL_<FIELD>` from a goal field name; and the delegation and handoff gate codes, composed
from a prefix constant to give `AN_DELEGATION_GATE_REQUIRED`, `AN_HANDOFF_APPROVAL_REQUIRED`,
`AN_DELEGATION_EVIDENCE_REQUIRED`, `AN_HANDOFF_EGRESS_GATE_MISSING`, and their siblings.

The level matters as much as the code: `has_errors` gates the exit code, warnings never do.

## C.2 Checker codes — contract structure and references

Raised by `nornyx check` and any command that validates a document. Error level and exit 1 unless
noted.

| Code | Raised when | Fail-closed behaviour | Where to look |
|---|---|---|---|
| `MISSING_TOP_LEVEL_BLOCK` | `nornyx:` or `project:` absent | error, exit 1 | The document head |
| `MISSING_PROJECT_NAME` / `INVALID_PROJECT` | `project.name` empty, or `project` is not a mapping | error, exit 1 | `project` |
| `UNKNOWN_VERSION` | `nornyx:` is not `0.1` or `0.2` | **warning** | The version marker |
| `UNKNOWN_TOP_LEVEL_BLOCK` | A top-level key is neither core nor a recognised extension | **warning**, suppressed for module-contributed blocks | The block name; consider whether a profile should be declared |
| `INVALID_BLOCK_TYPE` / `INVALID_MAPPING_BLOCK` / `INVALID_BLOCK_ENTRY` | A list block is not a list, a mapping block not a mapping, or an entry not a mapping | error, exit 1 | The block or entry index |
| `MISSING_<SINGULAR>_NAME` | A named list entry has no `name` | error, exit 1 | The entry index |
| `CONTEXT_WITHOUT_INCLUDE` / `HARNESS_WITHOUT_FLOW` / `INVALID_FLOW_STEP` | A context declares no `include`, a harness no `flow`, or a flow step is malformed | error, exit 1 | The entry |
| `INVALID_AGENT` / `INVALID_HARNESS` / `INVALID_EVIDENCE_REQUIRED` | Entry or evidence shape is wrong | error, exit 1 | The entry |
| `UNKNOWN_SKILL_REFERENCE` / `UNKNOWN_POLICY_REFERENCE` / `UNKNOWN_CONTEXT_REFERENCE` / `UNKNOWN_AGENT_REFERENCE` / `UNKNOWN_EVAL_REFERENCE` | A cross-block reference does not resolve | error, exit 1 | The referencing field |
| `MISSING_GOAL_ID` / `_PHASE` / `_OUTCOME` / `_APPROVAL` / `_EVIDENCE`, `MISSING_GOAL_<FIELD>`, `INVALID_GOAL_<FIELD>`, `INVALID_GOAL`, `GOAL_WITHOUT_VALIDATION` | A goal omits a required field, supplies a wrong shape, or declares no validation | error, exit 1 | `goals[i]` |

**Table C.1 — Core structural and reference codes.** All in `nornyx/checker.py`.

### Graph and contract codes

| Code | Raised when | Fail-closed behaviour | Where to look |
|---|---|---|---|
| `INVALID_GRAPH_BLOCK` / `INVALID_GRAPH_NODES` / `INVALID_GRAPH_EDGES` | The graph block or its collections are malformed | error, exit 1 | `graph` |
| `MISSING_GRAPH_NODE_ID` / `MISSING_GRAPH_NODE_KIND` / `DUPLICATE_GRAPH_NODE_ID` / `DUPLICATE_GRAPH_EDGE` / `GRAPH_SELF_EDGE` | A node omits `id` or `kind`, or a node id or edge repeats, or an edge is a self-loop | error, exit 1 | `graph.nodes`, `graph.edges` |
| `UNKNOWN_GRAPH_NODE_REFERENCE` / `UNKNOWN_GRAPH_REF_REFERENCE` | An edge endpoint is not a declared node, or a node's `ref` does not resolve in the block matching its kind | error, exit 1 | The node or edge |
| `GRAPH_EDGE_WITHOUT_RELATION` | An edge declares no relation verb | error, exit 1 | `graph.edges[i]` |
| `UNKNOWN_GRAPH_RELATION` | The verb is outside the twenty-three typed relations | warning | `graph.edges[i].relation` |
| `INVALID_GRAPH_RELATION_PAIR` | A known relation is used between disallowed source and target kinds | error, exit 1 | `nornyx/checker.py:144-168` |
| `GRAPH_EVIDENCE_NODE_WITHOUT_REF` | An evidence node carries no `ref` | warning | `graph.nodes[i]` |
| `INVALID_CONTRACTS_BLOCK` / `INVALID_CONTRACT_ENTRY` / `MISSING_CONTRACT_NAME` | The contracts block or an entry is malformed | error, exit 1 | `contracts` |
| `UNKNOWN_CONTRACT_GRAPH_REFERENCE` / `_APPROVAL_REFERENCE` / `_BUDGET_REFERENCE` | A contract references an undeclared node, approval, or budget | error, exit 1 | `contracts[i]` |
| `CONTRACT_APPROVAL_NOT_IN_GRAPH` / `CONTRACT_BUDGET_NOT_IN_GRAPH` / `CONTRACT_WITHOUT_EVIDENCE_NODE` | A declared control is not represented as a graph node | warning — an auditability signal | `graph.nodes` |

**Table C.2 — Graph and contract codes.** The three auditability warnings encode a design position:
a control that does not appear in the graph cannot be traced through it.

## C.3 Pack, rule, and composition codes

Raised while resolving profiles and modules and evaluating their closed rules. Error level unless
noted.

| Code | Raised when | Fail-closed behaviour | Where to look |
|---|---|---|---|
| `PACK_NOT_FOUND` | A named pack is not found in project or built-in discovery | error | `.nornyx/profiles/`, `.nornyx/modules/`, built-ins |
| `PACK_NOT_RESOLVED` | `project.profile` names an unresolvable profile | **warning** — deliberately backward compatible | `project.profile` |
| `PACK_MODULE_SELECTION_INVALID` | An explicit `project.modules` selection cannot be satisfied | error — module selections are fail-closed | `project.modules` |
| `PACK_KIND_MISMATCH` | A profile pack is validated as a module, or the reverse | error, exit 1 | The pack's `kind` |
| `PACK_SCHEMA_INVALID` / `_UNSUPPORTED`, `PACK_CATALOG_INVALID`, `PACK_CORE_INCOMPATIBLE` | The pack fails its closed schema, declares an unsupported schema or incompatible core, or the catalogue is malformed | error | `schemas/profile_pack_v1.schema.json`, `governance_module_v1.schema.json` |
| `PACK_INTEGRITY_MISSING` / `_MISMATCH` | No integrity block, or the content hash does not match | error | The pack's `integrity` |
| `PACK_DEPENDENCY_CYCLE` / `PACK_DECLARED_CONFLICT` | Modules cycle, or declare each other conflicting | error | `dependencies`, `conflicts` |
| `PACK_DUPLICATE_ID` / `_IDENTITY` / `_RULE`, `PACK_ITEM_ID_MISSING` | Repeated or unidentified elements within or across packs | error | The offending pack |
| `PACK_MONOTONICITY_CONFLICT` / `_APPROVAL` / `_EVIDENCE` | Composition would weaken or contradict an already-composed value | error — composition is monotonic by construction | `nornyx/governance/composition.py:48-120` |
| `PACK_LIMIT_EXCEEDED` / `PACK_BLOCK_SCHEMA_LIMIT_EXCEEDED` / `PACK_APPROVAL_SOURCE_LIMIT_EXCEEDED` | A bounded collection exceeds its cap (200 rules per pack, 2,000 composed, 64 block schemas, 64 structural checks) | error | `composition.py:25-27` |
| `PACK_BLOCK_SCHEMA_INVALID` / `_CONFLICT` / `_UNAVAILABLE` / `_REF_REJECTED` / `_REF_CYCLE` / `_KEYWORD_REJECTED` | A contributed block schema is malformed, conflicting, missing, or uses a rejected reference or keyword | error | The module's `block_schemas` |
| `PACK_PATH_INSPECTION_FAILED` / `_PATH_TYPE_INVALID` / `_SYMLINK_REJECTED` / `_RESERVED_NAMESPACE` / `_SOURCE_TIER_INVALID` / `_ENCODING_INVALID` / `_WRITE_ERROR` | Path, namespace, tier, or encoding screening rejects the pack | error; exit 2 for path and encoding failures | `nornyx/path_security.py`; `governance/loader.py` |
| `RULE_OPERATOR_UNKNOWN` / `_PATH_MISSING` / `_PATH_TYPE_ERROR` / `_SCALAR_TYPE_ERROR` / `_COLLECTION_TYPE_ERROR` / `_REFERENCE_TYPE_ERROR` / `_EMPTY_COLLECTION` / `_STEP_LIMIT_EXCEEDED` / `_REQUIREMENT_FAILED` | A closed governance rule cannot be evaluated, or evaluates to a failed requirement | error | The rule id in the pack |
| `GOVERNANCE_REQUIRED_BLOCK_MISSING` | A composed pack requires a block the document does not declare | error, exit 1 | The named block |
| `GOVERNANCE_BLOCK_SCHEMA_INVALID` | A declared block fails a contributed closed schema | error, exit 1 | The block — extra fields, including credential-like ones, are rejected by design |
| `GOVERNANCE_STRUCTURAL_CHECK_UNKNOWN` | A pack names a check the runtime does not implement | error | `structural_checks` |
| `GOVERNANCE_TIME_REQUIRED` / `GOVERNANCE_TIME_INVALID` | A time-sensitive check needs an evaluation instant that was absent or malformed | error | Supply `--as-of` |

**Table C.3 — Pack, rule, and governance codes.** Complete for `PACK_*`, `RULE_*`, and
`GOVERNANCE_*`.

## C.4 Approval, duty-separation, exception, and change codes

Forty-seven `APPROVAL_*` codes were extracted; the table samples the ones a reviewer meets most
often. The recurring theme is that non-human authority is rejected at declaration, at decision, and
at evidence.

| Code | Raised when | Fail-closed behaviour | Where to look |
|---|---|---|---|
| `APPROVAL_CORE_DENIED_ACTOR_ELIGIBLE` / `APPROVAL_CORE_DENIAL_MISSING` | A declaration lists a core-denied actor type as eligible, or fails to deny all non-human categories | normalises as invalid; structural error | `nornyx/governance/approvals.py:426-433`; `structural.py` |
| `APPROVAL_NON_HUMAN` | An assertion's claimed actor type is not `human`, or is in the denied list | **deny decision** | `nornyx/agentic/authz.py:1040-1042` |
| `APPROVAL_NON_HUMAN_AUTHORITY` | `accountable_authority` names a non-human actor | error | `approvals.py:494-499` |
| `APPROVAL_ROLE_INVALID` | The approver's role is outside eligible ∪ required roles | deny decision | `authz.py:1043-1045` |
| `APPROVAL_REVISION_MISMATCH` | The assertion's revision differs from the contract's or the declared binding | deny decision | `authz.py:1030-1035` |
| `APPROVAL_ACTION_MISMATCH` / `APPROVAL_EVIDENCE_MISSING` | The approval does not cover the action, or required evidence is not supplied | deny decision | `authz.py:1038,1046-1048` |
| `APPROVAL_STALE` / `APPROVAL_NOT_GRANTED` | Expired or future-issued; or `granted` is false | deny decision — future issuance fails closed | `authz.py:1053-1064` |
| `APPROVAL_EXPIRED` / `_EXPIRY_REQUIRED` / `_EXPIRY_INVALID`, `APPROVAL_REVISION_BINDING_REQUIRED` / `_INVALID`, `APPROVAL_INVALIDATION_REQUIRED` / `_CONDITION_INVALID` | Static checks on expiry, revision binding, and invalidation conditions | error, exit 1 | The approval declaration |
| `APPROVAL_GATE_SHOULD_DENY_AI_TOOL` / `_EXECUTION_SURFACE` / `APPROVAL_GATE_REQUIRES_EVIDENCE` | A governed-package gate omits a denial or its required evidence | error, exit 1 | `governed_package.approval_gates` |
| `SOD_SELF_APPROVAL` / `SOD_EVIDENCE_PRODUCER_SOLE_APPROVER` | The approver authored the change, or solely approved evidence they produced | error, exit 1 | The assignment |
| `SOD_NON_HUMAN_APPROVER` / `SOD_APPROVER_INVALID` / `_ROLE_MISMATCH`, `SOD_RELEASE_AUTHORITY_CONFLICT` / `SOD_EXCEPTION_AUTHORITY_CONFLICT` | The approver is non-human, unidentified, wrongly-roled, or overlaps an authority it must stay independent of | error | The assignment |
| `EXCEPTION_EXPIRED` / `_INTERVAL_INVALID` / `_TIME_INVALID` | The waiver's window has passed or is malformed | error, exit 1 | The exception record |
| `EXCEPTION_RENEWAL_NOT_ALLOWED` / `_APPROVAL_MISSING` / `_FORK_INVALID` / `_INTERVAL_INVALID` / `_REFERENCE_INVALID` | Renewal violates the declared renewal policy | error | `renewal_policy` |
| `EXCEPTION_CLOSURE_EVIDENCE_MISSING` / `_INVALID`, `EXCEPTION_SELF_APPROVAL`, `EXCEPTION_NON_HUMAN_AUTHORITY`, `EXCEPTION_CORE_CONTROL_FORBIDDEN`, `EXCEPTION_SCOPE_OVERLAP` / `_INVALID`, `EXCEPTION_LIFECYCLE_INVALID` | A waiver is unclosed, self-approved, non-humanly approved, aimed at an unwaivable control, overlapping, or illegally transitioned | error | The exception set |
| `CHANGE_NON_HUMAN_APPROVER` / `_AUTHORITY`, `CHANGE_APPROVER_ROLE_UNAUTHORIZED` | A change is approved by a non-human or an unauthorised role | error, exit 1 | The change record |
| `CHANGE_SCOPE_HASH_MISMATCH` | The declared scope no longer hashes to its recorded value | error | `change_scope_hash` |
| `CHANGE_HIGH_RISK_GATES_MISSING`, `CHANGE_IRREVERSIBLE_AUTHORITY_MISSING`, `CHANGE_ROLLBACK_REQUIRED` / `_ARTIFACT_MISSING`, `CHANGE_LIFECYCLE_TRANSITION_INVALID`, `CHANGE_TRANSITION_EVIDENCE_MISSING` | A risky change lacks gates, authority, a rollback plan, or transition evidence | error | The change record |

**Table C.4 — Approval, duty-separation, exception, and change codes (sampled).** Full sets in
`nornyx/governance/approvals.py` and `structural.py`.

## C.5 Evidence and architecture codes

| Code | Raised when | Fail-closed behaviour | Where to look |
|---|---|---|---|
| `EVIDENCE_REQUIRED_MISSING` | A composed evidence requirement has no matching record | error, exit 1 | The evidence set |
| `EVIDENCE_ARTIFACT_UNAVAILABLE` / `_ROOT_REQUIRED` | The artifact cannot be read, or lies outside the permitted root | error; exit 2 for path failures | The record's `artifact` |
| `EVIDENCE_ARTIFACT_HASH_MISMATCH` / `EVIDENCE_HASH_SUBSTITUTION` | Bytes do not hash to the declared value, or a hash appears substituted rather than recomputed | error, exit 1 | `content_hash` |
| `EVIDENCE_REVISION_MISMATCH` | A record's subject revision differs from the set's | error | `subject_revision` |
| `EVIDENCE_STALE` / `_GENERATED_IN_FUTURE` / `_TIME_INVALID` | Past its freshness window, dated in the future, or malformed | error, exit 1 | `generated_at`, `expires_at`, and the `--as-of` supplied |
| `EVIDENCE_DEPENDENCY_UNSATISFIED` / `_INVALID` / `_CYCLE` | Record dependencies unmet, malformed, or circular | error | The record's dependencies |
| `EVIDENCE_DUPLICATE_ID` / `_ID_INVALID` / `_SOURCE_VALUE_INVALID` / `EVIDENCE_IMPORT_ERROR` | Repeated or malformed identity or source; a failed import | error, exit 1 | The evidence set |
| `ARCH_EVIDENCE_TOOL_MISMATCH` / `_SCHEMA_MISMATCH` / `_CHECK_UNKNOWN` / `_STATUS_INCONSISTENT` | A report names the wrong tool, schema, or an undeclared check, or reports inconsistently | error | `schemas/architecture_report_v1.schema.json` |
| `ARCH_EVIDENCE_STALE` / `_GENERATED_IN_FUTURE` / `_TIME_INVALID` / `_TIME_REQUIRED` | Report freshness fails | error | Report timestamps |
| `ARCH_REPORT_REMOTE_SOURCE_REJECTED` / `_SYMLINK_REJECTED` / `_PATH_OUTSIDE_ROOT` / `_PATH_TYPE_INVALID` / `_UNAVAILABLE` / `_LIMIT_EXCEEDED` | Report path screening or bounds reject the source before reading | error, exit 2 | `nornyx/path_security.py` |
| `ARCH_REQUIRED_CHECK_FAILED` / `ARCH_EVIDENCE_MISSING` / `ARCH_DEPENDENCY_DIRECTION_VIOLATION` / `ARCH_LAYER_DIRECTION_INVALID` / `ARCH_REFERENCE_UNKNOWN` / `ARCH_DUPLICATE_ID` | A required check failed or has no evidence, or a declared architecture constraint is violated | error | The `architecture` block |

**Table C.5 — Evidence and architecture codes.** Complete for `EVIDENCE_*`; representative for
`ARCH_*` (twenty-eight codes extracted).

## C.6 Agentic-network static declaration codes

Raised by the structural checks `agentic_network_foundation.v1` and `agentic_network_delegation.v1`
when the `agentic_network` profile resolves. All are error level and drive exit 1. More than one
hundred and fifty distinct codes exist across `nornyx/governance/agentic_network.py` and
`agentic_delegation.py`; the table names the families with representatives.

| Family | Representative codes | Raised when |
|---|---|---|
| Identity invariants | `AN_NON_HUMAN_APPROVAL_INVALID`, `AN_IDENTITY_DUPLICATE`, `AN_IDENTITY_SUBJECT_DUPLICATE`, `AN_IDENTITY_ROLE_UNKNOWN`, `AN_IDENTITY_BINDING_DUPLICATE` | An identity claims human authority or approval rights, or repeats an id, subject, or framework binding |
| Reference integrity | `AN_CAPABILITY_UNKNOWN`, `AN_TRUST_ZONE_UNKNOWN`, `AN_MEMBERSHIP_UNKNOWN`, `AN_GATE_UNKNOWN`, `AN_POLICY_UNKNOWN`, `AN_EVIDENCE_UNKNOWN`, `AN_APPROVAL_UNKNOWN`, `AN_REVOCATION_UNKNOWN` | A reference does not resolve to a declared record |
| Revision binding | `AN_REVISION_REQUIRED`, `AN_REVISION_MUTABLE`, `AN_REVISION_MISMATCH`, `AN_REVISION_MALFORMED`, `AN_REVISION_ALGORITHM_UNSUPPORTED` | The subject revision is absent, mutable, inconsistent, or malformed |
| Authorisation validity | `AN_AUTHORIZATION_EXPIRED`, `AN_AUTHORIZATION_NOT_YET_VALID`, `AN_AUTHORIZATION_REVOKED`, `AN_AUTHORIZATION_INTERVAL_INVALID` | A grant is outside its validity window at the evaluation instant |
| Approval declaration | `AN_APPROVAL_DECLARATION_MISSING`, `AN_APPROVAL_ACTION_MISSING`, `AN_APPROVAL_DECLARED_ROLE_UNAUTHORIZED`, `AN_APPROVAL_MODULE_ROLE_OMITTED`, `AN_APPROVAL_ACCOUNTABLE_AUTHORITY_MISMATCH`, `AN_APPROVAL_DECLARATION_MODULE_CONTRADICTION` | The network authority approval is absent, misses a required action, or contradicts the module's roles |
| Approval record | `AN_APPROVAL_HUMAN_REQUIRED`, `AN_APPROVAL_ROLE_INVALID`, `AN_APPROVAL_PRODUCER_OUTSIDE_MODULE_AUTHORITY`, `AN_APPROVAL_RECORD_MISSING`, `AN_APPROVAL_RECORD_INVALID`, `AN_APPROVAL_REVOKED`, `AN_APPROVAL_EXPIRED`, `AN_APPROVAL_NOT_YET_VALID`, `AN_APPROVAL_EXPIRY_EXCESSIVE`, `AN_VALIDATION_TIME_REQUIRED` | The supplied record is absent, non-human, wrongly-roled, revoked, expired, or excessively long-lived |
| Capability semantics | `AN_CAPABILITY_ESCALATION`, `AN_CAPABILITY_NOT_DELEGABLE`, `AN_CAPABILITY_SCOPE_UNKNOWN`, `AN_CAPABILITY_SCOPE_WRONG_KIND`, `AN_CAPABILITY_DELEGATION_POLICY_CONTRADICTION` | A grant exceeds what is declared, or its scope is wrong |
| Delegation | `AN_SELF_DELEGATION`, `AN_DELEGATION_ACTION_ESCALATION`, `AN_DELEGATION_SCOPE_ESCALATION`, `AN_DELEGATION_DEPTH_EXCEEDED`, `AN_ONWARD_DELEGATION_DENIED`, `AN_DELEGATION_CHAIN_CYCLE`, `AN_DELEGATION_CHAIN_BROKEN`, `AN_DELEGATOR_MEMBERSHIP_REQUIRED`, `AN_DELEGATION_INTERVAL_EXCEEDS_PARENT`, `AN_DELEGATION_FORBIDDEN`, `AN_DELEGATION_GOVERNANCE_MISSING` | A delegation widens authority, exceeds depth, cycles, outlives its parent, or lacks the membership grounding it |
| Handoff | `AN_HANDOFF_AUTHORITY_ESCALATION`, `AN_HANDOFF_SELF`, `AN_HANDOFF_MEMBERSHIP_REQUIRED`, `AN_HANDOFF_DELEGATION_MISMATCH`, `AN_HANDOFF_MISSION_UNKNOWN`, `AN_HANDOFF_STATUS_CONTRADICTION`, `AN_HANDOFF_SUPERSEDED_REF_INVALID` | A handoff transfers more authority than the source holds, or is internally contradictory |
| Cross-zone gating (generated prefixes) | `AN_DELEGATION_GATE_REQUIRED`, `AN_DELEGATION_APPROVAL_REQUIRED`, `AN_DELEGATION_EVIDENCE_REQUIRED`, `AN_HANDOFF_GATE_SOURCE_MISMATCH`, `AN_HANDOFF_EGRESS_GATE_MISSING`, `AN_DELEGATION_INGRESS_GATE_MISSING`, `AN_HANDOFF_GATE_ACTION_MISSING`, `AN_DELEGATION_TRANSITION_NOT_ALLOWED` | A cross-zone record lacks a governing gate, or the gate does not cover the zones or action class |
| Protocol targets | `AN_PROTOCOL_TRANSITION_NOT_ALLOWED`, `AN_PROTOCOL_EGRESS_GATE_MISSING`, `AN_PROTOCOL_INGRESS_GATE_MISSING`, `AN_PROTOCOL_APPROVAL_REQUIRED`, `AN_PROTOCOL_EVIDENCE_REQUIRED`, `AN_PROTOCOL_IDENTITY_UNAUTHORIZED`, `AN_PROTOCOL_MEMBERSHIP_WRONG_ZONE`, `AN_PROTOCOL_CAPABILITY_UNAUTHORIZED` | A declared MCP or A2A target is ungated, unapproved, or advertised by an identity that does not hold the capability in that zone |
| Sensitive sharing | `AN_SENSITIVE_SHARE_BOUNDARY_MISSING`, `AN_DELEGATION_SENSITIVE_SHARING`, `AN_HANDOFF_SENSITIVE_SHARING`, `AN_RELATION_SENSITIVE_SHARING`, `AN_SHARE_NOT_ALLOWED_SOURCE`, `AN_SHARE_NOT_ALLOWED_TARGET`, `AN_SHARE_CATEGORY_UNKNOWN` | A record shares `secrets`, `credentials`, `tokens`, or `private_memory` across a prohibited boundary |
| Relations | `AN_RELATION_ENDPOINT_KIND_INVALID`, `AN_RELATION_CONTRADICTORY`, `AN_RELATION_REFERENCE_INCONSISTENT`, `AN_RELATION_APPROVER_NOT_HUMAN`, `AN_RELATION_UNDECLARED_AUTHORITY`, `AN_RELATION_SELF_REFERENCE` | A relation is wrongly typed, contradicts what it references, or asserts undeclared authority |
| Normalisation and review | `AN_NORMALIZATION_COLLISION`, `AN_CONTRACT_REVIEW_MISSING`, `AN_CONTRACT_REVIEW_AMBIGUOUS`, `AN_CONTRACT_REVIEW_REQUIREMENT_MISSING` | Identifiers collide under Unicode normalisation and case folding; or contract-review evidence is absent or ambiguous |

**Table C.6 — Agentic-network static families.** Search the two named modules for the complete sets.

## C.7 Generation and lock codes

| Code | Raised when | Fail-closed behaviour | Where to look |
|---|---|---|---|
| `AN_ARTIFACT_PROFILE_MISSING` / `AN_ARTIFACT_NETWORK_MISSING` | Generation without a resolved profile, or without an `agentic_network` block | generation refused, exit 1 | `project.profile`; the contract |
| `AN_ARTIFACT_FORBIDDEN_FIELD` / `AN_ARTIFACT_FORBIDDEN_VALUE` | A rendered artifact would carry a forbidden key segment (endpoint, credential, command, token, host, port, URL and the rest) or a forbidden value such as an IPv4 literal | generation fails closed, nothing written | The declaration that produced it |
| `AN_ARTIFACT_OUTPUT_INVALID` / `AN_ARTIFACT_WRITE_ERROR` | Invalid output directory, or a failed write | generation refused | `--out` |
| `AN_LOCK_REVISION_MUTABLE` | The subject revision is not content-addressed | lock build refused | `subject_revision` |
| `AN_LOCK_SOURCE_STALE` | The contract digest differs from the lock's — the ordinary "you edited the contract" signal | exit 1 from `lock-check` | Re-lock after review |
| `AN_LOCK_NETWORK_MISMATCH` / `AN_LOCK_REVISION_MISMATCH` | Network id or subject revision differs | exit 1 | Lock and contract |
| `AN_LOCK_PROFILE_MISMATCH` / `AN_LOCK_MODULE_MISMATCH` | A resolved pack's id, version, or content hash differs | exit 1 | `profiles resolve`, `modules list` |
| `AN_LOCK_SCHEMA_MISMATCH` / `AN_LOCK_CHECKS_MISMATCH` / `AN_LOCK_PROTOCOL_MISMATCH` | Block schemas, the runtime-events schema version, structural checks, or protocol declarations differ | exit 1 | The composition |
| `AN_LOCK_RECORD_MISMATCH` | A per-record digest differs — one identity, capability, zone, membership, gate, target, delegation, handoff, relation, or revocation changed | exit 1 | The named collection |
| `AN_LOCK_APPROVAL_MISMATCH` / `AN_LOCK_EVIDENCE_MISMATCH` | Composed approval or evidence requirement references differ | exit 1 | The composition |
| `AN_LOCK_ARTIFACT_MISMATCH` / `_MISSING` / `_UNEXPECTED` | An on-disk artifact's hash differs, is absent, or is not in the lock at all | exit 1 | The artifacts directory |
| `AN_LOCK_FORMAT_MISMATCH` / `AN_LOCK_MALFORMED` / `AN_LOCK_WRITE_ERROR` | Wrong lock format version, unparseable lock, or failed write | exit 1; parse failures exit 2 | The lock path |
| `PACK_LOCK_MISMATCH` / `_SET_MISMATCH` / `_DUPLICATE_ID` / `_DUPLICATE_KEY` / `_INVALID` / `_REQUIRED` | `nornyx.profiles.lock` disagrees with the resolved pack set, or is malformed | **exit 2**, not 1 | `profiles resolve --lock` |
| `PACKAGE_LOCK_ARTIFACT_HASH_MISMATCH` / `_ARTIFACT_MISSING` / `_MANIFEST_HASH_MISMATCH`, `MISSING_PACKAGE_LOCK`, `UNSAFE_PACKAGE_LOCK` | A governed package's lock no longer binds its artifacts or manifest | error, exit 1 | The package directory |

**Table C.7 — Generation and lock codes.** Complete for `AN_ARTIFACT_*` and `AN_LOCK_*`. Note the
exit-code split: network-lock failures surface as 1, profile-lock failures as 2.

## C.8 Runtime-evidence codes

Fifty `AN_EVT_*` codes are implemented in `nornyx/agentic_evidence.py`. All place the validation
report's `status` at `fail`; the command exits nonzero only under `--strict`. They are grouped here
by what they defend, which is how a failing report should be read.

**Envelope and binding.** `AN_EVT_MALFORMED` (unreadable, unparseable, or over the 8 MiB bound);
`AN_EVT_SCHEMA_INVALID` (fails the runtime-events schema); `AN_EVT_SCHEMA_LOCK_MISMATCH` (the
envelope's schema id or version differs from the lock's — a 1.0 stream is never silently upgraded);
`AN_EVT_LOCK_STALE` (the supplied lock no longer verifies against the contract);
`AN_EVT_NETWORK_MISMATCH`, `AN_EVT_REVISION_MISMATCH`, `AN_EVT_CONTRACT_MISMATCH`,
`AN_EVT_LOCK_MISMATCH` (the four per-event binding fields differ from expected values);
`AN_EVT_FIELD_REQUIRED` (an event omits a field its type requires, for example `capability_allowed`
without `capability_ref` or `policy_decision`); `AN_EVT_DECISION_CONTRADICTION` (the decision value
contradicts the event type); `AN_EVT_INVALID`.

**Reference and authority.** `AN_EVT_ACTOR_UNKNOWN` / `_REVOKED` / `_NOT_EFFECTIVE` and
`AN_EVT_TARGET_UNKNOWN` / `_REVOKED` (an identity is undeclared, revoked, or outside its window at
the event's timestamp); `AN_EVT_CAPABILITY_UNKNOWN`, `AN_EVT_DELEGATION_UNKNOWN`,
`AN_EVT_HANDOFF_UNKNOWN`, `AN_EVT_ZONE_UNKNOWN`, `AN_EVT_APPROVAL_UNKNOWN` (an undeclared
reference); `AN_EVT_CAPABILITY_NOT_HELD` (an allowance or tool use unbacked by a held or delegated
capability at that timestamp); `AN_EVT_DELEGATION_ACTOR_MISMATCH` / `_EXPIRED` / `_REVOKED`;
`AN_EVT_HANDOFF_PARTY_MISMATCH`; `AN_EVT_APPROVAL_NON_HUMAN` (an `approval_granted` event names a
non-human approver — applied to grants only, so a *refused* non-human approval still validates);
`AN_EVT_APPROVAL_ROLE_INVALID`.

**Ordering and dependency.** `AN_EVT_DUPLICATE_ID`; `AN_EVT_DUPLICATE_SEQUENCE`;
`AN_EVT_SEQUENCE_GAP` (per-mission sequences not contiguous from 1); `AN_EVT_ORDER_INVALID`
(timestamps decrease within a mission); `AN_EVT_DEPENDENCY_MISSING` (a `depends_on` target absent or
at a higher sequence); and the four paired-transition codes `AN_EVT_TOOL_WITHOUT_ALLOWANCE`,
`AN_EVT_ACCEPTANCE_WITHOUT_REQUEST`, `AN_EVT_COMPLETION_WITHOUT_INITIATION`,
`AN_EVT_GRANT_WITHOUT_REQUEST`.

**Occurrence and attempt.** `AN_EVT_OCCURRENCE_OPERATION_MISMATCH` (one occurrence id used for two
operations); `AN_EVT_ATTEMPT_ORDER_INVALID`; `AN_EVT_ATTEMPT_GAP` (attempts not contiguous from 1);
`AN_EVT_ATTEMPT_AFTER_SUCCESS` (a retry after a successful terminal event — repeated work must open
a new occurrence); `AN_EVT_ATTEMPT_OUTCOME_CONTRADICTION` (one attempt records more than one
outcome).

**Replay.** `AN_EVT_REPLAY` fires when two events share a content fingerprint. The fingerprint is a
digest of the event with transport fields removed — `event_id` and `sequence` in the legacy modes,
and additionally `timestamp` in explicit occurrence mode, so a duplicate cannot evade detection by
restamping. Occurrence identity is part of the fingerprint, so identical work in a new occurrence or
a new attempt is correctly not replay.

**Sensitive sharing and zone crossing.** `AN_EVT_CROSSING_NOT_DECLARED` (not an allowed transition
of the source zone); `AN_EVT_CROSSING_UNGOVERNED` (no gate governs it);
`AN_EVT_CROSSING_APPROVAL_MISSING` (the gate requires an approval the stream does not carry);
`AN_EVT_SENSITIVE_SHARING` (one of `secrets`, `credentials`, `tokens`, `private_memory` crosses a
prohibited boundary); `AN_EVT_SHARE_NOT_ALLOWED` (the category is outside the zone's allowlist).

**Evidence artifact paths.** `AN_EVT_ARTIFACT_MISSING` (the artifact does not exist, or its path
escapes the events file's own directory, symlink escapes included); `AN_EVT_ARTIFACT_HASH_MISMATCH`
(bytes do not hash to the declared value).

Every report also carries the limitation block: validated evidence proves conformance of supplied
records only; hash validity proves content binding, not event truth; Nornyx does not observe,
operate, or monitor the runtime.

## C.9 Interface codes

Three enumerations govern the in-process authorization interface. Unlike the diagnostics above,
these are *returned*, not printed.

| Enumeration | Members | Fail-closed behaviour |
|---|---|---|
| `AuthorizerLoadCode` | `CONTRACT_INVALID`, `PROFILE_MISSING`, `LOCK_INVALID`, `LOCK_STALE` | Raised as `AuthorizerLoadError`; no authorizer is produced |
| `IdentityResolutionCode` | `IDENTITY_UNKNOWN`, `IDENTITY_AMBIGUOUS` | Raised as `IdentityResolutionError`; explicitly *not* a policy decision |
| `DecisionCode` | The twenty-three members listed in Appendix B, section B.10 | Carried on a `Decision`; a non-`ALLOW` effect blocks the wrapped callable |

**Table C.8 — Interface enumerations.** From `nornyx/agentic/authz.py:405-440`.

The supported adapters raise `AdapterDenied` carrying the core `Decision` unmodified, and
`AdapterConfigurationError` for a malformed adapter-owned declaration; the framework submodules add
`MissingOptionalDependencyError` and `UnsupportedSPIVersionError` at import time.

The unpackaged legacy shim translates decision codes into twenty-two stable `AN_ADAPTER_*` strings:
`AN_ADAPTER_APPROVAL_NON_HUMAN`, `_APPROVAL_NOT_GRANTED`, `_APPROVAL_ROLE_INVALID`,
`_CAPABILITY_DENIED`, `_CAPABILITY_UNKNOWN`, `_CONTRACT_INVALID`, `_CROSSING_APPROVAL_REQUIRED`,
`_DELEGATION_INACTIVE`, `_DELEGATION_UNKNOWN`, `_EVIDENCE_INVALID`, `_FRAMEWORK_MISMATCH`,
`_HANDOFF_AUTHORITY`, `_HANDOFF_UNKNOWN`, `_HOOK_MISSING`, `_IDENTITY_UNKNOWN`, `_LOCK_INVALID`,
`_LOCK_STALE`, `_PROFILE_MISSING`, `_REQUEST_MALFORMED`, `_SENSITIVE_SHARING`, `_SHARE_NOT_ALLOWED`,
`_ZONE_CROSSING_DENIED`. These are compatibility codes only, not public interface guarantees.

## C.10 Governed-package codes

| Code | Raised when | Fail-closed behaviour |
|---|---|---|
| `INVALID_GOVERNED_PACKAGE` / `_PROFILE` / `_MISSION` / `_CHANGE` / `_RISK_TIER` | The declaration or one of its parts is malformed | validation fails, exit 1 |
| `INVALID_APPROVER_EXECUTION_SURFACE` / `EXECUTION_SURFACE_CANNOT_APPROVE` | An execution surface or AI tool is an eligible approver, or a surface declares `can_approve: true` | validation fails, exit 1 |
| `INVALID_INSTALLATION_POLICY` / `INVALID_SAFETY_BOUNDARY` | A permissive installation or safety flag is set | validation fails, exit 1 |
| `INVALID_APPROVAL_GATE` / `UNKNOWN_APPROVAL_GATE_EVIDENCE` / `MISSING_EVIDENCE_REQUIREMENT_ID` / `_TYPE` / `DUPLICATE_EVIDENCE_REQUIREMENT_ID` | A gate or evidence requirement is malformed, unknown, or repeated | validation fails, exit 1 |
| `HOOKS_REQUIRE_HOOK_RISK_REVIEW` / `MCP_REQUIRES_MCP_RISK_REVIEW` / `SECRETS_REQUIRE_SECRET_SCAN_EVIDENCE` / `CLAIM_MISMATCH_REQUIRES_EVIDENCE` | The scanner found hooks, protocol server definitions, secret-like patterns, or critical claim mismatches without the corresponding review evidence | validation fails, exit 1 |
| `CRITICAL_EXTERNAL_EVIDENCE_REQUIRES_SECURITY_GATE` / `EXTERNAL_WRITES_REQUIRE_APPROVAL_GATE` | Critical imported evidence or declared external writes lack a gate | validation fails, exit 1 |
| `REQUIRED_ADAPTER_UNAVAILABLE` / `OPTIONAL_ADAPTER_UNAVAILABLE` | A declared external evidence adapter produced no report | overall status `fail` for required adapters |
| `MISSING_REGISTERED_ARTIFACT_HASH` / `REGISTERED_ARTIFACT_MISSING` / `REGISTERED_ARTIFACT_HASH_MISMATCH` / `MISSING_REGISTERED_SOURCE_PATH` | Registration is incomplete, or an artifact no longer matches its recorded hash | validation fails, exit 1 |
| `UNSAFE_PACKAGE_PATH` / `UNSAFE_REGISTERED_ARTIFACT_PATH` / `UNSAFE_REGISTERED_SOURCE_PATH` / `UNSAFE_PACKAGE_MANIFEST` / `UNSAFE_PACKAGE_LOCK_ARTIFACT` | Path screening rejects a path before filesystem access | validation fails |
| `INVALID_PROVENANCE` / `INVALID_ARTIFACT` / `INVALID_PACKAGE_LOCK_ENTRY` / `INVALID_PACKAGE_LOCK_JSON` / `MISSING_PACKAGE_MANIFEST` / `PACKAGE_NOT_FOUND` | Provenance, artifacts, or the lock are malformed or absent | validation fails, exit 1 |
| `PACKAGE_WITHOUT_README` / `PACKAGE_WITHOUT_LICENSE` / `PACKAGE_CONTAINS_BINARY_FILES` / `PACKAGE_CONTAINS_MINIFIED_FILES` / `PACKAGE_HAS_UNCLEAR_REMOTE_ENDPOINTS` | Scanner observations about the artifact set | risk-surface findings, not automatic failures |

**Table C.9 — Governed-package codes.** Even a clean validation does not license the claim that a
package is safe; the permitted claim is inventoried, risk-surfaced, evidence-bound, hash-locked, and
approval-gated.

## C.11 Command-level codes

Emitted by the command-line layer as a single JSON object, usually before or instead of any
diagnostic list.

| Code | Raised when | Exit | Command |
|---|---|---|---|
| `PARSE_ERROR` | The contract cannot be parsed — including every `ref` resolution failure and duplicate-key rejection | 2 | `check`, `explain`, `symbols`, `agentic-network *`, `governance` |
| `AS_OF_INVALID` | `--as-of` is not a timezone-aware ISO-8601 timestamp | 2 | Every command accepting `--as-of` |
| `WORKSPACE_ERROR` | The manifest is missing, malformed, or names an unreadable member | 2 | `workspace-check` |
| `UNSUPPORTED_EVIDENCE_TOOL` / `EVIDENCE_IMPORT_ERROR` | An importer other than `syft` or `gitleaks`, or a report that cannot be normalised | 1 | `package evidence import` |
| `UNSUPPORTED_EVAL_TOOL` / `EVAL_IMPORT_ERROR` | An importer other than `promptfoo`, or a report that fails to bind | 1 | `eval-import` |
| `PACKAGE_SCAN_ERROR` / `_GENERATE_ERROR` / `_VALIDATE_ERROR` / `_REGISTER_ERROR` / `_RADAR_ERROR` | The corresponding package operation raised | 1 | `package *` |
| `HARNESS_RUN_ERROR` / `POLICY_CHECK_ERROR` / `EVAL_RUN_ERROR` | The corresponding planning command raised | 1 | `harness-run`, `policy-check`, `eval-run` |
| `INIT_ERROR` / `NO_EXAMPLES` / `FILE_EXISTS` | Starter generation failed; the bundled examples are absent; the output draft exists without `--force` | 1 | `init`, `examples`, `adopt init-lite` |

**Table C.10 — Command-level codes.** From `nornyx/cli.py`.

## C.12 Reading a diagnostic well

Three habits make this catalogue useful rather than decorative.

**Read the level before the code.** `UNKNOWN_TOP_LEVEL_BLOCK`, `UNKNOWN_VERSION`,
`PACK_NOT_RESOLVED`, and the three `CONTRACT_*_NOT_IN_GRAPH` auditability signals do not fail a
build. If your policy is that they should, your pipeline must say so; the tool will not.

**Read the exit code as a class, not a number.** A 2 is a structural refusal — the tool declined to
reason about the input at all. A 1 is a governance verdict. Conflating them hides parse failures
behind policy failures.

**Treat a passing evidence validation as a scoped statement.** The report's own limitation block
says what it means: the supplied records conform to the exact contract revision. It does not say the
events happened, that they are complete, or that anything enforced the contract at run time.
