# GOAL-051 Risk Note

This patch adds schema routing and versioned schema files, but keeps the historical compatibility path as the default. It does not change checker behavior, execute graphs, enable live connectors, call models, publish packages, deploy software, grant automatic approvals, or unlock GOAL-100.

Residual risk is compatibility confusion if future work removes the `compat` route too early. The next migration step should keep aliases and tests in place until consumers have moved to explicit schema versions.
