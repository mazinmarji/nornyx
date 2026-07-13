# Appendix - Structured Rule and Collection Semantics (F-02)

Status: normative PR 1 specification. No runtime evaluator is implemented.

## Closed language

The only v1 predicate operators are:

```text
exists not_exists equals not_equals in not_in contains contains_all
min_count max_count references_role references_evidence
references_approval matches_id
```

Exactly one operator is permitted per predicate. `matches_id` accepts only
literal identifier characters plus `*` and `?`; it is not a regular expression.
Unknown operators, unknown fields, malformed paths, nested condition groups,
and structurally invalid rules are schema errors. A future loader must stop
before composition; warnings or skipped rules are forbidden.

There are no expressions, scripts, regular expressions, templates, calls,
variables, arithmetic, interpolation, imports, or executable profile code.

## Path grammar

A path has one to eight dotted identifier segments. Any segment may end in
`[]` to traverse a list. Numeric indexes, filters, roots, parent traversal,
wildcards in paths, and function syntax are invalid. Examples:

```text
changes[].risk_tier
systems[].components[].owner
approvals[].eligible_roles
```

Resolution records concrete paths such as `changes[2].risk_tier`. Duplicate
concrete paths are de-duplicated in first-seen traversal order so one source
value produces at most one diagnostic per predicate.

## Quantification and selection

- A `when` predicate containing `[]` is existential: it matches when at least
  one applicable element matches.
- A `require` predicate containing `[]` is universal: every applicable element
  must satisfy it. Failures identify each concrete element.
- Conditions sharing the same collection prefix are evaluated per element.
  Matching `when` elements become that rule's selection for requirements with
  the same prefix. This makes "every selected high-risk change" precise.
- Predicates with different collection prefixes quantify independently. There
  is no implicit join between `changes[]` and `approvals[]`. Relational joins
  require a future, separately approved design or a fixed core check.
- Nested collections flatten to concrete index tuples in document order.
  Universal requirements cover every applicable leaf.
- Selection is inherited by nesting: when a `when` selection exists for a
  collection prefix, a `require` path that traverses that prefix — including
  paths that descend into deeper collections beneath it (for example
  `changes[].evidence[].kind` under a `changes[].risk` selection) — binds only
  to leaves whose binding starts with a selected element. Requirement paths
  that never traverse the selected prefix remain independent.
- Shared ancestors join under `all`: predicates whose paths traverse the same
  ancestor collection at any depth (for example `changes[].risk` and
  `changes[].evidence[].kind` both traverse `changes[]`) must be satisfied by
  the same ancestor element. Successful bindings are projected onto every
  traversed collection level and intersected per level; if no single ancestor
  element satisfies all traversing predicates, the condition does not match.
- Structural type errors while evaluating a `when` predicate (a scalar
  operator receiving a collection, a collection operator receiving a scalar,
  a malformed reference target) fail closed as diagnostics at the rule's
  severity. Ordinary missing-path and non-match outcomes remain silent
  non-matches.

For `all`, one collection element is selected only if all same-prefix
predicates match that element. For `any`, an element is selected if any
same-prefix predicate matches it. Conditions over unrelated prefixes remain
independent existential clauses.

## Missing, empty, null, and wrong types

- Empty collection in `when`: no match.
- Empty collection in `require`: fail closed. Authors may test an intentionally
  empty list with `max_count: 0` on the list's scalar path.
- Missing path: `exists` does not match and `not_exists` matches. Other
  operators do not match in `when` and fail in `require`.
- Null: the path exists. `exists` passes and `equals: null` passes. Operators
  requiring a string or collection report a structural type error.
- A `[]` segment resolving to a scalar is a structural evaluation error.
- A scalar operator (`equals`, `in`, `matches_id`) receiving a collection is a
  structural evaluation error.
- A collection operator (`contains`, `contains_all`, `min_count`, `max_count`)
  receiving a scalar is a structural evaluation error.
- Structural evaluation errors fail the rule closed and emit stable diagnostics;
  they are never converted to a non-match that could hide invalid governance.

## Test contract

`rule_semantics_cases.json` enumerates all cases above, including nested lists,
duplicates, invalid syntax, unknown operators, scalar/list mismatches, and
same-prefix selection. Schema tests prove invalid operators and paths are
rejected. These are specification tests, not claims that `nornyx check`
evaluates v1 rules today.

## F-02 closure

Resolution: closed for PR 1. Quantification, binding, edge cases, diagnostics,
and fail-closed load behavior are explicit and fixture-backed.
