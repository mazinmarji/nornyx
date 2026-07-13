# ADR-0030 - Architecture Evidence and Radar Boundary

Status: Accepted

Date: 2026-07-13

## Context

Architecture governance needs evidence from specialist tools without turning
Nornyx into a source analyzer or external-tool runner. Tool output contracts
also differ: dependency-cruiser documents a schema-backed JSON representation,
while Import Linter's documented CLI does not promise an equivalent stable JSON
report. Direct ingestion of every vendor format would couple the governance
engine to volatile implementation details.

Architecture Radar was proposed as a way to infer undeclared components from
repository layout. No repository corpus demonstrates that these heuristics are
reliable, and implementing them would cross the accepted no-source-analysis
boundary.

## Decision

1. Nornyx owns `nornyx.architecture_report.v1`, a small neutral JSON envelope
   that CI adapters may emit after running a specialist tool outside Nornyx.
2. Nornyx imports the local envelope, validates bounded shape and resource
   limits, rejects duplicate keys and unsafe paths, hashes the exact bytes, and
   emits `nornyx.architecture_evidence.v1`.
3. Nornyx does not execute or embed ArchUnit, Import Linter,
   dependency-cruiser, Semgrep, CodeQL, SonarQube, compiler checks, or scanners.
4. Raw vendor-report importers are not required in the current program. They
   may enter a separate future proposal only when a versioned stable format,
   representative fixtures, and maintenance ownership are demonstrated.
5. Architecture Radar is `rejected_with_ADR` for the current governance
   program. Re-entry requires a separately approved program with a real
   evidence corpus showing useful precision and an approach that does not make
   Nornyx a source-code-analysis engine.

## Consequences

- Evidence remains portable across specialist tools and bound to an exact
  revision, freshness interval, local artifact, and content hash.
- External CI owns tool invocation and mapping into the neutral envelope.
- The importer remains data-only, deterministic, local-only, and incapable of
  granting approval.
- A valid hash proves content binding, not that the tool's conclusion is true.

## Evidence

- [dependency-cruiser CLI output formats](https://github.com/sverweij/dependency-cruiser/blob/main/doc/cli.md)
- [Import Linter documented CLI](https://import-linter.readthedocs.io/en/stable/get_started/run/)
- `nornyx/governance/architecture.py`
- `tests/test_architecture_governance.py`
