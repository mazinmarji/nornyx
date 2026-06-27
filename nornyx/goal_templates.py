"""Goal and handoff templates for Nornyx development."""
from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path


_SAFE_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class GoalPacket:
    goal_id: str
    title: str
    slug: str
    goal_path: Path
    evidence_path: Path
    content: str
    evidence_content: str


def slugify(value: str) -> str:
    slug = _SAFE_SLUG_RE.sub("-", value.lower()).strip("-")
    return slug or "goal"


def make_goal_packet(goal_id: str, title: str, repo_root: Path | None = None) -> GoalPacket:
    repo = repo_root or Path(".")
    slug = slugify(title)
    goal_path = repo / "docs" / "goals" / f"{goal_id.lower()}-{slug}.md"
    evidence_path = repo / "docs" / "qa" / "evidence" / goal_id.upper() / "README.md"

    content = f"""# {goal_id.upper()} — {title}

## Goal

Define the exact delivery target.

## Scope

Add only the source, docs, tests, and evidence needed for this goal.

## Non-goals

Document what must not be changed.

## Context to load

```text
docs/
examples/
tests/
nornyx/
```

## Validation

```text
python -m pytest -q
python scripts/dev/audit_pmo_status.py
```

## Evidence

```text
{evidence_path.as_posix()}
```

## Done definition

```text
implementation complete
tests pass
PMO status updated
evidence recorded
human approval ready
```
"""

    evidence_content = f"""# {goal_id.upper()} Evidence — {title}

## Summary

Evidence for {goal_id.upper()}.

## Validation

Record local validation results here.

## Risks

Record known risks and mitigations here.

## Decision

Pending human review.
"""

    return GoalPacket(
        goal_id=goal_id.upper(),
        title=title,
        slug=slug,
        goal_path=goal_path,
        evidence_path=evidence_path,
        content=content,
        evidence_content=evidence_content,
    )


def render_handoff(project: str, status_summary: str, next_goal: str) -> str:
    return f"""# Handoff — {project}

## Current status

```text
{status_summary}
```

## Next goal

```text
{next_goal}
```

## Handoff note

Continue with the next governed goal. Keep scope small, evidence-backed, and safe by default.
"""
