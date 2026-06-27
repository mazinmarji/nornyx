# Nornyx Architecture

## v0.1 architecture

```text
.nyx file
  -> parser
  -> checker
  -> generator
  -> compatibility artifacts
```

## v1.0 architecture

```text
.nyx source
  -> parser
  -> AST
  -> semantic analyzer
  -> policy/capability checker
  -> context compiler
  -> harness runtime
  -> eval runner
  -> trace/evidence runtime
  -> artifact generators
  -> connector adapters
```

## Core packages

- `nornyx.parser`: v0.1 YAML-compatible loader.
- `nornyx.checker`: semantic checks.
- `nornyx.generator`: artifact generation.
- `nornyx.context_builder`: context pack builder with provenance.
- `nornyx.evidence`: evidence pack scaffold.
- `nornyx.cli`: command-line interface.

## Non-goals for v0.1

- native compilation;
- live LLM orchestration;
- arbitrary command execution;
- production deployment;
- secret handling;
- self-modifying code.
