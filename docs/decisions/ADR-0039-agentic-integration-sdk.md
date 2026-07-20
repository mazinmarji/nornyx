# ADR-0039 — Agentic Integration SDK: `nornyx.agentic` facade and distributable adapters

- Status: Proposed (design only; execution is a separate, owner-authorized milestone)
- Date: 2026-07-20
- Decision owner: human repository owner
- Relates to: ADR-0037 (AN-005 reference adapters, deliberately unpackaged)

## Context

AN-005 (ADR-0037) shipped CrewAI and LangGraph reference adapters under
`integrations/nornyx_agentic_adapters/`. They are **excluded from the wheel** —
correct, to keep heavy frameworks out of stable core — but they reach directly
into Nornyx internals. The imports in
`integrations/nornyx_agentic_adapters/governance_kernel.py` are, verbatim:

- `nornyx.agentic_artifacts` → `RUNTIME_EVENTS_SCHEMA_ID`,
  `RUNTIME_EVENTS_SCHEMA_VERSION`, `agentic_network_lock_digest`,
  `contract_digest`, `load_agentic_network_lock`, `verify_agentic_network_lock`
  (the harness/tests also use `build_/write_/render_*`)
- `nornyx.checker` → `check_document`, `has_errors`
- `nornyx.governance` → `GovernanceError`, `compose_document_governance`,
  `evaluate_document_governance`, `registry_for_contract` (tests also use
  `compose_governance`, `GovernanceRegistry`)
- `nornyx.parser` → `load_nyx`
- `nornyx.agentic_evidence` → `validate_runtime_events`, `load_runtime_events`

Two problems follow:

1. **Not distributable.** A `pip install nornyx` user cannot use the
   demonstrated integrations without cloning the repo and manipulating
   `sys.path` — the tests do exactly this
   (`sys.path.insert(0, str(INTEGRATIONS))`).
2. **No supported boundary.** The adapters depend on Nornyx's *internal* module
   layout, so any refactor of those internals silently breaks external adapters,
   and there is no contract describing what integrators may rely on.

## Decision

Introduce a **narrow, supported facade** `nornyx.agentic` (part of core
`nornyx`, shipped in the wheel) and move the adapters into a **separately
versioned, separately published** package `nornyx-agentic-adapters` that depends
only on that facade.

### 1. `nornyx/agentic/__init__.py` — the supported SPI

A curated re-export of exactly the integration surface, and nothing else. Every
name below is already public within its home module; this collects them into one
stable import path and pins the contract:

```python
# nornyx/agentic/__init__.py  (illustrative)
from nornyx.parser import load_nyx
from nornyx.checker import check_document, has_errors
from nornyx.governance import (
    GovernanceError, GovernanceRegistry,
    compose_governance, compose_document_governance,
    evaluate_document_governance, registry_for_contract,
)
from nornyx.agentic_artifacts import (
    RUNTIME_EVENTS_SCHEMA_ID, RUNTIME_EVENTS_SCHEMA_VERSION,
    LOCK_SCHEMA_ID, LOCK_FORMAT_VERSION, GENERATION_FORMAT_VERSION,
    contract_digest, agentic_network_lock_digest,
    build_agentic_network_lock, write_agentic_network_lock,
    load_agentic_network_lock, verify_agentic_network_lock,
    render_agentic_network_artifacts,
)
from nornyx.agentic_evidence import validate_runtime_events, load_runtime_events

SPI_VERSION = "1.0"  # the integration contract version, bumped independently
__all__ = [...]      # exactly the names above
```

Rules:

- The facade adds **no new behavior** — a curated re-export, so it cannot itself
  become a governance concept.
- `SPI_VERSION` is the integration contract version, independent of the package
  version (see `docs/VERSIONING.md`). Adapters declare the SPI range they
  support.
- A test (`tests/test_agentic_facade_surface.py`) freezes
  `nornyx.agentic.__all__` (adding a name is a reviewed change; removing or
  renaming one is a breaking SPI change) and asserts every name imports.

### 2. `nornyx-agentic-adapters` — the distributable package

One package (the adapters already share the framework-neutral
`governance_kernel`), with framework **extras** so a user installs only what
they need:

```
nornyx-agentic-adapters/            # separate PyPI project, own SemVer
  pyproject.toml                    # deps: nornyx>=1.7,<2 ; extras: [crewai], [langgraph]
  src/nornyx_agentic_adapters/
    __init__.py
    governance_kernel.py            # imports ONLY from nornyx.agentic
    crewai_adapter.py               # lazy `import crewai`; extra: [crewai]
    langgraph_adapter.py            # lazy `import langgraph`; extra: [langgraph]
    local_harness.py
```

- `pip install nornyx-agentic-adapters[crewai]` or `[langgraph]`; the base
  install pulls neither framework.
- The kernel imports **only** `from nornyx.agentic import ...` — never a private
  Nornyx module. The facade-surface test in core plus an import-boundary test in
  the adapter package enforce this.
- Preserve the existing invariant that **core `nornyx` never imports
  CrewAI/LangGraph**
  (`tests/test_agentic_integrations.py::test_default_install_does_not_package_integrations`
  already guards packaging; keep it).

### 3. Compatibility matrix (published in the adapter README + CI)

| adapters | nornyx SPI | CrewAI | LangGraph | Python |
| --- | --- | --- | --- | --- |
| 0.1.x | 1.0 (nornyx 1.7–1.x) | 1.15.x (test lowest+highest) | 1.2.x (test lowest+highest) | 3.10–3.13 |

The adapter package's CI tests the lowest and highest supported version of each
framework against the lowest and highest supported `nornyx`.

### 4. Migration for existing `integrations/` users

- Keep `integrations/nornyx_agentic_adapters/` in the Nornyx repo for one
  release as the source that is *synced* into the new package (or a thin shim
  re-exporting from it), with a deprecation note pointing at
  `pip install nornyx-agentic-adapters`.
- Update the AN-005/AN-006 docs and `run_demo.py` to import via `nornyx.agentic`
  plus the installed adapter package, and provide a **pip-only example** that
  runs without cloning `nornyx`.

## Consequences

- **Positive:** integrations become installable; the internal Nornyx layout is
  free to change behind a stable `nornyx.agentic` contract; core stays
  framework-free; the adapter package versions and releases on its own cadence.
- **Cost:** a second package to publish and a compatibility matrix to maintain —
  accepted, and strictly better than N adapters each reaching into internals.
- **Non-goals:** the facade does not expose the full governance implementation,
  does not add runtime execution, and does not let core import a framework.

## Alternatives considered

- **Separately versioned `nornyx-crewai` / `nornyx-langgraph`.** Rejected for
  now: the adapters share one kernel, so two packages would duplicate it.
  Revisit if the frameworks diverge enough that a shared kernel becomes a
  liability.
- **Ship adapters inside the `nornyx` wheel behind extras.** Rejected: it
  couples the core release cadence to framework churn and risks core importing a
  framework; the whole point of ADR-0037 was to keep them out of core.

## Execution checklist (follow-on milestone, not this ADR)

1. Add `nornyx/agentic/__init__.py` + `tests/test_agentic_facade_surface.py`;
   land in a `nornyx` minor release (≥1.8) that publishes the SPI.
2. Stand up the `nornyx-agentic-adapters` package; port the kernel to import
   only via `nornyx.agentic`; add framework extras + import-boundary test +
   matrix CI.
3. Ship the pip-only example; deprecate the in-repo `integrations/` copy.
