# Appendix - Governed-Package Scanner Integration Decision

Status: implemented sequencing decision and preserved historical rationale.

## Original decision

The governance specification was initially developed beside the unmerged
governed-package scanner-hardening branch. The decision required scanner
hardening to merge before shared Change Governance could reconcile evidence,
approval aliases, and the governed-package change shape. It also prohibited
the specification-only work from modifying scanner code or delegating existing
validation prematurely.

## Implemented outcome

The scanner hardening merged first. The completed `change_control` stage then
re-audited and reconciled the settled governed-package schema, scanner evidence,
approval aliases, task/change references, and examples. Governed packages now
delegate compatible change validation to the shared `nornyx.change.v1` model
without weakening the historical `id`/`type` minimum.

Architecture evidence import follows the same bounded, local report-import
boundary: Nornyx validates supplied evidence and does not execute scanners or
specialist tools. Regression coverage lives in the governed-package, change
governance, architecture evidence, compatibility, and security suites.

## Closure

The sequencing dependency is `implemented`; it is not an open branch or future
integration requirement. Re-entry requires an incompatible scanner evidence or
change-schema revision and a new compatibility review.
