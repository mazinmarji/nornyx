# GOAL-054 Risk Note

This patch changes README/docs command wording only. It does not change CLI behavior, parser behavior, checker behavior, schema routing, runtime execution, package publication, deployment, live connectors, automatic approvals, or GOAL-100.

Residual risk is that users may expect the `nornyx` console script before activating an environment where it is installed. README now uses the module command form for first-use reliability.
