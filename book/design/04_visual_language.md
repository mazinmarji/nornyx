# Visual Language — figure system (binding)

All figures are original, information-first, print-friendly (grayscale-safe), and use one of the
component systems below. No decorative graphics, no AI art, no robots/circuitry. Every figure:
number (`Figure <ch>.<n>`), descriptive title, caption explaining its *teaching* purpose,
referenced from body text, consistent notation.

## Notation (used across the whole book)

- Rectangles: components/actors. Rounded: human actors. Double border (or `class="authority"`):
  authoritative/normative elements. Dashed border: untrusted or out-of-coverage elements.
- Solid arrows: control/data flow. Dashed arrows: bypass or ungoverned paths. Diamond: decision.
- Shaded background bands: trust zones / tiers / layers. A small ⛔ or ✋ glyph marks enforcement
  points; 📄 marks evidence emission (use sparingly; text labels preferred).

## Component A — HTML/CSS figures (preferred for layers, tiers, zones, flows, sequences)

Wrap in:
```html
<figure class="nx-fig" id="fig-7-1">
  <div class="fig-body"> ... components ... </div>
  <figcaption><b>Figure 7.1 — Title.</b> Teaching caption.</figcaption>
</figure>
```
Available building blocks (CSS provided by the build; just use the classes):
- `<div class="layers">` containing `<div class="layer" data-note="...">Label</div>` rows —
  layered architectures (top = closest to human intent). Modifier `layer authority`,
  `layer untrusted`.
- `<div class="flow">` containing `<div class="node">A</div><div class="arr">→</div>...` —
  left-to-right pipelines. `arr deny` renders a blocked arrow (⛔); `arr dashed` a bypass.
  Wrap rows with `<div class="flow-col">` to stack parallel flows.
- `<div class="zones">` containing nested `<div class="zone" data-name="research-internal">`
  boxes with `<div class="node">` members — trust-zone containment; `zone untrusted` for dashed.
- `<div class="seq">` sequence diagrams: `<div class="seq-cols" data-cols="Caller|Adapter|
  Authorizer|Tool">` then message rows `<div class="msg" data-from="1" data-to="3"
  data-kind="call|return|deny">label</div>` (build renders as a grid with lifelines).
- `<div class="tiers">` containing `<div class="tier" data-name="Tier 2">` columns with `<ul>`
  bullet contents — comparison columns.
- `<div class="hier">` for trees (org hierarchies): nested `<ul><li>` rendered as a bracketed tree.
- Free-form fallback: `<table class="fig-table">` styled schematic tables.

## Component B — Graphviz DOT (for graphs: delegation chains, threat trees, composition DAGs)

Fenced block, rendered to SVG at build time with the book theme (fonts/colors injected — do not
set your own):
````
```dot
// fig=22-3 title="Adapter decision path"
digraph G { rankdir=LR; a [label="Framework call"]; ... }
```
````
The `// fig=` comment line is REQUIRED and drives numbering/anchor. Follow with a normal
`<figcaption>`-style bold caption paragraph: `**Figure 22.3 — Title.** Caption.` Use node attrs
only: `shape=box` (default), `shape=box, style=rounded` humans, `style=dashed` untrusted/bypass,
`peripheries=2` authoritative, `style=filled` for zone clusters via `subgraph cluster_x`.

## Required diagram inventory (owners = chapters)

system context (16); policy decision & enforcement flows (10, 22); identity/capability relations
(5, 17); trust zones (6, 31); delegation chains (5, 31); approval flows (9, 30); policy
composition (8, 18, 32); evidence lifecycle (11, 20); runtime sequence diagrams (20, 23, 24);
assurance-tier comparison (13); adapter boundary (22–25); bypass/threat (14, 34); CI/CD
governance flow (29); enterprise hierarchy (32); ecosystem positioning (4, 16). Chapters may add
more where they teach.
