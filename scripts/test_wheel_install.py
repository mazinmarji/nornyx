from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import venv


NETWORK_ENVIRONMENT = (
    "ALL_PROXY",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "NO_PROXY",
    "PIP_EXTRA_INDEX_URL",
    "PIP_INDEX_URL",
    "PIP_TRUSTED_HOST",
    "UV_EXTRA_INDEX_URL",
    "UV_INDEX_URL",
)


def _network_attempts(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    attempt_log: Path | None = None,
    expected_returncodes: tuple[int, ...] = (0,),
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
    attempts = _network_attempts(attempt_log)
    if attempts:
        raise RuntimeError(f"network access attempted by {' '.join(command)}: {attempts!r}")
    if result.returncode not in expected_returncodes:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


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

    network_attempts: list[dict[str, str]] = []
    agentic_starter_generated = False
    with tempfile.TemporaryDirectory(prefix="nornyx-wheel-smoke-") as raw_tmp:
        root = Path(raw_tmp)
        venv_root = root / "venv"
        venv.EnvBuilder(with_pip=True).create(venv_root)
        python = _venv_python(venv_root)
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        for name in NETWORK_ENVIRONMENT:
            env.pop(name, None)
            env.pop(name.lower(), None)
        env["PIP_NO_INDEX"] = "1"
        env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
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
        guard_source = Path(__file__).with_name("wheel_network_guard.py")
        if not guard_source.is_file():
            raise RuntimeError(f"wheel network guard is missing: {guard_source}")
        guard_module = purelib / "nornyx_wheel_network_guard.py"
        guard_module.write_bytes(guard_source.read_bytes())
        self_test_log = root / "network-guard-self-test.jsonl"
        self_test = _run(
            [
                str(python),
                "-I",
                "-c",
                (
                    "import json, sys; "
                    "from nornyx_wheel_network_guard import run_self_test; "
                    "print(json.dumps(run_self_test(sys.argv[1]), sort_keys=True))"
                ),
                str(self_test_log),
            ],
            cwd=root,
            env=env,
        )
        self_test_payload = json.loads(self_test.stdout)
        if self_test_payload != _network_attempts(self_test_log):
            raise RuntimeError("wheel network guard self-test evidence is inconsistent")

        # Pip imports its vendored HTTP stack even with --no-index; that stack
        # performs an IPv6 capability socket construction during import. Keep
        # installation offline with the explicit flags/environment below, then
        # activate the construction-denying observer for installed-product use.
        _run(
            [
                str(python),
                "-I",
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--disable-pip-version-check",
                str(wheel),
            ],
            cwd=root,
            env=env,
        )
        (purelib / "nornyx-wheel-smoke-network-guard.pth").write_text(
            "import nornyx_wheel_network_guard; "
            "nornyx_wheel_network_guard.install_from_environment()\n",
            encoding="utf-8",
        )
        attempt_log = root / "network-attempts.jsonl"
        attempt_log.unlink(missing_ok=True)
        env["NORNYX_NETWORK_ATTEMPT_LOG"] = str(attempt_log)
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
                    "root=resources.files('nornyx'); "
                    "s=root/'schemas'/'governance_evidence_v1.schema.json'; "
                    "p=root/'profiles_data'; "
                    "an=('agentic_network_v1.schema.json',"
                    "'agent_identities_v1.schema.json',"
                    "'agentic_capabilities_v1.schema.json'); "
                    "print(json.dumps({'version':nornyx.__version__,"
                    "'profiles':len(PROFILE_NAMES),'modules':len(r.module_names),"
                    "'schema':s.is_file(),'profile_resources':len(list(p.iterdir())),"
                    "'agentic_schemas':all((root/'schemas'/x).is_file() for x in an),"
                    "'validator':callable(validate_governance_evidence_file)}))"
                ),
            ],
            cwd=root,
            env=env,
            attempt_log=attempt_log,
        )
        payload = json.loads(probe.stdout)
        if payload != {
            "version": "1.6.2",
            "profiles": 13,
            "modules": 7,
            "schema": True,
            "profile_resources": 21,
            "agentic_schemas": True,
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
            attempt_log=attempt_log,
        )
        consumer_payload = json.loads(legacy_consumer.stdout)
        if consumer_payload != {
            "legacy_consumer": True,
            "approval_schema": "nornyx.normalized_approval.v1",
            "composition_schema": "nornyx.effective_governance.v1",
        }:
            raise RuntimeError(f"installed-wheel legacy consumer failed: {consumer_payload!r}")
        cli = _run(
            [str(python), "-I", "-m", "nornyx.cli", "modules", "list", "--json"],
            cwd=root,
            env=env,
            attempt_log=attempt_log,
        )
        modules = json.loads(cli.stdout)["modules"]
        if len(modules) != 7 or {item["source_tier"] for item in modules} != {"builtin"}:
            raise RuntimeError("installed-wheel CLI did not resolve seven bundled modules")
        profiles_cli = _run(
            [str(python), "-I", "-m", "nornyx.cli", "profiles", "list", "--json"],
            cwd=root,
            env=env,
            attempt_log=attempt_log,
        )
        if len(json.loads(profiles_cli.stdout)["profiles"]) != 13:
            raise RuntimeError("installed-wheel CLI did not resolve thirteen bundled profiles")
        generated_agentic_network = root / "agentic-network.nyx"
        _run(
            [
                str(python),
                "-I",
                "-m",
                "nornyx.cli",
                "init",
                "--profile",
                "agentic_network",
                "--name",
                "WheelAgenticNetwork",
                "--out",
                str(generated_agentic_network),
            ],
            cwd=root,
            env=env,
            attempt_log=attempt_log,
        )
        agentic_starter_generated = generated_agentic_network.is_file()
        if not agentic_starter_generated:
            raise RuntimeError("installed-wheel CLI did not generate the agentic starter")
        agentic_check = _run(
            [
                str(python),
                "-I",
                "-m",
                "nornyx.cli",
                "check",
                str(generated_agentic_network),
            ],
            cwd=root,
            env=env,
            attempt_log=attempt_log,
            expected_returncodes=(1,),
        )
        required_failures = {
            "EVIDENCE_REQUIRED_MISSING",
            "AN_CONTRACT_REVIEW_MISSING",
            "AN_APPROVAL_RECORD_MISSING",
        }
        missing_failures = {
            code for code in required_failures if f'"code": "{code}"' not in agentic_check.stdout
        }
        if missing_failures or '"code": "GOVERNANCE_BLOCK_SCHEMA_INVALID"' in agentic_check.stdout:
            raise RuntimeError(
                "installed-wheel agentic starter did not fail closed as expected: "
                f"missing={sorted(missing_failures)!r}\nstdout:\n{agentic_check.stdout}"
            )
        network_attempts = _network_attempts(attempt_log)
        network_used = bool(network_attempts)
        if network_used:
            raise RuntimeError(f"wheel smoke observed network attempts: {network_attempts!r}")

    print(
        json.dumps(
            {
                "status": "pass",
                "wheel": wheel.name,
                "version": payload["version"],
                "profiles": payload["profiles"],
                "modules": payload["modules"],
                "legacy_consumer": consumer_payload["legacy_consumer"],
                "agentic_starter_generated": agentic_starter_generated,
                "agentic_starter_check": "expected_evidence_failure",
                "network_used": network_used,
                "network_attempts": network_attempts,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
