# Nornyx Developer PMO Portal

A lightweight local-only PMO portal dedicated to Nornyx language development.

This version is intentionally box-based and focused on:

- PMO status from `docs/pmo/status/current_status.json`;
- direct local Git status from read-only `git` commands;
- optional remote GitHub branch check through read-only `git ls-remote`;
- a local KPI quality panel from deterministic repo metrics;
- an inspiring vision map layer from `vision_map.maps`;
- goal/work cards with completion, risk, evidence, and next work.

## Run — recommended

From the repository root:

```bash
python apps/nornyx-dev-pmo-portal/server.py --enable-all
```

Open:

```text
http://127.0.0.1:5174
```

## Run — local PMO + local Git only

No remote network call:

```bash
python apps/nornyx-dev-pmo-portal/server.py --enable-api --enable-git-api
```

## Windows PowerShell

```powershell
python apps\nornyx-dev-pmo-portal\server.py --enable-all
```

## APIs

```text
/api/dev/pmo/status
/api/dev/git/status
/api/dev/kpi/status
/api/dev/vision-map
```

## Git status behavior

The portal uses an allowlisted, read-only Git CLI layer:

```text
git rev-parse
git branch --show-current
git log -1
git status --porcelain
git rev-list --left-right --count
git remote get-url
git ls-remote   # only when remote Git is enabled
```

It does not write to the repo, run arbitrary shell commands, or require a GitHub token.

The KPI panel is also read-only. It uses local repo metrics and evidence-folder
scoring only; it does not run tests, call networks, or mutate files.

## Safety

- Intended for local developer use.
- Default host is `127.0.0.1`.
- No LLM calls.
- No UI shell execution.
- No external connectors.
- No secrets required.
- Remote Git status is opt-in through `--enable-remote-git` or `--enable-all`.
