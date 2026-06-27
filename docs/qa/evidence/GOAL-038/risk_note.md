# GOAL-038 Risk Note

Risk is medium-low. The change hardens domain-profile metadata, but does not
add runtime behavior.

Mitigations:

- every profile remains `optional_profile`;
- profile-only domain terms stay out of the mandatory core concept list;
- compatibility matrix separates compatible, review-gated, and conflicting
  profile pairings;
- conformance metadata includes migration guidance and v1 readiness decisions;
- generated starter documents pass `nornyx check` cleanly;
- safety non-goals remain shared across all domain profiles.

Approval is required before profile packs are treated as stable release gates.
