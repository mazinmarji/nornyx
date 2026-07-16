# CODEX GOAL — Complete the Nornyx Governance Program

**Status:** Active implementation goal
**Repository:** `mazinmarji/nornyx`
**Target baseline:** Current `main` at task start
**Execution owner:** Codex
**Closure authority:** Human review after independent audit

Codex must read this file in full before beginning implementation.

This document is the authoritative execution goal for completing the currently accepted Nornyx governance-extension program. Repository code, schemas, tests, ADRs, and current `main` remain the source of truth when this goal conflicts with stale planning text.

---

## Role

Act as:

- Principal governance-platform architect
- Senior Python and schema engineer
- Secure software-supply-chain engineer
- Policy-language designer
- Backward-compatibility owner
- Independent adversarial architecture auditor
- Release-readiness reviewer

Use the current local `main` branch and repository content as the only source of truth.

Do not assume earlier summaries, roadmap numbering, implementation status, version numbers, or branch state are current. Verify them before making changes.

---

# Mission

Complete the entire currently accepted Nornyx governance-extension program.

The result must leave no unresolved governance roadmap item.

Every governance candidate must end in exactly one final status:

- `implemented`
- `implemented_as_external_evidence_integration`
- `rejected_with_ADR`
- `superseded`
- `not_required_after_GSA`
- `future_proposal_outside_current_program`

Do not leave items labeled merely:

- planned
- deferred
- candidate
- later
- TBD
- TODO
- future work

unless they are explicitly classified as outside the completed current program and have a documented re-entry condition.

The completion claim must mean:

> All governance capabilities approved for the current Nornyx governance program are implemented, integrated, tested, documented, independently audited, and release-ready. There is no remaining mandatory “next governance” item in the current roadmap.

This does not mean implementing every theoretically possible governance feature. It means closing the approved program without uncontrolled product expansion.

---

# Current-state verification

Before changing anything:

1. Run:
   - `git status --short`
   - `git branch --show-current`
   - `git rev-parse HEAD`
   - `git log --oneline -15`
2. Confirm the current package version.
3. Confirm the current `main` commit.
4. Read:
   - all files under `docs/planning/governance-extension/`
   - all governance ADRs
   - `docs/02_ARCHITECTURE.md`
   - `docs/03_ROADMAP_TO_v1_AND_BEYOND.md`
   - `docs/05_SECURITY_MODEL.md`
   - `docs/40_NORNYX_DOMAIN_PROFILES_v0_3.md`
   - current release notes and changelog
5. Inspect:
   - `nornyx/governance/`
   - `nornyx/profiles.py`
   - `nornyx/profiles_data/`
   - profile catalog
   - schemas
   - governed-package implementation
   - package scanner
   - drift and evidence behavior
   - CLI
   - public exports
   - existing tests and fixtures
6. Record what is:
   - implemented
   - partially implemented
   - advisory only
   - absent
   - stale in documentation
   - contradictory
7. Do not reimplement completed functionality.
8. Do not trust planning documents when current code proves they are stale.

Create a current-state closure matrix before implementation.

---

# Non-negotiable Nornyx invariants

Preserve:

- `.nyx` as the authoritative project governance contract.
- The existing twelve stable concepts:
  - Intent
  - Agent
  - Policy
  - Eval
  - Approval
  - Evidence
  - Context
  - Artifact
  - Graph
  - Goal
  - Budget
  - Trace
- No unnecessary new stable-core concepts.
- Data-only governance packs.
- Local-only loading by default.
- Deterministic loading, composition, rendering and locking.
- Monotonic governance composition.
- Human authority for high-impact actions.
- AI tools and execution surfaces can never approve.
- No arbitrary expressions.
- No arbitrary Python.
- No profile-supplied executable code.
- No network registry.
- No entry-point discovery.
- No credential or secret loading.
- No automatic approval.
- No production deployment.
- No autonomous remediation.
- No external-tool execution by Nornyx.
- No source-code-analysis engine inside Nornyx.
- Specialist tools produce evidence; Nornyx validates and governs that evidence.
- Existing contracts remain compatible unless a change is explicitly approved and migrated.
- Existing profile APIs remain compatible where documented as public.
- Fail closed on ambiguous, malformed, conflicting, stale, forged or untrusted governance input.

Any proposed violation requires an ADR and must block implementation until human review.

---

# Program architecture

Maintain the four-layer model:

```text
Layer 4 — Project .nyx contracts
Layer 3 — Optional domain profiles
Layer 2 — Reusable governance modules
Layer 1 — Stable Nornyx core and governance engine
```

Projects select:

- one primary profile;
- zero or more compatible modules.

Do not introduce:

- arbitrary multi-profile composition;
- profile inheritance;
- remote packs;
- executable plugins;
- general-purpose policy programming.

---

# Workstream 1 — Foundational governance modules

Implement authoritative built-in, data-only governance modules for:

1. `human_approval`
2. `evidence_integrity`
3. `separation_of_duties`
4. `exception_management`
5. `change_control`

Each module must include:

- stable identity;
- version;
- compatible core range;
- dependencies;
- conflicts;
- required blocks;
- required evidence;
- approval requirements;
- structured rules;
- non-goals;
- provenance;
- integrity hash;
- tests;
- documentation;
- examples.

## Human Approval

Govern:

- eligible human roles;
- required roles;
- approval authority;
- action requiring approval;
- evidence required before approval;
- exact revision binding;
- approval expiry where relevant;
- invalidation conditions;
- explicit denial of:
  - `ai_tool`
  - `execution_surface`
  - autonomous agent
  - model
  - connector
  - generated output as approver

Reuse the existing approval normalizer.

Do not create a second approval model.

## Evidence Integrity

Govern:

- evidence schema identity;
- producer;
- artifact location;
- content hash;
- subject revision;
- tool name and version;
- freshness;
- generation time;
- status;
- evidence dependencies;
- stale evidence;
- missing evidence;
- conflicting evidence;
- malformed evidence;
- evidence substitution.

Hash integrity proves content binding, not truth. Document this explicitly.

## Separation of Duties

Govern relational controls such as:

- author must not approve own high-risk change;
- evidence producer must not be the sole approver where independence is required;
- release requester and final release approver may be required to be disjoint;
- exception requester and exception approver may be required to be disjoint.

Implement these as stable structural checks where the closed rule language is insufficient.

Do not expand the rule language merely to encode relational checks.

## Exception Management

Define one governed-exception model including:

- exception id;
- rule or control being relaxed;
- reason;
- scope;
- requester;
- accountable owner;
- approving authority;
- compensating controls;
- evidence;
- start time;
- expiry;
- renewal policy;
- closure evidence;
- status.

Rules:

- core safety invariants are not exceptable;
- pack integrity and no-executable-code rules are not exceptable;
- exceptions cannot be supplied by untrusted packs to weaken their own controls;
- expired exceptions fail closed;
- missing expiry fails;
- missing authority fails;
- missing compensating controls fails for high-risk relaxation.

---

# Workstream 2 — Generalized Change Governance

Implement `change_control` as the reusable owner of the shared change model.

Do not introduce a second incompatible change definition.

Create or finalize the shared change schema using the existing governed-package minimum:

Required compatibility tier:

- `id`
- `type`

Additive fields may include:

- purpose;
- lifecycle status;
- included scope;
- excluded scope;
- affected assets;
- affected systems;
- affected components;
- expected artifacts;
- risk tier;
- blast radius;
- reversibility;
- rollback requirement;
- rollback plan artifact;
- security impact;
- architecture impact;
- data impact;
- dependency impact;
- operational impact;
- required controls;
- required evaluations;
- required evidence;
- approver roles;
- separation of duties;
- revision binding;
- approval invalidation conditions;
- exceptions;
- closure evidence.

Implement change lifecycle validation:

```text
draft
→ proposed
→ approved
→ in_progress
→ completed
→ closed
```

Also support:

```text
rejected
rolled_back
cancelled
```

Define valid transitions as static declarations and evidence requirements. Nornyx does not watch systems continuously; CI or another caller reruns checks.

Implement stable diagnostics for:

- invalid lifecycle state;
- invalid lifecycle transition evidence;
- missing approval for high/critical risk;
- missing required evidence;
- irreversible change without explicit authority;
- rollback-required change without rollback artifact;
- stale approval after revision change;
- stale approval after scope change;
- architecture-impacting change without architecture evidence;
- missing closure evidence;
- separation-of-duties violation;
- expired exception.

## Governed-package reconciliation

Make governed packages use the shared change schema.

Preserve:

- existing governed-package examples;
- task-to-change references;
- expected-artifact relationships;
- scanner evidence;
- manifest and lock compatibility where promised.

No existing governed-package contract may silently change meaning.

Where byte identity cannot be retained, use the approved golden-migration procedure with:

- exact old hash;
- exact new hash;
- explicit reason;
- human approval;
- changelog entry.

---

# Workstream 3 — Architecture Governance

Implement:

- `architecture_conformance` governance module;
- `architecture_governance` optional profile;
- architecture schemas;
- architecture evidence schemas;
- evidence importers;
- starter contract;
- examples;
- tests;
- documentation.

## Architecture vocabulary

Support declared architecture for:

- architecture descriptions;
- viewpoints;
- systems;
- components;
- modules;
- layers;
- bounded contexts;
- interfaces;
- dependency directions;
- trust boundaries;
- data boundaries;
- deployment boundaries;
- canonical components;
- architecture decisions;
- ADR artifacts;
- principles;
- constraints;
- required checks;
- architecture exceptions.

Architecture impact belongs on the shared change model.

Do not duplicate architecture impact inside a separate change representation.

## Architecture evidence

Implement normalized evidence such as:

```json
{
  "schema": "nornyx.architecture_evidence.v1",
  "check_id": "dependency-boundaries",
  "tool": "import-linter",
  "tool_version": "2.0",
  "status": "pass",
  "subject_revision": "<revision>",
  "generated_at": "<timestamp>",
  "violations": [],
  "artifact": "reports/import-linter.json",
  "artifact_sha256": "<sha256>"
}
```

Nornyx may parse supplied reports.

Nornyx must not execute:

- ArchUnit;
- import-linter;
- dependency-cruiser;
- Semgrep;
- CodeQL;
- SonarQube;
- compiler checks;
- external scanners.

Implement evidence importers only when there is a stable, bounded report format.

Fail closed on:

- malformed reports;
- wrong schema;
- missing subject revision;
- revision mismatch;
- missing artifact hash;
- invalid status;
- evidence for a different check;
- stale evidence;
- required check without evidence.

Architecture Radar remains excluded unless an ADR based on real evidence proves it is necessary and can remain advisory.

---

# Workstream 4 — Supply-Chain Governance

Perform GSA against existing package-scanner and governed-package functionality before adding this module.

Implement `supply_chain` only if the analysis proves it is reusable beyond governed packages.

Govern:

- dependency identity;
- version;
- source registry;
- source provenance;
- hashes;
- lockfiles;
- SBOM evidence;
- licence evidence;
- vulnerability evidence;
- secret-scan evidence;
- package-manager scripts;
- hooks;
- build provenance;
- attestation;
- dependency exceptions;
- update policy;
- end-of-life status.

Reuse existing package-scanner evidence and importers.

Do not duplicate scanner logic.

Do not execute package managers, scanners or builds.

Classify the final result as one of:

- implemented reusable module;
- retained inside governed-package profile;
- external evidence contract only;
- rejected as duplicative.

Record the decision in an ADR.

---

# Workstream 5 — Data-Protection Governance

Apply GSA first.

Implement `data_protection` if justified.

Govern declaratively:

- data classification;
- personal data;
- credentials and secrets;
- regulated data;
- permitted purposes;
- permitted actors;
- prohibited destinations;
- model exposure;
- external-service exposure;
- retention period;
- deletion requirement;
- residency or boundary requirements;
- encryption evidence;
- anonymization evidence;
- access-review evidence;
- exception authority;
- expiry.

Nornyx does not inspect live databases or move/delete data.

External systems provide evidence.

Fail closed where required data classification or required evidence is missing.

Avoid turning Nornyx into a privacy-management platform.

---

# Workstream 6 — Lifecycle Governance

Apply GSA first.

Implement `lifecycle_management` for reusable governed-object lifecycle controls.

Potential governed objects:

- profiles;
- modules;
- policies;
- approvals;
- exceptions;
- agents;
- connectors;
- models;
- evidence contracts;
- architecture decisions;
- packages.

Lifecycle states may include:

```text
draft
proposed
approved
active
deprecated
suspended
retired
superseded
revoked
```

Govern:

- owner;
- authority;
- entry criteria;
- exit criteria;
- evidence;
- review date;
- expiry;
- replacement;
- migration;
- retirement evidence.

Do not create competing lifecycle fields for objects that already have defined semantics. Reuse a common lifecycle vocabulary only where it reduces duplication.

---

# Workstream 7 — Release Governance

Apply GSA first.

Implement `release_control` if reusable across profiles.

Govern:

- release identity;
- version;
- included changes;
- included artifacts;
- exact revision;
- release environment;
- required evaluations;
- required evidence;
- vulnerability and supply-chain evidence;
- rollback readiness;
- release authority;
- separation of duties;
- promotion authority;
- exception status;
- release decision;
- release closure.

Nornyx does not publish, deploy or promote releases.

It declares and checks whether the required evidence and approvals exist.

Reconcile with existing Nornyx release-readiness tooling rather than creating a parallel release system.

---

# Workstream 8 — Incident-Response Governance

Apply GSA first.

Implement `incident_response` if a reusable declarative contract is justified.

Govern:

- incident id;
- severity;
- affected systems;
- owner;
- commander;
- containment authority;
- evidence preservation;
- rollback or mitigation;
- communication obligations;
- approval requirements;
- post-incident review;
- corrective actions;
- closure evidence.

Nornyx must not operate systems, trigger containment, disable services or execute remediation.

External operational systems perform actions and emit evidence.

---

# Workstream 9 — Governance Surface Analysis

Complete the GSA method as a first-class documented Nornyx practice.

Apply it to Nornyx itself for:

- `.nyx` contracts;
- governance packs;
- modules;
- governed packages;
- external evidence;
- generated artifacts;
- approvals;
- exceptions;
- changes;
- architecture declarations;
- release decisions.

The method must cover:

1. system boundary;
2. governed-object inventory;
3. unacceptable losses;
4. hazards;
5. lifecycle;
6. owners;
7. authorities;
8. actions;
9. trust boundaries;
10. feedback paths;
11. evidence paths;
12. unsafe control actions;
13. constraints;
14. containment and rollback;
15. exceptions;
16. placement decision.

Create a governance-completeness matrix for each built-in profile.

Add `nornyx.gsa_report.v1` and CLI tooling only if the dogfood exercise proves that structured tooling materially improves repeatability.

Otherwise, explicitly decide:

```text
GSA remains a documented method with validated templates; no runtime tooling is justified.
```

Do not create tooling merely to satisfy the original roadmap wording.

---

# Workstream 10 — Profile integration

For each existing built-in profile, conduct GSA and determine which modules it should require.

Do not attach every module to every profile.

Document module selection for:

- minimal;
- standard;
- ai_coding;
- regulated;
- legacy_upgrade;
- nornyx_language;
- agentic_repo_harness;
- telecom_ops;
- business_ops;
- ai_governance;
- finance_ops;
- architecture_governance.

For every module-profile relation record:

- reason;
- controls gained;
- compatibility impact;
- evidence requirements;
- approval requirements;
- rejected alternative.

Preserve one primary profile plus modules.

Do not introduce peer multi-profile composition.

---

# Workstream 11 — Schema and extension-block architecture

The existing pack schemas currently carry rules and metadata.

Design the minimum safe mechanism for modules to contribute governed block schemas such as:

- changes;
- exceptions;
- architecture;
- releases;
- incidents;
- data classifications.

Requirements:

- data only;
- bounded JSON Schema subset;
- deterministic;
- no remote `$ref`;
- no dynamic code;
- no custom executable validators;
- no arbitrary format callbacks;
- local bundled references only;
- cycle detection;
- stable schema identities;
- versioning;
- compatibility checks;
- safe resource limits;
- stable diagnostics.

Do not silently reinterpret existing `.nyx` documents.

Do not add block-schema extensibility until its security and composition semantics are fully specified and tested.

---

# Workstream 12 — CLI and public API

Add only necessary commands.

Possible commands:

```text
nornyx modules list
nornyx modules inspect <name>
nornyx modules validate <path>
nornyx governance resolve
nornyx governance explain
nornyx governance matrix
nornyx evidence validate <file>
```

Do not add `governance analyze` unless GSA tooling is approved.

CLI requirements:

- text and JSON output where appropriate;
- stable exit codes;
- stable diagnostic codes;
- resolution provenance;
- lock status;
- module dependencies;
- active controls;
- required evidence;
- approval requirements;
- exception status;
- offline behavior.

Public API requirements:

- expose intentional stable contracts only;
- keep internal composition details private;
- document stability level;
- preserve existing signatures;
- add deprecation periods before removing public behavior.

---

# Workstream 13 — Security hardening

Threat-model all new governance surfaces.

At minimum test:

- malicious module;
- malicious profile;
- duplicate identities;
- namespace squatting;
- path traversal;
- symlink traversal;
- parent traversal;
- YAML resource exhaustion;
- schema bombs;
- local `$ref` cycles;
- remote `$ref`;
- malformed rule;
- unknown operator;
- forged normalized approval;
- stale approval;
- forged evidence;
- stale evidence;
- hash substitution;
- lock substitution;
- exception-based weakening;
- expired exception;
- self-approved change;
- profile attempting to remove evidence;
- module attempting to remove approval;
- project attempting to override a denial;
- package attempting to approve itself;
- architecture evidence for the wrong revision;
- release evidence for the wrong revision;
- Unicode/confusable identities;
- platform-specific path behavior.

Maintain:

- pack limits;
- composed-model limits;
- evaluator step limits;
- deterministic errors;
- no network imports;
- no subprocess execution;
- no hidden connector activation.

---

# Workstream 14 — Backward compatibility

Create a formal compatibility corpus containing:

- all existing profile starters;
- existing governed-package examples;
- existing `.nyx` examples;
- legacy profile API outputs;
- CLI stdout and exit codes;
- generated artifacts;
- locks;
- manifests;
- projection reports.

Compatibility classes:

- byte identical;
- canonical-LF identical;
- semantically equivalent;
- intentional migration requiring approval.

Never regenerate a golden merely because a test fails.

Every changed golden requires:

- old hash;
- new hash;
- exact diff;
- reason;
- compatibility classification;
- approval;
- changelog entry.

---

# Workstream 15 — Testing and assurance

Add:

- unit tests;
- integration tests;
- golden tests;
- adversarial tests;
- property-based or permutation tests;
- wheel-install tests;
- cross-platform tests;
- documentation-execution tests;
- performance/resource-limit tests.

Required areas:

- module loading;
- module discovery;
- module dependencies;
- module conflicts;
- deterministic composition;
- monotonic composition;
- schema composition;
- change lifecycle;
- approval invalidation;
- separation of duties;
- evidence integrity;
- exceptions;
- architecture evidence;
- supply-chain evidence;
- data-protection declarations;
- lifecycle rules;
- release governance;
- incident governance;
- GSA matrices;
- installed-wheel resources;
- backward compatibility.

Run at minimum:

```bash
python -m pytest -q
python -m ruff check .
python scripts/check-public-boundary.py --repo .
python -m build
python -m twine check dist/*
git diff --check
```

Also run all repository-specific:

- stable-language checks;
- release-readiness checks;
- RC checks;
- governed-package examples;
- governance examples;
- wheel smoke tests;
- CLI examples;
- documentation examples.

Linux CI must execute real symlink tests.

---

# Implementation sequencing

Do not create one unreviewable commit.

Use a dedicated program branch and logical, independently testable commits or PR-sized stages.

Recommended stages:

## Stage A — Program reconciliation

- current-state audit;
- roadmap-status update;
- final ADR set;
- extension-block schema design;
- exact implementation sequence.

## Stage B — Foundational modules

- human approval;
- evidence integrity;
- separation of duties;
- exception management.

## Stage C — Change Governance

- change_control;
- governed-package reconciliation;
- stale approval and lifecycle checks.

## Stage D — Architecture Governance

- architecture_conformance;
- architecture_governance profile;
- architecture evidence importers.

## Stage E — GSA and candidate decisions

Apply GSA to:

- supply chain;
- data protection;
- lifecycle;
- release;
- incident response.

For each, issue an ADR:

- implement;
- external evidence only;
- reject;
- not required.

## Stage F — Approved later modules

Implement only the modules approved by Stage E.

## Stage G — Profile integration

Assign modules to profiles based on documented GSA results.

## Stage H — Full hardening

- adversarial suite;
- compatibility suite;
- wheel verification;
- cross-platform verification;
- documentation execution.

## Stage I — Program closure audit

Independent audit and closure report.

Every stage must be CI-green before the next stage begins.

Do not continue past a Critical or High unresolved audit finding.

---

# Module-proliferation control

The earlier architecture audit imposed a module-freeze concern.

Do not ignore it.

Before implementing each later module, prove at least one:

1. It is reused by two or more profiles.
2. It reconciles duplicated existing semantics.
3. It addresses a high-priority GSA control gap.
4. It provides a stable evidence contract needed by real existing features.

Otherwise classify it as:

- not required;
- profile-local rule;
- external tool responsibility;
- human organizational process.

Program completion does not require implementing unjustified modules.

It requires making final, evidence-backed decisions.

---

# Required documentation outputs

Update existing planning documents to reflect actual implementation status.

Add:

```text
docs/planning/governance-extension/
  15_CURRENT_IMPLEMENTATION_INVENTORY.md
  16_GOVERNANCE_MODULE_CATALOG.md
  17_PROFILE_MODULE_MAPPING.md
  18_GSA_RESULTS.md
  19_COMPATIBILITY_REPORT.md
  20_SECURITY_ASSURANCE_REPORT.md
  21_PROGRAM_CLOSURE_REPORT.md
  22_FINAL_INDEPENDENT_AUDIT.md
```

The closure report must contain one row for every original and newly discovered roadmap item.

Required columns:

- item;
- original status;
- final status;
- implementation location;
- tests;
- documentation;
- residual risk;
- future re-entry condition.

No item may have an ambiguous final status.

---

# Independent final audit

After implementation, stop acting as the implementer.

Act as an independent adversarial review board.

Audit:

- stable-core discipline;
- module necessity;
- module proliferation;
- source-of-truth consistency;
- deterministic behavior;
- monotonicity;
- approval integrity;
- evidence integrity;
- exception safety;
- change-model consistency;
- governed-package compatibility;
- architecture-governance scope;
- specialist-tool separation;
- supply-chain duplication;
- data-protection scope;
- lifecycle-model duplication;
- release-tool duplication;
- incident-runtime boundary;
- GSA usefulness;
- schema safety;
- CLI stability;
- API stability;
- documentation accuracy;
- wheel packaging;
- cross-platform behavior;
- test adequacy;
- security;
- residual risks.

For each finding provide:

- id;
- severity;
- evidence;
- affected component;
- failure scenario;
- required correction;
- blocking status.

Return exactly one verdict:

- `GO`
- `GO WITH CONDITIONS`
- `NO-GO`

`GO` is required for program closure.

Do not declare closure with unresolved Critical or High findings.

Medium findings must either be corrected or explicitly accepted by a documented human decision.

---

# Program closure criteria

The governance program is complete only when all are true:

1. The current implementation inventory is accurate.
2. Foundational governance modules are implemented or formally rejected.
3. Change Governance is implemented and reconciled with governed packages.
4. Architecture Governance is implemented.
5. GSA is applied to Nornyx and every remaining candidate.
6. Supply-chain governance has a final implemented/rejected placement.
7. Data-protection governance has a final implemented/rejected placement.
8. Lifecycle governance has a final implemented/rejected placement.
9. Release governance has a final implemented/rejected placement.
10. Incident-response governance has a final implemented/rejected placement.
11. Every built-in profile has a documented module mapping.
12. All schemas are versioned and packaged.
13. All profile and module packs are integrity-locked.
14. No dual source of truth exists.
15. No unjustified stable-core concept was added.
16. No executable plugin mechanism exists.
17. No network registry exists.
18. No automatic approval exists.
19. No deployment or operational execution exists.
20. All old compatibility commitments are tested.
21. All approved migrations are documented.
22. Full tests pass.
23. Build and installed-wheel tests pass.
24. Linux security tests pass.
25. Documentation matches implementation.
26. There are no unresolved review threads.
27. The final independent audit verdict is `GO`.
28. The closure matrix contains no unresolved planned/deferred/TBD items.
29. The roadmap is rewritten to distinguish:
    - completed current program;
    - rejected items;
    - externally enforced responsibilities;
    - future proposals outside the program.
30. A human-approved release candidate is prepared.

Do not publish, tag or deploy unless explicitly authorized.

---

# Stop conditions

Stop and report instead of concealing the issue when:

- a core-language revision is required;
- backward compatibility cannot be preserved;
- a shared schema conflicts with governed packages;
- a module requires arbitrary expressions;
- a feature requires executing external tools;
- a feature requires network loading;
- an exception could weaken core safety;
- approval normalization loses meaning;
- evidence cannot be bound to the governed revision;
- deterministic output cannot be achieved;
- a proposed module has no demonstrated reuse or control gap;
- documentation and code cannot be reconciled;
- tests expose unresolved Critical or High defects.

Partial completion is not program closure.

---

# Final response format

Return:

## Executive Summary

## Repository Baseline

## Completed Governance Capabilities

## Governance Candidates Rejected or Assigned Externally

## Stable-Core Assessment

## Modules Implemented

## Profiles Added or Updated

## Schemas Added

## Public API and CLI Changes

## Backward-Compatibility Results

## Security Results

## Validation Results

List every command and exact outcome.

## Architecture Audit Findings

## Roadmap Closure Matrix

## Remaining Mandatory Work

This section must say exactly:

`None within the completed governance-extension program.`

Only use that sentence if all closure criteria are satisfied.

## Future Proposals Outside the Completed Program

List only genuinely new, externally triggered proposals. Do not present them as unfinished roadmap obligations.

## Final Verdict

Exactly one:

- `PROGRAM COMPLETE — READY FOR HUMAN RELEASE REVIEW`
- `PROGRAM INCOMPLETE — CORRECTIONS REQUIRED`
- `PROGRAM BLOCKED`

---

# Execution instruction

Run this goal with the strongest Codex reasoning model available, on a clean implementation branch from current `main`.

Do not authorize a release until the final independent audit returns `GO`.
