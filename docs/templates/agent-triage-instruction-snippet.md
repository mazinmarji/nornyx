# Agent Instruction Snippet — Requirement Discovery

Use this in AGENTS.md, CLAUDE.md, Codex task prompts, or role packets.

```text
If you discover a new Nornyx requirement, gap, missing concept, or future idea while implementing the assigned goal:

1. Do not expand scope automatically.
2. If it blocks the assigned goal, stop and record a triage candidate.
3. If it does not block the assigned goal, record a triage candidate and continue.
4. Save candidates under docs/backlog/triage-candidates/.
5. Include a stable concept key and use classification: core_now, near_core_candidate, extension_backlog, profile_specific, outside_nornyx, or rejected.
6. If the concept already exists in the Requirement Triage Matrix, match that classification.
7. Run python scripts/dev/check_triage_candidates.py before handoff.
8. Do not implement the candidate unless it is explicitly approved or part of the assigned goal.
```
