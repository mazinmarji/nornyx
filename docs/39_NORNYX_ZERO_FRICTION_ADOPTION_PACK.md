# Nornyx Zero-Friction Adoption Pack

## Purpose

The Zero-Friction Adoption Pack makes Nornyx useful before a user understands the full language.

The first experience should be:

```text
inspect repo
suggest adoption level
generate minimal .nyx
run fast checks
use Codex/Claude with clearer rails
```

## Adoption levels

| Level | Meaning | Behavior |
|---|---|---|
| `observe` | Advise only | Detect repo signals and suggest next step |
| `lite` | Minimal AI-coding rails | Generate minimal `.nyx`, safe policy, fast harness |
| `standard` | Normal Nornyx repo workflow | Add evidence, delivery state, quality gates |
| `team` | Multi-role delivery | Add role views, approval, task packets |
| `regulated` | High-assurance work | Add decision boundaries and evidence quality |
| `enterprise` | Organization-scale governance | Add compatibility, conformance, policy integration |

## First useful command

```powershell
python -m nornyx.cli adopt init-lite --project MyRepo --out nornyx.project.nyx
```

This creates a minimal, reviewable `.nyx` draft.

## Repo status command

```powershell
python -m nornyx.cli adopt status --repo .
```

This reports:

```text
languages detected
test folders detected
docs detected
AGENTS.md present or missing
recommended profile
recommended first command
```

## Lite `.nyx` output

Lite mode generates only the essential structure:

```text
project
intent
context
safe policy
builder agent
fast harness
basic eval
evidence requirements
```

It does not force full PMO, regulated controls, product lifecycle, or portal setup.

## Clean downstream validation

The adoption check validates the first-use path in a temporary clean repo:

```text
create minimal downstream repo signals
generate nornyx.project.nyx
run the current Nornyx checker on the generated draft
confirm init-lite does not overwrite without --force
```

This keeps the adoption promise practical without adding installers, network
setup, portal onboarding, or remote writes.

## Upgrade rule

Nornyx should recommend upgrade only when signals justify it:

```text
multiple active goals
multiple agents
security-sensitive work
release/operations handover
regulated or customer-impacting workflow
```

## Authoring relationship

```text
Zero-Friction Adoption = first five minutes
Authoring Assistant = guided creation and review experience
Full Nornyx = mature control-plane workflow
```

## Safety boundaries

The pack is local-only.

It must not:

```text
call an LLM
write remote GitHub state
overwrite files unless --force is used
auto-approve drafts
run production commands
implement the future authoring wizard
```
