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

### Pre-commit hook (`.git/hooks/pre-commit`)

```bash
#!/bin/sh
nornyx check nornyx.nyx || exit 1
nornyx generate nornyx.nyx --out .nornyx-check >/dev/null
if ! diff -q AGENTS.md .nornyx-check/AGENTS.md >/dev/null; then
  echo "AGENTS.md is out of sync with nornyx.nyx — run: nornyx generate nornyx.nyx --out . " >&2
  exit 1
fi
```

### GitHub Actions

```yaml
- run: pip install nornyx
- run: nornyx check nornyx.nyx
- run: nornyx generate nornyx.nyx --out .nornyx-check
- run: diff AGENTS.md .nornyx-check/AGENTS.md   # fails the build on drift
```

Now the `.nyx` is the single source of truth: edit it, regenerate, and CI fails
loudly if any committed artifact drifts. That's the whole point — one checked
source instead of a dozen hand-maintained files going stale.

## Scope reminder

Nornyx is a spec/checker layer, not a runtime. It generates and validates control
artifacts; it does not run your agents, deploy, or touch credentials.
