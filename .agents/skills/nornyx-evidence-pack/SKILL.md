# nornyx-evidence-pack

## Purpose

Create evidence folders, validation summaries, trace summaries, risk updates, and approval logs.

## Safe operating rules

- Work only from a scoped goal packet.
- Do not enable external connectors or MCP servers.
- Do not handle secrets or credentials.
- Do not run destructive commands.
- Require human approval for syntax, security, dependency, release, or connector changes.
- Record evidence under `docs/qa/evidence/<GOAL-ID>/`.

## Output contract

```markdown
## Skill Result
- Goal ID:
- Summary:
- Files changed:
- Commands run:
- Evidence path:
- Risks:
- Approval required:
```
