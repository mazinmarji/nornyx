from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import venv


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            env=env,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"command failed ({exc.returncode}): {' '.join(command)}\n"
            f"stdout:\n{exc.stdout}\nstderr:\n{exc.stderr}"
        ) from exc


def _venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _dependency_roots() -> tuple[Path, ...]:
    roots = set()
    for name in ("yaml", "jsonschema", "referencing"):
        spec = importlib.util.find_spec(name)
        if spec is None or spec.origin is None:
            raise RuntimeError(f"wheel smoke dependency {name!r} is not installed")
        roots.add(Path(spec.origin).resolve().parent.parent)
    return tuple(sorted(roots))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install and smoke-test one local Nornyx wheel.")
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args(argv)
    wheel = args.wheel.resolve(strict=True)
    if wheel.suffix != ".whl":
        parser.error("wheel must identify a .whl file")

    with tempfile.TemporaryDirectory(prefix="nornyx-wheel-smoke-") as raw_tmp:
        root = Path(raw_tmp)
        venv_root = root / "venv"
        venv.EnvBuilder(with_pip=True).create(venv_root)
        python = _venv_python(venv_root)
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        purelib_probe = _run(
            [
                str(python),
                "-I",
                "-c",
                "import sysconfig; print(sysconfig.get_paths()['purelib'])",
            ],
            cwd=root,
            env=env,
        )
        purelib = Path(purelib_probe.stdout.strip())
        (purelib / "nornyx-wheel-smoke-dependencies.pth").write_text(
            "".join(f"{item}\n" for item in _dependency_roots()),
            encoding="utf-8",
        )
        _run(
            [
                str(python),
                "-I",
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--disable-pip-version-check",
                str(wheel),
            ],
            cwd=root,
            env=env,
        )
        probe = _run(
            [
                str(python),
                "-I",
                "-c",
                (
                    "import json; "
                    "from importlib import resources; "
                    "import nornyx; "
                    "from nornyx.governance import GovernanceRegistry, "
                    "validate_governance_evidence_file; "
                    "from nornyx.profiles import PROFILE_NAMES; "
                    "r=GovernanceRegistry.builtins(); "
                    "s=resources.files('nornyx')/'schemas'/'governance_evidence_v1.schema.json'; "
                    "print(json.dumps({'version':nornyx.__version__,"
                    "'profiles':len(PROFILE_NAMES),'modules':len(r.module_names),"
                    "'schema':s.is_file(),'validator':callable(validate_governance_evidence_file)}))"
                ),
            ],
            cwd=root,
            env=env,
        )
        payload = json.loads(probe.stdout)
        if payload != {
            "version": "1.5.2",
            "profiles": 12,
            "modules": 6,
            "schema": True,
            "validator": True,
        }:
            raise RuntimeError(f"installed-wheel resource probe failed: {payload!r}")
        cli = _run(
            [str(python), "-I", "-m", "nornyx.cli", "modules", "list", "--json"],
            cwd=root,
            env=env,
        )
        modules = json.loads(cli.stdout)["modules"]
        if len(modules) != 6 or {item["source_tier"] for item in modules} != {"builtin"}:
            raise RuntimeError("installed-wheel CLI did not resolve six bundled modules")

    print(
        json.dumps(
            {
                "status": "pass",
                "wheel": wheel.name,
                "version": payload["version"],
                "profiles": payload["profiles"],
                "modules": payload["modules"],
                "network_used": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
