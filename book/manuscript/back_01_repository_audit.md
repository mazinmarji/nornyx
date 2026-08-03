---
title: "Repository Source Audit"
---

# Repository Source Audit

This audit records exactly which revision of Nornyx the book's technical statements describe, what
was verified during production, and where the previous edition's claims were corrected. It exists
so that a reader, reviewer, or auditor can reproduce the book's factual basis rather than trust it.

## Subject of the audit

| Property | Value |
|---|---|
| Repository | `mazinmarji/nornyx` (public, MIT licence) |
| Revision audited | `70d2b40ad79293209b43bdaa375f20badf63bdd7` |
| Revision subject | Merge of `feat/m2d-legacy-compatibility-shim` (pull request 56) |
| Audit date | 3 August 2026 |
| Audit method | Direct inspection of working tree, schemas, tests, workflows, and documentation; selected live execution of the command-line interface and the Python interface |

**Table J.1 — Audit subject.** The single revision to which every Nornyx claim in this book is pinned.

## Version axes at the audited revision

Nornyx deliberately versions several independent surfaces. Conflating them is a common source of
incorrect claims, so they are recorded separately.

| Axis | Value | Meaning |
|---|---|---|
| Python distribution | 1.11.0 | Package release on PyPI; independent of language version |
| Language and schema | 1.0 | Stable contract-language surface |
| Document declaration | `nornyx: "0.1"` / `"0.2"` | What contracts actually declare; the 1.0 target names the stable surface, not a new document version |
| Agentic integration interface | 1.2 | In-process authorization service-provider interface |
| Runtime-events schema | 1.1 | Selected by new locks; 1.0 remains valid for existing evidence |
| Network lock format | 1.0 | Content-addressed lock byte format |
| Supported Python | 3.10–3.13 | Advertised and tested range, plus a Windows job |
| Adapter package | `nornyx-agentic-adapters` 0.2.0 (Alpha) | Separate distribution and version line; depends on `nornyx>=1.10,<2` |
| CrewAI tested version | 1.15.4 | Exact pin, enforced at import |
| LangGraph tested version | 1.2.2 | Exact pin, enforced at import |

**Table J.2 — Version axes.** Each axis moves independently; a claim about one is not a claim about another.

## Scope of verification

Four independent audits were performed against the working tree, covering the core language and
toolchain; the agentic-network profile, evidence, locks, and authorization interface; framework
adapters and integrations; and governed packages, workspace governance, continuous integration,
and repository self-governance. Each produced a fact pack with file-path citations, which the
chapter authors were required to use as their ground truth. Where a chapter quotes source, schema,
or command output, the author verified it against the file directly.

Selected behavior was executed rather than only read: contract validation, artifact generation
(confirmed byte-identical across two runs), lock creation and verification, evidence validation
including negative cases, package scanning against hostile fixtures, and construction of an
authorizer through the documented interface. Framework adapters were verified by source and test
inspection; CrewAI and LangGraph themselves were not installed in the production environment, and
listings that depend on them are captioned accordingly.

## Implemented capability boundaries

The following are implemented at the audited revision, with test coverage: contract parsing,
validation, and diagnostics; deterministic artifact generation and drift detection; policy
reference resolution to canonical workspace sources; workspace checking across repositories;
domain profiles and governance modules with dependency-ordered, provenance-stamped, monotonic
composition and a timestamp-free lock; the agentic-network declaration model (identities,
capabilities, trust zones, memberships, gates, delegations, handoffs, relations, revocations, and
contract-only protocol targets); deterministic agentic artifact generation and content-addressed
network locking; supplied runtime-evidence validation including ordering, dependency, replay,
occurrence, and attempt semantics, with artifact-path containment; the authorization interface at
version 1.2 with frozen authorizer state and three decision outcomes; approval evaluation with
multi-layer refusal of non-human approvers; governed package scanning, radar, registration, and
import of external evidence from exactly two producers; and cooperative framework adapters for one
synchronous CrewAI tool surface and synchronous LangGraph state-graph nodes.

The following are documented but not implemented at this revision, and are labelled as guidance or
extension in the text: mandatory external enforcement of any kind; independent runtime attestation;
compilation or projection of contracts into external policy engines; a documentation service for
model clients; cross-repository policy references; a multi-level hierarchy conflict engine; and
the connector, guardrail, and memory surfaces described in planning documents. The legacy
compatibility shim merged at this revision is implemented but not packaged, and widens no coverage.

Declared non-goals, stated by the project itself, include being an agent runtime, an orchestration
framework, an identity provider, a secrets manager, a deployment engine, an observability backend,
or a live tool-protocol runtime; performing autonomous system modification; granting approvals; or
attesting runtime truth.

## Findings against the previous edition

The previous edition was pinned to the same revision, and its version table, coverage statements,
and assurance boundaries were found to be accurate. No factually incorrect Nornyx claim was
identified. Three classes of correction were nevertheless required, and are recorded in the
editorial change log: statements that were accurate but under-qualified at the point of use
(notably the capstone's narration of external gateway enforcement, which is an architectural
extension rather than product behavior); repository facts that were correct but incomplete in ways
that mattered pedagogically (the generator emits more artifacts than the previous edition's
command table implied; the policy rule language has two verbs, and `require` rules record pending
evidence obligations rather than executing checks); and honest details omitted entirely (the
repository does not run its own drift gate against a self-governing contract; the adapter package
is Alpha; the compatibility shim is unpackaged).

## Claims that could not be verified

The following are recorded as unverified rather than asserted anywhere in the book: the current
state of the package on the public index, including whether 1.11.0 has been published, since the
repository records 1.10.0 as the published version and publication is a separate authorized action;
any measured performance, latency, or scale characteristic, since the repository contains no
benchmark of that kind; the behavior of the adapters against framework versions other than the
exact pins; and any claim about how the software behaves in a deployment, since no deployment was
observed. Minor internal inconsistencies noted during the audit — a documentation count of frozen
modules that differs from the shipped count, a benchmark README that lags the interface version it
describes, and a duplicated constant — are reported in the traceability appendix and are not relied
upon by any chapter.

## Reproducing this audit

Clone the repository, check out the audited revision, install the package with its development
extra, and run the test suite; then generate, lock, and validate one of the bundled examples and
compare two generation runs byte for byte. The commands are listed in Appendix B, and the mapping
from book claims to repository paths is in Appendix J.
