# Nornyx 5-Minute Adoption

## Install Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

On Windows PowerShell, activate with:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Inspect A Repo

```bash
python -m nornyx.cli adopt status --repo .
```

Expected output: a local JSON readiness summary with suggested first adoption
steps. This does not call networks, connectors, models, or deployment systems.

## Inspect Schema Targets

```bash
python -m nornyx.cli schema
python -m nornyx.cli schema --version 0.2
python -m nornyx.cli schema --version 1.0
```

Expected output: local JSON schema metadata with `issues: []`. The default
schema command uses the compatibility target. The `0.2` target names the static
graph/contract schema, and the `1.0` target names the stable generalized
contract-language schema.

Schema inspection is not document validation. Use `check` for `.nyx` files.

## Create A Lite Draft

```bash
python -m nornyx.cli adopt init-lite --project ExampleProject --out nornyx.project.nyx
```

Expected output: a minimal `.nyx` draft containing project, intent, policy,
approval, evidence, and budget scaffolding.

## Check The Draft

```bash
python -m nornyx.cli check nornyx.project.nyx
```

Expected output: `Nornyx check passed` when the local contract is valid.

## Generate Local Artifacts

```bash
python -m nornyx.cli generate nornyx.project.nyx --out generated/nornyx
```

Expected output: local control-plane artifacts such as agent instructions,
policy, eval, context, harness, and evidence contract files.

## Boundary

This adoption path is local and review-first. It does not execute agents, run
live connectors, call models, deploy software, grant approvals, publish
packages, change schema routing, or unlock GOAL-100.
