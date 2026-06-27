"""Read-only delivery-state renderers for Nornyx.

These helpers render an already-produced delivery-state/PMO-status document
into shell, Markdown, or compact JSON text. They do not execute work.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


@dataclass(frozen=True)
class DeliveryBlock:
    id: str
    title: str
    status: str
    completion_pct: int
    completed_count: int
    pending_count: int
    evidence_count: int
    next_goal: str


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_blocks(status_doc: dict[str, Any]) -> list[DeliveryBlock]:
    blocks: list[DeliveryBlock] = []
    for raw in _as_list(status_doc.get("blocks")):
        if not isinstance(raw, dict):
            continue
        blocks.append(
            DeliveryBlock(
                id=str(raw.get("id", "")),
                title=str(raw.get("title", raw.get("id", "Untitled"))),
                status=str(raw.get("status", "unknown")),
                completion_pct=int(raw.get("completion_pct", 0) or 0),
                completed_count=len(_as_list(raw.get("completed"))),
                pending_count=len(_as_list(raw.get("pending"))),
                evidence_count=len(_as_list(raw.get("evidence"))),
                next_goal=str(raw.get("next_goal", "Not defined")),
            )
        )
    return blocks


def render_shell(status_doc: dict[str, Any]) -> str:
    project = str(status_doc.get("project", "Nornyx"))
    summary = status_doc.get("summary") if isinstance(status_doc.get("summary"), dict) else {}
    overall = str(summary.get("overall_status", "unknown"))
    next_goal = str(summary.get("next_recommended_goal", "Not defined"))

    lines = [
        f"{project} — {overall}",
        f"Next: {next_goal}",
        "",
    ]

    for block in normalize_blocks(status_doc):
        lines.extend(
            [
                block.title,
                f"  status: {block.status}",
                f"  completion: {block.completion_pct}%",
                f"  completed: {block.completed_count}",
                f"  pending: {block.pending_count}",
                f"  evidence: {block.evidence_count}",
                f"  next: {block.next_goal}",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def render_markdown(status_doc: dict[str, Any]) -> str:
    project = str(status_doc.get("project", "Nornyx"))
    summary = status_doc.get("summary") if isinstance(status_doc.get("summary"), dict) else {}
    overall = str(summary.get("overall_status", "unknown"))
    next_goal = str(summary.get("next_recommended_goal", "Not defined"))

    lines = [
        f"# {project} Delivery State",
        "",
        f"- **Overall status:** {overall}",
        f"- **Next recommended goal:** {next_goal}",
        "",
        "| Block | Status | Completion | Completed | Pending | Evidence | Next |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]

    for block in normalize_blocks(status_doc):
        lines.append(
            f"| {block.title} | {block.status} | {block.completion_pct}% | "
            f"{block.completed_count} | {block.pending_count} | {block.evidence_count} | {block.next_goal} |"
        )

    return "\n".join(lines).rstrip() + "\n"


def render_json(status_doc: dict[str, Any], *, compact: bool = False) -> str:
    normalized = {
        "project": status_doc.get("project", "Nornyx"),
        "summary": status_doc.get("summary", {}),
        "blocks": [block.__dict__ for block in normalize_blocks(status_doc)],
    }
    if compact:
        return json.dumps(normalized, separators=(",", ":"), ensure_ascii=False) + "\n"
    return json.dumps(normalized, indent=2, ensure_ascii=False) + "\n"


def render_delivery_state(status_doc: dict[str, Any], output_format: str) -> str:
    if output_format == "shell":
        return render_shell(status_doc)
    if output_format == "markdown":
        return render_markdown(status_doc)
    if output_format == "json":
        return render_json(status_doc)
    if output_format == "json-compact":
        return render_json(status_doc, compact=True)
    raise ValueError(f"Unsupported delivery-state format: {output_format}")
