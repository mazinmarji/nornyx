"""Command-line entry point: ``python -m nornyx_agentic_adapters.conformance``.

Exit codes are three-valued on purpose:

* ``0`` — every required case conformed.
* ``1`` — observed nonconformance, or a required framework was unavailable.
* ``2`` — invalid configuration, usage, or an internal error.

A run that could not complete must never exit ``0``, and must never leave a
partially written report behind for a consumer to read as authoritative.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence, TextIO

from .model import RunOutcome
from .report import serialize, validate_report, write_report
from .runner import available_suites, missing_required, run_conformance

EXIT_OK = 0
EXIT_NONCONFORMANT = 1
EXIT_USAGE = 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m nornyx_agentic_adapters.conformance",
        description=(
            "Run the Nornyx runtime adapter-conformance suites and emit a "
            "deterministic JSON report. Cooperative Tier 2, declared wrapped "
            "surfaces only. Opens no network, loads no credentials, calls no "
            "external model, and executes no connector."
        ),
    )
    parser.add_argument(
        "--suite",
        action="append",
        dest="suites",
        metavar="ID",
        help=f"run only this suite (repeatable). Available: {', '.join(available_suites())}",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="cases",
        metavar="ID",
        help="run only this case id (repeatable)",
    )
    parser.add_argument(
        "--require",
        action="append",
        dest="require",
        metavar="FRAMEWORK",
        default=None,
        help=(
            "fail if this framework's suite is unavailable (repeatable). Use in "
            "CI so a missing extra cannot pass as a silent skip."
        ),
    )
    parser.add_argument(
        "--json", dest="json_path", metavar="PATH", help="write the JSON report to PATH"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="print a human-readable summary instead of the JSON report",
    )
    return parser


def _print_summary(report: object, stream: TextIO) -> None:
    payload = report.as_dict()  # type: ignore[attr-defined]
    print(
        f"nornyx runtime adapter conformance: {payload['outcome'].upper()}", file=stream
    )
    print(
        f"  adapter {payload['adapter_name']} {payload['adapter_version']}"
        f" | nornyx {payload['nornyx_version']}"
        f" | SPI {payload['spi_version']}"
        f" | python {payload['python_version']}",
        file=stream,
    )
    print(f"  assurance: {payload['assurance_tier']} (declared wrapped surfaces only)", file=stream)
    for suite in payload["suites"]:
        version = suite.get("framework_version") or suite.get("unavailable_reason", "")
        print(f"  [{suite['outcome']}] {suite['suite_id']}  {version}", file=stream)
        for case in suite["cases"]:
            marker = {"pass": "ok", "fail": "FAIL", "not_representable": "n/a"}[
                case["outcome"]
            ]
            print(f"      {marker:>4}  {case['case_id']}", file=stream)
            if case["detail"]:
                print(f"            {case['detail']}", file=stream)
    print(
        "  Conformance observes declared wrapped surfaces under the exact "
        "versions named above. It does not authenticate agents or approvers, "
        "prove recorded events true, prevent bypass, or establish Tier 3.",
        file=stream,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        report = run_conformance(
            frameworks=args.suites,
            case_ids=args.cases,
            require=args.require or (),
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except Exception as exc:  # noqa: BLE001 - an internal failure is never exit 0
        print(f"internal error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_USAGE

    payload = report.as_dict()
    diagnostics = validate_report(payload)
    if diagnostics:
        print(
            "internal error: the produced report does not validate against its "
            "own schema:",
            file=sys.stderr,
        )
        for diagnostic in diagnostics[:20]:
            print(f"  {diagnostic}", file=sys.stderr)
        return EXIT_USAGE

    if args.json_path:
        try:
            write_report(payload, args.json_path)
        except OSError as exc:
            print(f"error: could not write the report: {type(exc).__name__}", file=sys.stderr)
            return EXIT_USAGE

    if args.summary:
        _print_summary(report, sys.stdout)
    elif not args.json_path:
        sys.stdout.write(serialize(payload))

    unavailable = missing_required(report, args.require or ())
    if unavailable:
        print(
            f"error: required framework suite(s) unavailable: {', '.join(unavailable)}",
            file=sys.stderr,
        )
        return EXIT_NONCONFORMANT

    failures = report.failures()
    if failures or report.outcome is RunOutcome.FAIL:
        for case in failures:
            print(f"nonconformant: {case.case_id}: {case.detail}", file=sys.stderr)
        return EXIT_NONCONFORMANT
    return EXIT_OK


__all__ = ["EXIT_NONCONFORMANT", "EXIT_OK", "EXIT_USAGE", "main"]
