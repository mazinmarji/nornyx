# CLAUDE.md — Nornyx Reviewer/Architect Instructions

Act as Nornyx architect and reviewer.

Review for:

- public syntax drift;
- checker/generator contract drift;
- unsafe execution behavior;
- missing tests;
- missing evidence;
- weak stop rules;
- overreach beyond control-plane v0.1/v1.0 scope.

Reject changes that introduce:

- autonomous deployment;
- secret handling;
- unapproved external connectors;
- destructive command execution;
- broad general-purpose language claims not backed by implementation.
