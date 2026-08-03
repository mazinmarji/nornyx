# Writer Instructions (read fully before writing anything)

You are one of several authors producing chapters of the textbook *Governed Agentic Systems:
Engineering Policy, Enforcement, Evidence, and Assurance — with Nornyx*. Your chapters must be
publication-quality textbook prose that a professional technology publisher could evaluate.

## Mandatory reading, in order

1. `/home/user/nornyx/book/design/01_book_design.md` — thesis, part structure, YOUR chapter briefs,
   the eight questions, progression rules, case-study strategy.
2. `/home/user/nornyx/book/design/02_style_guide.md` — voice, claim discipline, exact markup for
   callouts/listings/tables/figures/citations/index terms. BINDING.
3. `/home/user/nornyx/book/design/03_case_study_bible.md` — Northstar universe; canonical names.
4. `/home/user/nornyx/book/design/04_visual_language.md` — figure components; use them exactly.
5. `/home/user/nornyx/book/design/05_bibliography.md` — the ONLY citation keys you may use.
6. The fact packs in `/home/user/nornyx/book/factpack/` relevant to your chapters (your task
   message names the primary ones). Every Nornyx-specific statement must be supported there or
   verified by you directly against the repository at `/home/user/nornyx` (preferred for any code
   or schema you quote — read the actual file and cite its path in the listing caption).
7. The prior edition of the book (source material, NOT authority):
   `/tmp/claude-0/-home-user-nornyx/1f5114ce-1214-5a5b-8235-bf34ffc46410/scratchpad/book.txt` —
   reuse its good ideas (claims discipline, tier model, occurrence semantics) but write fresh
   textbook prose; do not copy its compressed style.

## Output

- One file per chapter: `/home/user/nornyx/book/manuscript/chNN_<slug>.md` (NN two-digit), with
  YAML front matter exactly:
  `---`\n`chapter: <n>`\n`part: <ROMAN>`\n`title: "<Title>"`\n`---`
  then `# <Title>` as the only H1.
- One notes file per chapter: `/home/user/nornyx/book/manuscript/notes/chNN_notes.md` containing:
  claims you could NOT verify (with what you wrote instead), any `PROPOSED-REF:` additions, and a
  list of the repository paths you personally verified.
- Do not modify ANY file outside `book/manuscript/`. Do not run `pip install`. You may run
  read-only commands (and `nornyx` CLI commands with outputs directed to /tmp) to verify behavior.

## Quality bar (the build enforces some of this mechanically)

- Length 3,800–5,500 words per chapter unless your task message says otherwise. No padding; no
  compression of hard topics.
- Chapter skeleton: opening scenario callout → learning objectives → prerequisites → 4–7 numbered
  `##` sections following the progression intuition → concept → architecture → implementation →
  verification → limitations → `## Summary` → `## Review questions` (4–6) → `## Exercises` (2–3)
  → `## Further reading` (2–5 citation keys, one line each on why).
- 2–5 figures per chapter using ONLY the sanctioned components; every figure numbered
  `Figure <ch>.<n>`, captioned with its teaching purpose, and referenced in body text. Use
  `<figure class="nx-fig" id="fig-<ch>-<n>">...<figcaption><b>Figure <ch>.<n> — Title.</b>
  caption</figcaption></figure>` for HTML figures; for DOT figures put the caption as a
  `**Figure <ch>.<n> — Title.** caption` paragraph immediately after the fenced block.
- Listings numbered `Listing <ch>.<n>` with bold caption paragraph after the fence; tables
  `Table <ch>.<n>` likewise. Real repository excerpts cite the path in the caption. Anything not
  runnable/verified is captioned "Illustrative".
- 10–25 index spans per chapter at definitional sites: `<span class="ix" data-ix="term">term</span>`
  (subentries via `data-ix="term!sub"`). IMPORTANT: keep each span on one line.
- Status badges for Nornyx capability statements: `**[implemented]**`, `**[guidance]**`,
  `**[extension]**` per the style guide (only from Ch. 16 onward as inline badges; earlier
  chapters use prose equivalents).
- Cross-reference earlier/later chapters by number per the book design; do not re-teach earlier
  material (one-sentence recap max).
- Case-study callouts advance the assigned thread; check the bible for your chapter's threads.
- Every major Nornyx claim in your chapters should be traceable: when you assert repository
  behavior, mention the evidence naturally (e.g., "the checker rejects … (diagnostic
  `AN_LOCK_ARTIFACT_HASH_MISMATCH`)") — precise, not manual-like.
- NEVER invent APIs, flags, field names, diagnostics, versions, or test names. When unsure,
  verify in the repo or soften to a general statement and log it in your notes file.

## Final reply

When done, reply with: per chapter — word count, figure/table/listing counts, the 3 most
load-bearing repository facts you relied on, and anything you flagged in notes.
