# FACT PACK 01 — Nornyx Core Language and Toolchain

Audit target: repository `/home/user/nornyx`, git HEAD `70d2b40` ("Merge pull request #56 … m2d-legacy-compatibility-shim"), package version **1.11.0** (`pyproject.toml:7`, `nornyx/__init__.py:3`, `manifest.json:4`). Audit date: 2026-08-03.

Status vocabulary used throughout:

- **IMPLEMENTED** — behavior exists in code, usually with tests.
- **ROADMAP/PLANNING** — described in design/planning documents only; not code.
- **NON-GOAL** — explicitly declared out of scope.

---

## 1. Identity and versions

- Nornyx self-describes as "A generalized agentic contract/control-plane language for governed AI software delivery" (`README.md:8`) and, in the short thesis, "a context-native agentic engineering language … the executable contract layer for human-model software delivery" (`docs/28_NORNYX_PRODUCT_THESIS_SHORT.md:3,55`).
- **Package (distribution) version: 1.11.0**; **language/schema version: 1.0** — these are explicitly independent axes: "The package (distribution) version is independent of the language/schema version" (`docs/VERSIONING.md:6-9`; table at lines 13-22). `manifest.json:4-5` records `"version": "1.11.0"` and `"language_version": "1.0.0"`.
- Other version axes (`docs/VERSIONING.md:13-22`): Agentic integration SPI **1.2** (`nornyx/agentic/authz.py:66`: `SPI_VERSION = "1.2"`), `agentic_network_governance` module **0.2.0**, agentic schema targets **v1**, network lock format **1.0** and generation format **1.0** (`nornyx/agentic_artifacts.py:36-37`), runtime-events schema **1.1** with 1.0 still supported (`nornyx/agentic_artifacts.py:43-44`).
- Package-version synchronization touches exactly **seven equality-enforced locations**, enforced by tests (`docs/VERSIONING.md:26-47`; tests named there: `tests/test_documentation_consistency.py`, `tests/test_governance_compatibility_corpus.py`, `tests/test_governance_extension_spec.py`, `tests/test_manifest_metadata.py`).
- Supported Python: 3.10-3.13 (`docs/VERSIONING.md:70-74`; `README.md:31`). Runtime dependencies: PyYAML, jsonschema, referencing (`pyproject.toml:27`).
- **Inside `.nyx` documents the version marker is still `nornyx: "0.1"` or `"0.2"`** — the v1.0 schema explicitly says "The .nyx document versions remain 0.1 and 0.2 for compatibility while this schema names the stable generalized agentic contract-language surface" (`schemas/nornyx_v1_0.schema.json:17`, `properties.nornyx` at lines 22-29). The checker warns `UNKNOWN_VERSION` for anything else (`nornyx/checker.py:599-609`).

## 2. The .nyx language

### 2.1 Syntax

- v0.1 is **frozen** and deliberately **YAML-compatible**: "v0.1 uses a YAML-compatible syntax to keep early effort focused on control-plane semantics instead of parser complexity" (`docs/01_LANGUAGE_SPEC_v0_1.md:5`). File extension `.nyx` (line 9). "The `.nyx` file is the source of truth. Generated artifacts are compatibility outputs." (line 219).
- A formal-grammar sketch (`FORMAL_GRAMMAR_V0_1`) is embedded in `nornyx/schema_model.py:29-47` and printable via `nornyx schema --format grammar` (`nornyx/cli.py:391-394`).
- A move to a dedicated (non-YAML) parser is **ROADMAP only**: "Future versions may move from YAML-compatible syntax to a dedicated parser" (`docs/01_LANGUAGE_SPEC_v0_1.md:276-277`); the "full LLM-native engineering language" (code modules, typed data models, services, effect/capability system, connector runtime, LSP, Registry, Studio) is the **final target**, research-only under RFC-0003 (`docs/16_FINAL_LANGUAGE_TARGET.md:3-9,13-49`).

### 2.2 Top-level blocks (the ACTUAL set)

Core top-level blocks — from `CORE_TOP_LEVEL_BLOCKS` (`nornyx/checker.py:32-48`) and matching the v1.0 JSON schema properties (`schemas/nornyx_v1_0.schema.json:21-149`):

```
nornyx, project, constitution, intents, contexts, skills, policies, agents,
harnesses, traces, evals, evidence, approvals, budgets, goals
```

- List blocks (entries are mappings with required `name`): `intents, contexts, skills, policies, agents, harnesses, traces, evals, approvals, budgets` (`nornyx/checker.py:7-18`); `goals` is a list of goal objects keyed by `id`. Mapping blocks: `constitution`, `evidence` (`nornyx/checker.py:30`).
- Deferred **extension** blocks tolerated by the checker (`EXTENSION_TOP_LEVEL_BLOCKS`, `nornyx/checker.py:50-62`): `experimental, graph, contracts, governed_package, adapters, connectors, guardrails, capabilities, incidents, containment, supply_chain`. Spec: "These blocks do not define stable v0.1 runtime behavior" (`docs/01_LANGUAGE_SPEC_v0_1.md:40-57`).
- The stable **general core** is fixed at twelve concepts: Intent, Agent, Policy, Eval, Approval, Evidence, Context, Artifact, Graph, Goal, Budget, Trace (`docs/47_NORNYX_STABLE_GENERALIZED_CONTRACT_LANGUAGE_v1_0.md:29-48`). Note "Artifact" is a concept, not a top-level block.
- Goal entries require `id, phase, goal, scope, non_goals, validation, evidence, approval, stop_rules` (`schemas/nornyx_v1_0.schema.json:231-257`; enforced in `nornyx/checker.py:761-818`).

### 2.3 Closed-schema behavior

All three document schemas set **`"additionalProperties": false` at the top level** — unknown top-level blocks fail JSON-schema validation — while individual blocks stay open (`additionalProperties: true`) inside: `schemas/nornyx_v1_0.schema.json:20`, `schemas/nornyx_v0_1.schema.json:10`, `schemas/nornyx_v0_2.schema.json:10`. The Python checker mirrors this more leniently: unknown top-level keys yield a `UNKNOWN_TOP_LEVEL_BLOCK` **warning**, not an error (`nornyx/checker.py:828-839`). Schema registry: `compat`/`0.1` → `nornyx_v0_1.schema.json` (still the default/compat target), `0.2`, `1.0` (`nornyx/schema_model.py:20-27`). Schemas are bundled in the wheel with a repo-root fallback (`nornyx/schema_model.py:13-17`; fixed in release 1.1.5, `CHANGELOG.md:628-634`).

The v1.0 schema also declares its own safety boundary as metadata: `"x-nornyx-safety-boundary": "Stable schema metadata only; does not publish packages, deploy software, enable live connectors, execute graph edges, call models, grant automatic approvals, or unlock GOAL-100."` (`schemas/nornyx_v1_0.schema.json:16`).

### 2.4 Taint and authority (context trust model)

- Contexts may declare `include`, `exclude`, `authority` (ordered glob patterns), `budget`, and a `taint` mapping per channel — see the real example `examples/governed_delivery_control_plane.nyx:23-46` (taint values there: `trusted_repo_file`, `authoritative_repo_file`, `untrusted`).
- The **default trust channels** are hardcoded in `nornyx/context_builder.py:9-30` (`DEFAULT_TRUST_CHANNELS`): `repo` → taint `trusted_repo_file` (trusted, may_define_policy false); `authoritative_repo` → `authoritative_repo_file` (authoritative, may_define_policy **true**); `user_prompt` and `external_web` → `untrusted` (may_define_policy false). A file matching an `authority` pattern is assigned the `authoritative_repo` channel with its rank (`nornyx/context_builder.py:67-78`); a context's declared `taint:` mapping overrides the channel default per channel (`nornyx/context_builder.py:81-87,136`).
- Trust rules recorded in every context pack: "untrusted context cannot define policy", "untrusted context cannot request privileged tool use", "higher-authority repo context wins over lower-authority context on conflict" (`nornyx/context_builder.py:97-101`) — and, critically, the pack itself states **"Authority rank is advisory metadata until a later enforcement goal."** (`nornyx/context_builder.py:170`). So the taint/authority model is IMPLEMENTED as metadata + provenance, with enforcement declared advisory.

### 2.5 Rule syntax — the actual recognized rule atoms

Policies use either shorthand `rules:` strings or explicit `deny:`/`require:` lists. `normalize_policy_rules` (`nornyx/policy_runtime.py:83-108`) recognizes exactly the prefixes `deny ` / `deny:` and `require ` / `require:`; any other rule string is bucketed into `require` (line 103-107). Rule tokens are free-form strings; **only deny rules are pattern-matched**, in `_matches_deny_rule` (`nornyx/policy_runtime.py:185-203`), which recognizes these substrings in the rule and step text:

- rule contains `production` → blocks steps mentioning `production|prod|deploy|release`;
- rule contains `secret` → blocks steps mentioning `secret|token|credential`;
- rule contains `destructive` → blocks `delete|destroy|drop|wipe|reset|remove`;
- rule contains `connector` → blocks connector-kind steps;
- rule contains `self_modification`/`self-modification` → blocks matching step text.

`require` rules are never executed; they are recorded as `pending_evidence` (`nornyx/policy_runtime.py:271-274`; documented in `docs/05_SECURITY_MODEL.md:41-42`). Canonical example rules: `deny secrets_to_llm`, `deny production_write_without_approval`, `require tests_if_code_changed`, `require evidence_if_harness_completed`, `require supply_chain_check_if_dependency_added` (`examples/governed_delivery_control_plane.nyx:62-69`).

Capability semantics (`nornyx/policy_runtime.py:111-137,278-357`): tool/connector/model steps are **deny-by-default** unless a matching `capabilities` declaration exists (`CAPABILITY_NOT_DECLARED`), declared capabilities default to `approval_required: true` (`CAPABILITY_APPROVAL_REQUIRED`), and connector/model steps additionally require a guardrail declaring one of `no_secrets|no_pii|schema_valid|output_schema` (`GUARDRAIL_REQUIRED_FOR_EXTERNAL_USE`, lines 224-231,324-334). Every policy report embeds `"default_capability_mode": "deny_unless_declared"` and a safety block asserting nothing was executed (`nornyx/policy_runtime.py:441-458`). Tests: `tests/test_policy_runtime.py`.

### 2.6 The `ref` mechanism for shared policies (IMPLEMENTED, shipped in 1.3.0)

A policy may reference one canonical definition instead of copying rules:

```yaml
policies:
  - name: SafeDeliveryPolicy
    ref: org_policies.nyx#SafeDeliveryPolicy
```

(verbatim from `nornyx/examples/governed_service.nyx:11-13`). Semantics (`nornyx/parser.py:111-177`):

- `ref` is `<path>#<PolicyName>`; the path is a **local** file relative to the contract — either a `.nyx` contract (policies list) or a workspace manifest (policies mapping) (`_extract_policy_rules`, lines 93-108);
- resolution happens **at load time, offline**, compiling the ref into inline `rules` and dropping the `ref` key, "so every downstream consumer — checker, generator, drift gate — sees a normal policy" (docstring lines 117-126);
- fail-closed errors: both `ref` and `rules` set (line 139-140), malformed ref (143-145), **remote/device ref sources rejected** (147-149), missing source file (154-155), invalid YAML/non-mapping source (156-166), policy not found (169-171).
- Tests: `tests/test_policy_ref.py` (7 tests). Changelog: `CHANGELOG.md:544-553` (1.3.0). README shows the workspace-manifest variant `ref: ../governance/nornyx.workspace.yaml#SafeDeliveryPolicy` (`README.md:165-176`).

### 2.7 Duplicate keys and the `on:` fix (parser hardening)

`NornyxSafeLoader` (`nornyx/parser.py:15-61`):

- **rejects every duplicate mapping key** at any nesting level (ConstructorError, lines 24-48);
- restricts YAML implicit booleans to `true/false` only, so `on/off/yes/no` remain string keys — fixing `- on: test_failure` parsing as `{True: ...}` (lines 15-22,51-61; released as 1.0.1, `CHANGELOG.md:687-693`; regression test `tests/test_parser_on_key_regression.py`);
- rejects remote/device-backed contract paths before any filesystem access (line 70-71).

## 3. The checker

`check_document` (`nornyx/checker.py:584-841`) returns `Diagnostic` dataclasses with `level, code, message, path, hint` (`nornyx/errors.py:4-22`). **Diagnostic codes are UPPER_SNAKE strings, not numeric (there is no `NYX###` scheme in core).** Full set of literal codes in `checker.py` (grep-extracted):

`CONTEXT_WITHOUT_INCLUDE, CONTRACT_APPROVAL_NOT_IN_GRAPH, CONTRACT_BUDGET_NOT_IN_GRAPH, CONTRACT_WITHOUT_EVIDENCE_NODE, DUPLICATE_GRAPH_EDGE, DUPLICATE_GRAPH_NODE_ID, GOAL_WITHOUT_VALIDATION, GRAPH_EDGE_WITHOUT_RELATION, GRAPH_EVIDENCE_NODE_WITHOUT_REF, GRAPH_SELF_EDGE, HARNESS_WITHOUT_FLOW, INVALID_AGENT, INVALID_BLOCK_ENTRY, INVALID_BLOCK_TYPE, INVALID_CONTRACTS_BLOCK, INVALID_CONTRACT_ENTRY, INVALID_EVIDENCE_REQUIRED, INVALID_FLOW_STEP, INVALID_GOAL, INVALID_GOVERNED_PACKAGE, INVALID_GRAPH_BLOCK, INVALID_GRAPH_EDGE(S), INVALID_GRAPH_NODE(S), INVALID_GRAPH_RELATION_PAIR, INVALID_HARNESS, INVALID_MAPPING_BLOCK, INVALID_PROJECT, MISSING_CONTRACT_NAME, MISSING_GOAL_APPROVAL, MISSING_GOAL_EVIDENCE, MISSING_GOAL_ID, MISSING_GOAL_OUTCOME, MISSING_GOAL_PHASE, MISSING_GRAPH_NODE_ID, MISSING_GRAPH_NODE_KIND, MISSING_PROJECT_NAME, MISSING_TOP_LEVEL_BLOCK, UNKNOWN_AGENT_REFERENCE, UNKNOWN_CONTEXT_REFERENCE, UNKNOWN_CONTRACT_APPROVAL_REFERENCE, UNKNOWN_CONTRACT_BUDGET_REFERENCE, UNKNOWN_CONTRACT_GRAPH_REFERENCE, UNKNOWN_EVAL_REFERENCE, UNKNOWN_GRAPH_NODE_REFERENCE, UNKNOWN_GRAPH_REF_REFERENCE, UNKNOWN_GRAPH_RELATION, UNKNOWN_POLICY_REFERENCE, UNKNOWN_SKILL_REFERENCE, UNKNOWN_TOP_LEVEL_BLOCK, UNKNOWN_VERSION` — plus generated codes `MISSING_<SINGULAR>_NAME` (e.g. `MISSING_POLICY_NAME`, `nornyx/checker.py:192-201`) and `MISSING_/INVALID_GOAL_<FIELD>` (`nornyx/checker.py:205-239`). CLI adds `PARSE_ERROR` (exit 2) and `AS_OF_INVALID` (exit 2) (`nornyx/cli.py:148-171`).

What is validated (matches the spec list at `docs/01_LANGUAGE_SPEC_v0_1.md:258-273`):

- required top-level blocks (`nornyx`, `project`), project name, list/mapping block shape;
- named-entry shape and required `name` per list entry;
- reference integrity: agent→skill, agent→policy, harness→context, harness flow step→agent/eval (`nornyx/checker.py:653-728`);
- graph: node id/kind required, duplicate node ids, edge endpoints must be declared nodes, `ref` targets must exist in the matching named block (kind→block map at `nornyx/checker.py:120-141`), evidence nodes should carry refs;
- **relation typing**: 23 recognized relations with allowed source/target kind pairs in `GRAPH_RELATION_RULES` (`nornyx/checker.py:144-168`) — e.g. `governs: policy → {agent, harness, adapter, connector, goal}`, `gated_by: {goal, agent, harness, artifact, module} → approval`, `has_skill: agent → skill`, `depends_on: * → *`. Unknown relations warn; wrong pairs error (`INVALID_GRAPH_RELATION_PAIR`);
- contracts: node refs, approval/budget references must resolve to declared approvals/budgets; auditability warnings when approvals/budgets/evidence are not represented as graph nodes (`nornyx/checker.py:452-581`);
- goals: full bounded-goal shape incl. `non_goals` and `stop_rules`;
- unknown top-level keys → warning.

Errors vs warnings: `has_errors` gates exit codes (`nornyx/checker.py:844-845`); `nornyx check` exits 1 on errors, 2 on parse/`--as-of` failure (`nornyx/cli.py:148-210`). Duplicate keys are rejected by the parser, unknown fields **inside** blocks are not checked by the core checker (blocks are open). Tests: `tests/test_parser_checker.py` (21 tests), `tests/test_graph_demo_expansion.py`.

Pack-aware checking: `nornyx check` also composes governance (profile/modules) for the document, suppresses `UNKNOWN_TOP_LEVEL_BLOCK` for module-contributed blocks, and appends governance diagnostics; `--as-of` pins the evaluation instant and **fails closed** on malformed/naive timestamps (`AS_OF_INVALID`, exit 2 — never a silent fallback to the live clock) (`nornyx/cli.py:133-210`; `CHANGELOG.md:95-102`, 1.9.0).

## 4. Generators, drift gates, workspace

### 4.1 `nornyx generate` (`nornyx/generator.py:76-182`)

Exact artifact set generated from one `.nyx`:

1. `AGENTS.md` (header "This file is generated. Edit the `.nyx` source instead.", intents + agent profiles) — lines 88-103;
2. `skills/<SafeName>/README.md` per skill — lines 105-116 (names sanitized by `_safe_segment`, line 18-21);
3. `context.yaml`, `harness.yaml`, `policy.yaml`, `evals.yaml`, `trace.yaml`, `goals.yaml` (block dumps, `sort_keys=False`) — lines 118-129;
4. per-goal `task_packets/<GOAL-ID>.md` and `goal_ledger.md` when goals exist — lines 131-159;
5. `evidence_contract.md` — lines 161-168;
6. `nornyx_generation_manifest.json` with schema `nornyx.generation_manifest.v0.1`, sorted `source_blocks`, sorted artifact paths, and **per-artifact sha256 hashes** — lines 170-181.

(The README's shorthand lists `AGENTS.md · skills/ · harness.yaml · policy.yaml · evals.yaml · context.yaml · evidence_contract.md`, `README.md:16-19,56`; the generator additionally writes `trace.yaml`, `goals.yaml`, task packets, goal ledger, and the manifest.)

Determinism mechanisms: all writes force **LF newlines** so output is byte-identical across platforms (`_write`, `nornyx/generator.py:11-15`; 1.1.0, `CHANGELOG.md:683-685`); artifact paths and hash lists are sorted (lines 28-36); **no timestamps** appear in generated artifacts. Tests: `tests/test_generator_hardening.py`.

### 4.2 Drift gates (two, both IMPLEMENTED)

- **Dev-side baseline gate** `nornyx/generation_drift.py`: regenerates two default cases (`examples/governed_delivery_control_plane.nyx`, `examples/nornyx_roadmap_goals.nyx`) into a temp dir and compares the generation manifest against committed baselines `tests/fixtures/generated_drift/*.json` (schema `nornyx.generated_drift_baseline.v0.1`; `DEFAULT_DRIFT_CASES` lines 24-35; `--update` path lines 104-115).
- **User-facing full-output gate** `nornyx drift <contract> --out <dir>` (`nornyx/repo_drift.py`): regenerates to a throwaway dir and compares **every** artifact by sha256 from the manifest against the committed directory, reporting `missing/changed/stray/ok`; motivation documented in the module docstring — an AGENTS.md-only diff "stays green when policy.yaml changes" (`nornyx/repo_drift.py:1-9`; report schema `nornyx.repo_drift_report.v0.1`). Exit nonzero on drift (`nornyx/cli.py:349-355`). Tests: `tests/test_repo_drift.py`.

### 4.3 Workspace manifests (`nornyx.workspace.yaml`) — cross-repo policy consistency

`nornyx/workspace.py` (module docstring, lines 1-17): a workspace manifest declares canonical policies once (`policies:` as mapping name→rules) and lists `members:` (contract paths); `check_workspace` verifies each member's named policy equals the canonical rule set (compared as normalized `deny X`/`require X` sets, lines 64-92). `--write` sync mode surgically rewrites only the matched policy's rule block, preserving comments and other blocks; missing policies/files are "left for a human … sync edits existing policies, it does not invent new blocks or files" (lines 218-225). Report schema `nornyx.workspace_report.v0.1`; statuses `pass|synced|drift`; local files only, no network (line 16). All paths screened through the governance path-safety loader (lines 43-61,227-241). Tests: `tests/test_workspace.py` (15 tests). History: 1.1.6-1.1.9 fixed real sync bugs (`CHANGELOG.md:583-627`).

## 5. CLI surface (`nornyx/cli.py:1371-1750`, prog `nornyx`, described as "Nornyx v0.1 CLI scaffold")

Full subcommand list with key flags:

| Command | Key flags / notes |
|---|---|
| `check <file>` | `--as-of` (fail-closed ISO-8601); pack-aware governance evaluation |
| `examples` | `--out` (copies bundled `.nyx` examples) |
| `generate <file>` | `--out` (default `generated`) |
| `package scan\|generate\|validate\|register\|radar\|evidence import (syft\|gitleaks)` | governed-package profile; scanner never executes payloads (`cmd_package_scan` prints `"package_payload_executed": false`, `nornyx/cli.py:281-300`) |
| `drift <file>` | `--out`, `--json` — full-output drift gate |
| `workspace-check` | `--manifest`, `--write` (sync), `--quiet`, `--json` |
| `goal-plan <file>` | `--out` |
| `schema` | `--format json\|grammar`, `--version compat\|0.1\|0.2\|1.0` |
| `context-build <file>` | `--repo`, `--out`, `--include-content` |
| `harness-run <file>` | `--harness`, `--repo`, `--out`, `--include-content` — "Plan a safe local harness run manifest" (planning, not execution) |
| `policy-check <file>` | `--harness`, `--out` — local policy/guardrail/capability decisions |
| `eval-run <file>` | `--eval`, `--results`, `--repo`, `--out`, `--strict` |
| `eval-import promptfoo <report>` | `--eval-name` (required), `--subject-revision`, `--out` |
| `connector-plan <file>` | `--out`, `--strict` — safe local connector/plugin adapter manifest |
| `editor-manifest`, `syntax`, `lsp-diagnostics <file>`, `complete [file] --path --prefix`, `symbols <file>` | editor/LSP tooling; `complete` emits LSP-shaped items (`README.md:58-77`) |
| `release-check`, `stable-language-check` | `--repo`, `--target-version`, `--approved`, `--strict` — local readiness reports; `--approved` records human approval |
| `language-evolution` | `--repo`, `--strict` — research report |
| `evidence-pack` | `--out` scaffold |
| `agentic-network generate\|lock\|lock-check\|evidence-validate` | `--out/--artifacts/--lock/--events/--as-of/--strict/--json`; deterministic artifacts + content-addressed lock + runtime-event evidence validation |
| `profiles [list\|inspect\|validate\|resolve\|compatibility]` | `--json`; `resolve --lock` writes `nornyx.profiles.lock`; lock mismatch exits **2** (`nornyx/cli.py:984-1025,1136-1147`) |
| `modules list\|inspect\|validate` | `--json` |
| `governance resolve\|explain\|matrix <file>` | `--as-of`, `--json` |
| `evidence validate <path>` | `--as-of`, `--json` |
| `doctor` | `--repo`, `--json` |
| `init` | `--profile <builtin>` XOR `--profile-path <local pack>`, `--name` (required), `--out`, `--force` (default profile `ai_coding`, `nornyx/cli.py:1296-1300`) |
| `fmt <file>` | `--write`, `--check` |
| `explain <file> [symbol]` | `--json` |
| `adopt status\|init-lite` | `--repo`, `--project`, `--out`, `--force` |
| `--version` | prints package version |

Public/stability boundary: `docs/public-boundary-policy.md` governs **content neutrality** (no private product/customer names anywhere in the public repo), not API stability. API/CLI stability for governance surfaces is defined in `docs/GOVERNANCE_CLI_AND_API.md`: `nornyx.governance.__all__` is the intentional public Python surface; "Public behavior will not be removed without a changelog deprecation notice lasting at least two package minor releases and six months" (lines 66-92); exit-code contract 0/1/2 with lock failures = 2 (lines 42-53); diagnostic namespaces `PACK_*, RULE_*, GOVERNANCE_*, APPROVAL_*, EVIDENCE_*, SOD_*, EXCEPTION_*, CHANGE_*, ARCH_*, AN_*` (lines 55-57). It also states flatly: "`nornyx governance analyze` does not exist" (line 10). Tests: `tests/test_governance_cli.py`, `tests/test_public_boundary.py`, `tests/test_readme_commands.py`, `tests/test_cli_dx.py`, `tests/test_cli_examples.py`, `tests/test_cli_schema.py`.

## 6. Profiles and governance modules

### 6.1 Catalog (`nornyx/profiles_data/catalog.json`)

- **13 built-in profiles**: minimal, standard, ai_coding, regulated, legacy_upgrade, nornyx_language, agentic_repo_harness, telecom_ops, business_ops, ai_governance, finance_ops, architecture_governance, agentic_network. Base: first six. **v0.3 domain profiles (projected)**: ai_coding, agentic_repo_harness, telecom_ops, business_ops, ai_governance, finance_ops. **v1-only** (no v0.3 projection): architecture_governance, agentic_network.
- **7 modules**: evidence_integrity, human_approval, separation_of_duties, exception_management, change_control, architecture_conformance, agentic_network_governance. The module catalog is "frozen at six for this program" per ADR-0031 (`CHANGELOG.md:404-408`) — agentic_network_governance was added afterwards under the AN track (so the shipped count is seven; the "six" refers to the GSA-era foundational set).
- Pack schemas: `schemas/profile_pack_v1.schema.json` (closed, 26 required fields incl. `provenance`, `integrity`, `starter_fragments`, `validation_rules`, `compatibility`, `non_goals`) and `schemas/governance_module_v1.schema.json` (closed; required incl. `dependencies`, `block_schemas` via properties, `rules`, `safety`). The v0.3 legacy pack shape remains `schemas/domain_profile_pack.schema.json`; "The 12 structured v1 packs under `nornyx/profiles_data/` are authoritative and are included in the wheel … the old root `profiles/*.yaml` mirrors were removed to prevent dual-source drift" (`docs/40_NORNYX_DOMAIN_PROFILES_v0_3.md:44-56`).

### 6.2 Composition, precedence, provenance (IMPLEMENTED — `nornyx/governance/`)

- `compose_governance(registry, profile_identity, module_ids, lock)` resolves the profile, orders modules by **dependency order**, rejects declared conflicts, and composes `[*modules, profile]` (profile layered last) (`nornyx/governance/composition.py:262-275`).
- Composition is **deterministic and monotonic**: fields merge by ordered union; conflicting scalar fields raise `PACK_MONOTONICITY_CONFLICT`; deny/require lists union with strict canonical-string checks (`composition.py:48-120`). Caps: 2000 composed rules, 64 block schemas, 64 structural checks (`composition.py:25-27`); per-pack 200 rules / composition 2000, duplicate in-pack ids fatal `PACK_DUPLICATE_ID` (`CHANGELOG.md:481-484`).
- **Provenance**: every composed element carries a record with `element_kind, element_id, source_id, source_version, layer (module|profile)` plus the pack's `PackProvenance` — `author, source_tier, source_revision, source_path` (`composition.py:30-45`; `nornyx/governance/models.py:46-58`). Source tiers: `builtin | project | org | explicit_path` (`schemas/profiles_lock_v1.schema.json`). Discovery order for a project: `.nornyx/profiles/` and `.nornyx/modules/` under the contract's directory, then built-ins (`docs/GOVERNANCE_CLI_AND_API.md:25`; `nornyx/governance/runtime.py:25-60`).
- **Locks**: `nornyx.profiles.lock` (schema `nornyx.profiles_lock.v1`) records `{id, version, source_tier, content_hash (sha256:…), path_hint}` per resolved pack, deliberately **timestamp-free** so "identical resolution inputs produce byte-identical locks" (`schemas/profiles_lock_v1.schema.json:$comment`). Locks are verified by `nornyx check`/`governance`/`profiles resolve` when present and never auto-rewritten; mismatch codes `PACK_LOCK_MISMATCH|SET_MISMATCH|DUPLICATE_ID|INVALID` exit 2 (`nornyx/cli.py:1136-1147`). Lock files bounded to 512 KiB strict UTF-8 JSON, duplicate keys rejected (`docs/GOVERNANCE_CLI_AND_API.md:38-40`).
- **Effective governance**: `CompositionResult.to_effective_dict()` emits the closed `nornyx.effective_governance.v2` schema (`schemas/effective_governance_v2.schema.json`) with required keys `schema, profile, modules, required_blocks, block_schemas, structural_checks, policies, evidence_requirements, approval_requirements, evaluations, rules, non_goals, starter_fragments, provenance, diagnostics`; `approval_requirements` entries are either `effective_approval_v1` or `normalized_approval.v2` payloads (lines 45-56). `to_dict()` stays the v1 compatibility view (`docs/GOVERNANCE_CLI_AND_API.md:110-115`).
- Unresolvable `project.profile` degrades to a `PACK_NOT_RESOLVED` **warning** (backward compatible), but explicit `project.modules` selections are **fail-closed** (`CHANGELOG.md:459-464`; `nornyx/governance/runtime.py:126`).
- `nornyx init` starters: profile starter fragments render a checkable document; sentinel-based project-name substitution and deterministic fragment merge with conflict errors (`nornyx/profiles.py:246-292`). v0.3 projection guarantees profiles never add mandatory core concepts and always declare non-goals blocking "live agent runtime", "automatic approvals", "production deployment" (`nornyx/profiles.py:161-169`).
- Tests: `tests/test_governance_runtime.py`, `tests/test_governance_foundations.py`, `tests/test_governance_compatibility_corpus.py`, `tests/test_legacy_governance_shim.py`, `tests/test_governance_audit_*` (path/lock security, structural semantics, approval integrity, cross-platform), `tests/test_governed_package_profile.py`.

## 7. Approval, exception, and separation-of-duties models

### 7.1 Schemas

- `governance_approval_model_v1.schema.json` — `nornyx.normalized_approval.v1`; **marked draft**: `$comment: "DRAFT internal normalization contract only…"`. Fields: required/eligible roles, `denied_actor_types`, `denied_execution_surfaces`, required evidence, actions, `timing` enum (`before_action|before_merge|before_release|before_external_write|unspecified|legacy_text`), optional exact `revision_binding` (kind `git|artifact_hash|package_manifest|other`, `exact: const true`), `expires_at`, `resolution` enum, `normalization_diagnostics` (codes `^APPROVAL_[A-Z0-9_]+$`), and a `source` record preserving the raw shape (six shapes incl. `legacy_goal_text`).
- `governance_approval_model_v2.schema.json` — `nornyx.normalized_approval.v2`; adds required `accountable_authority`, `exact_revision_required`, `expires_after` (relative), and a source `binding` sha256; bounded sizes.
- `effective_approval_v1.schema.json` — `nornyx.effective_approval.v1`: the composed approval envelope adding `operation`, `decisions`, `sources` (bounded retained-source lineage); verified via public `trusted_effective_approval` which "replays its bounded retained-source composition" (`docs/GOVERNANCE_CLI_AND_API.md:94-120`).
- `governance_exception_v1.schema.json` — `nornyx.governance_exceptions.v1`: closed exception records requiring `id, control, reason, scope, risk_tier (low|medium|high|critical), requester, accountable_owner, approving_authority, compensating_controls, evidence, starts_at, expires_at, renewal_policy (prohibited|manual_reapproval), closure_evidence, status (requested|approved|active|expired|closed|rejected)`.
- `separation_of_duties_v1.schema.json` — `nornyx.separation_of_duties.v1`: assignments with human-identity patterns (`user:|human:|person:` prefixes allowed).

### 7.2 Enforcement in code (IMPLEMENTED)

- **"AI cannot approve" is intrinsic, not configurable.** `CORE_DENIED_ACTOR_TYPES = ("ai_tool", "execution_surface", "autonomous_agent", "model", "connector", "generated_output")` with comment "These categories are intrinsically unable to hold approval authority. Packs and documents cannot redeclare them as human actors." (`nornyx/governance/approvals.py:34-43`). `is_non_human_authority` also catches exact tokens `tool, agent, system, service, external_service` and prefixes `agent:, model:, connector:, tool:, system:, service:, …` (lines 44-59,95-101). Declaring a core-denied actor as eligible/required normalizes as invalid `APPROVAL_CORE_DENIED_ACTOR_ELIGIBLE` (line 426-433); non-human `accountable_authority` → `APPROVAL_NON_HUMAN_AUTHORITY` (494-499). Composition always unions the core denials back in (lines 806-816).
- Structural checks in `nornyx/governance/structural.py` enforce: approvals must explicitly deny all non-human authority categories (lines 598-643), SOD approvers must be human/joined to the change with self-approval and independence-overlap rejection (lines 1175-1186 area; Stage 4 in `CHANGELOG.md:309-320`), high-risk roles reject non-human roles (2328-2341), evidence-authority chains must pass (`CHANGELOG.md:318-321`).
- The runtime SPI denies too: `DecisionCode.APPROVAL_NON_HUMAN` — "AI systems, tools, models, and execution surfaces cannot approve." (`nornyx/agentic/authz.py:426,1042`); agentic-network identities must be `authority: non_human` with `can_approve: false` (`nornyx/governance/agentic_network.py:1035-1039`); runtime-event validation flags `AN_EVT_APPROVAL_NON_HUMAN` (`nornyx/agentic_evidence.py:730`), and since 1.9.0 the human-approver rules are scoped to `approval_granted` only so a *refused* non-human approval can appear in valid evidence (`CHANGELOG.md:138-149`).
- Module data: `module_human_approval.yaml` requires roles `reviewer` (eligible + `security_reviewer`), denies all six actor types, requires `approval_record` evidence, `timing: before_action`, `exact_revision_required: true`, `expires_after: PT24H` (`nornyx/profiles_data/module_human_approval.yaml:33-57`).
- Tests: `tests/test_governance_audit_approval_integrity.py`, `tests/test_governance_security_assurance.py`, `tests/test_agentic_authz.py`, `tests/test_agentic_network_governance.py`, `tests/test_change_governance.py`.

## 8. Context builder, canonicalization, hashing, path security

- **Context packs** (`nornyx context-build`): schema `nornyx.context_pack.v0.1`; every entry carries `sha256` of file bytes, byte count, taint/channel/trust level, authority rank/pattern, and a `provenance` record (`source_type: repo_file`, `repo://` URI, repo root, sha256) (`nornyx/context_builder.py:105-174`). Content embedding is **off by default** ("keeps the pack safer and smaller", lines 107-110). Ignored dirs: `.git, .venv, node_modules, __pycache__, .pytest_cache, generated` (line 34). Test: `tests/test_context_provenance.py`.
- **Canonicalization for agentic artifacts/locks** (`nornyx/agentic_artifacts.py:140-156`): canonical bytes = `json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False)` UTF-8; digests are `"sha256:" + hexdigest`; rendered artifacts are sorted, 2-indent JSON + trailing newline — **timestamp-free** deterministic outputs (CHANGELOG AN-003, lines 204-210: "canonical, timestamp-free JSON declarations"). Generation manifests and repo drift both use plain `hashlib.sha256` over file bytes (`nornyx/generator.py:24-25`, `nornyx/repo_drift.py:26-27`). Pack `content_hash` integrity is verified on load (`nornyx/governance/loader.py:155,316`).
- **Path security** (`nornyx/path_security.py:15-52`): a deliberately **lexical, host-independent** rejector — URI schemes (except drive letters), UNC `\\`, NT device prefixes (`\??\`, `\Device\`, `\GLOBAL??\`), and Windows device component names (CON, PRN, AUX, NUL, COM1-9, LPT1-9, incl. superscript digits, extensions, ADS suffixes) anywhere in the path. Used before any filesystem access by the parser (`nornyx/parser.py:70-71`), policy refs (`parser.py:147-149`), workspace, CLI pack/evidence paths. The governance loader additionally rejects every unresolved symlink component from the filesystem anchor ("an explicit trust_root can narrow containment but cannot hide a higher ancestor", `docs/GOVERNANCE_CLI_AND_API.md:31-36`). Tests: `tests/test_symlink_support.py`, `tests/test_governance_audit_path_and_lock_security.py`, `tests/test_governance_audit_cross_platform.py`.

## 9. Release history arc (from `CHANGELOG.md`, whole file)

- **1.0.0** — v1.0.0 *GitHub source release* of the generalized agentic contract language (line 695-696). **1.0.1** — parser `on:`/bool fix. **1.1.0** — canonical-repo consolidation; generation drift gate; LF-newline determinism. **1.1.1-1.1.5** — examples consolidated, PyPI-publishable README/metadata (**1.1.2 = first PyPI-publishable release**), bundled examples + `nornyx examples`, onboarding docs, schemas bundled in wheel. **1.1.6** — `nornyx drift` (full-output) + `workspace-check`. **1.1.7-1.1.9** — workspace `--write` sync mode and YAML-indent bug fixes. **1.1.10** — README/PyPI polish.
- **1.2.0** — `--version`, `workspace-check --quiet`, third bundled example; first external contributor credits (@hass-nation). **1.3.0** — **policy `ref`**. **1.4.0** — Governed Package Profile (`package generate|register|radar`), public-boundary policy. **1.5.0** — **declarative governance runtime**: profile/module loading, monotonic composition, closed rule evaluation, approval normalization with intrinsic `ai_tool`/`execution_surface` denial, timestamp-free locks, pack-aware `check`, `profiles` subcommands, package scanner + external evidence import (syft/gitleaks). "Nornyx still does not claim packages are safe." (line 507-509). **1.5.1/1.5.2** — symlink/trust-root security fixes.
- **1.6.0** — an independent audit of a release candidate returned **NO-GO with findings AUD-001…AUD-022**; 1.6.0 is the remediation release (path/lock security invariants, human-only authority hardening, SOD, exception lifecycle fail-closed, compatibility corpus, `modules`/`governance`/`evidence` CLI, exit-code 2 for lock failures, migration markers). **1.6.1/1.6.2** — release-workflow fixes; v1.6.0/v1.6.1 were never on PyPI; **PyPI publication first occurs at 1.6.2** (lines 274-276,283-285). 1.6.2 also ships AN-001 (optional `agentic_network` profile + module).
- **1.7.0** — AN-002…AN-006: delegations/handoffs/relations, deterministic agentic-network artifacts + content-addressed lock + `evidence-validate`, unpackaged reference adapters (CrewAI/LangGraph), governed customer-support example, promptfoo importer, `docs/VERSIONING.md`, 3.10-3.13 CI matrix. **1.8.0** — core `nornyx.agentic` authorization SPI 1.0 (immutable lock-verified `Authorizer`, `EvidenceRecorder`, decision taxonomies; "cooperative Tier 2 only — no agent/approver authentication, no tool execution, no runtime-event truth claim"). **1.9.0** — `check --as-of` fail-closed; recorder canonicalization hardening; adapters dir rename; F1 fix (refused non-human approvals validate). **1.10.0** — runtime-events **1.1** occurrence/attempt semantics, SPI 1.1. **1.11.0** (2026-08-01) — `Authorizer.state` / SPI **1.2**; "Tagging and PyPI publication are performed separately through the approved release workflow" (lines 64-70). Unreleased: M2-D legacy compatibility shim work.
- `manifest.json:75-78` records the *published* package as 1.10.0 (`"package_publication": "1.10.0"`), deployment `not_deployed`, `goal_100: locked`. Release notes files exist for 1.2.0-1.5.2 only (`RELEASE_NOTES_v1.*.md` at repo root).

## 10. Security model — exact claims (`docs/05_SECURITY_MODEL.md`)

- Core assumption (verbatim, lines 3-5): "AI agents may make mistakes. They may also receive poisoned context. Therefore Nornyx should constrain agents by design."
- Nine security layers (lines 8-17): Constitution, Authority, Policy, Capability, Guardrail, Context taint, Trace, Evidence, Containment ("stop conditions, budgets, kill switch").
- Required constraints (lines 19-27, verbatim list): "untrusted context cannot define policy; untrusted context cannot request privileged tool use; secrets cannot be passed to external models; dependency additions require supply-chain check; production mutations require approval; self-modification requires approval; recursive loops must have bounded depth and cost."
- Stated limitation of the policy runtime (lines 29-31): "It is a **read-only decision manifest, not an execution engine**"; "the runtime records decisions but does not execute agents, tools, connectors, models, repairs, arbitrary commands, or approvals" (lines 42-43).
- Adapter/readiness boundaries: adapters must keep `execution_mode: contract_only` and `live_connector_execution: false` (lines 60-70 — enforced as JSON-schema consts, `schemas/nornyx_v1_0.schema.json:205-211`); conformance reports must keep `connectors_enabled: false` and `adapters_executed: false` (lines 72-81); bounded-execution readiness is "readiness … not execution" (lines 83-93).
- Agentic-network boundary (lines 95-106, near-verbatim): "Closed schemas reject endpoints, commands, credentials, token/key material, scripts, expressions, wildcard permissions, inline/remote schemas, and approval-granting fields. Every agent identity is non-human and non-approving. Structural validation fails closed on duplicate/false identity, unknown references, capability escalation, invalid or expired authorization, effective revocation, missing high-risk gates, and sensitive sharing. … Validation performs no socket, DNS, subprocess, framework, model, tool, connector, or source-analysis operation."
- Note carefully what is *not* claimed: constraints like "secrets cannot be passed to external models" are contract-level declarations checked/planned locally; Nornyx "validates declarations and supplied local evidence — it is not an agent runtime … and it does not attest runtime truth" (`README.md:226-229`); "Hash validity proves content binding, not event truth" (`CHANGELOG.md:214-215`; same in `docs/GOVERNANCE_CLI_AND_API.md:84-85`).

## 11. Positioning and non-goals

- What it is: "a generalized agentic contract/control-plane language for governed AI/software delivery … replace scattered control artifacts … with a single `.nyx` source of truth" (`docs/48_NORNYX_POSITIONING.md:3-13`).
- **Declared NON-GOALS** (verbatim, `docs/48_NORNYX_POSITIONING.md:17-25`): "not: a full autonomous runtime; a general-purpose programming language; a LangGraph, CrewAI, or LangChain replacement; a production execution engine; a live MCP/A2A connector runtime; automatic approval or self-modification; regulated/enterprise GOAL-100 promotion." Repeated in `docs/47…v1_0.md:81-91`.
- README scope/safety (`README.md:239-241`): "Nornyx is an **executable specification layer**, not a runtime. It does **not** implement autonomous system modification, production deployment, destructive tool use, credential handling, or arbitrary command execution. The name *Nornyx* is a provisional working brand (no formal legal clearance claimed)." Also: "Nornyx does **not** replace Codex, Claude Code, Cursor, Copilot, CI/CD, or human review" (`README.md:21`).
- Product thesis anti-goals (`docs/28…:31-37`): "another endless config pile / a premature Python replacement / a hidden autonomous execution system / a portal-first product / a proprietary trap around existing tools."
- `manifest.json:32-38` safety boundaries: "No arbitrary shell execution by default; No live LLM calls in v0.1 scaffold; No production deployment; No credential storage; No autonomous self-modification."

## 12. Real contract excerpts for quotation

**(a) Policy rules + constitution — `examples/governed_delivery_control_plane.nyx:7-13,62-69`:**

```yaml
constitution:
  principles:
    - human_authority_over_high_impact_actions
    - evidence_required_for_code_changes
    - no_secret_exposure
    - context_provenance_required
    - no_unapproved_self_modification
...
policies:
  - name: SafeEditPolicy
    rules:
      - deny secrets_to_llm
      - deny production_write_without_approval
      - require tests_if_code_changed
      - require evidence_if_harness_completed
      - require supply_chain_check_if_dependency_added
```

**(b) Context with taint and authority — `examples/governed_delivery_control_plane.nyx:23-46` (abridged):**

```yaml
contexts:
  - name: RepoContext
    include: ["README.md", "docs/**/*.md", "nornyx/**/*.py", "tests/**/*.py", "examples/**/*.nyx"]
    exclude: ["generated/**", "**/.env"]
    authority:
      - "docs/01_LANGUAGE_SPEC_v0_1.md"
      - "docs/05_SECURITY_MODEL.md"
      - "docs/agent/SAFE_COMMANDS.md"
      - "tests/**/*.py"
    taint:
      repo: trusted_repo_file
      authoritative_repo: authoritative_repo_file
      user_prompt: untrusted
      external_web: untrusted
```

**(c) Harness with repair loop and gates — `examples/governed_delivery_control_plane.nyx:89-116` (abridged):**

```yaml
harnesses:
  - name: DevHarness
    context: RepoContext
    flow:
      - agent: Architect
        action: plan
      - agent: Builder
        action: implement
      - tool: tests
        action: run
      - eval: RegressionEval
        action: run
      - evidence: DevEvidence
        action: pack
    repair:
      - on: test_failure
        agent: Builder
        action: repair
        max_attempts: 3
    gate:
      - require: tests.pass
      - require: security.pass
      - require: human_approval_before_merge
```

**(d) Org policy `ref` pair — `nornyx/examples/org_policies.nyx:9-16` and `nornyx/examples/governed_service.nyx:11-13`:**

```yaml
# org_policies.nyx — the single canonical definition
policies:
  - name: SafeDeliveryPolicy
    rules:
      - deny secrets_to_llm
      - require tests_if_code_changed
      - deny nondeterministic_evaluation
      - require evidence_if_harness_completed
      - require human_approval_before_merge

# governed_service.nyx — references, never copies
policies:
  - name: SafeDeliveryPolicy
    ref: org_policies.nyx#SafeDeliveryPolicy
```

**(e) Approvals, budgets, evidence contract — `examples/governed_delivery_control_plane.nyx:135-156`:**

```yaml
evidence:
  required:
    - patch.diff
    - changed_files.zip
    - test_report.json
    - eval_report.json
    - security_report.md
    - risk_update.md
    - approval_log.json

approvals:
  - name: HumanMergeApproval
    required_for:
      - production_deploy
      - policy_change
      - self_modification

budgets:
  - name: StandardDevBudget
    max_tokens: 100000
    max_cost_usd: 15
    max_runtime_minutes: 30
```

## 13. Test coverage map (tests/ — selected, by behavior)

| Behavior | Test file(s) |
|---|---|
| Parser + checker semantics | `tests/test_parser_checker.py` (21 tests), `tests/test_parser_on_key_regression.py` |
| Policy `ref` | `tests/test_policy_ref.py` (7) |
| Generator determinism + drift baselines | `tests/test_generator_hardening.py` (5) |
| Repo drift gate | `tests/test_repo_drift.py` (4) |
| Workspace check/sync | `tests/test_workspace.py` (15) |
| Context pack provenance/taint | `tests/test_context_provenance.py` |
| Schema model/registry | `tests/test_schema_model.py` (11), `tests/test_cli_schema.py` |
| CLI DX, examples, README commands | `tests/test_cli_dx.py`, `tests/test_cli_examples.py`, `tests/test_readme_commands.py` |
| Policy runtime / harness runtime / eval runtime / connector plan | `tests/test_policy_runtime.py`, `tests/test_harness_runtime.py`, `tests/test_eval_runtime.py`, `tests/test_connector_runtime.py` |
| Governance runtime, composition, rules, evidence | `tests/test_governance_runtime.py`, `tests/test_governance_foundations.py`, `tests/test_governance_cli.py`, `tests/test_governance_compatibility_corpus.py`, `tests/test_governance_extension_spec.py` |
| Audit-remediation invariants (paths, locks, approvals, SOD, cross-platform) | `tests/test_governance_audit_*.py` (8 modules), `tests/test_symlink_support.py` |
| Agentic network (artifacts, lock, delegation, evidence, authz, SPI) | `tests/test_agentic_*.py` (12+ modules incl. `test_agentic_authz.py`, `test_agentic_network_artifacts.py`, `test_agentic_network_evidence.py`, `test_agentic_crewai_native.py`) |
| Governed packages | `tests/test_governed_package_profile.py`, `tests/test_wheel_network_guard.py` |
| Docs/version consistency | `tests/test_documentation_consistency.py`, `tests/test_manifest_metadata.py`, `tests/test_public_boundary.py` |

Canonical release validation run for 1.11.0: 1523 passed, 55 skipped, 1575 collected (`manifest.json:57-64`; split is environment-dependent on optional framework extras).

## 14. Implemented vs roadmap vs non-goal — quick orientation

- **IMPLEMENTED (code + tests):** parser (safe loader, dup-key rejection, `on:` fix, remote-path rejection), policy `ref`, checker (all §3 diagnostics, graph relation typing), generator + generation manifest, both drift gates, workspace check/sync, context packs with taint/provenance hashes, policy/harness/eval/connector *planning* runtimes (decision manifests only), profiles/modules/governance composition + locks + provenance, approval normalization with intrinsic non-human denial, exceptions/SOD/change structural checks, governed-package scan/generate/register/radar, agentic-network generate/lock/lock-check/evidence-validate, `nornyx.agentic` SPI 1.2, editor tooling commands, doctor/adopt/fmt/explain.
- **ROADMAP/PLANNING documents (not code):** `docs/03_ROADMAP_TO_v1_AND_BEYOND.md` (strategic version model); `docs/16_FINAL_LANGUAGE_TARGET.md` (full LLM-native language, `nornyx harness run` executing agents, connector runtime, LSP/Registry/Studio); docs 30-39 series (portal contract, evergreen assurance, authoring assistant, adoption pack, etc. are extension/roadmap surfaces — some have data-only implementations, but their operational visions are roadmap); `docs/RFCs/RFC-0003` (language evolution research); `docs/61_NEXT_STRATEGIC_TRACK_AFTER_V101.md`. The 40-47 series documents *shipped* v0.3-v1.0 surfaces (metadata/validation only) and should be read as spec-of-implemented-metadata, not as runtime capability.
- **NON-GOALS (declared):** see §11. Additionally: bounded execution is a "future_proposal_outside_current_program" (`docs/05_SECURITY_MODEL.md:83-86`); GOAL-100 (regulated/enterprise promotion) is locked (`manifest.json:78`); harness/eval/policy commands never execute agents/tools/models.

## 15. Traceability rows

| Claim | Evidence path | Status |
|---|---|---|
| Package version 1.11.0; language/schema version 1.0; axes independent | `pyproject.toml:7`; `manifest.json:4-5`; `docs/VERSIONING.md:6-22` | implemented |
| `.nyx` documents declare `nornyx: "0.1"` or `"0.2"` even under the v1.0 schema | `schemas/nornyx_v1_0.schema.json:17,22-29`; `nornyx/checker.py:599-609` | implemented |
| 15 core top-level blocks + 11 deferred extension blocks | `nornyx/checker.py:32-62`; `schemas/nornyx_v1_0.schema.json:21-149` | implemented |
| Top-level schemas are closed (`additionalProperties: false`); block interiors open | `schemas/nornyx_v1_0.schema.json:20`; `nornyx_v0_1.schema.json:10`; `nornyx_v0_2.schema.json:10` | implemented |
| Checker treats unknown top-level blocks as warnings, not errors | `nornyx/checker.py:828-839` | implemented |
| Diagnostic codes are UPPER_SNAKE strings; no NYX### numeric scheme | `nornyx/checker.py` (all `Diagnostic(...)` calls); `nornyx/errors.py:4-22` | implemented |
| Parser rejects duplicate keys everywhere; `on/off/yes/no` stay strings | `nornyx/parser.py:24-61`; `tests/test_parser_on_key_regression.py` | implemented |
| Policy `ref` `<path>#<PolicyName>`, offline, compiled to inline rules, fail-closed | `nornyx/parser.py:111-177`; `tests/test_policy_ref.py`; `CHANGELOG.md:544-553` | implemented |
| Rule atoms = `deny`/`require` prefixes; unknown rules default into `require` | `nornyx/policy_runtime.py:83-108` | implemented |
| Deny matching keys on production/secret/destructive/connector/self-modification tokens | `nornyx/policy_runtime.py:185-203` | implemented |
| Capabilities deny-by-default; approval required by default; guardrail needed for model/connector | `nornyx/policy_runtime.py:111-137,278-357`; `docs/05_SECURITY_MODEL.md:29-43` | implemented |
| Generator artifact set incl. AGENTS.md, skills/, 6 YAML files, task packets, evidence contract, hash manifest | `nornyx/generator.py:76-182` | implemented |
| Determinism: LF newlines, sorted paths/hashes, no timestamps in generated artifacts | `nornyx/generator.py:11-36`; `CHANGELOG.md:683-685` | implemented |
| `nornyx drift` compares full artifact set by sha256 (AGENTS.md-only diff was insufficient) | `nornyx/repo_drift.py:1-92`; `CHANGELOG.md:613-618` | implemented |
| Workspace manifest = canonical policies + members; `--write` surgically syncs | `nornyx/workspace.py:1-17,218-299`; `tests/test_workspace.py` | implemented |
| 23 typed graph relations with source/target kind checking | `nornyx/checker.py:144-168,425-450` | implemented |
| Context packs: per-file sha256 provenance, taint channels, authority rank | `nornyx/context_builder.py:9-174`; `tests/test_context_provenance.py` | implemented |
| "Authority rank is advisory metadata until a later enforcement goal" | `nornyx/context_builder.py:170` | implemented (declared limitation) |
| Lexical remote/UNC/device path rejection before any FS access | `nornyx/path_security.py:15-52`; used in `parser.py:70-71` | implemented |
| Profile/module composition: dependency-ordered modules then profile, monotonic merge, provenance per element | `nornyx/governance/composition.py:30-45,262-275` | implemented |
| Timestamp-free `nornyx.profiles.lock` with sha256 content hashes; mismatch exits 2 | `schemas/profiles_lock_v1.schema.json`; `nornyx/cli.py:1136-1147` | implemented |
| Effective governance emitted as closed `nornyx.effective_governance.v2` | `schemas/effective_governance_v2.schema.json`; `docs/GOVERNANCE_CLI_AND_API.md:110-115` | implemented |
| 13 built-in profiles, 7 modules | `nornyx/profiles_data/catalog.json` | implemented |
| AI/tools/models/connectors intrinsically cannot hold approval authority | `nornyx/governance/approvals.py:34-59,426-433,494-499`; `nornyx/agentic/authz.py:1042` | implemented |
| Refused non-human approvals validate in evidence streams (grant-only scoping) | `CHANGELOG.md:138-149` (1.9.0 F1 fix) | implemented |
| Exception lifecycle (expiry, renewal `manual_reapproval`, closure evidence) fail-closed | `schemas/governance_exception_v1.schema.json`; `CHANGELOG.md:309-321` | implemented |
| `--as-of` fails closed (`AS_OF_INVALID`, exit 2), never falls back to live clock | `nornyx/cli.py:133-161`; `CHANGELOG.md:95-102` | implemented |
| Agentic-network artifacts canonical timestamp-free JSON; lock is content-addressed sha256 | `nornyx/agentic_artifacts.py:140-156`; `CHANGELOG.md:204-210` | implemented |
| "Hash validity proves content binding, not event truth"; no runtime observation | `CHANGELOG.md:211-215`; `docs/GOVERNANCE_CLI_AND_API.md:84-85` | implemented (declared limitation) |
| Adapters must be `execution_mode: contract_only`, `live_connector_execution: false` (schema consts) | `schemas/nornyx_v1_0.schema.json:203-211`; `docs/05_SECURITY_MODEL.md:60-70` | implemented |
| Exit codes 0/1/2 with lock/parse failures = 2 | `docs/GOVERNANCE_CLI_AND_API.md:42-53`; `nornyx/cli.py` | implemented |
| Governance public API deprecation policy (≥2 minor releases and 6 months) | `docs/GOVERNANCE_CLI_AND_API.md:88-92` | implemented (policy) |
| First PyPI publication at 1.6.2; 1.6.0/1.6.1 never on PyPI | `CHANGELOG.md:274-276,283-285` | implemented (historical fact) |
| 1.6.0 followed an independent NO-GO audit (AUD-001…AUD-022) | `CHANGELOG.md:288-348` | implemented (historical fact) |
| Published package as of manifest = 1.10.0; 1.11.0 tagged-in-repo release candidate | `manifest.json:39,48,76` | implemented (repo state) |
| Full LLM-native language, executing harness runtime, LSP, Registry, Studio | `docs/16_FINAL_LANGUAGE_TARGET.md`; `docs/RFCs/RFC-0003` | roadmap |
| Dedicated non-YAML parser | `docs/01_LANGUAGE_SPEC_v0_1.md:276-277` | roadmap |
| Bounded execution ("future_proposal_outside_current_program") | `docs/05_SECURITY_MODEL.md:83-93`; `docs/45_…v0_8.md` | roadmap |
| Not a runtime / not a LangGraph-CrewAI-LangChain replacement / no automatic approvals / no live MCP-A2A | `docs/48_NORNYX_POSITIONING.md:17-25`; `README.md:239-241` | non-goal |
| No arbitrary shell, no credential storage, no production deployment, no self-modification | `manifest.json:32-38`; `README.md:239-241` | non-goal |
| GOAL-100 (regulated/enterprise promotion) locked | `manifest.json:78`; `docs/47…v1_0.md:93-98` | non-goal (locked gate) |
| Nornyx does not claim scanned packages are safe | `CHANGELOG.md:507-509`; `README.md:198-200` | non-goal (declared limitation) |

## 16. Unverified or ambiguous

- **PyPI state**: the repo asserts publication history (first at 1.6.2; `manifest.json` says `package_publication: 1.10.0` while CHANGELOG dates 1.11.0 at 2026-08-01 with "tagging and PyPI publication … performed separately"). Whether 1.11.0 is actually live on PyPI cannot be verified from the repository alone.
- **Module count wording**: ADR-0031 froze the module catalog "at six for this program" (`CHANGELOG.md:407-408`), but the shipped catalog has seven modules (agentic_network_governance added under the later AN track). Writers should say "six foundational modules, plus the agentic-network module" rather than "six modules".
- **"12 structured v1 packs" vs 13 profiles**: `docs/40…:46-48` says twelve authoritative packs; `catalog.json` lists 13 profiles. The doc sentence predates the `agentic_network` profile addition (the same doc's last section describes agentic_network as additive). Treat the count in `docs/40` as stale by one.
- **README generator artifact list** omits `trace.yaml`, `goals.yaml`, task packets, `goal_ledger.md`, and the generation manifest that `generate` actually writes (`README.md:56` vs `nornyx/generator.py:118-181`). The code is the ground truth.
- **`docs/01_LANGUAGE_SPEC_v0_1.md` deferred-block list** omits `governed_package`, which the checker's `EXTENSION_TOP_LEVEL_BLOCKS` includes (`nornyx/checker.py:54`). Code list is authoritative.
- **Line-numbered citations into `nornyx/governance/structural.py`** (SOD/high-risk checks) were spot-checked by grep (lines 598-643, 1175-1186, 2328-2341) but that 2,400+-line module was not read end-to-end; writers should re-verify any specific structural-check sentence against the file before quoting.
- The `docs/30-39` extension series (portal contract, evergreen assurance, pattern lifecycle, handover controls, requirement triage, authoring assistant, zero-friction adoption) each have matching data-only modules/schemas/tests in the repo (e.g. `nornyx/portal_contract.py`, `tests/test_portal_contract_extension.py`), but this fact pack did not audit their internals; classify them case-by-case before making claims.
- Numbers "1523 passed, 55 skipped" come from `manifest.json`'s recorded canonical release run, not from a test execution performed during this audit (no tests were run for this fact pack).
