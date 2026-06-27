# GOAL-039 Risk Note

Risk is medium. Adapter and connector-contract conformance is close to external
systems, credentials, network egress, and runtime behavior.

Mitigations:

- conformance reports are static evidence artifacts;
- safety flags require connectors and adapters to remain disabled;
- unsafe adapter execution modes are blocked;
- live connector execution is blocked;
- endpoint/command connector metadata remains blocked by connector-plan;
- adapter contracts must reference declared connectors, policies, evals, and
  evidence;
- connector conformance must require approval and safe default modes;
- schemas encode non-execution and no-live-target assumptions.

Approval is mandatory before any connector or adapter behavior moves beyond
contract validation.
