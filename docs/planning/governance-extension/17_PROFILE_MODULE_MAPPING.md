# 17 - Profile Module Mapping

Status: implemented mapping for all 13 built-in profiles.

## Decision Rule

The 11 established profiles retain `required_modules: []`. Adding a module to
those packs would activate new required blocks, evidence files, approvals, and
fixed checks for existing contracts, violating the compatibility corpus. Their
GSA result is therefore an explicit project-level recommendation through
`project.modules`, not a silent profile migration. The new
`architecture_governance` profile was designed with governed blocks from its
first version and requires `architecture_conformance`.
The additive v1-only `agentic_network` profile likewise requires only the thin
`agentic_network_governance` module directly.

Selecting a module includes its dependency chain. In particular,
`change_control` includes evidence integrity, human approval, separation of
duties, and exception management; `architecture_conformance` includes that
entire chain plus architecture checks. `agentic_network_governance` includes
only the existing evidence-integrity and human-approval dependency chain.

## Mapping

| Profile | Required now | Recommended explicit selection | Reason and controls gained | Compatibility impact | Evidence and approval | Rejected alternative |
|---|---|---|---|---|---|---|
| `minimal` | none | none | Preserve the smallest starter and free-form profile behavior. | none | established starter evidence only | Requiring governance modules would contradict the profile's minimal purpose. |
| `standard` | none | `human_approval` for high-impact use | Adds hashed evidence and accountable human approval. | opt-in adds `governance_evidence` and `approvals`; no existing starter change | evidence manifest and approval record; reviewer authority | Automatic dependency would invalidate existing standard starters. |
| `ai_coding` | none | `change_control` | Governs repository changes, stale approval, rollback, exceptions, and independent review. | opt-in only | foundational records plus change record; reviewer/change authority | A profile-local change model would duplicate the shared schema. |
| `regulated` | none | `change_control`; `architecture_conformance` when architecture scope exists | Adds the full change chain and, where selected, declared architecture evidence. Supply chain remains external/package-owned by ADR-0031. | opt-in only; legacy starter bytes unchanged | full foundational/change evidence; architect evidence only when architecture module selected | Attaching every module would create unevidenced mandatory blocks and duplicate scanner controls. |
| `legacy_upgrade` | none | `change_control` | Makes migration scope, approval invalidation, rollback, and closure explicit. | opt-in only | change and foundational evidence; human reviewer | A new migration lifecycle would compete with shared change lifecycle. |
| `nornyx_language` | none | `architecture_conformance` for core changes | Adds change, architecture decision, dependency-direction, evidence, and human architecture controls. Supply-chain starter text remains advisory/package-owned. | opt-in only | full architecture chain; architect authority | Making it required would break the established language starter and legacy projection. |
| `agentic_repo_harness` | none | `change_control`; optionally `architecture_conformance` | Governs harness changes and, when needed, dependency boundaries without executing harnesses. | opt-in only | change evidence and human review; architecture report when selected | Embedding harness analysis in Nornyx violates the execution boundary. |
| `telecom_ops` | none | `change_control` | Governs high-impact operational contract changes while keeping live operations external. | opt-in only | change/foundational evidence; human change authority | Incident automation or a profile-local incident runtime is outside Nornyx. |
| `business_ops` | none | `change_control` | Governs process-contract changes, exceptions, evidence, and approval. | opt-in only | change/foundational evidence; human change authority | A generic workflow runtime or incident module is not justified. |
| `ai_governance` | none | `change_control` | Governs model/policy contract changes, independent evidence, exceptions, and stale approvals. | opt-in only | change/foundational evidence; accountable human authority | A second approval or model-lifecycle system would duplicate existing semantics. |
| `finance_ops` | none | `change_control` | Governs high-risk finance contract changes and separation of duties without operating financial systems. | opt-in only | full foundational/change evidence; disjoint human authority | Mandatory modules would alter an explicitly optional profile and imply operational enforcement. |
| `architecture_governance` | `architecture_conformance` | none beyond its dependency chain | Provides declared architecture, change controls, external conformance evidence, exceptions, and architect authority. | new profile; no legacy projection or existing contract changed | all foundational/change records plus architecture evidence; architect and reviewer roles | Peer-profile composition and architecture source inference are rejected. |
| `agentic_network` | `agentic_network_governance` | none beyond its dependency chain | Validates static identities, capabilities, memberships, trust zones, gates, protocol contracts, and revocations. | additive v1-only profile; no legacy projection or existing contract changed | network-contract review and approval record; human network-governance owner | A live agent runtime, transport, framework adapter, authentication system, or credential loader is rejected. |

## Evidence

Each adjacent `gsa/*.yaml` file answers the governance-completeness questions
for one profile. Tests require exact catalog coverage and validate the advisory
template shape. No matrix is loaded as executable pack data.
