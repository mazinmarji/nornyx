# Nornyx Easy Install / Use / Adapt / Integrate Plan

## Goal

Make Nornyx simple enough for first contact, but deep enough for serious AI engineering.

## Installation targets

### v0.1 / v0.2

```bash
pip install -e ".[dev]"
python -m pytest -q
nornyx doctor
```

### Developer global install

```bash
pipx install nornyx
# or
uv tool install nornyx
```

### Later binary install

Ship standalone binaries for:

- Windows x64;
- Linux x64;
- macOS arm64.

## First five-minute experience

```bash
nornyx init --profile ai_coding --name MyProject --out project.nyx
nornyx check project.nyx
nornyx explain project.nyx
nornyx generate project.nyx --out generated/my_project
nornyx doctor
```

## Progressive learning ladder

| Level | User learns | Required concepts |
|---|---|---|
| 1 | Define a goal | `project`, `goal`, `intent` |
| 2 | Add context and agent | `context`, `agent`, `skill` |
| 3 | Add governance | `policy`, `approval`, `budget` |
| 4 | Add quality | `test`, `eval`, `guardrail` |
| 5 | Add runtime behavior | `harness`, `trace`, `evidence` |
| 6 | Add ecosystem integration | `connector`, `extension`, `profile` |
| 7 | Add advanced AI behavior | `healing`, `improvement_loop`, `memory_policy` |

## Built-in profiles

This overlay adds an initial profile model:

```text
minimal
standard
ai_coding
regulated
legacy_upgrade
nornyx_language
agentic_repo_harness
telecom_ops
business_ops
ai_governance
finance_ops
```

Each profile has a local metadata file under `profiles/` and controls the
starter `.nyx` shape. The v0.3 domain profile packs are optional overlays on the
v0.2 graph/contract surface; they do not enable adapters, live connectors,
automatic approvals, or production runtime behavior.

The first complete authoring path is:

```bash
nornyx profiles
nornyx init --profile ai_coding --name MyProject --out project.nyx
nornyx check project.nyx
nornyx fmt project.nyx --check
nornyx explain project.nyx
nornyx doctor
```

## Integration targets

Nornyx should generate or integrate with:

- AGENTS.md;
- CLAUDE.md;
- GitHub Copilot instructions;
- skills folders;
- GitHub Actions;
- JSON Schema;
- OpenAPI;
- MCP connector manifests;
- A2A peer-agent contracts;
- OpenTelemetry GenAI trace conventions;
- Developer PMO Portal status JSON;
- evidence packs.

## Non-lock-in rule

Nornyx should **generate standard artifacts first** and enforce runtime behavior later.

This makes adoption possible even before the Nornyx runtime is mature.
