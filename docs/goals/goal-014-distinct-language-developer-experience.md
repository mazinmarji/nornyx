# GOAL-014 — Distinct Language Developer Experience

## Goal

Make Nornyx visibly distinct and easier to adopt by adding the first developer-experience layer:

- easy init;
- doctor readiness check;
- canonical formatting;
- explainability;
- profiles;
- distinct-language strategy docs;
- integration/tooling roadmap.

## Non-goals

- No full parser rewrite.
- No LSP implementation yet.
- No Tree-sitter grammar yet.
- No harness runtime execution.
- No external connector execution.

## Scope

Added/updated:

```text
nornyx/doctor.py
nornyx/fmt.py
nornyx/explain.py
nornyx/profiles.py
nornyx/cli.py
examples/nornyx_distinct_language_showcase.nyx
profiles/*.yaml
extensions/*.yaml
docs/23_DISTINCT_LANGUAGE_STRATEGY.md
docs/24_EASY_INSTALL_USE_ADAPT_INTEGRATE.md
docs/25_LLM_NATIVE_LANGUAGE_DX.md
docs/tooling/26_TOOLING_ROADMAP_LSP_TREESITTER.md
tests/test_cli_dx.py
```

## Validation

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

## Evidence

```text
docs/qa/evidence/GOAL-014/
```

## Done definition

- CLI DX commands work.
- Tests pass.
- Docs clearly distinguish Nornyx as a context-native agentic engineering language.
- No runtime/external execution is introduced.
