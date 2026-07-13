# 20 - Security Assurance Report

Status: implemented assurance record for the completed program surfaces.

## Scope

This report covers governance packs, composition, approvals, evidence,
exceptions, changes, architecture evidence, governed packages, locks, the new
inspection CLI, and public validation API. Nornyx remains local-only,
data-only, deterministic where promised, and unable to approve, deploy,
publish, remediate, analyze source, execute specialist tools, or retrieve
network content.

## Threat Closure Matrix

| Threat | Mitigation | Executable proof | Status |
|---|---|---|---|
| Malicious module/profile | Closed schemas, integrity hash, safe YAML, safety constants, no executable fields | module security/invalid profile fixtures; loader adversarial tests | mitigated |
| Duplicate identities | Same-tier identity collision fatal before composition | `test_registry_order_duplicate_detection_composition_and_locks` | mitigated |
| Namespace squatting | Non-bundled `nornyx.builtin.*` rejected | `test_loader_rejects_reserved_namespaces_and_resource_abuse` | mitigated |
| Path, parent, and symlink traversal | Inspect unresolved components from independent trust root, then real-path containment | loader, project discovery, both profile CLI entry points, module CLI, evidence CLI, and architecture report importer tests | mitigated; real symlinks authoritative on Linux CI |
| YAML exhaustion | 512 KiB, depth, node, and alias caps before semantic loading | pack and evidence resource-abuse tests | mitigated |
| Schema bombs, local cycles, dangling/remote `$ref` | Only bundled reviewed block schemas; bounded subset; complete nested reference-graph cycle and target validation | `test_governance_block_schema_subset_rejects_unsafe_references` | mitigated |
| Malformed/unknown rule | Closed schema/operators/path grammar; structural type errors fail closed | normative rule fixtures and runtime adversarial tests | mitigated |
| Forged or malformed approval | Full schema validation, exact re-normalization from retained source, and fail-closed raw-normalization errors | normalized invariant matrix, raw mutation matrix, and adversarial `nornyx check` tests | mitigated |
| Stale approval | Exact revision/scope, invalidation, and expiry checks | change/foundational mutation matrices | mitigated |
| Forged, stale, or substituted evidence | Schema, artifact containment, SHA-256, revision, dependency, freshness, and approval/exception reference checks | foundational and evidence CLI tests | mitigated |
| Lock substitution | Set, id, version, tier, and content hash verified; duplicates fatal | runtime and governance CLI tamper tests | mitigated |
| Exception weakening/expiry | Core exclusion set, disjoint human authority, evidence, interval, expiry, closure | foundational exception mutation matrix | mitigated |
| Self-approved change | Author/approver disjointness and matching high-risk approval checks | foundational and change mutation matrices | mitigated |
| Profile/module removes evidence or approval | No removal syntax; unknown removal fields rejected; union-only composition | `test_packs_cannot_declare_governance_removal_operations` and composition tests | mitigated |
| Project overrides a denial | Core non-human denials injected and normalization rejects eligible denied actors | approval normalization and composed-denial tests | mitigated |
| Package approves itself | Its own execution-surface id cannot be an eligible approver; payload never executes | `test_governed_package_cannot_approve_itself_through_its_execution_surface` | mitigated |
| Architecture evidence wrong revision | Neutral envelope and artifact hash/revision/freshness checks | architecture fail-closed matrix | mitigated |
| Release evidence wrong revision | Shared governance evidence contract rejects record/subject mismatch | `test_release_evidence_for_the_wrong_revision_fails_closed` | mitigated |
| Unicode/confusable identity | ASCII identifier grammar in pack schemas | `test_confusable_pack_identities_fail_schema_validation` | mitigated |
| Nondeterministic errors/output | Canonical pack/lock/report order, permutation tests, byte/hash corpus, repeated-error equality | runtime determinism, compatibility corpus, malformed evidence repetition | mitigated |
| Hidden network/process/connector activation | No runtime source fields or execution API; remote sources rejected; monkeypatched APIs remain untouched | `test_governance_inspection_invokes_no_process_or_network_api` | mitigated |

## Boundary Proofs

- Governance packs contain YAML data only and must assert all safety constants.
- Block schemas are bundled resources; packs cannot introduce inline or remote
  schemas, Python, validators, templates, or expressions.
- The inspection report builder is private and read-only. Commands verify an
  existing lock but never create or rewrite one.
- Evidence validation reads the declared file and relative artifacts only
  under explicit roots. Hash integrity proves byte binding, not truth.
- Architecture and package specialist tools remain outside Nornyx. Importers
  accept bounded local reports and do not invoke producers.
- High-impact authority remains human. AI tools, execution surfaces,
  autonomous agents, models, connectors, and generated output are intrinsically
  denied approval authority.

## Residual Risks

- A reviewed project-tier pack is trusted like other repository data. Locks and
  provenance expose changes but cannot determine author intent.
- Validly hashed evidence may still be false, incomplete, biased, or produced
  by a compromised tool. Human and specialist-system review remains required.
- Prose can contain prompt-injection text. It remains inert data and is never
  interpreted as policy, permission, code, or instruction.
- Real symlink behavior varies by platform and privilege. Windows tests skip
  only when symlink creation is unavailable; Linux CI is required for closure.
- Resource limits bound accepted data but cannot prove total resistance to all
  parser/library implementation defects. Dependency updates remain a normal
  supply-chain responsibility.

No finding justifies network loading, executable plugins, source analysis,
automatic approval, deployment, or autonomous remediation.
