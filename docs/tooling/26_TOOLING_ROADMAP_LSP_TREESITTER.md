# Tooling Roadmap — LSP, Tree-sitter, VS Code, and CI

## Why this matters

A language without tooling is a file format.

Nornyx needs enough tooling that humans and LLMs can work with it safely.

## v0.2 tooling

- `nornyx fmt`
- `nornyx explain`
- `nornyx doctor`
- schema/reference diagnostics
- GitHub Actions workflow scaffold

## v0.3 tooling

- formal grammar specification;
- Tree-sitter grammar for syntax highlighting and structural parsing;
- JSON Schema for v0.1 YAML-compatible form;
- VS Code extension with syntax highlighting;
- LSP prototype with diagnostics and completion.

## v0.8 local editor scaffold

GOAL-011 adds local editor-facing JSON commands:

```bash
python -m nornyx.cli editor-manifest --out generated/editor_manifest.json
python -m nornyx.cli syntax --out generated/nornyx_syntax.json
python -m nornyx.cli lsp-diagnostics examples/governed_delivery_control_plane.nyx --out generated/lsp_diagnostics.json
python -m nornyx.cli complete examples/governed_delivery_control_plane.nyx --path agent.policy --prefix Safe
python -m nornyx.cli symbols examples/governed_delivery_control_plane.nyx
```

The scaffold provides:

- syntax highlighting metadata for canonical and deferred top-level blocks;
- LSP-shaped diagnostics from parser/checker output;
- completion items for top-level blocks and common references;
- document symbols for project and named block entries;
- formatting through the existing deterministic `nornyx fmt` command.

This is not a long-running LSP server and not a Tree-sitter grammar. It is a
stable local contract that an editor extension can consume without network,
connector, model, or runtime execution.

## v0.4 tooling

- go-to-definition for agents, contexts, policies, harnesses, evals, and skills;
- rename support;
- missing-reference quick fixes;
- inline evidence/gate warnings;
- generated context preview.

## v1.0 tooling

- stable LSP;
- package/profile registry support;
- extension manifests;
- MCP/A2A connector diagnostics;
- OpenTelemetry trace export;
- PMO portal integration;
- migration tooling.

## Design rule

Do not build an IDE first. Build a strong CLI, stable schema, and deterministic formatter first.
