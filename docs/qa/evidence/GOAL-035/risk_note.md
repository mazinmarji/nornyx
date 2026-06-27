# GOAL-035 Risk Note

Risk is medium-low. The change adds optional profile metadata, generated
starter-document defaults, docs, schema, and tests. It does not add runtime
execution, live connectors, LLM/model calls, automatic approvals,
self-modification, production deployment, or arbitrary command execution.

Primary residual risk: profile packs could be misunderstood as mandatory core
language concepts. This is mitigated by explicit `optional_profile` metadata,
the v0.3 docs, tests that keep profile-only domain terms out of the core concept
set, and PMO wording that reserves stricter profile conformance for v0.6.

Approval is required before treating profile semantics as stable or promoting
any profile into release-candidate scope.
