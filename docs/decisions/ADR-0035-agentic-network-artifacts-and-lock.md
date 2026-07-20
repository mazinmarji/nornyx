# ADR-0035 — Deterministic Agentic-Network Artifacts, Protocol Declarations, and Network Lock (AN-003)

- Status: Proposed (implementation authorized by the owner's AN-completion goal;
  human review remains the final closure authority)
- Date: 2026-07-19
- Decision owner: human repository owner

## Context

An approved agentic-network contract needs deterministic, non-executable
governance artifacts that external frameworks and reviewers can consume, and a
content-addressed lock that detects drift between the contract, its resolved
governance composition, and its generated controls. AN-001 provides none of
this. Existing conventions: `generate_artifacts` writes LF-only files with a
hash-bearing generation manifest; `nornyx.profiles.lock` binds pack identities
and content hashes; `canonical_pack_hash` provides canonical JSON hashing.

## Decision

Add the bounded module `nornyx/agentic_artifacts.py` (not a stable public
export) and the grouped CLI command `nornyx agentic-network` with subcommands
`generate`, `lock`, `lock-check`, and (per ADR-0036) `evidence-validate`.

### Owned artifacts (stable filenames, default out dir `generated/agentic_network`)

- `network_manifest.json`
- `identity_manifest.json`
- `capability_matrix.json`
- `trust_zone_map.json`
- `delegation_policy_bundle.json`
- `handoff_manifest.json`
- `runtime_evidence_contract.json`
- `a2a_declaration.json` — an A2A-compatible declaration (not an A2A runtime)
- `mcp_capability_declaration.json` — an MCP-compatible capability declaration
  (not an MCP server)
- `agentic_generation_manifest.json` — artifact list with sha256 hashes

### Owned lock

`nornyx.agentic_network.lock` (JSON, schema `nornyx.agentic_network_lock.v1`),
default location: the contract's directory. It binds, at minimum: lock format
version; network id; subject revision; the canonical source-contract digest;
profile and module identities, versions, and pack content hashes; bundled
governance-schema ids for the composed blocks; runtime-evidence schema version;
protocol declaration versions; the sorted content digests of every identity,
capability, membership, trust zone, gate, delegation, handoff, relation, and
revocation record; approval and evidence requirement references; and the
sha256 of every generated artifact.

Digests are computed from canonical JSON (`sort_keys`, compact separators,
UTF-8) of the parsed document content, so semantically irrelevant formatting
in the `.nyx` source does not change hashes while any semantic change does.
The lock contains no secrets and attests contract/artifact binding only —
never runtime behavior, producer identity, or truth.

`lock-check` fails closed on: stale source contract, changed profile or module
hash, changed schema id set, changed record digest, changed or missing
artifact, unexpected governed artifact in the output directory, hash
substitution, mutable subject revision, and wrong network id. `generate`
refuses to run when the composed governance or the contract fails validation.

### Protocol declarations

Declarations carry only: static identity labels, capability labels and scopes,
expected message classes, contract identifiers, schema identifiers, required
approvals, evidence expectations, trust-zone restrictions, denied sensitive
categories, protocol version labels, and the mandatory pair
`execution_mode: contract_only`, `live_connector_execution: false`. Generation
fails closed if any URL, IP address, hostname, port, command, credential,
token, key, session, or transport-activation field would be emitted, and the
generator rejects source protocol targets containing such material. No
protocol certification is claimed.

## Rejected alternatives

- Reusing `generate_artifacts` — rejected: that surface is a frozen v0.1
  compatibility generator with golden baselines; mixing concerns risks byte
  drift of existing artifacts.
- Extending `nornyx.profiles.lock` — rejected: the profiles lock binds pack
  resolution, not contract content or generated artifacts; overloading it
  would change an existing lock format's meaning.
- Timestamped artifacts — rejected: nondeterministic.
- YAML artifacts — rejected: JSON with canonical ordering matches existing
  manifest/lock conventions and avoids YAML canonicalization ambiguity.

## Compatibility effect

Purely additive: new files, new CLI group, no change to existing generators,
locks, artifacts, or exit codes. Existing `generate`, `drift`, and profile
lock behavior is untouched.

## Security boundaries

Local-only file IO through the existing loader path/symlink protections for
inputs; outputs use LF, relative paths only, no environment or machine data.
No network, subprocess, credential, or endpoint content. The lock never grants
or implies approval.

## Public API / CLI / packaging effect

CLI adds the `agentic-network` group only. `nornyx/agentic_artifacts.py` is
importable but not part of the documented stable public API. Packaging adds
the bundled `agentic_network_lock_v1.schema.json` and
`agentic_runtime_events_v1.schema.json` resources (root `schemas/` copies
included).

## Determinism requirements

Byte-identical output across repeated runs, platforms, and semantically
irrelevant input permutations (key order, formatting); canonical ordering by
record id; semantic changes must change the affected hashes; root-source and
installed-wheel generation must agree byte-for-byte.

## Human authority

Generation and locking record declarations; approval semantics are untouched
and remain human. A lock is evidence of binding, not acceptance.

## Non-goals

Serving protocols, opening connections, discovery, deployment, signing,
attestation of runtime compliance.

## Test obligations

Repeated-generation byte identity; permutation stability; formatting-only
stability; mutation changes hashes; credential/endpoint/command rejection;
stale-lock, wrong-hash, missing/unexpected-artifact detection; golden fixture
hashes; installed-wheel equality; Windows path and Linux symlink coverage;
zero network and zero subprocess observation.

## Migration implications

None for existing artifacts. New golden fixtures are recorded with exact
hashes in the compatibility corpus as additive entries.

## Residual risks

The lock proves binding of reviewed bytes, not producer honesty; a hostile
local writer can regenerate a consistent lock — detection of unauthorized
regeneration remains a repository/review control (git history, PR review),
which is documented.
