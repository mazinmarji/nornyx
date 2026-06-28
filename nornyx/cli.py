from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adoption import adoption_status, write_lite_nyx
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
from .harness_runtime import HarnessRuntimeError, run_harness
from .language_evolution import build_language_evolution_report, write_language_evolution_report
from .parser import NornyxParseError, load_nyx
from .policy_runtime import PolicyRuntimeError, evaluate_harness_policy, write_policy_report
from .profiles import PROFILE_NAMES, write_profile
from .release_readiness import (
    build_release_readiness_report,
    build_stable_language_report,
    write_release_readiness_report,
)
from .schema_model import (
    FORMAL_GRAMMAR_V0_1,
    SCHEMA_REGISTRY,
    schema_model_summary,
    validate_schema_model,
)


def cmd_check(args: argparse.Namespace) -> int:
    try:
        doc = load_nyx(args.file)
    except NornyxParseError as exc:
        print(json.dumps({"level": "error", "code": "PARSE_ERROR", "message": str(exc)}, indent=2))
        return 2
    diagnostics = check_document(doc)
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


def cmd_evidence_pack(args: argparse.Namespace) -> int:
    paths = create_evidence_pack(args.out)
    print(f"Evidence scaffold written to {args.out}")
    for path in paths:
        print(path)
    return 0


def cmd_profiles(args: argparse.Namespace) -> int:
    for name in PROFILE_NAMES:
        print(name)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    report = run_doctor(args.repo)
    print(doctor_json(report) if args.json else format_doctor(report))
    return 0 if report["ok"] else 1


def cmd_init(args: argparse.Namespace) -> int:
    try:
        path = write_profile(args.out, args.profile, args.name, force=args.force)
    except (ValueError, FileExistsError) as exc:
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
    print(f"Next: nornyx check {written[0].as_posix()}")
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

    p = sub.add_parser("profiles", help="List built-in Nornyx profiles")
    p.set_defaults(func=cmd_profiles)

    p = sub.add_parser("doctor", help="Check local Nornyx repository readiness")
    p.add_argument("--repo", default=".")
    p.add_argument("--json", action="store_true", help="Emit machine-readable readiness JSON")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("init", help="Create a starter .nyx file from a built-in profile")
    p.add_argument("--profile", choices=PROFILE_NAMES, default="ai_coding")
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
