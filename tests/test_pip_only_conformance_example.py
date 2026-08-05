"""Tests for the pip-only registry-backed conformance example.

These run offline. The example's *network* behaviour -- actually installing a
published distribution from the index -- is exercised by the `pip-only-example`
CI job and by running the module directly; wiring that into the ordinary test
suite would make every unit run depend on PyPI availability.

What is covered here is everything that can be verified without the index: the
failure taxonomy, the containment and schema-closure logic the leakage and
resource checks are built on, the envelope classification, and the structural
invariant that keeps the probe runnable inside a clean environment at all.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = REPO_ROOT / "examples"
EXAMPLE_DIR = EXAMPLES_DIR / "pip_only_conformance"

# Imported as a package for the same reason the benchmark suite does it: the
# module names here (failures, probe, runner) are generic enough to collide with
# other example packages if their directory went on sys.path directly.
if str(EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLES_DIR))

from pip_only_conformance import failures as failures_mod  # noqa: E402
from pip_only_conformance import probe as probe_mod  # noqa: E402
from pip_only_conformance import runner as runner_mod  # noqa: E402

FailureClass = failures_mod.FailureClass
PipOnlyExampleError = failures_mod.PipOnlyExampleError


# ---------------------------------------------------------------------------
# Failure taxonomy
# ---------------------------------------------------------------------------


def test_taxonomy_is_exactly_the_seven_agreed_classes() -> None:
    assert {member.value for member in FailureClass} == {
        "REGISTRY_INSTALL_FAILED",
        "INSTALLED_VERSION_MISMATCH",
        "SOURCE_TREE_LEAKAGE_DETECTED",
        "PACKAGED_RESOURCE_MISSING",
        "PACKAGED_RESOURCE_INVALID",
        "CONFORMANCE_EXECUTION_FAILED",
        "EXAMPLE_INPUT_INVALID",
    }


def test_only_caller_error_is_not_attributed_to_the_distribution() -> None:
    """Misusing the example must never read as a defect in the published package."""
    caller_error = PipOnlyExampleError(FailureClass.EXAMPLE_INPUT_INVALID, "bad input")
    assert caller_error.attributable_to_distribution is False

    for member in FailureClass:
        if member is FailureClass.EXAMPLE_INPUT_INVALID:
            continue
        assert PipOnlyExampleError(member, "x").attributable_to_distribution is True


def test_error_serializes_class_detail_and_attribution() -> None:
    error = PipOnlyExampleError(
        FailureClass.PACKAGED_RESOURCE_MISSING, "no schema", evidence={"package": "p"}
    )
    payload = error.as_dict()
    assert payload["failure_class"] == "PACKAGED_RESOURCE_MISSING"
    assert payload["detail"] == "no schema"
    assert payload["attributable_to_distribution"] is True
    assert payload["evidence"] == {"package": "p"}


# ---------------------------------------------------------------------------
# Path containment -- the basis of the leakage check
# ---------------------------------------------------------------------------


def test_path_containment_is_not_a_string_prefix_test(tmp_path: Path) -> None:
    """`/a/bc` must not count as living inside `/a/b`."""
    base = tmp_path / "b"
    sibling = tmp_path / "bc"
    base.mkdir()
    sibling.mkdir()
    inner = base / "deep" / "file.py"
    inner.parent.mkdir(parents=True)
    inner.write_text("", encoding="utf-8")

    assert probe_mod.path_is_inside(inner, base) is True
    assert probe_mod.path_is_inside(base, base) is True
    assert probe_mod.path_is_inside(sibling, base) is False


def test_leakage_is_clean_when_every_origin_is_under_site_packages(tmp_path: Path) -> None:
    site = tmp_path / "site-packages"
    (site / "nornyx_agentic_adapters").mkdir(parents=True)
    origins = {
        "nornyx_agentic_adapters": str(site / "nornyx_agentic_adapters" / "__init__.py"),
        "report_schema": str(site / "nornyx_agentic_adapters" / "s.json"),
    }
    findings = probe_mod.leakage_findings(
        origins, site_packages=str(site), forbidden_roots=[str(tmp_path / "repo")]
    )
    assert findings == []


def test_leakage_flags_an_origin_outside_site_packages(tmp_path: Path) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    elsewhere = tmp_path / "elsewhere" / "mod.py"
    elsewhere.parent.mkdir(parents=True)

    findings = probe_mod.leakage_findings(
        {"conformance_kit": str(elsewhere)}, site_packages=str(site), forbidden_roots=[]
    )
    assert len(findings) == 1
    assert findings[0]["label"] == "conformance_kit"
    assert "outside the environment's site-packages" in findings[0]["reason"]


def test_leakage_flags_a_repository_root_even_when_it_looks_installed(tmp_path: Path) -> None:
    """The case that matters: a checkout that is *also* under site-packages.

    An editable or `pip install .` layout can put repository paths on the import
    path in ways a naive site-packages check would bless. Naming the repository
    roots explicitly is what makes this falsifiable.
    """
    site = tmp_path / "site-packages"
    repo = site / "checkout"
    repo.mkdir(parents=True)
    leaked = repo / "nornyx_agentic_adapters" / "__init__.py"
    leaked.parent.mkdir(parents=True)

    findings = probe_mod.leakage_findings(
        {"nornyx_agentic_adapters": str(leaked)},
        site_packages=str(site),
        forbidden_roots=[str(repo)],
    )
    assert len(findings) == 1
    assert "inside a repository root" in findings[0]["reason"]


def test_repository_roots_include_this_checkout() -> None:
    roots = [Path(root) for root in runner_mod.repository_roots()]
    assert any(root == REPO_ROOT for root in roots)


# ---------------------------------------------------------------------------
# Schema closure -- the basis of PACKAGED_RESOURCE_INVALID
# ---------------------------------------------------------------------------


def test_closed_schema_reports_no_violations() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "safety": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"ok": {"type": "boolean"}},
            }
        },
    }
    assert probe_mod.schema_closure_violations(schema) == []


def test_open_nested_object_is_reported_with_its_pointer() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "safety": {"type": "object", "properties": {"ok": {"type": "boolean"}}}
        },
    }
    violations = probe_mod.schema_closure_violations(schema)
    assert violations == ["/properties/safety"]


def test_open_root_object_is_reported() -> None:
    assert probe_mod.schema_closure_violations(
        {"type": "object", "properties": {"a": {"type": "string"}}}
    ) == ["<root>"]


def test_closure_walks_into_lists() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "any": {"anyOf": [{"type": "object", "properties": {"x": {"type": "string"}}}]}
        },
    }
    assert probe_mod.schema_closure_violations(schema) == ["/properties/any/anyOf/0"]


# ---------------------------------------------------------------------------
# Envelope handling
# ---------------------------------------------------------------------------


def test_passing_envelope_yields_the_audit_record() -> None:
    envelope = {"status": "pass", "audit": {"distribution": {"version": "0.3.0"}}}
    assert runner_mod.raise_for_envelope(envelope) == {"distribution": {"version": "0.3.0"}}


def test_failing_envelope_is_raised_as_its_own_class() -> None:
    envelope = {
        "status": "fail",
        "failure_class": "PACKAGED_RESOURCE_MISSING",
        "detail": "schema absent",
        "evidence": {"package": "nornyx_agentic_adapters.conformance.schemas"},
    }
    with pytest.raises(PipOnlyExampleError) as caught:
        runner_mod.raise_for_envelope(envelope)
    assert caught.value.failure_class is FailureClass.PACKAGED_RESOURCE_MISSING
    assert caught.value.evidence["package"].endswith("schemas")


def test_unknown_failure_class_does_not_silently_pass() -> None:
    with pytest.raises(PipOnlyExampleError) as caught:
        runner_mod.raise_for_envelope({"status": "fail", "failure_class": "SOMETHING_NEW"})
    assert caught.value.failure_class is FailureClass.CONFORMANCE_EXECUTION_FAILED


def test_success_without_an_audit_record_is_a_failure() -> None:
    with pytest.raises(PipOnlyExampleError) as caught:
        runner_mod.raise_for_envelope({"status": "pass"})
    assert caught.value.failure_class is FailureClass.CONFORMANCE_EXECUTION_FAILED


def test_envelope_is_extracted_from_surrounding_output() -> None:
    stdout = f"noise\n{probe_mod.RESULT_SENTINEL} " '{"status": "pass", "audit": {}}' "\nmore\n"
    assert runner_mod.parse_envelope(stdout)["status"] == "pass"


def test_missing_envelope_is_reported_rather_than_read_as_success() -> None:
    with pytest.raises(PipOnlyExampleError) as caught:
        runner_mod.parse_envelope("Traceback (most recent call last):\n  boom\n")
    assert caught.value.failure_class is FailureClass.CONFORMANCE_EXECUTION_FAILED


def test_unparsable_envelope_is_reported() -> None:
    with pytest.raises(PipOnlyExampleError) as caught:
        runner_mod.parse_envelope(f"{probe_mod.RESULT_SENTINEL} not-json")
    assert caught.value.failure_class is FailureClass.CONFORMANCE_EXECUTION_FAILED


# ---------------------------------------------------------------------------
# Caller-input validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["", "   ", ">=0.3.0", "0.3.*", "latest", "v0.3.0"])
def test_inexact_versions_are_caller_errors(bad: str) -> None:
    with pytest.raises(PipOnlyExampleError) as caught:
        runner_mod.run_example(version=bad)
    assert caught.value.failure_class is FailureClass.EXAMPLE_INPUT_INVALID
    assert caught.value.attributable_to_distribution is False


def test_nonpositive_timeout_is_a_caller_error() -> None:
    with pytest.raises(PipOnlyExampleError) as caught:
        runner_mod.run_example(version="0.3.0", timeout=0)
    assert caught.value.failure_class is FailureClass.EXAMPLE_INPUT_INVALID


def test_default_version_is_an_exact_release() -> None:
    assert runner_mod._VERSION_RE.match(runner_mod.DEFAULT_VERSION)


# ---------------------------------------------------------------------------
# Structural invariants
# ---------------------------------------------------------------------------


def test_probe_imports_nothing_from_the_repository() -> None:
    """The probe is copied into a clean environment and run there.

    If it ever grows an import from its own package, it stops being runnable in
    the environment it exists to inspect -- and the failure would look like a
    packaging bug rather than an example bug. Enforced structurally.
    """
    tree = ast.parse((EXAMPLE_DIR / "probe.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"relative import at line {node.lineno}"
            assert not (node.module or "").startswith(
                ("examples", "pip_only_conformance", "nornyx.")
            ), f"repository import {node.module!r} at line {node.lineno}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(
                    ("examples", "pip_only_conformance")
                ), f"repository import {alias.name!r} at line {node.lineno}"


def test_probe_module_imports_without_the_adapter_installed() -> None:
    """Importing the probe must not require the distribution under test.

    The adapter is imported lazily inside the stages precisely so the pure
    helpers stay testable here. This test would fail the moment that changed.
    """
    assert probe_mod.EXPECTED_SCHEMA_ID == "nornyx.agentic_runtime_conformance.v1"
    assert probe_mod.BASE_SUITES == ("distribution", "enforcement_boundary")


def test_base_suites_require_no_framework_extra() -> None:
    """A pip-only run must not need crewai or langgraph to prove anything."""
    assert "crewai" not in probe_mod.BASE_SUITES
    assert "langgraph" not in probe_mod.BASE_SUITES


def test_readme_documents_every_failure_class() -> None:
    readme = (EXAMPLE_DIR / "README.md").read_text(encoding="utf-8")
    for member in FailureClass:
        assert member.value in readme, f"{member.value} is undocumented"


def test_readme_states_the_constant_versus_observed_distinction() -> None:
    readme = (EXAMPLE_DIR / "README.md").read_text(encoding="utf-8")
    assert "external_model_service_called" in readme
    assert "scripted_in_process_model_called" in readme
    assert "structural constant" in readme
    assert "observed" in readme


# ---------------------------------------------------------------------------
# Provenance -- which file, from where, of what type, with what hash
# ---------------------------------------------------------------------------

provenance_mod = __import__("pip_only_conformance.provenance", fromlist=["provenance"])


def _report(**overrides) -> dict:
    entry = {
        "metadata": {"name": "nornyx-agentic-adapters", "version": "0.3.0"},
        "download_info": {
            "url": (
                "https://files.pythonhosted.org/packages/ab/cd/"
                "nornyx_agentic_adapters-0.3.0-py3-none-any.whl"
            ),
            "archive_info": {"hashes": {"sha256": "a" * 64}},
        },
    }
    entry.update(overrides)
    return {"install": [{"metadata": {"name": "jsonschema", "version": "4.26.0"}}, entry]}


def test_provenance_reads_host_filename_type_and_hash() -> None:
    found = provenance_mod.parse_install_report(
        _report(), distribution="nornyx-agentic-adapters"
    )
    assert found.host == "files.pythonhosted.org"
    assert found.filename == "nornyx_agentic_adapters-0.3.0-py3-none-any.whl"
    assert found.artifact_type == "wheel"
    assert found.sha256 == "a" * 64
    assert found.from_pypi is True
    assert found.is_wheel is True
    assert provenance_mod.provenance_violations(
        found, expected_version="0.3.0", distribution="nornyx-agentic-adapters"
    ) == []


def test_provenance_matches_across_name_spellings() -> None:
    """`nornyx_agentic_adapters` and `nornyx-agentic-adapters` are the same project."""
    report = _report(metadata={"name": "nornyx_agentic_adapters", "version": "0.3.0"})
    assert (
        provenance_mod.parse_install_report(report, distribution="nornyx-agentic-adapters")
        is not None
    )


def test_absent_entry_is_a_provenance_violation() -> None:
    violations = provenance_mod.provenance_violations(
        None, expected_version="0.3.0", distribution="nornyx-agentic-adapters"
    )
    assert violations and "no entry" in violations[0]


def test_sdist_is_rejected_even_when_version_is_right() -> None:
    """An sdist is built locally; it is not the artifact consumers receive."""
    report = _report(
        download_info={
            "url": "https://files.pythonhosted.org/packages/ab/nornyx_agentic_adapters-0.3.0.tar.gz",
            "archive_info": {"hashes": {"sha256": "b" * 64}},
        }
    )
    found = provenance_mod.parse_install_report(report, distribution="nornyx-agentic-adapters")
    assert found.artifact_type == "sdist"
    violations = provenance_mod.provenance_violations(
        found, expected_version="0.3.0", distribution="nornyx-agentic-adapters"
    )
    assert any("not a wheel" in item for item in violations)


def test_non_pypi_host_is_rejected() -> None:
    """A mirror or private index must not pass as 'from PyPI'."""
    report = _report(
        download_info={
            "url": "https://internal.example.com/simple/nornyx_agentic_adapters-0.3.0-py3-none-any.whl",
            "archive_info": {"hashes": {"sha256": "c" * 64}},
        }
    )
    found = provenance_mod.parse_install_report(report, distribution="nornyx-agentic-adapters")
    violations = provenance_mod.provenance_violations(
        found, expected_version="0.3.0", distribution="nornyx-agentic-adapters"
    )
    assert any("not PyPI" in item for item in violations)


def test_missing_hash_is_a_violation() -> None:
    report = _report(
        download_info={
            "url": (
                "https://files.pythonhosted.org/packages/ab/"
                "nornyx_agentic_adapters-0.3.0-py3-none-any.whl"
            ),
            "archive_info": {},
        }
    )
    found = provenance_mod.parse_install_report(report, distribution="nornyx-agentic-adapters")
    violations = provenance_mod.provenance_violations(
        found, expected_version="0.3.0", distribution="nornyx-agentic-adapters"
    )
    assert any("SHA-256" in item for item in violations)


def test_version_disagreement_between_report_and_request_is_a_violation() -> None:
    found = provenance_mod.parse_install_report(
        _report(), distribution="nornyx-agentic-adapters"
    )
    violations = provenance_mod.provenance_violations(
        found, expected_version="0.4.0", distribution="nornyx-agentic-adapters"
    )
    assert any("expected '0.4.0'" in item for item in violations)


def test_legacy_single_hash_spelling_still_yields_provenance() -> None:
    report = _report(
        download_info={
            "url": (
                "https://files.pythonhosted.org/packages/ab/"
                "nornyx_agentic_adapters-0.3.0-py3-none-any.whl"
            ),
            "archive_info": {"hash": "sha256=" + "d" * 64},
        }
    )
    found = provenance_mod.parse_install_report(report, distribution="nornyx-agentic-adapters")
    assert found.sha256 == "d" * 64


def test_pip_environment_drops_every_index_redirection_vector(monkeypatch) -> None:
    """`PIP_INDEX_URL` and friends must not survive into the child."""
    monkeypatch.setenv("PIP_INDEX_URL", "https://evil.example.com/simple")
    monkeypatch.setenv("PIP_EXTRA_INDEX_URL", "https://also-evil.example.com/simple")
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))
    env = runner_mod._clean_env()
    assert "PIP_INDEX_URL" not in env
    assert "PIP_EXTRA_INDEX_URL" not in env
    assert "PYTHONPATH" not in env
    # A user- or site-level pip.conf can carry the same redirection.
    assert env["PIP_CONFIG_FILE"] == os.devnull


def test_install_command_binds_index_and_requires_a_wheel() -> None:
    """Read from the source: the two flags that make 'published wheel' checkable."""
    source = (EXAMPLE_DIR / "runner.py").read_text(encoding="utf-8")
    assert '"--index-url"' in source
    assert "PYPI_INDEX_URL" in source
    assert '"--only-binary"' in source
    assert '"--report"' in source


# ---------------------------------------------------------------------------
# Process truth -- the envelope must agree with the exit status
# ---------------------------------------------------------------------------


def test_pass_envelope_with_nonzero_exit_is_rejected() -> None:
    with pytest.raises(PipOnlyExampleError) as caught:
        runner_mod.check_process_consistency({"status": "pass"}, returncode=3)
    assert caught.value.failure_class is FailureClass.CONFORMANCE_EXECUTION_FAILED
    assert caught.value.evidence["returncode"] == 3


def test_fail_envelope_with_zero_exit_is_rejected() -> None:
    """A failing run that exits 0 would pass any exit-code-based gate."""
    with pytest.raises(PipOnlyExampleError) as caught:
        runner_mod.check_process_consistency({"status": "fail"}, returncode=0)
    assert caught.value.failure_class is FailureClass.CONFORMANCE_EXECUTION_FAILED


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(PipOnlyExampleError) as caught:
        runner_mod.check_process_consistency({"status": "maybe"}, returncode=0)
    assert caught.value.failure_class is FailureClass.CONFORMANCE_EXECUTION_FAILED


@pytest.mark.parametrize("status,code", [("pass", 0), ("fail", 1), ("fail", 2)])
def test_consistent_combinations_are_accepted(status: str, code: int) -> None:
    runner_mod.check_process_consistency({"status": status}, returncode=code)


# ---------------------------------------------------------------------------
# Fault injection -- every class forced through the public path
# ---------------------------------------------------------------------------


class _FakeModule:
    def __init__(self, path: str) -> None:
        self.__file__ = path


def _probe_envelope(capsys) -> dict:
    captured = capsys.readouterr().out
    for line in captured.splitlines():
        if line.startswith(probe_mod.RESULT_SENTINEL):
            return json.loads(line[len(probe_mod.RESULT_SENTINEL) :])
    raise AssertionError(f"probe emitted no envelope:\n{captured}")


def _site_packages(monkeypatch, tmp_path: Path) -> Path:
    """Pin the probe's notion of site-packages so fakes can live inside it.

    Without this the fault tests would depend on the real interpreter's
    purelib, and every injected origin would fail the containment check for the
    wrong reason.
    """
    site = tmp_path / "site-packages"
    site.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        probe_mod.sysconfig, "get_paths", lambda *a, **k: {"purelib": str(site)}
    )
    return site


def _installed(site: Path, version: str = "0.3.0") -> dict:
    package = site / "nornyx_agentic_adapters"
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    origin = str(package / "__init__.py")
    return {
        "naa": _FakeModule(origin),
        "kit": _FakeModule(origin),
        "harness": _FakeModule(origin),
        "report_module": _FakeModule(origin),
        "installed_version": version,
        "dunder_version": version,
        "_origin": origin,
    }


def test_fault_installed_version_mismatch(monkeypatch, capsys, tmp_path) -> None:
    site = _site_packages(monkeypatch, tmp_path)
    monkeypatch.setattr(probe_mod, "stage_import", lambda: _installed(site, "0.2.0"))
    code = probe_mod.main(["--expect-version", "0.3.0"])
    envelope = _probe_envelope(capsys)
    assert code == 1
    assert envelope["failure_class"] == "INSTALLED_VERSION_MISMATCH"
    assert envelope["evidence"]["installed_version"] == "0.2.0"
    assert PipOnlyExampleError(
        FailureClass(envelope["failure_class"]), ""
    ).attributable_to_distribution is True


def test_fault_metadata_and_dunder_version_disagree(monkeypatch, capsys, tmp_path) -> None:
    site = _site_packages(monkeypatch, tmp_path)
    imported = _installed(site, "0.3.0")
    imported["dunder_version"] = "0.2.0"
    monkeypatch.setattr(probe_mod, "stage_import", lambda: imported)
    assert probe_mod.main(["--expect-version", "0.3.0"]) == 1
    assert _probe_envelope(capsys)["failure_class"] == "INSTALLED_VERSION_MISMATCH"


def test_fault_source_tree_leakage(monkeypatch, capsys, tmp_path) -> None:
    """A checkout nested *inside* site-packages must still be caught.

    This is the case a naive site-packages check would bless: the origin really
    is under site-packages, and only the explicit repository root reveals it.
    """
    site = _site_packages(monkeypatch, tmp_path)
    checkout = site / "checkout"
    leaked = checkout / "nornyx_agentic_adapters" / "__init__.py"
    leaked.parent.mkdir(parents=True)
    leaked.write_text("", encoding="utf-8")

    imported = _installed(site)
    imported["naa"] = _FakeModule(str(leaked))
    monkeypatch.setattr(probe_mod, "stage_import", lambda: imported)
    monkeypatch.setattr(probe_mod, "stage_resources", lambda _i: {})

    code = probe_mod.main(
        ["--expect-version", "0.3.0", "--forbidden-root", str(checkout)]
    )
    envelope = _probe_envelope(capsys)
    assert code == 1
    assert envelope["failure_class"] == "SOURCE_TREE_LEAKAGE_DETECTED"
    findings = {item["label"]: item for item in envelope["evidence"]["findings"]}
    assert set(findings) == {"nornyx_agentic_adapters"}
    assert "inside a repository root" in findings["nornyx_agentic_adapters"]["reason"]


def test_fault_packaged_resource_missing(monkeypatch, capsys, tmp_path) -> None:
    """A resource package that does not exist is a MISSING, not an INVALID."""
    site = _site_packages(monkeypatch, tmp_path)
    imported = _installed(site)
    imported["report_module"].SCHEMA_PACKAGE = "nornyx_absent_package_xyz.schemas"
    imported["report_module"].SCHEMA_NAME = "nope.json"
    imported["harness"].FIXTURE_PACKAGE = "nornyx_absent_package_xyz.fixtures"
    imported["harness"].FIXTURE_NAME = "nope.nyx"
    monkeypatch.setattr(probe_mod, "stage_import", lambda: imported)

    assert probe_mod.main(["--expect-version", "0.3.0"]) == 1
    envelope = _probe_envelope(capsys)
    assert envelope["failure_class"] == "PACKAGED_RESOURCE_MISSING"
    assert "package-data" in envelope["detail"]


def _invalid_content_setup(monkeypatch, tmp_path, *, schema, authorizer_raises=False):
    site = _site_packages(monkeypatch, tmp_path)
    imported = _installed(site)
    origin = imported["_origin"]

    class _Kit:
        __file__ = origin
        CONFORMANCE_SCHEMA_VERSION = "1.0"

        @staticmethod
        def load_report_schema():
            return schema

    class _Harness:
        __file__ = origin

        @staticmethod
        def build_authorizer():
            if authorizer_raises:
                raise ValueError("fixture is truncated")
            return type("A", (), {"subject_revision": "git:deadbeef"})()

    imported["kit"] = _Kit()
    imported["harness"] = _Harness()
    monkeypatch.setattr(probe_mod, "stage_import", lambda: imported)
    monkeypatch.setattr(probe_mod, "stage_resources", lambda _i: {})
    return imported


def test_fault_resource_invalid_wrong_schema_identity(monkeypatch, capsys, tmp_path) -> None:
    _invalid_content_setup(
        monkeypatch, tmp_path, schema={"$id": "nornyx.adapter_conformance.v0.7"}
    )
    assert probe_mod.main(["--expect-version", "0.3.0"]) == 1
    envelope = _probe_envelope(capsys)
    assert envelope["failure_class"] == "PACKAGED_RESOURCE_INVALID"
    assert envelope["evidence"]["declared_id"] == "nornyx.adapter_conformance.v0.7"


def test_fault_resource_invalid_open_schema(monkeypatch, capsys, tmp_path) -> None:
    """An open schema cannot reject a malformed report, so it is not valid."""
    _invalid_content_setup(
        monkeypatch,
        tmp_path,
        schema={
            "$id": probe_mod.EXPECTED_SCHEMA_ID,
            "type": "object",
            "properties": {"safety": {"type": "object", "properties": {}}},
        },
    )
    assert probe_mod.main(["--expect-version", "0.3.0"]) == 1
    envelope = _probe_envelope(capsys)
    assert envelope["failure_class"] == "PACKAGED_RESOURCE_INVALID"
    assert "<root>" in envelope["evidence"]["open_objects"]


def test_fault_resource_invalid_fixture_does_not_load(monkeypatch, capsys, tmp_path) -> None:
    """Present-but-truncated is INVALID; reading bytes would have passed it."""
    _invalid_content_setup(
        monkeypatch,
        tmp_path,
        schema={"$id": probe_mod.EXPECTED_SCHEMA_ID, "type": "object",
                "additionalProperties": False, "properties": {}},
        authorizer_raises=True,
    )
    assert probe_mod.main(["--expect-version", "0.3.0"]) == 1
    envelope = _probe_envelope(capsys)
    assert envelope["failure_class"] == "PACKAGED_RESOURCE_INVALID"
    assert "governance contract" in envelope["detail"]


def _conformance_setup(monkeypatch, tmp_path, *, payload, diagnostics=()):
    site = _site_packages(monkeypatch, tmp_path)
    imported = _installed(site)
    origin = imported["_origin"]

    class _Kit:
        __file__ = origin
        CONFORMANCE_SCHEMA_VERSION = "1.0"

        @staticmethod
        def load_report_schema():
            return {
                "$id": probe_mod.EXPECTED_SCHEMA_ID,
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            }

        @staticmethod
        def run_conformance(frameworks=None):
            return type("R", (), {"as_dict": staticmethod(lambda: payload)})()

        @staticmethod
        def validate_report(_payload):
            return diagnostics

        @staticmethod
        def serialize(_report):
            return "stable"

    class _Harness:
        __file__ = origin

        @staticmethod
        def build_authorizer():
            return type("A", (), {"subject_revision": "git:deadbeef"})()

    imported["kit"] = _Kit()
    imported["harness"] = _Harness()
    monkeypatch.setattr(probe_mod, "stage_import", lambda: imported)
    monkeypatch.setattr(probe_mod, "stage_resources", lambda _i: {})


_GOOD_SAFETY = {
    "scripted_in_process_model_called": False,
    "external_model_service_called": False,
}


def test_fault_conformance_outcome_not_pass(monkeypatch, capsys, tmp_path) -> None:
    _conformance_setup(
        monkeypatch,
        tmp_path,
        payload={
            "outcome": "fail",
            "safety": _GOOD_SAFETY,
            "suites": [{"cases": [{"id": "c1", "outcome": "fail"}]}],
        },
    )
    assert probe_mod.main(["--expect-version", "0.3.0"]) == 1
    envelope = _probe_envelope(capsys)
    assert envelope["failure_class"] == "CONFORMANCE_EXECUTION_FAILED"
    assert envelope["evidence"]["failed_cases"] == ["c1"]


def test_fault_report_fails_its_own_schema(monkeypatch, capsys, tmp_path) -> None:
    _conformance_setup(
        monkeypatch,
        tmp_path,
        payload={"outcome": "pass", "safety": _GOOD_SAFETY, "suites": []},
        diagnostics=("safety.blocked_outbound_attempts is required",),
    )
    assert probe_mod.main(["--expect-version", "0.3.0"]) == 1
    envelope = _probe_envelope(capsys)
    assert envelope["failure_class"] == "CONFORMANCE_EXECUTION_FAILED"
    assert envelope["evidence"]["diagnostics"]


def test_fault_scripted_model_true_on_a_base_run(monkeypatch, capsys, tmp_path) -> None:
    """The observed field must stay observed: true here would be a real defect."""
    _conformance_setup(
        monkeypatch,
        tmp_path,
        payload={
            "outcome": "pass",
            "suites": [],
            "safety": {
                "scripted_in_process_model_called": True,
                "external_model_service_called": False,
            },
        },
    )
    assert probe_mod.main(["--expect-version", "0.3.0"]) == 1
    envelope = _probe_envelope(capsys)
    assert envelope["failure_class"] == "CONFORMANCE_EXECUTION_FAILED"
    assert "instantiates no model" in envelope["detail"]


def test_fault_registry_install_failed_through_the_runner(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(runner_mod, "_create_environment", lambda root: tmp_path / "python")
    monkeypatch.setattr(
        runner_mod,
        "_run",
        lambda *a, **k: runner_mod._Completed(returncode=1, stdout="", stderr="No matching dist"),
    )
    with pytest.raises(PipOnlyExampleError) as caught:
        runner_mod.run_example(version="0.3.0", timeout=30)
    assert caught.value.failure_class is FailureClass.REGISTRY_INSTALL_FAILED
    assert caught.value.evidence["returncode"] == 1


def test_fault_install_timeout_is_classified(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(runner_mod, "_create_environment", lambda root: tmp_path / "python")
    monkeypatch.setattr(
        runner_mod,
        "_run",
        lambda *a, **k: runner_mod._Completed(returncode=-1, stdout="", stderr="", timed_out=True),
    )
    with pytest.raises(PipOnlyExampleError) as caught:
        runner_mod.run_example(version="0.3.0", timeout=30)
    assert caught.value.failure_class is FailureClass.REGISTRY_INSTALL_FAILED
    assert "timed out" in caught.value.detail


def test_fault_pip_launch_failure_is_classified(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(runner_mod, "_create_environment", lambda root: tmp_path / "python")
    monkeypatch.setattr(
        runner_mod,
        "_run",
        lambda *a, **k: runner_mod._Completed(
            returncode=-1, stdout="", stderr="", launch_error="no such file"
        ),
    )
    with pytest.raises(PipOnlyExampleError) as caught:
        runner_mod.run_example(version="0.3.0", timeout=30)
    assert caught.value.failure_class is FailureClass.REGISTRY_INSTALL_FAILED
    assert "could not be launched" in caught.value.detail


def test_venv_creation_failure_is_never_blamed_on_the_package(monkeypatch) -> None:
    def _boom(_root):
        raise OSError("disk full")

    monkeypatch.setattr(runner_mod.venv.EnvBuilder, "create", lambda self, root: _boom(root))
    with pytest.raises(PipOnlyExampleError) as caught:
        runner_mod.run_example(version="0.3.0", timeout=30)
    assert caught.value.failure_class is FailureClass.EXAMPLE_INPUT_INVALID
    assert caught.value.attributable_to_distribution is False


def test_every_failure_class_has_fault_injection_coverage() -> None:
    """Guard against a class being added without a test that forces it."""
    covered = {
        "REGISTRY_INSTALL_FAILED",
        "INSTALLED_VERSION_MISMATCH",
        "SOURCE_TREE_LEAKAGE_DETECTED",
        "PACKAGED_RESOURCE_MISSING",
        "PACKAGED_RESOURCE_INVALID",
        "CONFORMANCE_EXECUTION_FAILED",
        "EXAMPLE_INPUT_INVALID",
    }
    assert {member.value for member in FailureClass} == covered
    source = Path(__file__).read_text(encoding="utf-8")
    for name in covered:
        assert source.count(name) >= 2, f"{name} lacks fault-injection coverage"


# ---------------------------------------------------------------------------
# The no-clone claim
# ---------------------------------------------------------------------------


def test_checkout_detection_is_marker_based_not_depth_based(tmp_path: Path) -> None:
    """Copied out of the repository, the example must claim no repository roots.

    A fixed parent-depth rule would name an arbitrary ancestor of the copy --
    and since the clean venv is created under the system temp root, that could
    forbid the very directory the installation lives in.
    """
    staging = tmp_path / "standalone"
    shutil.copytree(
        EXAMPLE_DIR, staging / "pip_only_conformance",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    code = textwrap.dedent(
        """
        import json, sys
        from pip_only_conformance.runner import repository_roots
        print(json.dumps(repository_roots()))
        """
    )
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH"}}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=staging,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) == []


def test_checkout_detection_finds_this_repository() -> None:
    """The same rule must still identify a real checkout when there is one."""
    assert str(REPO_ROOT) in runner_mod.repository_roots()


def test_standalone_launcher_copies_only_the_package() -> None:
    source = (REPO_ROOT / "scripts" / "run_pip_only_example_standalone.py").read_text(
        encoding="utf-8"
    )
    assert "copytree" in source
    assert "PACKAGE_DIR" in source
    # It must strip the repository from the child's import path and then prove
    # no repository path appears anywhere in the emitted record.
    assert "PYTHONPATH" in source
    assert "_assert_no_repository_paths" in source


#: Top-level modules the copied package must never import. `nornyx` is the core
#: package: the example must not need it, only the adapter distribution it
#: installs. `nornyx_agentic_adapters` is deliberately absent from this set --
#: it is the distribution under test, imported from the clean environment.
_FORBIDDEN_ROOTS = {"examples", "tests", "nornyx", "scripts", "integrations", "adapters"}


def test_example_package_has_no_repository_imports() -> None:
    """The whole package, not just the probe, must be copyable and runnable.

    Any absolute import of a repository top-level module would make the
    standalone copy fail at import time rather than at verification time.
    """
    offenders: list[str] = []
    for module in sorted(EXAMPLE_DIR.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                root = (node.module or "").split(".")[0]
            elif isinstance(node, ast.Import):
                root = node.names[0].name.split(".")[0]
            else:
                continue
            if root in _FORBIDDEN_ROOTS:
                offenders.append(f"{module.name}:{node.lineno} imports {root!r}")
    assert offenders == []


def test_probe_may_import_the_distribution_under_test() -> None:
    """Guard the exemption above so it cannot quietly widen.

    The probe must import `nornyx_agentic_adapters` — that is its job. The
    check must not be written so loosely that it would also permit `nornyx`.
    """
    assert "nornyx_agentic_adapters" not in _FORBIDDEN_ROOTS
    assert "nornyx" in _FORBIDDEN_ROOTS
    source = (EXAMPLE_DIR / "probe.py").read_text(encoding="utf-8")
    assert "import nornyx_agentic_adapters" in source
