# Nornyx Architecture

## Current architecture

The implemented product is a static contract and control-plane language. The
current processing path is:

```text
.nyx contract
  -> YAML-compatible safe parser
  -> hard-coded semantic checker
  -> deterministic compatibility-artifact generator
```

Additional implemented components create static reports, manifests, evidence
scaffolds, governed-package artifacts, and readiness plans. Their names may
include `runtime`, `adapter`, or `connector` for historical reasons, but they do
not turn Nornyx into an autonomous execution engine.

## Contract-only surface

- `nornyx.parser` parses local `.nyx` data and resolves local policy references.
- `nornyx.checker` performs static semantic checks.
- `nornyx.generator` writes local derived artifacts.
- `nornyx.context_builder` builds local context packs with provenance.
- `nornyx.evidence` creates evidence scaffolds.
- `nornyx.harness_runtime` produces bounded plans and reports; it does not run
  arbitrary project commands.
- Adapter and connector modules validate declarations and readiness metadata;
  they do not open live connectors, load credentials, or deploy software.
- The governed-package scanner reads local payloads without executing them.

## Planned governance extension

The Declarative Governance Extension Framework is planned as an additive,
data-only layer:

```text
local profile/module data
  -> safe schema validation
  -> deterministic local resolution
  -> monotonic composition
  -> constrained rule evaluation
  -> existing checker and generator surfaces
```

In PR 1, this pipeline is a specification and test foundation only. No loader,
registry, composition engine, rule evaluator, or starter renderer has been
connected to `nornyx check`, `nornyx init`, or any public API.

## Deferred and superseded descriptions

Earlier architecture notes described an AST, context compiler, harness runtime,
eval runner, trace/evidence runtime, and connector-adapter execution pipeline as
the v1.0 architecture. That diagram was an aspirational roadmap, not implemented
behavior. It is superseded as a statement of current product identity.

Future work may add bounded static analysis and local evidence import, but live
adapter execution, model orchestration, deployment, credential loading,
automatic approval, and arbitrary command execution remain non-goals unless a
separate capability design and human approval explicitly changes that boundary.

## Stable identity

Nornyx remains a generalized contract/checker/generator/governance language,
not a general-purpose programming language or autonomous runtime. Planned
features must preserve deterministic outputs, explicit evidence and approvals,
human authority for high-impact actions, and fail-closed safety behavior.
