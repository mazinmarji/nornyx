# 05 - Profile and Governance-Module Specification

Status: PR 1 specification. Draft schemas and fixtures exist; no loader,
registry, composition engine, or rule evaluator is connected to Nornyx.

## 1. Versioned formats

Profiles and modules are both declarative governance inputs, but they use
separate discriminated schemas:

- `nornyx.profile_pack.v1` / `profile_pack_v1.schema.json` for one optional
  primary profile;
- `nornyx.governance_module.v1` / `governance_module_v1.schema.json` for
  reusable additive controls;
- frozen historical `nornyx.profile_pack.v0_3` /
  `domain_profile_pack.schema.json` for legacy API views only.

A complete v1 profile never claims v0.3 conformance. Modules are not profiles
with a flag, which prevents profile-only starter and compatibility fields from
leaking into reusable modules. "Pack" remains an architectural umbrella term,
not a shared format discriminator.

## 2. Profile pack v1

The profile schema requires:

```text
schema kind id name display_name version compatible_core status
purpose domain required_modules required_blocks recommended_blocks
default_policies required_evidence default_evaluations
approval_requirements graph starter_fragments validation_rules
compatibility conflicts migration_guidance non_goals provenance integrity
```

Identity is lowercase dot-separated `[a-z0-9_.]` with at least two segments.
Version is SemVer. `compatible_core` is a conjunction of simple version
comparisons such as `>=0.2 <=1.0`; OR, wildcards, functions, and expressions
are invalid. Unknown top-level fields fail schema validation.

Profiles may declare graph node kinds and relationship constraints, literal
starter data, structured rules, compatibility/conflict metadata, defaults,
and requirements. They cannot contain code, templates, loader hooks, URLs,
credentials, commands, or Python entry points.

## 3. Governance module v1

The module schema requires stable identity/version/core range, dependencies,
conflicts, required blocks, policies, evidence requirements, approval
requirements, evaluations, structured rules, non-goals, provenance, integrity,
and an explicit safety object.

Every valid module has these immutable safety values:

```yaml
safety:
  data_only: true
  local_only: true
  network_access: false
  executable_code: false
  command_execution: false
  credential_access: false
  can_grant_approval: false
  can_weaken_core_safety: false
```

Modules add requirements only. They cannot grant approvals, remove denials,
weaken core checks, create exceptions, or choose their own loading source.
Dependencies are ids, not paths. Cycles and conflicts are future load-time
errors. The module loader and composition engine are explicitly outside PR 1.

## 4. Legacy v0.3 relationship

The old schema remains byte-for-byte frozen. The explicit v1-to-v0.3
projection, exact projected fields, out-of-band loss report, failure cases,
public API behavior, and deprecation strategy are normative in
`appendix_LEGACY_PROJECTION.md`.

A future v0.3 import shim, if retained, must be explicit and provenance-marked.
It is not needed to prove the public v1-to-legacy compatibility view in PR 1
and must not silently reinterpret prose `validation_rules` as executable rules.

## 5. Structured rule language

The closed operator set is:

```text
exists not_exists equals not_equals in not_in contains contains_all
min_count max_count references_role references_evidence
references_approval matches_id
```

Exactly one operator is allowed per predicate. `all` or `any` may group one
flat level of predicates; nested groups are invalid. Paths permit at most eight
dotted segments with optional `[]` list traversal. There are no expressions,
regexes, scripts, calls, variables, arithmetic, imports, executable logic, or
pack-defined operators. `matches_id` is a bounded wildcard match over identifier
characters with `*` and `?`, not regex execution.

Unknown operators and invalid paths are schema errors. A future loader must
fail before composition. The complete collection quantification, missing/null/
type behavior, nested-list semantics, de-duplication, and binding rules are
normative in `appendix_RULE_COLLECTION_SEMANTICS.md`.

`references_role` reads only the normalized approval representation defined in
`appendix_APPROVAL_NORMALIZATION.md`. It never guesses roles from gate names,
actions, prose, or arbitrary fields.

Limits: at most 200 rules per profile or module, at most 2,000 composed rules,
and a future evaluator step budget proportional to concrete path resolutions.
Exceeding a limit fails with `PACK_LIMIT_EXCEEDED`. Any limit increase requires
an ADR and resource-abuse tests.

## 6. Starter fragments

Starter fragments are literal YAML-compatible values targeted at known
top-level blocks. They are not templates. The only future substitution is the
project name at a fixed, engine-owned set of locations; packs cannot declare
substitution points. PR 1 does not refactor `profile_document()` or starter
generation.

## 7. Future local discovery

Planned precedence is deterministic:

```text
1. explicit user-selected local path
2. project .nornyx/profiles or .nornyx/modules directory
3. configured organization directory
4. bundled files
```

No URL is valid. Network loading and Python entry-point discovery are deferred
non-goals. Explicit paths and source roots will be canonicalized; symlinked
pack files will be rejected. Same-tier identity ambiguity is fatal. Cross-tier
shadowing is reported with provenance.

An organization-tier pack requires a committed lock. A missing org lock is an
error, not a warning, and every resolve/check report must display the configured
org root and selected source tier. Project/builtin packs may initially warn
when no lock exists, subject to the future loader ADR.

## 8. Integrity and lock canonicalization

Pack content hash is defined exactly as:

1. parse with the Nornyx safe YAML loader;
2. require one mapping document;
3. remove the top-level `integrity` member;
4. serialize as JSON with sorted keys, `ensure_ascii=False`, UTF-8, and compact
   separators `(',', ':')`;
5. SHA-256 those bytes and prefix the lowercase digest with `sha256:`.

No textual YAML excision is allowed. Comments, YAML key order, and CRLF/LF do
not alter the canonical content hash; parsed values do.

`nornyx.profiles_lock.v1` contains only resolved id, version, source tier,
content hash, and path hint. Time fields are schema-invalid. Identical inputs
must produce byte-identical lock files. Hash, version, tier, or missing-pack
mismatch is fatal.

## 9. Loader hardening requirements for later PRs

Future loading must use `NornyxSafeLoader`, UTF-8, a 512 KiB file cap, YAML
alias/depth limits, canonical source-root checks, symlink rejection, a 200-rule
per-pack cap, a 2,000-rule composed cap, and stable fail-closed diagnostics.
It may not import network libraries, execute commands, import profile Python,
load credentials, or evaluate templates.

## 10. Draft-schema status

Root schemas and bundled `nornyx/schemas/` copies are exact. They are packaged
by the existing `schemas/*.json` package-data rule, but no runtime registry
routes to them. Fixtures distinguish schema validation and specification
contracts from current runtime behavior.
