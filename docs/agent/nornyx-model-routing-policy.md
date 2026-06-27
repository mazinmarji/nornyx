# Nornyx Model Routing Policy

## Purpose

Choose the cheapest safe model/reasoning level for each Nornyx goal.

## Routing matrix

| Work type | Codex profile | Claude review | Human approval |
|---|---:|---:|---:|
| Docs/examples | standard | optional | none |
| Parser/checker tests | elevated | optional | recommended |
| Generator/artifact compatibility | elevated | required | recommended |
| Grammar or public syntax | maximum | required | required |
| Security/capability/connector policy | maximum | required | mandatory |
| Runtime execution/harness loops | maximum | required | required |
| Release/tag/public announcement | blocked unless approved | required | mandatory |

## Escalation

- First validation failure: fix in scope.
- Second validation failure: raise reasoning and narrow context.
- Third validation failure: stop and write failure record.
- Security-sensitive ambiguity: stop and request review.
