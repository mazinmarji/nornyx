# 18 - Governance Surface Analysis Results

Status: implemented final placement record for all candidate domains.

## Method Result

The 16-step method in doc 09 was applied to Nornyx itself and the remaining
candidate domains. It materially improved placement decisions, but a runtime
schema or CLI would only serialize review judgments already clearer in versioned
documents. Final decision:

> GSA remains a documented method with validated templates; no runtime tooling
> is justified.

This is `not_required_after_GSA` under ADR-0031. The advisory profile matrices
under `gsa/` are validated by tests but are never loaded by the governance
runtime.

## Nornyx Dogfood: 16 Steps

| Step | Result |
|---|---|
| System boundary | Local repository, `.nyx` contracts, bundled/project packs, generated artifacts, local evidence, and package inputs are inside validation; networks, tools, deployment systems, identity systems, and operational systems are outside. |
| Governed objects | Contracts, packs, modules, governed packages, evidence, generated artifacts, approvals, exceptions, changes, architecture declarations, and release decisions. |
| Unacceptable losses | Unsafe policy weakening, forged human authority, evidence substitution, unreviewed high-risk change, package execution, stale architecture decision, release without human approval. |
| Hazards | Malformed or shadowed packs, stale locks, non-human approver, missing/hash-mismatched evidence, expired exception, stale revision/scope, unsafe package hooks, duplicated lifecycle models. |
| Lifecycle | Packs load/compose/lock; evidence generates/expires; approvals bind/invalidate; changes transition/close; exceptions start/expire/close; releases remain candidate until human approval. |
| Owners | Project owner owns contracts; maintainers own built-ins; named human authorities own approvals, exceptions, changes, architecture, and releases; specialist systems own analysis. |
| Authorities | Human roles only for high-impact decisions; tools and generated output are intrinsically denied approval authority. |
| Actions | Author, review, approve, reject, validate, import evidence, generate inert artifacts, close, retire, and release-decision recording. Nornyx performs no operational action. |
| Trust boundaries | Local pack paths, project documents, package payloads, neutral evidence reports, generated-output comparison, and human-supplied approval records. |
| Feedback paths | CI reruns checks; locks expose pack changes; drift compares generation; timestamps and revision/scope hashes expose stale evidence and approval. |
| Evidence paths | Local SHA-256 artifacts, scanner reports, normalized external evidence, transition records, ADRs, approval records, and release reports. |
| Unsafe control actions | Missing review, wrong authority, approval before evidence, stale approval retained, exception over core safety, pass status with violations, release approval inferred from tooling. |
| Constraints | Monotonic composition, closed rules, fixed checks, exact revision/scope binding, local artifact containment, explicit expiry, non-exceptable safety invariants. |
| Containment/rollback | Resource caps, fail-closed diagnostics, no execution, bounded change blast radius, rollback declarations, package payload remains inert, release/tag/publish flags remain false. |
| Exceptions | One project-owned model with human authority, compensating controls, expiry, closure evidence, and immutable core exclusions. |
| Placement | Stable invariants in engine; reusable declarative controls in seven modules after ADR-0033; architecture and agentic-network governance in optional profiles; specialist analysis and operations external; package scanning package-owned. |

## Surface Completeness

| Surface | Owner / authority | Evidence and drift | Containment / retirement | Placement status |
|---|---|---|---|---|
| `.nyx` contracts | project owner / human reviewer | checker diagnostics, CI, generated drift | fail closed; retire in version control | `implemented` |
| governance packs | maintainers/project owner / code review | canonical hash, provenance, lock, resolution trace | local-only, resource limits, version/supersession | `implemented` |
| modules | maintainers / human review | integrity hash, composition provenance, tests | monotonic merge, conflicts, namespace freeze | `implemented` |
| governed packages | package owner / human gate | scanner, manifest/lock, claim mismatch, adapters | payload never executes; package can be rejected/retired | `implemented` |
| external evidence | specialist producer / human consumer | schema, hash, revision, tool/version, freshness | local import only; expire and replace | `implemented` |
| generated artifacts | project owner / review | deterministic regeneration and drift | overwrite only explicit outputs; regenerate/retire | `implemented` |
| approvals | accountable human | normalized retained source, evidence, revision/scope, expiry | invalidation and denial of non-human authority | `implemented` |
| exceptions | accountable owner and disjoint approver | review evidence, interval, compensating controls | expiry, closure, core controls never excepted | `implemented` |
| changes | change owner and human approver | transition, evidence, scope hash, revision, closure | blast radius, rollback, reject/cancel/close | `implemented` |
| architecture | architecture owner and architect | neutral report, ADR, hash, revision, freshness | no source inference or remediation; supersede decisions | `implemented` |
| release decisions | release owner and human release authority | release-readiness/stabilization report and validation matrix | publish/tag/deploy false until approval; supersede candidate | `implemented` in existing tooling |

## Candidate Priority And Placement

Priority tuple order is `(Impact, Irreversibility, Trust exposure, Existing gap,
Likelihood, Autonomy)`, each scored 1-3.

| Candidate | Tuple | GSA evidence | Final status |
|---|---|---|---|
| Supply chain | `(3,3,3,1,3,2)` | Scanner and governed-package gates already own inventory, scripts, hooks, secrets, license presence, SBOM/secret adapters, provenance, and package locks. A module would duplicate the only real consumer. | `implemented_as_external_evidence_integration` |
| Data protection | `(3,3,3,2,2,2)` | Profiles deny secrets/PII exposure, but retention, residency, access, and deletion are organizational/live-system facts with no shared local evidence envelope. | `not_required_after_GSA` |
| Lifecycle | `(2,2,2,1,2,1)` | Changes, approvals, exceptions, architecture decisions, packs, packages, and release candidates already own distinct states. One vocabulary would erase valid differences. | `not_required_after_GSA` |
| Release control | `(3,3,2,1,2,1)` | Existing release readiness and stabilization already enforce evidence, no-go conditions, human authority, and no publish/tag/deploy. Shared modules cover reusable change controls. | `superseded` |
| Incident response | `(3,3,3,2,2,2)` | Incident actions and evidence live in operational systems; current profiles provide no stable two-profile incident contract or executable fixtures. | `not_required_after_GSA` |
| GSA runtime tooling | `(1,1,1,1,1,1)` | Documents and a small validated template give repeatability without adding a new report schema and CLI lifecycle. | `not_required_after_GSA` |

## Stage F Result

No later candidate passes the module-proliferation gate. Stage F is complete
with no additional module implementation. Re-entry conditions are normative in
ADR-0031.

## Later ADR-0033 Addendum

AN-001 is outside the closed Stage F candidate set. Its advisory GSA matrix
places static identity, capability, membership, trust-zone, gate, protocol
contract, and revocation controls in one optional profile and one thin module.
Authentication, identity issuance, discovery, transport, live MCP/A2A,
framework execution, operational monitoring, and runtime enforcement remain
external. This evidence justifies the seventh module without reopening the
specialist-module decisions in ADR-0031.
