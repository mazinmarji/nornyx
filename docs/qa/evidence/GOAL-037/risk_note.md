# GOAL-037 Risk Note

Risk is medium-low. The change strengthens diagnostics but keeps graph behavior
static.

Mitigations:

- relation checks are source/target validation only;
- duplicate and self-edge diagnostics are warnings;
- contract auditability gaps are warnings;
- graph validation does not execute edges or infer runtime actions;
- connector-plan remains disabled by default and approval-gated;
- docs state that graph execution, live connectors, automatic approvals,
  self-modification, and production deployment remain out of scope.

Approval is required before semantic consistency rules become release gates.
