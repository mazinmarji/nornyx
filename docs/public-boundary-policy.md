# Public Boundary Policy

Nornyx is a public, product-neutral package.

Public repository content must not contain private downstream platform names,
private repository names, internal product names, customer names, credentials,
secrets, or organization-specific operational details.

This boundary applies to source code, source comments, tests, fixtures, examples,
generated outputs, documentation, release notes, issues, and pull request bodies.

Tests must use synthetic neutral markers instead of real private names. Synthetic
markers are allowed only when they test public-boundary behavior and must not be
copied into generated public artifacts.

If a downstream product needs to test its own private denylist, that denylist
must live outside the public Nornyx repository. Local-only term files used for
private checks must remain ignored and uncommitted.
