# Nornyx Requirement Triage Matrix

## Purpose

This matrix classifies all currently identified Nornyx concepts so development can proceed without endless scope expansion.

The goal is:

```text
freeze the core,
keep useful advanced concepts,
avoid bloat,
and guide future implementation.
```

## Classification categories

| Category | Meaning | Action |
|---|---|---|
| `core_now` | Required for v0.1 to work | Implement/harden soon |
| `near_core_candidate` | Important and likely future core, but waits for parser/checker maturity | Docs/schema/local validator only |
| `extension_backlog` | Useful future extension | Roadmap/backlog |
| `profile_specific` | Useful in one domain/profile | Add later as profile |
| `outside_nornyx` | Nornyx may integrate/contract with it, but should not implement it | Do not implement |
| `rejected` | Adds complexity without enough value | Do not add |

---

# 1. Core now

These should remain the v0.1/v0.2 foundation.

| Concept | Reason |
|---|---|
| `project` | Root language/project boundary |
| `goal` | Main unit of governed work |
| `intent` | Explicit purpose for humans and LLMs |
| `context` | Controls what the model/agent may use |
| `agent` | First-class actor/role |
| `policy` | Safety, permissions, constraints |
| `harness` | Workflow/check/repair discipline |
| `eval` | Behavior and quality measurement |
| `evidence` | Proof of work and outcome |
| `approval` | Human authority gate |
| `trace` | Audit and observability |
| `budget` | Token/tool/runtime control |
| `delivery_state` | Status, pending, completed, risk, next action |

## Core priority

```text
GOAL-001 — freeze block semantics
GOAL-002 — harden parser/checker
GOAL-003 — harden generator
```

---

# 2. Near-core candidates

These are important, but should not disrupt v0.1 core freeze.

| Concept | Reason | Recommended handling |
|---|---|---|
| `handover` | Controls transitions between product, dev, release, ops | Candidate after GOAL-001/GOAL-002 |
| `assumption` | Prevents silent LLM invention | Local validator/docs now |
| `open_question` | Captures unresolved unknowns | Local validator/docs now |
| `decision_needed` | Owner-bound unresolved decision | Local validator/docs now |
| `decision_boundary` | Separates AI suggestion from human decision | Regulated candidate |
| `evidence_quality` | Ensures evidence is audit-grade, not merely present | Regulated candidate |
| `authority_order` | Prevents context/source conflict | Should be part of context hardening |
| `provenance` | Tracks source of context/evidence | Near-core for safe context |

---

# 3. Extension backlog

These are useful but should not be immediate core.

| Concept | Reason | Extension |
|---|---|---|
| `intake` | Product discovery input | Product lifecycle extension |
| `persona` | User role model | Product lifecycle extension |
| `journey` | User workflow / UX path | Product lifecycle extension |
| `prototype` | Mockup/wireframe handover | Product lifecycle extension |
| `operations` | Runbook, monitoring, rollback contracts | Operations extension |
| `product_eval` | Business/user outcome validation | Product lifecycle extension |
| `lifecycle_state` | Idea → ops → improvement stage | Product lifecycle extension |
| `data_source` | Data origin declaration | Data/regulated extension |
| `data_provenance` | Trust/freshness lineage | Data/regulated extension |
| `uncertainty_policy` | Missing/stale/conflicting data handling | Data/regulated extension |
| `tenant_boundary` | Multi-tenant data isolation | Security/enterprise extension |
| `incident_response` | Incidents, severity, containment | Operations extension |
| `operations_eval` | Runtime service health evaluation | Operations extension |
| `compliance_eval` | Compliance-specific validation | Regulated extension |
| `data_quality_eval` | Data-specific validation | Data extension |
| `customer_safe_view` | Role-filtered external status | Portal/role-view extension |
| `safe_mode` | Operational degraded behavior | Operations extension |
| `audit_export` | Audit/report export contract | Regulated extension |

---

# 4. Profile-specific concepts

These should be delivered later as profiles, not core.

| Profile | Concepts |
|---|---|
| `ai_coding` | AGENTS.md, skills, coding harness, PR evidence |
| `regulated` | decision boundaries, evidence quality, compliance eval |
| `legacy_upgrade` | repo audit, migration, compatibility checks |
| `telecom_ops` | NOC workflows, incident triage, network change approval |
| `cold_chain` | telemetry, compliance, shipment risk, evidence export |
| `civic_services` | citizen issues, work orders, public status |
| `enterprise_portal` | role views, dashboard contracts, reporting |
| `agentic_network` | static agent identities, capabilities, memberships, trust zones, gates, contract-only protocol targets, revocation |

---

# 5. Outside Nornyx

Agent authentication and identity issuance, service discovery, runtime
presence, agent orchestration, live MCP/A2A transport, endpoint and credential
management, framework execution, production consoles, and automatic approval
remain external systems. Nornyx may validate bounded static contracts and
evidence about them; untrusted context cannot define policy or permissions.

Nornyx may define contracts for these, but should not implement them.

| Outside system | Nornyx boundary |
|---|---|
| Full product-management suite | Define intake/handover contracts only |
| Design/prototyping tool | Reference mockups/prototype artifacts only |
| Ticketing system | Generate handoff/ticket payloads later |
| Monitoring platform | Define SLO/monitoring contract only |
| BI dashboard | Export state/evidence data only |
| Identity provider | Reference roles/owners only |
| Audit database | Define evidence requirements only |
| IoT stream processor | Define data-source/provenance contract only |
| Compliance management system | Define compliance evidence contract only |
| Customer support platform | Define support handoff only |
| Production operations console | Define runbook/incident contract only |

---

# 6. Rejected for now

| Idea | Reason |
|---|---|
| Full Nornyx portal engine | Overloads the language |
| Autonomous production self-healing | Too risky before policy/runtime maturity |
| Live MCP/A2A connector execution by default | Requires security/capability maturity |
| Automatic GitHub writes | Must remain human-gated |
| Full general-purpose programming replacement | Wrong near-term target |
| Tool-specific command language | Nornyx must be vendor-neutral |
| Prompt trick catalog | Pattern lifecycle should filter and validate |
| Unlimited examples | Examples help but create maintenance burden |

---

# 7. Requirement funnel

Every new concept must pass this funnel:

```text
1. Does it prevent LLM misuse?
2. Does it improve core language correctness?
3. Does it reduce duplicated repo artifacts?
4. Does it improve evidence, safety, or handover?
5. Can it be checked or generated?
6. Is it broadly useful, or profile-specific?
7. Does it belong outside Nornyx?
```

## Action rule

```text
If core_now: implement/harden.
If near_core_candidate: docs/schema/local validator only.
If extension_backlog: roadmap/backlog.
If profile_specific: wait for profile.
If outside_nornyx: define boundary only.
If rejected: do not add.
```

---

# 8. Immediate development recommendation

Stop broad gap discovery now.

Proceed with:

```text
GOAL-001 — Core block spec freeze
GOAL-002 — Parser/checker hardening
GOAL-003 — Artifact generator hardening
```

The matrix can be revisited after each goal, but should not keep expanding the repo without implementation value.
