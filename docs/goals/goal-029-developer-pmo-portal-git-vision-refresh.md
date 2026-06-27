# GOAL-029 — Developer PMO Portal Git Status and Vision Map Refresh

## Goal

Replace the weak portal experience with a clean local Developer PMO Portal that shows:

```text
box-based PMO status
direct local Git status
optional remote GitHub status
inspiring vision map
goal/work cards
```

## Scope

Add:

```text
read-only git status API
optional remote GitHub branch check using git ls-remote
box-based local portal UI
vision map renderer
tests for git status helpers
updated portal README
evidence note
```

## Non-goals

Do not add:

```text
GitHub token integration
GitHub API writes
shell execution from UI
LLM calls
production deployment
remote command execution
public hosting
```

## Acceptance

```powershell
python -m pytest -q tests/test_nornyx_dev_pmo_portal_git_status.py
python apps\nornyx-dev-pmo-portal\server.py --enable-all
```

Open:

```text
http://127.0.0.1:5174
```
