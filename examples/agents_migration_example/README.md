# Bounded AGENTS.md migration example

**This example is not a full AGENTS.md conversion. It is a bounded migration
example with an explicit residual set.**

Two files, both checked:

| File | What it is |
| --- | --- |
| `agents_migration_example.nyx` | The **mapped** half — a subset of this repository's root `AGENTS.md` expressed as governed decisions |
| `residual_guidance.yaml` | The **unmapped** half — instructions that deliberately stay outside `.nyx`, and why |

## What this proves

- A subset of real `AGENTS.md` guidance can be expressed as a contract that
  passes `nornyx check` — declared agents, capability and approval boundaries,
  evidence requirements, and eval metrics.
- Every `deny` rule in the contract sits inside a token family the policy
  runtime actually evaluates. A test enforces this.
- A residual set exists, is non-empty, and every entry names where the
  guidance still lives.

## What this does not prove

- **Not** that `AGENTS.md` can be replaced. It remains authoritative, and the
  contract names it under `contexts.authority`.
- **Not** that the migrated rules are enforced at runtime. `policies.deny`
  entries are declared-flow checks over declared harness steps, not runtime
  interception of secrets, deployments, or destructive operations. See
  [`docs/67_M5_A2B_MIGRATION_GUIDE_AGENTS_POLICIES_EVALS.md`](../../docs/67_M5_A2B_MIGRATION_GUIDE_AGENTS_POLICIES_EVALS.md).
- **Not** that this migration is complete, representative of your repository,
  or a template to copy without judgement.
- **Not** any external adoption signal.

## Run it

```bash
python -m nornyx.cli check examples/agents_migration_example/agents_migration_example.nyx
python -m nornyx.cli check examples/agents_migration_example/agents_migration_example.nyx --strict
```

Both pass. `--strict` (M5-A-4) fails on a `policies.deny` name outside the
evaluated rule-name vocabulary; this contract has none, which is the point.
Without `--strict` such a name only warns (`UNKNOWN_POLICY_RULE`), so existing
contracts are not broken.

Being *in* the vocabulary means a rule is **eligible** for evaluation — not that
it matches any particular declared flow. The diagnostic is about names, and
says nothing about outcomes.

Inspect the residual list:

```bash
python -c "import yaml,sys; d=yaml.safe_load(open('examples/agents_migration_example/residual_guidance.yaml',encoding='utf-8')); [print('-', e['source_instruction'], '->', e['where_it_remains']) for e in d['residual_guidance']]"
```

Run both halves' tests:

```bash
python -m pytest -q tests/test_agents_migration_example.py
```

## Why the residual list is required

CI validating only the contract would, over time, teach maintainers that only
the mapped controls matter — which is exactly the erosion the migration guide
warns about. So the residual list is tested too: it must exist, be non-empty,
and every entry must declare `source_instruction`, `reason_not_migrated`,
`where_it_remains`, and `future_option`.

The tests are **structural**. They do not pin the row count, the exact source
text, or the presence of any particular instruction — a test requiring specific
rows would break on unrelated `AGENTS.md` edits, and a brittle control is one
that eventually gets deleted, taking the control with it.

## Why a healthy migration leaves much outside .nyx

**A migration with no residual guidance is suspicious because it may have
over-mapped guidance into controls.**

Roughly half of the source guidance does not move here, and that ratio is
normal. "Implement small, scoped patches" has no governed size concept; "write
clear commit messages" has no commit-message concept. Encoding either as
`deny prefer_small_prs` or `deny clear_commit_messages` would produce a rule
the checker accepts and the policy runtime never evaluates — a contract that
looks governed and enforces nothing.

An honest omission is visible. An inert rule is not. That asymmetry is the
whole reason this example ships both halves.
