# GOAL-018 Evidence — Optional Portal Contract Extension

## Summary

Adds a small optional portal-contract extension so Nornyx can describe role views and render targets without becoming a portal engine.

## Added

```text
docs/decisions/ADR-0012-portal-contract-not-portal-engine.md
docs/30_NORNYX_OPTIONAL_PORTAL_CONTRACT_EXTENSION.md
schemas/portal_contract.schema.json
examples/nornyx_portal_contract.nyx
nornyx/portal_contract.py
tests/test_portal_contract_extension.py
```

## Safety

This is contract/validation only.

It does not add a React portal, authentication, database, connectors, shell execution, LLM calls, production actions, or automatic writes.

## Validation

```text
python -m pytest -q tests/test_portal_contract_extension.py
```
