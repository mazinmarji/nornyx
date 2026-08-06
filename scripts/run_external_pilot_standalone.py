"""Run the external adoption pilot from outside any checkout.

The pilot claims an external adopter can run it without cloning `nornyx`.
Invoking it from the repository exercises the code but not that claim, because
the launcher itself came from the checkout.

This performs the acquisition the claim implies: it copies **only** the pilot
package to a directory outside every checkout, strips the repository from the
child's import path, runs it there, and then proves from the emitted adoption
record that nothing resolved from the repository.

The pilot's own inner controls still apply: it still builds its own clean
virtual environment, still installs from PyPI, and still performs its own
leakage checks against that environment.
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
PACKAGE_DIR = REPO_ROOT / "examples" / "external_adoption_pilot"
PACKAGE_NAME = "external_adoption_pilot"


def _child_env() -> dict[str, str]:
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("PIP_")
        and name not in {"PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"}
    }
    env["PIP_CONFIG_FILE"] = os.devnull
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return env


def _assert_no_repository_paths(record: dict, *, repo_root: Path) -> None:
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

    walk(record, "")
    if offenders:
        raise SystemExit(
            "standalone run resolved paths inside the repository it was copied "
            "from:\n  " + "\n  ".join(offenders)
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    if not PACKAGE_DIR.is_dir():
        raise SystemExit(f"pilot package not found at {PACKAGE_DIR}")

    with tempfile.TemporaryDirectory(prefix="nornyx-pilot-standalone-") as raw_tmp:
        staging = Path(raw_tmp).resolve()
        shutil.copytree(
            PACKAGE_DIR,
            staging / PACKAGE_NAME,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

        print(f"running {PACKAGE_NAME} from {staging} (repository at {REPO_ROOT})")
        completed = subprocess.run(
            [
                sys.executable, "-m", PACKAGE_NAME,
                "--json", "--timeout", str(args.timeout),
            ],
            cwd=staging,
            env=_child_env(),
            check=False,
            text=True,
            capture_output=True,
            timeout=args.timeout + 300,
        )
        if completed.returncode != 0:
            print(completed.stdout)
            print(completed.stderr, file=sys.stderr)
            raise SystemExit(f"standalone pilot exited {completed.returncode}")

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            print(completed.stdout[-4000:])
            raise SystemExit(f"standalone pilot emitted unparsable JSON: {exc}") from exc

        if payload.get("status") != "pass":
            print(json.dumps(payload, indent=2, sort_keys=True))
            raise SystemExit("standalone pilot did not pass")

        record = payload["record"]
        _assert_no_repository_paths(record, repo_root=REPO_ROOT)

        if args.out:
            args.out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

        delta = record.get("governance_delta", {})
        variants = {v["id"]: v for v in record.get("variants", [])}
        print(
            "standalone OK: adapter "
            f"{payload['adapter_version']} + crewai {payload['crewai_version']}; "
            f"ungoverned executions={variants['ungoverned']['executions']}, "
            f"denied executions={variants['governed_unauthorized']['executions']}, "
            f"prevented={delta.get('action_prevented_when_unauthorized')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
