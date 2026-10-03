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

**A card's title and subtitle are one block**, laid out at the size they are drawn at (after
the on-screen clamp, so the block is laid out again when the zoom changes):
- the title wraps at word breaks to at most two lines within the card's text width
  (`w - 12 - 2 × section inset`); a line still too long ends in an ellipsis
- the subtitle is one line, cut the same way, and its top sits `space.textGap` (3) under the
  title's last line
- the block's foot stays where a lone title sits, or sits lower, down to the inner edge, when
  that is what makes it fit; under a container's glyph or below the body the block grows down
  from there instead
- inside a card the block stays below the glyph (its foot plus 2) and inside the inner edge;
  when it cannot, the least important line goes first: the subtitle is hidden
  (`data-lod="hidden"`), then the title is cut to one line
- a lone title (no subtitle) that needs a second line gets room for both under the glyph: the
  glyph shrinks for it (`glyphBox`), keeping its aspect and never below 60% of its size;
  whether the title needs the line is judged from a per-character width table, so the layout
  engine and the renderer agree
- at a screen scale of 0.25 or less, a title that still runs into its glyph is hidden
  (`data-lod="hidden"`)
- a cut line keeps the full text in a `<title>` child and sets `data-truncated`; the status chip
  does not move, and a waits-on caption follows the block's real foot
- a title drawn outside its card (outside label mode, under the card) is not held to the card's
  width: it stays on one line, uncut, and only its subtitle's place follows `space.textGap`
- the SVG export (`scripts/export_svg.py`) draws through the same code, so it wraps and cuts the
  same way

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
- **Statuses:** each status a visible card or wire names in `config.status`, in the order the
  notation's `statuses` list declares them, with its title and meaning. A status is validated
  against that list, so the legend lists only declared ones; its sample is a small rounded chip,
  dashed when the status declares `outline: dashed`, as the card's chip and outline are drawn.

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
| Symbols generated from the notation; pins, leads, terminal points | `src/10-model.js` (`installNotationSymbols`, `symbolOf`), `src/30-canvas.js`, `src/05-data-core.js` (`templatePorts`: a gate's terminals are its template ports) | `tests/notation_qa.py`, `tests/boundary_attachment_qa.py`, `tests/ports_panel_qa.py` |
| Radius offset from inside; elevation shadows; recess and raised bevels | `src/55-render.js` | `tests/notation_qa.py`, `tests/sections_qa.py` |
| Type roles, sentence case, subtitle, Markdown body | `src/55-render.js`, `styles/app.css` | `tests/typography_qa.py` |
| Title and subtitle as one block inside the card | `src/55-render.js` (`fitComponentLabels`), `space.textGap` in `src/03-notation-core.js` | `tests/card_text_fit_qa.py` |
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

## Domain notation: work-engine

The Work Engine gap map is drawn in its own notation, `work-engine`. It extends `schematic`, so
every built-in glyph and token still applies, and it adds kinds for records, surfaces and work
items, so a reader tells a store from a page from a piece of work by its shape.

- The notation lives in `data/work-engine.notation.json`.
- A document uses it with `"notation": "work-engine"` and carries the file's content unchanged
  as `references[0]`: `{id: "notation-work-engine", kind: "notation", label: "Work Engine",
  data: ...}`. `examples/work-engine/notation.sov` is such a document, with one card per glyph.
- Glyph ids carry the prefix `we-`, because the data core reads a component whose symbol is
  `port` as a point.
- Every glyph has an `in` terminal at `[28, 32]` facing left and an `out` terminal at `[68, 32]`
  facing right, as `act` has, so its body sits between x 28 and x 68.
- `tests/work_engine_notation_qa.py` checks the file, the example, the resolved glyphs, the
  statuses and the legend.

**Glyphs**

| Id | Title | Family | Drawn as | Meaning |
| --- | --- | --- | --- | --- |
| `we-record` | Record | record | a cylinder | A store the work engine keeps its facts in, such as a table, a file or a log. |
| `we-surface` | Surface | surface | a window with a title bar | A place a person or an agent reads or acts on the work, such as a page, a panel or a command. |
| `we-migration` | Migration | work | a sheet with a folded corner and an arrow to the right | Work that moves data or behaviour from one home to another. |
| `we-port` | Port | work | the sheet with two opposed arrows | Work that connects one part to another so each can reach the other. |
| `we-refactor` | Refactor | work | the sheet with two curved arrows in a circle | Work that reshapes existing code without changing what it does. |
| `we-specification` | Specification | work | the sheet with three text lines | Work that writes down what something must do before it is built. |

The four work items share the sheet, so they read as one kind, and differ by the mark inside it.

**Categories.** `C1` Record, `C2` Surface, `C3` Work item. A card's `config.colorSlot` 6, 7 and
8 are those slots, and the legend names them.

**Statuses.** The notation declares, in order, the values a document drawn in it may give
`config.status`. Each is `{id, title, meaning, outline: solid | dashed, opacity}`: `outline` is
how the card's border is drawn, and `opacity`, when present, is how strongly the card is drawn.
A dashed outline marks a thing that is not built.

| Id | Title | Outline | Opacity | Meaning |
| --- | --- | --- | --- | --- |
| `exists` | Exists | solid | | Built and in use today. |
| `partial` | Partial | solid | | Built in part; some of what it must do is still missing. |
| `missing` | Missing | dashed | 0.55 | Needed by the work engine and not built yet. |
| `proposed` | Proposed | dashed | | Planned work that nobody has started. |

**A status on a card or a wire.** A Component or a Wire names one of these in `config.status`,
and lists what it waits on in `config.waitsOn` (people, rules and decisions; DATA-FORMATS.md
"Status and waits-on"). The data core validates a status against the statuses of the document's
resolved notation, never against a list of its own: a value the notation does not declare is
`STATUS_UNKNOWN`, and any value in a notation that declares no statuses (such as `schematic`) is
`STATUS_UNDECLARED`. Create and update refuse them; loading reports them. The renderer draws a
card's status as a chip in its top-right corner, 6 in from both edges, holding the status title in
the caption role at its base size; a status with `outline: dashed` dashes the card's outline
(`6 4`), and one with `opacity` draws the card at that opacity. What a card waits on is a caption
under it, in the muted ink: "Waits on Bdo, rule R-29, decision D1". A Wire's status title and
what it waits on follow its label in its caption, and a dashed status dashes its line. The legend
lists each status used, in the notation's order (section 5). `examples/work-engine/status.sov`
shows all four statuses; `tests/status_waits_on_qa.py` checks them.

## Open

- A card with more terminals than fit on one side: spread evenly (now), or grow the card.
- Right-to-left scripts in narration.
- Importing a notation from an existing library (a draw.io shape set, a KiCad symbol library)
  as a converter, never at render time.
