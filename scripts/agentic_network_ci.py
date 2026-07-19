"""AN-006 reference CI workflow for the agentic-network governance chain.

Safe to run offline after dependencies are installed: no credentials, no
external systems, no production writes. Every step exits nonzero on
violation. See docs/agentic-network/11_REFERENCE_CI.md.

Steps:
 1. (optional, --wheel) build the candidate wheel and run all later Nornyx
    steps against a clean installation of that wheel;
 2. check the `.nyx` contract;
 3. resolve the profile and modules;
 4. generate deterministic controls;
 5. verify generated-artifact determinism (regenerate and byte-compare);
 6. write and verify the agentic-network lock;
 7. import the supplied external eval results (Promptfoo-style; not executed);
 8. validate eval thresholds and dataset integrity;
 9. run the safe CrewAI demonstration path;
10. run the safe LangGraph demonstration path;
11. validate emitted runtime events against the exact lock;
12. validate human approval and revision binding (contract governance);
13. assemble the final audit package;
14. exit nonzero on any violation.

Usage:
    python scripts/agentic_network_ci.py --out dist/agentic-network-ci [--wheel]
"""

from __future__ import annotations

import argparse
import filecmp
import json
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "agentic_network_support"
CONTRACT = EXAMPLE / "support_network.nyx"
AS_OF = "2026-07-17T00:00:00Z"


class StepFailure(RuntimeError):
    pass


def _run(step: str, command: list[str], *, cwd: Path = ROOT) -> str:
    print(f"[agentic-network-ci] {step}: {' '.join(str(c) for c in command)}")
    result = subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, check=False
    )
    sys.stdout.write(result.stdout)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise StepFailure(f"step failed: {step} (exit {result.returncode})")
    return result.stdout


def _prepare_python(out: Path, use_wheel: bool) -> list[str]:
    if not use_wheel:
        return [sys.executable]
    dist = out / "wheel-dist"
    _run("build-wheel", [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist)])
    wheels = sorted(dist.glob("nornyx-*.whl"))
    if not wheels:
        raise StepFailure("no candidate wheel produced")
    env_dir = out / "wheel-venv"
    venv.EnvBuilder(with_pip=True).create(env_dir)
    python = env_dir / ("Scripts" if sys.platform == "win32" else "bin") / "python"
    _run(
        "install-wheel",
        [str(python), "-m", "pip", "install", "--no-index", str(wheels[0])],
    )
    return [str(python)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ROOT / "dist" / "agentic-network-ci"))
    parser.add_argument(
        "--wheel",
        action="store_true",
        help="Build the candidate wheel and run Nornyx steps from it",
    )
    args = parser.parse_args(argv)
    out = Path(args.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    try:
        python = _prepare_python(out, args.wheel)
        nornyx = [*python, "-m", "nornyx.cli"]

        _run("check-contract", [*nornyx, "check", str(CONTRACT)])
        _run(
            "resolve-governance",
            [*nornyx, "governance", "resolve", str(CONTRACT), "--as-of", AS_OF, "--json"],
        )

        artifacts = out / "artifacts"
        _run(
            "generate-controls",
            [
                *nornyx,
                "agentic-network",
                "generate",
                str(CONTRACT),
                "--out",
                str(artifacts),
                "--as-of",
                AS_OF,
            ],
        )
        regenerated = out / "artifacts-recheck"
        _run(
            "regenerate-controls",
            [
                *nornyx,
                "agentic-network",
                "generate",
                str(CONTRACT),
                "--out",
                str(regenerated),
                "--as-of",
                AS_OF,
            ],
        )
        comparison = filecmp.dircmp(artifacts, regenerated)
        if comparison.diff_files or comparison.left_only or comparison.right_only:
            raise StepFailure(
                "generated controls are not deterministic: "
                f"{comparison.diff_files or comparison.left_only or comparison.right_only}"
            )

        lock_path = out / "nornyx.agentic_network.lock"
        _run(
            "write-lock",
            [
                *nornyx,
                "agentic-network",
                "lock",
                str(CONTRACT),
                "--artifacts",
                str(artifacts),
                "--out",
                str(lock_path),
                "--as-of",
                AS_OF,
            ],
        )
        _run(
            "verify-lock",
            [
                *nornyx,
                "agentic-network",
                "lock-check",
                str(CONTRACT),
                "--lock",
                str(lock_path),
                "--artifacts",
                str(artifacts),
                "--as-of",
                AS_OF,
            ],
        )

        imported_results = out / "imported_eval_results.json"
        _run(
            "import-eval-results",
            [
                *nornyx,
                "eval-import",
                "promptfoo",
                str(EXAMPLE / "eval" / "promptfoo_results.json"),
                "--eval-name",
                "support_response_quality",
                "--subject-revision",
                "git:feedfacefeedfacefeedfacefeedfacefeedface",
                "--out",
                str(imported_results),
            ],
        )
        _run(
            "validate-eval-thresholds",
            [
                *nornyx,
                "eval-run",
                str(CONTRACT),
                "--results",
                str(imported_results),
                "--repo",
                str(EXAMPLE),
                "--out",
                str(out / "eval_report.json"),
                "--strict",
            ],
        )

        # The demonstration (CrewAI path, LangGraph path, evidence emission)
        # runs from the repository because the adapters are deliberately not
        # packaged; Nornyx validation of the emitted evidence runs through
        # the selected Nornyx interpreter below.
        demo_out = out / "demo"
        _run(
            "run-framework-demonstrations",
            [sys.executable, str(EXAMPLE / "run_demo.py"), "--out", str(demo_out)],
        )
        for framework in ("crewai", "langgraph"):
            _run(
                f"validate-{framework}-evidence",
                [
                    *nornyx,
                    "agentic-network",
                    "evidence-validate",
                    str(CONTRACT),
                    "--events",
                    str(demo_out / f"{framework}_events.json"),
                    "--lock",
                    str(demo_out / "nornyx.agentic_network.lock"),
                    "--as-of",
                    AS_OF,
                    "--out",
                    str(out / f"{framework}_evidence_report.json"),
                    "--strict",
                ],
            )

        # Human approval + revision binding are part of contract governance;
        # `check` above enforced them. Re-assert explicitly via evidence
        # validation of the governance evidence set.
        _run(
            "validate-approval-and-revision-binding",
            [
                *nornyx,
                "governance",
                "explain",
                str(CONTRACT),
                "--as-of",
                AS_OF,
                "--json",
            ],
        )

        audit = out / "audit-package"
        audit.mkdir()
        for source in [
            lock_path,
            out / "eval_report.json",
            out / "crewai_evidence_report.json",
            out / "langgraph_evidence_report.json",
            demo_out / "demo_summary.json",
        ]:
            shutil.copy2(source, audit / source.name)
        shutil.copytree(artifacts, audit / "artifacts")
        manifest = {
            "schema": "nornyx.agentic_network_audit_package.v1",
            "contract": CONTRACT.name,
            "as_of": AS_OF,
            "contents": sorted(
                path.relative_to(audit).as_posix()
                for path in audit.rglob("*")
                if path.is_file()
            ),
        }
        (audit / "audit_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except StepFailure as failure:
        print(json.dumps({"status": "fail", "reason": str(failure)}, indent=2))
        return 1
    print(
        json.dumps(
            {"status": "pass", "audit_package": str(audit)},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
