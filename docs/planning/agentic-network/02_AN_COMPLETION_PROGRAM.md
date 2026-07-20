# AN-002..AN-006 — Agentic-Network Completion Program

Status: **merged and closed.** Delivered via PR #37 (merge commit `e4fb39e0`,
base `e252bbe`, final audited head `8ddf0187`); the implementation branch has
been deleted. The independent detached-head audit closed both findings
(AN-CLOSE-AUD-001, LOW, fix `ed166309`; AN-CLOSE-AUD-003, MEDIUM, fix
`8ddf0187`), and post-merge CI on `main` passed on every job. This record
documents evidence only; merging the AN program did not by itself perform a
release, publication, deployment, runtime enablement, or automatic approval —
those remain separate, explicitly authorized actions (the package release ships
as 1.7.0).

## Scope delivered

| Phase | Decision | Delivery |
| --- | --- | --- |
| Phase 0 | ADR-0034..ADR-0038 | frozen architecture for delegation/handoff/relations, artifacts+lock, runtime evidence, adapters, product proof |
| AN-002 | ADR-0034 | `agentic_network_governance` 0.2.0: closed `delegations`/`handoffs`/`relations`, boolean `delegable` + `max_delegation_depth`, fixed check `agentic_network_delegation.v1`, migration `migration:modules-agentic-network-governance-v2` |
| AN-003 | ADR-0035 | `nornyx/agentic_artifacts.py`: 10 deterministic artifacts, `nornyx.agentic_network_lock.v1`, CLI `agentic-network generate/lock/lock-check` |
| AN-004 | ADR-0036 | `nornyx/agentic_evidence.py`: `nornyx.agentic_runtime_events.v1` (18 closed types), conformance + bounded ordering validation, CLI `agentic-network evidence-validate` |
| AN-005 | ADR-0037 | `integrations/nornyx_agentic_adapters/`: framework-free kernel, CrewAI + LangGraph adapters, deterministic harness; not packaged |
| AN-006 | ADR-0038 | `examples/agentic_network_support/` (Governed Customer Support Network), `nornyx/eval_import.py` + `eval-import promptfoo`, `scripts/agentic_network_ci.py`, `docs/agentic-network/` set, README section |

## Boundary preserved

No stable-core concept, top-level block, public Python export, runtime
authentication, identity issuance, transport, endpoint, command, credential,
framework execution in core, service discovery, live MCP/A2A connectivity,
automatic approval, release, publication, or deployment behavior was added.
The package version remains 1.6.2 and no tag was created.

## Independent adversarial audit ledger

The implementation was reviewed as untrusted after all phases and the full
suite passed. Findings:

### AN2-AUD-001 — cross-zone gates not bound to zone gate declarations
- Severity: LOW. File: `nornyx/governance/agentic_delegation.py`
  (`_cross_zone_controls`).
- Failure scenario: a cross-zone delegation or handoff cites a gate covering
  the zones and action class that neither zone declares in
  `egress_gate_refs`/`ingress_gate_refs`, bypassing the zone-side control
  symmetry protocol targets already enforce.
- Remediation: added `AN_DELEGATION_/AN_HANDOFF_EGRESS_GATE_MISSING` and
  `..._INGRESS_GATE_MISSING`; positive cross-zone fixtures now declare the
  gates; new negative test
  `test_cross_zone_delegation_gates_must_be_zone_declared`.
- Status: CLOSED (fix commit: final remediation commit; regression test in
  `tests/test_agentic_network_delegation.py`). Residual: none.

### AN3-AUD-001 — artifact writer could follow a pre-planted symlink
- Severity: MEDIUM. File: `nornyx/agentic_artifacts.py`
  (`write_agentic_network_artifacts`).
- Failure scenario: a local attacker plants
  `generated/agentic_network/identity_manifest.json -> ../../victim`; the
  next generation writes through the link and clobbers the victim path.
- Remediation: `os.lstat` inspection of every target; symlinked,
  reparse-point, or non-regular targets are refused with
  `AN_ARTIFACT_OUTPUT_INVALID` (matching the lock writer's hardening).
- Status: CLOSED (regression test
  `test_writer_refuses_symlinked_artifact_targets`, Linux-effective and
  skip-marked where symlinks are unavailable). Residual: parent-directory
  symlinks remain governed by the same repository-level controls as the
  existing v0.1 generator.

### AN4-AUD-001 — evidence-artifact resolution root undocumented
- Severity: INFO (documentation accuracy). File:
  `docs/agentic-network/06_RUNTIME_EVIDENCE.md`.
- Remediation: documented that `evidence_artifact.path` resolves relative to
  the events file's directory with containment enforced.
- Status: CLOSED.

### AN5-AUD-001 — kernel recorded external crossings without approval
- Severity: LOW. File:
  `integrations/nornyx_agentic_adapters/governance_kernel.py`
  (`record_zone_crossing`).
- Failure scenario: an adapter records an external-classified crossing
  without an approval reference; the violation is only caught later at
  evidence validation instead of failing fast at the hook.
- Remediation: external-classified destinations now require `approval_ref`
  (`AN_ADAPTER_CROSSING_APPROVAL_REQUIRED`) and emit a policy violation.
- Status: CLOSED (regression assertion in
  `test_zone_and_sensitive_sharing_enforcement`). Residual: adapter
  enforcement remains cooperative by design; evidence validation stays the
  final authority.

Also remediated during verification: two hardcoded intentional-migration
counts (7 → 8) in `tests/test_governance_compatibility_corpus.py` and
`tests/test_governance_audit_compatibility.py` to admit the recorded AN-002
migration.

### Audited with no finding

Stable-core preservation; schema closure (`additionalProperties: false`
throughout, reviewed keyword subset); composed-module approval authority end
to end; revision binding and lock correctness (field-by-field verification,
duplicate-key-rejecting loads); determinism (repeat/permutation/formatting
byte identity, wheel-vs-source byte identity, pinned golden digests);
delegation subset/depth/cycle semantics; handoff
responsibility-not-authority; replay/ordering model; sensitive-category
denial at every layer; packaging boundaries (no framework imports in core,
integrations and support example excluded from the wheel, version
unchanged); zero-network/zero-process observation in every new test family;
credential scan of the full diff (no credentials, keys, tokens, or live
endpoints); documentation command accuracy and prohibited-claims checks.

## Residual risks (accepted and documented)

1. Supplied evidence can be omitted or fabricated by a runtime; Nornyx
   proves conformance of supplied records only (stated in every report).
2. Adapter enforcement is cooperative; bypassing the adapter bypasses the
   hook (stated in adapter docs and README).
3. Structural signature references are not cryptographic verification; none
   is claimed.
4. The network lock binds bytes, not producers; unauthorized regeneration is
   a repository-review control.
5. Sub-directory contents of the artifact output directory are outside the
   lock's unexpected-artifact detection, which governs the flat locked
   namespace only.
