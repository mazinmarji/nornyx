# 02 — Problem Statement and Scope

Status: accepted scope, implemented by the governance-extension program. The
problem description below records the pre-implementation repository state.

## Problem

At the program baseline, every new governance domain required Python changes in at least four
places: `profiles.py` (names, pack dict, stability, compatibility matrix,
starter template branches), `checker.py` (any new validation), `cli.py`
(choices/help), and tests. Profile "packs" exist as YAML but are dead data.
Pack `validation_rules` are prose and enforce nothing. The v0.3 pack schema is
const-pinned and cannot version forward.

Consequences:
- Adding a domain profile is a core-maintainer activity, not a governance
  author activity.
- Organizations cannot ship approved profiles to their projects without forking.
- Validation intent (the prose rules) silently diverges from validation
  behavior (checker code).
- The YAML/Python mirror pair is a standing drift hazard held together by one test.

## Goal

New governance requirements should be expressible primarily as **data**:
reusable governance modules, optional domain profiles, and project contracts —
loaded, validated, composed, and evaluated by a stable core engine. Python
changes should be needed only when the *engine* itself needs a new capability
(new rule operator, new merge behavior), which is deliberately rare and
deliberately reviewed.

## In scope

1. Declarative pack format (profiles + modules) with schema, integrity hash,
   provenance, and compatibility metadata (doc 05).
2. Loader, registry, precedence, and trust model — local-only (doc 05 §6, doc 10).
3. Deterministic composition semantics with monotonic safety (doc 06).
4. Constrained declarative validation-rule language (doc 05 §5, ADR-0023).
5. Migration of the 11 established profiles to authoritative packs, plus the
   additive architecture profile (doc 11).
6. Generalized change governance as a reusable module reconciled with
   `governed_package.changes` (doc 07).
7. Architecture governance as an optional profile over external-tool evidence
   (doc 08).
8. Governance Surface Analysis method (doc 09).
9. Threat model and security requirements (doc 10).
10. Phased roadmap, test plan, audit (docs 12–14).

## Out of scope (explicit non-goals)

- Any execution of pack-supplied code (no plugins, no entry-point code, no
  templates with logic).
- Network fetching of packs (no registry client, no remote refs) — not even
  behind a flag in the initial design.
- A general-purpose policy language (no arbitrary expressions, no user-defined
  functions, no Turing-complete rule constructs).
- Replacing specialist analyzers (ArchUnit, import-linter, dependency-cruiser,
  Semgrep, CodeQL, SonarQube) — Nornyx declares/verifies evidence, tools produce it.
- Runtime enforcement — Nornyx stays a contract/checker/generator/governance
  layer; nothing here creates an execution engine.
- Multi-profile free composition (ADR-0022 limits the completed program to one
  primary profile plus modules; overlays are `rejected_with_ADR`).
- Changing `.nyx` core language semantics or schema versions.

## Non-negotiable invariants preserved (checklist used by the audit, doc 14)

`.nyx` authoritative; deterministic generation; drift detection; explicit
evidence/approval semantics; human authority over high-impact actions; no
automatic approval; no unrestricted execution; no arbitrary command execution;
no production deployment; no credential/secret loading; no live connectors; no
model invocation by the profile system; no self-modification; no
profile-supplied Python; no remote download by default; backward compatibility
for existing `.nyx` files, built-in profile names, `nornyx init`/`nornyx
profiles`; fail-closed handling of invalid/conflicting/untrusted packs; a
profile or module must never weaken core safety policy.

## Success criteria

- A new domain profile can be added by writing one pack file + fixtures; zero
  Python edits; `nornyx profiles validate` passes it; `nornyx init --profile-path`
  scaffolds from it.
- All 11 established profiles load from packs with byte-identical or
  explicitly approved starter output; the additive architecture profile has a
  reviewed golden.
- Every prose validation rule in current packs either becomes a structured rule
  or is explicitly recorded as "descriptive, not enforceable" in the pack.
- Full existing test suite passes unmodified except where a change is an
  intentional, documented migration.
