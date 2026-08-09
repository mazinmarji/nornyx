# Book build

Assembles the manuscript in `book/manuscript/` into one reviewable HTML file.

```bash
python book/tools/build_book.py
```

**Requires [Graphviz](https://graphviz.org/download/)** on `PATH`. Twenty-five of
the book's figures are Graphviz sources; without `dot` the build stops rather
than emitting them as literal text.

The result is `book/tools/out/book.html` — a single self-contained document with
the stylesheet inlined, so it opens from disk with no server and no network.
`book/.gitignore` keeps the output untracked; it is a generated artifact.

## Scope

**HTML and CSS only.** There is deliberately no PDF or DOCX stage.

The original pipeline that produced this book's typeset deliverables was never
committed — `book/.gitignore` excluded it, and it did not survive the machine it
ran on. Its fingerprint (`build/package.json`, `build/out/*_paged.html`) says it
was Node plus Paged.js. Rather than reconstruct a PDF stage that cannot be run
or verified here, this build stops at the HTML the manuscript is authored
against. Adding a Paged.js or pandoc step later means consuming `book.html`; the
assembly, numbering, index, and citation work is already done by then.

## What the build does that CSS cannot

Most of the manuscript's figure vocabulary
(`book/design/04_visual_language.md`) is plain declarative markup that
`assets/book.css` styles directly. Three things need real logic:

| Concern | Why it needs Python |
| --- | --- |
| Sequence figures | `<div class="seq-cols" data-cols="Agent\|Adapter\|Tool">` carries its columns in a delimited attribute, and CSS cannot split an attribute value. The build expands them into elements and resolves each message's `data-from`/`data-to` into an explicit `grid-column`. |
| Citations | `[@key]` becomes a numbered link into the canonical bibliography in `book/design/05_bibliography.md`. |
| Index | The 611 `<span class="ix" data-ix="main!sub">` markers each get an anchor, collected into a back-of-book index with `!` nesting sub-entries. |
| Graph figures | 25 ```` ```dot ```` fences are rendered through Graphviz and recoloured onto `currentColor`, so one rendering serves light, dark, and print. |

Ordering comes from frontmatter (`chapter`, `part`, `appendix`), never from
filenames, so renaming a file cannot silently reorder the book. Part titles are
parsed from `book/design/01_book_design.md` rather than duplicated here.

## Failure modes are deliberate

The build refuses to produce a book rather than produce a misleading one:

- an unknown citation key — enforcing in the toolchain the claim discipline that
  `book/design/02_style_guide.md` states in prose;
- a bibliography line that does not parse, which would otherwise resurface
  confusingly as an "unknown citation key" in some chapter;
- a duplicate chapter number, an unrecognised part, a missing title, or a file
  that cannot be classified as front matter, chapter, appendix, or back matter.

`book/manuscript/notes/` is drafting apparatus and is never part of the book.

## Tests

`tests/test_book_build.py` runs in the standard suite. It covers the synthetic
failure modes above and pins the real book's structure — 41 chapters, 9
appendices, 8 parts — so a manuscript change that drops a chapter fails loudly.
