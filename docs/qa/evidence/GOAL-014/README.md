# GOAL-014 Evidence — Distinct Language Developer Experience

## Summary

This overlay adds the first dedicated developer-experience layer for Nornyx:

- `nornyx init`
- `nornyx doctor`
- `nornyx fmt`
- `nornyx explain`
- `nornyx profiles`

It also adds docs and examples that clarify how Nornyx becomes distinct, easy to learn, easy to install, easy to adapt, and easy to integrate.

This completion patch closes the remaining GOAL-014 gaps:

- exposes the documented `nornyx doctor` CLI command;
- keeps `nornyx doctor --json` available for tooling;
- makes the distinct-language showcase pass `nornyx check`;
- records metadata for every built-in starter profile;
- documents the stable first authoring loop.

## Changed files

- `nornyx/cli.py`
- `tests/test_cli_dx.py`
- `examples/nornyx_distinct_language_showcase.nyx`
- `profiles/legacy_upgrade.yaml`
- `docs/24_EASY_INSTALL_USE_ADAPT_INTEGRATE.md`
- `docs/25_LLM_NATIVE_LANGUAGE_DX.md`
- `docs/pmo/status/current_status.json`
- `docs/qa/evidence/GOAL-014/README.md`

## Safety

- No LLM calls.
- No external connectors.
- No shell execution from UI.
- No production access.
- No secrets handling.
- No autonomous self-modification.

## Validation expected

```bash
python -m pytest -q tests/test_cli_dx.py
python -m pytest -q
nornyx profiles
nornyx init --profile ai_coding --name Demo --out generated/demo_project.nyx --force
nornyx check generated/demo_project.nyx
nornyx fmt generated/demo_project.nyx --check
nornyx explain generated/demo_project.nyx
nornyx doctor
```


## PMO status

GOAL-014 should appear as a normal goal card in the Developer PMO Portal. Its PMO block title is now `GOAL-014 — Distinct Language Developer Experience`.

The block is now complete because the scoped GOAL-014 DX layer is usable through
the local CLI. Grammar-native parsing, real LSP/Tree-sitter support, runtime
execution, and connector execution remain outside this goal and stay future
work under separate packets.

## Risk note

Risk is low. The patch is local CLI/docs/test/example/profile metadata only. It
does not call LLMs, execute harness flows, enable connectors, load secrets,
deploy software, or change parser/checker semantics.

## Approval requirement

Human approval is required before merge, release, public syntax change,
dependency addition, connector enablement, runtime execution expansion, or
security-model change.
