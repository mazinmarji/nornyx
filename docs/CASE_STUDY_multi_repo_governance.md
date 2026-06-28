# Case study: dogfooding Nornyx until its own governance broke

*How an adversarial two-repo test and a cold-start trial found three real bugs in
Nornyx — including in Nornyx's own recommended drift gate — and what shipped to
fix them (v1.1.5 → v1.1.9).*

## The claim under test

Nornyx turns scattered AI-engineering control files (`AGENTS.md`, policy, harness,
evals, evidence) into one checked `.nyx` source, with a drift gate so they can't
fall out of sync. The pitch that justifies it for a real org is **multi-repo**:
keep policy consistent across many repos. So the question wasn't "does it generate
files" — it was "does the consistency story actually hold when you push on it?"

## Step 1 — build a real app under it

We built **GovFlags**, a small feature-flag API, end-to-end under a contract:
`BRD.md → govflags.nyx → generated control artifacts → tested FastAPI app + a
drift-gate CI`. 24 tests, governance encoded as executable tests, AGENTS.md
generated at the repo root. Clean. The single-repo story worked.

## Step 2 — attack the multi-repo claim

We added a second governed app, **NotifySvc**, sharing GovFlags' `SafeDeliveryPolicy`.
Then we evolved the org standard in one repo and watched what each safety net
caught.

| Safety net | Caught the divergence? |
|---|---|
| GovFlags' own Nornyx drift gate | **No — green** |
| NotifySvc's own Nornyx drift gate | **No — green** |
| (there was no org-level check) | — |

Both repos passed their own gates while the shared policy silently diverged. Two
distinct bugs fell out of this:

**Bug 1 — cross-repo blind spot.** Nornyx enforced consistency *within* a repo but
had no notion of a policy living *above* repos. Each repo owned a copy; change one
and the others never knew.

**Bug 2 — the recommended gate under-checked.** Sharper and more embarrassing: the
drift gate in Nornyx's *own* `USE_IN_YOUR_REPO.md` diffed **only `AGENTS.md`**. But
`AGENTS.md` doesn't render policy rules — those live in `policy.yaml`. So a policy
change left `AGENTS.md` byte-identical and the gate passed **green**. The tool's
own guidance gave a false sense of safety.

## Step 3 — fix them in the open

- **`nornyx drift <contract> --out <dir>`** (v1.1.6) — full-output gate; compares
  *every* generated artifact by hash, so `policy.yaml` drift is caught.
- **`nornyx workspace-check`** (v1.1.6) — a workspace manifest declares canonical
  policies once and verifies every member repo matches. No more silent divergence.
- **`nornyx workspace-check --write`** (v1.1.7) — sync mode: edit the policy once
  in the manifest and *propagate* it into each member, surgically (only the rule
  block is rewritten; comments and other blocks preserved), so members stay
  self-contained and `nornyx check`-valid.

Deliberately **not** done: a language-level `policy-ref`. That would reopen the
frozen v1.0 schema and force a cross-repo resolution/lockfile design, and it
trades away a property worth keeping — a contract that's auditable on its face.
Sync mode gives single-source-at-authoring without those costs.

## Step 4 — cold-start as a stranger

Then we threw away all the author's context: fresh venv, `pip install` the wheel,
follow the README like a new user, `nornyx init` two services, write a workspace
manifest, run sync.

**Bug 3 — sync no-opped on real contracts.** `nornyx init` (and `yaml.safe_dump`)
emit the policy list as a YAML block sequence at the key's own indent
(`policies:` then `- name:` at column 0). The sync editor assumed items were
indented deeper, so on exactly the contracts new users get, `--write` either did
nothing or leaked old rules. Fixed in v1.1.9, with regression tests for both YAML
indentation forms.

## What this says about whether Nornyx is "needed"

- The single-repo source-of-truth + drift gate is **solid** — that part held
  throughout.
- The multi-repo consistency story — the part that actually justifies the tool for
  a real org — **did not hold out of the box**, and the built-in gates gave a
  *false green*. That's the most important kind of bug for a governance tool, and
  it was only found by attacking the tool with its own use case.
- Every fix was driven by a concrete failing scenario, not a roadmap. The cold-start
  trial (no author context) found a bug the author never would have.

The honest takeaway: the need is real and the wedge (drift + audit across repos) is
real, but the value comes from *being attacked and fixed in public*, not from a
feature list. Three releases of bug-fixes later, the multi-repo story holds end to
end — and the process of getting there is the strongest evidence that the tool is
doing something real.

## Timeline

| Version | What |
|---|---|
| v1.1.5 | Ship JSON schemas inside the wheel (`nornyx schema` worked for pip users) |
| v1.1.6 | `nornyx drift` (full-output gate) + `nornyx workspace-check` |
| v1.1.7 | `workspace-check --write` (sync mode) |
| v1.1.8 | Sync edge-case hardening + scheduled-job docs |
| v1.1.9 | Fix sync no-op on `init`-style block sequences (found by cold-start) |
