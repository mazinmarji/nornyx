# AGENTS.md — Nornyx Repository

This repository is the released Nornyx project. Current documentation
authority and public positioning are defined in `docs/README.md` and
`docs/48_NORNYX_POSITIONING.md`.

## Role guidance

### Architect Agent
- Keep Nornyx positioned as a vendor-neutral governance contract language for
  AI software delivery. Treat control-plane, compiler, and generator
  terminology as implementation mechanisms, not the primary product identity.
- Do not expand Nornyx into a general-purpose language runtime; execution and
  enforcement remain external.
- Preserve the staged roadmap.

### Builder Agent
- Implement small, scoped patches.
- Run `pytest` before completion.
- Run `nornyx check examples/governed_delivery_control_plane.nyx` after language/checker changes.
- Avoid arbitrary command execution features unless guarded by explicit capability design.

### Reviewer Agent
- Check that changes preserve safety boundaries.
- Check generated artifact compatibility.
- Reject changes that weaken policy, evidence, or approval semantics.

### Security Agent
- Treat context poisoning, prompt injection, tool misuse, dependency risk, and self-modification as first-class threats.
- Do not allow untrusted context to define policy or permissions.

## Output contract for AI-assisted patches

Every meaningful patch should include:

- changed files list;
- test result;
- risk note;
- evidence note;
- whether approval is required.
