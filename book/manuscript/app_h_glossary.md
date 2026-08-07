---
appendix: H
title: "Appendix H — Glossary"
---

# Appendix H — Glossary

Terms are defined as this book uses them. Where a term has a broader industry meaning, the entry
says so. Terms marked *(Nornyx)* name something specific to the Nornyx implementation at the
audited revision; all others are general to the discipline. Chapter references point to where the
term is developed, not merely mentioned.

**Agentic system.** A software system in which a model-driven planner selects and invokes tools,
so that the sequence of actions is determined at run time rather than fixed by program structure.
(Chapter 1.)

**Approval.** A record in which an accountable human accepts a specific action on a specific
subject revision, carrying eligible roles, denied actor types, required evidence, validity period,
and invalidation conditions. An approval is not a boolean flag and is not transferable between
revisions. (Chapter 9.)

**Approval-required.** A decision outcome distinct from allow and deny, meaning that the request
satisfies policy but may not proceed until a qualifying approval exists. (Chapters 7, 19.)

**Assurance claim.** A statement about what may reasonably be concluded from a system's controls
and evidence, within named assumptions and scope. Distinct from a decision, an observation, and an
evidence binding. (Chapter 3.)

**Assurance tier.** A classification of governance strength by enforcement independence and
evidence trust rather than by control count. Tier 1 is design-time governance; Tier 2 adds
cooperative in-process enforcement over declared surfaces; Tier 3 requires mandatory enforcement
and independent attestation outside the governed process. (Chapter 13.)

**Attempt.** One retry within an occurrence. Authorization allowances and lifecycle state are
attempt-scoped, so a retry cannot silently reuse an earlier authorization. (Chapters 12, 20.)

**Attribute-based access control (ABAC).** Authorization computed from subject, resource, action,
and environment attributes. Related to, but not sufficient for, agentic governance because it
addresses request authorization without evidence, approval semantics, or coverage claims.
(Chapter 4.)

**Authority.** The right of a source or actor to determine a class of decision. Scoped, never a
universal boolean: a source may be authoritative for one decision class and not another.
Distinguished from relevance and from technical reachability. (Chapters 5, 6.)

**Authorization service-provider interface (SPI).** *(Nornyx)* The public in-process interface
through which a consumer constructs an authorizer from a validated contract and lock and evaluates
requests. Version 1.2 at the audited revision. (Chapter 19.)

**Authorizer state.** *(Nornyx)* A frozen, detached view of the validated document, composition,
verified lock payload, and digests, exposed so that consumers need not re-read or re-compose the
source. (Chapter 19.)

**Bypass.** Execution of a governed action along a path the enforcement point does not observe.
For cooperative enforcement, calling the underlying function directly is a bypass and is an
architectural fact to be declared, not a defect to be hidden. (Chapter 14.)

**Canonicalization.** Mapping semantically equivalent inputs to one stable representation before
hashing, so that digests identify meaning rather than formatting. Must itself be versioned; a
change to canonicalization is a compatibility event. (Chapter 8.)

**Capability.** A declared bounded action surface available to an identity, with scope, risk
classification, delegability, and gate references. Possessing a capability does not imply that any
particular use of it is permitted. (Chapter 5.)

**Claim register.** A deliverable listing each external claim with its assurance tier, governed
surface, evidence producer, subject revision, and residual dependency. (Chapters 3, 39.)

**Confused deputy.** A component that misuses its own authority on behalf of a less privileged
caller. In agent systems the classic instance is a tool that acts with the agent's authority on
instructions carried in untrusted content. (Chapters 5, 6.)

**Contract.** *(Nornyx)* A `.nyx` document declaring project, contexts, policies, agents, skills,
harnesses, gates, evidence, approvals, and optional profile records. The authoritative source from
which control artifacts are generated. (Chapter 17.)

**Control drift.** Divergence between two representations of the same control — for example, a
generated policy artifact edited by hand so that it no longer matches its source. One of four
drift types, alongside policy, configuration, and framework-adapter drift. (Chapter 2.)

**Cooperative enforcement.** Enforcement that depends on the caller invoking the governed path.
Effective against mistakes and unaware code, ineffective against a caller that chooses another
path. Contrasted with authoritative or mandatory enforcement. (Chapters 10, 13.)

**Coverage inventory.** A machine-readable declaration classifying each framework surface as
wrapped, unsupported, or unwrapped. Part of an adapter's public interface, because a working
example otherwise reads as whole-framework governance. (Chapters 14, 25.)

**Decision.** The conclusion an evaluator reaches for one request. Establishes what the evaluator
concluded, not that the identity or context asserted in the request was authentic. (Chapter 3.)

**Delegation.** A grant of bounded authority from one identity to another, limited by capability,
scope, depth, and time. Distinct from handoff. (Chapter 5.)

**Determinism (of evaluation).** The property that the same contract and request yield the same
decision, without dependence on ambient state, wall-clock time, or mutable retained structures.
A prerequisite for testable governance. (Chapter 7.)

**Determinism (of generation).** The property that the same semantic input produces the same
output bytes, which is what makes drift detection meaningful rather than noisy. (Chapters 8, 21.)

**Diagnostic code.** A stable identifier for a validation or authorization failure, enabling
pipelines and tooling to gate on specific conditions rather than parse prose. *(Nornyx)* codes are
upper-snake-case strings grouped into families. (Chapter 21, Appendix C.)

**Digest.** A cryptographic hash used to bind content. Establishes that bytes have not changed
relative to a recorded value; establishes nothing about the truth, completeness, or producer of
those bytes. (Chapter 12.)

**Drift gate.** A check that fails when generated artifacts no longer match what the source would
produce, or when a committed baseline diverges from regeneration. (Chapters 21, 29.)

**Evidence.** A record or artifact supporting a bounded claim about a subject, bound to that
subject's revision and to a producer. Distinct from logs, which serve debugging, and from
telemetry, which serves operations. (Chapter 11.)

**Evidence binding.** The relationship between supplied bytes, their declared digests, and the
subject revision. Establishes correspondence, not that the bytes describe reality. (Chapter 3.)

**Exception (waiver).** A bounded, owned, time-limited record permitting a deviation from a
control, in place of silently deleting the rule. (Chapter 9.)

**Fail-closed.** Behavior in which a component that cannot evaluate, verify, or record denies the
action. Contrasted with fail-open, in which the action proceeds when governance is unavailable.
(Chapter 10.)

**Framework-adapter drift.** Divergence between the surfaces a framework exposes and the surfaces
an adapter wraps, typically introduced by a framework upgrade. (Chapters 2, 25.)

**Gate.** A decision boundary combining policy evaluation, evidence requirements, and optionally
human approval, kept separable so that a failure identifies which requirement was unmet.
(Chapters 5, 9.)

**Governance as code.** The practice of expressing organizational governance — authority,
approval, evidence obligations, and their composition — in versioned, checkable artifacts.
Broader than policy as code, which addresses authorization rules alone. (Chapter 4.)

**Governance debt.** The accumulated cost of maintaining multiple uncoordinated representations of
the same governance intent. Behaves like technical debt. (Chapter 2.)

**Governed agentic system.** An agentic system whose actions are constrained by an explicit,
versioned model of identity, capability, policy, enforcement, evidence, and human accountability.
(Chapters 1, 4.)

**Handoff.** Transfer of work or responsibility to an actor that must already hold, or validly
receive, the required capability. Treating handoff as an implicit grant creates an
authority-escalation path. (Chapter 5.)

**Identity (governance).** A stable declared subject with namespace, status, validity, framework
bindings, and revocation state, independent of any framework's object identity or display name.
(Chapter 5.)

**Lock.** A content-addressed structure binding a contract digest, subject revision, composition
identities, schema set, record digests, evidence schema selection, and generated artifact hashes
into one named candidate. Binds bytes, not producers. (Chapters 12, 18.)

**Maker–checker.** A separation of duties in which the party proposing a change may not approve
it. (Chapters 9, 30.)

**Mission.** The complete governed run within which operations, occurrences, and attempts are
identified. (Chapters 12, 20.)

**Membership.** The record authorizing an identity and a capability set within a particular trust
zone; identity alone does not imply universal access. (Chapter 6.)

**Model Context Protocol (MCP).** A protocol for exposing tools and resources to model clients.
In this book, treated both as a governed subject (packages as untrusted inert input) and as a
potential publication surface. (Chapter 27.)

**Non-goal.** A capability a system explicitly declines to provide. Part of the security
architecture, because undeclared non-goals become false assumptions. (Chapter 16.)

**Occurrence.** One scheduled visit to a stable governed operation — a loop iteration, a parallel
branch, or a fresh invocation — within which attempts are counted. (Chapters 12, 20.)

**Operation.** The stable governed surface being invoked, identified independently of how many
times it is visited. (Chapters 12, 20.)

**Policy as code.** The practice of expressing authorization rules in a versioned, testable
language evaluated by an engine rather than interpreted by people. (Chapter 4.)

**Policy decision point (PDP).** The component that evaluates whether a request is permitted.
(Chapters 4, 10.)

**Policy enforcement point (PEP).** The component that controls whether the action actually
proceeds. Separating it from the decision point is what makes both auditable. (Chapters 4, 10.)

**Profile.** *(Nornyx)* A packaged set of domain-specific governance declarations that composes
into a contract's effective governance with recorded provenance. (Chapter 18.)

**Proof boundary.** The explicit statement of what a validation establishes and what it leaves
open — in particular, that validating supplied evidence proves conformance of the supplied
records, not that the recorded events occurred. (Chapters 3, 20.)

**Provenance.** The traceability of each effective rule or artifact to the source that contributed
it. (Chapter 8.)

**Replay fingerprint.** A semantic identifier for an event that excludes transport-restamped
fields such as identifiers, sequence numbers, and timestamps, and includes substantive fields and
occurrence identity, so that restamping cannot manufacture a new event. (Chapters 12, 20.)

**Revision binding.** Association of a decision, approval, or evidence item with an immutable
subject version, so that a change to the subject invalidates the association. (Chapters 9, 12.)

**Runtime evidence.** Records emitted during execution describing decisions and observations,
supplied by a producer and validated for conformance against a contract, lock, and revision.
(Chapters 11, 20.)

**Separation of duties.** A control ensuring that no single actor holds a combination of
capabilities that would allow unilateral completion of a sensitive action. (Chapters 9, 31.)

**Supplied evidence.** Evidence provided by a producer rather than independently observed by the
validator. The distinction determines what any conclusion drawn from it may claim. (Chapter 11.)

**Taint.** A classification marking content as untrusted or externally controlled, travelling with
the context so that downstream decisions can refuse to let it define policy. (Chapter 6.)

**Trust zone.** A declared boundary governing membership, transitions, sharing allowances, and
never-share categories. Not necessarily a network segment. (Chapter 6.)

**Unwrapped surface.** A surface an adapter deliberately does not govern because it belongs to the
caller — distinct from an unsupported surface, which the adapter could govern but does not yet.
(Chapter 25.)

**Wrapped surface.** A framework surface for which an adapter claims governance and for which the
corresponding allow, deny, failure, bypass, and evidence tests exist. (Chapters 14, 25.)
