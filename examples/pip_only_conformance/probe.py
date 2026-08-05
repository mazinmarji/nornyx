"""Verification that runs *inside* the clean environment, against the installed
``nornyx-agentic-adapters`` distribution and nothing else.

This module is deliberately standalone. The runner copies this single file into
a temporary directory and executes it with the clean environment's interpreter,
so it must import nothing from ``examples.pip_only_conformance`` and nothing
from the repository. Its only imports are the standard library and the
distribution under test -- and the distribution is imported lazily, inside the
stages, so the pure helpers below stay importable (and unit-testable) in an
environment where the adapter is not installed at all.

Every stage maps to exactly one failure class. The module always emits a single
JSON envelope on stdout prefixed with ``RESULT_SENTINEL``; it never relies on
the exit code alone to carry meaning, and never lets a traceback be the report.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import sysconfig
import traceback

#: Identity the bundled report schema must declare. A different id means the
#: kit is validating against something that is not the runtime-conformance
#: contract, which would make a passing report meaningless.
EXPECTED_SCHEMA_ID = "nornyx.agentic_runtime_conformance.v1"

#: Suites that need no framework extra. This is the whole point of a *pip-only*
#: example: prove the published distribution on its own, with neither CrewAI nor
#: LangGraph installed.
BASE_SUITES = ("distribution", "enforcement_boundary")

RESULT_SENTINEL = "PIPONLY_RESULT"

DISTRIBUTION_NAME = "nornyx-agentic-adapters"


# --------------------------------------------------------------------------
# Pure helpers. No imports of the distribution, so the repository test suite
# can exercise these directly without installing anything.
# --------------------------------------------------------------------------


def normalize(path: str | os.PathLike[str]) -> str:
    """Absolute, symlink-resolved, case-normalized form for containment tests."""
    return os.path.normcase(str(Path(path).resolve()))


def path_is_inside(path: str | os.PathLike[str], root: str | os.PathLike[str]) -> bool:
    """True when ``path`` lies at or beneath ``root``.

    Compared on normalized absolute paths rather than with string prefixes, so
    ``/a/bc`` is not treated as living inside ``/a/b``.
    """
    target = Path(normalize(path))
    base = Path(normalize(root))
    return target == base or base in target.parents


def leakage_findings(
    origins: dict[str, str],
    *,
    site_packages: str,
    forbidden_roots: list[str],
) -> list[dict[str, str]]:
    """Positive evidence about where each artifact actually resolved from.

    This is the load-bearing check for ``SOURCE_TREE_LEAKAGE_DETECTED``, and it
    is written as an assertion about observed origins rather than as an absence
    check. Confirming that no checkout is present would prove nothing about
    where an import resolved; confirming that every origin lies under
    ``site-packages`` and outside every repository root does.
    """
    findings: list[dict[str, str]] = []
    for label, origin in sorted(origins.items()):
        if not path_is_inside(origin, site_packages):
            findings.append(
                {
                    "label": label,
                    "origin": origin,
                    "reason": "resolved outside the environment's site-packages",
                }
            )
            continue
        for root in forbidden_roots:
            if path_is_inside(origin, root):
                findings.append(
                    {
                        "label": label,
                        "origin": origin,
                        "reason": f"resolved inside a repository root ({root})",
                    }
                )
                break
    return findings


def schema_closure_violations(schema: object) -> list[str]:
    """JSON pointers to object definitions that do not close extra properties.

    Mirrors the adapter's own ``test_bundled_schema_closes_every_object_definition``
    so the example asserts the same property the package asserts about itself,
    rather than inventing a weaker one.
    """
    open_objects: list[str] = []

    def walk(node: object, pointer: str) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                if node.get("additionalProperties") is not False:
                    open_objects.append(pointer or "<root>")
            for key, value in node.items():
                walk(value, f"{pointer}/{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{pointer}/{index}")

    walk(schema, "")
    return open_objects


class ProbeFailure(Exception):
    """Raised by a stage; carries the failure class it maps to."""

    def __init__(self, failure_class: str, detail: str, **evidence: object) -> None:
        super().__init__(detail)
        self.failure_class = failure_class
        self.detail = detail
        self.evidence = evidence


# --------------------------------------------------------------------------
# Stages. Each maps to exactly one failure class.
# --------------------------------------------------------------------------


def stage_import() -> dict[str, object]:
    """Import the installed distribution. Failure here means it is unusable."""
    try:
        import importlib.metadata as md

        import nornyx_agentic_adapters as naa
        import nornyx_agentic_adapters.conformance as kit
        from nornyx_agentic_adapters.conformance import harness, report as report_module
    except Exception as exc:  # noqa: BLE001 - the class is the report
        raise ProbeFailure(
            "REGISTRY_INSTALL_FAILED",
            f"the installed distribution is not importable: {exc!r}",
            traceback=traceback.format_exc(),
        ) from exc

    try:
        installed_version = md.version(DISTRIBUTION_NAME)
    except Exception as exc:  # noqa: BLE001
        raise ProbeFailure(
            "REGISTRY_INSTALL_FAILED",
            f"no installed distribution metadata for {DISTRIBUTION_NAME}: {exc!r}",
        ) from exc

    return {
        "naa": naa,
        "kit": kit,
        "harness": harness,
        "report_module": report_module,
        "installed_version": installed_version,
        "dunder_version": getattr(naa, "__version__", None),
    }


def stage_version(imported: dict[str, object], expected: str) -> None:
    installed = str(imported["installed_version"])
    dunder = imported["dunder_version"]
    if installed != expected:
        raise ProbeFailure(
            "INSTALLED_VERSION_MISMATCH",
            f"installed distribution reports {installed!r}, expected {expected!r}",
            installed_version=installed,
            expected_version=expected,
        )
    if dunder != expected:
        raise ProbeFailure(
            "INSTALLED_VERSION_MISMATCH",
            f"package __version__ is {dunder!r} while metadata reports {installed!r}",
            dunder_version=dunder,
            installed_version=installed,
        )


def stage_resources(imported: dict[str, object]) -> dict[str, str]:
    """Resolve bundled resources through importlib.resources, as the kit does."""
    from importlib import resources

    harness = imported["harness"]
    report_module = imported["report_module"]
    origins: dict[str, str] = {}

    for label, package, name in (
        (
            "report_schema",
            report_module.SCHEMA_PACKAGE,
            report_module.SCHEMA_NAME,
        ),
        (
            "contract_fixture",
            harness.FIXTURE_PACKAGE,
            harness.FIXTURE_NAME,
        ),
    ):
        try:
            resource = resources.files(package).joinpath(name)
            if not resource.is_file():
                raise FileNotFoundError(f"{package}/{name}")
            origins[label] = str(Path(str(resource)).resolve())
        except ProbeFailure:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProbeFailure(
                "PACKAGED_RESOURCE_MISSING",
                (
                    f"could not resolve {package}/{name} from the installed "
                    f"distribution: {exc!r}. A resource that exists in the source "
                    "tree but not the wheel is an undeclared package-data entry."
                ),
                package=package,
                resource=name,
            ) from exc
    return origins


def stage_resource_content(imported: dict[str, object]) -> dict[str, object]:
    """Resolution succeeded; now prove the content is the real thing."""
    kit = imported["kit"]
    harness = imported["harness"]

    try:
        schema = kit.load_report_schema()
    except Exception as exc:  # noqa: BLE001
        raise ProbeFailure(
            "PACKAGED_RESOURCE_INVALID",
            f"the bundled report schema did not parse: {exc!r}",
        ) from exc

    declared_id = schema.get("$id") if isinstance(schema, dict) else None
    if declared_id != EXPECTED_SCHEMA_ID:
        raise ProbeFailure(
            "PACKAGED_RESOURCE_INVALID",
            f"bundled schema declares $id {declared_id!r}, expected {EXPECTED_SCHEMA_ID!r}",
            declared_id=declared_id,
        )

    violations = schema_closure_violations(schema)
    if violations:
        raise ProbeFailure(
            "PACKAGED_RESOURCE_INVALID",
            (
                "bundled schema leaves object definitions open; an open schema "
                "cannot reject a malformed report"
            ),
            open_objects=violations,
        )

    # The fixture is not merely readable text: it has to compose, lock, and load
    # as a governance contract. Reading bytes would prove the file shipped;
    # building an Authorizer proves it shipped *intact*.
    try:
        authorizer = harness.build_authorizer()
        subject_revision = authorizer.subject_revision
    except Exception as exc:  # noqa: BLE001
        raise ProbeFailure(
            "PACKAGED_RESOURCE_INVALID",
            f"the bundled contract fixture did not load as a governance contract: {exc!r}",
            traceback=traceback.format_exc(),
        ) from exc

    return {
        "schema_id": declared_id,
        "schema_version": kit.CONFORMANCE_SCHEMA_VERSION,
        "fixture_subject_revision": subject_revision,
    }


def stage_conformance(imported: dict[str, object]) -> dict[str, object]:
    """Run the kit from the installed distribution and validate its own report."""
    kit = imported["kit"]
    try:
        report = kit.run_conformance(frameworks=list(BASE_SUITES))
        payload = report.as_dict()
    except Exception as exc:  # noqa: BLE001
        raise ProbeFailure(
            "CONFORMANCE_EXECUTION_FAILED",
            f"the installed conformance kit raised: {exc!r}",
            traceback=traceback.format_exc(),
        ) from exc

    diagnostics = kit.validate_report(payload)
    if diagnostics:
        raise ProbeFailure(
            "CONFORMANCE_EXECUTION_FAILED",
            "the emitted report failed validation against its own bundled schema",
            diagnostics=[str(item) for item in diagnostics],
        )

    if payload.get("outcome") != "pass":
        failed = [
            case.get("id")
            for suite in payload.get("suites", [])
            for case in suite.get("cases", [])
            if case.get("outcome") == "fail"
        ]
        raise ProbeFailure(
            "CONFORMANCE_EXECUTION_FAILED",
            f"conformance outcome is {payload.get('outcome')!r}, expected 'pass'",
            failed_cases=failed,
        )

    # Determinism, observed from the installed distribution rather than assumed.
    if kit.serialize(report) != kit.serialize(kit.run_conformance(frameworks=list(BASE_SUITES))):
        raise ProbeFailure(
            "CONFORMANCE_EXECUTION_FAILED",
            "two identical runs produced different reports; the report is not deterministic",
        )

    safety = payload.get("safety", {})
    # On the base pip-only path no framework extra is installed, so no suite
    # instantiates a model. `false` here is an *observed* value, not a
    # convenient default -- a native CrewAI run reports `true` for this field.
    if safety.get("scripted_in_process_model_called") is not False:
        raise ProbeFailure(
            "CONFORMANCE_EXECUTION_FAILED",
            (
                "scripted_in_process_model_called is "
                f"{safety.get('scripted_in_process_model_called')!r} on a base-suite run "
                "that instantiates no model"
            ),
        )
    if safety.get("external_model_service_called") is not False:
        raise ProbeFailure(
            "CONFORMANCE_EXECUTION_FAILED",
            "external_model_service_called is not false",
        )

    return {
        "outcome": payload["outcome"],
        "schema": payload.get("schema"),
        "schema_version": payload.get("schema_version"),
        "assurance_tier": payload.get("assurance_tier"),
        "nornyx_version": payload.get("nornyx_version"),
        "adapter_version": payload.get("adapter_version"),
        "spi_version": payload.get("spi_version"),
        "suites": [
            {
                "outcome": suite.get("outcome"),
                "cases": len(suite.get("cases", [])),
            }
            for suite in payload.get("suites", [])
        ],
        "cases": sum(len(suite.get("cases", [])) for suite in payload.get("suites", [])),
        "safety": safety,
    }


def build_audit(
    *,
    imported: dict[str, object],
    resource_origins: dict[str, str],
    content: dict[str, object],
    conformance: dict[str, object],
    site_packages: str,
    import_origins: dict[str, str],
) -> dict[str, object]:
    """The independently auditable record this example exists to emit."""
    safety = conformance.get("safety", {})
    return {
        "distribution": {
            "name": DISTRIBUTION_NAME,
            "version": imported["installed_version"],
            "dunder_version": imported["dunder_version"],
        },
        "environment": {
            "python": sys.version.split()[0],
            "executable": sys.executable,
            "site_packages": site_packages,
            "working_directory": os.getcwd(),
        },
        "import_origins": import_origins,
        "resource_origins": resource_origins,
        "resource_content": content,
        "conformance": {
            key: value for key, value in conformance.items() if key != "safety"
        },
        # The distinction that keeps this record honest. Emitting only the
        # structural constant would read as evidence while measuring nothing.
        "model_calls": {
            "external_model_service_called": {
                "value": safety.get("external_model_service_called"),
                "kind": "structural_constant",
                "means": (
                    "a design property of the kit: it contacts no external model "
                    "service or endpoint"
                ),
            },
            "scripted_in_process_model_called": {
                "value": safety.get("scripted_in_process_model_called"),
                "kind": "observed",
                "means": (
                    "measured per run; false here because the base pip-only path "
                    "installs no framework extra and instantiates no model"
                ),
            },
        },
        "safety": safety,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pip-only distribution conformance probe.")
    parser.add_argument("--expect-version", required=True)
    parser.add_argument("--forbidden-root", action="append", default=[])
    args = parser.parse_args(argv)

    site_packages = str(Path(sysconfig.get_paths()["purelib"]).resolve())
    forbidden_roots = [str(Path(root).resolve()) for root in args.forbidden_root]

    try:
        imported = stage_import()
        stage_version(imported, args.expect_version)

        import_origins = {
            "nornyx_agentic_adapters": str(Path(imported["naa"].__file__).resolve()),
            "conformance_kit": str(Path(imported["kit"].__file__).resolve()),
        }
        resource_origins = stage_resources(imported)

        findings = leakage_findings(
            {**import_origins, **resource_origins},
            site_packages=site_packages,
            forbidden_roots=forbidden_roots,
        )
        if findings:
            raise ProbeFailure(
                "SOURCE_TREE_LEAKAGE_DETECTED",
                "one or more artifacts did not resolve from the installed distribution",
                findings=findings,
            )

        content = stage_resource_content(imported)
        conformance = stage_conformance(imported)
        audit = build_audit(
            imported=imported,
            resource_origins=resource_origins,
            content=content,
            conformance=conformance,
            site_packages=site_packages,
            import_origins=import_origins,
        )
    except ProbeFailure as failure:
        envelope = {
            "status": "fail",
            "failure_class": failure.failure_class,
            "detail": failure.detail,
            "evidence": failure.evidence,
        }
        print(f"{RESULT_SENTINEL} {json.dumps(envelope, sort_keys=True, default=str)}")
        return 1

    envelope = {"status": "pass", "failure_class": None, "detail": "", "audit": audit}
    print(f"{RESULT_SENTINEL} {json.dumps(envelope, sort_keys=True, default=str)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
