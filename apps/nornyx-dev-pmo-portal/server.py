from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from nornyx.kpi_metrics import collect_repo_kpis, score_evidence_dir  # noqa: E402

DEFAULT_HOST = os.getenv("NORNYX_PMO_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("NORNYX_PMO_PORT", "5174"))
GIT_TIMEOUT_SECONDS = float(os.getenv("NORNYX_PMO_GIT_TIMEOUT_SECONDS", "4"))

FAVICON_SVG = b"""<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 64 64\"><title>Nornyx</title><rect width=\"64\" height=\"64\" rx=\"14\" fill=\"#101827\"/><path d=\"M18 43V17h7l14 17V17h7v26h-7L25 26v17z\" fill=\"#e7f0ff\"/><circle cx=\"47\" cy=\"18\" r=\"5\" fill=\"#7dd3fc\"/></svg>"""


def favicon_bytes() -> bytes:
    return FAVICON_SVG



def compact_sha(value: str, length: int = 8) -> str:
    return value[:length] if value else ""


def normalize_github_web_url(remote_url: str) -> str:
    """Normalize common GitHub remote URLs to a browser URL."""
    remote_url = (remote_url or "").strip()
    if not remote_url:
        return ""

    if remote_url.startswith("git@github.com:"):
        path = remote_url.removeprefix("git@github.com:")
        return "https://github.com/" + path.removesuffix(".git")

    if remote_url.startswith("https://github.com/"):
        return remote_url.removesuffix(".git")

    if remote_url.startswith("http://github.com/"):
        return "https://github.com/" + remote_url.removeprefix("http://github.com/").removesuffix(".git")

    return remote_url.removesuffix(".git")


def count_worktree_changes(porcelain: str) -> dict[str, Any]:
    """Count a `git status --porcelain=v1` response."""
    modified = staged = untracked = 0
    for line in porcelain.splitlines():
        if not line.strip():
            continue
        if line.startswith("??"):
            untracked += 1
            continue
        index_status = line[0] if len(line) > 0 else " "
        worktree_status = line[1] if len(line) > 1 else " "
        if index_status != " ":
            staged += 1
        if worktree_status != " ":
            modified += 1

    total = modified + staged + untracked
    return {
        "dirty": total > 0,
        "modified_count": modified,
        "staged_count": staged,
        "untracked_count": untracked,
        "total_changed": total,
    }


def remote_status_from_counts(local_sha: str, remote_sha: str, ahead: int, behind: int) -> str:
    if ahead > 0 and behind > 0:
        return "diverged"
    if ahead > 0:
        return "local_ahead"
    if behind > 0:
        return "local_behind"
    if local_sha and remote_sha and compact_sha(local_sha) == compact_sha(remote_sha):
        return "up_to_date"
    if remote_sha and local_sha and compact_sha(local_sha) != compact_sha(remote_sha):
        return "different_head"
    return "unknown"


def run_git(args: list[str], *, timeout: float = GIT_TIMEOUT_SECONDS) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def git_text(args: list[str], *, timeout: float = GIT_TIMEOUT_SECONDS) -> str:
    result = run_git(args, timeout=timeout)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def collect_local_git_status() -> dict[str, Any]:
    branch = git_text(["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
    commit = git_text(["rev-parse", "--short", "HEAD"]) or "unknown"
    upstream = git_text(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]) or ""
    porcelain = git_text(["status", "--porcelain=v1"])
    changed = [line for line in porcelain.splitlines() if line.strip()]
    change_counts = count_worktree_changes(porcelain)
    ahead = behind = 0

    if upstream:
        counts = git_text(["rev-list", "--left-right", "--count", f"{upstream}...HEAD"])
        if counts:
            parts = counts.split()
            if len(parts) == 2:
                behind = int(parts[0])
                ahead = int(parts[1])

    remote_url = git_text(["config", "--get", "remote.origin.url"])
    github_web_url = normalize_github_web_url(remote_url)
    short_sha = compact_sha(commit)
    return {
        "branch": branch,
        "commit": commit,
        "short_sha": short_sha,
        "commit_url": f"{github_web_url}/commit/{commit}" if github_web_url and commit != "unknown" else "",
        "commit_message": git_text(["log", "-1", "--pretty=%s"]) or "",
        "upstream": upstream,
        "remote_url": remote_url,
        "github_web_url": github_web_url,
        "changed_count": len(changed),
        "changed_files": changed[:20],
        "ahead": ahead,
        "behind": behind,
        "clean": len(changed) == 0,
        "dirty": change_counts["dirty"],
        "modified_count": change_counts["modified_count"],
        "staged_count": change_counts["staged_count"],
        "untracked_count": change_counts["untracked_count"],
        "total_changed": change_counts["total_changed"],
        "worktree": change_counts,
        "remote_status": remote_status_from_counts(commit, "", ahead, behind),
    }


def collect_remote_git_status() -> dict[str, Any]:
    remote_url = git_text(["config", "--get", "remote.origin.url"])
    branch = git_text(["rev-parse", "--abbrev-ref", "HEAD"]) or "HEAD"
    if not remote_url:
        return {
            "enabled": True,
            "checked": False,
            "available": False,
            "status": "not_configured",
            "error": "No remote.origin.url configured.",
            "reason": "No remote.origin.url configured.",
        }

    result = run_git(["ls-remote", "--heads", "origin", branch])
    if result.returncode != 0:
        return {
            "enabled": True,
            "checked": True,
            "available": False,
            "remote": "origin",
            "branch": branch,
            "status": "unavailable",
            "short_sha": "",
            "error": (result.stderr or result.stdout or "git ls-remote failed").strip(),
            "reason": (result.stderr or result.stdout or "git ls-remote failed").strip(),
        }

    remote_sha = ""
    for line in result.stdout.splitlines():
        if line.strip():
            remote_sha = line.split()[0][:12]
            break

    local_sha = git_text(["rev-parse", "--short=12", "HEAD"])
    matches = bool(remote_sha and local_sha and remote_sha.startswith(local_sha))
    return {
        "enabled": True,
        "checked": True,
        "available": bool(remote_sha),
        "remote": "origin",
        "branch": branch,
        "remote_commit": remote_sha or "not-found",
        "short_sha": compact_sha(remote_sha),
        "local_commit": local_sha or "unknown",
        "matches_local_head": matches,
        "status": "up_to_date" if matches else "different_head",
    }


def load_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def goal_packet_metadata(path: Path) -> dict[str, Any]:
    """Read lightweight metadata for a goal packet without changing PMO status."""
    title = path.stem.replace("-", " ").title()
    goal_id = ""
    phase = "future"
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("# ") and not goal_id:
                title = stripped.removeprefix("# ").strip()
                parts = title.split(":", 1)[0].split("—", 1)[0].strip().split()
                goal_id = parts[0] if parts and parts[0].upper().startswith("GOAL-") else ""
            elif stripped.lower() == "## phase":
                phase = "pending"
            elif phase == "pending" and stripped:
                phase = stripped
                break
    except OSError:
        pass
    return {
        "id": goal_id or path.stem,
        "title": title,
        "phase": phase if phase != "pending" else "future",
        "name": path.name,
        "path": str(path.relative_to(ROOT)),
    }


def collect_pmo_status() -> dict[str, Any]:
    status = load_json_file(ROOT / "docs" / "pmo" / "status" / "current_status.json", {})
    if not status:
        status = load_json_file(ROOT / "docs" / "pmo" / "status" / "current_status.example.json", {})

    goals_root = ROOT / "docs" / "goals"
    goals = []
    if goals_root.exists():
        for path in sorted(goals_root.glob("*.md")):
            goals.append(goal_packet_metadata(path))

    return {
        "project": status.get("project", "Nornyx"),
        "source_of_truth": status.get("source_of_truth", {}),
        "summary": status.get("summary", {}),
        "blocks": status.get("blocks", []),
        "goals": goals[:80],
        "vision_map": status.get("vision_map", {}),
    }


def collect_portal_kpis() -> dict[str, Any]:
    """Collect read-only local KPIs for the portal visibility panel."""
    repo_kpis = collect_repo_kpis(ROOT)
    evidence_score = score_evidence_dir(ROOT / "docs" / "qa" / "evidence" / "GOAL-029")
    return {
        "schema_version": "1.0",
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo_kpis": repo_kpis,
        "current_goal_evidence": evidence_score,
        "safety": {
            "mode": "read_only_local_metrics",
            "writes": "disabled",
            "network": "disabled",
            "shell_execution": "disabled",
        },
    }


def vision_map() -> dict[str, Any]:
    return {
        "north_star": "Nornyx becomes the executable contract layer for human-model software delivery.",
        "lanes": [
            {
                "name": "Language Core",
                "items": ["core block spec", "parser/checker", "formatter", "IR"],
            },
            {
                "name": "Agentic Engineering",
                "items": ["context", "agents", "policy", "harness", "evals", "evidence"],
            },
            {
                "name": "Governance",
                "items": ["delivery state", "handover", "decision boundaries", "evidence quality"],
            },
            {
                "name": "Developer Experience",
                "items": ["CLI", "authoring assistant", "portal", "renderers", "examples"],
            },
            {
                "name": "Evergreen Future",
                "items": ["extensions", "patterns", "compatibility", "triage", "profiles"],
            },
        ],
    }


class NornyxPMOHandler(SimpleHTTPRequestHandler):
    enable_api = False
    enable_git_api = False
    enable_remote_git = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(APP_ROOT), **kwargs)

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _favicon(self) -> None:
        body = favicon_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if path in {"/favicon.ico", "/favicon.svg"}:
            self._favicon()
            return

        if path == "/api/dev/pmo/status":
            if not self.enable_api:
                self._json(403, {"error": "PMO API disabled. Start with --enable-api."})
                return
            self._json(200, collect_pmo_status())
            return

        if path == "/api/dev/git/status":
            if not self.enable_git_api:
                self._json(403, {"error": "Git API disabled. Start with --enable-git-api."})
                return

            payload: dict[str, Any] = {"local": collect_local_git_status()}
            if self.enable_remote_git:
                payload["remote"] = collect_remote_git_status()
            else:
                payload["remote"] = {
                    "enabled": False,
                    "checked": False,
                    "status": "disabled",
                    "reason": "Start with --enable-remote-git.",
                }
            payload["checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            payload["safety"] = {
                "mode": "read_only_git_status",
                "writes": "disabled",
                "shell_execution": "disabled",
                "github_token": "not_used",
            }
            self._json(200, payload)
            return

        if path == "/api/dev/kpi/status":
            if not self.enable_api:
                self._json(403, {"error": "PMO API disabled. Start with --enable-api."})
                return
            self._json(200, collect_portal_kpis())
            return

        if path == "/api/dev/vision-map":
            if not self.enable_api:
                self._json(403, {"error": "PMO API disabled. Start with --enable-api."})
                return
            self._json(200, vision_map())
            return

        super().do_GET()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local Nornyx Developer PMO Portal.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    parser.add_argument("--enable-api", action="store_true")
    parser.add_argument("--enable-git-api", action="store_true")
    parser.add_argument("--enable-remote-git", action="store_true")
    parser.add_argument("--enable-all", action="store_true")
    args = parser.parse_args()

    if args.enable_all:
        args.enable_api = True
        args.enable_git_api = True
        args.enable_remote_git = True

    NornyxPMOHandler.enable_api = args.enable_api
    NornyxPMOHandler.enable_git_api = args.enable_git_api
    NornyxPMOHandler.enable_remote_git = args.enable_remote_git

    server = ThreadingHTTPServer((args.host, args.port), NornyxPMOHandler)
    print(f"Nornyx Developer PMO Portal: http://{args.host}:{args.port}")
    print(f"API: {'enabled' if args.enable_api else 'disabled'}")
    print(f"Git API: {'enabled' if args.enable_git_api else 'disabled'}")
    print(f"Remote Git: {'enabled' if args.enable_remote_git else 'disabled'}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
