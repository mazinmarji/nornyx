"""Tests for the book build (``book/tools/build_book.py``).

The builder is a standalone script rather than an importable package, so it is
loaded the same way ``tests/test_public_boundary.py`` loads the boundary
checker. Tests split into two groups: unit tests driving a synthetic manuscript
in ``tmp_path``, and integration tests that build the real book and pin the
structural facts a silent regression would change.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "book" / "tools" / "build_book.py"
MANUSCRIPT = ROOT / "book" / "manuscript"
DESIGN = ROOT / "book" / "design"


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_book", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # The builder uses `from __future__ import annotations` with @dataclass, and
    # dataclasses resolves the resulting string annotations through
    # sys.modules[cls.__module__]. Registering before exec keeps that lookup from
    # failing on a module loaded outside the normal import system.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def builder():
    return _load_builder()


@pytest.fixture(scope="module")
def built(builder):
    page, stats = builder.build_book()
    return page, stats


# --------------------------------------------------------------------------
# Structure of the real book
# --------------------------------------------------------------------------


def test_book_builds_with_the_expected_shape(built) -> None:
    _, stats = built
    assert stats["chapters"] == 41
    assert stats["appendices"] == 9
    assert stats["parts"] == 8
    assert stats["documents"] == 54  # 41 chapters + 9 appendices + 1 front + 3 back


def test_every_chapter_and_appendix_appears_exactly_once(builder) -> None:
    documents = builder.load_documents(MANUSCRIPT)
    chapters = [d.chapter for d in documents if d.kind == "chapter"]
    appendices = [d.appendix for d in documents if d.kind == "appendix"]
    assert sorted(chapters) == list(range(1, 42))
    assert sorted(appendices) == ["A", "B", "C", "D", "E", "F", "G", "H", "J"]


def test_documents_are_ordered_front_chapters_appendices_back(builder) -> None:
    kinds = [d.kind for d in builder.load_documents(MANUSCRIPT)]
    assert kinds == sorted(kinds, key=["front", "chapter", "appendix", "back"].index)


def test_chapters_run_in_part_order_then_chapter_order(builder) -> None:
    documents = [d for d in builder.load_documents(MANUSCRIPT) if d.kind == "chapter"]
    seen_parts = [d.part for d in documents]
    # Parts appear as contiguous runs, in the canonical order.
    runs = [p for i, p in enumerate(seen_parts) if i == 0 or seen_parts[i - 1] != p]
    assert runs == builder.PART_ORDER
    assert [d.chapter for d in documents] == sorted(d.chapter for d in documents)


def test_drafting_notes_are_not_part_of_the_book(builder, built) -> None:
    """``manuscript/notes/`` is apparatus for writers and must never ship."""
    documents = builder.load_documents(MANUSCRIPT)
    assert all("notes" not in d.path.parts for d in documents)
    page, _ = built
    assert "editorial_pass" not in page


# --------------------------------------------------------------------------
# Bibliography and citations
# --------------------------------------------------------------------------


def test_bibliography_parses_every_declared_entry(builder) -> None:
    """Regression: entries carrying a qualifier once failed to parse.

    ``- **swebok-testing** *(testing framing)* — ...`` did not match the strict
    entry pattern, so the key vanished from the bibliography and then surfaced
    as an "unknown citation key" in five chapters. The loose key-line pattern
    now cross-checks the strict one.
    """
    text = (DESIGN / "05_bibliography.md").read_text(encoding="utf-8")
    declared = builder._BIB_KEY_LINE.findall(text)
    parsed = [key for key, _ in builder.load_bibliography(DESIGN)]
    assert parsed == declared
    assert "swebok-testing" in parsed


def test_bibliography_entries_render_their_markdown(builder, built) -> None:
    """Regression: entries were inserted raw, so 48 of 50 showed literal ``*``.

    The entries are markdown fragments -- they italicise titles, mark revisions
    as code, and end in bare URLs -- so they must go through a renderer rather
    than straight into the page.
    """
    page, _ = built
    rendered = re.findall(r'<li id="ref-[^"]+">.*?</li>', page, re.S)
    assert len(rendered) == 50
    literal_emphasis = [entry for entry in rendered if re.search(r"(?<!\*)\*(?!\*)", entry)]
    assert not literal_emphasis, f"{len(literal_emphasis)} entries still show raw markdown"
    assert sum("<em>" in entry for entry in rendered) >= 45
    assert sum("<a href" in entry for entry in rendered) >= 15


def test_render_inline_drops_the_wrapping_paragraph(builder) -> None:
    assert builder.render_inline("Plain *title* here.") == "Plain <em>title</em> here."


def test_qualifier_is_preserved_in_the_rendered_entry(builder) -> None:
    entries = dict(builder.load_bibliography(DESIGN))
    assert "ref-note" in entries["swebok-testing"]
    assert "testing framing" in entries["swebok-testing"]


def test_every_citation_in_the_book_resolves(built) -> None:
    """Each rendered reference link must point at a bibliography entry that exists."""
    page, _ = built
    targets = set(re.findall(r'<li id="ref-([A-Za-z0-9._-]+)"', page))
    referenced = set(re.findall(r'<a class="cite" href="#ref-([A-Za-z0-9._-]+)"', page))
    assert referenced, "the book rendered no citations at all"
    assert referenced <= targets, f"dangling references: {sorted(referenced - targets)}"


def test_unknown_citation_key_fails_the_build(builder) -> None:
    bibliography = [("known", "A known work.")]
    with pytest.raises(builder.BuildError, match="unknown citation key"):
        builder.link_citations("<p>text [@ghost]</p>", bibliography)


def test_citations_render_as_numbered_links(builder) -> None:
    bibliography = [("alpha", "A."), ("beta", "B.")]
    out, used = builder.link_citations("<p>x [@beta] y [@alpha; @beta]</p>", bibliography)
    assert 'href="#ref-beta"' in out
    assert "[2]" in out and "[1]" in out
    assert used == {"alpha", "beta"}


def test_citations_inside_code_are_left_alone(builder) -> None:
    """A listing containing "[@" is literal text, not a reference."""
    bibliography = [("alpha", "A.")]
    markup = "<p>see [@alpha]</p><pre><code>lookup(&quot;[@alpha]&quot;)</code></pre>"
    out, _ = builder.link_citations(markup, bibliography)
    assert out.count('href="#ref-alpha"') == 1
    assert "<code>lookup(&quot;[@alpha]&quot;)</code>" in out


# --------------------------------------------------------------------------
# Index
# --------------------------------------------------------------------------


def test_index_anchors_are_unique_and_complete(built) -> None:
    page, stats = built
    assert stats["index_entries"] == page.count('<span class="ix" id="ix-')
    ids = [f'id="ix-{n}"' for n in range(1, stats["index_entries"] + 1)]
    assert all(anchor in page for anchor in ids)


def test_index_nests_subentries_under_their_main_entry(builder) -> None:
    entries = [("policy", "ix-1"), ("policy!subjects", "ix-2"), ("zone", "ix-3")]
    out = builder.build_index_html(entries)
    assert "<dt>policy" in out
    assert "<dd>subjects" in out
    assert out.index("<dt>policy") < out.index("<dd>subjects") < out.index("<dt>zone")


def test_index_markers_inside_code_are_not_anchored(builder) -> None:
    markup = '<pre><code><span class="ix" data-ix="x">x</span></code></pre>'
    out, entries, _ = builder.collect_index(markup)
    assert entries == []
    assert out == markup


# --------------------------------------------------------------------------
# Sequence figures
# --------------------------------------------------------------------------


def test_sequence_columns_are_expanded_from_the_delimited_attribute(builder) -> None:
    """CSS cannot split ``data-cols``; the build must produce real elements."""
    markup = '<div class="seq-cols" data-cols="Agent|Adapter|Tool"></div>'
    out = builder.expand_sequences(markup)
    assert 'data-count="3"' in out
    assert out.count('class="seq-col"') == 3
    assert ">Agent<" in out and ">Tool<" in out


def test_sequence_messages_get_grid_placement_and_direction(builder) -> None:
    markup = (
        '<div class="msg" data-from="2" data-to="5" data-kind="call">a</div>'
        '<div class="msg" data-from="4" data-to="1" data-kind="deny">b</div>'
    )
    out = builder.expand_sequences(markup)
    assert "grid-column: 2 / 6;" in out
    assert "grid-column: 1 / 5;" in out
    assert "msg-ltr" in out and "msg-rtl" in out
    assert "msg-deny" in out


def test_real_sequence_figures_all_expand(built) -> None:
    page, _ = built
    assert 'data-cols=' not in page  # every one was rewritten
    assert page.count('class="seq-col"') > 0


def test_recurring_callouts_are_typed(builder, built) -> None:
    """All nine recurring callout kinds must be distinguishable.

    Undifferentiated they read as one long grey block, so a reader skimming for
    the argument cannot tell a worked example from a warning from a statement of
    scope. The kind comes from the bolded lead, not from writer-added classes.
    """
    page, _ = built
    found = {
        kind: page.count(f'callout callout-{kind}"') for kind in set(builder.CALLOUT_KINDS.values())
    }
    assert all(count > 0 for count in found.values()), found
    # Every chapter opens with a scenario, objectives, and prerequisites.
    assert found["scenario"] == 41
    assert found["objectives"] == 41
    assert found["prerequisites"] == 41
    assert sum(found.values()) > 300


def test_unknown_callout_leads_fall_through_untyped(builder) -> None:
    """One-off leads keep the generic style rather than being mislabelled."""
    markup = "<blockquote>\n<p><strong>Residual risks accepted.</strong> text</p></blockquote>"
    assert builder.classify_callouts(markup) == markup


def _stylesheet(page: str) -> str:
    css = page.split("<style>", 1)[1].split("</style>", 1)[0]
    return re.sub(r"\s+", " ", css)


def _without_viewport_media_blocks(css: str) -> str:
    """Strip ``@media (max-width: ...)`` blocks, brace-matched.

    Splitting on the first ``@media`` does not work: the dark-scheme block sits
    near the top of the file and would take the whole stylesheet with it.
    """
    out, i = [], 0
    while i < len(css):
        start = css.find("@media (max-width", i)
        if start == -1:
            out.append(css[i:])
            break
        out.append(css[i:start])
        depth, j = 0, css.index("{", start)
        for j in range(j, len(css)):
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
                if depth == 0:
                    break
        i = j + 1
    return "".join(out)


def test_stylesheet_never_hides_sequence_columns(built) -> None:
    """Regression: a narrow-screen rule set ``.seq-col { display: none }``.

    That stripped every column label from sequence figures on a phone, leaving
    an unlabelled stack of sentences -- the diagram stopped being a diagram and
    read as prose. A figure whose content *is* the relationship between its
    columns cannot survive losing them, so narrow screens pan the figure
    instead.
    """
    css = _stylesheet(built[0])
    assert re.search(r"\.seq-col[^{]*\{[^}]*display:\s*none", css) is None


def test_figures_pan_rather_than_reflow_at_every_width(built) -> None:
    """Panning is not a narrow-screen special case.

    Wrapping broke figures on the desktop too: 34 of 42 flows ran onto two to
    four rows inside the old 34rem column, so arrows pointed off the end of a
    line and steps could be read out of order. Both rules are therefore global,
    not confined to a media query.
    """
    unconditional = _without_viewport_media_blocks(_stylesheet(built[0]))
    assert re.search(r"\.nx-fig \.fig-body \{[^}]*overflow-x: auto", unconditional)
    assert re.search(r"\.flow \{[^}]*flex-wrap: nowrap", unconditional)


def test_nodes_are_visually_distinct_from_the_page(built) -> None:
    """Regression: nodes were --paper, the same fill as the page behind them.

    A box with no fill contrast and a hairline border reads as a word rather
    than a box, which is why figures looked like text. Page, container, and node
    now occupy three different surfaces.
    """
    css = _stylesheet(built[0])
    node_rule = re.search(r"\.node \{[^}]*\}", css)
    assert node_rule, "no .node rule found"
    assert "background: var(--band-deep)" in node_rule.group(0)


def test_prose_and_figures_get_different_measures(built) -> None:
    """Figures must be allowed wider than the text column, or they cramp."""
    css = _stylesheet(built[0])
    assert re.search(r"--measure:\s*40rem", css)
    assert re.search(r"--wide:\s*60rem", css)
    assert ".doc > .nx-fig," in css  # figures break out of the prose track


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------


def test_every_table_scrolls_inside_its_own_container(built) -> None:
    """Regression: bare tables made the whole page scroll sideways on a phone.

    A table wider than the viewport widened the document itself, so at 375px
    every line of prose ran off-screen. Confining the scroll to the table keeps
    the body readable. Code blocks already scroll inside their own ``<pre>``.
    """
    page, _ = built
    tables = page.count("<table")
    assert tables > 0, "the book rendered no tables, so this would prove nothing"
    assert page.count('<div class="table-wrap"><table') == tables


def test_wrap_tables_leaves_code_alone(builder) -> None:
    markup = "<p>x</p><table><tr><td>a</td></tr></table><pre><code>&lt;table&gt;</code></pre>"
    out = builder.wrap_tables(markup)
    assert out.count('class="table-wrap"') == 1
    assert "<pre><code>&lt;table&gt;</code></pre>" in out


# --------------------------------------------------------------------------
# Manuscript validation
# --------------------------------------------------------------------------


def _write(path: Path, meta: str, body: str = "# T\n\ntext\n") -> None:
    path.write_text(f"---\n{meta}\n---\n\n{body}", encoding="utf-8")


def test_missing_title_is_rejected(builder, tmp_path: Path) -> None:
    _write(tmp_path / "ch01_x.md", "chapter: 1\npart: I")
    with pytest.raises(builder.BuildError, match="no 'title'"):
        builder.load_documents(tmp_path)


def test_duplicate_chapter_number_is_rejected(builder, tmp_path: Path) -> None:
    _write(tmp_path / "ch01_a.md", 'chapter: 1\npart: I\ntitle: "A"')
    _write(tmp_path / "ch01_b.md", 'chapter: 1\npart: I\ntitle: "B"')
    with pytest.raises(builder.BuildError, match="duplicate chapter number"):
        builder.load_documents(tmp_path)


def test_unknown_part_is_rejected(builder, tmp_path: Path) -> None:
    _write(tmp_path / "ch01_a.md", 'chapter: 1\npart: XI\ntitle: "A"')
    with pytest.raises(builder.BuildError, match="not one of"):
        builder.load_documents(tmp_path)


def test_unclassifiable_file_is_rejected(builder, tmp_path: Path) -> None:
    _write(tmp_path / "stray.md", 'title: "Stray"')
    with pytest.raises(builder.BuildError, match="cannot classify"):
        builder.load_documents(tmp_path)


def test_part_titles_come_from_the_design_document(builder) -> None:
    titles = builder.load_part_titles(DESIGN)
    assert set(titles) >= set(builder.PART_ORDER)
    assert titles["I"] == "Why Governed Agentic Systems Are Needed"


# --------------------------------------------------------------------------
# Output document
# --------------------------------------------------------------------------


def test_output_is_a_single_self_contained_document(built) -> None:
    page, _ = built
    assert page.startswith("<!doctype html>")
    # The stylesheet is inlined: no external fetches, so the file is reviewable
    # from disk with no server and no network.
    assert "<style>" in page
    assert 'rel="stylesheet"' not in page
    assert "<script" not in page


def test_table_of_contents_links_to_every_document(builder, built) -> None:
    page, _ = built
    for doc in builder.load_documents(MANUSCRIPT):
        assert f'href="#{doc.slug}"' in page
        assert f'id="{doc.slug}"' in page


def test_persistent_index_reaches_every_chapter_and_appendix(builder, built) -> None:
    """The sidebar is how a reader moves between subjects mid-book.

    The contents page at the top is only reachable by scrolling back to it, so
    every chapter, appendix, and end-matter target must also be in the nav that
    stays on screen.
    """
    page, _ = built
    nav = page.split('<nav class="booknav"', 1)[1].split("</nav>", 1)[0]
    documents = builder.load_documents(MANUSCRIPT)
    for doc in documents:
        assert f'href="#{doc.slug}"' in nav, f"{doc.label} missing from the persistent index"
    assert 'href="#bibliography"' in nav
    assert 'href="#index"' in nav
    # Grouped by part so 41 chapters stay scannable.
    assert nav.count("<details") == len(builder.PART_ORDER) + 2  # parts + appendices + end matter


def test_index_navigation_needs_no_script(built) -> None:
    """Collapsible parts are <details>, so navigation survives with JS disabled."""
    page, _ = built
    assert "<script" not in page
    assert "<details" in page


def test_main_cli_writes_the_book(builder, tmp_path: Path, capsys) -> None:
    out = tmp_path / "nested" / "book.html"
    assert builder.main(["--out", str(out)]) == 0
    assert out.exists()
    assert "documents=54" in capsys.readouterr().out
