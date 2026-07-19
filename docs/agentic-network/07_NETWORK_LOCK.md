# The Agentic-Network Lock

`nornyx.agentic_network.lock` (schema `nornyx.agentic_network_lock.v1`) is a
deterministic, content-addressed binding of:

- the canonical governed-content digest of the parsed contract
  (`source_contract_digest` — stable under formatting and keyed-record
  reordering, changed by any semantic edit);
- the network id and immutable subject revision;
- the resolved profile and module identities, versions, and pack hashes;
- the composed block-schema ids and structural checks;
- the runtime-events schema version and protocol declaration versions;
- a sorted content digest for every identity, capability, membership, trust
  zone, gate, protocol target, delegation, handoff, relation, and
  revocation record;
- approval and evidence requirement references;
- the SHA-256 of every generated artifact.

```text
nornyx agentic-network lock CONTRACT --artifacts generated/agentic_network --out nornyx.agentic_network.lock --as-of 2026-07-17T00:00:00Z
nornyx agentic-network lock-check CONTRACT --lock nornyx.agentic_network.lock --artifacts generated/agentic_network --as-of 2026-07-17T00:00:00Z
```

## What lock-check detects

Stale source contract (`AN_LOCK_SOURCE_STALE`), changed profile or module
(`AN_LOCK_PROFILE_MISMATCH`, `AN_LOCK_MODULE_MISMATCH`), changed schema set
(`AN_LOCK_SCHEMA_MISMATCH`), changed structural checks
(`AN_LOCK_CHECKS_MISMATCH`), changed records (`AN_LOCK_RECORD_MISMATCH`),
changed/missing/unexpected artifacts (`AN_LOCK_ARTIFACT_MISMATCH`,
`AN_LOCK_ARTIFACT_MISSING`, `AN_LOCK_ARTIFACT_UNEXPECTED`), wrong network
(`AN_LOCK_NETWORK_MISMATCH`), wrong or mutable revision
(`AN_LOCK_REVISION_MISMATCH`, `AN_LOCK_REVISION_MUTABLE`), and hash
substitution inside the lock itself.

## What the lock is not

The lock contains no secrets and attests contract/artifact binding only. It
never attests that runtime behavior complied, who produced the bytes, or
that the content is true. A hostile local writer can regenerate a consistent
lock — detecting unauthorized regeneration is a repository control (git
history and human review), not a lock property.
