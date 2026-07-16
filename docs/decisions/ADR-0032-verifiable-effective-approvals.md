# ADR-0032 - Verifiable Effective Approvals

## Status

Accepted for the PR #30 remediation candidate. Final release authorization is
not implied.

## Context

Approval composition previously emitted a normalized-approval claim whose
retained source was only a list of paths. That representation could not be
re-normalized and therefore could not prove how intersected eligibility,
unioned requirements, intrinsic denials, or scalar conflicts produced the
reported result. Adding more fields to the public v1 serializer would also
break existing 1.x consumers.

## Decision

Nornyx uses three explicit representations:

- `nornyx.normalized_approval.v1` is the legacy public compatibility view;
- `nornyx.normalized_approval.v2` is a bounded retained-source representation
  with a deterministic source-consistency binding and a fallback identity
  derived only from source shape and canonical source path;
- `nornyx.effective_approval.v1` is the composed representation.

`NormalizedApproval.to_dict()` and `CompositionResult.to_dict()` always retain
their base-compatible v1 shapes. Callers select the new representations
explicitly with `to_verifiable_dict()` and `to_effective_dict()`; the latter is
schema-bound as `nornyx.effective_governance.v2`.

Every effective approval embeds at most 32 flattened v2 leaves. Each leaf has
its canonical hash and pack provenance: pack identity, kind, version, tier,
pack path, approval element path, element index, and pack content hash. The
effective record declares the composition operation and decisions. Eligible
roles are the intersection of all non-empty restrictions; empty layers never
erase an existing restriction. Required roles, denials, evidence, actions,
and invalidation conditions use deterministic ordered union. Disjoint
non-empty eligibility, an excluded required role, contradictory denials, or
conflicting scalar fields fails composition.

`trusted_effective_approval` schema-validates and bounds the envelope,
revalidates every leaf, authenticates its exact pack/id/kind/version/tier/path,
content hash, approval index, and raw approval, replays the same pure
composition function, and compares the complete result. Built-in provenance
is resolved only from the packaged catalog. Project, organization, and
explicit-path provenance requires an independently established registry from
the caller. Single-source and multi-source approvals use the same
representation.

The v2 source hash is a consistency binding, not a signature. Normalized v2
callers that know the source location pass expected source context to
`trusted_normalized_approval`. Effective approval authenticity comes from the
packaged catalog or the explicit registry supplied to the effective verifier.
An organization registry does not itself prove lock use; lock-aware callers
must retain the existing lock verification/composition boundary. Effective
reporting artifacts are not accepted as document-authored approvals or rule
inputs without registry context.

## Consequences

Effective governance output no longer presents composed data as a raw
normalized approval. Tampering with a retained leaf, source hash, order,
recipe, provenance, or final field fails verification. The bounded flattened
form prevents recursive source amplification. Legacy constructors and their
v1 serializer remain available; current governance reporting uses the
versioned effective representation.
