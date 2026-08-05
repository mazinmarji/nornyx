"""Run the pip-only example from outside any checkout.

The example claims it works without cloning `nornyx`. Invoking it from the
repository -- which is what the ordinary CI step does -- exercises the code but
not that claim: the launcher itself came from the checkout, and the repository
was importable in the parent process the whole time.

This script closes that gap by performing the acquisition the claim implies.
It copies **only** the example package to a directory outside every checkout,
scrubs the repository from the child's import path, runs the example there, and
then proves from the emitted audit record that nothing resolved from the
repository.

The example's own inner controls are unchanged and still apply: it still builds
its own clean virtual environment, still installs from PyPI, and still performs
its own leakage checks against that environment.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "examples" / "pip_only_conformance"
PACKAGE_NAME = "pip_only_conformance"


def _child_env() -> dict[str, str]:
    """Environment for the standalone child: no repository, no pip inheritance."""
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("PIP_")
        and name not in {"PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"}
    }
    env["PIP_CONFIG_FILE"] = os.devnull
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return env


def _assert_no_repository_paths(audit: dict, *, repo_root: Path) -> None:
    """No path in the record may lie inside the checkout this was copied from."""
    marker = os.path.normcase(str(repo_root))
    offenders: list[str] = []

    def walk(node: object, pointer: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{pointer}/{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{pointer}/{index}")
        elif isinstance(node, str) and os.path.normcase(node).startswith(marker):
            offenders.append(f"{pointer} = {node}")

    walk(audit, "")
    if offenders:
        raise SystemExit(
            "standalone run resolved paths inside the repository it was copied "
            "from:\n  " + "\n  ".join(offenders)
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=None)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args(argv)

    if not PACKAGE_DIR.is_dir():
        raise SystemExit(f"example package not found at {PACKAGE_DIR}")

    # Deliberately outside the repository: the system temp root, not a path
    # under REPO_ROOT, so "outside every checkout" is literally true.
    with tempfile.TemporaryDirectory(prefix="nornyx-standalone-") as raw_tmp:
        staging = Path(raw_tmp).resolve()
        destination = staging / PACKAGE_NAME
        # Copy only the package. No tests, no repository, no tooling.
        shutil.copytree(
            PACKAGE_DIR,
            destination,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

        command = [sys.executable, "-m", PACKAGE_NAME, "--json", "--timeout", str(args.timeout)]
        if args.version:
            command += ["--version", args.version]

        print(f"running {PACKAGE_NAME} from {staging} (repository at {REPO_ROOT})")
        completed = subprocess.run(
            command,
            cwd=staging,
            env=_child_env(),
            check=False,
            text=True,
            capture_output=True,
            timeout=args.timeout + 120,
        )
        if completed.returncode != 0:
            print(completed.stdout)
            print(completed.stderr, file=sys.stderr)
            raise SystemExit(
                f"standalone example exited {completed.returncode}"
            )

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            print(completed.stdout)
            raise SystemExit(f"standalone example emitted unparsable JSON: {exc}") from exc

        if payload.get("status") != "pass":
            print(json.dumps(payload, indent=2, sort_keys=True))
            raise SystemExit("standalone example did not pass")

        audit = payload["audit"]
        _assert_no_repository_paths(audit, repo_root=REPO_ROOT)

        provenance = audit.get("provenance", {})
        conformance = audit.get("conformance", {})
        print(
            "standalone OK: "
            f"{provenance.get('filename')} ({provenance.get('artifact_type')}) "
            f"from {provenance.get('host')}, "
            f"{conformance.get('cases')} cases, outcome {conformance.get('outcome')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
