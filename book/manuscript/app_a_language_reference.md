---
appendix: A
title: "Appendix A — Nornyx Language Reference"
---

# Appendix A — Nornyx Language Reference

This appendix is a reference for the `.nyx` contract language as implemented at the audited
revision `70d2b40ad792` (distribution 1.11.0, language/schema 1.0). It is organised for lookup
rather than for reading straight through: each section gives the purpose of a construct, its
fields, a minimal fragment that a checker accepts, and the validation behaviour you should expect.
Chapter 17 teaches the core language; Chapter 18 teaches profiles, modules, and locks; Chapters 5,
6, and 31 develop the agentic-network declaration model conceptually. Everything here is
**[implemented]** unless the entry says otherwise.

Two cautions apply throughout. First, the checker validates *declarations*; it does not observe or
constrain a running agent. Second, block interiors are open, so a field the checker does not
mention is not thereby forbidden — it is simply unvalidated unless a governance module contributes
a closed block schema for that block.

## A.1 Version declarations and the meaning of the 1.0 target

Every contract begins with a version marker and a project block. These are the only two required
top-level blocks; omitting either produces `MISSING_TOP_LEVEL_BLOCK`.

```yaml
nornyx: "0.1"
project:
  name: GovernedDeliveryControlPlane
```

The accepted values of `nornyx:` are exactly `"0.1"` and `"0.2"` (the unquoted numeric forms `0.1`
and `0.2` are also accepted). Anything else yields the warning `UNKNOWN_VERSION` — a warning, not
an error, so the document still checks. The hint the checker emits is instructive: use `"0.1"` for
the scaffold, `"0.2"` for graph contracts.

The version *inside* the document is not the version of the schema that validates it. Four axes
move independently and must not be conflated.

| Axis | Value at the audited revision | Where it is recorded |
|---|---|---|
| Distribution (package) version | 1.11.0 | `pyproject.toml:7`; `manifest.json:4` |
| Language/schema version | 1.0 | `manifest.json:5` (`language_version`) |
| In-document version marker | `"0.1"` or `"0.2"` | `nornyx:` key |
| Agentic integration SPI | 1.2 | `nornyx/agentic/authz.py:66` |

**Table A.1 — The independent version axes.** Package and language versions are explicitly
declared independent in `docs/VERSIONING.md:6-9`; a reader who assumes the distribution number
names the language will mis-read every compatibility statement in this book.

The 1.0 target therefore does *not* mean "write `nornyx: "1.0"`". The v1.0 schema
(`schemas/nornyx_v1_0.schema.json`) names the stable generalised agentic contract-language surface
while keeping the document markers at 0.1 and 0.2 for compatibility; its own comment says so
(line 17). What 1.0 stabilises is the *concept set*: twelve stable core concepts — Intent, Agent,
Policy, Eval, Approval, Evidence, Context, Artifact, Graph, Goal, Budget, Trace — of which Artifact
is a concept expressed inside other blocks rather than a top-level block of its own. The schema
also carries an explicit safety boundary as metadata: it "does not publish packages, deploy
software, enable live connectors, execute graph edges, call models, grant automatic approvals, or
unlock GOAL-100" (`schemas/nornyx_v1_0.schema.json:16`).

Three document schemas are registered: `compat`/`0.1`, `0.2`, and `1.0`. The compatibility target
remains the default, which is why `nornyx schema` without `--version` prints the 0.1 schema.

## A.2 The validation model: closed at the top, open inside

All three document schemas set `additionalProperties: false` at the top level. A block name the
schema does not know fails JSON-schema validation outright. Individual blocks, by contrast, keep
`additionalProperties: true` inside, so unknown *fields* within a recognised block are not schema
errors.

The Python checker mirrors this asymmetry more leniently. An unrecognised top-level key produces
the **warning** `UNKNOWN_TOP_LEVEL_BLOCK` with the hint "Keep experimental blocks under
`experimental:` until the spec stabilizes" — the document still passes. Only when a governance
module contributes a closed block schema for that block does the interior become validated; the
`nornyx check` command then suppresses the unknown-block warning for module-contributed blocks and
appends the module's own diagnostics instead.

This is the single most important structural fact about the language. Reading a passing `nornyx
check` as "everything in this file is validated" is a mistake. What is validated is: the presence
of required blocks, the shape of recognised blocks, the required `name` (or `id`) on each entry,
cross-references between blocks, graph relation typing, goal completeness, and whatever closed
schemas the resolved profile and modules contribute.

Two parser-level rules apply before any of that. Duplicate mapping keys are rejected at every
nesting level, so a second `policies:` key cannot silently shadow the first. And YAML's implicit
boolean conversion is restricted to `true`/`false` only, so `on`, `off`, `yes`, and `no` remain
strings — which is what makes the repair-loop key `- on: test_failure` parse as the string `"on"`
rather than as boolean true.

## A.3 The core top-level blocks

Fifteen block names make up the core set (`nornyx/checker.py:32-48`). Ten of them are lists whose
entries are mappings carrying a required `name`; `goals` is a list keyed by `id`; `constitution`
and `evidence` are mappings; `nornyx` and `project` are the required scalars/mapping above.

| Block | Kind | Purpose | Key fields observed in bundled contracts |
|---|---|---|---|
| `nornyx` | scalar | Document version marker | — |
| `project` | mapping | Names the governed subject | `name` (required), `description`, `category`, `profile`, `modules` |
| `constitution` | mapping | Non-negotiable principles the contract asserts | `principles` |
| `intents` | named list | Why the system exists and what success means | `name`, `goal`, `success` |
| `contexts` | named list | The governed input surface and its trust model | `name`, `include`, `exclude`, `authority`, `budget`, `taint` |
| `skills` | named list | Named capabilities of agents, with typed inputs/outputs | `name`, `purpose`, `input`, `output` |
| `policies` | named list | Deny/require rules, or a `ref` to a canonical policy | `name`, `rules` **or** `deny`/`require`, `ref` |
| `agents` | named list | Roles that act, bound to skills and a policy | `name`, `role`, `skills`, `policy` |
| `harnesses` | named list | The bounded flow, repair loop, and gates | `name`, `context`, `flow`, `repair`, `gate` |
| `traces` | named list | What is captured and under which telemetry standard | `name`, `standard`, `capture` |
| `evals` | named list | Threshold assertions over evaluation results | `name`, `metrics`, `datasets`, `integrity` |
| `evidence` | mapping | The evidence contract for the document | `required` |
| `approvals` | named list | Human approval requirements | `name`, `required_for`, plus the governed-approval fields of A.9 |
| `budgets` | named list | Bounded token, cost, and time limits | `name`, `max_tokens`, `max_cost_usd`, `max_runtime_minutes` |
| `goals` | list keyed by `id` | Bounded work units with stop rules | see A.8 |

**Table A.2 — Core top-level blocks.** Field lists are drawn from
`examples/governed_delivery_control_plane.nyx` and the v1.0 schema; because block interiors are
open, they are the fields the toolchain reads, not an exhaustive permitted set.

### Minimal valid fragments

Each fragment below is the smallest form the checker accepts for that block, assuming the
surrounding document supplies `nornyx` and `project`.

```yaml
constitution:
  principles:
    - human_authority_over_high_impact_actions

intents:
  - name: GovernedAIDelivery
    goal: "Govern AI-assisted delivery with policies, evals, approvals, and evidence."

contexts:
  - name: RepoContext
    include: ["docs/**/*.md"]

skills:
  - name: PatchBuilder
    purpose: "Produce small scoped patches."

policies:
  - name: SafeEditPolicy
    rules:
      - deny secrets_to_llm

agents:
  - name: Builder
    role: "Implement small scoped patches."
    skills: [PatchBuilder]
    policy: SafeEditPolicy

harnesses:
  - name: DevHarness
    context: RepoContext
    flow:
      - agent: Builder
        action: implement

evidence:
  required:
    - patch.diff

approvals:
  - name: HumanMergeApproval
    required_for: [production_deploy]

budgets:
  - name: StandardDevBudget
    max_tokens: 100000
```

**Listing A.1 — Minimal accepted fragments per core block.** Patterned on
`examples/governed_delivery_control_plane.nyx`; each entry carries the required `name` and the
minimum content the checker needs to avoid a shape error.

Note the reference-integrity rules these fragments satisfy. An agent's `skills` must name declared
skills (`UNKNOWN_SKILL_REFERENCE`) and its `policy` a declared policy (`UNKNOWN_POLICY_REFERENCE`).
A harness's `context` must name a declared context (`UNKNOWN_CONTEXT_REFERENCE`), and each flow
step naming an agent or eval must resolve (`UNKNOWN_AGENT_REFERENCE`, `UNKNOWN_EVAL_REFERENCE`). A
context with no `include` draws `CONTEXT_WITHOUT_INCLUDE`; a harness with no `flow` draws
`HARNESS_WITHOUT_FLOW`. Missing `name` on a list entry produces a generated code of the form
`MISSING_<SINGULAR>_NAME`, for example `MISSING_POLICY_NAME`.

## A.4 The extension top-level blocks

Eleven further block names are recognised by the checker as deferred extension surfaces
(`nornyx/checker.py:50-62`): `experimental`, `graph`, `contracts`, `governed_package`, `adapters`,
`connectors`, `guardrails`, `capabilities`, `incidents`, `containment`, and `supply_chain`. The
language specification is explicit that "these blocks do not define stable v0.1 runtime behavior".

Their status varies and should not be flattened. `graph` and `contracts` are fully checked
(A.10). `governed_package` is validated by the governed-package profile and its own schema.
`capabilities` and `guardrails` are read by the local policy-decision runtime (A.7) and, under the
agentic-network module, `capabilities` gains a closed schema (A.11). `adapters` and `connectors`
are validated as declarations only, with `execution_mode: contract_only` and
`live_connector_execution: false` enforced as schema constants. `experimental`, `incidents`,
`containment`, and `supply_chain` are tolerated placeholders; the requirements matrix classifies
incident response, containment, and supply chain as planned rather than implemented.

## A.5 Context trust: taint channels and authority

A context declares which files enter the governed input surface, and with what trust. Four trust
channels are hardcoded in `nornyx/context_builder.py:9-30`.

| Channel | Default taint value | Trust level | May define policy |
|---|---|---|---|
| `repo` | `trusted_repo_file` | trusted | no |
| `authoritative_repo` | `authoritative_repo_file` | authoritative | **yes** |
| `user_prompt` | `untrusted` | untrusted | no |
| `external_web` | `untrusted` | untrusted | no |

**Table A.3 — Default trust channels and taint values.** Only the authoritative repository channel
may define policy; a context's own `taint:` mapping overrides the default taint per channel but
does not invent new channels.

A file matching one of the ordered `authority:` glob patterns is assigned the
`authoritative_repo` channel together with its rank — rank 1 for the first matching pattern, and so
on. Every entry in a generated context pack carries the file's SHA-256, byte count, channel, taint,
trust level, authority rank and pattern, and a provenance record naming the repository root and a
`repo://` URI. Content embedding is off by default; `--include-content` turns it on.

Three trust rules are written into every context pack: untrusted context cannot define policy,
untrusted context cannot request privileged tool use, and higher-authority repository context wins
over lower-authority context on conflict. The pack itself records the limitation honestly:
"Authority rank is advisory metadata until a later enforcement goal" (`context_builder.py:170`).
Treat the authority model as provenance and ranking metadata, not as an enforcement mechanism.

```yaml
contexts:
  - name: RepoContext
    include: ["README.md", "docs/**/*.md", "tests/**/*.py"]
    exclude: ["generated/**", "**/.env"]
    authority:
      - "docs/05_SECURITY_MODEL.md"
      - "tests/**/*.py"
    taint:
      repo: trusted_repo_file
      authoritative_repo: authoritative_repo_file
      user_prompt: untrusted
      external_web: untrusted
```

**Listing A.2 — A context with authority ranking and explicit taint.** From
`examples/governed_delivery_control_plane.nyx:23-46` (abridged). The `authority` list is ordered:
position determines rank.

## A.6 The policy rule grammar

There are exactly two rule verbs. Rules may be written either as shorthand strings under `rules:`
or as explicit `deny:` and `require:` lists; both normalise to the same pair of sets.

```yaml
policies:
  - name: SafeEditPolicy
    rules:
      - deny secrets_to_llm
      - require tests_if_code_changed
  - name: SupportGovernance
    deny:
      - secrets_to_agents
    require:
      - exact_revision_binding
```

**Listing A.3 — The two equivalent rule forms.** Shorthand from
`examples/governed_delivery_control_plane.nyx:62-69`; explicit lists from
`examples/agentic_network_support/support_network.nyx:49-60`.

Normalisation recognises exactly four prefixes: `deny ` and `deny:` for denials, `require ` and
`require:` for requirements (`nornyx/policy_runtime.py:83-108`). **A rule string with no
recognised prefix is bucketed into `require`.** This is the single most important trap in the rule
grammar: a misspelled `dney secrets_to_llm` does not error, it becomes a requirement — and
requirements are never executed.

Rule tokens themselves are free-form strings. Only deny rules are pattern-matched, and only against
a lower-cased rendering of the flow step. `_matches_deny_rule` (`nornyx/policy_runtime.py:185-203`)
recognises five token categories.

| Token in the rule | Blocks a step whose text contains | Example rule |
|---|---|---|
| `production` | `production`, `prod`, `deploy`, `release` | `deny production_write_without_approval` |
| `secret` | `secret`, `token`, `credential` | `deny secrets_to_llm` |
| `destructive` | `delete`, `destroy`, `drop`, `wipe`, `reset`, `remove` | `deny destructive_schema_change` |
| `connector` | any step of connector kind | `deny connector_use_without_guardrail` |
| `self_modification` / `self-modification` | `self_modification`, `self-modification`, `modify self` | `deny self_modification_without_approval` |

**Table A.4 — The deny token categories.** A deny rule containing none of these substrings matches
nothing; the token vocabulary is closed and lexical, not semantic.

`require` rules are never evaluated as conditions. They are recorded as `pending_evidence` in the
policy report — a declaration that something must be shown, not a check that it was. The security
model states this plainly: the policy runtime is "a read-only decision manifest, not an execution
engine".

Capability semantics complete the picture. Tool, connector, and model steps are deny-by-default
unless a matching entry exists in the `capabilities` block (`CAPABILITY_NOT_DECLARED`); a declared
capability defaults to `approval_required: true` (`CAPABILITY_APPROVAL_REQUIRED`); and connector or
model steps additionally require a guardrail declaring one of `no_secrets`, `no_pii`,
`schema_valid`, or `output_schema` (`GUARDRAIL_REQUIRED_FOR_EXTERNAL_USE`). Every policy report
embeds `"default_capability_mode": "deny_unless_declared"` and a safety block asserting that
nothing was executed.

## A.7 The `ref` mechanism

A policy may reference one canonical definition instead of copying its rules.

```yaml
policies:
  - name: SafeDeliveryPolicy
    ref: org_policies.nyx#SafeDeliveryPolicy
```

**Listing A.4 — A referenced policy.** Verbatim from `nornyx/examples/governed_service.nyx:11-13`.

The syntax is `<path>#<PolicyName>`. The path is a **local** file relative to the referencing
contract, and may be either another `.nyx` contract (whose `policies` list is searched) or a
workspace manifest (whose `policies` mapping is searched). Resolution happens at load time,
offline, and compiles the reference into inline `rules` while dropping the `ref` key — so every
downstream consumer, from checker to generator to drift gate, sees an ordinary policy.

Six conditions fail closed with a parse error, all raised before any downstream stage runs:

| Condition | Message shape |
|---|---|
| Both `ref` and `rules` set on one policy | `set either 'ref' or 'rules', not both` |
| Malformed reference (missing path or name) | `'ref' must be '<path>#<PolicyName>'` |
| Remote or device-backed reference path | `remote or device-backed ref sources are not allowed` |
| Source file not found | `ref source not found: <path>` |
| Source is invalid YAML, or not a mapping | `is invalid YAML` / `is not a mapping` |
| Named policy absent from the source | `policy <name> not found in <path>` |

**Table A.5 — Fail-closed conditions for `ref` resolution.** From `nornyx/parser.py:111-177`. All
are `NornyxParseError`, so `nornyx check` exits 2 rather than 1.

The mechanism is deliberately within-repository. A cross-repository policy reference was
considered and declined; the workspace manifest and `nornyx workspace-check` occupy that space
instead, so that a contract remains readable on its face without network resolution.

## A.8 Goals

Goal entries are the language's bounded-work unit, and they are the strictest core construct. Nine
fields are required: `id`, `phase`, `goal`, `scope`, `non_goals`, `validation`, `evidence`,
`approval`, and `stop_rules`. `scope`, `non_goals`, `validation`, and `stop_rules` must be lists of
non-empty strings; `evidence` and `approval` are strings.

```yaml
goals:
  - id: GOAL-SUPPORT-001
    phase: AN-006
    goal: Prove allowed, denied, delegated, handed-off, and approved flows.
    scope: [support_network.nyx, governance_evidence/, eval/]
    non_goals:
      - live customer traffic
      - credential loading
    validation:
      - nornyx check examples/agentic_network_support/support_network.nyx
    evidence: governance_evidence/
    approval: required before accepting the exact network-contract revision
    stop_rules:
      - stop on identity, capability, trust-zone, approval, or evidence ambiguity
```

**Listing A.5 — A complete goal.** Abridged from
`examples/agentic_network_support/support_network.nyx:85-103`.

Missing required fields produce generated codes `MISSING_GOAL_<FIELD>`; wrong shapes produce
`INVALID_GOAL_<FIELD>`. The presence of `non_goals` and `stop_rules` in the *required* set is the
language's structural stance that a bounded work unit must say where it stops, not only what it
attempts.

## A.9 The `graph` and `contracts` blocks

Under the 0.2 marker a contract may declare a typed graph. Nodes require `id` and `kind`; duplicate
ids are errors; edge endpoints must be declared nodes; a node carrying `ref` must resolve into the
matching named block for its kind; and evidence nodes without a `ref` are flagged. Self-edges and
duplicate edges are rejected.

Twenty-three relation verbs are typed with allowed source and target kinds
(`nornyx/checker.py:144-168`): `authorizes_context_for`, `bounded_by`, `bounds`, `depends_on`,
`gated_by`, `gates`, `gates_promotion`, `governs`, `governed_by`, `has_skill`, `must_produce`,
`produces`, `produces_artifact`, `produces_evidence`, `records_trace`, `requires_evidence`,
`scopes_context`, `satisfies_intent`, `uses_connector`, `uses_context`, `validates`,
`validated_by`, and `validates_contract`. An unrecognised relation warns
(`UNKNOWN_GRAPH_RELATION`); a recognised relation used between the wrong kinds is an error
(`INVALID_GRAPH_RELATION_PAIR`). Only `depends_on` accepts any pair.

The `contracts` block ties graph nodes to approvals and budgets; approval and budget references
must resolve to declared entries, and the checker warns when approvals, budgets, or evidence are
not represented as graph nodes at all, on the grounds that an unrepresented control is an
unauditable one.

## A.10 The agentic-network declaration model

Under the optional `agentic_network` profile and its `agentic_network_governance` module, three
blocks gain closed schemas: `agentic_network`, `agent_identities`, and `capabilities`. The whole
model is static: it declares who exists, what they may do, where they may operate, what may cross a
boundary, and what must be approved — and it declares **no** runtime, endpoint, credential,
authentication, transport, or execution behaviour.

### Required top-level structure

The `agentic_network` block is closed and requires eight keys: `schema` (constant
`nornyx.agentic_network.v1`), `id`, `subject_revision`, `trust_zones`, `memberships`,
`protocol_targets`, `network_gates`, and `revocations`. `delegations`, `handoffs`, and `relations`
are optional. `subject_revision` must match `git:` followed by 40 or 64 hexadecimal characters, or
`sha256:` followed by 64 — branch names and tags are unrepresentable, because a mutable revision
cannot bind an approval.

### The record types

| Record | Required fields (closed) | Notable constraints |
|---|---|---|
| Agent identity | `id`, `role_ref`, `identity_class`, `namespace`, `subject`, `framework_bindings`, `capability_refs`, `status`, `valid_from`, `expires_at`, `revocation_refs`, `authority`, `can_approve` | `authority` is the constant `non_human`; `can_approve` is the constant `false`; `identity_class` ∈ {`local_agent`, `external_agent`, `service_agent`, `test_agent`} |
| Capability | `name`, `actions`, `risk`, `scope_type`, `scope_refs`, `delegable`, `required_gate_refs`, `required_approval_refs`, `required_evidence_refs` | `scope_type` is the constant `context`; `risk` ∈ {`low`, `medium`, `high`, `critical`}; optional `max_delegation_depth` 1–8 |
| Trust zone | `id`, `classification`, `allowed_transition_targets`, `share_allowlist`, `never_share`, `ingress_gate_refs`, `egress_gate_refs` | `never_share` must be **non-empty**; seven classifications: `governed_local`, `internal`, `isolated`, `test`, `external`, `external_contract_only`, `contract_only` |
| Membership | `id`, `identity_ref`, `trust_zone_ref`, `capability_refs`, `status`, `valid_from`, `expires_at`, `revocation_refs` | `status` ∈ {`authorized`, `suspended`, `revoked`, `expired`} |
| Network gate | `id`, `action_classes`, `source_zone_refs`, `target_zone_refs`, `required_policy_refs`, `required_approval_refs`, `required_evidence_refs` | `action_classes` non-empty |
| Protocol target | `id`, `protocol`, `version`, `execution_mode`, `live_connector_execution`, identity/membership/zone refs, `share`, `never_share`, required gate/approval/evidence refs | `protocol` ∈ {`mcp`, `a2a`} only; `execution_mode` constant `contract_only`; `live_connector_execution` constant `false`; `never_share` non-empty |
| Delegation | `id`, `delegator_ref`, `delegate_ref`, `capability_ref`, `purpose`, `actions`, `scope_refs`, `status`, validity interval, `max_depth`, `current_depth`, `onward_delegation`, zone refs, required refs, `revocation_refs` | `max_depth` 1–8; `current_depth` 0–8; `onward_delegation` ∈ {`denied`, `allowed_with_policy`} |
| Handoff | `id`, `from_identity_ref`, `to_identity_ref`, `purpose`, `mission_ref`, zone refs, `required_capability_refs`, `delegation_refs`, `shared_context`, `never_share`, `status`, validity interval, required refs, `revocation_refs` | `status` ∈ {`initiated`, `accepted`, `completed`, `rejected`, `expired`, `revoked`, `superseded`}; `required_capability_refs` and `never_share` non-empty |
| Relation | `id`, `type`, `source`, `target` | endpoints typed over ten kinds; eleven verbs (below) |
| Revocation | `target` (one of seven closed target kinds), `effective_at`, `reason`, required approval/evidence refs | targets: agent identity, membership, capability assignment, protocol target, approval record, delegation, handoff |

**Table A.6 — The agentic-network record types.** Field lists from
`schemas/agentic_network_v1.schema.json`, `schemas/agent_identities_v1.schema.json`, and
`schemas/agentic_capabilities_v1.schema.json`. Every one of these object types is closed.

The eleven relation verbs are `identifies`, `owns`, `advertises_capability`, `delegates_to`,
`hands_off_to`, `communicates_with`, `crosses_trust_zone`, `shares_with`,
`requires_approval_from`, `revokes`, and `observed_by`. Collections are bounded: 256 trust zones,
1,024 memberships, delegations, handoffs, identities and capabilities, 2,048 relations.

### What cannot be expressed

The two constants on every identity — `authority: non_human` and `can_approve: false` — make an
approving AI identity *unrepresentable*, not merely rejected. Code enforces the same invariant
again at three further layers (static check `AN_NON_HUMAN_APPROVAL_INVALID`, engine
`APPROVAL_NON_HUMAN`, evidence `AN_EVT_APPROVAL_NON_HUMAN`), which is a deliberate defence in depth
rather than redundancy.

Because every block schema is closed, credential-shaped fields cannot be added. Generation adds a
second, content-level barrier: artifact rendering scans for forbidden key segments — among them
`apikey`, `bearer`, `cmd`, `command`, `credential`, `endpoint`, `host`, `ip`, `password`, `port`,
`secret`, `session`, `shell`, `token`, `uri`, `url` — plus the pairs (`api`,`key`),
(`key`,`material`), (`private`,`key`), (`access`,`key`), and IPv4 literals in values. A violation
fails generation closed with `AN_ARTIFACT_FORBIDDEN_FIELD` or `AN_ARTIFACT_FORBIDDEN_VALUE`.

Four sensitive categories are defined once and shared by the static checker, the authorization
engine, and the evidence validator: `secrets`, `credentials`, `tokens`, `private_memory`. They may
never be shared across a prohibited boundary in a zone, protocol target, delegation, handoff,
relation, or runtime event.

```yaml
- id: zone.customer_channel
  classification: external_contract_only
  allowed_transition_targets: []
  share_allowlist: [customer_response, evidence_digest]
  never_share: [secrets, credentials, tokens, private_memory]
  ingress_gate_refs: [gate.customer_response]
  egress_gate_refs: []
```

**Listing A.6 — An external trust zone.** From
`examples/agentic_network_support/support_network.nyx:326-332`. An empty
`allowed_transition_targets` means nothing may leave this zone by declaration.

### A note on strictness

Declaring the `agentic_network` profile switches on a large body of structural checking. A network
fragment that checks clean as a set of unknown blocks will typically produce a substantial
diagnostic list once the profile is selected, naming exactly the missing approvals, gates,
evidence records, and revision bindings. Appendix E shows a worked instance of that difference.
This is the intended behaviour: the profile is what turns declarations into obligations.

## A.11 Diagnostics, exit codes, and what the language does not do

Diagnostic codes are upper-snake-case strings carried on a `Diagnostic` record with `level`,
`code`, `message`, `path`, and `hint`. There is no numeric code scheme in the core. Errors gate the
exit code; warnings do not. `nornyx check` exits 0 on success, 1 when any error-level diagnostic is
present, and 2 on a parse failure or a malformed `--as-of` value. Appendix C catalogues the code
families.

Finally, the boundary. The language declares; it does not act. Nornyx is positioned as an
executable specification layer, not a runtime: it is explicitly not a full autonomous runtime, not
a general-purpose programming language, not a replacement for LangGraph, CrewAI, or LangChain, not
a production execution engine, not a live MCP or A2A connector runtime, and it does not implement
automatic approval or self-modification. A contract that says `deny production_write_without_approval`
has stated a rule; whether anything enforces it at run time is the subject of Chapters 10, 13,
and 22.
