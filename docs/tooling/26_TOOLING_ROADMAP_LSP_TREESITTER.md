# Tooling Roadmap — LSP, Tree-sitter, VS Code, and CI

## Why this matters

A language without tooling is a file format.

Nornyx needs enough tooling that humans and LLMs can work with it safely.

## Strategic status under the post-v1.0 reweighting

Per `docs/03_ROADMAP_TO_v1_AND_BEYOND.md`, tooling in this file splits into two
tiers:

- **Acceptable near-term tooling:** `fmt`, `check`, `explain`, `doctor`,
  diagnostics, completion data, the editor manifest, and the local JSON
  commands. These stay on the roadmap because they serve the CLI-first design
  rule.
- **Adoption-gated (P3):** the full LSP, the Tree-sitter grammar, the
  package/profile registry, and any extension marketplace. The version-tagged
  sections below are historical planning surface, not commitments; none of
  these items proceeds until every promotion gate passes:
  1. repeated user requests for the capability;
  2. at least one external pilot blocked by the missing tooling;
  3. a stable schema, formatter, and checker;
  4. an identified owner and maintenance plan.

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

Adoption-gated (P3) — see the strategic status section above:

- stable LSP;
- package/profile registry support;
- extension manifests;
- MCP/A2A connector diagnostics;
- OpenTelemetry trace export;
- PMO portal integration;
- migration tooling.

## Design rule

Do not build an IDE first. Build a strong CLI, stable schema, and deterministic formatter first.
