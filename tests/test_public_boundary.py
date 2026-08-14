from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-public-boundary.py"


def _load_public_boundary_module():
    spec = importlib.util.spec_from_file_location("check_public_boundary", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_boundary_script_passes_repository_tree() -> None:
    module = _load_public_boundary_module()

    assert module.check_public_boundary(ROOT) == []


def test_public_boundary_script_reports_neutral_marker_without_echoing_value(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_public_boundary_module()
    marker = "PRIVATE_DOWNSTREAM_PLATFORM"
    (tmp_path / "README.md").write_text(marker, encoding="utf-8")

    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 1
    assert "term_fingerprint=" in output
    assert "README.md:1" in output
    assert marker not in output


def test_public_boundary_script_uses_ignored_local_terms_without_echoing_values(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_public_boundary_module()
    local_marker = "LOCAL_PRIVATE_BOUNDARY_MARKER"
    (tmp_path / ".private-boundary-terms.txt").write_text(local_marker, encoding="utf-8")
    (tmp_path / "notes.md").write_text(local_marker, encoding="utf-8")

    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 1
    assert "term_fingerprint=" in output
    assert "notes.md:1" in output
    assert ".private-boundary-terms.txt" not in output
    assert local_marker not in output


def test_public_boundary_script_ignores_local_term_file_itself(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_public_boundary_module()
    local_marker = "LOCAL_PRIVATE_BOUNDARY_MARKER"
    (tmp_path / ".private-boundary-terms.txt").write_text(local_marker, encoding="utf-8")
    (tmp_path / "README.md").write_text("# Clean public tree\n", encoding="utf-8")

    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 0
    assert "public boundary check passed" in output
    assert local_marker not in output


def test_public_boundary_script_ignores_claude_worktrees(tmp_path: Path) -> None:
    module = _load_public_boundary_module()
    nested = tmp_path / ".claude" / "worktrees" / "review"
    nested.mkdir(parents=True)
    (nested / "notes.md").write_text("PRIVATE_DOWNSTREAM_PLATFORM", encoding="utf-8")

    assert module.check_public_boundary(tmp_path) == []


def _assemble(*parts: str) -> str:
    """Build a flagged fixture at runtime.

    Flagged phrases are assembled from fragments so this tracked file never
    contains them as contiguous text; repository-wide text searches stay clean
    even though these tests exercise the strategy-shape rules.
    """
    return "".join(parts)


def _assert_no_product_compound_echo(output: str) -> None:
    lowered = output.lower()
    for sep in (" ", "-", "_", ".", ""):
        assert _assemble("nornyx", sep, "enterprise") not in lowered


def test_strategy_rules_flag_nonpublic_product_edition_variants(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_public_boundary_module()
    variants = [
        _assemble("Nornyx", " ", "Enterprise")
        + " or any third-party service can later operate the same semantics.",
        "See " + _assemble("nornyx", "-", "enterprise") + "/README for details.",
        "import " + _assemble("nornyx", "_", "enterprise") + ".bridge",
        "The " + _assemble("Nornyx", "", "Enterprise") + " deployment topology.",
        "the " + _assemble("NORNYX", ".", "ENTERPRISES") + " module",
    ]

    for index, text in enumerate(variants):
        target = tmp_path / f"doc_{index}.md"
        target.write_text(text + "\n", encoding="utf-8")

        result = module.main(["--repo", str(tmp_path)])
        output = capsys.readouterr().out

        assert result == 1, text
        assert "rule=nonpublic-product-edition" in output, text
        assert "hint=" in output
        _assert_no_product_compound_echo(output)
        target.unlink()


def test_strategy_rules_flag_commercial_boundary_variants(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_public_boundary_module()
    cases = [
        (
            "The " + _assemble("commercial", "/", "open-source")
            + " boundary becomes clearer.",
            "rule=commercial-open-source-boundary",
        ),
        (
            "An " + _assemble("open source", " versus ", "commercial") + " split.",
            "rule=commercial-open-source-boundary",
        ),
        (
            "documentation states the draft status and "
            + _assemble("commercial", " ", "boundary")
            + ";",
            "rule=commercial-boundary",
        ),
        (
            "Available in the " + _assemble("enterprise", " ", "edition") + " only.",
            "rule=product-edition-shape",
        ),
        (
            "Contact sales about the " + _assemble("commercial", " ", "tier") + ".",
            "rule=product-edition-shape",
        ),
    ]

    for index, (text, expected_rule) in enumerate(cases):
        target = tmp_path / f"doc_{index}.md"
        target.write_text(text + "\n", encoding="utf-8")

        result = module.main(["--repo", str(tmp_path)])
        output = capsys.readouterr().out

        assert result == 1, text
        assert expected_rule in output, text
        assert text not in output
        target.unlink()


def test_strategy_rule_flags_public_versus_enterprise_contrast(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_public_boundary_module()
    cases = [
        "## " + _assemble("Public/Core", " versus ", "Enterprise") + " boundary",
        "The " + _assemble("core", " vs ", "enterprise") + " split is documented.",
        "An " + _assemble("Enterprise", " versus ", "public core") + " comparison.",
        "The " + _assemble("open-source", " vs. ", "enterprise") + " divide.",
    ]

    for index, text in enumerate(cases):
        target = tmp_path / f"doc_{index}.md"
        target.write_text(text + "\n", encoding="utf-8")

        result = module.main(["--repo", str(tmp_path)])
        output = capsys.readouterr().out

        assert result == 1, text
        assert "rule=public-vs-enterprise-split" in output, text
        target.unlink()


def test_strategy_rule_catches_compound_wrapped_across_lines(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_public_boundary_module()
    wrapped = (
        "Consequence: " + _assemble("Nornyx", "\n", "Enterprise")
        + " can later operate the same public semantics.\n"
    )
    (tmp_path / "wrapped.md").write_text(wrapped, encoding="utf-8")

    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 1
    assert "wrapped.md:1: rule=nonpublic-product-edition" in output
    _assert_no_product_compound_echo(output)


def test_strategy_rule_catches_flagged_file_path(tmp_path: Path, capsys) -> None:
    module = _load_public_boundary_module()
    name = _assemble("nornyx", "-", "enterprise") + "-notes.md"
    (tmp_path / name).write_text("Nothing private in the content.\n", encoding="utf-8")

    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 1
    assert "rule=nonpublic-product-edition" in output
    assert "line=0 scope=path" in output
    assert f"path_fingerprint={module._fingerprint(name)}" in output
    assert name not in output
    _assert_no_product_compound_echo(output)


def test_private_local_term_in_filename_is_detected_and_redacted(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_public_boundary_module()
    local_marker = "LOCAL_PRIVATE_BOUNDARY_MARKER"
    (tmp_path / ".private-boundary-terms.txt").write_text(local_marker, encoding="utf-8")
    sensitive_name = local_marker + "-notes.md"
    (tmp_path / sensitive_name).write_text("# Clean public content\n", encoding="utf-8")

    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 1
    assert local_marker not in output
    assert sensitive_name not in output
    assert "line=0 scope=path" in output
    assert f"path_fingerprint={module._fingerprint(sensitive_name)}" in output
    assert "term_fingerprint=" in output


def test_content_finding_in_sensitively_named_file_redacts_path(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_public_boundary_module()
    local_marker = "LOCAL_PRIVATE_BOUNDARY_MARKER"
    (tmp_path / ".private-boundary-terms.txt").write_text(local_marker, encoding="utf-8")
    sensitive_name = local_marker + "-notes.md"
    (tmp_path / sensitive_name).write_text(
        "The body mentions " + local_marker + " once.\n", encoding="utf-8"
    )

    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 1
    assert local_marker not in output
    assert sensitive_name not in output
    assert "line=1 scope=content" in output
    assert f"path_fingerprint={module._fingerprint(sensitive_name)}" in output


def test_legitimate_public_language_passes(tmp_path: Path, capsys) -> None:
    module = _load_public_boundary_module()
    text = "\n".join(
        [
            "# Interoperability",
            "A PEP can call a separately operated PDP using AuthZEN 1.0.",
            "Any organization, adapter, gateway, or commercial product may use",
            "the same public contract.",
            "Public Nornyx MUST NOT add enterprise policy distribution/caching.",
            "GOAL-100 keeps regulated/enterprise promotion locked.",
            "Standards Mapping and Enterprise Assurance stays vendor-neutral.",
            'BeyondCorp: "A New Approach to Enterprise Security."',
            "Commercial and open-source implementations interoperate here.",
            "## Public Core scope boundary",
            "Large-scale hosted operation of those semantics is not",
            "implemented here.",
            "Approval fatigue at enterprise scale is an unsolved problem.",
            "Build versus buy versus platform is a Chapter 37 question.",
            "Nornyx is a vendor-neutral governance contract language for AI",
            "software delivery.",
        ]
    )
    (tmp_path / "public.md").write_text(text + "\n", encoding="utf-8")

    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 0
    assert "public boundary check passed" in output
