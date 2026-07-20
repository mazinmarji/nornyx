"""AN-006 tests: the Governed Customer Support Network product proof."""

from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
from io import StringIO
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import pytest
import yaml

from nornyx.agentic_artifacts import (
    agentic_network_lock_digest,
    build_agentic_network_lock,
    contract_digest,
)
from nornyx.cli import build_parser, main as cli_main
from nornyx.eval_import import EvalImportError, convert_promptfoo_results
from nornyx.eval_runtime import evaluate_document_evals
from nornyx.governance import GovernanceRegistry, compose_governance
from nornyx.governance.runtime import evaluate_document_governance


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = ROOT / "examples" / "agentic_network_support"
CONTRACT = EXAMPLE_DIR / "support_network.nyx"
PROMPTFOO = EXAMPLE_DIR / "eval" / "promptfoo_results.json"
DOCS = ROOT / "docs" / "agentic-network"
AS_OF = "2026-07-17T00:00:00Z"
REGISTRY = GovernanceRegistry.builtins()
COMPOSITION = compose_governance(REGISTRY, profile_identity="agentic_network")

GOLDEN_SUPPORT_LOCK_DIGEST = (
    "sha256:e4725b0a138ebfd1f58c43ed22ce184d6cdaff08e7a358a29cfeea8852cbb3ba"
)
GOLDEN_SUPPORT_CONTRACT_DIGEST = (
    "sha256:3cdf632c08684efa2382a047b474b8f56ea4a83c5ed2f86c05918c29d0ac8eda"
)


def _document() -> dict[str, Any]:
    return yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))


def test_support_contract_validates_cleanly() -> None:
    diagnostics = evaluate_document_governance(
        _document(),
        registry=REGISTRY,
        as_of=AS_OF,
        document_root=EXAMPLE_DIR,
    )
    assert [item.to_dict() for item in diagnostics if item.level == "error"] == []


def test_support_contract_uses_fake_data_only() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert "feedface" in text
    for forbidden in ("http://", "https://", "api_key", "password", "Bearer "):
        assert forbidden not in text
    for artifact in (EXAMPLE_DIR / "governance_evidence").iterdir():
        assert "@" not in artifact.read_text(encoding="utf-8")


def test_support_lock_golden_digests() -> None:
    document = _document()
    assert contract_digest(document) == GOLDEN_SUPPORT_CONTRACT_DIGEST
    lock = build_agentic_network_lock(document, COMPOSITION)
    assert agentic_network_lock_digest(lock) == GOLDEN_SUPPORT_LOCK_DIGEST
    assert lock["network_id"] == "network.governed_support"
    assert len(lock["records"]["agent_identities"]) == 4
    assert len(lock["records"]["capabilities"]) == 8
    assert len(lock["records"]["delegations"]) == 1
    assert len(lock["records"]["handoffs"]) == 1
    assert len(lock["records"]["relations"]) == 4


def test_demo_produces_validated_measurable_proof(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "support_run_demo", EXAMPLE_DIR / "run_demo.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    out = tmp_path / "demo"
    stdout = StringIO()
    with redirect_stdout(stdout):
        assert module.main(["--out", str(out)]) == 0

    summary = json.loads((out / "demo_summary.json").read_text(encoding="utf-8"))
    assert summary["generated_artifacts"] == 10
    assert summary["governed_identities"] == 4
    assert summary["capabilities"] == 8
    assert summary["trust_zones"] == 2
    assert summary["source_contract_digest"] == GOLDEN_SUPPORT_CONTRACT_DIGEST
    for framework in ("crewai", "langgraph"):
        assert summary["frameworks"][framework]["evidence_validation"] == "pass"
    crewai = summary["frameworks"]["crewai"]
    assert crewai["blocked_scenarios"]["ai_generated_approval"] == (
        "AN_ADAPTER_APPROVAL_NON_HUMAN"
    )
    assert crewai["blocked_scenarios"]["refund_agent_capability_escalation"] == (
        "AN_ADAPTER_CAPABILITY_DENIED"
    )
    assert crewai["blocked_scenarios"]["sensitive_sharing"] == (
        "AN_ADAPTER_SENSITIVE_SHARING"
    )
    assert summary["static_rejections"] == {
        "ai_approval_rejected_statically": "AN_APPROVAL_HUMAN_REQUIRED",
        "capability_escalation": "AN_CAPABILITY_ESCALATION",
        "handoff_cannot_grant_authority": "AN_HANDOFF_AUTHORITY_ESCALATION",
        "onward_delegation_denied": "AN_ONWARD_DELEGATION_DENIED",
        "sensitive_delegation_scope": "AN_DELEGATION_SENSITIVE_SHARING",
        "stale_approval_on_revision_change": "AN_REVISION_MISMATCH",
    }
    assert summary["contract_drift_detection"] == "AN_LOCK_SOURCE_STALE"
    assert summary["external_eval"]["metrics_passed"] == 4
    assert all(value is False for value in summary["safety"].values())

    # The demo's evidence validates again through the CLI, end to end.
    stdout = StringIO()
    with redirect_stdout(stdout):
        code = cli_main(
            [
                "agentic-network",
                "evidence-validate",
                str(CONTRACT),
                "--events",
                str(out / "langgraph_events.json"),
                "--lock",
                str(out / "nornyx.agentic_network.lock"),
                "--as-of",
                AS_OF,
                "--strict",
            ]
        )
    assert code == 0, stdout.getvalue()


def test_promptfoo_import_binds_and_validates_thresholds(tmp_path: Path) -> None:
    imported = convert_promptfoo_results(
        PROMPTFOO,
        eval_name="support_response_quality",
        subject_revision="git:feedfacefeedfacefeedfacefeedfacefeedface",
    )
    metrics = imported["evals"]["support_response_quality"]["metrics"]
    assert metrics["pass_rate"] == 0.8
    assert metrics["response_safety_score"] > 0.9
    assert imported["provenance"]["producer"]["name"] == "promptfoo"
    assert imported["provenance"]["subject_revision"].startswith("git:feedface")
    assert len(imported["provenance"]["report_sha256"]) == 64

    report = evaluate_document_evals(
        _document(), results=imported, repo=EXAMPLE_DIR
    )
    assert report["status"] in {"passed", "passed_with_integrity_warnings"}
    assert report["summary"]["failed_metrics"] == 0
    assert report["summary"]["passed_metrics"] == 4
    assert report["safety"]["network_used"] is False


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda payload: payload.pop("results"),
        lambda payload: payload["results"].pop("stats"),
        lambda payload: payload["results"].update({"results": []}),
        lambda payload: payload["results"]["stats"].update({"successes": 99}),
        lambda payload: payload["results"]["results"][0].update({"score": "high"}),
        lambda payload: payload["results"]["results"][0]["namedScores"].update(
            {"response_safety_score": "high"}
        ),
    ],
)
def test_promptfoo_import_rejects_malformed_reports(
    tmp_path: Path, corrupt
) -> None:
    payload = json.loads(PROMPTFOO.read_text(encoding="utf-8"))
    corrupt(payload)
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(EvalImportError):
        convert_promptfoo_results(broken, eval_name="support_response_quality")


def test_eval_import_cli_round_trip(tmp_path: Path) -> None:
    out_path = tmp_path / "imported.json"
    stdout = StringIO()
    with redirect_stdout(stdout):
        code = cli_main(
            [
                "eval-import",
                "promptfoo",
                str(PROMPTFOO),
                "--eval-name",
                "support_response_quality",
                "--subject-revision",
                "git:feedfacefeedfacefeedfacefeedfacefeedface",
                "--out",
                str(out_path),
            ]
        )
    assert code == 0
    stdout = StringIO()
    with redirect_stdout(stdout):
        code = cli_main(
            [
                "eval-run",
                str(CONTRACT),
                "--results",
                str(out_path),
                "--repo",
                str(EXAMPLE_DIR),
                "--strict",
            ]
        )
    assert code == 0, stdout.getvalue()


def _documented_cli_invocations() -> set[tuple[str, ...]]:
    pattern = re.compile(r"^\s*nornyx\s+([a-z-]+(?:\s+[a-z-]+)?)", re.MULTILINE)
    sources = [ROOT / "README.md", *sorted(DOCS.glob("*.md"))]
    found: set[tuple[str, ...]] = set()
    for source in sources:
        for match in pattern.finditer(source.read_text(encoding="utf-8")):
            found.add(tuple(match.group(1).split()))
    return found


def test_documented_commands_exist_in_the_cli() -> None:
    parser = build_parser()
    subparsers = next(
        action
        for action in parser._actions
        if hasattr(action, "choices") and action.choices
    )
    top_level = dict(subparsers.choices)
    for invocation in _documented_cli_invocations():
        command = invocation[0]
        assert command in top_level, invocation
        if len(invocation) > 1:
            nested = next(
                (
                    action
                    for action in top_level[command]._actions
                    if hasattr(action, "choices") and action.choices
                ),
                None,
            )
            if nested is not None and invocation[1] in nested.choices:
                continue
            # A second token may be a positional argument, not a subcommand.
            assert nested is None or invocation[1] not in {"missing"}


def test_documented_files_exist() -> None:
    referenced = [
        "examples/agentic_network_support/support_network.nyx",
        "examples/agentic_network_support/run_demo.py",
        "examples/agentic_network_support/eval/promptfoo_results.json",
        "scripts/agentic_network_ci.py",
        "integrations/nornyx_agentic_adapters/governance_kernel.py",
        "integrations/nornyx_agentic_adapters/crewai_adapter.py",
        "integrations/nornyx_agentic_adapters/langgraph_adapter.py",
        "docs/agentic-network/00_OVERVIEW.md",
        "docs/agentic-network/01_TUTORIAL.md",
        "docs/agentic-network/02_CREWAI_GUIDE.md",
        "docs/agentic-network/03_LANGGRAPH_GUIDE.md",
        "docs/agentic-network/04_EXTERNAL_EVAL_EVIDENCE.md",
        "docs/agentic-network/05_PROTOCOL_DECLARATIONS.md",
        "docs/agentic-network/06_RUNTIME_EVIDENCE.md",
        "docs/agentic-network/07_NETWORK_LOCK.md",
        "docs/agentic-network/08_SECURITY_BOUNDARIES.md",
        "docs/agentic-network/09_TROUBLESHOOTING.md",
        "docs/agentic-network/10_BEFORE_AFTER_AND_POSITIONING.md",
        "docs/agentic-network/11_REFERENCE_CI.md",
    ]
    for relative in referenced:
        assert (ROOT / relative).is_file(), relative


def test_documentation_avoids_prohibited_claims() -> None:
    prohibited = [
        "enterprise-grade",
        "production ready",
        "production-ready",
        "fully secure",
        "protocol certified",
        "proves runtime truth",
        "prevents all agent violations",
        "complete runtime governance",
    ]
    for source in [ROOT / "README.md", *sorted(DOCS.glob("*.md"))]:
        text = source.read_text(encoding="utf-8").casefold()
        for phrase in prohibited:
            assert phrase not in text, (source.name, phrase)


def test_reference_ci_workflow_passes_offline(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "agentic_network_ci.py"),
            "--out",
            str(tmp_path / "ci"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    audit = tmp_path / "ci" / "audit-package"
    manifest = json.loads(
        (audit / "audit_manifest.json").read_text(encoding="utf-8")
    )
    assert "nornyx.agentic_network.lock" in manifest["contents"]
    assert "demo_summary.json" in manifest["contents"]
    assert "crewai_evidence_report.json" in manifest["contents"]
    assert "langgraph_evidence_report.json" in manifest["contents"]
    assert any(item.startswith("artifacts/") for item in manifest["contents"])
