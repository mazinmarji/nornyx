#!/usr/bin/env python3
"""
Update Developer PMO Portal status from GitHub Actions context.

This script keeps docs/pmo/status/current_status.json current enough for a
developer-only PMO portal.

Properties:
- CI-safe.
- No secrets are written.
- No shell execution.
- No direct GitHub API dependency.
- Uses GitHub event JSON and environment variables already supplied by Actions.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


STATUS_PATH = Path(os.environ.get("DEV_PMO_STATUS_PATH", "docs/pmo/status/current_status.json"))


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_github_event() -> Dict[str, Any]:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        return {}
    path = Path(event_path)
    if not path.exists():
        return {}
    return read_json(path, {})


def ensure_shape(data: Dict[str, Any]) -> Dict[str, Any]:
    data.setdefault("project", "Developer PMO Portal")
    data.setdefault("status", "active")
    data.setdefault("updated_at", None)
    data.setdefault("source_of_truth", {})
    data.setdefault("github_status", {})
    data.setdefault("vision_map", {})
    data.setdefault("goals", [])
    data.setdefault("risks", [])
    data.setdefault("evidence", [])
    data.setdefault("next_actions", [])

    source = data["source_of_truth"]
    source.setdefault("type", "github_repo")
    source.setdefault("repo", "")
    source.setdefault("branch", "main")
    source.setdefault("commit_sha", "")
    source.setdefault("status_sync", "enabled")
    source.setdefault("last_event", None)

    github = data["github_status"]
    github.setdefault("overall", "unknown")
    github.setdefault("delivery_stage", "repo_observed")
    github.setdefault("last_commit", {})
    github.setdefault("pull_request", {})
    github.setdefault("checks", {})
    github.setdefault("timeline", [])

    github["last_commit"].setdefault("sha", "")
    github["last_commit"].setdefault("message", "")
    github["last_commit"].setdefault("author", "")
    github["last_commit"].setdefault("committed_at", "")
    github["last_commit"].setdefault("url", "")

    github["pull_request"].setdefault("number", None)
    github["pull_request"].setdefault("title", "")
    github["pull_request"].setdefault("state", "none")
    github["pull_request"].setdefault("draft", False)
    github["pull_request"].setdefault("merged", False)
    github["pull_request"].setdefault("url", "")

    github["checks"].setdefault("state", "unknown")
    github["checks"].setdefault("summary", "")
    github["checks"].setdefault("workflow", "")
    github["checks"].setdefault("run_id", "")
    github["checks"].setdefault("url", "")

    vision = data["vision_map"]
    vision.setdefault("refresh_policy", {})
    vision["refresh_policy"].setdefault("portal_poll_seconds", 20)
    vision.setdefault("priority_order", [])
    vision.setdefault("maps", [])

    return data


def append_timeline(data: Dict[str, Any], item: Dict[str, Any]) -> None:
    timeline: List[Dict[str, Any]] = data["github_status"].setdefault("timeline", [])
    timeline.insert(0, {"at": utc_now(), **item})
    data["github_status"]["timeline"] = timeline[:50]


def github_url(repo: str, sha: str = "", run_id: str = "") -> str:
    if not repo:
        return ""
    if run_id:
        return f"https://github.com/{repo}/actions/runs/{run_id}"
    if sha:
        return f"https://github.com/{repo}/commit/{sha}"
    return f"https://github.com/{repo}"


def update_from_push(data: Dict[str, Any], event: Dict[str, Any]) -> None:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    sha = os.environ.get("GITHUB_SHA", "")
    branch = os.environ.get("GITHUB_REF_NAME", "")

    head_commit = event.get("head_commit") or {}
    author = head_commit.get("author") or {}

    data["source_of_truth"].update(
        {
            "repo": repo,
            "branch": branch,
            "commit_sha": sha,
            "last_event": "push",
        }
    )

    data["github_status"]["last_commit"].update(
        {
            "sha": sha,
            "message": head_commit.get("message", ""),
            "author": author.get("name", ""),
            "committed_at": head_commit.get("timestamp", ""),
            "url": github_url(repo, sha=sha),
        }
    )
    data["github_status"]["overall"] = "committed"
    data["github_status"]["delivery_stage"] = "committed"

    append_timeline(
        data,
        {
            "kind": "commit",
            "status": "committed",
            "label": "Commit observed",
            "summary": head_commit.get("message", "")[:220],
            "url": github_url(repo, sha=sha),
        },
    )


def update_from_pull_request(data: Dict[str, Any], event: Dict[str, Any]) -> None:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    action = event.get("action", "")
    pr = event.get("pull_request") or {}
    merged = bool(pr.get("merged"))
    state = pr.get("state") or "unknown"

    if merged:
        delivery_stage = "merged"
        overall = "merged"
    elif state == "open":
        delivery_stage = "pr_open"
        overall = "pr_open"
    else:
        delivery_stage = f"pr_{state}"
        overall = delivery_stage

    data["source_of_truth"].update(
        {
            "repo": repo,
            "branch": os.environ.get("GITHUB_REF_NAME", ""),
            "commit_sha": os.environ.get("GITHUB_SHA", ""),
            "last_event": f"pull_request.{action}",
        }
    )

    data["github_status"]["pull_request"].update(
        {
            "number": pr.get("number"),
            "title": pr.get("title", ""),
            "state": state,
            "draft": bool(pr.get("draft")),
            "merged": merged,
            "url": pr.get("html_url", ""),
        }
    )
    data["github_status"]["overall"] = overall
    data["github_status"]["delivery_stage"] = delivery_stage

    append_timeline(
        data,
        {
            "kind": "pull_request",
            "status": delivery_stage,
            "label": f"PR {action}",
            "summary": pr.get("title", ""),
            "url": pr.get("html_url", ""),
        },
    )


def update_from_workflow_run(data: Dict[str, Any], event: Dict[str, Any]) -> None:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    workflow = event.get("workflow_run") or {}
    conclusion = workflow.get("conclusion") or "unknown"
    status = workflow.get("status") or "unknown"
    run_id = str(workflow.get("id") or os.environ.get("GITHUB_RUN_ID", ""))

    if status != "completed":
        checks_state = "running"
        overall = "checks_running"
    elif conclusion == "success":
        checks_state = "passed"
        overall = "checks_passed"
    elif conclusion in {"failure", "timed_out", "cancelled", "startup_failure"}:
        checks_state = "failed"
        overall = "checks_failed"
    else:
        checks_state = conclusion
        overall = f"checks_{conclusion}"

    data["source_of_truth"].update(
        {
            "repo": repo,
            "branch": workflow.get("head_branch") or os.environ.get("GITHUB_REF_NAME", ""),
            "commit_sha": workflow.get("head_sha") or os.environ.get("GITHUB_SHA", ""),
            "last_event": "workflow_run.completed",
        }
    )

    data["github_status"]["checks"].update(
        {
            "state": checks_state,
            "summary": f"{workflow.get('name', 'Workflow')} {checks_state}",
            "workflow": workflow.get("name", ""),
            "run_id": run_id,
            "url": workflow.get("html_url") or github_url(repo, run_id=run_id),
        }
    )
    data["github_status"]["overall"] = overall
    data["github_status"]["delivery_stage"] = overall

    append_timeline(
        data,
        {
            "kind": "checks",
            "status": checks_state,
            "label": "Workflow completed",
            "summary": f"{workflow.get('name', 'Workflow')} => {checks_state}",
            "url": workflow.get("html_url") or github_url(repo, run_id=run_id),
        },
    )


def update_vision_map_from_status(data: Dict[str, Any]) -> None:
    """Keep visible vision-map nodes synchronized with live GitHub status."""
    stage = data.get("github_status", {}).get("delivery_stage", "repo_observed")
    checks_state = data.get("github_status", {}).get("checks", {}).get("state", "unknown")

    maps = data.setdefault("vision_map", {}).setdefault("maps", [])
    for map_item in maps:
        if map_item.get("id") != "github-delivery-flow":
            continue

        for node in map_item.setdefault("nodes", []):
            node_id = node.get("id")
            if node_id == "committed":
                node["status"] = "done" if stage in {
                    "committed", "pr_open", "checks_running", "checks_passed",
                    "checks_failed", "merged"
                } else "observed"
            elif node_id == "pr-opened":
                node["status"] = "done" if stage in {
                    "pr_open", "checks_running", "checks_passed", "checks_failed", "merged"
                } else "pending"
            elif node_id == "checks":
                if stage == "checks_failed" or checks_state == "failed":
                    node["status"] = "blocked"
                elif stage == "checks_passed" or checks_state == "passed":
                    node["status"] = "done"
                elif stage == "checks_running":
                    node["status"] = "active"
                else:
                    node["status"] = "pending"
            elif node_id == "merged":
                node["status"] = "done" if stage == "merged" else "pending"
            elif node_id == "pmo-synced":
                node["status"] = "done"


def main() -> None:
    data = ensure_shape(read_json(STATUS_PATH, {}))
    event = load_github_event()
    event_name = os.environ.get("GITHUB_EVENT_NAME", "manual")

    if event_name == "push":
        update_from_push(data, event)
    elif event_name == "pull_request":
        update_from_pull_request(data, event)
    elif event_name == "workflow_run":
        update_from_workflow_run(data, event)
    else:
        data["source_of_truth"]["last_event"] = event_name
        append_timeline(
            data,
            {
                "kind": "pmo_status",
                "status": "synced",
                "label": "PMO status synced",
                "summary": f"Manual or scheduled sync from event: {event_name}",
                "url": github_url(os.environ.get("GITHUB_REPOSITORY", "")),
            },
        )

    update_vision_map_from_status(data)
    data["updated_at"] = utc_now()
    write_json(STATUS_PATH, data)


if __name__ == "__main__":
    main()
