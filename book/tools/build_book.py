"""Assemble the *Governed Agentic Systems* manuscript into one reviewable HTML book.

Scope is deliberately HTML + CSS. There is no PDF or DOCX stage: those depend on
tooling (Paged.js, pandoc) that cannot be exercised in this environment, and a
build step nobody can run is worse than an absent one. The output is a single
self-contained ``book.html`` that renders the whole manuscript in a browser.

What this module owns, and why each piece has to live in Python rather than CSS:

* **Ordering.** Front matter, then Parts I-VIII in chapter order, then appendices
  A-J, then back matter. The order is derived from each file's frontmatter, never
  from filenames, so renaming a chapter cannot silently reorder the book.
* **Sequence figures.** ``<div class="seq-cols" data-cols="A|B|C">`` carries its
  columns in a delimited attribute, and CSS cannot split an attribute value. The
  build expands those into real column elements and resolves each message's
  ``data-from``/``data-to`` into explicit grid placement.
* **Citations.** ``[@key]`` becomes a numbered reference into the canonical
  bibliography. An unknown key is a build error, which enforces in the toolchain
  the claim discipline that ``book/design/02_style_guide.md`` states in prose.
* **Index.** The manuscript carries 500+ ``<span class="ix" data-ix="main!sub">``
  markers. Each becomes a numbered anchor, collected into a back-of-book index.

Run ``python book/tools/build_book.py`` and open ``book/tools/out/book.html``.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import mistune
import yaml

BOOK_ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT_DIR = BOOK_ROOT / "manuscript"
DESIGN_DIR = BOOK_ROOT / "design"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "out"

BOOK_TITLE = "Governed Agentic Systems"
BOOK_SUBTITLE = "Engineering Policy, Enforcement, Evidence, and Assurance — with Nornyx"

# Roman numerals for Parts I-VIII, in book order. Parsed part titles are matched
# against this so an unexpected part in the design document fails loudly.
PART_ORDER = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]

_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
_PART_HEADING = re.compile(r"^###\s+Part\s+([IVX]+)\s+—\s+(.+?)\s*$", re.M)
# A bibliography line is "- **key** — entry", optionally carrying a qualifier
# such as "- **kernighan-pike** *(optional craft ref)* — entry". _BIB_KEY_LINE
# matches the looser shape so the build can detect entries the strict pattern
# would drop, rather than silently losing a reference and reporting its
# citations as unknown.
_BIB_ENTRY = re.compile(
    r"^-\s+\*\*([A-Za-z0-9][A-Za-z0-9._-]*)\*\*"
    r"(?:\s+\*\(([^)]*)\)\*)?"
    r"\s+—\s+(.+?)\s*$",
    re.M,
)
_BIB_KEY_LINE = re.compile(r"^-\s+\*\*([A-Za-z0-9][A-Za-z0-9._-]*)\*\*", re.M)
_CITATION = re.compile(r"\[@([A-Za-z0-9._-]+(?:\s*;\s*@[A-Za-z0-9._-]+)*)\]")
_IX_SPAN = re.compile(r'<span class="ix" data-ix="([^"]*)"\s*>')
_SEQ_COLS = re.compile(r'<div class="seq-cols" data-cols="([^"]*)"\s*>\s*</div>')
_MSG = re.compile(r'<div class="msg"((?:\s+data-[a-z]+="[^"]*")+)\s*>')
_ATTR = re.compile(r'data-([a-z]+)="([^"]*)"')
_TABLE = re.compile(r"<table\b.*?</table>", re.S)

# Renders markdown fragments (bibliography entries), as opposed to whole
# documents. The `url` plugin turns the bare URLs several entries end in into
# real links.
_INLINE_MARKDOWN = mistune.create_markdown(
    renderer=mistune.HTMLRenderer(escape=False), plugins=["url"]
)

# Rendered HTML regions whose contents are literal text: citation and index
# processing must not descend into them, or a code listing that happens to
# contain "[@" would be rewritten into a reference.
_PROTECTED = re.compile(r"(<pre\b.*?</pre>|<code\b.*?</code>)", re.S)

# Table wrapping guards block code only. _PROTECTED also splits on *inline*
# <code>, and this manuscript's tables routinely contain it (`| `--flag` | ... |`),
# which would cut a table across chunk boundaries so that neither half matched.
# A table cannot occur inside <pre>, so the narrower guard is sufficient.
_PRE_ONLY = re.compile(r"(<pre\b.*?</pre>)", re.S)


class BuildError(Exception):
    """A manuscript or design-document problem that must stop the build."""


@dataclass
class Document:
    """One manuscript file, with the metadata that fixes its place in the book."""

    path: Path
    kind: str  # "front" | "chapter" | "appendix" | "back"
    title: str
    body: str
    slug: str
    chapter: int | None = None
    part: str | None = None
    appendix: str | None = None
    html: str = ""
    sections: list[tuple[str, str]] = field(default_factory=list)

    @property
    def label(self) -> str:
        """Short spine label, e.g. "Chapter 7" or "Appendix A"."""
        if self.kind == "chapter":
            return f"Chapter {self.chapter}"
        if self.kind == "appendix":
            return f"Appendix {self.appendix}"
        return self.title


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "section"


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Return ``(metadata, body)``; a file without frontmatter yields ``({}, text)``."""
    match = _FRONTMATTER.match(text)
    if not match:
        return {}, text
    meta = yaml.safe_load(match.group(1)) or {}
    if not isinstance(meta, dict):
        raise BuildError(f"frontmatter must be a mapping, got {type(meta).__name__}")
    return meta, text[match.end() :]


def render_inline(text: str) -> str:
    """Render a single line of markdown without the wrapping block paragraph.

    Used for bibliography entries, which are markdown fragments rather than
    documents: they italicise titles, mark revisions as code, and cite bare URLs.
    """
    rendered = _INLINE_MARKDOWN(text).strip()
    if rendered.startswith("<p>") and rendered.endswith("</p>"):
        rendered = rendered[len("<p>") : -len("</p>")]
    return rendered.strip()


def load_part_titles(design_dir: Path = DESIGN_DIR) -> dict[str, str]:
    """Parse Part titles from the design document rather than hardcoding them.

    The design document is the source of truth for the book's shape; duplicating
    the titles here would let the two drift apart silently.
    """
    source = design_dir / "01_book_design.md"
    titles = {roman: title for roman, title in _PART_HEADING.findall(_read(source))}
    missing = [roman for roman in PART_ORDER if roman not in titles]
    if missing:
        raise BuildError(f"{source.name} declares no title for Part(s): {', '.join(missing)}")
    return titles


def load_bibliography(design_dir: Path = DESIGN_DIR) -> list[tuple[str, str]]:
    """Parse the canonical bibliography into ``[(key, rendered_entry)]``, in file order."""
    source = design_dir / "05_bibliography.md"
    text = _read(source)
    matches = _BIB_ENTRY.findall(text)
    if not matches:
        raise BuildError(f"{source.name} yielded no bibliography entries")

    # Every line that looks like an entry must have parsed. Without this check a
    # formatting variant the strict pattern misses would drop the reference and
    # then surface, confusingly, as an "unknown citation key" in some chapter.
    declared = _BIB_KEY_LINE.findall(text)
    parsed = {key for key, _, _ in matches}
    dropped = [key for key in declared if key not in parsed]
    if dropped:
        raise BuildError(
            f"{source.name}: {len(dropped)} entry line(s) did not parse: {', '.join(dropped)}"
        )

    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key, qualifier, body in matches:
        if key in seen:
            raise BuildError(f"duplicate bibliography key: {key}")
        seen.add(key)
        note = f' <span class="ref-note">({html.escape(qualifier)})</span>' if qualifier else ""
        # Entries are markdown: nearly every one italicises a title and several
        # carry bare URLs. Inserted raw they would render as literal asterisks
        # and dead URL text, so the body goes through the inline renderer.
        entries.append((key, f"{render_inline(body)}{note}"))
    return entries


def load_documents(manuscript_dir: Path = MANUSCRIPT_DIR) -> list[Document]:
    """Discover manuscript files and return them in book order.

    Order comes from frontmatter (``chapter``/``appendix``/``part``), not from
    filenames. ``notes/`` is drafting apparatus and is never part of the book.
    """
    documents: list[Document] = []
    for path in sorted(manuscript_dir.glob("*.md")):
        meta, body = split_frontmatter(_read(path))
        title = meta.get("title")
        if not title:
            raise BuildError(f"{path.name}: frontmatter has no 'title'")
        slug = _slugify(path.stem)
        if "chapter" in meta:
            part = str(meta.get("part") or "").strip()
            if part not in PART_ORDER:
                raise BuildError(f"{path.name}: part {part!r} is not one of {PART_ORDER}")
            documents.append(
                Document(
                    path=path,
                    kind="chapter",
                    title=str(title),
                    body=body,
                    slug=slug,
                    chapter=int(meta["chapter"]),
                    part=part,
                )
            )
        elif "appendix" in meta:
            documents.append(
                Document(
                    path=path,
                    kind="appendix",
                    title=str(title),
                    body=body,
                    slug=slug,
                    appendix=str(meta["appendix"]).strip(),
                )
            )
        elif path.stem.startswith("front"):
            documents.append(
                Document(path=path, kind="front", title=str(title), body=body, slug=slug)
            )
        elif path.stem.startswith("back"):
            documents.append(
                Document(path=path, kind="back", title=str(title), body=body, slug=slug)
            )
        else:
            raise BuildError(f"{path.name}: cannot classify (no chapter/appendix, no front/back)")

    chapters = [d.chapter for d in documents if d.kind == "chapter"]
    duplicates = {n for n in chapters if chapters.count(n) > 1}
    if duplicates:
        raise BuildError(f"duplicate chapter number(s): {sorted(duplicates)}")

    order = {"front": 0, "chapter": 1, "appendix": 2, "back": 3}

    def sort_key(doc: Document) -> tuple:
        if doc.kind == "chapter":
            return (order[doc.kind], PART_ORDER.index(doc.part or ""), doc.chapter or 0, "")
        if doc.kind == "appendix":
            return (order[doc.kind], 0, 0, doc.appendix or "")
        return (order[doc.kind], 0, 0, doc.path.stem)

    return sorted(documents, key=sort_key)


class _BookRenderer(mistune.HTMLRenderer):
    """HTML renderer that gives every heading a stable, book-unique id.

    Without ids there is nothing for the table of contents to link to. Ids are
    prefixed with the document slug because section numbering (``7.1``) repeats
    across chapters and would otherwise collide.
    """

    def __init__(self, doc_slug: str) -> None:
        super().__init__(escape=False)
        self._doc_slug = doc_slug
        self._seen: dict[str, int] = {}
        self.headings: list[tuple[int, str, str]] = []

    def heading(self, text: str, level: int, **attrs: object) -> str:
        plain = re.sub(r"<[^>]+>", "", text).strip()
        base = f"{self._doc_slug}--{_slugify(plain)}"
        count = self._seen.get(base, 0)
        self._seen[base] = count + 1
        anchor = base if count == 0 else f"{base}-{count + 1}"
        self.headings.append((level, anchor, plain))
        return f'<h{level} id="{anchor}">{text}</h{level}>\n'


def render_markdown(body: str, doc_slug: str) -> tuple[str, list[tuple[int, str, str]]]:
    """Render one document's markdown, returning ``(html, headings)``."""
    renderer = _BookRenderer(doc_slug)
    markdown = mistune.create_markdown(
        renderer=renderer,
        plugins=["table", "strikethrough", "url"],
    )
    return markdown(body), renderer.headings


def _map_outside_code(text: str, transform) -> str:
    """Apply ``transform`` to every part of ``text`` that is not a code region."""
    parts = _PROTECTED.split(text)
    return "".join(part if index % 2 else transform(part) for index, part in enumerate(parts))


def expand_sequences(markup: str) -> str:
    """Turn ``data-cols`` and ``data-from``/``data-to`` into real layout.

    CSS cannot split ``"Agent|Enforcement point|Decision point"`` into columns,
    and cannot turn an arbitrary ``data-from`` value into a grid position. Both
    are resolved here so the stylesheet stays declarative.
    """

    def expand_cols(match: re.Match[str]) -> str:
        names = [name.strip() for name in match.group(1).split("|") if name.strip()]
        cells = "".join(f'<div class="seq-col">{html.escape(name)}</div>' for name in names)
        return f'<div class="seq-cols" data-count="{len(names)}">{cells}</div>'

    def place_message(match: re.Match[str]) -> str:
        attrs = dict(_ATTR.findall(match.group(1)))
        try:
            start = int(attrs.get("from", "1"))
            end = int(attrs.get("to", "1"))
        except ValueError as exc:  # pragma: no cover - malformed manuscript
            raise BuildError(f"sequence message has non-numeric endpoints: {attrs}") from exc
        kind = attrs.get("kind", "call")
        low, high = min(start, end), max(start, end)
        direction = "rtl" if end < start else "ltr"
        style = f"grid-column: {low} / {high + 1};"
        return (
            f'<div class="msg msg-{html.escape(kind)} msg-{direction}" '
            f'style="{style}" data-from="{start}" data-to="{end}">'
        )

    markup = _SEQ_COLS.sub(expand_cols, markup)
    return _MSG.sub(place_message, markup)


def wrap_tables(markup: str) -> str:
    """Put each table in its own horizontal scroll container.

    A wide table is the one thing in this manuscript that cannot be made to fit
    a phone without either shrinking text to unreadability or dropping columns.
    Left bare it widens the whole page, so the body scrolls sideways and every
    line of prose runs off the screen. Wrapping confines the scroll to the table
    itself. Code blocks already scroll inside their own ``<pre>``.
    """
    parts = _PRE_ONLY.split(markup)
    return "".join(
        part
        if index % 2
        else _TABLE.sub(lambda m: f'<div class="table-wrap">{m.group(0)}</div>', part)
        for index, part in enumerate(parts)
    )


def link_citations(
    markup: str, bibliography: list[tuple[str, str]]
) -> tuple[str, set[str]]:
    """Replace ``[@key]`` with numbered references; unknown keys stop the build."""
    numbers = {key: index for index, (key, _) in enumerate(bibliography, start=1)}
    used: set[str] = set()
    unknown: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        keys = [part.strip().lstrip("@") for part in match.group(1).split(";")]
        rendered = []
        for key in keys:
            if key not in numbers:
                # Collected rather than rendered: an unknown key always raises
                # below, so there is no partially-built output to mark up.
                unknown.add(key)
                continue
            used.add(key)
            number = numbers[key]
            rendered.append(f'<a class="cite" href="#ref-{key}" title="{html.escape(key)}">[{number}]</a>')
        return "".join(rendered)

    result = _map_outside_code(markup, lambda chunk: _CITATION.sub(replace, chunk))
    if unknown:
        raise BuildError(
            "unknown citation key(s) not in book/design/05_bibliography.md: "
            + ", ".join(sorted(unknown))
        )
    return result, used


def collect_index(markup: str, counter_start: int = 0) -> tuple[str, list[tuple[str, str]], int]:
    """Give each ``ix`` span an anchor id and collect ``(entry, anchor)`` pairs."""
    entries: list[tuple[str, str]] = []
    counter = counter_start

    def anchor(match: re.Match[str]) -> str:
        nonlocal counter
        counter += 1
        ident = f"ix-{counter}"
        entries.append((match.group(1), ident))
        return f'<span class="ix" id="{ident}" data-ix="{match.group(1)}">'

    result = _map_outside_code(markup, lambda chunk: _IX_SPAN.sub(anchor, chunk))
    return result, entries, counter


def build_index_html(entries: list[tuple[str, str]]) -> str:
    """Render the back-of-book index; ``main!sub`` nests sub-entries under main."""
    tree: dict[str, dict[str, list[str]]] = {}
    for raw, anchor in entries:
        main, _, sub = raw.partition("!")
        main = main.strip() or "(unlabelled)"
        tree.setdefault(main, {}).setdefault(sub.strip(), []).append(anchor)

    def links(anchors: list[str]) -> str:
        return ", ".join(
            f'<a href="#{a}">{i}</a>' for i, a in enumerate(anchors, start=1)
        )

    rows = []
    for main in sorted(tree, key=lambda value: value.lower()):
        subs = tree[main]
        direct = subs.get("", [])
        head = f"<dt>{html.escape(main)}"
        if direct:
            head += f" <span class=\"locs\">{links(direct)}</span>"
        head += "</dt>"
        rows.append(head)
        for sub in sorted((s for s in subs if s), key=lambda value: value.lower()):
            rows.append(
                f'<dd>{html.escape(sub)} <span class="locs">{links(subs[sub])}</span></dd>'
            )
    return '<dl class="index">\n' + "\n".join(rows) + "\n</dl>"


def build_toc(documents: list[Document], part_titles: dict[str, str]) -> str:
    """Render the table of contents, grouping chapters under their parts."""
    lines = ['<nav class="toc" id="toc">', "<h1>Contents</h1>", "<ol class=\"toc-list\">"]
    current_part: str | None = None
    open_part = False
    for doc in documents:
        if doc.kind == "chapter" and doc.part != current_part:
            if open_part:
                lines.append("</ol></li>")
            current_part = doc.part
            lines.append(
                f'<li class="toc-part"><span class="part-label">Part {current_part}</span>'
                f' — {html.escape(part_titles[current_part or ""])}<ol>'
            )
            open_part = True
        elif doc.kind != "chapter" and open_part:
            lines.append("</ol></li>")
            open_part = False
            current_part = None

        label = f'<span class="toc-label">{html.escape(doc.label)}</span> ' if doc.kind in {"chapter", "appendix"} else ""
        lines.append(f'<li class="toc-{doc.kind}"><a href="#{doc.slug}">{label}{html.escape(doc.title)}</a>')
        if doc.sections:
            lines.append('<ol class="toc-sections">')
            for anchor, text in doc.sections:
                lines.append(f'<li><a href="#{anchor}">{html.escape(text)}</a></li>')
            lines.append("</ol>")
        lines.append("</li>")
    if open_part:
        lines.append("</ol></li>")
    lines.extend(['<li class="toc-back"><a href="#bibliography">Bibliography</a></li>',
                  '<li class="toc-back"><a href="#index">Index</a></li>',
                  "</ol>", "</nav>"])
    return "\n".join(lines)


def build_book(
    manuscript_dir: Path = MANUSCRIPT_DIR,
    design_dir: Path = DESIGN_DIR,
    assets_dir: Path = ASSETS_DIR,
) -> tuple[str, dict]:
    """Build the whole book, returning ``(html, stats)``."""
    part_titles = load_part_titles(design_dir)
    bibliography = load_bibliography(design_dir)
    documents = load_documents(manuscript_dir)
    if not documents:
        raise BuildError(f"no manuscript files found in {manuscript_dir}")

    index_entries: list[tuple[str, str]] = []
    used_keys: set[str] = set()
    counter = 0
    figure_count = 0

    for doc in documents:
        markup, headings = render_markdown(doc.body, doc.slug)
        markup = expand_sequences(markup)
        markup = wrap_tables(markup)
        markup, doc_used = link_citations(markup, bibliography)
        markup, doc_index, counter = collect_index(markup, counter)
        used_keys |= doc_used
        index_entries.extend(doc_index)
        figure_count += markup.count('class="nx-fig"')
        # The document's own H1 becomes the section heading, so drop it from the
        # per-document contents and keep only H2 sections.
        doc.sections = [(anchor, text) for level, anchor, text in headings if level == 2]
        doc.html = markup

    body_parts: list[str] = []
    current_part: str | None = None
    for doc in documents:
        if doc.kind == "chapter" and doc.part != current_part:
            current_part = doc.part
            body_parts.append(
                f'<section class="part-opener" id="part-{current_part}">'
                f'<p class="part-number">Part {current_part}</p>'
                f'<h1>{html.escape(part_titles[current_part or ""])}</h1>'
                "</section>"
            )
        label = f'<p class="doc-label">{html.escape(doc.label)}</p>' if doc.kind in {"chapter", "appendix"} else ""
        body_parts.append(
            f'<section class="doc doc-{doc.kind}" id="{doc.slug}">{label}{doc.html}</section>'
        )

    bib_rows = "\n".join(
        f'<li id="ref-{key}"><span class="ref-num">[{number}]</span> {text}</li>'
        for number, (key, text) in enumerate(bibliography, start=1)
    )
    bibliography_html = (
        '<section class="doc doc-back" id="bibliography"><h1>Bibliography</h1>'
        f'<ol class="refs">{bib_rows}</ol></section>'
    )
    index_html = (
        '<section class="doc doc-back" id="index"><h1>Index</h1>'
        f"{build_index_html(index_entries)}</section>"
    )

    css = _read(assets_dir / "book.css")
    toc = build_toc(documents, part_titles)

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(BOOK_TITLE)}</title>
<style>
{css}
</style>
</head>
<body>
<header class="titlepage">
<h1>{html.escape(BOOK_TITLE)}</h1>
<p class="subtitle">{html.escape(BOOK_SUBTITLE)}</p>
</header>
{toc}
<main>
{"".join(body_parts)}
{bibliography_html}
{index_html}
</main>
</body>
</html>
"""

    stats = {
        "documents": len(documents),
        "chapters": sum(1 for d in documents if d.kind == "chapter"),
        "appendices": sum(1 for d in documents if d.kind == "appendix"),
        "parts": len({d.part for d in documents if d.kind == "chapter"}),
        "figures": figure_count,
        "index_entries": len(index_entries),
        "bibliography_entries": len(bibliography),
        "citations_used": len(used_keys),
        "bytes": len(page.encode("utf-8")),
    }
    return page, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT_DIR / "book.html",
        help="output HTML path (default: book/tools/out/book.html)",
    )
    parser.add_argument(
        "--manuscript", type=Path, default=MANUSCRIPT_DIR, help="manuscript directory"
    )
    parser.add_argument("--design", type=Path, default=DESIGN_DIR, help="design directory")
    args = parser.parse_args(argv)

    try:
        page, stats = build_book(args.manuscript, args.design)
    except BuildError as exc:
        print(f"book build failed: {exc}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")
    summary = ", ".join(f"{key}={value}" for key, value in stats.items())
    print(f"wrote {args.out}")
    print(summary)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
