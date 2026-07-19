from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import yaml

from . import __version__
from .adoption import adoption_status, write_lite_nyx
from .agentic_artifacts import (
    DEFAULT_ARTIFACT_DIR,
    DEFAULT_LOCK_NAME,
    agentic_network_lock_digest,
    build_agentic_network_lock,
    load_agentic_network_lock,
    verify_agentic_network_lock,
    write_agentic_network_artifacts,
    write_agentic_network_lock,
)
from .agentic_evidence import load_runtime_events, validate_runtime_events
from .checker import check_document, has_errors
from .connector_runtime import (
    ConnectorRuntimeError,
    build_connector_report,
    write_connector_report,
)
from .context_builder import build_context_pack, write_context_pack
from .doctor import doctor_json, format_doctor, run_doctor
from .eval_runtime import (
    EvalRuntimeError,
    evaluate_document_evals,
    load_eval_results,
    write_eval_report,
)
from .editor_tools import (
    completion_items,
    document_symbols,
    editor_manifest,
    lsp_diagnostics_for_file,
    syntax_highlighting_spec,
    write_json_payload,
)
from .evidence import create_evidence_pack
from .explain import explain_document
from .fmt import format_file
from .generator import generate_artifacts
from .goals import write_goal_plan
from .governance import (
    GovernanceError,
    GovernanceModule,
    GovernanceRegistry,
    ProfilePack,
    compose_document_governance,
    compose_governance,
    evaluate_document_governance,
    load_local_pack,
    load_lock,
    lock_for_packs,
    registry_for_contract,
    registry_for_directory,
    validate_governance_evidence_file,
    write_lock,
)
from .governance.errors import error as governance_error
from .governance.loader import inspect_local_file, reject_remote_or_device_path
from .governance.locks import GovernanceLockError
from .governance.reporting import build_governance_report
from .governed_package import (
    generate_governed_package,
    radar_governed_packages,
    register_existing_package,
    validate_governed_package_source,
)
from .harness_runtime import HarnessRuntimeError, run_harness
from .language_evolution import build_language_evolution_report, write_language_evolution_report
from .package_scanner import parse_gitleaks_report, parse_syft_report, scan_package, write_json
from .parser import NornyxParseError, load_nyx
from .policy_runtime import PolicyRuntimeError, evaluate_harness_policy, write_policy_report
from .profiles import PROFILE_NAMES, render_profile_document, write_profile
from .release_readiness import (
    build_release_readiness_report,
    build_stable_language_report,
    write_release_readiness_report,
)
from .repo_drift import check_repo_drift, format_repo_drift
from .workspace import (
    WorkspaceError,
    check_workspace,
    format_workspace,
    format_workspace_failures,
)
from .schema_model import (
    FORMAL_GRAMMAR_V0_1,
    SCHEMA_REGISTRY,
    schema_model_summary,
    validate_schema_model,
)


PACKAGE_RADAR_REPORT_DEFAULT = "dist/radar_report.json"
PACKAGE_RADAR_CONTRACT_DEFAULT = "dist/radar_suggested.nyx"


def _absolute_contract_path(path: str | Path) -> tuple[Path, Path]:
    reject_remote_or_device_path(path, code_prefix="PACK", noun="Contract")
    supplied = Path(path)
    trust_root = Path(supplied.anchor) if supplied.is_absolute() else Path.cwd()
    contract = supplied if supplied.is_absolute() else Path.cwd() / supplied
    return contract, trust_root


def _optional_profile_lock(directory: Path, *, trust_root: Path) -> Path | None:
    try:
        return inspect_local_file(
            directory / "nornyx.profiles.lock",
            allowed_root=directory,
            trust_root=trust_root,
            code_prefix="PACK",
            noun="Profile lock",
            allow_missing=True,
        )
    except GovernanceError as exc:
        raise GovernanceLockError(*exc.diagnostics) from exc


def cmd_check(args: argparse.Namespace) -> int:
    try:
        registry = registry_for_contract(args.file)
    except GovernanceError as exc:
        for diag in exc.diagnostics:
            print(json.dumps(diag.to_dict(), indent=2))
        return 1
    try:
        doc = load_nyx(args.file)
    except NornyxParseError as exc:
        print(json.dumps({"level": "error", "code": "PARSE_ERROR", "message": str(exc)}, indent=2))
        return 2
    diagnostics = list(check_document(doc))
    try:
        contract_path, trust_root = _absolute_contract_path(args.file)
        contract_path = Path(os.path.realpath(contract_path))
        document_root = contract_path.parent
        lock_path = _optional_profile_lock(document_root, trust_root=trust_root)
        composition = compose_document_governance(
            doc,
            registry=registry,
            lock_path=lock_path,
        )
        if composition is not None:
            contributed_blocks = {item.block for item in composition.block_schemas}
            diagnostics = [
                item
                for item in diagnostics
                if not (
                    item.code == "UNKNOWN_TOP_LEVEL_BLOCK"
                    and item.path in contributed_blocks
                )
            ]
        diagnostics.extend(
            evaluate_document_governance(
                doc,
                registry=registry,
                lock_path=lock_path,
                as_of=datetime.now(timezone.utc).isoformat(),
                document_root=document_root,
            )
        )
    except GovernanceError as exc:
        diagnostics.extend(exc.diagnostics)
    for diag in diagnostics:
        print(json.dumps(diag.to_dict(), indent=2))
    if has_errors(diagnostics):
        return 1
    print("Nornyx check passed")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    doc = load_nyx(args.file)
    diagnostics = check_document(doc)
    if has_errors(diagnostics):
        for diag in diagnostics:
            print(json.dumps(diag.to_dict(), indent=2))
        return 1
    paths = generate_artifacts(doc, args.out)
    print(f"Generated {len(paths)} artifacts in {args.out}")
    for path in paths:
        print(path)
    return 0


def cmd_package_generate(args: argparse.Namespace) -> int:
    try:
        paths = generate_governed_package(args.file, args.out)
    except (ValueError, NornyxParseError) as exc:
        print(json.dumps({"level": "error", "code": "PACKAGE_GENERATE_ERROR", "message": str(exc)}, indent=2))
        return 1
    print(f"Generated inert governed package with {len(paths)} artifacts in {args.out}")
    for path in paths:
        print(path)
    return 0


def cmd_package_validate(args: argparse.Namespace) -> int:
    try:
        diagnostics = validate_governed_package_source(args.path)
    except (ValueError, NornyxParseError, json.JSONDecodeError) as exc:
        print(json.dumps({"level": "error", "code": "PACKAGE_VALIDATE_ERROR", "message": str(exc)}, indent=2))
        return 1
    if args.json:
        payload = {"status": "fail" if has_errors(diagnostics) else "pass", "diagnostics": [d.to_dict() for d in diagnostics]}
        print(json.dumps(payload, indent=2))
    else:
        for diag in diagnostics:
            print(json.dumps(diag.to_dict(), indent=2))
        if not has_errors(diagnostics):
            print("Nornyx governed package validation passed")
    return 1 if has_errors(diagnostics) else 0


def cmd_package_register(args: argparse.Namespace) -> int:
    try:
        paths = register_existing_package(args.source, args.out, contract=args.contract)
    except (ValueError, NornyxParseError) as exc:
        print(json.dumps({"level": "error", "code": "PACKAGE_REGISTER_ERROR", "message": str(exc)}, indent=2))
        return 1
    print(f"Registered existing artifact set with {len(paths)} outputs in {args.out}")
    for path in paths:
        print(path)
    return 0


def cmd_package_radar(args: argparse.Namespace) -> int:
    try:
        out = args.out
        if args.suggest_contract and out == PACKAGE_RADAR_REPORT_DEFAULT:
            out = PACKAGE_RADAR_CONTRACT_DEFAULT
        report = radar_governed_packages(args.source, out, suggest_contract=args.suggest_contract)
    except ValueError as exc:
        print(json.dumps({"level": "error", "code": "PACKAGE_RADAR_ERROR", "message": str(exc)}, indent=2))
        return 1
    print(json.dumps({"status": "pass", "report_path": report["report_path"], "candidate_count": len(report["candidate_packages"])}, indent=2))
    return 0


def cmd_package_scan(args: argparse.Namespace) -> int:
    try:
        report = scan_package(args.source, out_dir=args.out, package_id=args.package_id)
    except ValueError as exc:
        print(json.dumps({"level": "error", "code": "PACKAGE_SCAN_ERROR", "message": str(exc)}, indent=2))
        return 1
    print(
        json.dumps(
            {
                "status": "pass",
                "out": str(Path(args.out)),
                "package_id": report["package_id"],
                "risk_tier": report["risk_surface"]["risk_tier"],
                "total_files_scanned": report["summary"]["total_files_scanned"],
                "package_payload_executed": False,
            },
            indent=2,
        )
    )
    return 0


def cmd_package_evidence_import(args: argparse.Namespace) -> int:
    tool = args.tool.lower()
    parsers = {"syft": parse_syft_report, "gitleaks": parse_gitleaks_report}
    parser = parsers.get(tool)
    if parser is None:
        print(
            json.dumps(
                {
                    "level": "error",
                    "code": "UNSUPPORTED_EVIDENCE_TOOL",
                    "message": f"unsupported evidence tool: {args.tool}",
                },
                indent=2,
            )
        )
        return 1
    try:
        reject_remote_or_device_path(
            args.report_path,
            code_prefix="PACKAGE",
            noun="External evidence report",
        )
        reject_remote_or_device_path(
            args.out,
            code_prefix="PACKAGE",
            noun="External evidence output",
        )
        records = parser(Path(args.report_path), args.package_id)
        payload = {
            "status": "pass",
            "tool": tool,
            "package_id": args.package_id,
            "evidence_count": len(records),
            "evidence": records,
        }
        out_path = Path(args.out)
        if out_path.suffix.lower() != ".json":
            out_path = out_path / f"{tool}_normalized_evidence.json"
        write_json(out_path, payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"level": "error", "code": "EVIDENCE_IMPORT_ERROR", "message": str(exc)}, indent=2))
        return 1
    print(json.dumps({"status": "pass", "out": out_path.as_posix(), "evidence_count": len(records)}, indent=2))
    return 0


def cmd_drift(args: argparse.Namespace) -> int:
    report = check_repo_drift(args.file, args.out)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_repo_drift(report))
    return 0 if report["status"] == "pass" else 1


def cmd_workspace_check(args: argparse.Namespace) -> int:
    try:
        report = check_workspace(args.manifest, write=args.write)
    except (WorkspaceError, NornyxParseError) as exc:
        print(json.dumps({"level": "error", "code": "WORKSPACE_ERROR", "message": str(exc)}, indent=2))
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    elif args.quiet:
        if report["status"] not in ("pass", "synced"):
            failures = format_workspace_failures(report)
            if failures:
                print(failures)
    else:
        print(format_workspace(report))
    # `synced` means we fixed divergence on disk: success for `--write`.
    return 0 if report["status"] in ("pass", "synced") else 1


def cmd_goal_plan(args: argparse.Namespace) -> int:
    doc = load_nyx(args.file)
    diagnostics = check_document(doc)
    if has_errors(diagnostics):
        for diag in diagnostics:
            print(json.dumps(diag.to_dict(), indent=2))
        return 1
    paths = write_goal_plan(doc, args.out)
    print(f"Generated {len(paths)} goal-plan artifacts in {args.out}")
    for path in paths:
        print(path)
    return 0


def cmd_schema(args: argparse.Namespace) -> int:
    if args.format == "grammar":
        print(FORMAL_GRAMMAR_V0_1)
        return 0
    summary = schema_model_summary(args.version)
    issues = validate_schema_model(args.version)
    payload = {"summary": summary, "issues": issues}
    print(json.dumps(payload, indent=2))
    return 1 if issues else 0


def cmd_context_build(args: argparse.Namespace) -> int:
    doc = load_nyx(args.file)
    pack = build_context_pack(doc, args.repo, include_content=args.include_content)
    path = write_context_pack(pack, args.out)
    print(f"Context pack written to {path} with {pack['count']} entries")
    return 0


def cmd_harness_run(args: argparse.Namespace) -> int:
    try:
        doc = load_nyx(args.file)
        diagnostics = check_document(doc)
        if has_errors(diagnostics):
            for diag in diagnostics:
                print(json.dumps(diag.to_dict(), indent=2))
            return 1
        manifest = run_harness(
            doc,
            args.repo,
            args.out,
            harness_name=args.harness,
            include_content=args.include_content,
        )
    except (NornyxParseError, HarnessRuntimeError) as exc:
        print(
            json.dumps(
                {"level": "error", "code": "HARNESS_RUN_ERROR", "message": str(exc)},
                indent=2,
            )
        )
        return 1
    print(f"Harness run manifest written to {Path(args.out) / 'run_manifest.json'}")
    print(json.dumps({"harness": manifest["harness"], "status": manifest["status"]}, indent=2))
    return 0


def cmd_policy_check(args: argparse.Namespace) -> int:
    try:
        doc = load_nyx(args.file)
        diagnostics = check_document(doc)
        if has_errors(diagnostics):
            for diag in diagnostics:
                print(json.dumps(diag.to_dict(), indent=2))
            return 1
        report = evaluate_harness_policy(doc, harness_name=args.harness)
    except (NornyxParseError, PolicyRuntimeError) as exc:
        print(
            json.dumps(
                {"level": "error", "code": "POLICY_CHECK_ERROR", "message": str(exc)},
                indent=2,
            )
        )
        return 1
    if args.out:
        path = write_policy_report(report, args.out)
        print(f"Policy report written to {path}")
    print(
        json.dumps(
            {
                "harness": report["harness"],
                "default_capability_mode": report["default_capability_mode"],
                "summary": report["summary"],
            },
            indent=2,
        )
    )
    return 0


def cmd_eval_run(args: argparse.Namespace) -> int:
    try:
        doc = load_nyx(args.file)
        diagnostics = check_document(doc)
        if has_errors(diagnostics):
            for diag in diagnostics:
                print(json.dumps(diag.to_dict(), indent=2))
            return 1
        results = load_eval_results(args.results) if args.results else None
        report = evaluate_document_evals(
            doc,
            eval_names=args.eval,
            results=results,
            repo=args.repo,
        )
    except (NornyxParseError, EvalRuntimeError) as exc:
        print(
            json.dumps(
                {"level": "error", "code": "EVAL_RUN_ERROR", "message": str(exc)},
                indent=2,
            )
        )
        return 1
    if args.out:
        path = write_eval_report(report, args.out)
        print(f"Eval report written to {path}")
    print(
        json.dumps(
            {
                "status": report["status"],
                "summary": report["summary"],
            },
            indent=2,
        )
    )
    if args.strict and report["status"] in {"blocked_integrity", "failed", "invalid"}:
        return 1
    return 0


def cmd_connector_plan(args: argparse.Namespace) -> int:
    try:
        doc = load_nyx(args.file)
        diagnostics = check_document(doc)
        if has_errors(diagnostics):
            for diag in diagnostics:
                print(json.dumps(diag.to_dict(), indent=2))
            return 1
        report = build_connector_report(doc)
    except (NornyxParseError, ConnectorRuntimeError) as exc:
        print(
            json.dumps(
                {"level": "error", "code": "CONNECTOR_PLAN_ERROR", "message": str(exc)},
                indent=2,
            )
        )
        return 1
    if args.out:
        path = write_connector_report(report, args.out)
        print(f"Connector report written to {path}")
    print(
        json.dumps(
            {
                "status": report["status"],
                "summary": report["summary"],
            },
            indent=2,
        )
    )
    if args.strict and report["status"] == "blocked":
        return 1
    return 0


def cmd_editor_manifest(args: argparse.Namespace) -> int:
    payload = editor_manifest()
    if args.out:
        path = write_json_payload(payload, args.out)
        print(f"Editor manifest written to {path}")
    print(json.dumps(payload, indent=2))
    return 0


def cmd_syntax(args: argparse.Namespace) -> int:
    payload = syntax_highlighting_spec()
    if args.out:
        path = write_json_payload(payload, args.out)
        print(f"Syntax highlighting spec written to {path}")
    print(json.dumps(payload, indent=2))
    return 0


def cmd_lsp_diagnostics(args: argparse.Namespace) -> int:
    payload = lsp_diagnostics_for_file(args.file)
    if args.out:
        path = write_json_payload(payload, args.out)
        print(f"LSP diagnostics written to {path}")
    print(json.dumps(payload, indent=2))
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    doc = None
    if args.file:
        try:
            doc = load_nyx(args.file)
        except NornyxParseError:
            doc = None
    payload = completion_items(doc, path=args.path, prefix=args.prefix)
    if args.out:
        path = write_json_payload(payload, args.out)
        print(f"Completion items written to {path}")
    print(json.dumps(payload, indent=2))
    return 0


def cmd_symbols(args: argparse.Namespace) -> int:
    try:
        doc = load_nyx(args.file)
    except NornyxParseError as exc:
        print(json.dumps({"level": "error", "code": "PARSE_ERROR", "message": str(exc)}, indent=2))
        return 2
    payload = document_symbols(doc)
    if args.out:
        path = write_json_payload(payload, args.out)
        print(f"Document symbols written to {path}")
    print(json.dumps(payload, indent=2))
    return 0


def cmd_release_check(args: argparse.Namespace) -> int:
    report = build_release_readiness_report(
        args.repo,
        target_version=args.target_version,
        approved=args.approved,
    )
    if args.out:
        path = write_release_readiness_report(report, args.out)
        print(f"Release readiness report written to {path}")
    print(
        json.dumps(
            {
                "status": report["status"],
                "target_version": report["target_version"],
                "summary": report["summary"],
            },
            indent=2,
        )
    )
    if args.strict and report["status"] == "blocked":
        return 1
    return 0


def cmd_stable_language_check(args: argparse.Namespace) -> int:
    report = build_stable_language_report(
        args.repo,
        target_version=args.target_version,
        approved=args.approved,
    )
    if args.out:
        path = write_release_readiness_report(report, args.out)
        print(f"Stable language report written to {path}")
    print(
        json.dumps(
            {
                "status": report["status"],
                "target_version": report["target_version"],
                "summary": report["summary"],
            },
            indent=2,
        )
    )
    if args.strict and report["status"] == "blocked":
        return 1
    return 0


def cmd_language_evolution(args: argparse.Namespace) -> int:
    report = build_language_evolution_report(args.repo)
    if args.out:
        path = write_language_evolution_report(report, args.out)
        print(f"Language evolution report written to {path}")
    print(
        json.dumps(
            {
                "status": report["status"],
                "summary": report["summary"],
                "recommended_next_goal": report["recommended_next_goal"],
            },
            indent=2,
        )
    )
    if args.strict and report["summary"]["blocking_issues"]:
        return 1
    return 0


def _agentic_document_and_composition(
    args: argparse.Namespace,
) -> tuple[dict, "object"]:
    """Load, fully validate, and compose one agentic-network contract.

    Raises SystemExit-style tuples via ValueError paths; callers translate
    GovernanceError/NornyxParseError into diagnostics output.
    """

    registry = registry_for_contract(args.file)
    doc = load_nyx(args.file)
    contract_path, trust_root = _absolute_contract_path(args.file)
    contract_path = Path(os.path.realpath(contract_path))
    document_root = contract_path.parent
    lock_path = _optional_profile_lock(document_root, trust_root=trust_root)
    as_of = getattr(args, "as_of", None) or datetime.now(timezone.utc).isoformat()
    diagnostics = list(check_document(doc))
    composition = compose_document_governance(
        doc,
        registry=registry,
        lock_path=lock_path,
    )
    if composition is not None:
        contributed_blocks = {item.block for item in composition.block_schemas}
        diagnostics = [
            item
            for item in diagnostics
            if not (
                item.code == "UNKNOWN_TOP_LEVEL_BLOCK"
                and item.path in contributed_blocks
            )
        ]
    diagnostics.extend(
        evaluate_document_governance(
            doc,
            registry=registry,
            lock_path=lock_path,
            as_of=as_of,
            document_root=document_root,
        )
    )
    if has_errors(diagnostics):
        raise GovernanceError(*[d for d in diagnostics if d.level == "error"])
    if composition is None:
        raise governance_error(
            "AN_ARTIFACT_PROFILE_MISSING",
            "Agentic-network commands require a resolved governance profile.",
            path="project.profile",
        )
    return doc, composition


def cmd_agentic_network_generate(args: argparse.Namespace) -> int:
    try:
        doc, composition = _agentic_document_and_composition(args)
        paths = write_agentic_network_artifacts(doc, composition, args.out)
    except NornyxParseError as exc:
        print(json.dumps({"level": "error", "code": "PARSE_ERROR", "message": str(exc)}, indent=2))
        return 2
    except GovernanceError as exc:
        _print_pack_error(exc, as_json=getattr(args, "json", False))
        return 1
    payload = {
        "status": "pass",
        "out": Path(args.out).as_posix(),
        "artifact_count": len(paths),
        "artifacts": [path.name for path in paths],
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_agentic_network_lock(args: argparse.Namespace) -> int:
    try:
        doc, composition = _agentic_document_and_composition(args)
        lock_payload = build_agentic_network_lock(doc, composition)
        mismatches = verify_agentic_network_lock(
            lock_payload,
            doc,
            composition,
            artifacts_dir=args.artifacts,
        )
        if mismatches:
            payload = {
                "status": "fail",
                "diagnostics": [item.to_dict() for item in mismatches],
            }
            print(json.dumps(payload, indent=2))
            return 1
        written = write_agentic_network_lock(lock_payload, args.out)
    except NornyxParseError as exc:
        print(json.dumps({"level": "error", "code": "PARSE_ERROR", "message": str(exc)}, indent=2))
        return 2
    except GovernanceError as exc:
        _print_pack_error(exc, as_json=getattr(args, "json", False))
        return 1
    payload = {
        "status": "pass",
        "lock_path": Path(written).as_posix(),
        "lock_digest": agentic_network_lock_digest(lock_payload),
        "artifact_count": len(lock_payload["artifacts"]),
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_agentic_network_lock_check(args: argparse.Namespace) -> int:
    try:
        doc, composition = _agentic_document_and_composition(args)
        lock_payload = load_agentic_network_lock(args.lock)
        diagnostics = verify_agentic_network_lock(
            lock_payload,
            doc,
            composition,
            artifacts_dir=args.artifacts,
        )
    except NornyxParseError as exc:
        print(json.dumps({"level": "error", "code": "PARSE_ERROR", "message": str(exc)}, indent=2))
        return 2
    except GovernanceError as exc:
        _print_pack_error(exc, as_json=getattr(args, "json", False))
        return 1
    payload = {
        "schema": "nornyx.agentic_network_lock_check.v1",
        "status": "fail" if diagnostics else "pass",
        "lock_digest": agentic_network_lock_digest(lock_payload),
        "diagnostics": [item.to_dict() for item in diagnostics],
    }
    print(json.dumps(payload, indent=2))
    return 1 if diagnostics else 0


def cmd_agentic_network_evidence_validate(args: argparse.Namespace) -> int:
    try:
        doc, composition = _agentic_document_and_composition(args)
        lock_payload = load_agentic_network_lock(args.lock)
        events_payload, events_root = load_runtime_events(args.events)
        report = validate_runtime_events(
            doc,
            composition,
            lock_payload,
            events_payload,
            events_root=events_root,
        )
    except NornyxParseError as exc:
        print(json.dumps({"level": "error", "code": "PARSE_ERROR", "message": str(exc)}, indent=2))
        return 2
    except GovernanceError as exc:
        _print_pack_error(exc, as_json=getattr(args, "json", False))
        return 1
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"Evidence report written to {out_path.as_posix()}")
    print(
        json.dumps(
            {
                "status": report["status"],
                "event_count": report["event_count"],
                "mission_count": report["mission_count"],
                "diagnostic_count": len(report["diagnostics"]),
            },
            indent=2,
        )
    )
    if args.strict and report["status"] != "pass":
        return 1
    return 0


def cmd_evidence_pack(args: argparse.Namespace) -> int:
    paths = create_evidence_pack(args.out)
    print(f"Evidence scaffold written to {args.out}")
    for path in paths:
        print(path)
    return 0


def _print_pack_error(exc: GovernanceError, *, as_json: bool) -> None:
    payload = {
        "status": "error",
        "diagnostics": [item.to_dict() for item in exc.diagnostics],
    }
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        for item in exc.diagnostics:
            print(f"{item.code}: {item.message}")


def _explicit_pack_path_and_trust_root(path: str | Path) -> tuple[Path, Path]:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate, Path(candidate.anchor)
    trust_root = Path.cwd()
    return trust_root / candidate, trust_root


def _reject_remote_cli_path(path: str | Path, *, code_prefix: str, noun: str) -> None:
    reject_remote_or_device_path(path, code_prefix=code_prefix, noun=noun)


def cmd_profiles(args: argparse.Namespace) -> int:
    command = getattr(args, "profiles_command", None)
    as_json = getattr(args, "json", False)
    registry = (
        GovernanceRegistry()
        if command in {"resolve", "validate"}
        else GovernanceRegistry.builtins()
    )
    if command is None:
        for name in PROFILE_NAMES:
            print(name)
        return 0
    try:
        if command == "list":
            entries = []
            for name in registry.profile_names:
                profile = registry.resolve_profile(name)
                entries.append(
                    {
                        "name": profile.name,
                        "id": profile.id,
                        "version": profile.version,
                        "status": profile.status,
                        "source_tier": profile.provenance.source_tier,
                    }
                )
            if as_json:
                print(json.dumps({"status": "ok", "profiles": entries}, indent=2))
            else:
                for item in entries:
                    print(
                        f"{item['name']} {item['version']} {item['status']} "
                        f"({item['source_tier']})"
                    )
            return 0
        if command == "inspect":
            profile = registry.resolve_profile(args.name)
            payload = profile.as_dict()
            payload["resolved_provenance"] = profile.provenance.to_dict()
            payload["resolved_content_hash"] = profile.content_hash
            print(
                json.dumps({"status": "ok", "profile": payload}, indent=2)
                if as_json
                else yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).rstrip()
            )
            return 0
        if command == "validate":
            _reject_remote_cli_path(args.path, code_prefix="PACK", noun="Pack")
            path, trust_root = _explicit_pack_path_and_trust_root(args.path)
            pack = load_local_pack(
                path,
                allowed_root=path.parent,
                trust_root=trust_root,
            )
            payload = {
                "status": "valid",
                "kind": "profile" if isinstance(pack, ProfilePack) else "module",
                "id": pack.id,
                "version": pack.version,
                "content_hash": pack.content_hash,
                "path": path.as_posix(),
            }
            print(json.dumps(payload, indent=2) if as_json else f"Valid {payload['kind']}: {pack.id}@{pack.version}")
            return 0
        if command == "resolve":
            # Resolution sees the same discovery tiers as `nornyx check`:
            # project-local .nornyx/{profiles,modules} under the current
            # directory, then built-ins. An existing lock is verified unless
            # --lock explicitly regenerates it; a mismatch exits 2.
            resolve_registry = registry_for_directory(Path.cwd())
            lock_file = Path.cwd() / "nornyx.profiles.lock"
            existing_lock = None
            if not args.lock:
                discovered_lock = _optional_profile_lock(
                    Path.cwd(),
                    trust_root=Path.cwd(),
                )
                if discovered_lock is not None:
                    existing_lock = load_lock(
                        discovered_lock,
                        allowed_root=Path.cwd(),
                        trust_root=Path.cwd(),
                    )
            try:
                result = compose_governance(
                    resolve_registry,
                    profile_identity=args.name,
                    lock=existing_lock,
                )
            except GovernanceError as exc:
                _print_pack_error(exc, as_json=as_json)
                return 2 if _is_lock_failure(exc) else 1
            payload = result.to_dict()
            payload["status"] = "resolved"
            payload["resolution_trace"] = list(resolve_registry.resolution_trace)
            payload["lock_verified"] = existing_lock is not None
            if args.lock:
                lock = lock_for_packs([*result.modules, result.profile])
                lock_path = write_lock(lock_file, lock)
                payload["lock_path"] = lock_path.as_posix()
            print(
                json.dumps(payload, indent=2)
                if as_json
                else yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).rstrip()
            )
            return 0
        if command == "compatibility":
            profiles = [registry.resolve_profile(name) for name in args.names]
            selected_ids = {item.id for item in profiles}
            selected_names = {item.name for item in profiles}
            conflicts: set[tuple[str, str]] = set()
            review: set[tuple[str, str]] = set()
            for profile in profiles:
                raw = profile.raw
                for identity in raw["conflicts"]:
                    if identity in selected_ids or identity in selected_names:
                        conflicts.add(tuple(sorted((profile.name, identity))))
                for identity in raw["compatibility"]["requires_review_with"]:
                    if identity in selected_ids or identity in selected_names:
                        review.add(tuple(sorted((profile.name, identity))))
            payload = {
                "status": "conflict" if conflicts else "compatible",
                "profiles": [item.name for item in profiles],
                "conflicts": [list(item) for item in sorted(conflicts)],
                "requires_review": [list(item) for item in sorted(review)],
            }
            print(
                json.dumps(payload, indent=2)
                if as_json
                else yaml.safe_dump(payload, sort_keys=False).rstrip()
            )
            return 1 if conflicts else 0
    except GovernanceError as exc:
        _print_pack_error(exc, as_json=as_json)
        return 2 if _is_lock_failure(exc) else 1
    raise ValueError(f"Unsupported profiles command {command!r}")


def cmd_modules(args: argparse.Namespace) -> int:
    command = args.modules_command
    as_json = args.json
    try:
        if command == "validate":
            _reject_remote_cli_path(args.path, code_prefix="PACK", noun="Pack")
            registry = GovernanceRegistry()
        else:
            registry = registry_for_directory(Path.cwd())
        if command == "list":
            modules = []
            for name in registry.module_names:
                module = registry.resolve_module(name)
                modules.append(
                    {
                        "name": module.name,
                        "id": module.id,
                        "version": module.version,
                        "dependencies": list(module.dependencies),
                        "source_tier": module.provenance.source_tier,
                        "content_hash": module.content_hash,
                    }
                )
            payload = {"status": "ok", "modules": modules}
            print(
                json.dumps(payload, indent=2)
                if as_json
                else yaml.safe_dump(payload, sort_keys=False).rstrip()
            )
            return 0
        if command == "inspect":
            module = registry.resolve_module(args.name)
            payload = module.as_dict()
            payload["resolved_provenance"] = module.provenance.to_dict()
            payload["resolved_content_hash"] = module.content_hash
            output = {"status": "ok", "module": payload}
            print(
                json.dumps(output, indent=2)
                if as_json
                else yaml.safe_dump(output, sort_keys=False, allow_unicode=True).rstrip()
            )
            return 0
        if command == "validate":
            _reject_remote_cli_path(args.path, code_prefix="PACK", noun="Pack")
            path, trust_root = _explicit_pack_path_and_trust_root(args.path)
            pack = load_local_pack(
                path,
                allowed_root=path.parent,
                trust_root=trust_root,
            )
            if not isinstance(pack, GovernanceModule):
                raise governance_error(
                    "PACK_KIND_MISMATCH",
                    "Module validation requires a governance module pack.",
                    path=path.as_posix(),
                    source_id=pack.id,
                )
            payload = {
                "status": "valid",
                "kind": "module",
                "id": pack.id,
                "version": pack.version,
                "dependencies": list(pack.dependencies),
                "content_hash": pack.content_hash,
                "path": path.as_posix(),
            }
            print(
                json.dumps(payload, indent=2)
                if as_json
                else yaml.safe_dump(payload, sort_keys=False).rstrip()
            )
            return 0
    except GovernanceError as exc:
        _print_pack_error(exc, as_json=as_json)
        return 1
    raise ValueError(f"Unsupported modules command {command!r}")


_LOCK_ERROR_CODES = {
    "PACK_LOCK_MISMATCH",
    "PACK_LOCK_SET_MISMATCH",
    "PACK_LOCK_DUPLICATE_ID",
    "PACK_LOCK_INVALID",
}


def _is_lock_failure(exc: GovernanceError) -> bool:
    return isinstance(exc, GovernanceLockError) or any(
        item.code in _LOCK_ERROR_CODES for item in exc.diagnostics
    )


def _governance_report_for_path(args: argparse.Namespace) -> dict[str, object]:
    registry = registry_for_contract(args.file)
    document = load_nyx(args.file)
    contract_path, trust_root = _absolute_contract_path(args.file)
    contract_path = Path(os.path.realpath(contract_path))
    lock_path = _optional_profile_lock(contract_path.parent, trust_root=trust_root)
    as_of = args.as_of or datetime.now(timezone.utc).isoformat()
    report = build_governance_report(
        document,
        registry=registry,
        lock_path=lock_path,
        as_of=as_of,
        document_root=contract_path.parent,
    )
    report["contract"] = contract_path.as_posix()
    report["validation_time"] = as_of
    return report


def cmd_governance(args: argparse.Namespace) -> int:
    as_json = args.json
    try:
        report = _governance_report_for_path(args)
    except NornyxParseError as exc:
        payload = {
            "status": "error",
            "diagnostics": [
                {"level": "error", "code": "PARSE_ERROR", "message": str(exc)}
            ],
        }
        print(
            json.dumps(payload, indent=2)
            if as_json
            else f"PARSE_ERROR: {exc}"
        )
        return 2
    except GovernanceError as exc:
        _print_pack_error(exc, as_json=as_json)
        return 2 if _is_lock_failure(exc) else 1

    if args.governance_command == "resolve":
        payload = report
    elif args.governance_command == "explain":
        payload = {
            "schema": report["schema"],
            "status": report["status"],
            "contract": report["contract"],
            "profile": report["profile"],
            "modules": report["modules"],
            "lock": report["lock"],
            "active_controls": report["active_controls"],
            "required_evidence": report["required_evidence"],
            "approval_requirements": report["approval_requirements"],
            "exception_status": report["exception_status"],
            "diagnostics": report["diagnostics"],
        }
    elif args.governance_command == "matrix":
        payload = {
            "schema": "nornyx.governance_matrix.v1",
            "status": report["status"],
            "contract": report["contract"],
            "lock": report["lock"],
            "matrix": report["matrix"],
            "diagnostics": report["diagnostics"],
        }
    else:
        raise ValueError(
            f"Unsupported governance command {args.governance_command!r}"
        )
    print(
        json.dumps(payload, indent=2)
        if as_json
        else yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).rstrip()
    )
    return 1 if report["status"] == "fail" else 0


def cmd_evidence(args: argparse.Namespace) -> int:
    as_json = args.json
    try:
        _reject_remote_cli_path(args.path, code_prefix="EVIDENCE", noun="Evidence")
        path, trust_root = _explicit_pack_path_and_trust_root(args.path)
        as_of = args.as_of or datetime.now(timezone.utc).isoformat()
        diagnostics = validate_governance_evidence_file(
            path,
            allowed_root=path.parent,
            trust_root=trust_root,
            as_of=as_of,
        )
        failed = any(item.level == "error" for item in diagnostics)
        payload = {
            "status": "fail" if failed else "pass",
            "path": path.as_posix(),
            "validation_time": as_of,
            "diagnostics": [item.to_dict() for item in diagnostics],
        }
        if as_json:
            print(json.dumps(payload, indent=2))
        elif diagnostics:
            print(yaml.safe_dump(payload, sort_keys=False).rstrip())
        else:
            print(f"Valid governance evidence: {path.as_posix()}")
        return 1 if failed else 0
    except GovernanceError as exc:
        _print_pack_error(exc, as_json=as_json)
        return 1


def cmd_doctor(args: argparse.Namespace) -> int:
    report = run_doctor(args.repo)
    print(doctor_json(report) if args.json else format_doctor(report))
    return 0 if report["ok"] else 1


def cmd_init(args: argparse.Namespace) -> int:
    try:
        if args.profile_path:
            _reject_remote_cli_path(
                args.profile_path,
                code_prefix="PACK",
                noun="Pack",
            )
            source, trust_root = _explicit_pack_path_and_trust_root(args.profile_path)
            pack = load_local_pack(
                source,
                allowed_root=source.parent,
                trust_root=trust_root,
            )
            if not isinstance(pack, ProfilePack):
                raise ValueError("--profile-path must identify a profile pack, not a module.")
            target = Path(args.out)
            if target.exists() and not args.force:
                raise FileExistsError(f"{target} already exists. Use --force to overwrite.")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                yaml.safe_dump(
                    render_profile_document(pack, args.name),
                    sort_keys=False,
                    allow_unicode=True,
                    width=100,
                ),
                encoding="utf-8",
            )
            path = target
        else:
            path = write_profile(
                args.out,
                args.profile or "ai_coding",
                args.name,
                force=args.force,
            )
    except (GovernanceError, ValueError, FileExistsError) as exc:
        print(json.dumps({"level": "error", "code": "INIT_ERROR", "message": str(exc)}, indent=2))
        return 1
    print(f"Nornyx project draft written to {path}")
    return 0


def cmd_examples(args: argparse.Namespace) -> int:
    from importlib import resources

    dest = Path(args.out)
    dest.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    src = resources.files("nornyx") / "examples"
    for entry in sorted(src.iterdir(), key=lambda e: e.name):
        if entry.name.endswith(".nyx"):
            target = dest / entry.name
            target.write_text(entry.read_text(encoding="utf-8"), encoding="utf-8")
            written.append(target)
    if not written:
        print(json.dumps({"level": "error", "code": "NO_EXAMPLES",
                          "message": "no bundled examples found"}, indent=2))
        return 1
    print(f"Wrote {len(written)} example(s) to {dest.as_posix()}/:")
    for w in written:
        print(f"  {w.as_posix()}")
    nudge = next((w for w in written if "governed_delivery" in w.name), written[0])
    print(f"Next: nornyx check {nudge.as_posix()}")
    return 0


def cmd_fmt(args: argparse.Namespace) -> int:
    rendered = format_file(args.file, write=args.write)
    current = Path(args.file).read_text(encoding="utf-8")
    if args.check and current != rendered:
        print(f"{args.file} is not formatted")
        return 1
    if not args.write and not args.check:
        print(rendered, end="")
    elif args.write:
        print(f"Formatted {args.file}")
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    try:
        doc = load_nyx(args.file)
    except NornyxParseError as exc:
        print(json.dumps({"level": "error", "code": "PARSE_ERROR", "message": str(exc)}, indent=2))
        return 2
    print(explain_document(doc, args.symbol, as_json=args.json))
    return 0


def cmd_adopt_status(args: argparse.Namespace) -> int:
    print(json.dumps(adoption_status(args.repo), indent=2))
    return 0


def cmd_adopt_init_lite(args: argparse.Namespace) -> int:
    try:
        path = write_lite_nyx(args.project, args.out, repo_root=args.repo, force=args.force)
    except FileExistsError as exc:
        print(json.dumps({"level": "error", "code": "FILE_EXISTS", "message": str(exc)}, indent=2))
        return 1
    print(f"Nornyx Lite draft written to {path}")
    print("Next: review, then run `python -m nornyx.cli check {}`".format(path))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nornyx", description="Nornyx v0.1 CLI scaffold")
    parser.add_argument("--version", action="version", version=f"nornyx {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check", help="Validate a .nyx file")
    p.add_argument("file")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("examples", help="Copy bundled .nyx examples into a directory")
    p.add_argument("--out", default="examples")
    p.set_defaults(func=cmd_examples)

    p = sub.add_parser("generate", help="Generate AGENTS.md, skills, harness, policy, evals, evidence contract")
    p.add_argument("file")
    p.add_argument("--out", default="generated")
    p.set_defaults(func=cmd_generate)

    package = sub.add_parser("package", help="Governed package profile commands")
    package_sub = package.add_subparsers(dest="package_command", required=True)

    p = package_sub.add_parser("scan", help="Run the built-in deterministic package scanner")
    p.add_argument("source")
    p.add_argument("--out", default="dist/package-scan")
    p.add_argument("--package-id", default="package")
    p.set_defaults(func=cmd_package_scan)

    p = package_sub.add_parser("generate", help="Generate an inert governed package from a .nyx contract")
    p.add_argument("file")
    p.add_argument("--out", default="dist/governed-package")
    p.set_defaults(func=cmd_package_generate)

    p = package_sub.add_parser("validate", help="Validate a governed package contract, manifest, or directory")
    p.add_argument("path")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_package_validate)

    p = package_sub.add_parser("register", help="Hash-lock and describe an existing artifact directory")
    p.add_argument("source")
    p.add_argument("--contract")
    p.add_argument("--out", default="dist/registered-package")
    p.set_defaults(func=cmd_package_register)

    p = package_sub.add_parser("radar", help="Propose governed package candidates from a folder")
    p.add_argument("source")
    p.add_argument("--out", default=PACKAGE_RADAR_REPORT_DEFAULT)
    p.add_argument("--suggest-contract", action="store_true")
    p.set_defaults(func=cmd_package_radar)

    evidence = package_sub.add_parser("evidence", help="Import external package evidence reports")
    evidence_sub = evidence.add_subparsers(dest="evidence_command", required=True)

    p = evidence_sub.add_parser("import", help="Normalize an external evidence report")
    p.add_argument("tool", choices=["syft", "gitleaks"])
    p.add_argument("report_path")
    p.add_argument("--package-id", default="package")
    p.add_argument("--out", default="dist/external-evidence")
    p.set_defaults(func=cmd_package_evidence_import)

    p = sub.add_parser(
        "drift",
        help="Full-output drift gate: compare a committed generated dir to a fresh generate",
    )
    p.add_argument("file")
    p.add_argument("--out", default="generated", help="Committed generated-artifact directory")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_drift)

    p = sub.add_parser(
        "workspace-check",
        help="Verify member repos' policies match a workspace's canonical standard",
    )
    p.add_argument("--manifest", default="nornyx.workspace.yaml")
    p.add_argument(
        "--write",
        action="store_true",
        help="Sync mode: rewrite each member's diverging policy to the canonical rules",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Only print failing members when drift is found",
    )
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_workspace_check)

    p = sub.add_parser("goal-plan", help="Generate a bounded goal plan from .nyx source")
    p.add_argument("file")
    p.add_argument("--out", default="generated/goal_plan")
    p.set_defaults(func=cmd_goal_plan)

    p = sub.add_parser("schema", help="Inspect the Nornyx schema model")
    p.add_argument("--format", choices=["json", "grammar"], default="json")
    p.add_argument(
        "--version",
        choices=sorted(SCHEMA_REGISTRY),
        default="compat",
        help="Schema target to inspect; default keeps the compatibility schema path",
    )
    p.set_defaults(func=cmd_schema)

    p = sub.add_parser("context-build", help="Build a context pack with provenance hashes")
    p.add_argument("file")
    p.add_argument("--repo", default=".")
    p.add_argument("--out", default="generated/context_pack.json")
    p.add_argument(
        "--include-content",
        action="store_true",
        help="Embed file content in context pack",
    )
    p.set_defaults(func=cmd_context_build)

    p = sub.add_parser("harness-run", help="Plan a safe local harness run manifest")
    p.add_argument("file")
    p.add_argument("--harness")
    p.add_argument("--repo", default=".")
    p.add_argument("--out", default="generated/harness_run")
    p.add_argument(
        "--include-content",
        action="store_true",
        help="Embed file content in context pack",
    )
    p.set_defaults(func=cmd_harness_run)

    p = sub.add_parser("policy-check", help="Evaluate local policy, guardrail, and capability decisions")
    p.add_argument("file")
    p.add_argument("--harness")
    p.add_argument("--out")
    p.set_defaults(func=cmd_policy_check)

    p = sub.add_parser("eval-run", help="Create a local eval report with integrity checks")
    p.add_argument("file")
    p.add_argument("--eval", action="append", help="Eval name to run; defaults to all evals")
    p.add_argument("--results", help="Optional local JSON results with observed metric values")
    p.add_argument("--repo", default=".")
    p.add_argument("--out")
    p.add_argument("--strict", action="store_true", help="Return non-zero on failed or blocked evals")
    p.set_defaults(func=cmd_eval_run)

    p = sub.add_parser(
        "connector-plan",
        help="Create a safe local connector/plugin adapter manifest",
    )
    p.add_argument("file")
    p.add_argument("--out")
    p.add_argument("--strict", action="store_true", help="Return non-zero on blocked connector plans")
    p.set_defaults(func=cmd_connector_plan)

    p = sub.add_parser("editor-manifest", help="Emit editor integration metadata")
    p.add_argument("--out")
    p.set_defaults(func=cmd_editor_manifest)

    p = sub.add_parser("syntax", help="Emit syntax highlighting metadata")
    p.add_argument("--out")
    p.set_defaults(func=cmd_syntax)

    p = sub.add_parser("lsp-diagnostics", help="Emit LSP-compatible diagnostics for a .nyx file")
    p.add_argument("file")
    p.add_argument("--out")
    p.set_defaults(func=cmd_lsp_diagnostics)

    p = sub.add_parser("complete", help="Emit completion items for a .nyx file/path")
    p.add_argument("file", nargs="?")
    p.add_argument("--path", default="")
    p.add_argument("--prefix", default="")
    p.add_argument("--out")
    p.set_defaults(func=cmd_complete)

    p = sub.add_parser("symbols", help="Emit document symbols for a .nyx file")
    p.add_argument("file")
    p.add_argument("--out")
    p.set_defaults(func=cmd_symbols)

    p = sub.add_parser("release-check", help="Create a local release readiness report")
    p.add_argument("--repo", default=".")
    p.add_argument("--target-version", default="1.0.0")
    p.add_argument("--approved", action="store_true", help="Record human release approval")
    p.add_argument("--out")
    p.add_argument("--strict", action="store_true", help="Return non-zero on blocking readiness errors")
    p.set_defaults(func=cmd_release_check)

    p = sub.add_parser("stable-language-check", help="Create a local v1.0 stable-language report")
    p.add_argument("--repo", default=".")
    p.add_argument("--target-version", default="1.0.0")
    p.add_argument("--approved", action="store_true", help="Record human v1.0 release approval")
    p.add_argument("--out")
    p.add_argument("--strict", action="store_true", help="Return non-zero on blocking stable-language errors")
    p.set_defaults(func=cmd_stable_language_check)

    p = sub.add_parser("language-evolution", help="Create a local language evolution research report")
    p.add_argument("--repo", default=".")
    p.add_argument("--out")
    p.add_argument("--strict", action="store_true", help="Return non-zero on research-contract issues")
    p.set_defaults(func=cmd_language_evolution)

    p = sub.add_parser("evidence-pack", help="Create an evidence pack scaffold")
    p.add_argument("--out", default="generated/evidence")
    p.set_defaults(func=cmd_evidence_pack)

    agentic = sub.add_parser(
        "agentic-network",
        help="Deterministic agentic-network governance artifacts, lock, and evidence",
    )
    agentic_sub = agentic.add_subparsers(dest="agentic_command", required=True)

    p = agentic_sub.add_parser(
        "generate",
        help="Generate deterministic agentic-network declaration artifacts",
    )
    p.add_argument("file")
    p.add_argument("--out", default=DEFAULT_ARTIFACT_DIR)
    p.add_argument("--as-of", help="Explicit offset timestamp for validation")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_agentic_network_generate)

    p = agentic_sub.add_parser(
        "lock",
        help="Write the content-addressed agentic-network lock",
    )
    p.add_argument("file")
    p.add_argument("--artifacts", default=DEFAULT_ARTIFACT_DIR)
    p.add_argument("--out", default=DEFAULT_LOCK_NAME)
    p.add_argument("--as-of", help="Explicit offset timestamp for validation")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_agentic_network_lock)

    p = agentic_sub.add_parser(
        "lock-check",
        help="Verify the agentic-network lock against the current contract",
    )
    p.add_argument("file")
    p.add_argument("--lock", default=DEFAULT_LOCK_NAME)
    p.add_argument("--artifacts", default=DEFAULT_ARTIFACT_DIR)
    p.add_argument("--as-of", help="Explicit offset timestamp for validation")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_agentic_network_lock_check)

    p = agentic_sub.add_parser(
        "evidence-validate",
        help="Validate supplied local runtime-event evidence against the lock",
    )
    p.add_argument("file")
    p.add_argument("--events", required=True, help="Local runtime-events JSON file")
    p.add_argument("--lock", default=DEFAULT_LOCK_NAME)
    p.add_argument("--as-of", help="Explicit offset timestamp for validation")
    p.add_argument("--out", help="Optional deterministic report output path")
    p.add_argument("--strict", action="store_true", help="Exit nonzero on failure")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_agentic_network_evidence_validate)

    p = sub.add_parser("profiles", help="Inspect and validate local Nornyx profiles")
    p.set_defaults(func=cmd_profiles, profiles_command=None)
    profile_sub = p.add_subparsers(dest="profiles_command")

    profile_command = profile_sub.add_parser("list", help="List built-in profiles")
    profile_command.add_argument("--json", action="store_true")
    profile_command.set_defaults(func=cmd_profiles)

    profile_command = profile_sub.add_parser("inspect", help="Inspect a built-in v1 profile")
    profile_command.add_argument("name")
    profile_command.add_argument("--json", action="store_true")
    profile_command.set_defaults(func=cmd_profiles)

    profile_command = profile_sub.add_parser("validate", help="Validate one local pack")
    profile_command.add_argument("path")
    profile_command.add_argument("--json", action="store_true")
    profile_command.set_defaults(func=cmd_profiles)

    profile_command = profile_sub.add_parser("resolve", help="Resolve one built-in profile")
    profile_command.add_argument("name")
    profile_command.add_argument("--lock", action="store_true")
    profile_command.add_argument("--json", action="store_true")
    profile_command.set_defaults(func=cmd_profiles)

    profile_command = profile_sub.add_parser(
        "compatibility", help="Analyze declared profile compatibility"
    )
    profile_command.add_argument("names", nargs="+")
    profile_command.add_argument("--json", action="store_true")
    profile_command.set_defaults(func=cmd_profiles)

    p = sub.add_parser("modules", help="Inspect and validate local governance modules")
    module_sub = p.add_subparsers(dest="modules_command", required=True)

    module_command = module_sub.add_parser("list", help="List available governance modules")
    module_command.add_argument("--json", action="store_true")
    module_command.set_defaults(func=cmd_modules)

    module_command = module_sub.add_parser("inspect", help="Inspect one governance module")
    module_command.add_argument("name")
    module_command.add_argument("--json", action="store_true")
    module_command.set_defaults(func=cmd_modules)

    module_command = module_sub.add_parser("validate", help="Validate one local module pack")
    module_command.add_argument("path")
    module_command.add_argument("--json", action="store_true")
    module_command.set_defaults(func=cmd_modules)

    p = sub.add_parser("governance", help="Inspect effective contract governance")
    governance_sub = p.add_subparsers(dest="governance_command", required=True)
    for command, help_text in (
        ("resolve", "Resolve the complete effective governance model"),
        ("explain", "Explain active controls and requirements"),
        ("matrix", "Show controls and requirements by contributing pack"),
    ):
        governance_command = governance_sub.add_parser(command, help=help_text)
        governance_command.add_argument("file")
        governance_command.add_argument(
            "--as-of",
            help="Explicit offset timestamp for freshness and expiry validation",
        )
        governance_command.add_argument("--json", action="store_true")
        governance_command.set_defaults(func=cmd_governance)

    p = sub.add_parser("evidence", help="Validate local governance evidence")
    evidence_sub = p.add_subparsers(dest="evidence_command", required=True)
    evidence_command = evidence_sub.add_parser(
        "validate", help="Validate one governance evidence set"
    )
    evidence_command.add_argument("path")
    evidence_command.add_argument(
        "--as-of",
        help="Explicit offset timestamp for freshness validation",
    )
    evidence_command.add_argument("--json", action="store_true")
    evidence_command.set_defaults(func=cmd_evidence)

    p = sub.add_parser("doctor", help="Check local Nornyx repository readiness")
    p.add_argument("--repo", default=".")
    p.add_argument("--json", action="store_true", help="Emit machine-readable readiness JSON")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("init", help="Create a starter .nyx file from a built-in profile")
    profile_source = p.add_mutually_exclusive_group()
    profile_source.add_argument("--profile", choices=PROFILE_NAMES)
    profile_source.add_argument("--profile-path", help="Explicit local v1 profile pack")
    p.add_argument("--name", required=True)
    p.add_argument("--out", default="nornyx.project.nyx")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("fmt", help="Format a .nyx file")
    p.add_argument("file")
    p.add_argument("--write", action="store_true")
    p.add_argument("--check", action="store_true")
    p.set_defaults(func=cmd_fmt)

    p = sub.add_parser("explain", help="Explain a .nyx file or symbol")
    p.add_argument("file")
    p.add_argument("symbol", nargs="?")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_explain)

    adopt = sub.add_parser("adopt", help="Zero-friction adoption helpers")
    adopt_sub = adopt.add_subparsers(dest="adopt_command", required=True)

    p = adopt_sub.add_parser("status", help="Inspect local repo and suggest first Nornyx adoption step")
    p.add_argument("--repo", default=".")
    p.set_defaults(func=cmd_adopt_status)

    p = adopt_sub.add_parser("init-lite", help="Generate a minimal Nornyx Lite .nyx draft")
    p.add_argument("--project", required=True)
    p.add_argument("--repo", default=".")
    p.add_argument("--out", default="nornyx.project.nyx")
    p.add_argument("--force", action="store_true", help="Overwrite output file if it already exists")
    p.set_defaults(func=cmd_adopt_init_lite)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
