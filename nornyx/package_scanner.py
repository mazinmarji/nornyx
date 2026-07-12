from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
from typing import Any

import yaml

from . import __version__


SCANNER_NAME = "nornyx-deterministic-package-scanner"
SCANNER_VERSION = "1.0"
TEXT_SAMPLE_LIMIT = 256_000
LARGE_FILE_BYTES = 5 * 1024 * 1024
LONG_LINE_CHARS = 2_000
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules", ".venv", "venv"}
SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

SECRET_VALUE_RE = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|credential|private[_-]?key|bearer)\s*[:=]\s*['\"]?([A-Za-z0-9_./+=:@-]{8,})"
)
SECRET_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "high"),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"), "high"),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "high"),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"), "high"),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "critical"),
    ("ssh_private_key", re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----"), "critical"),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{12,}"), "high"),
    ("generic_secret_assignment", SECRET_VALUE_RE, "high"),
]
SECRET_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "credentials",
    "credentials.json",
    "secrets.json",
    "id_rsa",
    "id_ed25519",
}
CREDENTIAL_TERMS = re.compile(r"(?i)\b(secret|credential|password|token|api[_-]?key|private[_-]?key)\b")

URL_RE = re.compile(r"\bhttps?://[^\s'\"<>)]+")
DOMAIN_RE = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:com|net|org|io|dev|ai|app|cloud|co|sh|run|xyz|internal)\b",
    re.IGNORECASE,
)
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
LOCALHOST_PORT_RE = re.compile(r"\b(?:localhost|127\.0\.0\.1|0\.0\.0\.0):(\d{2,5})\b", re.IGNORECASE)

HOOK_PATH_RE = re.compile(
    r"(?i)(^|/)(hooks?|\.claude/hooks|\.git/hooks)(/|$)|\b(pre-commit|post-commit|pre-push|preinstall|postinstall|prepare)\b"
)
HOOK_CONTENT_RE = re.compile(r"(?i)\b(on_save|on_start|on_exit|preinstall|postinstall|pre-commit|pre-push)\b")
SCRIPT_NAME_RE = re.compile(r"(?i)(setup|install|postinstall|preinstall|bootstrap|configure|makefile)")
SHELL_EXTENSIONS = {".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd"}
EXECUTABLE_EXTENSIONS = SHELL_EXTENSIONS | {".exe", ".dll", ".so", ".dylib", ".bin", ".app"}

MCP_KEY_RE = re.compile(r"(?i)\b(mcpServers|mcp_servers|mcp-server|modelcontextprotocol)\b")
MCP_COMMAND_RE = re.compile(r"(?i)\b(npx|uvx|python|node|bun|deno)\b.*\bmcp\b|\bmcp\b.*\b(command|args)\b")
BROAD_PATH_RE = re.compile(
    r"""(?ix)
    (   "/"                        # filesystem root passed as a quoted argument
      | '/'
      | ~(?=[/"'\s]|$)             # home directory reference (~ or ~/...)
      | \$HOME\b
      | %USERPROFILE%
      | [A-Za-z]:[\\/](?![\w.])    # bare drive root, e.g. C:\ or C:/ (not C:\project\...)
      | /home\b                    # broad *nix home tree
      | /Users\b
      | /root\b
      | /etc\b
    )
    """
)
FILESYSTEM_RE = re.compile(r"(?i)\b(filesystem|file system|fs|readFile|writeFile|path)\b")
BROWSER_NETWORK_RE = re.compile(r"(?i)\b(browser|fetch|http|websocket|network|url)\b")
DATABASE_RE = re.compile(r"(?i)\b(postgres|mysql|sqlite|database|mongodb|redis)\b")

DANGEROUS_COMMAND_PATTERNS: list[tuple[str, re.Pattern[str], str, str]] = [
    ("rm_rf", re.compile(r"\brm\s+-[^\n]*r[^\n]*f|\brm\s+-[^\n]*f[^\n]*r", re.IGNORECASE), "critical", "Remove broad destructive delete commands or gate them behind human review."),
    ("sudo", re.compile(r"\bsudo\b", re.IGNORECASE), "high", "Avoid privilege escalation in governed packages."),
    ("chmod_x", re.compile(r"\bchmod\s+\+x\b", re.IGNORECASE), "medium", "Review executable permission changes."),
    ("chown", re.compile(r"\bchown\b", re.IGNORECASE), "medium", "Review ownership changes."),
    ("curl_pipe_sh", re.compile(r"\bcurl\b[^\n|]*\|[^\n]*(?:sh|bash|zsh)\b", re.IGNORECASE), "critical", "Do not pipe remote scripts into a shell."),
    ("wget_pipe_sh", re.compile(r"\bwget\b[^\n|]*\|[^\n]*(?:sh|bash|zsh)\b", re.IGNORECASE), "critical", "Do not pipe remote scripts into a shell."),
    ("powershell_encoded", re.compile(r"\bpowershell(?:\.exe)?\b[^\n]*(?:-enc|-encodedcommand)\b", re.IGNORECASE), "critical", "Review encoded PowerShell commands."),
    ("eval", re.compile(r"\beval\s*\(", re.IGNORECASE), "high", "Avoid dynamic code execution."),
    ("exec", re.compile(r"\bexec\s*\(", re.IGNORECASE), "high", "Avoid dynamic process execution."),
    ("os_system", re.compile(r"\bos\.system\s*\(", re.IGNORECASE), "high", "Review shell execution from Python."),
    ("subprocess", re.compile(r"\bsubprocess\.(?:run|Popen|call|check_call|check_output)\s*\(", re.IGNORECASE), "high", "Review subprocess execution."),
    ("child_process_exec", re.compile(r"\bchild_process\.(?:exec|execSync|spawn)\s*\(", re.IGNORECASE), "high", "Review Node child process execution."),
    ("base64_exec", re.compile(r"\bbase64\b[^\n|]*\|[^\n]*(?:sh|bash|python|node|powershell)", re.IGNORECASE), "critical", "Review decoded command execution."),
    ("npm_install_scripts", re.compile(r"\bnpm\s+(?:install|ci)\b(?![^\n]*--ignore-scripts)", re.IGNORECASE), "medium", "Use explicit script controls when installing dependencies."),
    ("pip_install_url", re.compile(r"\bpip\s+install\b[^\n]*(?:https?://|git\+)", re.IGNORECASE), "high", "Review remote package installation."),
    ("docker_privileged", re.compile(r"\bdocker\s+run\b[^\n]*(?:--privileged|-v\s*/:|--volume\s+/:)", re.IGNORECASE), "critical", "Avoid privileged or root-mounted containers."),
    ("kubectl_mutate", re.compile(r"\bkubectl\s+(?:apply|delete|replace|patch)\b", re.IGNORECASE), "high", "Gate cluster mutations behind approval."),
    ("terraform_mutate", re.compile(r"\bterraform\s+(?:apply|destroy)\b", re.IGNORECASE), "critical", "Gate infrastructure mutations behind approval."),
    ("git_credentials", re.compile(r"\bgit\s+credential\b|\.git-credentials", re.IGNORECASE), "high", "Avoid credential access."),
    ("ssh_read", re.compile(r"(?:~|\$HOME|%USERPROFILE%)[/\\]\.ssh|/\.ssh/", re.IGNORECASE), "high", "Avoid SSH credential access."),
    ("aws_read", re.compile(r"(?:~|\$HOME|%USERPROFILE%)[/\\]\.aws|/\.aws/", re.IGNORECASE), "high", "Avoid cloud credential access."),
    ("env_read", re.compile(r"\b(?:cat|type|Get-Content)\s+\.env\b|readFileSync\(['\"]\.env", re.IGNORECASE), "high", "Avoid reading environment secret files."),
    ("external_upload", re.compile(r"\b(curl|wget)\b[^\n]*(?:-X\s+POST|-X\s+PUT|-F\s+|-d\s+|--data|--upload-file)", re.IGNORECASE), "high", "Review external writes/uploads."),
]


@dataclass(frozen=True)
class TextSample:
    text: str
    truncated: bool
    binary_like: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_evidence_id(*parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, default=str)
    return "ev-" + sha256_text(payload)[:16]


def relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def iter_source_files(source: Path) -> tuple[Path, list[Path]]:
    if source.is_file():
        return source.parent, [source]
    files: list[Path] = []
    # os.walk with followlinks=False does not descend into symlinked directories,
    # so a symlink cycle inside an untrusted package cannot loop the scanner.
    for dirpath, dirnames, filenames in os.walk(source, followlinks=False):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        for filename in filenames:
            candidate = Path(dirpath) / filename
            # Skip symlinked files as well: they can point outside the package tree
            # (e.g. at /etc/passwd) and must not be inventoried or read.
            if candidate.is_symlink():
                continue
            if candidate.is_file() and not any(
                part in SKIP_DIRS for part in candidate.relative_to(source).parts
            ):
                files.append(candidate)
    return source, sorted(files, key=lambda item: item.relative_to(source).as_posix())


def read_text_sample(path: Path) -> TextSample:
    try:
        with path.open("rb") as handle:
            data = handle.read(TEXT_SAMPLE_LIMIT + 1)
    except OSError:
        return TextSample("", False, True)
    truncated = len(data) > TEXT_SAMPLE_LIMIT
    data = data[:TEXT_SAMPLE_LIMIT]
    if b"\x00" in data:
        return TextSample("", truncated, True)
    try:
        return TextSample(data.decode("utf-8"), truncated, False)
    except UnicodeDecodeError:
        return TextSample(data.decode("utf-8", errors="ignore"), truncated, True)


def classify_file(path: Path, sample: TextSample) -> str:
    suffix = path.suffix.lower()
    if sample.binary_like:
        return "binary"
    if suffix in {".md", ".rst", ".txt"}:
        return "documentation"
    if suffix in {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"}:
        return "configuration"
    if suffix in {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".rb", ".java"}:
        return "source"
    if suffix in SHELL_EXTENSIONS:
        return "script"
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed:
        return guessed
    return "text"


def sanitize_excerpt(text: str, *, limit: int = 160) -> str:
    redacted = SECRET_VALUE_RE.sub(lambda match: f"{match.group(1)}=REDACTED_SECRET_LIKE_VALUE", text)
    for _, pattern, _ in SECRET_PATTERNS:
        redacted = pattern.sub("REDACTED_SECRET_LIKE_VALUE", redacted)
    redacted = redacted.replace("\r", " ").replace("\n", " ").strip()
    if len(redacted) > limit:
        return redacted[: limit - 3] + "..."
    return redacted


def evidence_record(
    *,
    evidence_type: str,
    package_id: str,
    file_path: str | None,
    finding_type: str,
    severity: str,
    source: str = "built_in_scanner",
    source_tool: str = SCANNER_NAME,
    source_version: str | None = None,
    confidence: str = "medium",
    status: str = "observed",
    raw_secret_stored: bool = False,
    sanitized_evidence: str = "",
    artifact_path: str = "",
    file_hash: str = "",
    requires_human_review: bool = True,
    recommendation: str = "",
    deterministic: bool = True,
    network_used: bool = False,
    execution_used: bool = False,
) -> dict[str, Any]:
    return {
        "evidence_id": stable_evidence_id(evidence_type, file_path, finding_type, sanitized_evidence),
        "evidence_type": evidence_type,
        "source": source,
        "source_tool": source_tool,
        "source_version": source_version if source_version is not None else SCANNER_VERSION if source_tool == SCANNER_NAME else "",
        "package_id": package_id,
        "file_path": file_path,
        "finding_type": finding_type,
        "severity": severity,
        "confidence": confidence,
        "status": status,
        "raw_secret_stored": raw_secret_stored,
        "sanitized_evidence": sanitized_evidence,
        "artifact_path": artifact_path,
        "hash": file_hash,
        "requires_human_review": requires_human_review,
        "recommendation": recommendation,
        "deterministic": deterministic,
        "network_used": network_used,
        "execution_used": execution_used,
    }


def file_inventory_item(path: Path, root: Path) -> tuple[dict[str, Any], TextSample]:
    sample = read_text_sample(path)
    rel = relative_to_root(path, root)
    # A single unreadable / race-deleted / permission-denied file must not abort
    # the whole scan of an untrusted package. Record it and keep going.
    try:
        size_bytes = path.stat().st_size
    except OSError:
        size_bytes = 0
    try:
        digest = sha256_file(path)
    except OSError:
        digest = ""
    lines = sample.text.splitlines() if sample.text else []
    long_lines = [index + 1 for index, line in enumerate(lines) if len(line) > LONG_LINE_CHARS]
    minified = bool(long_lines) or (len(lines) <= 3 and len(sample.text) > 10_000)
    item = {
        "path": rel,
        "size_bytes": size_bytes,
        "extension": path.suffix.lower(),
        "mime_classification": classify_file(path, sample),
        "sha256": digest,
        "read_error": digest == "",
        "hidden_or_dotfile": any(part.startswith(".") for part in Path(rel).parts),
        "binary_like": sample.binary_like,
        "large_file": size_bytes > LARGE_FILE_BYTES,
        "suspicious_long_line_or_minified": minified,
        "text_sample_truncated": sample.truncated,
    }
    return item, sample


def line_findings(
    *,
    text: str,
    rel: str,
    package_id: str,
    patterns: list[tuple[str, re.Pattern[str], str, str]],
    evidence_type: str,
    file_hash: str,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for finding_type, pattern, severity, recommendation in patterns:
            match = pattern.search(line)
            if not match:
                continue
            findings.append(
                {
                    "finding_id": stable_evidence_id(evidence_type, rel, finding_type, line_number),
                    "file_path": rel,
                    "line_number": line_number,
                    "finding_type": finding_type,
                    "severity": severity,
                    "matched_pattern": pattern.pattern,
                    "sanitized_evidence_excerpt": sanitize_excerpt(line),
                    "recommendation": recommendation,
                    "requires_human_review": severity in {"medium", "high", "critical"},
                    "evidence": evidence_record(
                        evidence_type=evidence_type,
                        package_id=package_id,
                        file_path=rel,
                        finding_type=finding_type,
                        severity=severity,
                        confidence="high",
                        sanitized_evidence=sanitize_excerpt(line),
                        file_hash=file_hash,
                        requires_human_review=severity in {"medium", "high", "critical"},
                        recommendation=recommendation,
                    ),
                }
            )
    return findings


def detect_secrets(rel: str, text: str, file_hash: str, package_id: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    name = Path(rel).name.lower()
    if name in SECRET_FILE_NAMES:
        findings.append(
            {
                "finding_id": stable_evidence_id("secret_scan", rel, "credential_file_name"),
                "finding_type": "credential_file_name",
                "file_path": rel,
                "line_number": None,
                "raw_value_stored": False,
                "evidence": "REDACTED_SECRET_LIKE_VALUE",
                "severity": "high",
                "requires_human_review": True,
                "evidence_record": evidence_record(
                    evidence_type="secret_scan",
                    package_id=package_id,
                    file_path=rel,
                    finding_type="credential_file_name",
                    severity="high",
                    confidence="medium",
                    raw_secret_stored=False,
                    sanitized_evidence="REDACTED_SECRET_LIKE_VALUE",
                    file_hash=file_hash,
                    recommendation="Remove credential-like files or provide explicit security review evidence.",
                ),
            }
        )
    for line_number, line in enumerate(text.splitlines(), start=1):
        for finding_type, pattern, severity in SECRET_PATTERNS:
            if not pattern.search(line):
                continue
            findings.append(
                {
                    "finding_id": stable_evidence_id("secret_scan", rel, finding_type, line_number),
                    "finding_type": "secret_like_pattern",
                    "pattern_type": finding_type,
                    "file_path": rel,
                    "line_number": line_number,
                    "raw_value_stored": False,
                    "evidence": "REDACTED_SECRET_LIKE_VALUE",
                    "severity": severity,
                    "requires_human_review": True,
                    "evidence_record": evidence_record(
                        evidence_type="secret_scan",
                        package_id=package_id,
                        file_path=rel,
                        finding_type="secret_like_pattern",
                        severity=severity,
                        confidence="medium",
                        raw_secret_stored=False,
                        sanitized_evidence="REDACTED_SECRET_LIKE_VALUE",
                        file_hash=file_hash,
                        recommendation="Rotate/remove the value if real and require security review evidence.",
                    ),
                }
            )
    return findings


def classify_endpoint(line: str, endpoint: str) -> str:
    lower = line.lower()
    if "webhook" in lower or "callback" in lower:
        return "webhook_callback"
    if re.search(r"\b(curl|wget)\b", lower) and re.search(r"\|\s*(sh|bash|zsh)", lower):
        return "execution"
    if re.search(r"\b(post|put|patch|--upload-file|-f\s+|-d\s+|--data)\b", lower):
        return "upload_write"
    if re.search(r"\b(git clone|pip install|npm install|curl|wget)\b", lower):
        return "download"
    if endpoint.startswith("http"):
        return "unknown"
    return "informational"


def valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def detect_endpoints(rel: str, text: str, file_hash: str, package_id: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        endpoints: list[str] = []
        endpoints.extend(URL_RE.findall(line))
        endpoints.extend(DOMAIN_RE.findall(line))
        endpoints.extend(item for item in IP_RE.findall(line) if valid_ip(item))
        if not endpoints:
            continue
        for endpoint in sorted(set(endpoints)):
            safe_endpoint = sanitize_excerpt(endpoint)
            endpoint_type = classify_endpoint(line, endpoint)
            severity = "high" if endpoint_type in {"execution", "upload_write", "webhook_callback"} else "low"
            findings.append(
                {
                    "finding_id": stable_evidence_id("endpoint_scan", rel, safe_endpoint, line_number),
                    "file_path": rel,
                    "line_number": line_number,
                    "finding_type": "external_endpoint",
                    "endpoint": safe_endpoint,
                    "endpoint_classification": endpoint_type,
                    "severity": severity,
                    "sanitized_evidence_excerpt": sanitize_excerpt(line),
                    "requires_human_review": endpoint_type in {"execution", "upload_write", "webhook_callback", "unknown"},
                    "evidence_record": evidence_record(
                        evidence_type="endpoint_scan",
                        package_id=package_id,
                        file_path=rel,
                        finding_type=f"endpoint_{endpoint_type}",
                        severity=severity,
                        confidence="medium",
                        sanitized_evidence=sanitize_excerpt(line),
                        file_hash=file_hash,
                        recommendation="Review endpoint purpose and require approval for remote execution or writes.",
                        requires_human_review=endpoint_type != "informational",
                    ),
                }
            )
    return findings


def detect_hooks(rel: str, text: str, file_hash: str, package_id: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if HOOK_PATH_RE.search(rel):
        findings.append(
            {
                "finding_id": stable_evidence_id("hook_risk", rel, "hook_path"),
                "file_path": rel,
                "finding_type": "hook_path",
                "severity": "high",
                "matched_pattern": HOOK_PATH_RE.pattern,
                "sanitized_evidence_excerpt": rel,
                "recommendation": "Require hook risk review before any activation.",
                "requires_human_review": True,
                "evidence": evidence_record(
                    evidence_type="hook_risk",
                    package_id=package_id,
                    file_path=rel,
                    finding_type="hook_path",
                    severity="high",
                    confidence="high",
                    sanitized_evidence=rel,
                    file_hash=file_hash,
                    recommendation="Require hook risk review before any activation.",
                ),
            }
        )
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not HOOK_CONTENT_RE.search(line):
            continue
        findings.append(
            {
                "finding_id": stable_evidence_id("hook_risk", rel, "hook_content", line_number),
                "file_path": rel,
                "line_number": line_number,
                "finding_type": "hook_content",
                "severity": "high",
                "matched_pattern": HOOK_CONTENT_RE.pattern,
                "sanitized_evidence_excerpt": sanitize_excerpt(line),
                "recommendation": "Require hook risk review before any activation.",
                "requires_human_review": True,
                "evidence": evidence_record(
                    evidence_type="hook_risk",
                    package_id=package_id,
                    file_path=rel,
                    finding_type="hook_content",
                    severity="high",
                    confidence="medium",
                    sanitized_evidence=sanitize_excerpt(line),
                    file_hash=file_hash,
                    recommendation="Require hook risk review before any activation.",
                ),
            }
        )
    return findings


def detect_mcp(rel: str, text: str, file_hash: str, package_id: str) -> list[dict[str, Any]]:
    if not (MCP_KEY_RE.search(rel) or MCP_KEY_RE.search(text) or MCP_COMMAND_RE.search(text)):
        return []
    severity = "medium"
    risk_classification = "medium"
    reasons = []
    if BROAD_PATH_RE.search(text):
        severity = "critical"
        risk_classification = "critical"
        reasons.append("broad_filesystem_path")
    if FILESYSTEM_RE.search(text):
        severity = "high" if severity != "critical" else severity
        risk_classification = "high" if risk_classification != "critical" else risk_classification
        reasons.append("filesystem_access")
    if BROWSER_NETWORK_RE.search(text) or URL_RE.search(text):
        severity = "high" if severity != "critical" else severity
        risk_classification = "high" if risk_classification != "critical" else risk_classification
        reasons.append("browser_or_network_access")
    if DATABASE_RE.search(text):
        severity = "high" if severity != "critical" else severity
        risk_classification = "high" if risk_classification != "critical" else risk_classification
        reasons.append("database_access")
    if not reasons:
        reasons.append("mcp_config_reference")
    return [
        {
            "finding_id": stable_evidence_id("mcp_risk", rel, ",".join(reasons)),
            "file_path": rel,
            "finding_type": "mcp_server_definition",
            "severity": severity,
            "risk_classification": risk_classification,
            "matched_pattern": "mcpServers/mcp_servers/server command definitions",
            "sanitized_evidence_excerpt": sanitize_excerpt(text),
            "recommendation": "Require MCP risk review before starting any server.",
            "requires_human_review": True,
            "reasons": reasons,
            "evidence_record": evidence_record(
                evidence_type="mcp_risk",
                package_id=package_id,
                file_path=rel,
                finding_type="mcp_server_definition",
                severity=severity,
                confidence="high",
                sanitized_evidence=sanitize_excerpt(text),
                file_hash=file_hash,
                recommendation="Require MCP risk review before starting any server.",
            ),
        }
    ]


def detect_scripts(rel: str, text: str, file_hash: str, package_id: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    suffix = Path(rel).suffix.lower()
    name = Path(rel).name.lower()
    if suffix in SHELL_EXTENSIONS or SCRIPT_NAME_RE.search(name):
        findings.append(
            {
                "finding_id": stable_evidence_id("script_risk", rel, "setup_or_shell_script"),
                "file_path": rel,
                "finding_type": "setup_install_or_shell_script",
                "severity": "high" if SCRIPT_NAME_RE.search(name) else "medium",
                "matched_pattern": "setup/install/shell script path",
                "sanitized_evidence_excerpt": rel,
                "recommendation": "Treat scripts as inert until explicitly reviewed and approved.",
                "requires_human_review": True,
                "evidence_record": evidence_record(
                    evidence_type="script_risk",
                    package_id=package_id,
                    file_path=rel,
                    finding_type="setup_install_or_shell_script",
                    severity="high" if SCRIPT_NAME_RE.search(name) else "medium",
                    confidence="high",
                    sanitized_evidence=rel,
                    file_hash=file_hash,
                    recommendation="Treat scripts as inert until explicitly reviewed and approved.",
                ),
            }
        )
    if name == "package.json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {}
        scripts = payload.get("scripts") if isinstance(payload, dict) else None
        if isinstance(scripts, dict):
            for script_name, command in sorted(scripts.items()):
                if script_name in {"preinstall", "install", "postinstall", "prepare", "prepublish", "prepack"}:
                    excerpt = f"{script_name}: {sanitize_excerpt(str(command))}"
                    findings.append(
                        {
                            "finding_id": stable_evidence_id("script_risk", rel, script_name),
                            "file_path": rel,
                            "finding_type": "package_manager_lifecycle_script",
                            "severity": "high",
                            "matched_pattern": script_name,
                            "sanitized_evidence_excerpt": excerpt,
                            "recommendation": "Require lifecycle script review before installation.",
                            "requires_human_review": True,
                            "evidence_record": evidence_record(
                                evidence_type="script_risk",
                                package_id=package_id,
                                file_path=rel,
                                finding_type="package_manager_lifecycle_script",
                                severity="high",
                                confidence="high",
                                sanitized_evidence=excerpt,
                                file_hash=file_hash,
                                recommendation="Require lifecycle script review before installation.",
                            ),
                        }
                    )
    return findings


def claim_flags_from_text(text: str) -> dict[str, bool]:
    lower = text.lower()
    return {
        "docs_only": bool(re.search(r"\b(docs?|documentation)\s+only\b", lower)),
        "no_network": bool(re.search(r"\b(no|without)\s+(network|internet|external endpoints?)\b", lower)),
        "no_execution": bool(re.search(r"\b(no|without)\s+(execution|scripts?|commands?)\b", lower)),
        "no_secrets": bool(re.search(r"\b(no|without)\s+(secrets?|credentials?|tokens?)\b", lower)),
        "template_only": "template only" in lower,
        "local_only": "local only" in lower,
    }


def collect_claims(source_root: Path, files: list[Path], package_claims: dict[str, Any] | None) -> dict[str, Any]:
    claims = {key: bool(value) for key, value in (package_claims or {}).items() if isinstance(value, bool)}
    text_parts: list[str] = []
    for path in files:
        if path.name.lower().startswith("readme"):
            text_parts.append(read_text_sample(path).text)
    for key, value in claim_flags_from_text("\n".join(text_parts)).items():
        claims.setdefault(key, value)
    return {
        "trust_level": {
            "upstream_readme": "untrusted_claim",
            "package_manifest": "untrusted_claim",
            "package_description": "untrusted_claim",
            "declared_capabilities": "untrusted_claim",
        },
        "claims": claims,
    }


def detect_claim_mismatches(claim_model: dict[str, Any], summaries: dict[str, Any], package_id: str) -> list[dict[str, Any]]:
    claims = claim_model.get("claims", {})
    checks = [
        ("docs_only", summaries["hooks"] or summaries["mcp"] or summaries["scripts"], "docs_only_but_risk_surfaces_observed", "critical"),
        ("no_network", summaries["endpoints"], "no_network_but_endpoints_observed", "high"),
        ("no_execution", summaries["scripts"], "no_execution_but_scripts_observed", "critical"),
        ("no_secrets", summaries["secrets"], "no_secrets_but_secret_like_patterns_observed", "high"),
        ("template_only", summaries["executables"], "template_only_but_executable_files_observed", "high"),
        ("local_only", summaries["webhooks_or_remote"], "local_only_but_remote_endpoints_observed", "high"),
    ]
    mismatches: list[dict[str, Any]] = []
    for claim, observed, finding_type, severity in checks:
        if not claims.get(claim) or not observed:
            continue
        mismatches.append(
            {
                "finding_id": stable_evidence_id("claim_vs_evidence", claim, finding_type),
                "claim": claim,
                "claim_trust_level": "untrusted_claim",
                "observed_evidence": observed,
                "evidence_trust_level": "risk_evidence",
                "finding_type": finding_type,
                "severity": severity,
                "requires_human_review": True,
                "recommendation": "Do not treat package claims as truth; require human review of observed evidence.",
                "evidence_record": evidence_record(
                    evidence_type="claim_vs_evidence",
                    package_id=package_id,
                    file_path=None,
                    finding_type=finding_type,
                    severity=severity,
                    confidence="high",
                    sanitized_evidence=f"{claim} contradicted by observed evidence",
                    recommendation="Do not treat package claims as truth; require human review of observed evidence.",
                ),
            }
        )
    return mismatches


def risk_tier(findings: list[dict[str, Any]]) -> str:
    max_severity = "low"
    for finding in findings:
        severity = str(finding.get("severity", "info"))
        if SEVERITY_ORDER.get(severity, 0) > SEVERITY_ORDER[max_severity]:
            max_severity = severity
    if max_severity in {"critical", "high"}:
        return max_severity
    if max_severity == "medium":
        return "medium"
    return "low"


def severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(item.get("severity", "info")) for item in findings)
    return {severity: counts.get(severity, 0) for severity in ["info", "low", "medium", "high", "critical"]}


def parse_syft_report(report_path: Path, package_id: str) -> list[dict[str, Any]]:
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    artifacts = payload.get("artifacts", []) if isinstance(payload, dict) else []
    records: list[dict[str, Any]] = []
    for item in artifacts if isinstance(artifacts, list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "unknown"))
        version = str(item.get("version", ""))
        records.append(
            evidence_record(
                evidence_type="sbom",
                source="external_adapter",
                source_tool="syft",
                source_version=str(payload.get("descriptor", {}).get("version", "")) if isinstance(payload.get("descriptor"), dict) else "",
                package_id=package_id,
                file_path=None,
                finding_type="sbom_component",
                severity="info",
                confidence="medium",
                status="imported",
                sanitized_evidence=f"{name} {version}".strip(),
                artifact_path=report_path.as_posix(),
                requires_human_review=False,
                recommendation="Use SBOM evidence during supply-chain review.",
                deterministic=False,
                network_used=False,
                execution_used=True,
            )
        )
    return records


def parse_gitleaks_report(report_path: Path, package_id: str) -> list[dict[str, Any]]:
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    leaks = payload if isinstance(payload, list) else payload.get("findings", []) if isinstance(payload, dict) else []
    records: list[dict[str, Any]] = []
    for item in leaks if isinstance(leaks, list) else []:
        if not isinstance(item, dict):
            continue
        rel = str(item.get("File") or item.get("file") or "")
        rule = str(item.get("RuleID") or item.get("rule_id") or "gitleaks_secret")
        records.append(
            evidence_record(
                evidence_type="secret_scan",
                source="external_adapter",
                source_tool="gitleaks",
                package_id=package_id,
                file_path=rel or None,
                finding_type=rule,
                severity="high",
                confidence="medium",
                status="imported",
                raw_secret_stored=False,
                sanitized_evidence="REDACTED_SECRET_LIKE_VALUE",
                artifact_path=report_path.as_posix(),
                requires_human_review=True,
                recommendation="Review external secret scanner finding and rotate if real.",
                deterministic=False,
                network_used=False,
                execution_used=True,
            )
        )
    return records


ADAPTER_PARSERS = {
    "syft": parse_syft_report,
    "gitleaks": parse_gitleaks_report,
}


def normalize_adapter_config(config: Any) -> list[dict[str, Any]]:
    if not isinstance(config, list):
        return []
    adapters: list[dict[str, Any]] = []
    for item in config:
        if isinstance(item, dict):
            adapters.append(item)
    return adapters


def run_external_adapters(
    adapters_config: Any,
    *,
    package_id: str,
    source: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    executions: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for adapter in normalize_adapter_config(adapters_config):
        name = str(adapter.get("name", "")).strip()
        enabled = bool(adapter.get("enabled", adapter.get("enabled") is not False))
        required = bool(adapter.get("required", False))
        # A required adapter fails by default; opt out explicitly with failure_policy: warn.
        failure_policy = str(adapter.get("failure_policy", "fail" if required else "warn"))
        mode = str(adapter.get("mode", "local_cli"))
        network_required = bool(adapter.get("network_required", False) or mode == "api")
        status = "disabled"
        detail = ""
        parsed_records: list[dict[str, Any]] = []
        report_path_value = adapter.get("report_path") or adapter.get("artifact_path")
        command = str(adapter.get("command", name))
        available = bool(shutil.which(command)) if command else False
        if not enabled:
            detail = "adapter disabled"
        elif network_required and not adapter.get("allow_network", False):
            status = "unavailable"
            detail = "network adapter requires explicit allow_network"
        elif report_path_value:
            report_path = Path(str(report_path_value))
            if not report_path.is_absolute():
                report_path = source / report_path
            parser = ADAPTER_PARSERS.get(name)
            if parser is None:
                status = "unavailable"
                detail = "no parser registered for adapter"
            elif not report_path.exists():
                status = "failed"
                detail = "configured report_path does not exist"
            else:
                try:
                    parsed_records = parser(report_path, package_id)
                    records.extend(parsed_records)
                    status = "imported"
                    detail = f"imported {len(parsed_records)} evidence records"
                except (json.JSONDecodeError, OSError, ValueError) as exc:
                    status = "failed"
                    detail = f"failed to parse report: {exc}"
        else:
            status = "unavailable"
            detail = "external tools are not executed automatically; provide report_path to import evidence"
        if enabled and not report_path_value and available:
            detail += "; command is available but not executed by Nornyx"
        execution = {
            "name": name,
            "type": adapter.get("type", "external_evidence"),
            "mode": mode,
            "enabled": enabled,
            "required": required,
            "failure_policy": failure_policy,
            "network_required": network_required,
            "status": status,
            "detail": detail,
            "evidence_count": len(parsed_records),
            "package_payload_executed": False,
        }
        executions.append(execution)
        if enabled and status in {"unavailable", "failed"}:
            diagnostics.append(
                {
                    "level": "error" if required and failure_policy != "warn" else "warning",
                    "code": "REQUIRED_ADAPTER_UNAVAILABLE" if required else "OPTIONAL_ADAPTER_UNAVAILABLE",
                    "adapter": name,
                    "message": detail,
                }
            )
    summary = {
        "status": "fail" if any(item["level"] == "error" for item in diagnostics) else "pass",
        "source_path": source.as_posix(),
        "adapter_count": len(executions),
        "evidence_count": len(records),
        "evidence_count_by_source": dict(Counter(record["source_tool"] for record in records)),
        "diagnostics": diagnostics,
    }
    return records, summary, executions


def render_table_report(title: str, findings: list[dict[str, Any]], empty: str) -> str:
    lines = [f"# {title}\n\n"]
    if not findings:
        lines.append(empty + "\n")
        return "".join(lines)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in findings:
        grouped[str(finding.get("severity", "info"))].append(finding)
    for severity in ["critical", "high", "medium", "low", "info"]:
        items = grouped.get(severity, [])
        if not items:
            continue
        lines.append(f"## {severity.title()}\n\n")
        for finding in items:
            path = finding.get("file_path") or finding.get("path") or "<package>"
            kind = finding.get("finding_type", "finding")
            excerpt = finding.get("sanitized_evidence_excerpt") or finding.get("evidence") or finding.get("sanitized_evidence") or ""
            lines.append(f"- `{kind}` in `{path}`")
            if finding.get("line_number"):
                lines.append(f" line {finding['line_number']}")
            if excerpt:
                lines.append(f": {sanitize_excerpt(str(excerpt))}")
            lines.append("\n")
    return "".join(lines)


def render_inventory(report: dict[str, Any]) -> str:
    lines = ["# Source Inventory\n\n"]
    summary = report["summary"]
    lines.append(f"- Total files scanned: {summary['total_files_scanned']}\n")
    lines.append(f"- Total bytes scanned: {summary['total_bytes_scanned']}\n")
    lines.append(f"- Binary-like files: {summary['binary_like_files']}\n")
    lines.append(f"- Hidden/dotfiles: {summary['hidden_or_dotfiles']}\n\n")
    for item in report["files"]:
        lines.append(f"- `{item['path']}` ({item['size_bytes']} bytes, `{item['sha256']}`)\n")
    return "".join(lines)


def render_analysis(report: dict[str, Any]) -> str:
    lines = ["# Package Analysis\n\n"]
    lines.append("Nornyx treats package contents and claims as untrusted input.\n\n")
    lines.append(f"- Package ID: `{report['package_id']}`\n")
    lines.append(f"- Risk tier: `{report['risk_surface']['risk_tier']}`\n")
    lines.append(f"- Total findings: {report['risk_surface']['finding_count']}\n")
    lines.append("- Statement: This package was inventoried, risk-surfaced, evidence-bound, hash-locked, and approval-gated.\n")
    return "".join(lines)


def render_risk(report: dict[str, Any]) -> str:
    lines = ["# Risk Surface Report\n\n"]
    risk = report["risk_surface"]
    lines.append(f"- Risk tier: `{risk['risk_tier']}`\n")
    lines.append(f"- Risk score: `{risk['risk_score']}`\n")
    for severity, count in risk["finding_count_by_severity"].items():
        lines.append(f"- {severity}: {count}\n")
    lines.append("\n## Explanations\n\n")
    for explanation in risk["explanations"]:
        lines.append(f"- {explanation}\n")
    return "".join(lines)


def scan_package(
    source_path: str | Path,
    *,
    out_dir: str | Path | None = None,
    package_id: str = "package",
    package_claims: dict[str, Any] | None = None,
    evidence_adapters: Any = None,
) -> dict[str, Any]:
    source = Path(source_path)
    if not source.exists():
        raise ValueError(f"package scan source does not exist: {source}")
    root, files = iter_source_files(source)
    inventory: list[dict[str, Any]] = []
    findings: dict[str, list[dict[str, Any]]] = {
        "hooks": [],
        "mcp": [],
        "secrets": [],
        "endpoints": [],
        "commands": [],
        "scripts": [],
    }
    evidence_records: list[dict[str, Any]] = []
    localhost_ports: set[int] = set()
    credential_term_files: set[str] = set()
    executable_files: list[str] = []
    webhooks_or_remote: list[str] = []
    invalid_structured_files: list[dict[str, Any]] = []

    for path in files:
        item, sample = file_inventory_item(path, root)
        rel = item["path"]
        inventory.append(item)
        if Path(rel).suffix.lower() in EXECUTABLE_EXTENSIONS:
            executable_files.append(rel)
        text = sample.text
        if not text:
            continue
        if CREDENTIAL_TERMS.search(text):
            credential_term_files.add(rel)
        for port_match in LOCALHOST_PORT_RE.finditer(text):
            localhost_ports.add(int(port_match.group(1)))
        if Path(rel).suffix.lower() in {".json", ".yaml", ".yml"}:
            try:
                if Path(rel).suffix.lower() == ".json":
                    json.loads(text)
                else:
                    yaml.safe_load(text)
            except (json.JSONDecodeError, yaml.YAMLError) as exc:
                invalid_structured_files.append({"path": rel, "error": sanitize_excerpt(str(exc))})
        findings["hooks"].extend(detect_hooks(rel, text, item["sha256"], package_id))
        findings["mcp"].extend(detect_mcp(rel, text, item["sha256"], package_id))
        findings["secrets"].extend(detect_secrets(rel, text, item["sha256"], package_id))
        endpoint_findings = detect_endpoints(rel, text, item["sha256"], package_id)
        findings["endpoints"].extend(endpoint_findings)
        if any(item.get("endpoint_classification") in {"webhook_callback", "upload_write", "execution", "unknown"} for item in endpoint_findings):
            webhooks_or_remote.append(rel)
        findings["commands"].extend(
            line_findings(
                text=text,
                rel=rel,
                package_id=package_id,
                patterns=DANGEROUS_COMMAND_PATTERNS,
                evidence_type="command_risk",
                file_hash=item["sha256"],
            )
        )
        findings["scripts"].extend(detect_scripts(rel, text, item["sha256"], package_id))

    claim_model = collect_claims(root, files, package_claims)
    mismatch_summaries = {
        "hooks": [item["file_path"] for item in findings["hooks"]],
        "mcp": [item["file_path"] for item in findings["mcp"]],
        "scripts": [item["file_path"] for item in findings["scripts"]],
        "endpoints": [item["file_path"] for item in findings["endpoints"]],
        "secrets": [item["file_path"] for item in findings["secrets"]],
        "executables": executable_files,
        "webhooks_or_remote": webhooks_or_remote,
    }
    claim_mismatches = detect_claim_mismatches(claim_model, mismatch_summaries, package_id)

    for key in ["hooks", "mcp", "secrets", "endpoints", "commands", "scripts"]:
        for finding in findings[key]:
            evidence = finding.get("evidence_record") or finding.get("evidence")
            if isinstance(evidence, dict):
                evidence_records.append(evidence)
    for mismatch in claim_mismatches:
        evidence_records.append(mismatch["evidence_record"])
    for item in inventory:
        evidence_records.append(
            evidence_record(
                evidence_type="discovered_file_inventory",
                package_id=package_id,
                file_path=item["path"],
                finding_type="file_inventory",
                severity="info",
                confidence="high",
                status="observed",
                raw_secret_stored=False,
                sanitized_evidence=f"{item['path']} {item['size_bytes']} bytes",
                file_hash=item["sha256"],
                requires_human_review=False,
                recommendation="Use file hash for integrity review.",
            )
        )

    adapter_records, adapter_summary, adapter_executions = run_external_adapters(
        evidence_adapters,
        package_id=package_id,
        source=root,
    )
    evidence_records.extend(adapter_records)

    all_risk_findings = (
        findings["hooks"]
        + findings["mcp"]
        + findings["secrets"]
        + findings["endpoints"]
        + findings["commands"]
        + findings["scripts"]
        + claim_mismatches
    )
    for record in adapter_records:
        if record.get("severity") in {"high", "critical"}:
            all_risk_findings.append(record)
    tier = risk_tier(all_risk_findings)
    score = sum(SEVERITY_ORDER.get(str(item.get("severity", "info")), 0) for item in all_risk_findings)
    explanations = []
    for label, values in [
        ("hooks detected", findings["hooks"]),
        ("MCP configs detected", findings["mcp"]),
        ("setup/install/lifecycle scripts detected", findings["scripts"]),
        ("secret-like content detected", findings["secrets"]),
        ("dangerous commands detected", findings["commands"]),
        ("claim-vs-evidence mismatch detected", claim_mismatches),
    ]:
        if values:
            explanations.append(f"{label}: {len(values)} finding(s)")
    if any(item.get("finding_type") in {"broad_filesystem_access", "mcp_server_definition"} and item.get("severity") == "critical" for item in all_risk_findings):
        explanations.append("critical broad filesystem or MCP access observed")
    if not explanations:
        explanations.append("No high-risk surfaces detected by the built-in deterministic scanner.")

    source_hash = sha256_text(json.dumps([{"path": item["path"], "sha256": item["sha256"]} for item in inventory], sort_keys=True))
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "package_id": package_id,
        "source_path": source.as_posix(),
        "source_root": root.as_posix(),
        "source_hash": source_hash,
        "scanner": {
            "name": SCANNER_NAME,
            "version": SCANNER_VERSION,
            "nornyx_version": __version__,
            "deterministic": True,
            "network_used": False,
            "package_payload_executed": False,
        },
        "summary": {
            "total_files_scanned": len(inventory),
            "total_bytes_scanned": sum(item["size_bytes"] for item in inventory),
            "hidden_or_dotfiles": sum(1 for item in inventory if item["hidden_or_dotfile"]),
            "binary_like_files": sum(1 for item in inventory if item["binary_like"]),
            "large_files": sum(1 for item in inventory if item["large_file"]),
            "suspicious_long_line_or_minified_files": sum(1 for item in inventory if item["suspicious_long_line_or_minified"]),
            "localhost_ports": sorted(localhost_ports),
            "credential_term_files": sorted(credential_term_files),
            "invalid_structured_files": invalid_structured_files,
        },
        "files": inventory,
        "findings": findings,
        "claim_vs_evidence": {
            "trust_levels": claim_model["trust_level"],
            "claims": claim_model["claims"],
            "mismatches": claim_mismatches,
        },
        "evidence_records": evidence_records,
        "risk_surface": {
            "risk_tier": tier,
            "risk_score": score,
            "finding_count": len(all_risk_findings),
            "finding_count_by_severity": severity_counts(all_risk_findings),
            "explanations": explanations,
        },
        "external_evidence_summary": adapter_summary,
        "adapter_execution_report": {
            "executions": adapter_executions,
            "package_payload_executed": False,
        },
        "safety_boundary": {
            "package_payload_executed": False,
            "network_used_by_builtin_scanner": False,
            "raw_secret_values_stored": False,
            "hooks_activated": False,
            "mcp_servers_started": False,
        },
    }
    if out_dir is not None:
        write_scan_reports(report, out_dir)
    return report


def report_hashes(out: Path, names: list[str]) -> list[dict[str, str]]:
    hashes: list[dict[str, str]] = []
    for name in names:
        path = out / name
        if path.exists():
            hashes.append({"path": name, "sha256": sha256_file(path)})
    return hashes


def write_scan_reports(report: dict[str, Any], out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    reports: list[tuple[str, Any]] = [
        ("package_analysis.json", report),
        ("risk_surface_report.json", report["risk_surface"]),
        ("hook_risk_report.json", {"findings": report["findings"]["hooks"]}),
        ("mcp_risk_report.json", {"findings": report["findings"]["mcp"]}),
        ("secret_scan_report.json", {"findings": report["findings"]["secrets"]}),
        ("endpoint_scan_report.json", {"findings": report["findings"]["endpoints"]}),
        ("command_risk_report.json", {"findings": report["findings"]["commands"]}),
        ("claim_vs_evidence_report.json", report["claim_vs_evidence"]),
        ("external_evidence_summary.json", report["external_evidence_summary"]),
        ("adapter_execution_report.json", report["adapter_execution_report"]),
    ]
    for filename, payload in reports:
        path = out / filename
        write_json(path, payload)
        written.append(path)
    markdown = {
        "package_analysis.md": render_analysis(report),
        "risk_surface_report.md": render_risk(report),
        "source_inventory.md": render_inventory(report),
        "hook_risk_review.md": render_table_report("Hook Risk Review", report["findings"]["hooks"], "No hook risk findings were observed.\n"),
        "mcp_risk_review.md": render_table_report("MCP Risk Review", report["findings"]["mcp"], "No MCP risk findings were observed.\n"),
        "secret_scan_report.md": render_table_report("Secret Scan Report", report["findings"]["secrets"], "No secret-like findings were observed.\n"),
        "endpoint_scan_report.md": render_table_report("Endpoint Scan Report", report["findings"]["endpoints"], "No endpoint findings were observed.\n"),
        "command_risk_report.md": render_table_report("Command Risk Report", report["findings"]["commands"], "No dangerous command findings were observed.\n"),
        "claim_vs_evidence_report.md": render_table_report("Claim-vs-Evidence Report", report["claim_vs_evidence"]["mismatches"], "No claim-vs-evidence mismatches were observed.\n"),
        "external_evidence_summary.md": render_table_report("External Evidence Summary", report["external_evidence_summary"].get("diagnostics", []), "No external adapter diagnostics were observed.\n"),
    }
    for filename, content in markdown.items():
        path = out / filename
        write_text(path, content)
        written.append(path)
    return written
