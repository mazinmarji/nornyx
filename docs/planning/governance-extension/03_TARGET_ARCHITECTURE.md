# 03 — Target Architecture

## Four-layer governance model

```text
Layer 4  Project contract (.nyx)          — actual files, roles, tools, evidence,
                                            thresholds, authorities, exceptions
Layer 3  Optional domain profiles (packs) — terminology, defaults, required
                                            controls, starter content, rules
Layer 2  Reusable governance modules      — change_control, human_approval,
         (separate data-only schema)         separation_of_duties, ...
Layer 1  Stable Nornyx core               — Intent, Agent, Policy, Eval,
                                            Approval, Evidence, Context,
                                            Artifact, Graph, Goal, Budget, Trace
                                            + parser + checker + generator +
                                            composition engine + rule evaluator
```

Dependency direction is strictly downward: 4 → 3 → 2 → 1. The core never
imports pack content at build time; packs never contain code. Modules may
depend on modules (acyclic); profiles depend on modules; projects select one
profile plus zero or more additional modules.

## Layer 1 — Stable core: no new core concepts

Evaluation of candidate core additions (per brief §3):

| Candidate | Verdict | Rationale |
|---|---|---|
| `Change` | **Module** (ADR-0021, doc 07) | Cross-domain, yes — but expressible as a named block whose semantics come from `change_control`; governed packages already prove a change block can live in a profile. Core addition would force a schema rev of 0.1/0.2/1.0 and re-check of every existing contract for zero near-term benefit. Rejection criterion met: "do not add a core concept merely because one profile needs it." |
| `Exception` | **Module** (`exception_management`) | Exceptions are only meaningful relative to a rule/control — they belong beside the rules engine, not in the concept dozen. Composition engine understands a *generic* exceptions block shape (doc 06 §6) without making Exception a core concept. |
| `Risk` | **Attribute, not concept** | risk_tier already appears as a field (governed packages). A Risk noun invites a risk-management product. Rejected. |
| `Control` | **Rejected** | "Control" is what Policy + Approval + Evidence already jointly express. A separate concept would create two vocabularies for the same thing. |
| `Architecture` | **Profile** (doc 08) | Domain-specific; fails the universality test. |

**Conclusion: zero core-concept additions.** The 12 concepts stand. What the
core *does* gain is engine capability: pack loading, composition, rule
evaluation — mechanisms, not vocabulary.

## Layer 2 — Reusable governance modules

Modules use `nornyx.governance_module.v1`, separate from the profile-pack
schema. They are declarative and composable; they carry required-block names,
default policies, required evidence types, approval requirements, structured
rules, and non-goals. No code. Extension block-schema fragments are deferred
until the Change Governance PR demonstrates the exact safe contract needed.

MVP module set (deliberately small — see audit finding F-07):

| Module | Provides |
|---|---|
| `change_control` | `changes:` block schema + lifecycle/impact/approval rules (doc 07) |
| `human_approval` | approval-gate shapes, denied-approver-type rules (`ai_tool`, `execution_surface`), no-auto-approval invariants |
| `separation_of_duties` | author≠approver rules, role-disjointness constraints |
| `evidence_integrity` | evidence hash/revision-binding requirements, staleness rules |
| `exception_management` | governed exception shape: authority, reason, scope, compensating controls, expiry |

Deferred to post-MVP (defined in packs when a profile actually needs them):
`supply_chain` (should reconcile with the scanner branch's evidence records
first), `architecture_conformance` (with doc 08), `data_protection`,
`lifecycle_management`, `release_control`, `incident_response`.

## Layer 3 — Optional domain profiles

A profile pack assembles modules and adds: domain terminology, defaults,
required controls, graph node kinds and relationship constraints, evidence
expectations, starter fragments, and profile-scoped rules. Existing 11 names
migrate as-is (doc 11). New examples enabled by the system:
`architecture_governance` (doc 08) is the first proof-of-concept profile that
ships *after* the engine exists.

## Layer 4 — Project contracts

`.nyx` files stay authoritative. They select a profile (`project.profile` — the
existing field), optionally add modules (`project.modules: [...]` — new,
optional, additive), and bind concrete reality: paths, roles, tools, evidence
artifacts, thresholds, approval authorities, risk classifications, exceptions.
Contracts may tighten anything; relaxation requires a governed exception
(doc 06 §6).

## Component diagram

```text
                  ┌────────────────────────────────────────────────┐
                  │                nornyx CLI                      │
                  │ init / check / generate / profiles {list,      │
                  │ inspect, validate, resolve, compatibility}     │
                  └───────┬──────────────────────────┬─────────────┘
                          │                          │
             ┌────────────▼───────────┐   ┌──────────▼──────────┐
             │  Profile Registry      │   │  Parser (.nyx)      │
             │  (identity, precedence,│   │  + policy ref       │
             │   lock verification)   │   │    resolution       │
             └────────────┬───────────┘   └──────────┬──────────┘
                          │                          │
             ┌────────────▼───────────┐              │
             │  Pack Loader           │              │
             │  (safe YAML, size caps,│              │
             │   schema validation,   │              │
             │   canonical paths)     │              │
             └────────────┬───────────┘              │
                          │                          │
             ┌────────────▼───────────┐              │
             │  Dependency +          │              │
             │  Compatibility Resolver│              │
             └────────────┬───────────┘              │
                          │                          │
             ┌────────────▼──────────────────────────▼──────────┐
             │  Composition Engine                              │
             │  (deterministic merge, monotonic safety,         │
             │   provenance recording per merged element)       │
             └────────────┬─────────────────────────────────────┘
                          │  effective governance model
        ┌─────────────────┼──────────────────────┐
        │                 │                      │
┌───────▼───────┐ ┌───────▼────────┐  ┌──────────▼─────────┐
│ Checker       │ │ Rule Evaluator │  │ Starter Renderer / │
│ (core rules,  │ │ (constrained   │  │ Generator          │
│  unchanged)   │ │  declarative)  │  │ (fragment assembly)│
└───────┬───────┘ └───────┬────────┘  └──────────┬─────────┘
        └────────┬────────┘                      │
        ┌────────▼────────┐            ┌─────────▼──────────┐
        │ Diagnostic      │            │ Provenance +       │
        │ Formatter       │            │ Drift artifacts    │
        └─────────────────┘            └────────────────────┘
```

## Loading sequence

1. CLI resolves requested profile identity (name or explicit path).
2. Registry walks discovery precedence (doc 05 §6): explicit path →
   `.nornyx/profiles/` → org dir → built-ins. First identity match wins;
   same-identity at multiple tiers is reported (provenance), different content
   under the same identity at one tier is a **fatal conflict**.
3. Loader safe-parses the pack (size/depth caps), validates against
   `nornyx.profile_pack.v1` schema, verifies integrity hash if a lock exists.
4. Dependency resolver loads required modules transitively (cycle ⇒ fatal),
   producing a deterministic topological order (ties broken lexicographically
   by pack id).
5. Compatibility analyzer checks core-range and declared conflicts (fail-closed).

## Validation sequence (`nornyx check`)

1. Parse `.nyx` (existing).
2. If the contract declares a profile/modules and packs are resolvable:
   compose effective model (doc 06); else fall back to today's behavior
   (backward compatible — a bare contract with no packs checks exactly as now).
3. Run existing hard-coded core checks (unchanged, never relaxable by packs).
4. Run composed structured rules through the rule evaluator.
5. Emit unified diagnostics with stable codes and per-rule provenance
   ("rule ARCH-001 from pack org.acme.arch_governance@1.2.0").

## Generation sequence (`nornyx init`, `nornyx generate`)

1. Compose effective model as above.
2. Starter renderer assembles fragments in deterministic layer order
   (core skeleton → module fragments → profile fragments), then applies
   project parameters (name). Pure data substitution — no template logic
   (doc 05 §5.4).
3. Output passes `nornyx check` by construction (tested invariant, today's
   behavior preserved).

Cross-references: pack format → doc 05; merge semantics → doc 06; security →
doc 10; migration → doc 11; phases → doc 12.
