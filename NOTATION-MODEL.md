# Notation Model · built (2026-09-25)

A diagram speaks a notation: the shapes, colours, marks and type its readers already know.
Electronics has its symbols, logic has IEEE 91 gates, process work has BPMN, plant work has
P&ID. Today the editor has one notation and its choices are scattered through the code:
- symbol drawings are hand-written `<symbol>`s with their own wire stubs
- a per-symbol table says where wires meet a glyph (`INLINE_TERMINAL_Y`, `GLYPH_CONTROL_STEM`)
- corner radii, stroke weights and label offsets are literals in the renderer
- captions are the symbol's code name in capitals (`ACT`, `HOLD`)
- nothing tells a reader what the colours and shapes mean

This model gathers them into one declared thing, a **notation**, and makes the editor's own
look the first notation rather than the only one.

## Words

| Word | Meaning |
| --- | --- |
| **Notation** | A named, versioned vocabulary: tokens, colour roles, glyphs, signal shapes. `schematic` is built in. |
| **Token** | A named size: a radius, a stroke weight, a type role, a spacing, an elevation. |
| **Colour role** | What a colour means (`flow.out`, `flow.in`, `signal.high`), with a light and a dark value. |
| **Category** | A palette slot a domain may name ("Billing", "Carrier A"). |
| **Glyph** | A drawing in a 96 x 64 box, with a title, a meaning and its terminals. |
| **Terminal** | A place on a glyph a wire may meet: `{id, role, at: [x, y], toward}`. |
| **Pin** | The short line a glyph draws from a terminal to its box edge. It is always drawn: it says "connect here". |
| **Lead** | The line from the card's edge to the pin, drawn only when a wire is attached. |
| **Icon** | A glyph with no terminals. It decorates and is never connected through. |
| **Text role** | Title, subtitle, body, caption or narration, each with its own type token. |
| **Legend** | What the notation's colours, glyphs and signal shapes mean, for what this document uses. |

## 1. A notation is data

```json
{ "id": "logic", "name": "Logic gates (IEEE 91)", "version": 1, "extends": "schematic",
  "source": "IEEE Std 91-1984, distinctive shapes",
  "tokens":  { "radius": {"core": 6, "card": 10}, "stroke": {"structure": 1.5, "flow": 2.25, "symbol": 2.5} },
  "colours": { "signal.high": {"light": "#1E8A5A", "dark": "#5CD69A"} },
  "categories": [{"slot": "C1", "name": "Data"}, {"slot": "C2", "name": "Clock"}],
  "glyphs": { "and2": { "title": "And", "family": "logic", "meaning": "High when every input is high.",
      "draw": [{"d": "M30 12h18a20 20 0 0 1 0 40H30z"}],
      "terminals": [{"id": "a", "role": "in", "at": [30, 22], "toward": "left"},
                    {"id": "b", "role": "in", "at": [30, 42], "toward": "left"},
                    {"id": "y", "role": "out", "at": [68, 32], "toward": "right"}],
      "signal": {"combine": "and"} } } }
```

- `extends` inherits everything it does not name. A notation is resolved once, into one
  flat table.
- The built-in notations live in `src/03-notation-core.js`, with no DOM, so the server
  renders and validates with the same table.
- A document names its notation with `document.notation: "logic"`. It may also carry its own
  notation in `references[]` (`kind: "notation"`), so the file stands alone. An unknown
  notation is refused (`UNKNOWN_NOTATION`), never replaced by the default.
- The editor builds its `<symbol>` elements from the resolved glyphs, and sets its CSS custom
  properties from the tokens and colour roles. A domain notation changes the picture without
  changing the code.

## 2. Terminal glyphs

A glyph that is meant to be wired declares its terminals. The renderer, not the drawing,
connects them:

- **Pin.** From each terminal to the glyph box edge in its `toward` direction, drawn at the
  symbol weight. This replaces the stubs each drawing carried (`M8 32h20`). The glyph body
  sits between its pins, so every glyph is symmetric about what it connects.
- **Lead.** From the card's edge to the pin's end, only when that terminal is wired. This is
  what `appendComponentLeads` does today, generalised to any terminal on any side.
- **Points.** A card whose glyph declares terminals takes one attachment point per terminal:
  - the point sits on the card edge its terminal faces, aligned with the terminal (`t` from
    `at`)
  - its flow is the terminal's role
  - the built-in glyphs name their terminals `in`, `out` and `control`, so every existing
    document binds unchanged
  - a logic gate's `a`, `b` and `y` become three points, so two wires meet an AND gate on its
    two inputs instead of being spliced before it
- **Signal.** A glyph may declare a `signal.combine` (`and`, `or`, `not`, `xor`...). It becomes
  the card's default combine, so the drawing and the simulation cannot disagree.
- An icon (no terminals) gets no pins and no leads. Its card keeps the standard `in`, `out` and
  `control` points.

`INLINE_TERMINAL_Y` and `GLYPH_CONTROL_STEM` are deleted: the axis and the control stem are
the terminals' own `at`.

## 3. Tokens

**Radius: offset from inside** (docs/cosmetics/corner-radii.png).
- The core keeps `radius.core`, and each line outward adds the thickness of the band inside it.
  Every line is concentric, and a thick wall is round outside.
- A plain card's radius is `radius.card` whatever its height.
- Every radius is capped at a quarter of the shorter side.
- A small mark (a capsule, a handle) is fully round or square, never in between.

**Stroke weights**, in world units: `structure` (outlines, section lines), `flow` (wires),
`symbol` (glyph bodies, pins, leads). Each has one value; a selected or highlighted state
multiplies it.

**Elevation.** A card's elevation is its nesting depth plus one:
- root cards at 1
- a card inside a container at 2, and so on
- canvas marks (wires, labels) at 0

Each level has a soft shadow token (offset, blur, opacity, separate for light and dark), drawn
with an SVG filter, so exports carry it. A nested card is lifted from its container the way
the container is lifted from the canvas. The offset outline behind cards
(`component-body-depth`) is removed: depth is a shadow, not a second border.

**Spacing.** One token each: label clearance from an edge or a line, pin length, the gap
between stacked text lines. These replace the 8, 11 and 15 offsets now in the renderer.

## 4. Type

Text is drawn as authored. Nothing on the canvas is forced into capitals. A glyph's `title`
is written in sentence case ("Act", "Hold", "And"), and is the caption a card shows when it
has no label.

| Role | Where | Token |
| --- | --- | --- |
| **title** | a card's label; a container's heading | `type.title` (600 weight) |
| **subtitle** | `config.subtitle`, one line under the title | `type.subtitle` (400, muted) |
| **body** | `config.presentation.text`, inside the card | `type.body` |
| **caption** | wire labels, point labels, channel tags | `type.caption` |
| **narration** | the subtitle track (below) | `type.narration` |

**Body text is a small, safe Markdown:**
- `**bold**`, `*italic*` and `` `code` ``
- line breaks
- `- ` list items

Anything else is shown as typed. Nothing is interpreted as HTML.

**Narration** is interface narration, shown the way a film shows subtitles:
- a caption bar at the foot of the canvas, one line or two, in the reader's language
- it comes from `document.narration`, a list of `{at, say, focus?}`:
  - `at` is a clock time or a scenario step
  - `focus` names the components to highlight while the line shows
- scenario steps may carry their own `say`
- while the clock runs, the line for the current time is shown
- `render({narration: i})` puts line `i` in a picture, which makes a narrated walkthrough a
  sequence of pictures
- narration never changes the document's meaning; it is presentation, like a layout

## 5. Legend

`legend(doc)` is derived, never authored by hand. It lists what this document uses:

- **Marks:** the in, out and control terminal marks, junction dots, and the `+` / `−` edges if
  signals are present.
- **Colours:** each categorical slot used by a card or wire, with its category name when the
  notation or the document names it.
- **Glyphs:** each glyph used, with its title and meaning.
- **Signal shapes:** the clock waveforms and the binary or continuous indicators used.
- **Sections:** each section preset used (disk, pipe...).

In the editor it is a panel. In a picture it is a block placed beside the drawing
(`render({legend: true})`), never over it.

A document may rename a category (`document.legend.names: {C3: "Refunds"}`) or hide an entry.
It may not add an entry for something it does not use.

## 6. What is built first

1. Tokens, radius, elevation shadows, spacing (the `schematic` notation's values).
2. The notation core, with glyphs and terminals; symbols generated from it; the terminal
   tables removed; pins and leads from terminals.
3. Type roles, sentence-case titles, Markdown body, subtitle, narration.
4. Legend.
5. The `logic` notation (and, or, not, nand, nor, xor, buffer) and an example. It proves a
   domain can bring its own shapes, terminals and colours without code.

Each step is judged by the layout review (`skills/layout-review`) on its pictures, and by
contrast (`scripts/contrast_audit.py`).

## As built (2026-09-25)

| Part | Where | Test |
| --- | --- | --- |
| Notations, tokens, glyphs and terminals, the `logic` notation | `src/03-notation-core.js` (no DOM; the server loads it) | `tests/notation_qa.py` |
| Symbols generated from the notation; pins, leads, terminal points | `src/10-model.js` (`installNotationSymbols`), `src/30-canvas.js`, `src/06-attachment-core.js` | `tests/notation_qa.py`, `tests/boundary_attachment_qa.py` |
| Radius offset from inside; elevation shadows; recess and raised bevels | `src/55-render.js` | `tests/notation_qa.py`, `tests/sections_qa.py` |
| Type roles, sentence case, subtitle, Markdown body | `src/55-render.js`, `styles/app.css` | `tests/typography_qa.py` |
| Narration track | `src/66-narration.js`; pictures in `src/75-persistence.js` | `tests/typography_qa.py` |
| Legend | `src/67-legend.js` | `tests/legend_qa.py`, `tests/server_render_qa.py` |
| Crossings drawn as hops | `src/55-render.js`, `src/40-routing.js` | `tests/wire_crossing_qa.py` |

Notes from building it:
- A glyph's box leaves room at the card's foot for its title, and one line more for a
  subtitle. The layout engine uses the same formula (`glyphBox`, `terminalOffset`), so a
  laid-out wire is straight.
- An unplaced point on a card with a glyph sits on its own terminal's line, so every lead is
  straight. A point moved by hand gets a lead with one dogleg.
- The layered engine levels a card by the terminals its wires use, not by card centres. It
  widens a gap for the wires crossing it, and levels a source card with its successors.
- Resolving a notation registers its terminal points before any component is read. The data
  core resolves it while normalising, so a file, the server and the editor agree.
- An explicit `set` before the simulation's first step replaces a lever's declared starting
  value. Found by the half adder's truth table.

## Open

- A card with more terminals than fit on one side: spread evenly (now), or grow the card.
- Right-to-left scripts in narration.
- Importing a notation from an existing library (a draw.io shape set, a KiCad symbol library)
  as a converter, never at render time.
