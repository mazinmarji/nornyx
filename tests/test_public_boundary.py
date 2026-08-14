from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-public-boundary.py"


def _load_public_boundary_module():
    spec = importlib.util.spec_from_file_location("check_public_boundary", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assemble(*parts: str) -> str:
    """Build a flagged fixture at runtime.

    Flagged phrases are assembled from fragments so this tracked file never
    contains them as contiguous text; repository-wide text searches stay clean
    even though these tests exercise the strategy-shape rules.
    """
    return "".join(parts)


def _assert_no_product_compound_echo(output: str) -> None:
    lowered = output.lower()
    for sep in (" ", "-", "_", ".", ":", ""):
        assert _assemble("nornyx", sep, "enterprise") not in lowered


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


def test_nested_claude_directory_is_scanned(tmp_path: Path, capsys) -> None:
    nested = tmp_path / "examples" / "pkg" / ".claude"
    nested.mkdir(parents=True)
    (nested / "mcp.json").write_text(
        '{"note": "PRIVATE_DOWNSTREAM_PLATFORM"}\n', encoding="utf-8"
    )
    module = _load_public_boundary_module()

    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 1
    assert "examples/pkg/.claude/mcp.json:1" in output


def test_marker_exempt_file_still_scanned_for_other_layers(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_public_boundary_module()
    local_marker = "LocalPrivateVendorMark"
    (tmp_path / ".private-boundary-terms.txt").write_text(local_marker, encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    exempt = tests_dir / "test_public_boundary.py"
    exempt.write_text(
        "\n".join(
            [
                'MARKER = "PRIVATE_DOWNSTREAM_PLATFORM"',
                "leak = '" + _assemble("Nornyx", " ", "Enterprise") + "'",
                "vendor = '" + local_marker + "'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 1
    assert "tests/test_public_boundary.py:2" in output
    assert "rule=nonpublic-product-edition" in output
    canonical_fp = module._fingerprint(module._canonical_term_text(local_marker))
    assert f"term_fingerprint={canonical_fp}" in output
    marker_fp = module._fingerprint("PRIVATE_DOWNSTREAM_PLATFORM")
    assert marker_fp not in output
    assert local_marker not in output


def test_sensitive_path_never_leaves_finding_objects(tmp_path: Path) -> None:
    module = _load_public_boundary_module()
    local_marker = "LocalPrivateVendorMark"
    (tmp_path / ".private-boundary-terms.txt").write_text(local_marker, encoding="utf-8")
    parent = tmp_path / (local_marker + "-private")
    parent.mkdir()
    target = parent / (local_marker + "-notes.md")
    target.write_text("The body mentions " + local_marker + " once.\n", encoding="utf-8")

    findings = module.check_public_boundary(tmp_path)
    serialized = (repr(findings) + json.dumps(findings)).casefold()

    assert findings
    assert {finding["scope"] for finding in findings} == {"path", "content"}
    assert local_marker.casefold() not in serialized
    assert "notes.md" not in serialized
    expected_rel = local_marker + "-private/" + local_marker + "-notes.md"
    for finding in findings:
        assert finding["path"] == module.REDACTED_PATH
        assert finding["path_fingerprint"] == module._fingerprint(expected_rel)


def test_clean_path_findings_keep_normal_location(tmp_path: Path) -> None:
    module = _load_public_boundary_module()
    marker = "PRIVATE_DOWNSTREAM_PLATFORM"
    (tmp_path / "README.md").write_text("intro\n" + marker + "\n", encoding="utf-8")

    findings = module.check_public_boundary(tmp_path)

    assert findings == [
        {
            "path": "README.md",
            "line": 2,
            "scope": "content",
            "term_fingerprint": module._fingerprint(marker),
        }
    ]


def test_local_term_canonical_matching_variants(tmp_path: Path, capsys) -> None:
    module = _load_public_boundary_module()
    term = "LocalPrivateVendorMark"
    # BOM-prefixed local term file must still load the term.
    (tmp_path / ".private-boundary-terms.txt").write_bytes(
        b"\xef\xbb\xbf" + term.encode("utf-8") + b"\n"
    )
    canonical_fp = module._fingerprint(module._canonical_term_text(term))
    cases = [
        "lower-case body " + term.lower(),
        "upper-case body " + term.upper(),
        "zero-width body " + term[:5] + "\u200b" + term[5:],
        "joiner body " + term[:5] + "\u200d" + term[5:],
    ]

    for index, text in enumerate(cases):
        target = tmp_path / f"doc_{index}.md"
        target.write_text(text + "\n", encoding="utf-8")

        result = module.main(["--repo", str(tmp_path)])
        output = capsys.readouterr().out

        assert result == 1, text
        assert f"term_fingerprint={canonical_fp}" in output, text
        assert term.casefold() not in output.casefold()
        target.unlink()

    (tmp_path / "ok.md").write_text("Ordinary MixedCase Public Text.\n", encoding="utf-8")
    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out
    assert result == 0
    assert "public boundary check passed" in output


def test_local_term_mixed_case_path_components_detected(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_public_boundary_module()
    term = "LocalPrivateVendorMark"
    (tmp_path / ".private-boundary-terms.txt").write_text(term, encoding="utf-8")

    upper_name = term.upper() + "-notes.md"
    (tmp_path / upper_name).write_text("clean body\n", encoding="utf-8")
    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out
    assert result == 1
    assert "line=0 scope=path" in output
    assert f"path_fingerprint={module._fingerprint(upper_name)}" in output
    assert term.casefold() not in output.casefold()
    (tmp_path / upper_name).unlink()

    parent = tmp_path / ("vendor-" + term.lower())
    parent.mkdir()
    (parent / "readme.md").write_text("clean body\n", encoding="utf-8")
    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out
    assert result == 1
    assert "line=0 scope=path" in output
    expected_rel = "vendor-" + term.lower() + "/readme.md"
    assert f"path_fingerprint={module._fingerprint(expected_rel)}" in output
    assert term.casefold() not in output.casefold()


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


def test_strategy_rules_flag_commercial_split_variants(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_public_boundary_module()
    cases = [
        (
            "The " + _assemble("commercial", "/", "open-source")
            + " boundary becomes clearer.",
            "rule=commercial-oss-split",
        ),
        (
            "An " + _assemble("open source", " versus ", "commercial") + " split.",
            "rule=commercial-oss-split",
        ),
        (
            "documentation states the draft status and "
            + _assemble("commercial", " ", "boundary")
            + ";",
            "rule=commercial-scope-phrase",
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


def test_strategy_rule_flags_enterprise_counterpart_contrast(
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
        assert "rule=enterprise-counterpart-contrast" in output, text
        target.unlink()


def test_strategy_rule_separator_matrix(tmp_path: Path, capsys) -> None:
    module = _load_public_boundary_module()
    cases = [
        (_assemble("Nornyx", ": ", "Enterprise"), "rule=nonpublic-product-edition"),
        (_assemble("nornyx", "\\", "enterprise"), "rule=nonpublic-product-edition"),
        (
            _assemble("Nornyx", "\u200b", "Enterprise"),
            "rule=nonpublic-product-edition",
        ),
        (_assemble("enterprise", "-", "edition"), "rule=product-edition-shape"),
        (_assemble("enterprise", "_", "edition"), "rule=product-edition-shape"),
        (_assemble("enterprise", ".", "edition"), "rule=product-edition-shape"),
        (_assemble("enterprise", "/", "edition"), "rule=product-edition-shape"),
        (_assemble("commercial", ".", "tier"), "rule=product-edition-shape"),
        (_assemble("commercial", "_", "boundary"), "rule=commercial-scope-phrase"),
        (_assemble("commercial", ".", "open.source"), "rule=commercial-oss-split"),
        (_assemble("commercial", "_", "open_source"), "rule=commercial-oss-split"),
        (
            _assemble("public.core", " versus ", "enterprise"),
            "rule=enterprise-counterpart-contrast",
        ),
        (
            _assemble("public_core", " vs ", "enterprise"),
            "rule=enterprise-counterpart-contrast",
        ),
        (
            _assemble("public/core", " versus ", "enterprise"),
            "rule=enterprise-counterpart-contrast",
        ),
        (
            _assemble("public", "\u200b", "core", " versus ", "enterprise"),
            "rule=enterprise-counterpart-contrast",
        ),
    ]

    for index, (text, expected_rule) in enumerate(cases):
        target = tmp_path / f"doc_{index}.md"
        target.write_text("The " + text + " marker.\n", encoding="utf-8")

        result = module.main(["--repo", str(tmp_path)])
        output = capsys.readouterr().out

        assert result == 1, text
        assert expected_rule in output, text
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


def test_strategy_rule_catches_three_line_contrast(tmp_path: Path, capsys) -> None:
    module = _load_public_boundary_module()
    wrapped = _assemble("public/core", "\n", "versus", "\n", "enterprise boundary") + "\n"
    (tmp_path / "wrapped.md").write_text(wrapped, encoding="utf-8")

    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 1
    assert "wrapped.md:1: rule=enterprise-counterpart-contrast" in output
    assert output.count("rule=enterprise-counterpart-contrast") == 1


def test_strategy_rule_catches_three_line_split(tmp_path: Path, capsys) -> None:
    module = _load_public_boundary_module()
    wrapped = _assemble("commercial", "\n", "versus", "\n", "open source lines") + "\n"
    (tmp_path / "wrapped.md").write_text(wrapped, encoding="utf-8")

    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 1
    assert "wrapped.md:1: rule=commercial-oss-split" in output
    assert output.count("rule=commercial-oss-split") == 1


def test_paragraph_break_is_not_a_soft_wrap(tmp_path: Path, capsys) -> None:
    module = _load_public_boundary_module()
    text = _assemble("Nornyx", "\n\n", "Enterprise") + " teams review it.\n"
    (tmp_path / "doc.md").write_text(text, encoding="utf-8")

    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 0
    assert "public boundary check passed" in output


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


def test_strategy_shaped_parent_component_detected(tmp_path: Path, capsys) -> None:
    module = _load_public_boundary_module()
    parent = tmp_path / _assemble("nornyx", "-", "enterprise")
    parent.mkdir()
    (parent / "readme.md").write_text("Nothing private in the content.\n", encoding="utf-8")

    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 1
    assert "rule=nonpublic-product-edition" in output
    assert "line=0 scope=path" in output
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
            "The enterprise architecture team reviewed the design.",
            "An enterprise customer asked for evidence exports.",
            "Commercial software may adopt the public contract.",
            "The open-source standard is versioned upstream.",
            "Generic hosted deployment guidance stays vendor-neutral.",
            "Teams adopt Nornyx. Enterprise architects evaluate it separately.",
            "plain lower-case enterprise usage passes.",
            "Nornyx is a vendor-neutral governance contract language for AI",
            "software delivery.",
        ]
    )
    (tmp_path / "public.md").write_text(text + "\n", encoding="utf-8")

    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 0
    assert "public boundary check passed" in output
