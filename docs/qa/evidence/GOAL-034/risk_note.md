# Risk Note

Risk level: medium.

GOAL-034 introduces the first v0.2 graph/contract surface, so the main risk is
scope confusion. The implemented surface is static validation only:

- no graph runtime;
- no runtime execution;
- no domain profiles;
- no adapters;
- no live connectors;
- no LLM/model calls;
- no automatic approvals;
- no self-modification;
- no production deployment.

Future work should keep v0.3 profiles, v0.4 adapters, and v0.8 bounded
execution readiness separate from this static v0.2 contract model.

Follow-up cleanup note: the schema file remains at the historical
`schemas/nornyx_v0_1.schema.json` path for compatibility, but now declares
support for both `0.1` and `0.2`. Split versioned schema files remain future
cleanup work and should not block v0.3 profile planning.
