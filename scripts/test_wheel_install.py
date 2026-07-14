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
        legacy_consumer = _run(
            [
                str(python),
                "-I",
                "-c",
                """
import json
from nornyx.governance import CompositionResult, GovernanceModule, NormalizedApproval
from nornyx.governance.models import PackProvenance

provenance = PackProvenance("human", "project", "git:base", "module.yaml")
legacy_binding = {
    "kind": "git", "revision": "base-revision", "exact": True,
    "scope_hash": "sha256:" + "a" * 64,
}
module = GovernanceModule(
    "org.example.module", "module", "1.0.0", ">=1.0,<2.0",
    (), (), (), (), (), (), (), (), (), provenance, "sha256:" + "0" * 64, {},
)
approval = NormalizedApproval(
    "HumanGate", ("reviewer",), ("reviewer",), ("ai_tool",),
    ("execution_surface",), ("review",), ("merge",), "before_merge",
    "user:owner", legacy_binding, ("revision_changed",), None, "complete", (),
    "ordinary_approval", "approvals[0]", {"name": "HumanGate"}, "eligible_roles",
)
composition = CompositionResult(
    None, (module,), (), (), (), (approval,), (), (), (), (), (),
)
approval_payload = approval.to_dict()
composition_payload = composition.to_dict()
assert module.block_schemas == () and module.structural_checks == ()
assert approval.exact_revision_required is None and approval.expires_after is None
assert composition.block_schemas is None and composition.structural_checks is None
assert approval_payload["schema"] == "nornyx.normalized_approval.v1"
assert approval_payload["revision_binding"] == legacy_binding
assert "exact_revision_required" not in approval_payload
assert "expires_after" not in approval_payload
assert composition_payload["schema"] == "nornyx.effective_governance.v1"
assert "block_schemas" not in composition_payload
assert "structural_checks" not in composition_payload
print(json.dumps({"legacy_consumer": True, "approval_schema": approval_payload["schema"],
                  "composition_schema": composition_payload["schema"]}))
""",
            ],
            cwd=root,
            env=env,
        )
        consumer_payload = json.loads(legacy_consumer.stdout)
        if consumer_payload != {
            "legacy_consumer": True,
            "approval_schema": "nornyx.normalized_approval.v1",
            "composition_schema": "nornyx.effective_governance.v1",
        }:
            raise RuntimeError(
                f"installed-wheel legacy consumer failed: {consumer_payload!r}"
            )
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
                "legacy_consumer": consumer_payload["legacy_consumer"],
                "network_used": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
