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
from pathlib import Path
import sys

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
