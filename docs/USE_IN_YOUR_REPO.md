# Use Nornyx in your repo

The demo shows Nornyx working on an example. This is how you adopt it on your own
project so your AI-engineering control artifacts stop drifting.

## 1. Scaffold a contract

```bash
pip install nornyx
nornyx init --name YourRepo --out nornyx.nyx
```

`nornyx init` writes a starter `.nyx`. Pick a profile with `--profile` (default
`ai_coding`):

```
minimal · standard · ai_coding · regulated · legacy_upgrade ·
agentic_repo_harness · telecom_ops · business_ops · ai_governance · finance_ops
```

## 2. Make it yours, then check it

Edit `nornyx.nyx` — set your `contexts` (which files are authority vs untrusted),
`policies` (e.g. `deny secrets_to_llm`, `require tests_if_code_changed`),
`agents`, and the `harness` flow + gates. Then:

```bash
nornyx check nornyx.nyx
```

## 3. Generate and place the artifacts

```bash
nornyx generate nornyx.nyx --out .nornyx/
```

This produces `AGENTS.md`, `skills/`, `harness.yaml`, `policy.yaml`, `evals.yaml`,
`context.yaml`, and `evidence_contract.md`. Put the ones your tools read where
they look for them — most importantly:

```bash
cp .nornyx/AGENTS.md AGENTS.md
```

`AGENTS.md` / `CLAUDE.md` at the repo root is what Claude Code, Cursor, and
Copilot pick up. Treat every generated file as **build output of `nornyx.nyx`** —
edit the `.nyx`, never the generated file.

## 4. Commit the source + the artifacts you use

Commit `nornyx.nyx` (the source of truth) and the generated artifacts you depend
on (e.g. `AGENTS.md`).

## Keep them from drifting

`nornyx generate` is deterministic (stable LF output), so a regenerate-and-diff
is a reliable drift gate.

> **Diff the whole generated set, not just `AGENTS.md`.** `AGENTS.md` does not
> render policy rules — those go to `policy.yaml`. A gate that only diffs
> `AGENTS.md` stays green when your *policy* changes. Commit the whole generated
> directory and use `nornyx drift`, which compares every artifact by hash.

Commit the generated directory (e.g. `.nornyx/`) alongside `nornyx.nyx`, then:

```bash
nornyx drift nornyx.nyx --out .nornyx   # exit 1 on any added/removed/changed artifact
```

### Pre-commit hook (`.git/hooks/pre-commit`)

```bash
#!/bin/sh
nornyx check nornyx.nyx >/dev/null || exit 1
nornyx drift nornyx.nyx --out .nornyx || {
  echo "Generated artifacts are out of sync. Fix: nornyx generate nornyx.nyx --out .nornyx" >&2
  exit 1
}
```

### GitHub Actions

```yaml
- run: pip install nornyx
- run: nornyx check nornyx.nyx
- run: nornyx drift nornyx.nyx --out .nornyx   # fails the build on any drift
```

Now the `.nyx` is the single source of truth: edit it, regenerate, and CI fails
loudly if any committed artifact drifts. That's the whole point — one checked
source instead of a dozen hand-maintained files going stale.

## Keep policy consistent across many repos

A single `.nyx` is the source of truth *within* one repo. It says nothing about
whether two repos share the same policy — each can carry a divergent copy of the
"same" org policy and still pass its own drift gate. For an org standard that
lives **above** repos, declare it once in a workspace manifest:

```yaml
# nornyx.workspace.yaml
workspace: AcmeOrg
policies:
  SafeDeliveryPolicy:
    - deny secrets_to_llm
    - require tests_if_code_changed
    - require human_approval_before_merge
members:
  - path: service-a/nornyx.nyx
  - path: service-b/nornyx.nyx
```

```bash
nornyx workspace-check --manifest nornyx.workspace.yaml   # exit 1 if any member diverges
```

This verifies every member's named policy matches the canonical rule set, so a
change to the org standard can't silently leave some repos behind.

**Edit once, propagate (sync mode).** Add `--write` to push the canonical policy
*down* into each member, so you maintain the org policy in exactly one place (the
manifest) instead of hand-copying it:

```bash
nornyx workspace-check --manifest nornyx.workspace.yaml --write
```

The rewrite is surgical — it replaces only the matched policy's rule block and
leaves the rest of each contract (comments, other blocks) untouched, so members
stay self-contained and auditable. A member that doesn't declare the policy at
all (or a missing file) is left for a human rather than invented. Run it in a
pre-commit hook or a scheduled job, and commit the propagated changes.

## Scope reminder

Nornyx is a spec/checker layer, not a runtime. It generates and validates control
artifacts; it does not run your agents, deploy, or touch credentials.
