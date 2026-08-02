"""ADR-0043 M2-E: runner, CLI, determinism, and report-writing behavior.

Uses the two suites that need no framework extra, so this module runs in the
default adapter-foundation matrix.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from nornyx_agentic_adapters.conformance import (
    CaseOutcome,
    RunOutcome,
    SuiteOutcome,
    available_suites,
    run_conformance,
    serialize,
    validate_report,
    write_report,
)
from nornyx_agentic_adapters.conformance.cli import (
    EXIT_NONCONFORMANT,
    EXIT_OK,
    EXIT_USAGE,
    main,
)

BASE_SUITES = ["distribution", "enforcement_boundary"]


@pytest.fixture(scope="module")
def base_report():
    return run_conformance(frameworks=BASE_SUITES)


def test_available_suites_are_deterministic_and_complete() -> None:
    assert available_suites() == ("distribution", "enforcement_boundary", "crewai", "langgraph")
    assert available_suites() == available_suites()


def test_base_suites_conform_and_the_report_validates(base_report) -> None:
    assert base_report.outcome is RunOutcome.PASS, [c.detail for c in base_report.failures()]
    assert validate_report(base_report.as_dict()) == ()
    assert {s.suite_id for s in base_report.suites} == set(BASE_SUITES)


def test_report_is_byte_identical_across_repeated_runs() -> None:
    first = serialize(run_conformance(frameworks=BASE_SUITES))
    second = serialize(run_conformance(frameworks=BASE_SUITES))
    assert first == second


def test_report_is_byte_identical_across_processes_and_hash_seeds(tmp_path: Path) -> None:
    """Set and dict iteration order must not leak into the bytes."""
    code = (
        "from nornyx_agentic_adapters.conformance import run_conformance, serialize\n"
        f"import sys; sys.stdout.write(serialize(run_conformance(frameworks={BASE_SUITES!r})))\n"
    )
    outputs = []
    for seed in ("0", "1"):
        completed = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            env={**_child_env(), "PYTHONHASHSEED": seed},
            timeout=300,
        )
        assert completed.returncode == 0, completed.stderr
        outputs.append(completed.stdout)
    assert outputs[0] == outputs[1]


def _child_env() -> dict[str, str]:
    import os

    env = dict(os.environ)
    env.pop("PYTHONHASHSEED", None)
    return env


def test_report_contains_no_environment_specific_noise(base_report) -> None:
    text = serialize(base_report)
    import re

    assert not re.search(r"[A-Za-z]:\\\\", text), "a Windows absolute path leaked"
    assert not re.search(r'"/(home|Users|tmp)', text), "a POSIX absolute path leaked"
    assert "Traceback (most recent call last)" not in text
    assert str(Path.cwd()) not in text


def test_report_safety_block_is_the_kits_own_not_the_validators(base_report) -> None:
    """The kit executes governed actions; a copied validator safety block would
    assert ``tools_executed: false`` immediately after executing a tool."""
    safety = base_report.as_dict()["safety"]
    assert safety["adapter_actions_executed"] is True
    # Observed, not declared: the guard names the suites it covered and reports
    # a real count. It is deliberately NOT restated as a "network was used"
    # flag — a blocked attempt means the network was not reached, so such a
    # flag would invert the meaning.
    assert safety["guarded_suites"] == ["enforcement_boundary"]
    assert safety["blocked_outbound_attempts"] == 0
    assert "network_used" not in safety
    assert safety["models_called"] is False
    assert "tools_executed" not in safety


def test_unknown_suite_and_unknown_required_framework_are_rejected() -> None:
    with pytest.raises(ValueError, match="unknown suite"):
        run_conformance(frameworks=["not_a_suite"])
    with pytest.raises(ValueError, match="unknown required framework"):
        run_conformance(frameworks=BASE_SUITES, require=["not_a_framework"])


def test_requiring_a_framework_that_was_not_selected_is_rejected() -> None:
    """Otherwise `require` is a silent no-op under that flag combination, and
    a CI edit adding --suite would disarm the gate without saying so."""
    with pytest.raises(ValueError, match="not selected to run"):
        run_conformance(frameworks=["enforcement_boundary"], require=["crewai"])


def test_an_unmatched_case_id_is_rejected_rather_than_yielding_an_empty_pass() -> None:
    with pytest.raises(ValueError, match="no conformance case matches"):
        run_conformance(frameworks=["enforcement_boundary"], case_ids=["no.such.case"])


def test_duplicate_case_ids_are_rejected() -> None:
    """A duplicate case id would let one result stand in for another."""
    import dataclasses

    from nornyx_agentic_adapters.conformance import runner

    suite = run_conformance(frameworks=["enforcement_boundary"]).suites[0]
    first = suite.cases[0]
    with pytest.raises(ValueError, match="duplicate conformance case id"):
        runner._validate_case_ids_unique([dataclasses.replace(suite, cases=(first, first))])
    runner._validate_case_ids_unique([suite])


def test_case_selection_narrows_the_run() -> None:
    report = run_conformance(
        frameworks=["enforcement_boundary"], case_ids=["neutral.enforce.allow"]
    )
    assert [c.case_id for s in report.suites for c in s.cases] == ["neutral.enforce.allow"]


def test_a_run_that_produced_no_cases_is_not_a_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """Selecting a framework whose extra is absent verifies nothing, so it
    cannot report `pass` with zero evidence behind it."""
    from nornyx_agentic_adapters.conformance import runner

    monkeypatch.setattr(
        runner,
        "_load_framework_suite",
        lambda framework: (_ for _ in ()).throw(ImportError("absent")),
    )
    report = runner.run_conformance(frameworks=["crewai"])
    assert report.cases() == ()
    assert report.outcome is RunOutcome.FAIL


def test_requiring_an_absent_framework_fails_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    from nornyx_agentic_adapters.conformance import runner

    def refuse(framework: str):
        raise ImportError(f"{framework} is not installed")

    monkeypatch.setattr(runner, "_load_framework_suite", refuse)
    report = runner.run_conformance(frameworks=["crewai"], require=["crewai"])
    assert report.outcome is RunOutcome.FAIL
    assert runner.missing_required(report, ["crewai"]) == ("crewai",)

    # An unavailable suite is still distinguishable from a passing one: it
    # carries a reason and no cases, so a reader cannot mistake absence for
    # evidence even when the run was not required to have it.
    permissive = runner.run_conformance(frameworks=["crewai"])
    unavailable = permissive.suites[0]
    assert unavailable.outcome is SuiteOutcome.UNAVAILABLE
    assert unavailable.unavailable_reason
    assert unavailable.cases == ()


# ------------------------------------------------------------------ report writing
def test_write_report_is_atomic_and_round_trips(tmp_path: Path, base_report) -> None:
    destination = tmp_path / "nested" / "report.json"
    write_report(base_report, destination)
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert validate_report(payload) == ()
    assert destination.read_text(encoding="utf-8") == serialize(base_report)
    assert list(destination.parent.glob(".conformance-*")) == [], "a temp file was left behind"


def test_write_report_refuses_a_directory(tmp_path: Path, base_report) -> None:
    with pytest.raises(IsADirectoryError):
        write_report(base_report, tmp_path)


def test_a_failed_serialization_leaves_no_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A consumer must never read a truncated report as authoritative."""
    from nornyx_agentic_adapters.conformance import report as report_module

    destination = tmp_path / "report.json"
    monkeypatch.setattr(
        report_module, "serialize", lambda _payload: (_ for _ in ()).throw(TypeError("boom"))
    )
    with pytest.raises(TypeError):
        report_module.write_report({"anything": True}, destination)
    assert not destination.exists()
    assert list(tmp_path.glob(".conformance-*")) == []


# ------------------------------------------------------------------ CLI behavior
def test_cli_exits_zero_and_emits_a_validating_report(tmp_path: Path, capsys) -> None:
    destination = tmp_path / "cli.json"
    code = main(["--suite", "enforcement_boundary", "--json", str(destination)])
    assert code == EXIT_OK
    assert validate_report(json.loads(destination.read_text(encoding="utf-8"))) == ()


def test_cli_writes_json_to_stdout_by_default(capsys) -> None:
    assert main(["--suite", "enforcement_boundary"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "nornyx.agentic_runtime_conformance.v1"


def test_cli_summary_states_the_tier_2_boundary(capsys) -> None:
    assert main(["--suite", "enforcement_boundary", "--summary"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "tier_2_cooperative" in out
    assert "declared wrapped surfaces only" in out
    assert "does not authenticate agents or approvers" in out
    assert "prevent bypass" in out


def test_cli_returns_usage_exit_for_an_unknown_suite(capsys) -> None:
    assert main(["--suite", "not_a_suite"]) == EXIT_USAGE
    assert "unknown suite" in capsys.readouterr().err


def test_cli_returns_nonconformant_when_a_required_framework_is_absent(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from nornyx_agentic_adapters.conformance import runner

    monkeypatch.setattr(
        runner,
        "_load_framework_suite",
        lambda framework: (_ for _ in ()).throw(ImportError("absent")),
    )
    assert main(["--suite", "crewai", "--require", "crewai"]) == EXIT_NONCONFORMANT
    assert "unavailable" in capsys.readouterr().err


def test_cli_internal_error_never_exits_zero_and_writes_no_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from nornyx_agentic_adapters.conformance import cli as cli_module

    destination = tmp_path / "never.json"
    monkeypatch.setattr(
        cli_module,
        "run_conformance",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("internal")),
    )
    assert main(["--json", str(destination)]) == EXIT_USAGE
    assert "internal error" in capsys.readouterr().err
    assert not destination.exists()


def test_cli_reports_a_nonconforming_case_as_exit_one(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """The gate must actually fail when a case fails."""
    from nornyx_agentic_adapters.conformance import cli as cli_module
    from nornyx_agentic_adapters.conformance import runner

    real = runner.run_conformance

    def failing(**kwargs):
        report = real(**kwargs)
        broken = report.suites[0].cases[0]
        import dataclasses

        mutated = dataclasses.replace(broken, outcome=CaseOutcome.FAIL, detail="seeded failure")
        suite = dataclasses.replace(
            report.suites[0], outcome=SuiteOutcome.FAIL, cases=(mutated,)
        )
        return dataclasses.replace(report, suites=(suite,), outcome=RunOutcome.FAIL)

    monkeypatch.setattr(cli_module, "run_conformance", failing)
    assert main(["--suite", "enforcement_boundary"]) == EXIT_NONCONFORMANT
    assert "seeded failure" in capsys.readouterr().err


def test_module_entry_point_runs_outside_the_package(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "nornyx_agentic_adapters.conformance",
            "--suite",
            "enforcement_boundary",
            "--summary",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=300,
    )
    assert completed.returncode == EXIT_OK, completed.stderr
    assert "tier_2_cooperative" in completed.stdout
