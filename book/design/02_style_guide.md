# Style Guide and Claim Discipline (binding for all chapter writers)

## Voice and prose

- Professional textbook prose: explanatory, neutral, cohesive, long-form. Full sentences and
  developed paragraphs carry the argument; bullet lists only for genuinely enumerable items
  (never as a substitute for explanation). No feature-dump paragraphs.
- Present tense for system behavior; past tense for history. "We" for author+reader working
  through a problem is acceptable and preferred over "the reader" (never more than once per
  ~2 pages). Second person sparingly, in exercises and labs.
- No marketing adjectives (revolutionary, powerful, seamless, robust-as-praise, future-proof,
  cutting-edge, best-in-class). No em-dash-heavy fragment style. Expand every abbreviation at
  first use per chapter (PDP, PEP, SPI, MCP, A2A, RBAC, ABAC, IAM, CI/CD, SBOM...).
- Analogies: no extended cross-domain analogy (the telecom analogy was removed in final review);
  small local analogies where they genuinely clarify, and every analogy states where it breaks.
- Difficulty ramps: never introduce a Nornyx-specific term before the general problem it solves.

## Terminology (canonical; do not vary)

governed agentic system · control plane · executable specification · contract (a `.nyx`
document) · policy decision point (PDP) · policy enforcement point (PEP) · cooperative
enforcement · independent (mandatory) enforcement · assurance tier 1/2/3 (design-time /
cooperative runtime / independent enforcement) · trust zone · capability · gate · approval ·
exception · evidence (never "proof" for supplied evidence) · lock · digest · drift (control /
policy / configuration / framework-adapter) · occurrence · attempt · mission · operation ·
coverage inventory · wrapped / unsupported / unwrapped surface · fail-closed / fail-open ·
maker–checker · claim register · proof boundary. Nornyx file: "contract" or "`.nyx` contract",
not "script"/"config". The company is "Northstar Services" ("Northstar").

## Claim discipline (hard rules)

1. Every statement about Nornyx behavior must be supported by the fact packs
   (`book/factpack/*.md`), which cite repository paths. If the fact packs do not support a
   statement, do not write it; add it to your chapter-notes "unverified" list instead.
2. Status labels: use the inline badges **[implemented]**, **[guidance]**, **[extension]**
   exactly as defined in the book design (Ch. 16 explains them to the reader; before Ch. 16, use
   prose: "as implemented at the snapshot", "documented target architecture", "an architectural
   extension beyond the current repository"). Never present [guidance]/[extension] material in a
   way that could read as implemented.
3. Never invent a Nornyx API, CLI flag, field name, diagnostic code, or version number. Copy them
   from fact packs. If an example cannot be verified as runnable, caption it
   "Illustrative — not drawn from the repository" or use the fictional-system framing.
4. The eight assurance questions are the recurring analytical frame; major claims in Parts III–VII
   should be exercised against them at least once per chapter.
5. Standards mappings are interpretive; never state or imply certification, formal compliance,
   legal sufficiency, or regulatory approval.
6. Comparisons with named technologies (OPA, Cedar, service meshes, gateways...) must be neutral,
   dimension-based, and sourced from the bibliography; never declare Nornyx categorically superior.

## Structure markers (exact HTML/markdown forms; the build maps them to design)

- Chapter file header (YAML front matter):
  `---` / `chapter: <n>` / `part: <roman>` / `title: "..."` / `---`
- Headings: `#` chapter title (once), `##` sections, `###` subsections. No deeper.
- Callout boxes (blockquote with a bold label line, exactly these labels):
  `> **Opening scenario.** ...` · `> **Learning objectives.**` (followed by a list) ·
  `> **Prerequisites.** ...` · `> **Key idea.** ...` · `> **Misconception.** ...` ·
  `> **Nornyx in practice.** ...` · `> **Assurance boundary.** ...` ·
  `> **Design checkpoint.** ...` · `> **Case study — <Thread>.** ...`
- End matter sections: `## Summary` (paragraph + short list), `## Review questions`,
  `## Exercises`, `## Further reading` (citation keys with one-line reasons).
- Code: fenced blocks with language (`yaml`, `python`, `json`, `bash`, `text`). Introduce every
  first-of-kind listing line by line in surrounding prose. Listings that come from the repository
  cite the path in the caption. Listing captions: a bold paragraph immediately after the block:
  `**Listing 17.2 — Title.** Caption sentence(s).`
- Tables: markdown pipe tables, with `**Table 4.1 — Title.** caption` paragraph after.
- Figures: see `04_visual_language.md`. Numbered per chapter (`Figure 12.3`), every figure
  referenced from body text, caption explains the teaching purpose.
- Citations: `[@key]` inline, keys ONLY from `05_bibliography.md`. Multiple: `[@nist-ai-rmf;
  @slsa]`. If you need a source that is not listed, add a "PROPOSED-REF:" line in your chapter
  notes; do not invent keys or facts.
- Cross-references to chapters: "Chapter 12" / "Section 12.3" in prose (no links needed).
- Index terms: wrap important term introductions as `<span class="ix" data-ix="term!subterm">
  term</span>` — 10–25 per chapter, at definitional sites only.

## Length and density

4,000–6,500 words per chapter; 2–5 figures; 1–4 tables; 2–6 listings (Parts IV–VI more
code-dense; Part I lighter). Do not pad; do not compress difficult topics.
