# 04 — Governance Metamodel

Status: implemented normative metamodel.

## Entities and relationships

```text
PackSource (builtin | project | org | explicit_path)
  └─ contains → ProfilePack | GovernanceModule (separate schemas)
       ├─ declares → RequiredBlock names (bound to packaged block schemas)
       ├─ declares → Defaults (policies, evidence, approvals, budgets)
       ├─ declares → Rules (constrained declarative, doc 05 §5)
       ├─ declares → StarterFragments (inert data)
       ├─ declares → GraphVocabulary (node kinds, relation constraints)
       ├─ requires → Module packs (acyclic)
       └─ declares → Compatibility (compatible_core, conflicts, review-with)

EffectiveModel = compose(core, modules*, profile, org_policy?, contract, exceptions*)
  ├─ every element carries Provenance {pack_id, version, layer, source_tier}
  └─ evaluated by → Checker (core, fixed) + RuleEvaluator (composed rules)

Exception (governed relaxation)
  ├─ targets → one rule/control id
  ├─ requires → authority (role), reason, scope, compensating_controls, expires
  └─ recorded in → contract only (packs cannot grant exceptions to themselves)
```

## Meaning of each layer's contribution

| Layer | May add | May tighten | May relax |
|---|---|---|---|
| Core | everything baseline | — | never |
| Module | blocks, rules, required evidence/approvals, denials | yes | **no** |
| Profile | same as module + terminology, defaults, starters | yes | **no** |
| Org policy | rules, denials, required controls | yes | **no** |
| Project contract | concrete bindings, extra controls | yes | only via governed exception |
| Exception | — | — | one target, with authority + expiry |

This is the monotonic-safety table; doc 06 defines the merge mechanics and
doc 10 threat-models attempts to violate it.

## Identity model

- Pack id: reverse-DNS-ish stable string, e.g. `nornyx.builtin.ai_coding`,
  `org.acme.module.change_control`. Built-ins own the `nornyx.builtin.*`
  namespace; the loader **rejects** non-builtin sources claiming it.
- Short name (`ai_coding`) is a registry alias resolved through precedence;
  collisions across tiers are resolved by precedence and *reported*; collisions
  within a tier are fatal.
- Rule ids are namespaced by pack id at composition time
  (`nornyx.builtin.ai_coding/AICODE-001`); packs reference their own rules by
  local id.

## Versioning model

- Pack `version`: SemVer. Breaking pack changes (removed rule, changed block
  schema) require major bump; the composition engine warns when a lock recorded
  a different major.
- Profile `schema`: the format discriminator (`nornyx.profile_pack.v1`);
  modules use `nornyx.governance_module.v1`.
  Format evolution is additive within v1; v2 requires a new schema file, never
  reinterpretation of v1 fields (doc 11 §5 covers v0.3 → v1).
- `compatible_core`: declared compatibility with the Nornyx language/core surface
  (e.g. `">=0.2 <=1.0"`), checked at load, fail-closed if unsatisfied.

## What is deliberately NOT in the metamodel

- No pack-defined operators, functions, or expressions (rule language is a
  closed vocabulary — ADR-0023).
- No pack-to-pack patching (a pack cannot modify another pack's rules, only
  add its own; conflicts surface as diagnostics, not silent overrides).
- No implicit inheritance chains (a profile lists its modules explicitly;
  no "extends: other_profile" in v1 — rejected to prevent diamond-merge
  ambiguity; revisit only with evidence of need).
- No runtime hooks of any kind.
