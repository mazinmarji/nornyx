# ADR-0046 — Graph Vocabulary Enforcement: the Checker Checks the Boundary the Docs Describe

- Status: Accepted (checker correctness; no language, schema, or runtime change)
- Date: 2026-09-17
- Decision owner: human repository owner
- Relates to: ADR-0040 (assurance tiers and claim boundaries); `docs/42_NORNYX_GRAPH_VALIDATION_v0_5.md`; `docs/50_NORNYX_GRAPH_DEMO.md`; `docs/63_NORNYX_GRAPH_DEMO_EXPANDED.md`; issue #104

## Context

The graph documentation describes `graph:` as a static control-plane contract whose nodes are governance concepts and whose edges are "semantic, audit, and control relationships". `docs/42_NORNYX_GRAPH_VALIDATION_v0_5.md` says custom relations "produce warnings so profile or adapter authors can document them explicitly", and the profile-pack schema (`schemas/profile_pack_v1.schema.json`, `$defs.graph`) *requires* every profile to declare `graph.node_kinds` and `graph.relationship_constraints`.

Issue #104 measured that none of this was checked. A contract carrying five world-model entities (`customer`, `service`, `network_element`, `alarm`, `change`) in a five-node cycle, related by `depends_on`, inside a governed `contracts:` entry, under `project.profile: telecom_ops`, passed `nornyx check --strict` with zero diagnostics. Four mechanisms in `nornyx/checker.py` allowed it:

1. `graph.nodes[].kind` was an open string; no core vocabulary existed.
2. `ref` was resolved for fourteen kinds only; `artifact`, `module`, `profile`, `project` and `contract` refs were free text.
3. `depends_on` was declared `({"*"}, {"*"})` — a recognised relation that matched every pair, so it never triggered `UNKNOWN_GRAPH_RELATION` or `INVALID_GRAPH_RELATION_PAIR`.
4. Profile `graph.node_kinds` and `graph.relationship_constraints` were read only by the legacy v0.3 projection; the checker's relation table was a module constant that never consulted the active profile. The `UNKNOWN_GRAPH_RELATION` hint therefore pointed authors at a mechanism with no effect.

Two further facts bound the fix. Cycle detection already exists in `governance/structural.py` for evidence dependencies and exception renewals but was never applied to `graph.edges`. And the shipped profile declarations are **not** closed vocabularies: `telecom_ops` declares `[profile, context, policy, approval, budget, goal]` while its own starter document uses `agent` and `evidence` nodes, and six built-in profiles declare `[]`. The only reading consistent with the shipped data is that a profile's list *adds* to the core kinds.

The checker is a pure function of the document (`check_document(doc)`); the active profile is composed afterwards by `nornyx check`. The `nornyx.agentic` loader, generation drift, repository drift and the LSP all call the checker without a composition and act only on error-level diagnostics.

## Decision

**The `graph:` block is validated against an explicit vocabulary, and a profile can only widen it.**

1. **Core vocabulary.** `CORE_GRAPH_NODE_KINDS` names the nineteen kinds the language already uses in `_graph_ref_targets` and `GRAPH_RELATION_RULES`: `adapter, agent, approval, artifact, budget, connector, context, contract, eval, evidence, goal, harness, intent, module, policy, profile, project, skill, trace`. No kind was added; the set was made explicit. A test (`test_core_vocabulary_is_self_consistent`) pins that every kind the relation rules mention is in it.

2. **Profile extension is additive.** `GraphVocabulary` = core kinds ∪ the active profile's `graph.node_kinds`; each `relationship_constraints` entry adds one allowed `from_kind → relation → to_kind` triple, declaring the relation if it is not a core one and widening the allowed pairs if it is (`architecture_governance` widens `governs` to reach `component`). A profile cannot remove a core kind or narrow a core relation. Profile-declared relations are pair-checked exactly like core ones.

3. **Threading.** `check_document(doc, *, graph_vocabulary=None)`. `nornyx check` and the agentic-network commands compose governance first and pass `graph_vocabulary_for_profile_pack(composition.profile)`, so project- and organisation-supplied packs extend the vocabulary exactly as built-ins do. When no vocabulary is supplied the checker resolves `project.profile` against the built-in registry (packaged data only, `lru_cache`d) and otherwise uses the core vocabulary. The explicit argument is authoritative.

4. **Diagnostics, warning-first.** Three new codes, all `warning` so an existing contract keeps its exit status and `--strict` promotes them:
   - `UNKNOWN_GRAPH_NODE_KIND` — a kind outside the vocabulary. Edges touching such a node skip pair validation: the node diagnostic covers them and no new hard error is introduced.
   - `GRAPH_NODE_WITHOUT_REF` — a kind with no in-document resolution target (`artifact`, `module`, any profile-declared kind) carries no `ref`. Mirrors the existing `GRAPH_EVIDENCE_NODE_WITHOUT_REF`.
   - `GRAPH_CYCLE` — the edge set forms a cycle. Inverse spellings (`governed_by`, `gated_by`, `bounded_by`, `validated_by`, `uses_context`) are folded onto their canonical direction first, so a relationship declared from both ends is not a two-node cycle; self-edges keep their own diagnostic. Reported once per strongly connected component, members sorted.

   Two existing codes keep their existing severity and gain coverage: `UNKNOWN_GRAPH_REF_REFERENCE` (error) now also resolves `profile` (against `project.profile` / `project.profile_pack.name`), `project` (against `project.name`) and `contract` (against `contracts[].name`) — the same condition class the code already reports for fourteen kinds; and `INVALID_GRAPH_RELATION_PAIR` (error) now applies profile constraints. `UNKNOWN_GRAPH_RELATION` no longer fires for a relation the active profile declares, which makes its hint true.

5. **`depends_on` is closed by the vocabulary, not by a special rule.** Its `({"*"}, {"*"})` rule stands, but `*` now ranges over known kinds only, because pair validation runs only when both endpoints are known. Nothing shipped uses `depends_on`.

6. **What is out of scope, deliberately.** Path existence for `artifact` / `module` refs is not checked: the shipped expanded demo's refs are repository-relative while the checker has no root, and any choice of root would produce false positives. Presence is checked; existence belongs to a root-aware layer if it is ever wanted. No graph kind for any domain entity is added to core (see issue #104: "do not turn discovery of a boundary defect into product expansion").

## Consequences

- The specimen in `tests/fixtures/graph_boundary/issue_104_probe.nyx` now yields five `UNKNOWN_GRAPH_NODE_KIND` warnings and one `GRAPH_CYCLE`, exits 0 plain and 1 under `--strict`. `tests/test_graph_boundary.py` pins that, the additive profile semantics, the widened-not-narrowed rule, inverse-pair folding, ref resolution, and that both shipped graph demos and every generated domain-profile document gain **no** diagnostic of any level.
- Existing valid contracts are unaffected: no shipped `.nyx` uses a non-core kind, an artifact or module node without a ref, `depends_on`, or a cycle. Third-party contracts that do will see warnings, and will fail only under `--strict`, which is the documented promotion path.
- The `nornyx.agentic` loader, drift tools and LSP are unchanged in behaviour (they act on errors only); the LSP will surface the new warnings, which is desirable.
- The language surface (`nornyx_v0_2` / `nornyx_v1_0` schemas) is untouched; `graphNode.kind` remains a string in the schema. This is a checker change under package versioning, not a language change.
- Follow-on, not decided here: promoting `UNKNOWN_GRAPH_NODE_KIND` to an error in a later minor release once one released version has carried the warning.

## Alternatives considered

- **Treat a profile's `node_kinds` as a closed vocabulary.** Rejected: it would fail the profiles' own starter documents and every profile that declares `[]`. The shipped data settles the semantics as additive.
- **Make the new conditions errors immediately.** Rejected: contracts that pass today would start failing in a patch release; `--strict` already exists as the promotion path and is what CI reaches for.
- **Enforce only in the governance layer, where the profile is known.** Rejected: profile-less documents would remain unchecked, and the original probe had no profile.
- **Check `artifact` / `module` ref paths on disk.** Rejected for this change: no unambiguous root exists in the pure checker, and the shipped demo would false-positive.
- **Narrow `depends_on` with a bespoke kind list.** Rejected: the wildcard is only dangerous over unknown kinds, and closing the kind vocabulary closes it without inventing a second rule.
