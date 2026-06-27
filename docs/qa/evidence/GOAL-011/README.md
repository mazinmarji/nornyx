# GOAL-011 Evidence: LSP and Editor Tooling

## Summary

GOAL-011 added local editor tooling scaffolds.

Implemented:

- `nornyx.editor_tools` for syntax highlighting metadata, editor manifest,
  LSP-shaped diagnostics, completion items, document symbols, and JSON output;
- CLI commands: `editor-manifest`, `syntax`, `lsp-diagnostics`, `complete`,
  and `symbols`;
- regression tests for editor manifest safety, syntax metadata, diagnostics,
  parse errors, reference completions, document symbols, and CLI JSON output;
- documentation for local editor integration and the non-server boundary.

## Validation

Commands run:

```bash
python -m ruff check nornyx\editor_tools.py nornyx\cli.py tests\test_editor_tools.py tests\test_cli_dx.py
python -m pytest tests\test_editor_tools.py tests\test_cli_dx.py -q
python -m nornyx.cli editor-manifest --out generated\editor_manifest_goal_011.json
python -m nornyx.cli syntax --out generated\syntax_goal_011.json
python -m nornyx.cli lsp-diagnostics examples\governed_delivery_control_plane.nyx --out generated\lsp_diagnostics_goal_011.json
python -m nornyx.cli complete examples\governed_delivery_control_plane.nyx --path agent.policy --prefix Safe --out generated\completions_goal_011.json
python -m nornyx.cli symbols examples\governed_delivery_control_plane.nyx --out generated\symbols_goal_011.json
python -m pytest -q
python -m nornyx.cli check examples\governed_delivery_control_plane.nyx
python -m nornyx.cli check examples\nornyx_roadmap_goals.nyx
```

Result:

- focused editor/CLI tests passed: `12 passed`;
- editor metadata commands completed and wrote ignored generated JSON outputs;
- full validation passed.

## Risk Note

This patch provides local JSON contracts only. It does not start a long-running
LSP server, install an editor extension, add Tree-sitter, call models, enable
connectors, access networks, or mutate files except through the existing
explicit `fmt --write` path.

## Evidence Note

Generated GOAL-011 artifacts show:

- editor manifest with `starts_language_server: false`;
- syntax metadata for canonical and deferred Nornyx blocks;
- empty diagnostics for `examples/governed_delivery_control_plane.nyx`;
- `SafeEditPolicy` completion for `agent.policy`;
- document symbols for project, context, skills, policy, agents, harness,
  trace, eval, approval, and budget.

## Approval

Human approval is required before merge, release, public syntax change,
dependency addition, connector enablement, or security-model change.
