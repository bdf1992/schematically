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

**Scale.** A notation has one document scale, `tokens.scale`: a number from 0.5 to 4, 1 in the
built-in notation. It is the one factor every drawn size follows, the way CSS `rem` sizes follow
one root font size, so the same symbol draws at the same size everywhere in a document and, at
the same scale, across documents. A value outside the range, or one that is not a number, is
refused with `SCALE_INVALID`; it is never clamped.
- `resolve()` applies it once, after flattening `extends`, to the tokens it returns, so a reader
  of `tokens(doc)` draws scaled with no multiplication of its own. The built-in tokens stay as
  written.
- Multiplied: every stroke weight (`stroke.*`), every text role's `size` and its own `min`,
  `space.pin`, `type.screen.max` (so a scaled label is not capped), and the glyph token's `w` and
  `h` (below).
- Not multiplied: `type.screen.min` (the 12 px floor is screen pixels), `radius`, the other
  `space` tokens and `elevation`.
- The renderer multiplies the marks it draws by the same number: the visible port circle
  (radius 5), the terminal mark (12 by 3.2), the junction dot (3.6), the body of a Point that
  carries wires (4, or 4.5 at a junction), the wire hop (6.5) and the chevron. The stylesheet
  multiplies each literal size on a class drawn in a picture by `--scale`.
- Hit targets, grips, halos, handles, marker badges and every routing distance are editor or
  layout quantities and keep their size. A card's stored size is not changed by the scale.
- Some drawn marks keep their size because the geometry they belong to does not scale: the
  section bevel (stroke 4, set `space.bevel` inside the outline), the through mark (a capsule 9
  wide), the net badge and the 8 px endpoint and point tags (literal sizes, not clamps), packets,
  and the outline of a status chip or a badge. A selected or hovered wire keeps its literal width
  (4 and 3.3).
- Direction marks are spaced by length: a directed wire under 20 draws none, one up to 480
  (`ARROW_SPACING`) draws one at the middle of its longest straight segment, and each further 480
  adds one more, at most 4, on the next-longest segments (two share a segment only when it is
  longer than 480). A mark keeps 8 or more from a bend and slides along its segment to clear hops
  and junctions, and a duplex wire puts a forward and a reverse mark side by side at each place.
- A notation chain that declares no `tokens.scale` anywhere (one that does not extend
  `schematic`) is drawn unscaled.

**Glyph.** `tokens.glyph` is the glyph's box, `{w, h}` in world units: 80.64 by 40.4 in the
built-in notation, the box a 112 by 84 card gives a one-line title. The glyph is drawn in that box
on every card that has room for it (§4), so the same symbol is the same size across a document's
cards whatever their sizes. The scale multiplies `w` and `h` (161.28 by 80.8 at scale 2). A `w` or
`h` that is not a finite number above 0 is refused with `GLYPH_SIZE_INVALID`; it is never replaced
by the built-in size. A symbol keeping one size while the box around it grows is the practice of
Graphviz (`fixedsize`, a node sized from its label), ELK's node size constraints and BPMN tools.

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

**The screen clamp is a live-editor aid.** On the canvas every role is held between
`type.screen.min` (12 screen px) and `type.screen.max` (16 times the scale), so text stays
readable while the camera zooms; strokes and marks are world units and follow the camera. A
picture (`render.svg`, `render.png`, `scripts/export_svg.py`) and a snapshot (`file.svg`, File >
Export SVG) are not the screen: both draw every label at its base size times the scale, whatever
the camera zoom, so a file is the same zoomed in or out and its labels keep their proportion to
its strokes. A card's body text is the exception on the canvas: it is drawn as in a picture, at
its base size times the scale in world units, because its line step and position are world units.

**A card's title and subtitle are one block**, laid out at the size they are drawn at (after
the on-screen clamp, so the block is laid out again when the zoom changes):
- the title wraps at word breaks to at most two lines within the card's text width
  (`w - 12 - 2 × section inset`); a line still too long ends in an ellipsis. A line that is one
  word, with no break to wrap at, may use the card's full inner width (`w - 8`, section inset
  ignored) before it is cut
- a title inside its card that would still be cut may shrink below the 12 px screen floor, down
  to 10 px on screen, before an ellipsis is used; only a size that keeps it whole is taken, and
  the text carries `data-shrunk="true"`. Every other label keeps the 12 px floor
- the subtitle is one line, cut the same way, and its top sits `space.textGap` (3) under the
  title's last line
- the block's foot stays where a lone title sits, or sits lower, down to the inner edge, when
  that is what makes it fit; under a container's glyph or below the body the block grows down
  from there instead
- inside a card the block stays below the glyph (its foot plus 2) and inside the inner edge;
  when it cannot, the least important line goes first: the subtitle is hidden
  (`data-lod="hidden"`), then the title is cut to one line
- the glyph is drawn in the glyph token's box (§3) on a card that has room for it. With F the
  token and s = min(F.w / 96, F.h / 64), the drawn glyph is 96s by 64s, and the card has room when
  96s is at most 72% of its width and 64s fits between the feet kept for the text on both sides of
  the axis: 8, plus 1.15 title sizes a title line, plus 1.3 subtitle sizes for a subtitle
  (`glyphRoom`). A shaped card is measured by its inner rectangle
- on a card without room the glyph's box follows the card, as it did before the token:
  `min(72% of the width, 108)` wide and `max(24, min(55% of the height, 70, the height less both
  feet))` high (70% for a glyph whose terminals are its points)
- a lone title (no subtitle) that needs a second line gets room for both under the glyph: on a
  card without room the glyph shrinks for it (`glyphBox`), keeping its aspect and never below 60%
  of its size; whether the title needs the line is judged from a per-character width table, so
  the layout engine and the renderer agree. A card has room for the token only when the two lines
  fit under it without that shrink
- a card that draws a symbol glyph and has no room for it is reported by `layout.metrics` as a
  `glyph-room` finding, naming the card, its size and the size it needs. A container's title
  mark and a card hosted on a wire are not held to it. The finding has no weight in the score.
  Rendering, opening and saving never change a card's stored size; the layered layout grows the
  card (LAYOUT-MODEL.md "What `layered` does")
- at a screen scale of 0.25 or less, a title that still runs into its glyph is hidden
  (`data-lod="hidden"`)
- the editor draws less text as it zooms out, at two levels held in one place, `DETAIL_FLOORS`
  in `src/55-render.js` (`{body: 0.6, secondary: 0.25}`, both screen scales): below `body`, a
  card's body text would draw under 7.2 screen px and is hidden; below `secondary`, the
  deep-overview level, subtitles and wire labels are hidden. Each hidden text carries
  `data-lod="hidden"`, and a hidden subtitle gives its room to the title and stays in the card's
  tooltip
- `secondary` equals the scale at which a title over its glyph is already hidden, so that a
  fitted view keeps its wire labels and subtitles: the review fixture `02-service-circuit`
  fitted to a 1440 wide window sits at 0.459, and at 0.284 on a 768 wide one (measured
  2026-10-09). Both values are first settings
- card titles, group titles and bus labels are not hidden by these levels, nor are port labels,
  end tags or reciprocity marks. A picture is drawn at screen scale 1, so it shows all of it
- a cut line sets `data-truncated`, and the full title (and subtitle) is the card's tooltip: a
  `<title class="card-text-full">` on the card's group, never inside the drawn `<text>`, so a
  text's contents are only what is drawn; the status chip
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
- **Wire kinds:** each wire kind a visible wire names in `config.kind`, in the order the notation's
  `kinds` list declares them, with its title and meaning; its sample is a line 22 long in the
  kind's dash, weight and arrowhead ("Kinds", below).

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
  laid-out wire is straight. Since 2026-10-04 the box is the glyph token's wherever the card has
  room (`glyphRoom`, `tests/glyph_fixed_size_qa.py`).
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
`config.status`. Each is `{id, title, meaning, outline: solid | dashed, opacity, tone: safe |
alert | danger, glyph}`: `outline` is how the card's border is drawn, `opacity`, when present, is
how strongly the card is drawn, `tone` is the status colour its chip is filled with, and `glyph` is
one character drawn before the title, so colour is never the only cue (WCAG 2.2 SC 1.4.1).
A dashed outline marks a thing that is not built.

| Id | Title | Outline | Opacity | Tone | Glyph | Meaning |
| --- | --- | --- | --- | --- | --- | --- |
| `exists` | Exists | solid | | safe | ✓ | Built and in use today. |
| `partial` | Partial | solid | | alert | ◷ | Built in part; some of what it must do is still missing. |
| `missing` | Missing | dashed | 0.55 | danger | ✕ | Needed by the work engine and not built yet. |
| `proposed` | Proposed | dashed | | alert | ◷ | Planned work that nobody has started. |

A status that declares a tone draws its chip as a solid pill filled with that status tone
(`statusTone` in `src/00-state.js`: safe #01B597, alert #C28923, danger #7F1F26 in light and safe #28D4B2,
alert #E3A849, danger #EC5258 in dark, the same in every palette), holding the glyph, a space and the title in #141414 or #FFFFFF, whichever has the higher
contrast on the fill. A status that declares no tone draws its chip as before: an outline in the
card's colour over a faint fill of it, holding the title alone.

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

**Dashed means open or provisional.** A dashed outline in a picture is drawn for two things: a status
that declares `outline: dashed` (needed and not built, or proposed), and a group or plane with
`config.intake: true` (an open region; SECTION-MODEL.md "Borders"). An unplaced card is faded, not
dashed. A group with no intake draws no outline and a soft inset; a plane, a container and a gate
draw solid.

A badge is the chip without a status's meaning: text and a palette colour, no outline, no opacity, no legend entry (DATA-FORMATS.md "Badges").

**Concerns.** The notation asks the four built-in document questions in Work Engine words, under the
same ids and in the same order, and adds five card questions, each asked of the symbols it names
("Concerns" below). It declares none for Wires.

| Id | Applies | Asked of | Title | Question |
| --- | --- | --- | --- | --- |
| `what` | document | | What it shows | Which part of the work engine does this map show? |
| `why` | document | | What it is for | What would someone build or settle from this map? |
| `alternatives` | document | | Other readings | What else describes the same ground, and why read this map? |
| `smaller` | document | | Smallest slice | What is the smallest slice of this map that stands on its own? |
| `meaning` | component | `we-record` | Holds | What does this record hold? |
| `authority` | component | `we-surface` | Authority | What does this surface have authority over? |
| `evidence` | component | `we-record`, `we-surface` | Evidence | What in the kernel shows this status? |
| `owner` | component | `we-record` | Owner | Which task owns building it? |
| `backing` | component | `we-specification` | Backing | Which records answer this query? |

A migration, a port, a refactor and a group are asked nothing. `docs/workengine/map.sov` answers
all of these from the gap map's own fields (`docs/workengine/GAPS.md` "The full map").

**Wire kinds.** The notation declares five, named by what the line means ("Kinds" below gives the
fields and the rules):

| Id | Meaning | Dash | Weight | Arrowhead |
| --- | --- | --- | --- | --- |
| `flow` | Facts are read along it on request. | solid | regular | chevron |
| `stream` | A continuous feed carried as channels. | solid | regular | filled |
| `control` | One side governs the other. | solid | heavy | filled |
| `reference` | One side is listed by the other and nothing moves. | solid | regular | none |
| `proposed` | Planned and not built. | dashed (open) | regular | chevron |

Each of the four relations of `docs/workengine/map.sov` takes one. A record that backs a query is
`flow`: the query reads the record when it is asked. A surface that feeds tracks to the Recording
record is `stream`: a continuous feed of several channels. A surface registered by the Surface
registration record is `reference`: a listing along which nothing moves, so it carries no arrowhead.
The migration that moves records out of the control store is `proposed`: planned work, and its wire
keeps the status `proposed` as well. No wire of the map is `control`: a heavy wire is 4.5 wide and
the lanes of the map's buses sit 6 apart. `tests/work_engine_wire_kinds_qa.py` checks the list and
the map.

### Kinds

A notation declares what its lines and borders are drawn as in one list, `kinds`, for wires and
regions both. An entry is `{id, applies, title, meaning, dash, weight, arrowhead, open}`:

| Field | Values | Absent means |
| --- | --- | --- |
| `id` | a non-empty string | refused |
| `applies` | `wire` or `region` | refused |
| `title`, `meaning` | strings, shown in the legend | the id; no meaning |
| `dash` | `solid` or `dashed`; for a region also `none` (no outline) | refused |
| `weight` | `regular` or `heavy`; a wire kind only | `regular` |
| `arrowhead` | `chevron`, `filled` or `none`; a wire kind only | `chevron` |
| `open` | `true` or `false` | `false` |

The rules, each reported as `KIND_INVALID` naming the notation, the entry and the rule
(`kindFindings` in `src/03-notation-core.js`):

- An unknown key or value is refused; so are `weight` or `arrowhead` on a region kind and `dash:
  none` on a wire kind.
- An id is used once within one `applies`.
- **Dashed is reserved for open.** `dash: dashed` needs `open: true`, and `open: true` needs `dash:
  dashed`: a dashed line or border means open or provisional and nothing else, the same meaning a
  dashed status and an intake region carry.
- A wire kind that is not open differs from every other wire kind that is not open in `weight` or in
  `arrowhead`, so two kinds never draw alike.

An entry with a finding is not admitted: `kindsOf(notation, 'wire' | 'region')` gives the admitted
entries in declared order. `merge` replaces arrays, so `resolve()` joins `kinds` along the `extends`
chain itself: a later notation's entry replaces an earlier notation's entry with the same `applies`
and `id`, in its place.

**Region kinds.** The `schematic` notation declares five, and the renderer reads a region's border
from them by id (SECTION-MODEL.md "Borders"): `group` (dash `none`), `plane`, `container` and `gate`
(`solid`) and `intake` (`dashed`, open). A Component takes no `config.kind`: a region's kind is what
it is.

**Wire kinds.** A Wire names one in `config.kind`. There is no built-in wire kind, so the data core
validates it against the document's resolved notation as it does a status: `KIND_UNDECLARED` when
the notation declares no wire kinds, `KIND_UNKNOWN` when the id is not one of them (the message
lists the declared ids). Create and update refuse them; loading reports them, with every
`KIND_INVALID` finding of the notation. A wire with a kind is drawn as its entry declares
(`renderWires` in `src/55-render.js`), in attributes and inline styles so a picture carries them:

- `dash: dashed` draws the line `6 4`, the one dash pattern a picture uses.
- `weight: heavy` draws the line at twice `tokens.stroke.flow` (two weights at 1 to 2, the narrow and
  wide lines of ISO 128); `regular` is `tokens.stroke.flow`. Selected and hover still multiply it.
- `arrowhead: chevron` is the direction mark every wire draws; `filled` draws each mark as the closed
  triangle through the chevron's three points, filled in the wire's stroke colour; `none` draws no
  mark. How many marks a wire carries and where they sit is not the kind's: it is the spacing rule
  (`ARROW_SPACING`).
- A filled arrowhead is drawn at twice its size on a heavy wire (14 by 10 in place of 7 by 5), so
  the mark scales with the stroke as an SVG marker does by default (`markerUnits: strokeWidth`).
  The chevron is the same size at every weight.

The wire's group carries `data-kind`. A wire with no kind draws as before, and a status with
`outline: dashed` still dashes its wire. The legend lists each wire kind a visible wire uses, after
the statuses, with a sample line in that kind's dash, weight and arrowhead. The `work-engine`
notation declares five ("Domain notation: work-engine"). `tests/wire_kind_qa.py` checks all of this.

### Concerns

A notation declares the questions a schematic drawn in it should answer in one list, `concerns`, for
the document, for Components and for Wires. An entry is `{id, applies, title, question, meaning,
symbols}`:

| Field | Values | Absent means |
| --- | --- | --- |
| `id` | a non-empty string | refused |
| `applies` | `document`, `component` or `wire` | refused |
| `question` | a non-empty string after trimming: what is asked | refused |
| `title` | a string: a short name for the question | the id |
| `meaning` | a string: what a good answer holds | no meaning |
| `symbols` | a non-empty list of symbol ids, each a non-empty string, none repeated; a component concern only | asked of every Component |

The rules, each reported as `CONCERN_INVALID` naming the notation, the entry and the rule
(`concernFindings` in `src/03-notation-core.js`):

- An entry is an object, and a key outside the six is refused.
- `id` and `question` are non-empty strings; `applies` is one of the three; `title` and `meaning`,
  when present, are strings.
- An id is used once within one `applies`.
- `symbols` belongs to a component concern: on a document or a wire concern it is refused. It is a
  non-empty list of non-empty strings with no repeats; an empty list, a repeat, a value that is not
  a string and a value that is not a list are each refused.

**A concern names the symbols it is asked of.** A component concern with `symbols` is asked only of
the Components whose `symbolId` is in the list; one without `symbols` is asked of every Component.
This entry is asked of record cards and of no other card, so a group or a query has no owner row
that nobody could answer:

```json
{"id": "owner", "applies": "component", "symbols": ["we-record"], "title": "Owner", "question": "Which task owns building it?"}
```

A symbol id is not checked against the notation's glyphs: an id no Component uses is asked of
nothing and is not a finding. One function reads the list, `concernsAskedOf` in
`src/05-data-core.js`, and the answer check, the report and `answerConcerns` all ask it.

An entry with a finding is not admitted: `concernsOf(notation, 'document' | 'component' | 'wire')`
gives the admitted entries in declared order. `resolve()` joins `concerns` along the `extends` chain
by the join it uses for `kinds`: a later notation's entry replaces an earlier notation's entry with
the same `applies` and `id`, in its place, and an entry with a new id is added after the ones before.
The later entry replaces the earlier one whole, `symbols` included: a later entry without `symbols`
is asked of every Component, whatever the earlier one named.

**The built-in document concerns.** The `schematic` notation declares four, and every notation that
extends it (`logic`, `work-engine`, a carried one) inherits them; `work-engine` rewords all four
("Domain notation: work-engine"). It declares none for Components and none for Wires.

| Id | Title | Question |
| --- | --- | --- |
| `what` | What it is | What is this a schematic of, in one or two sentences? |
| `why` | Why build it | Why would someone build this or study it? |
| `alternatives` | Alternatives | What are the alternatives, and why this one over the others? |
| `smaller` | Smaller first | Can a smaller version be built first, and what is it? |

**A domain rewords one.** A domain notation asks a built-in question in its own words by declaring an
entry with the same `applies` and `id`. This entry keeps `why` second in the list and changes what is
asked; the other two add a question for every card and one for every wire:

```json
"concerns": [
  {"id": "why", "applies": "document", "title": "Why run it", "question": "Why would the plant run this line?"},
  {"id": "made-by", "applies": "component", "question": "What makes this, and from what?"},
  {"id": "carries", "applies": "wire", "question": "What moves along this, and how much?"}
]
```

**Answers.** A document answers its document concerns in `meta.answers`; a Component and a Wire
answer theirs in `config.answers` (DATA-FORMATS.md "Answers"). The data core validates an answer
against the concerns of the document's resolved notation, never against a list of its own: a key
the notation does not declare is `ANSWER_UNKNOWN`, and any key where the notation declares no concerns
for that `applies` is `ANSWER_UNDECLARED`. A Component's answer to a component concern that is not
asked of its symbol is `ANSWER_UNKNOWN` too, the message listing the ids asked of that symbol, and
the report holds no row for it. A concern with no answer is open. Open is information and
never a finding: `SovSchematicData.concernReport(doc)` lists every declared concern as answered or
open with its question, and `node scripts/validate_sov.mjs --concerns` prints the open ones.
Nothing is drawn for a concern. `tests/concerns_qa.py` checks all of this.

## Open

- A card with more terminals than fit on one side: spread evenly (now), or grow the card.
- Right-to-left scripts in narration.
- Importing a notation from an existing library (a draw.io shape set, a KiCad symbol library)
  as a converter, never at render time.
