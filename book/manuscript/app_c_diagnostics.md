---
appendix: C
title: "Appendix C — Diagnostic Code Guide"
---

# Appendix C — Diagnostic Code Guide

Diagnostic codes are the stable public vocabulary of a governance toolchain. A pipeline that keys
on message text breaks on the next wording change; a pipeline that keys on codes does not. This
appendix catalogues the code families present in Nornyx at the audited revision `70d2b40ad792`, so
that a reader who meets a code in continuous-integration output can find out what raised it, what
the tool did about it, and where to look next.

**Coverage statement.** This is a *representative* catalogue, not an exhaustive one. Several
families are large — the agentic-network static checks alone contribute more than one hundred and
fifty codes across two modules — and reproducing them all would produce a listing rather than a
guide. Every code printed below was extracted from the repository by direct search or observed in a
live command run during preparation; where a family is sampled rather than complete, the section
says so and names the file to search. No code in this appendix is invented.

## C.1 How codes are shaped

Codes are upper-snake-case strings. **There is no numeric code scheme in the core** — nothing of
the form `NYX001` exists, and a reader who has seen such a scheme in another tool should not expect
one here. Core diagnostics travel on a record with five fields: `level` (`error` or `warning`),
`code`, `message`, `path`, and `hint`.

Ten namespaces are documented as reserved and stable: `PACK_*`, `RULE_*`, `GOVERNANCE_*`,
`APPROVAL_*`, `EVIDENCE_*`, `SOD_*`, `EXCEPTION_*`, `CHANGE_*`, `ARCH_*`, and `AN_*`. The core
checker predates that scheme and uses unprefixed structural names such as `MISSING_PROJECT_NAME`.

Three codes are *generated* rather than written out literally, so searching the source for the
exact string will fail:

- `MISSING_<SINGULAR>_NAME` — from the singular form of a named list block, giving
  `MISSING_POLICY_NAME`, `MISSING_HARNESS_NAME`, `MISSING_TRACE_NAME`, `MISSING_EVAL_NAME`.
- `MISSING_GOAL_<FIELD>` and `INVALID_GOAL_<FIELD>` — from the goal field name, giving
  `MISSING_GOAL_SCOPE`, `INVALID_GOAL_STOP_RULES`, and so on.
- `AN_DELEGATION_*` and `AN_HANDOFF_*` gate and authority codes — composed from a prefix constant,
  giving `AN_DELEGATION_GATE_REQUIRED`, `AN_HANDOFF_APPROVAL_REQUIRED`,
  `AN_DELEGATION_EVIDENCE_REQUIRED`, `AN_HANDOFF_EGRESS_GATE_MISSING`, and their siblings.

The level matters as much as the code. `has_errors` gates the exit code; warnings never do. A
document producing twenty warnings still exits 0.

## C.2 Checker codes — contract structure and references

Raised by `nornyx check` and by any command that validates a document. Unless noted, these are
error level and drive exit 1.

| Code | Raised when | Fail-closed behaviour | Where to look |
|---|---|---|---|
| `MISSING_TOP_LEVEL_BLOCK` | `nornyx:` or `project:` absent | error, exit 1 | The document head |
| `MISSING_PROJECT_NAME` | `project.name` empty or absent | error, exit 1 | `project.name` |
| `INVALID_PROJECT` | `project` is not a mapping | error, exit 1 | `project` |
| `UNKNOWN_VERSION` | `nornyx:` is not `0.1` or `0.2` | **warning**, exit unaffected | The version marker |
| `UNKNOWN_TOP_LEVEL_BLOCK` | A top-level key is neither core nor a recognised extension | **warning**, suppressed for module-contributed blocks | The block name; consider whether a profile should be declared |
| `INVALID_BLOCK_TYPE` / `INVALID_MAPPING_BLOCK` | A list block is not a list, or a mapping block is not a mapping | error, exit 1 | The block |
| `INVALID_BLOCK_ENTRY` | A list entry is not a mapping | error, exit 1 | The entry index |
| `MISSING_<SINGULAR>_NAME` | A named list entry has no `name` | error, exit 1 | The entry index |
| `CONTEXT_WITHOUT_INCLUDE` | A context declares no `include` patterns | error, exit 1 | `contexts[i].include` |
| `HARNESS_WITHOUT_FLOW` | A harness declares no `flow` | error, exit 1 | `harnesses[i].flow` |
| `INVALID_FLOW_STEP` | A flow step is malformed | error, exit 1 | `harnesses[i].flow[j]` |
| `INVALID_AGENT` / `INVALID_HARNESS` | Entry shape is wrong | error, exit 1 | The entry |
| `UNKNOWN_SKILL_REFERENCE` | An agent names an undeclared skill | error, exit 1 | `agents[i].skills` |
| `UNKNOWN_POLICY_REFERENCE` | An agent names an undeclared policy | error, exit 1 | `agents[i].policy` |
| `UNKNOWN_CONTEXT_REFERENCE` | A harness names an undeclared context | error, exit 1 | `harnesses[i].context` |
| `UNKNOWN_AGENT_REFERENCE` / `UNKNOWN_EVAL_REFERENCE` | A flow step names an undeclared agent or eval | error, exit 1 | The flow step |
| `INVALID_EVIDENCE_REQUIRED` | `evidence.required` is malformed | error, exit 1 | `evidence.required` |
| `MISSING_GOAL_ID` / `MISSING_GOAL_PHASE` / `MISSING_GOAL_OUTCOME` / `MISSING_GOAL_APPROVAL` / `MISSING_GOAL_EVIDENCE` | A goal omits a required field | error, exit 1 | `goals[i]` |
| `MISSING_GOAL_<FIELD>` / `INVALID_GOAL_<FIELD>` | A goal's list field is absent or not a list of non-empty strings | error, exit 1 | `goals[i].<field>` |
| `GOAL_WITHOUT_VALIDATION` | A goal declares no validation commands | error, exit 1 | `goals[i].validation` |
| `INVALID_GOAL` | Goal entry shape is wrong | error, exit 1 | `goals[i]` |

**Table C.1 — Core structural and reference codes.** All in `nornyx/checker.py`.

### Graph and contract codes

| Code | Raised when | Fail-closed behaviour | Where to look |
|---|---|---|---|
| `INVALID_GRAPH_BLOCK` / `INVALID_GRAPH_NODES` / `INVALID_GRAPH_EDGES` | The graph block or its collections are malformed | error, exit 1 | `graph` |
| `MISSING_GRAPH_NODE_ID` / `MISSING_GRAPH_NODE_KIND` | A node omits `id` or `kind` | error, exit 1 | `graph.nodes[i]` |
| `DUPLICATE_GRAPH_NODE_ID` / `DUPLICATE_GRAPH_EDGE` | Repeated node id or edge | error, exit 1 | `graph` |
| `GRAPH_SELF_EDGE` | An edge's endpoints are identical | error, exit 1 | `graph.edges[i]` |
| `UNKNOWN_GRAPH_NODE_REFERENCE` | An edge endpoint is not a declared node | error, exit 1 | `graph.edges[i]` |
| `UNKNOWN_GRAPH_REF_REFERENCE` | A node's `ref` does not resolve in the block matching its kind | error, exit 1 | `graph.nodes[i].ref` |
| `GRAPH_EVIDENCE_NODE_WITHOUT_REF` | An evidence node carries no `ref` | warning | `graph.nodes[i]` |
| `GRAPH_EDGE_WITHOUT_RELATION` | An edge declares no relation verb | error, exit 1 | `graph.edges[i]` |
| `UNKNOWN_GRAPH_RELATION` | The relation verb is outside the twenty-three typed relations | warning | `graph.edges[i].relation` |
| `INVALID_GRAPH_RELATION_PAIR` | A known relation is used between disallowed source/target kinds | error, exit 1 | `nornyx/checker.py:144-168` for the allowed pairs |
| `INVALID_CONTRACTS_BLOCK` / `INVALID_CONTRACT_ENTRY` / `MISSING_CONTRACT_NAME` | The contracts block or an entry is malformed | error, exit 1 | `contracts` |
| `UNKNOWN_CONTRACT_GRAPH_REFERENCE` / `UNKNOWN_CONTRACT_APPROVAL_REFERENCE` / `UNKNOWN_CONTRACT_BUDGET_REFERENCE` | A contract references an undeclared graph node, approval, or budget | error, exit 1 | `contracts[i]` |
| `CONTRACT_APPROVAL_NOT_IN_GRAPH` / `CONTRACT_BUDGET_NOT_IN_GRAPH` / `CONTRACT_WITHOUT_EVIDENCE_NODE` | A control is declared but not represented as a graph node | warning — an auditability signal | `graph.nodes` |

**Table C.2 — Graph and contract codes.** The three auditability warnings encode a design position:
a control that does not appear in the graph cannot be traced through it.

## C.3 Pack, rule, and composition codes

Raised while resolving profiles and modules and evaluating their closed rules.

| Code | Raised when | Fail-closed behaviour | Where to look |
|---|---|---|---|
| `PACK_NOT_FOUND` | A named pack cannot be located in project or built-in discovery | error | `.nornyx/profiles/`, `.nornyx/modules/`, then built-ins |
| `PACK_NOT_RESOLVED` | `project.profile` names an unresolvable profile | **warning** — deliberately backward compatible | `project.profile` |
| `PACK_MODULE_SELECTION_INVALID` | An explicit `project.modules` selection cannot be satisfied | error — module selections are fail-closed | `project.modules` |
| `PACK_KIND_MISMATCH` | A profile pack is passed to `modules validate`, or vice versa | error, exit 1 | The pack's `kind` |
| `PACK_SCHEMA_INVALID` / `PACK_SCHEMA_UNSUPPORTED` | The pack fails its own closed schema, or declares an unsupported schema | error | `schemas/profile_pack_v1.schema.json`, `governance_module_v1.schema.json` |
| `PACK_INTEGRITY_MISSING` / `PACK_INTEGRITY_MISMATCH` | A pack has no integrity block, or its content hash does not match | error | The pack's `integrity` |
| `PACK_DEPENDENCY_CYCLE` / `PACK_DECLARED_CONFLICT` | Modules form a cycle, or declare each other as conflicting | error | Module `dependencies` and `conflicts` |
| `PACK_DUPLICATE_ID` / `PACK_DUPLICATE_IDENTITY` / `PACK_DUPLICATE_RULE` / `PACK_ITEM_ID_MISSING` | Repeated or unidentified elements within or across packs | error | The offending pack |
| `PACK_MONOTONICITY_CONFLICT` / `PACK_MONOTONICITY_APPROVAL` / `PACK_MONOTONICITY_EVIDENCE` | Composition would have to weaken or contradict an already-composed value | error — composition is monotonic by construction | `nornyx/governance/composition.py:48-120` |
| `PACK_LIMIT_EXCEEDED` / `PACK_BLOCK_SCHEMA_LIMIT_EXCEEDED` / `PACK_APPROVAL_SOURCE_LIMIT_EXCEEDED` | A bounded collection exceeds its cap (200 rules per pack, 2,000 composed, 64 block schemas, 64 structural checks) | error | `composition.py:25-27` |
| `PACK_BLOCK_SCHEMA_INVALID` / `_CONFLICT` / `_UNAVAILABLE` / `_REF_REJECTED` / `_REF_CYCLE` / `_KEYWORD_REJECTED` | A contributed block schema is malformed, conflicting, missing, or uses a rejected reference or keyword | error | The module's `block_schemas` |
| `PACK_PATH_INSPECTION_FAILED` / `PACK_PATH_TYPE_INVALID` / `PACK_SYMLINK_REJECTED` / `PACK_RESERVED_NAMESPACE` / `PACK_SOURCE_TIER_INVALID` / `PACK_ENCODING_INVALID` | Path screening, namespace, tier, or encoding checks reject the pack before or during load | error, exit 2 for path and encoding failures | `nornyx/path_security.py`; `nornyx/governance/loader.py` |
| `PACK_CATALOG_INVALID` / `PACK_CORE_INCOMPATIBLE` / `PACK_WRITE_ERROR` | The built-in catalogue is malformed, the pack declares an incompatible core, or a write fails | error | `nornyx/profiles_data/catalog.json` |
| `RULE_OPERATOR_UNKNOWN` / `RULE_PATH_MISSING` / `RULE_PATH_TYPE_ERROR` / `RULE_SCALAR_TYPE_ERROR` / `RULE_COLLECTION_TYPE_ERROR` / `RULE_REFERENCE_TYPE_ERROR` / `RULE_EMPTY_COLLECTION` / `RULE_STEP_LIMIT_EXCEEDED` / `RULE_REQUIREMENT_FAILED` | A closed governance rule cannot be evaluated, or evaluates to a failed requirement | error | The rule id in the module pack |
| `GOVERNANCE_REQUIRED_BLOCK_MISSING` | A composed pack requires a block the document does not declare | error, exit 1 | The named block |
| `GOVERNANCE_BLOCK_SCHEMA_INVALID` | A declared block fails a contributed closed schema | error, exit 1 | The block; extra fields, including credential-like ones, are rejected by design |
| `GOVERNANCE_STRUCTURAL_CHECK_UNKNOWN` | A pack names a structural check the runtime does not implement | error | The pack's `structural_checks` |
| `GOVERNANCE_TIME_REQUIRED` / `GOVERNANCE_TIME_INVALID` | A time-sensitive check needs an evaluation instant that was absent or malformed | error | Supply `--as-of` |

**Table C.3 — Pack, rule, and governance codes.** Complete for `PACK_*`, `RULE_*`, and
`GOVERNANCE_*` as extracted from `nornyx/`.

## C.4 Approval, duty-separation, exception, and change codes

The approval family is the largest of the governance namespaces; forty-seven codes were extracted.
The table samples the ones a reviewer meets most often, grouped by what they defend.

| Code | Raised when | Fail-closed behaviour | Where to look |
|---|---|---|---|
| `APPROVAL_CORE_DENIED_ACTOR_ELIGIBLE` | A declaration lists a core-denied actor type as eligible or required | normalises as invalid | `nornyx/governance/approvals.py:426-433` |
| `APPROVAL_CORE_DENIAL_MISSING` | The declaration fails to deny all non-human authority categories | error | `nornyx/governance/structural.py` |
| `APPROVAL_NON_HUMAN` | An approval assertion's claimed actor type is not `human`, or is in the denied list | **deny decision** at the SPI | `nornyx/agentic/authz.py:1040-1042` |
| `APPROVAL_NON_HUMAN_AUTHORITY` | `accountable_authority` names a non-human actor | error | `approvals.py:494-499` |
| `APPROVAL_ROLE_INVALID` | The approver's role is outside `eligible_roles ∪ required_roles` | deny decision | `authz.py:1043-1045` |
| `APPROVAL_REVISION_MISMATCH` | The assertion's subject revision differs from the contract's, or from the declared binding | deny decision | `authz.py:1030-1035` |
| `APPROVAL_ACTION_MISMATCH` | The approval does not cover the requested action | deny decision | `authz.py:1038` |
| `APPROVAL_EVIDENCE_MISSING` | Required evidence references are not a subset of those supplied | deny decision | `authz.py:1046-1048` |
| `APPROVAL_STALE` | The approval has expired, or is issued in the future | deny decision — future issuance fails closed | `authz.py:1053-1063` |
| `APPROVAL_NOT_GRANTED` | The assertion's `granted` flag is false | deny decision | `authz.py:1064` |
| `APPROVAL_EXPIRED` / `APPROVAL_EXPIRY_REQUIRED` / `APPROVAL_EXPIRY_INVALID` | Static checks on the declared expiry | error, exit 1 | The approval declaration |
| `APPROVAL_REVISION_BINDING_REQUIRED` / `_INVALID` | A binding is absent or malformed where one is required | error | `revision_binding` |
| `APPROVAL_INVALIDATION_REQUIRED` / `_CONDITION_INVALID` | Invalidation conditions absent or malformed | error | `invalidation_conditions` |
| `APPROVAL_GATE_SHOULD_DENY_AI_TOOL` / `_EXECUTION_SURFACE` / `APPROVAL_GATE_REQUIRES_EVIDENCE` | A governed-package approval gate omits a denial or its required evidence | error, exit 1 | `governed_package.approval_gates` |
| `SOD_SELF_APPROVAL` | The approver is the author of the change | error, exit 1 | `separation_of_duties` assignments |
| `SOD_NON_HUMAN_APPROVER` / `SOD_APPROVER_INVALID` / `SOD_APPROVER_ROLE_MISMATCH` | The approver is not human, is unidentified, or holds the wrong role | error | The assignment |
| `SOD_EVIDENCE_PRODUCER_SOLE_APPROVER` | The producer of the evidence is also its only approver | error | The assignment |
| `SOD_RELEASE_AUTHORITY_CONFLICT` / `SOD_EXCEPTION_AUTHORITY_CONFLICT` | Release or exception authority overlaps a role it must remain independent of | error | The assignment |
| `EXCEPTION_EXPIRED` / `EXCEPTION_INTERVAL_INVALID` / `EXCEPTION_TIME_INVALID` | The waiver's validity window has passed or is malformed | error, exit 1 | The exception record |
| `EXCEPTION_RENEWAL_NOT_ALLOWED` / `_APPROVAL_MISSING` / `_FORK_INVALID` / `_INTERVAL_INVALID` / `_REFERENCE_INVALID` | Renewal violates the declared renewal policy | error | `renewal_policy` |
| `EXCEPTION_CLOSURE_EVIDENCE_MISSING` / `_INVALID` | A closed exception lacks valid closure evidence | error | `closure_evidence` |
| `EXCEPTION_SELF_APPROVAL` / `EXCEPTION_NON_HUMAN_AUTHORITY` / `EXCEPTION_AUTHORITY_INVALID` | The waiver is self-approved or approved by a non-human authority | error | The exception record |
| `EXCEPTION_CORE_CONTROL_FORBIDDEN` | The waiver targets a control that may not be excepted | error | The exception's `control` |
| `EXCEPTION_SCOPE_OVERLAP` / `EXCEPTION_SCOPE_INVALID` / `EXCEPTION_LIFECYCLE_INVALID` | Overlapping or malformed scope, or an invalid lifecycle transition | error | The exception set |
| `CHANGE_NON_HUMAN_APPROVER` / `CHANGE_NON_HUMAN_AUTHORITY` / `CHANGE_APPROVER_ROLE_UNAUTHORIZED` | A change is approved by a non-human, or by an unauthorised role | error, exit 1 | The change record |
| `CHANGE_SCOPE_HASH_MISMATCH` | The declared change scope no longer hashes to its recorded value | error | `change_scope_hash` |
| `CHANGE_HIGH_RISK_GATES_MISSING` / `CHANGE_IRREVERSIBLE_AUTHORITY_MISSING` | A high-risk or irreversible change lacks its required gates or authority | error | The change's risk tier |
| `CHANGE_ROLLBACK_REQUIRED` / `CHANGE_ROLLBACK_ARTIFACT_MISSING` | No rollback plan or artifact for a change that requires one | error | The change record |
| `CHANGE_LIFECYCLE_TRANSITION_INVALID` / `CHANGE_TRANSITION_EVIDENCE_MISSING` | An unpermitted lifecycle move, or one without its evidence | error | The change record |

**Table C.4 — Approval, duty-separation, exception, and change codes (sampled).** The full sets are
in `nornyx/governance/approvals.py`, `structural.py`, and the `change`/`exception` structural
checks. The recurring theme is that non-human authority is rejected at declaration, at decision,
and at evidence.

## C.5 Evidence and architecture codes

| Code | Raised when | Fail-closed behaviour | Where to look |
|---|---|---|---|
| `EVIDENCE_REQUIRED_MISSING` | A composed evidence requirement has no matching record | error, exit 1 | The evidence set |
| `EVIDENCE_ARTIFACT_UNAVAILABLE` / `EVIDENCE_ARTIFACT_ROOT_REQUIRED` | The named artifact cannot be read, or lies outside the permitted root | error, exit 2 for path failures | The record's `artifact` |
| `EVIDENCE_ARTIFACT_HASH_MISMATCH` | The artifact's bytes do not hash to the declared value | error, exit 1 | The record's `content_hash` |
| `EVIDENCE_HASH_SUBSTITUTION` | A hash appears to have been substituted rather than recomputed | error | The evidence set |
| `EVIDENCE_REVISION_MISMATCH` | A record's subject revision differs from the set's | error | `subject_revision` |
| `EVIDENCE_STALE` / `EVIDENCE_GENERATED_IN_FUTURE` / `EVIDENCE_TIME_INVALID` | The record is past its freshness window, dated in the future, or malformed | error, exit 1 | `generated_at`, `expires_at`, and the `--as-of` you supplied |
| `EVIDENCE_DEPENDENCY_UNSATISFIED` / `_INVALID` / `_CYCLE` | Declared record dependencies are unmet, malformed, or circular | error | The record's dependencies |
| `EVIDENCE_DUPLICATE_ID` / `EVIDENCE_ID_INVALID` / `EVIDENCE_SOURCE_VALUE_INVALID` | Repeated or malformed record identity or source | error | The evidence set |
| `EVIDENCE_IMPORT_ERROR` | An external evidence import fails | error, exit 1 | The imported report |
| `ARCH_EVIDENCE_TOOL_MISMATCH` / `_SCHEMA_MISMATCH` / `_CHECK_UNKNOWN` | An architecture report names the wrong tool, schema, or an undeclared check | error | `schemas/architecture_report_v1.schema.json` |
| `ARCH_EVIDENCE_STALE` / `_GENERATED_IN_FUTURE` / `_TIME_INVALID` / `_TIME_REQUIRED` | Report freshness fails | error | `generated_at`, `expires_at` |
| `ARCH_REPORT_REMOTE_SOURCE_REJECTED` / `_SYMLINK_REJECTED` / `_PATH_OUTSIDE_ROOT` / `_PATH_TYPE_INVALID` | Report path screening rejects the source before reading | error, exit 2 | `nornyx/path_security.py` |
| `ARCH_REQUIRED_CHECK_FAILED` / `ARCH_EVIDENCE_MISSING` / `ARCH_EVIDENCE_STATUS_INCONSISTENT` | A declared required check failed, has no evidence, or reports inconsistently | error | `architecture.required_checks` |
| `ARCH_DEPENDENCY_DIRECTION_VIOLATION` / `ARCH_LAYER_DIRECTION_INVALID` / `ARCH_REFERENCE_UNKNOWN` / `ARCH_DUPLICATE_ID` | Declared architecture constraints are violated | error | The `architecture` block |

**Table C.5 — Evidence and architecture codes.** Complete for `EVIDENCE_*`; representative for
`ARCH_*` (twenty-eight codes extracted).

## C.6 Agentic-network static declaration codes

These are raised by the two structural checks `agentic_network_foundation.v1` and
`agentic_network_delegation.v1` when the `agentic_network` profile is resolved. More than one
hundred and fifty distinct codes exist across
`nornyx/governance/agentic_network.py` and `nornyx/governance/agentic_delegation.py`; the table
below names the families and one or two representatives of each.

| Family | Representative codes | Raised when | Fail-closed behaviour |
|---|---|---|---|
| Identity invariants | `AN_NON_HUMAN_APPROVAL_INVALID`, `AN_IDENTITY_DUPLICATE`, `AN_IDENTITY_SUBJECT_DUPLICATE`, `AN_IDENTITY_ROLE_UNKNOWN`, `AN_IDENTITY_BINDING_DUPLICATE` | An identity claims human authority or approval rights, repeats an id, subject, or framework binding, or names an undeclared role | error, exit 1 |
| Reference integrity | `AN_CAPABILITY_UNKNOWN`, `AN_TRUST_ZONE_UNKNOWN`, `AN_MEMBERSHIP_UNKNOWN`, `AN_GATE_UNKNOWN`, `AN_POLICY_UNKNOWN`, `AN_EVIDENCE_UNKNOWN`, `AN_APPROVAL_UNKNOWN`, `AN_REVOCATION_UNKNOWN` | A reference does not resolve to a declared record | error, exit 1 |
| Revision binding | `AN_REVISION_REQUIRED`, `AN_REVISION_MUTABLE`, `AN_REVISION_MISMATCH`, `AN_REVISION_MALFORMED`, `AN_REVISION_ALGORITHM_UNSUPPORTED` | The subject revision is absent, mutable, inconsistent, or malformed | error, exit 1 |
| Authorisation validity | `AN_AUTHORIZATION_EXPIRED`, `AN_AUTHORIZATION_NOT_YET_VALID`, `AN_AUTHORIZATION_REVOKED`, `AN_AUTHORIZATION_INTERVAL_INVALID` | A membership or grant is outside its validity window at the evaluation instant | error, exit 1 |
| Approval declaration | `AN_APPROVAL_DECLARATION_MISSING`, `AN_APPROVAL_ACTION_MISSING`, `AN_APPROVAL_DECLARED_ROLE_UNAUTHORIZED`, `AN_APPROVAL_MODULE_ROLE_OMITTED`, `AN_APPROVAL_ACCOUNTABLE_AUTHORITY_MISMATCH`, `AN_APPROVAL_DECLARATION_MODULE_CONTRADICTION` | The `agentic_network_authority` approval is absent, does not cover a required action, or contradicts the module's roles | error, exit 1 |
| Approval record | `AN_APPROVAL_HUMAN_REQUIRED`, `AN_APPROVAL_ROLE_INVALID`, `AN_APPROVAL_PRODUCER_OUTSIDE_MODULE_AUTHORITY`, `AN_APPROVAL_RECORD_MISSING`, `AN_APPROVAL_RECORD_INVALID`, `AN_APPROVAL_REVOKED`, `AN_APPROVAL_EXPIRED`, `AN_APPROVAL_NOT_YET_VALID`, `AN_APPROVAL_EXPIRY_EXCESSIVE`, `AN_VALIDATION_TIME_REQUIRED` | The supplied approval record is absent, non-human, wrongly-roled, revoked, expired, or excessively long-lived | error, exit 1 |
| Capability semantics | `AN_CAPABILITY_ESCALATION`, `AN_CAPABILITY_NOT_DELEGABLE`, `AN_CAPABILITY_SCOPE_UNKNOWN`, `AN_CAPABILITY_SCOPE_WRONG_KIND`, `AN_CAPABILITY_DELEGATION_POLICY_CONTRADICTION` | A capability grant exceeds what is declared, or its scope is wrong | error, exit 1 |
| Delegation | `AN_SELF_DELEGATION`, `AN_DELEGATION_ACTION_ESCALATION`, `AN_DELEGATION_SCOPE_ESCALATION`, `AN_DELEGATION_DEPTH_EXCEEDED`, `AN_ONWARD_DELEGATION_DENIED`, `AN_DELEGATION_CHAIN_CYCLE`, `AN_DELEGATION_CHAIN_BROKEN`, `AN_DELEGATOR_MEMBERSHIP_REQUIRED`, `AN_DELEGATION_INTERVAL_EXCEEDS_PARENT`, `AN_DELEGATION_FORBIDDEN`, `AN_DELEGATION_GOVERNANCE_MISSING` | A delegation widens authority, exceeds its depth, cycles, outlives its parent, or lacks the membership that would ground it | error, exit 1 |
| Handoff | `AN_HANDOFF_AUTHORITY_ESCALATION`, `AN_HANDOFF_SELF`, `AN_HANDOFF_MEMBERSHIP_REQUIRED`, `AN_HANDOFF_DELEGATION_MISMATCH`, `AN_HANDOFF_MISSION_UNKNOWN`, `AN_HANDOFF_STATUS_CONTRADICTION`, `AN_HANDOFF_SUPERSEDED_REF_INVALID` | A handoff transfers more authority than the source holds, or is internally contradictory | error, exit 1 |
| Cross-zone gating (generated prefixes) | `AN_DELEGATION_GATE_REQUIRED`, `AN_DELEGATION_APPROVAL_REQUIRED`, `AN_DELEGATION_EVIDENCE_REQUIRED`, `AN_HANDOFF_GATE_SOURCE_MISMATCH`, `AN_HANDOFF_EGRESS_GATE_MISSING`, `AN_DELEGATION_INGRESS_GATE_MISSING`, `AN_HANDOFF_GATE_ACTION_MISSING`, `AN_DELEGATION_TRANSITION_NOT_ALLOWED` | A cross-zone record lacks a governing gate, or the referenced gate does not cover the zones or action class | error, exit 1 |
| Protocol targets | `AN_PROTOCOL_TRANSITION_NOT_ALLOWED`, `AN_PROTOCOL_EGRESS_GATE_MISSING`, `AN_PROTOCOL_INGRESS_GATE_MISSING`, `AN_PROTOCOL_APPROVAL_REQUIRED`, `AN_PROTOCOL_EVIDENCE_REQUIRED`, `AN_PROTOCOL_IDENTITY_UNAUTHORIZED`, `AN_PROTOCOL_MEMBERSHIP_WRONG_ZONE`, `AN_PROTOCOL_CAPABILITY_UNAUTHORIZED` | A declared MCP or A2A target is ungated, unapproved, or advertised by an identity that does not hold the capability in that zone | error, exit 1 |
| Sensitive sharing | `AN_SENSITIVE_SHARE_BOUNDARY_MISSING`, `AN_DELEGATION_SENSITIVE_SHARING`, `AN_HANDOFF_SENSITIVE_SHARING`, `AN_RELATION_SENSITIVE_SHARING`, `AN_SHARE_NOT_ALLOWED_SOURCE`, `AN_SHARE_NOT_ALLOWED_TARGET`, `AN_SHARE_CATEGORY_UNKNOWN` | A record shares one of `secrets`, `credentials`, `tokens`, `private_memory` across a prohibited boundary, or shares a category no zone allows | error, exit 1 |
| Relations | `AN_RELATION_ENDPOINT_KIND_INVALID`, `AN_RELATION_CONTRADICTORY`, `AN_RELATION_REFERENCE_INCONSISTENT`, `AN_RELATION_APPROVER_NOT_HUMAN`, `AN_RELATION_UNDECLARED_AUTHORITY`, `AN_RELATION_SELF_REFERENCE` | A relation is wrongly typed, contradicts the record it references, or asserts authority nothing declares | error, exit 1 |
| Normalisation | `AN_NORMALIZATION_COLLISION` | Two identifiers collide under Unicode normalisation and case folding | error, exit 1 |
| Contract review | `AN_CONTRACT_REVIEW_MISSING`, `AN_CONTRACT_REVIEW_AMBIGUOUS`, `AN_CONTRACT_REVIEW_REQUIREMENT_MISSING` | The required contract-review evidence is absent or ambiguous | error, exit 1 |

**Table C.6 — Agentic-network static families.** Search
`nornyx/governance/agentic_network.py` and `agentic_delegation.py` for the complete sets.

## C.7 Generation and lock codes

| Code | Raised when | Fail-closed behaviour | Where to look |
|---|---|---|---|
| `AN_ARTIFACT_PROFILE_MISSING` | Generation is attempted without a resolved governance profile | generation refused, exit 1 | `project.profile` |
| `AN_ARTIFACT_NETWORK_MISSING` | The contract has no `agentic_network` block | generation refused | The contract |
| `AN_ARTIFACT_FORBIDDEN_FIELD` | A rendered artifact would contain a forbidden key segment (endpoint, credential, command, token, host, port, URL, and so on) | generation fails closed, nothing written | The declaration that produced the field |
| `AN_ARTIFACT_FORBIDDEN_VALUE` | A rendered value contains an IPv4 literal or other forbidden content | generation fails closed | The declaration |
| `AN_ARTIFACT_OUTPUT_INVALID` / `AN_ARTIFACT_WRITE_ERROR` | The output directory is invalid, or a write fails | generation refused | `--out` |
| `AN_LOCK_REVISION_MUTABLE` | The subject revision is not content-addressed | lock build refused | `subject_revision` |
| `AN_LOCK_SOURCE_STALE` | The contract digest differs from the one the lock recorded — **the ordinary "you edited the contract" signal** | exit 1 from `lock-check` | Re-run `agentic-network lock` after review |
| `AN_LOCK_NETWORK_MISMATCH` / `AN_LOCK_REVISION_MISMATCH` | Network id or subject revision differs from the lock | exit 1 | The lock and the contract |
| `AN_LOCK_PROFILE_MISMATCH` / `AN_LOCK_MODULE_MISMATCH` | A resolved pack's id, version, or content hash differs | exit 1 | `nornyx profiles resolve`, `nornyx modules list` |
| `AN_LOCK_SCHEMA_MISMATCH` | A contributed block schema or the runtime-events schema version differs | exit 1 | The module's `block_schemas` |
| `AN_LOCK_CHECKS_MISMATCH` | The set of structural checks differs | exit 1 | The composed `structural_checks` |
| `AN_LOCK_PROTOCOL_MISMATCH` | A protocol declaration differs | exit 1 | `protocol_targets` |
| `AN_LOCK_RECORD_MISMATCH` | A per-record digest differs — one identity, capability, zone, membership, gate, target, delegation, handoff, relation, or revocation changed | exit 1 | The named record collection |
| `AN_LOCK_APPROVAL_MISMATCH` / `AN_LOCK_EVIDENCE_MISMATCH` | Composed approval or evidence requirement references differ | exit 1 | The composition |
| `AN_LOCK_ARTIFACT_MISMATCH` / `AN_LOCK_ARTIFACT_MISSING` / `AN_LOCK_ARTIFACT_UNEXPECTED` | An on-disk artifact's hash differs, is absent, or is not in the lock at all | exit 1 | `--artifacts` directory |
| `AN_LOCK_FORMAT_MISMATCH` | The lock's format version differs from the expected 1.0 | exit 1 | The lock head |
| `AN_LOCK_MALFORMED` / `AN_LOCK_WRITE_ERROR` | The lock file cannot be parsed, or cannot be written | exit 1; parse failures exit 2 | The lock path |
| `PACK_LOCK_MISMATCH` / `PACK_LOCK_SET_MISMATCH` / `PACK_LOCK_DUPLICATE_ID` / `PACK_LOCK_DUPLICATE_KEY` / `PACK_LOCK_INVALID` / `PACK_LOCK_REQUIRED` | `nornyx.profiles.lock` disagrees with the resolved pack set, or is malformed | **exit 2**, not 1 | `nornyx profiles resolve --lock` |
| `PACKAGE_LOCK_ARTIFACT_HASH_MISMATCH` / `_ARTIFACT_MISSING` / `_MANIFEST_HASH_MISMATCH` / `MISSING_PACKAGE_LOCK` / `UNSAFE_PACKAGE_LOCK` | A governed package's lock no longer binds its artifacts or manifest | error, exit 1 | The package directory |

**Table C.7 — Generation and lock codes.** Complete for `AN_ARTIFACT_*` and `AN_LOCK_*`. Note the
exit-code split: network-lock failures surface as 1 from `lock-check`, while profile-lock failures
surface as 2 from the governance commands.

## C.8 Runtime-evidence codes

Fifty `AN_EVT_*` codes are implemented in `nornyx/agentic_evidence.py`. All of them place the
validation report's `status` at `fail`; the command exits nonzero only under `--strict`. They are
grouped here by what they defend, which is how you should read a failing report.

### Envelope and binding

| Code | Raised when |
|---|---|
| `AN_EVT_MALFORMED` | The events file cannot be read or parsed, or exceeds the 8 MiB bound |
| `AN_EVT_SCHEMA_INVALID` | The envelope fails the runtime-events schema |
| `AN_EVT_SCHEMA_LOCK_MISMATCH` | The envelope's schema id or version differs from the lock's `runtime_events_schema` — a 1.0 stream is never silently upgraded |
| `AN_EVT_LOCK_STALE` | The supplied lock itself no longer verifies against the contract |
| `AN_EVT_NETWORK_MISMATCH` | `network_id` differs from the contract's |
| `AN_EVT_REVISION_MISMATCH` | `subject_revision` differs |
| `AN_EVT_CONTRACT_MISMATCH` | `contract_digest` differs |
| `AN_EVT_LOCK_MISMATCH` | `network_lock_digest` differs |
| `AN_EVT_FIELD_REQUIRED` | An event omits a field its type requires (for example `capability_allowed` without `capability_ref` or `policy_decision`) |
| `AN_EVT_DECISION_CONTRADICTION` | The decision value contradicts the event type |
| `AN_EVT_INVALID` | The event is otherwise structurally invalid |

### Reference and authority

| Code | Raised when |
|---|---|
| `AN_EVT_ACTOR_UNKNOWN` / `_REVOKED` / `_NOT_EFFECTIVE` | The acting identity is undeclared, revoked, or outside its validity window at the event's timestamp |
| `AN_EVT_TARGET_UNKNOWN` / `_REVOKED` | The target identity is undeclared or revoked |
| `AN_EVT_CAPABILITY_UNKNOWN` / `AN_EVT_DELEGATION_UNKNOWN` / `AN_EVT_HANDOFF_UNKNOWN` / `AN_EVT_ZONE_UNKNOWN` / `AN_EVT_APPROVAL_UNKNOWN` | A referenced record is not declared |
| `AN_EVT_CAPABILITY_NOT_HELD` | An allowance or tool use is not backed by a held or delegated capability at that timestamp |
| `AN_EVT_DELEGATION_ACTOR_MISMATCH` / `_EXPIRED` / `_REVOKED` | The delegation does not ground this actor at this time |
| `AN_EVT_HANDOFF_PARTY_MISMATCH` | The event's parties are not the handoff's parties |
| `AN_EVT_APPROVAL_NON_HUMAN` | An `approval_granted` event names a non-human approver — applied to grants only, so a *refused* non-human approval still validates |
| `AN_EVT_APPROVAL_ROLE_INVALID` | The approver's role lies outside the composed module authority |

### Ordering and dependency

| Code | Raised when |
|---|---|
| `AN_EVT_DUPLICATE_ID` | Two events share an `event_id` |
| `AN_EVT_DUPLICATE_SEQUENCE` | Two events in one mission share a sequence number |
| `AN_EVT_SEQUENCE_GAP` | Per-mission sequences are not contiguous from 1 |
| `AN_EVT_ORDER_INVALID` | Timestamps decrease within a mission |
| `AN_EVT_DEPENDENCY_MISSING` | A `depends_on` target does not exist at a lower sequence |
| `AN_EVT_TOOL_WITHOUT_ALLOWANCE` | A `tool_invoked` has no preceding allowance |
| `AN_EVT_ACCEPTANCE_WITHOUT_REQUEST` | A delegation acceptance has no request |
| `AN_EVT_COMPLETION_WITHOUT_INITIATION` | A handoff completion has no initiation |
| `AN_EVT_GRANT_WITHOUT_REQUEST` | An approval grant has no request |

### Occurrence and attempt

| Code | Raised when |
|---|---|
| `AN_EVT_OCCURRENCE_OPERATION_MISMATCH` | One occurrence id is used for two different operations |
| `AN_EVT_ATTEMPT_ORDER_INVALID` | Attempts within an occurrence are out of order |
| `AN_EVT_ATTEMPT_GAP` | Attempts are not contiguous from 1 |
| `AN_EVT_ATTEMPT_AFTER_SUCCESS` | A retry follows a successful terminal event in the same occurrence — repeated work must open a new occurrence |
| `AN_EVT_ATTEMPT_OUTCOME_CONTRADICTION` | One attempt records more than one outcome |

### Replay

| Code | Raised when |
|---|---|
| `AN_EVT_REPLAY` | Two events share a content fingerprint. The fingerprint is a digest of the event with transport fields removed: `event_id` and `sequence` in the legacy modes, and additionally `timestamp` in explicit occurrence mode, so a duplicate cannot evade detection by restamping. Occurrence identity is part of the fingerprint, so identical work in a new occurrence or a new attempt is not replay. |

### Sensitive sharing and zone crossing

| Code | Raised when |
|---|---|
| `AN_EVT_CROSSING_NOT_DECLARED` | The crossing is not an allowed transition of the source zone |
| `AN_EVT_CROSSING_UNGOVERNED` | No gate governs the crossing |
| `AN_EVT_CROSSING_APPROVAL_MISSING` | The governing gate requires an approval the stream does not carry |
| `AN_EVT_SENSITIVE_SHARING` | The event shares one of `secrets`, `credentials`, `tokens`, `private_memory` across a prohibited boundary |
| `AN_EVT_SHARE_NOT_ALLOWED` | The shared category is outside the relevant zone's allowlist |

### Evidence artifacts

| Code | Raised when |
|---|---|
| `AN_EVT_ARTIFACT_MISSING` | The referenced artifact does not exist, or its path escapes the events file's own directory (symlink escapes included) |
| `AN_EVT_ARTIFACT_HASH_MISMATCH` | The artifact's bytes do not hash to the declared value |

**Tables C.8a–C.8g — Runtime-evidence codes by category.** Complete for `AN_EVT_*`. Every report
also carries the limitation block: validated evidence proves conformance of supplied records only,
hash validity proves content binding rather than event truth, and Nornyx does not observe, operate,
or monitor the runtime.

## C.9 Interface codes

Three enumerations govern the in-process authorization interface. Unlike the diagnostics above,
these are *returned*, not printed.

| Enumeration | Members | Fail-closed behaviour |
|---|---|---|
| `AuthorizerLoadCode` | `CONTRACT_INVALID`, `PROFILE_MISSING`, `LOCK_INVALID`, `LOCK_STALE` | Raised as `AuthorizerLoadError`; no authorizer is produced |
| `IdentityResolutionCode` | `IDENTITY_UNKNOWN`, `IDENTITY_AMBIGUOUS` | Raised as `IdentityResolutionError`; explicitly *not* a policy decision |
| `DecisionCode` | The twenty-three members listed in Appendix B, section B.10 | Carried on a `Decision`; a non-`ALLOW` effect blocks the wrapped callable |

**Table C.9 — Interface enumerations.** From `nornyx/agentic/authz.py:405-440`.

The supported adapters raise `AdapterDenied` carrying the core `Decision` unmodified, and
`AdapterConfigurationError` for a malformed adapter-owned declaration; the framework submodules add
`MissingOptionalDependencyError` and `UnsupportedSPIVersionError` at import time.

The unpackaged legacy shim translates decision codes into twenty-two stable `AN_ADAPTER_*` strings:
`AN_ADAPTER_APPROVAL_NON_HUMAN`, `_APPROVAL_NOT_GRANTED`, `_APPROVAL_ROLE_INVALID`,
`_CAPABILITY_DENIED`, `_CAPABILITY_UNKNOWN`, `_CONTRACT_INVALID`, `_CROSSING_APPROVAL_REQUIRED`,
`_DELEGATION_INACTIVE`, `_DELEGATION_UNKNOWN`, `_EVIDENCE_INVALID`, `_FRAMEWORK_MISMATCH`,
`_HANDOFF_AUTHORITY`, `_HANDOFF_UNKNOWN`, `_HOOK_MISSING`, `_IDENTITY_UNKNOWN`, `_LOCK_INVALID`,
`_LOCK_STALE`, `_PROFILE_MISSING`, `_REQUEST_MALFORMED`, `_SENSITIVE_SHARING`,
`_SHARE_NOT_ALLOWED`, and `_ZONE_CROSSING_DENIED`. These are compatibility codes only, not public
interface guarantees.

## C.10 Governed-package codes

| Code | Raised when | Fail-closed behaviour |
|---|---|---|
| `INVALID_GOVERNED_PACKAGE` / `_PROFILE` / `_MISSION` / `_CHANGE` / `_RISK_TIER` | The package declaration or one of its parts is malformed | validation fails, exit 1 |
| `INVALID_APPROVER_EXECUTION_SURFACE` / `EXECUTION_SURFACE_CANNOT_APPROVE` | An execution surface or AI tool is listed as an eligible approver, or a surface declares `can_approve: true` | validation fails, exit 1 |
| `INVALID_INSTALLATION_POLICY` / `INVALID_SAFETY_BOUNDARY` | A permissive installation or safety flag is set — installed, executable by default, explicit install not required, or secrets, production data, autonomous execution, external writes, or deployment allowed | validation fails, exit 1 |
| `INVALID_APPROVAL_GATE` / `UNKNOWN_APPROVAL_GATE_EVIDENCE` / `MISSING_EVIDENCE_REQUIREMENT_ID` / `_TYPE` / `DUPLICATE_EVIDENCE_REQUIREMENT_ID` | A gate is malformed, references unknown evidence, or evidence requirements are malformed or repeated | validation fails, exit 1 |
| `HOOKS_REQUIRE_HOOK_RISK_REVIEW` / `MCP_REQUIRES_MCP_RISK_REVIEW` / `SECRETS_REQUIRE_SECRET_SCAN_EVIDENCE` / `CLAIM_MISMATCH_REQUIRES_EVIDENCE` | The scanner found hooks, MCP definitions, secret-like patterns, or critical claim mismatches without the corresponding review evidence | validation fails, exit 1 |
| `CRITICAL_EXTERNAL_EVIDENCE_REQUIRES_SECURITY_GATE` / `EXTERNAL_WRITES_REQUIRE_APPROVAL_GATE` | Critical imported evidence or declared external writes lack a security or approval gate | validation fails, exit 1 |
| `REQUIRED_ADAPTER_UNAVAILABLE` / `OPTIONAL_ADAPTER_UNAVAILABLE` | A declared external evidence adapter produced no report; required adapters default to a failing policy | overall scan status `fail` for required adapters |
| `MISSING_REGISTERED_ARTIFACT_HASH` / `REGISTERED_ARTIFACT_MISSING` / `REGISTERED_ARTIFACT_HASH_MISMATCH` / `MISSING_REGISTERED_SOURCE_PATH` | Registration is incomplete or an artifact no longer matches its recorded hash | validation fails, exit 1 |
| `UNSAFE_PACKAGE_PATH` / `UNSAFE_REGISTERED_ARTIFACT_PATH` / `UNSAFE_REGISTERED_SOURCE_PATH` / `UNSAFE_PACKAGE_MANIFEST` / `UNSAFE_PACKAGE_LOCK_ARTIFACT` | Path screening rejects a path before filesystem access | validation fails |
| `INVALID_PROVENANCE` / `INVALID_ARTIFACT` / `INVALID_PACKAGE_LOCK_ENTRY` / `INVALID_PACKAGE_LOCK_JSON` / `MISSING_PACKAGE_MANIFEST` / `PACKAGE_NOT_FOUND` | Provenance, artifacts, or the lock are malformed or absent | validation fails, exit 1 |
| `PACKAGE_WITHOUT_README` / `PACKAGE_WITHOUT_LICENSE` / `PACKAGE_CONTAINS_BINARY_FILES` / `PACKAGE_CONTAINS_MINIFIED_FILES` / `PACKAGE_HAS_UNCLEAR_REMOTE_ENDPOINTS` | Scanner observations about the artifact set | risk-surface findings, not automatic failures |

**Table C.10 — Governed-package codes.** From `nornyx/governed_package.py` and
`nornyx/package_scanner.py`. Even a clean validation does not license the claim that a package is
safe; the permitted claim is that it was inventoried, risk-surfaced, evidence-bound, hash-locked,
and approval-gated.

## C.11 Command-level codes

These are emitted by the command-line layer itself as a single JSON object, usually before or
instead of any diagnostic list.

| Code | Raised when | Exit | Command |
|---|---|---|---|
| `PARSE_ERROR` | The contract cannot be parsed — including every `ref` resolution failure and duplicate-key rejection | 2 | `check`, `explain`, `symbols`, the agentic-network group, `governance` |
| `AS_OF_INVALID` | `--as-of` is not a timezone-aware ISO-8601 timestamp | 2 | `check` and every command accepting `--as-of` |
| `WORKSPACE_ERROR` | The workspace manifest is missing, malformed, or names an unreadable member | 2 | `workspace-check` |
| `UNSUPPORTED_EVIDENCE_TOOL` | A package evidence importer other than `syft` or `gitleaks` is named | 1 | `package evidence import` |
| `EVIDENCE_IMPORT_ERROR` | The named evidence report cannot be normalised | 1 | `package evidence import` |
| `UNSUPPORTED_EVAL_TOOL` | An eval importer other than `promptfoo` is named | 1 | `eval-import` |
| `EVAL_IMPORT_ERROR` | The eval report fails to bind — for example a report digest or subject-revision mismatch | 1 | `eval-import` |
| `PACKAGE_SCAN_ERROR` / `PACKAGE_GENERATE_ERROR` / `PACKAGE_VALIDATE_ERROR` / `PACKAGE_REGISTER_ERROR` / `PACKAGE_RADAR_ERROR` | The corresponding package operation raised | 1 | `package *` |
| `HARNESS_RUN_ERROR` / `POLICY_CHECK_ERROR` / `EVAL_RUN_ERROR` | The corresponding planning command raised | 1 | `harness-run`, `policy-check`, `eval-run` |
| `INIT_ERROR` | Starter generation failed — unresolvable profile, output collision without `--force`, fragment merge conflict | 1 | `init` |
| `NO_EXAMPLES` | The bundled example set cannot be located | 1 | `examples` |
| `FILE_EXISTS` | The output draft already exists and `--force` was not given | 1 | `adopt init-lite` |

**Table C.11 — Command-level codes.** From `nornyx/cli.py`.

## C.12 Reading a diagnostic well

Three habits make this catalogue useful rather than decorative.

First, **read the level before the code**. Warnings such as `UNKNOWN_TOP_LEVEL_BLOCK`,
`UNKNOWN_VERSION`, `PACK_NOT_RESOLVED`, and the three `CONTRACT_*_NOT_IN_GRAPH` auditability
signals do not fail a build. If your policy is that they should, your pipeline must say so; the
tool will not.

Second, **read the exit code as a class, not a number**. A 2 is a structural refusal — the tool
declined to reason about the input at all. A 1 is a governance verdict. Conflating them hides
parse failures behind policy failures.

Third, **treat a passing evidence validation as a scoped statement**. The report's own limitation
block says what it means: the supplied records conform to the exact contract revision. It does not
say the events happened, that they are complete, or that anything enforced the contract at run
time.
