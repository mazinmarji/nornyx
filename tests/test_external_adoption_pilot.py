"""Tests for the external adoption pilot (M5-A-1).

These run offline. The pilot's network behaviour — installing published
distributions and driving CrewAI — is exercised by the `external-adoption-pilot`
CI job and by running the module directly; wiring it into the ordinary suite
would make every unit run depend on PyPI availability and a large framework
install.

What is covered here is the part that decides whether a run *means* anything:
the failure taxonomy and its attribution, the comparative governance checks, the
containment logic behind leakage detection, envelope and process-consistency
handling, and the structural invariants that keep the scenario runnable inside a
clean environment.
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
PILOT_DIR = EXAMPLES_DIR / "external_adoption_pilot"

if str(EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLES_DIR))

from external_adoption_pilot import failures as failures_mod  # noqa: E402
from external_adoption_pilot import runner as runner_mod  # noqa: E402
from external_adoption_pilot import scenario as scenario_mod  # noqa: E402

PilotFailure = failures_mod.PilotFailure
PilotError = failures_mod.PilotError


# ---------------------------------------------------------------------------
# Taxonomy and attribution
# ---------------------------------------------------------------------------


def test_taxonomy_is_exactly_the_seven_pilot_classes() -> None:
    assert {member.value for member in PilotFailure} == {
        "REGISTRY_INSTALL_FAILED",
        "INSTALLED_VERSION_MISMATCH",
        "FRAMEWORK_EXTRA_UNAVAILABLE",
        "SOURCE_TREE_LEAKAGE_DETECTED",
        "SCENARIO_EXECUTION_FAILED",
        "GOVERNANCE_EXPECTATION_UNMET",
        "PILOT_INPUT_INVALID",
    }


def test_only_caller_error_is_not_attributed_to_the_distributions() -> None:
    assert (
        PilotError(PilotFailure.PILOT_INPUT_INVALID, "x").attributable_to_distribution
        is False
    )
    for member in PilotFailure:
        if member is PilotFailure.PILOT_INPUT_INVALID:
            continue
        assert PilotError(member, "x").attributable_to_distribution is True


def test_every_class_carries_an_actionable_remedy() -> None:
    """A first-time user needs to know what to do, not just what broke."""
    for member in PilotFailure:
        remedy = PilotError(member, "x").remedy
        assert remedy and len(remedy) > 40, member


def test_serialized_failure_carries_class_attribution_and_remedy() -> None:
    payload = PilotError(
        PilotFailure.FRAMEWORK_EXTRA_UNAVAILABLE, "crewai missing", evidence={"v": "1"}
    ).as_dict()
    assert payload["failure_class"] == "FRAMEWORK_EXTRA_UNAVAILABLE"
    assert payload["attributable_to_distribution"] is True
    assert "extra" in payload["remedy"]
    assert payload["evidence"] == {"v": "1"}


# ---------------------------------------------------------------------------
# The comparative governance checks -- the pilot's primary control
# ---------------------------------------------------------------------------


def _variants(**overrides) -> dict[str, dict]:
    base = {
        "ungoverned": {
            "executions": 1, "authorizations": 0,
            "decision_events": [], "observation_events": [],
        },
        "governed_authorized": {
            "executions": 1, "authorizations": 1,
            "decision_events": ["capability_requested", "capability_allowed"],
            "observation_events": ["tool_invoked"],
        },
        "governed_unauthorized": {
            "executions": 0, "authorizations": 1,
            "decision_events": ["capability_requested", "capability_denied"],
            "observation_events": [],
        },
    }
    for key, patch in overrides.items():
        base[key] = {**base[key], **patch}
    return base


def test_a_healthy_run_reports_no_governance_problems() -> None:
    assert scenario_mod.governance_problems(_variants()) == []


def test_retried_denials_are_fine_while_they_pair_up() -> None:
    """CrewAI may retry a denied tool call; every request must still be answered."""
    problems = scenario_mod.governance_problems(
        _variants(
            governed_unauthorized={
                "decision_events": [
                    "capability_requested", "capability_denied",
                    "capability_requested", "capability_denied",
                    "capability_requested", "capability_denied",
                ],
                "authorizations": 3,
            }
        )
    )
    assert problems == []


def test_unpaired_requests_and_denials_are_reported() -> None:
    problems = scenario_mod.governance_problems(
        _variants(
            governed_unauthorized={
                "decision_events": [
                    "capability_requested", "capability_denied", "capability_requested",
                ]
            }
        )
    )
    assert any("did not pair" in item for item in problems)


def test_fail_closed_violation_is_the_headline_problem() -> None:
    """The action running on a denied capability is the defect that matters."""
    problems = scenario_mod.governance_problems(
        _variants(governed_unauthorized={"executions": 1})
    )
    assert any("fail-closed did not hold" in item for item in problems)


def test_blocking_the_authorized_path_is_also_a_failure() -> None:
    """A control that only ever blocks is an outage, not governance."""
    problems = scenario_mod.governance_problems(
        _variants(governed_authorized={"executions": 0})
    )
    assert any("outage" in item for item in problems)


def test_a_dead_baseline_invalidates_the_whole_comparison() -> None:
    """If the ungoverned action never ran, a denial demonstrates nothing."""
    problems = scenario_mod.governance_problems(
        _variants(ungoverned={"executions": 0})
    )
    assert any("demonstrates nothing" in item for item in problems)


def test_success_observation_on_denial_is_reported() -> None:
    problems = scenario_mod.governance_problems(
        _variants(governed_unauthorized={"observation_events": ["tool_invoked"]})
    )
    assert any("success observation" in item for item in problems)


def test_missing_allowed_event_is_reported() -> None:
    problems = scenario_mod.governance_problems(
        _variants(governed_authorized={"decision_events": ["capability_requested"]})
    )
    assert any("capability_allowed" in item for item in problems)


def test_evidence_appearing_without_governance_is_reported() -> None:
    problems = scenario_mod.governance_problems(
        _variants(ungoverned={"decision_events": ["capability_allowed"]})
    )
    assert any("decision evidence" in item for item in problems)


# ---------------------------------------------------------------------------
# Containment / leakage
# ---------------------------------------------------------------------------


def test_containment_is_not_a_string_prefix_test(tmp_path: Path) -> None:
    base = tmp_path / "b"
    sibling = tmp_path / "bc"
    base.mkdir()
    sibling.mkdir()
    assert scenario_mod.path_is_inside(base / "x.py", base) is True
    assert scenario_mod.path_is_inside(sibling / "x.py", base) is False


def test_leakage_flags_a_checkout_nested_inside_site_packages(tmp_path: Path) -> None:
    site = tmp_path / "site-packages"
    checkout = site / "checkout"
    checkout.mkdir(parents=True)
    findings = scenario_mod.leakage_findings(
        {"crewai": str(checkout / "crewai" / "__init__.py")},
        site_packages=str(site),
        forbidden_roots=[str(checkout)],
    )
    assert len(findings) == 1
    assert "inside a repository root" in findings[0]["reason"]


def test_leakage_flags_an_origin_outside_site_packages(tmp_path: Path) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    findings = scenario_mod.leakage_findings(
        {"nornyx_agentic_adapters": str(tmp_path / "elsewhere" / "m.py")},
        site_packages=str(site),
        forbidden_roots=[],
    )
    assert findings and "outside site-packages" in findings[0]["reason"]


# ---------------------------------------------------------------------------
# Envelope and process truth
# ---------------------------------------------------------------------------


def test_passing_envelope_yields_the_record() -> None:
    assert runner_mod.raise_for_envelope({"status": "pass", "record": {"a": 1}}) == {"a": 1}


def test_failing_envelope_is_raised_as_its_own_class() -> None:
    with pytest.raises(PilotError) as caught:
        runner_mod.raise_for_envelope(
            {
                "status": "fail",
                "failure_class": "GOVERNANCE_EXPECTATION_UNMET",
                "detail": "fail-closed did not hold",
                "evidence": {"variants": {}},
            }
        )
    assert caught.value.failure_class is PilotFailure.GOVERNANCE_EXPECTATION_UNMET
    assert caught.value.attributable_to_distribution is True


def test_success_without_a_record_is_a_failure() -> None:
    with pytest.raises(PilotError) as caught:
        runner_mod.raise_for_envelope({"status": "pass"})
    assert caught.value.failure_class is PilotFailure.SCENARIO_EXECUTION_FAILED


def test_unknown_failure_class_does_not_pass_silently() -> None:
    with pytest.raises(PilotError) as caught:
        runner_mod.raise_for_envelope({"status": "fail", "failure_class": "NEW_THING"})
    assert caught.value.failure_class is PilotFailure.SCENARIO_EXECUTION_FAILED


def test_envelope_is_found_even_when_framework_output_shares_the_line() -> None:
    """CrewAI writes rich console output without always ending it in a newline.

    The sentinel therefore has to be found mid-line, not only at line start —
    this is a regression test for a real failure seen during development.
    """
    noisy = f"╰── crew output {runner_mod.RESULT_SENTINEL} " '{"status": "pass"}'
    assert runner_mod.parse_envelope(noisy)["status"] == "pass"


def test_missing_envelope_is_reported_rather_than_read_as_success() -> None:
    with pytest.raises(PilotError) as caught:
        runner_mod.parse_envelope("Traceback...\n")
    assert caught.value.failure_class is PilotFailure.SCENARIO_EXECUTION_FAILED


def test_envelope_file_is_preferred_over_stdout(tmp_path: Path) -> None:
    path = tmp_path / "envelope.json"
    path.write_text(json.dumps({"status": "pass", "record": {"from": "file"}}), encoding="utf-8")
    envelope = runner_mod._read_envelope(path, stdout="garbage", stderr="", returncode=0)
    assert envelope["record"] == {"from": "file"}


def test_absent_envelope_file_falls_back_to_stdout(tmp_path: Path) -> None:
    stdout = f"{runner_mod.RESULT_SENTINEL} " '{"status": "pass", "record": {"from": "stdout"}}'
    envelope = runner_mod._read_envelope(
        tmp_path / "nope.json", stdout=stdout, stderr="", returncode=0
    )
    assert envelope["record"] == {"from": "stdout"}


def test_pass_envelope_with_nonzero_exit_is_rejected() -> None:
    with pytest.raises(PilotError) as caught:
        runner_mod.check_process_consistency({"status": "pass"}, returncode=2)
    assert caught.value.failure_class is PilotFailure.SCENARIO_EXECUTION_FAILED


def test_fail_envelope_with_zero_exit_is_rejected() -> None:
    with pytest.raises(PilotError) as caught:
        runner_mod.check_process_consistency({"status": "fail"}, returncode=0)
    assert caught.value.failure_class is PilotFailure.SCENARIO_EXECUTION_FAILED


# ---------------------------------------------------------------------------
# Caller input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["", "  ", ">=0.3.0", "latest", "v0.3.0"])
def test_inexact_versions_are_caller_errors(bad: str) -> None:
    with pytest.raises(PilotError) as caught:
        runner_mod.run_pilot(adapter_version=bad)
    assert caught.value.failure_class is PilotFailure.PILOT_INPUT_INVALID
    assert caught.value.attributable_to_distribution is False


def test_nonpositive_timeout_is_a_caller_error() -> None:
    with pytest.raises(PilotError) as caught:
        runner_mod.run_pilot(timeout=0)
    assert caught.value.failure_class is PilotFailure.PILOT_INPUT_INVALID


def test_venv_failure_is_never_blamed_on_the_packages(monkeypatch) -> None:
    monkeypatch.setattr(
        runner_mod.venv.EnvBuilder, "create",
        lambda self, root: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(PilotError) as caught:
        runner_mod.run_pilot(timeout=30)
    assert caught.value.failure_class is PilotFailure.PILOT_INPUT_INVALID
    assert caught.value.attributable_to_distribution is False


def test_install_failure_is_classified(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(runner_mod, "_create_environment", lambda root: tmp_path / "py")
    monkeypatch.setattr(
        runner_mod, "_run",
        lambda *a, **k: runner_mod._Completed(1, "", "No matching distribution"),
    )
    with pytest.raises(PilotError) as caught:
        runner_mod.run_pilot(timeout=30)
    assert caught.value.failure_class is PilotFailure.REGISTRY_INSTALL_FAILED


def test_install_timeout_is_classified(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(runner_mod, "_create_environment", lambda root: tmp_path / "py")
    monkeypatch.setattr(
        runner_mod, "_run",
        lambda *a, **k: runner_mod._Completed(-1, "", "", timed_out=True),
    )
    with pytest.raises(PilotError) as caught:
        runner_mod.run_pilot(timeout=30)
    assert caught.value.failure_class is PilotFailure.REGISTRY_INSTALL_FAILED
    assert "timed out" in caught.value.detail


# ---------------------------------------------------------------------------
# Structural invariants and the no-clone claim
# ---------------------------------------------------------------------------


_FORBIDDEN_ROOTS = {"examples", "tests", "scripts", "integrations", "adapters"}


def test_pilot_package_has_no_repository_imports() -> None:
    """The whole package must be copyable and runnable outside the repository."""
    offenders: list[str] = []
    for module in sorted(PILOT_DIR.glob("*.py")):
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


def test_scenario_imports_nothing_from_its_own_package() -> None:
    """The scenario is copied alone into the clean environment and run there."""
    tree = ast.parse((PILOT_DIR / "scenario.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"relative import at line {node.lineno}"
            assert not (node.module or "").startswith(
                "external_adoption_pilot"
            ), f"package import at line {node.lineno}"


def test_scenario_imports_frameworks_lazily() -> None:
    """Importing the scenario must not require crewai or the adapter.

    The pure helpers above are tested here, in an environment where neither is
    installed. A module-level framework import would break that.
    """
    assert scenario_mod.RESULT_SENTINEL == "PILOT_RESULT"
    assert scenario_mod.READ_CAPABILITY == "read_governed_context"


def test_checkout_detection_is_marker_based(tmp_path: Path) -> None:
    """Copied out of the repository, the pilot must claim no repository roots."""
    staging = tmp_path / "standalone"
    shutil.copytree(
        PILOT_DIR, staging / "external_adoption_pilot",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    code = textwrap.dedent(
        """
        import json
        from external_adoption_pilot.runner import repository_roots
        print(json.dumps(repository_roots()))
        """
    )
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=staging, env=env,
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) == []


def test_checkout_detection_finds_this_repository() -> None:
    assert str(REPO_ROOT) in runner_mod.repository_roots()


def test_core_version_is_recorded_not_pinned() -> None:
    """Pinning core exactly would break this pilot the day nornyx 1.12.0 ships."""
    source = (PILOT_DIR / "runner.py").read_text(encoding="utf-8")
    assert "--expect-core" not in source
    scenario_source = (PILOT_DIR / "scenario.py").read_text(encoding="utf-8")
    assert 'parser.add_argument("--expect-core", default=None)' in scenario_source


def test_readme_documents_every_failure_class() -> None:
    readme = (PILOT_DIR / "README.md").read_text(encoding="utf-8")
    for member in PilotFailure:
        assert member.value in readme, f"{member.value} is undocumented"


def test_readme_explains_why_the_benchmark_is_not_reused() -> None:
    """Acceptance requires reuse or a documented reason. This is the reason."""
    readme = (PILOT_DIR / "README.md").read_text(encoding="utf-8")
    assert "crewai_governance_benchmark" in readme
    assert "not shipped in any published distribution" in readme


def test_readme_states_the_constant_versus_observed_distinction() -> None:
    readme = (PILOT_DIR / "README.md").read_text(encoding="utf-8")
    assert "external_model_service_called" in readme
    assert "scripted_in_process_model_called" in readme
    assert "structural constant" in readme
    assert "observed" in readme
