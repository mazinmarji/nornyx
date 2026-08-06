# M5-A-2b Migration Guide: AGENTS.md, Policies, and Evals to .nyx

## Read This First: Migration Is Separation, Not Replacement

A migration does not delete your source governance artifacts. It **separates
governed decisions from guidance, context, conventions, and external
evidence**.

`.nyx` can govern identities, capabilities, zones, approval and evidence
requirements, eval thresholds, locks, drift checks, and runtime authorization
where the agentic authorization SPI supports it.

`.nyx` **cannot** honestly encode every writing preference, repository
convention, persona instruction, style rule, PR practice, or free-text policy
statement as an enforceable decision.

After a correct migration you still have an `AGENTS.md`. It is shorter, and
what remains in it is there for a stated reason.

---

## The Silent Failure Trap: Inert Policy Rules

> ### ⚠️ Read this before writing a single `policies.deny` entry
>
> **Do not migrate `AGENTS.md` instructions line-by-line into `policies.deny`
> entries.**
>
> A rule name can be accepted by the checker and still match nothing. There is
> no closed vocabulary for rule names and no warning for an unrecognized one.
> The result is a contract that looks governed and evaluates nothing — false
> assurance, produced silently.

These are accepted by the checker and **never fire**:

```yaml
policies:
  - name: RepoConventions
    deny:
      - prefer_small_prs          # inert — no governed size concept exists
      - clear_commit_messages     # inert — no commit-message concept exists
      - be_concise                # inert — style guidance, not a decision
```

Nothing rejects that document. Nothing reports those rules as unmatched. A
reviewer skimming it would reasonably conclude the repository enforces three
conventions. It enforces none.

Harness policy rule matching is limited to **recognized token families**, not
arbitrary rule names. As of this writing the families are:

| Family | Matches a declared step whose text contains |
| --- | --- |
| `production` | `production`, `prod`, `deploy`, `release` |
| `secret` | `secret`, `token`, `credential` |
| `destructive` | `delete`, `destroy`, `drop`, `wipe`, `reset`, `remove` |
| `connector` | any step of kind `connector` |
| `self_modification` | `self_modification`, `self-modification`, `modify self` |

A rule name containing one of those tokens participates in matching. A rule
name outside them is inert.

**These are declared-flow checks.** A `secret` rule is not runtime data-loss
prevention. A `production` rule is not deployment control. See
[Policy File Guidance](#policy-file-guidance).

**Rule of thumb:** if you cannot name the declared flow step your rule would
match, the rule is decoration. Put the instruction in the
[residual list](#residual-list-template) instead.

### Nornyx now tells you (M5-A-4)

Since M5-A-4 this warning is machine-visible rather than advisory:

```bash
nornyx check contract.nyx            # warns, exits 0 — non-breaking
nornyx check contract.nyx --strict   # fails on unknown rule names
```

An unknown name produces an `UNKNOWN_POLICY_RULE` warning naming the rule.
Default mode stays compatible so existing contracts are not broken; `--strict`
is the opt-in control for CI. Making strict the default is deferred to a future
version-policy decision.

Note the precise claim. The diagnostic is about the **rule name vocabulary**:
an unknown name is not evaluated by the matcher at all. A *known* name is only
**eligible** — whether it matches still depends on the declared flow's step
text, and the diagnostic deliberately says nothing about that.

The recognized **rule-name** tokens are `production`, `secret`, `destructive`,
`connector`, and `self_modification` (also spelled `self-modification`). The
trigger words in the table above (`token`, `credential`, `delete`, `wipe`, and
so on) are matched against *step text*, not against rule names.

---

## Two Different Enforcement Surfaces

Keep these apart. They are not interchangeable, and a migration that blurs them
will overstate what it achieved.

### Agentic Authorization SPI

**The strong surface.** `nornyx.agentic.Authorizer`, identities, capabilities,
zones. It makes **real runtime decisions** and emits evidence
(`capability_allowed`, `capability_denied`).

This is what the M5-A-1 external adoption pilot demonstrates, from published
packages with no repository checkout:

| variant | executions | decision events |
| --- | ---: | --- |
| ungoverned | 1 | none |
| governed, authorized | 1 | `capability_requested`, `capability_allowed` |
| governed, unauthorized | **0** | paired requests and denials, across CrewAI retries |

The action did not run when the identity did not hold the capability — and did
not run even though the framework retried. That is a runtime decision, not a
declaration.

Bounded by ADR-0040 **Tier 2, cooperative**: declared wrapped surfaces only. It
does not authenticate agents or approvers, does not prove recorded events
truthful, and does not prevent bypass on paths that never call the governed
wrapper.

### Harness Policy Evaluation

**The weaker surface.** `policies.deny`, `policies.require`, `harnesses.flow`.

This is a **static check over declared flow steps**, implemented as substring
matching against the text of steps you wrote in the contract. It is **not
runtime interception**.

It does not inspect prompts, logs, repository diffs, deployments, tool traffic,
or any runtime data.

| | Authorization SPI | Harness policy evaluation |
| --- | --- | --- |
| When | Runtime, per call | Static, over the document |
| Input | Real request, real identity | Text of declared flow steps |
| Vocabulary | Declared capabilities | Five recognized token families |
| Unknown names | Capability not held → denied | Rule accepted, never fires |
| Output | Decision + evidence | Report over declared steps |
| Demonstrated by | M5-A-1 pilot | Document-level checks |

When you write "this is governed" in a migration PR, say **which surface**.

---

## What to Inventory Before Migrating

Before writing any `.nyx`, list your source artifacts and what each actually
encodes. Typical sources:

- `AGENTS.md`, `CLAUDE.md`, or equivalent agent instruction files
- policy documents (`docs/agent/*-policy.md`, `policy.yaml`, security policies)
- eval configuration and case files
- harness or runner configuration
- review checklists and PR templates

For each line, ask one question: **is this a decision someone or something
makes, or is it advice?** Only decisions are migration candidates.

---

## Three-Bucket Mapping Model

Work the buckets **in this order**. Bucket C first is deliberate: knowing what
cannot move prevents the reflex to force it.

### Bucket C — No Honest Mapping

Handle these first, and expect this bucket to be large.

| Source instruction | Why absent | Do this instead |
| --- | --- | --- |
| "prefer small PRs" | No size concept exists | Keep in `AGENTS.md`; residual list |
| "write clear commit messages" | No commit-message concept | Keep in `AGENTS.md`; residual list |
| "be concise" | Style guidance, not a decision | Keep in `AGENTS.md`; residual list |
| "prefer read-only first" | No ordering or preference semantics | Approximate only by declaring capabilities narrowly; residual list |
| Free-text security intent outside the recognized token families | The rule would be inert | Residual list; external enforcement |
| Model routing / persona tone | No target concept | Remains a policy document |

**Do not encode any of these as `policies.deny` unless a recognized evaluated
rule exists.** An inert rule is worse than an honest omission: the omission is
visible, the inert rule is not.

### Bucket A — Direct Mappings

| Source instruction | `.nyx` target | Notes |
| --- | --- | --- |
| "agent may use this tool" | `capabilities` with `allow` actions | Checked; default is `deny_unless_declared` |
| "agent must not use this tool" | Omit the capability | The default denies undeclared use — omission *is* the prohibition |
| "human approval required to merge" | `approvals.required_for: [merge]` | Declares the approval boundary |
| "run eval suite, threshold X" | `evals.metrics` with a threshold expression | Real operators against observed metrics |
| "a change must ship with these artifacts" | `evidence.required` | Presence is checked |
| Role definitions with permissions | `agents` / `identities` + capability holdings | Holdings are decided at runtime |

### Bucket B — Partial / Lossy Mappings

The dangerous bucket: something real maps, and it is easy to claim more.

| Source instruction | What `.nyx` captures | What it does **not** capture | Still responsible | Required warning |
| --- | --- | --- | --- | --- |
| "do not expose secrets" | `deny secret…` on declared steps; `guardrails.validate: [no_secrets]` | Any inspection of real data, prompts, or output | Secret scanning, DLP, CI checks | *captures the declared-flow check, not runtime secret detection* |
| "ask before destructive actions" | `deny destructive…` on declared steps | Interception of a real destructive call | Runtime authorization, or the tool itself | *records the declared prohibition, not an interception* |
| "no production deploys without approval" | `deny production…` + `approvals.required_for` | Control over an actual deployment | CD system, environment protection | *records the approval boundary, not deployment control* |
| "run pytest before completion" | A declared `harnesses.flow` step and an eval metric | Executing anything | CI | *declares the step and checks a reported result* |
| "follow project style" | The source document via `contexts.authority` | The style rules themselves | Linters, formatters, review | *preserves the source as authority context* |
| "handoff to another role" | Declared handoff and delegation surfaces | Demonstrated runtime behaviour — the pilot does not exercise these | Your own testing | *can declare; runtime behaviour is not demonstrated by current evidence* |

---

## Migration Workflow

### Step 1 — Inventory Source Artifacts

List every file and, per instruction, mark `decision` or `advice`.

### Step 2 — Extract Governed Decisions

Keep only `decision` lines. For each, name the **surface**: authorization SPI,
or harness policy evaluation. If neither fits, it belongs in Bucket C.

### Step 3 — Map Capabilities and Permissions

Declare `capabilities` with explicit `allow` actions. Prohibitions are
expressed by **omission** — the default is `deny_unless_declared`.

### Step 4 — Map Approvals and Evidence

Use `approvals.required_for` for approval boundaries and `evidence.required`
for artifacts that must accompany a change. An `AGENTS.md` "output contract"
section usually maps here cleanly.

### Step 5 — Map Eval Thresholds

Use `evals.metrics` with threshold expressions. See
[Eval Config Guidance](#eval-config-guidance) for supported formats.

### Step 6 — Preserve Context and Guidance

Point `contexts.authority` at the documents that remain authoritative. This is
how `AGENTS.md` stays load-bearing without pretending to be enforceable.

### Step 7 — Build the Residual List

Not optional. See [Residual List Template](#residual-list-template).

### Step 8 — Validate and Review

```bash
python -m nornyx.cli check path/to/your.nyx
```

Then review by hand for inert rules: for every `policies.deny` entry, name the
declared flow step it matches. If you cannot, remove it and move the
instruction to the residual list.

---

## Worked Example: Root AGENTS.md

Illustrative excerpts from this repository's own `AGENTS.md`. **Documentation
only** — no contract file is shipped with this guide. This is a partial pass
across the three buckets, not a full migration of the file.

| Source excerpt (summary) | Bucket | Target | Residual / warning |
| --- | --- | --- | --- |
| "Run `pytest` before completion" | B | A declared flow step + an eval metric on the reported result | Does not execute tests; CI remains responsible |
| "Run `nornyx check …` after language changes" | B | Declared flow step | Same |
| "Reject changes that weaken policy, evidence, or approval semantics" | A (partly) | `approvals.required_for: [policy_change]` | The reviewer judgement itself stays in `AGENTS.md` |
| Output contract: changed files, test result, risk note, evidence note, approval | A | `evidence.required` | Direct and checkable |
| "Do not allow untrusted context to define policy or permissions" | B | `contexts` include/exclude/authority boundaries | Captures the declared scope, not runtime provenance of context |
| "Implement small, scoped patches" | **C** | none | Residual: no governed size concept |
| "Keep Nornyx positioned as a control-plane language first" | **C** | none | Residual: product direction, not a decision |
| Architect / Builder / Reviewer / Security role guidance | A + C | `agents` with capability holdings for the permission parts | The prose guidance per role stays in `AGENTS.md` |

Note the shape of the result: the migrated portion is real and checkable, and
roughly half the file does not move. That ratio is normal and healthy.

---

## Eval Config Guidance

**Supported and repo-grounded:** promptfoo-shaped case rows —

```json
{"request": "Where is my order #4400?", "expected": "status_lookup"}
```

— together with holdout files and metric thresholds, as used by
`examples/crewai_governance_benchmark/contract/eval/` and
`examples/agentic_network_support/eval/`.

Metric thresholds are real: `evals.metrics` entries accept a bare metric name
or a threshold expression, evaluated with comparison operators against observed
metrics.

**Evidence gaps — not supported by anything in this repository:**

- OpenAI Evals
- DeepEval
- ragas
- any other non-promptfoo eval format

No mapping is offered for these because no artifact here demonstrates one.
Treat a proposed mapping for them as unverified until an example exists.

---

## Policy File Guidance

**Harness policies are evaluated against declared flow steps. They do not
inspect arbitrary runtime data, prompts, logs, repository diffs, deployments,
or tool traffic.**

Concretely:

- A `production` / `deploy` rule **can flag a declared flow step** whose text
  says "deploy to production".
- It **does not intercept a real deployment** unless another system routes that
  deployment decision through a governed authorization or approval path.

The same applies to `secret` rules and secret handling, and to `destructive`
rules and destructive operations. In each case `.nyx` records that you declared
the constraint over a declared flow. Enforcement of the real action belongs to
the authorization SPI (if the call path is wrapped) or to an external system.

When migrating a policy document, split it into:

1. decisions expressible on the authorization surface — capabilities, zones;
2. declared-flow constraints within the recognized token families;
3. everything else — residual list.

---

## Residual List Template

**A migration with an empty residual list is suspicious. It may mean the
migration over-mapped guidance into controls.**

Include this table in your migration PR:

```markdown
## Residual Guidance Not Migrated to .nyx

| Source instruction | Reason not migrated | Where it remains | Future option |
| --- | --- | --- | --- |
| prefer small PRs | no governed size concept | AGENTS.md | possible future lint/check |
| write clear commit messages | no commit-message concept | AGENTS.md | external commit policy |
| be concise | style guidance, not governed decision | AGENTS.md | reviewer convention |
```

---

## Wording for Migration PRs

Use language that survives review.

**Say:**

- "can declare" / "can check" / "can preserve as context" / "can link as evidence"
- "captures the governed part, not the writing preference"
- "records the approval boundary, not deployment control"
- "N instructions migrated, M retained as guidance — see residual list"

**Do not say:**

- that `.nyx` replaces `AGENTS.md`, policy docs, or eval configs
- that `policies.deny` entries are enforced at runtime
- that migration preserves all behaviour or converts all governance
- that a green check proves the instructions are followed

---

## What This Guide Does Not Cover

- **Standards mapping.** Issue #47 and
  [`64_STANDARDS_MAPPING_AND_ENTERPRISE_ASSURANCE.md`](64_STANDARDS_MAPPING_AND_ENTERPRISE_ASSURANCE.md)
  are not started and are not addressed here.
- **Extending the recognized rule families.** The five families are what the
  policy runtime matches today. Widening them is runtime work with its own
  review, not a documentation change, so this guide describes the current
  behaviour rather than a desired one.
- **Non-promptfoo eval formats.** Named above as evidence gaps.
- **Runtime provenance of context.** Whether context is trustworthy is outside
  the Tier 2 boundary.
- **External adoption.** Nothing here is evidence that anyone outside the
  maintainer flow has migrated anything.

## Future Follow-Ups

Recorded, not committed to:

- An **inert-rule linter** flagging `policies.deny` names outside the
  recognized families would make this guide's central warning enforceable
  rather than advisory. This is the highest-value follow-on identified by the
  grounding pass.
- ~~A **checkable worked example** contract under `examples/`~~ — **done in
  M5-A-3**: [`examples/agents_migration_example/`](../examples/agents_migration_example/README.md)
  ships a validated contract *and* a structurally tested residual list, so CI
  checks both the mapped and the unmapped half. The worked example in this
  guide remains illustrative; that directory is the evidence.
- Widening recognized rule families, if real migrations show consistent
  demand — with tests, as runtime work.

## Related

- [`66_M5_A2_EXTERNAL_ADOPTION_SOLICITATION.md`](66_M5_A2_EXTERNAL_ADOPTION_SOLICITATION.md)
  — external adoption path, reviewer quickstart, success criteria
- [`examples/external_adoption_pilot/README.md`](../examples/external_adoption_pilot/README.md)
  — the pilot demonstrating the authorization surface
- [`03_ROADMAP_TO_v1_AND_BEYOND.md`](03_ROADMAP_TO_v1_AND_BEYOND.md) — M5 status
