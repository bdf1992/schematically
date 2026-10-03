# A spatial board for the Work Engine: what atlas-vtt's pieces map to

Written 2026-10-02 for task `schematically-spatial-board-study-from-atlas-vtt`. The question:
Bdo wants the work map navigable at large scale, with agents and tasks as pieces carrying status
and metadata. atlas-vtt is a virtual tabletop whose whole job is a large zoomable board of pieces
with badges and pinned notes, so its pieces are a checklist for ours. This study maps each of its
pieces onto what Schematically has on dev, builds one small board from live workstation data,
and measures how the current renderer holds up at 100, 1000 and 4000 pieces.

## Sources

Clean room: atlas-vtt is AGPL-3.0. It was read for what its pieces do, from its README, its
CHANGELOG and its repository metadata, through `gh api`, on 2026-10-02. No source file of it was
opened, and nothing of it is in this repository.

| Source | Where | What it gave |
| --- | --- | --- |
| atlas-vtt README | `gh api repos/ByteMirror/atlas-vtt/readme` (github.com/ByteMirror/atlas-vtt) | the feature list: maps and grids, tokens, fog and player view, note pins, widgets, scenes |
| atlas-vtt CHANGELOG.md | `gh api repos/ByteMirror/atlas-vtt/contents/CHANGELOG.md` | how conditions, pins, widgets, snapshots and the player view behave, release by release |
| atlas-vtt package.json, dependencies only | `gh api repos/ByteMirror/atlas-vtt/contents/package.json` | the renderer: `pixi.js` ^8.21, `pixi-viewport` ^6.0.3 (WebGL scene graph with a pan/zoom viewport) |
| atlas-vtt repository record | `gh api repos/ByteMirror/atlas-vtt` | licence AGPL-3.0, description, last push 2026-10-02 |
| The scale gate | `spikes/glsp-projection/evidence/_ref-SCALE-GATE.md`, `_ref-scale-benchmark-results.json`, `_ref-scale_benchmark.py` | F0/F1/F2, the budgets in section 4, the decision rule in section 7, the frame-timing method |
| Groups, layouts, statuses | `SECTION-MODEL.md` "Groups (reading only)", `LAYOUT-MODEL.md` "As built: layouts", `formats/schematic.document.schema.json` `$defs.status` and `$defs.waitsOn`, `src/55-render.js` | what dev can already say |

What the sources say, kept apart from what I take from them:

- Said by atlas-vtt: tokens are pieces you move and resize on a map, with a nameplate, resource
  bars and number badges; they can be hidden from players. Conditions show as badges on a token,
  with a hover card naming them, may carry a number (Frightened 2), and can be applied to several
  tokens at once. A statblock is a linked creature note, previewed by holding Ctrl over a token
  and shown side by side on a DM screen. A note pin links a Markdown note (or a heading in it, or
  another map) to a location, and opens it in a floating panel on the map. Fog is revealed as
  players explore. The player view is a separate window that shows the map without GM information
  (hidden tokens, selection, handles), copies a new frame only when the map changes, and shows the
  initiative tracker and widgets of its own map. Widgets are counters, timers and clocks that float
  on their own cards above the map and can be shared across a collection's scenes. A scene is a
  map image with a grid and its pieces, saved as an `.atlasmap` file, switched with a keyboard map
  switcher, and saved under named snapshots that can be restored.
- My inference: the board's value is that the reader never leaves it. Status, what something
  waits on and the record behind a piece are on or one hover from the piece. That is the bar the
  table below holds Schematically to.

## The pieces

Gap ids B01 to B07 are new; each has an entry in the `docs/workengine/gaps.json` format under
"Gap entries" below. The board slice in `board-sample.sov` uses only what the second column says
exists.

| atlas-vtt piece | What it does there | Schematically on dev | Gap |
| --- | --- | --- | --- |
| token | A movable piece standing for a character or creature: an image sized in grid cells, a nameplate, resource bars, number badges, hidden from players when the GM wants | A Component: a task is a card with `config.label`, `config.subtitle`, `config.status` and `x, y` (what `ws schematically project` writes). A session is a card too (`board_pins.mjs`), but the Work Engine notation has no session kind, so a session is drawn as an `act` card with its state in the subtitle text | B01 |
| conditions | Badges on the token, with a hover card naming them; a badge can carry a number; one condition can go on many tokens at once | `config.status`: one chip per card from the notation's `statuses` (`src/55-render.js` draws the chip, dashed outline and opacity); `config.waitsOn` draws a "Waits on ..." caption under the card. One status per card; no second badge, no count, no hover card | B02 |
| statblock | The record behind a token (a creature note), previewed on hover and shown in full on a DM screen | A reference: `references[]` entries keep a `target` (`src/05-data-core.js` reference normalizer), and the projection keeps each field's basis (`meta.basis.<id>.<field>.from`, declared or derived). Nothing shows the basis or a record link from a card: the Inspector (`src/50-selection.js`) lists objects, not their source record | B03 |
| note pin | A Markdown note (or a heading, or another map) pinned to a place and read or edited in a floating panel there | None. Dev's reference kinds are `notation` and `scenario`; no kind holds anchored text and nothing draws a reference that has a target. The slice uses a caption instead: a Point whose outside label is the waiting text, wired to the card's top port with the caption "waits on". "Pin another map" has a partial match: a Component's own canvas (`canvas:component:<id>`) | B04 |
| fog | Areas stay dark for players until the GM reveals them | Per-entity editor state only: `entity.editor.hidden` (`src/15-editor-kernel.js`) hides one Component and its children for everyone. Nothing hides a region, and nothing hides by audience | B05 |
| player view | A second, read-only window on the same map for another audience: hides GM-only pieces and chrome, follows the live map | A layout view: `document.layout.views[id]` stores `{name, audience, nodes, routes}` (`src/08-layout-core.js`), but `audience` is stored and listed only; it filters nothing. A picture export (`scripts/export_svg.py`) is read-only but does not follow the document | B06 |
| widgets | Counters, timers and clocks on their own cards floating above the map, optionally shared across scenes | The legend block (`src/67-legend.js`) is the one screen-anchored card; the sim clock and `schematic.run.*` run records (start, step, settle, trace, replay) hold time and counts for a running circuit. Nothing counts the board's own pieces (tasks by status, live sessions) on screen | B07 |
| scenes | One map with its grid and pieces, saved as a file; a switcher between maps; named snapshots to restore | Exists. A `.sov` document is the scene; `layout.views` are alternative arrangements of it (the toolbar's layout menu switches between them); checkpoints (`meta.checkpoints`, `checkpointStore` in `src/15-editor-kernel.js`) are named states to restore. Switching between documents is the workstation's side (`ws schematically project` per mission) | none |

## The slice

`docs/workengine/board-sample.sov` is one result of this pipeline, run 2026-10-02:

1. `ws schematically project schematically-schematically-maps-the-work-engine-s --out %TEMP%/mission.sov`,
   with `WS_SCHEMATICALLY_CHECKOUT` set to this worktree (the canonical checkout has no
   `data/work-engine.notation.json` yet and refuses with `NOTATION_MISSING`): 12 task cards with
   status chips, one case group of 11 members, 5 "depends on" Wires.
2. `ws session list --json` to `%TEMP%/sessions.json`.
3. `node scripts/board_pins.mjs %TEMP%/mission.sov %TEMP%/sessions.json --neutral --out docs/workengine/board-sample.sov`:
   one session piece (the one live session bound to a task in the mission: this study's own
   contract engineer, `s01`, wired "works on" to `t10`) and one pinned note (the only card with
   `waitsOn`, `t10`). Task ids became `t01` to `t12`, the session id `s01`; titles are kept; the
   per-field basis paths became `tasks/<tNN>.json#<field>` and the workstation revision was
   dropped. The mission and case ids are kept, as names of the board, not of a task or session.

`node scripts/validate_sov.mjs docs/workengine/board-sample.sov` passes (15 components, 7 wires),
and `python scripts/board_scale_probe.py --view docs/workengine/board-sample.sov --shot <png>`
draws all 15 (it prints any Component that was not drawn).

What doing it showed:

- A live session is not the same as a session with a process. A contract engineer runs as a
  subagent and has `process: absent` and `pid: null` while it works, so `board_pins.mjs` reads
  "live" as not ended and not stale. Filtering on `process: live` would have shown no agent at
  work on this mission.
- The pinned note repeats what the card already says: dev draws `config.waitsOn` as a "Waits on
  ..." caption under the card (`src/55-render.js`), so the waiting text is on the board twice.
  A note kind (B04) should carry what the card cannot (a longer text, a link), not restate a field.
- A wire into a card's left port from a piece placed to its right routes around the card, so
  session pieces go in a column left of the board and notes in a column right of it, wired to the
  card's top port. A board that adds pieces next to placed cards needs to know which side each port
  is on; that is placement knowledge `board_pins.mjs` hard-codes.
- A task with no title is drawn under its id (`label` basis `derived`, reason "title absent").
  After `--neutral` that card reads `t09`, which is right for a sample and useless on a real board.

## Scale

`python scripts/board_scale_probe.py` builds boards in the sample's shape (statuses cycling
through the four notation statuses, every tenth card waiting on someone, 20 cards to a group, one
"depends on" Wire per piece after the first, the notation the sample carries), opens each in
headless Chromium the way `tests/performance_regression_qa.py` does (index.html as page content,
the document through `SovSchematicAPI.document.replace`), and records three numbers per size into
`docs/workengine/board-scale.json`. The frame wait is the reference benchmark's (two animation
frames), with the clock started before the camera change. Pan and zoom are medians of five.

Measured 2026-10-02 on this Windows 11 host, F0 (the SVG DOM renderer on dev), headless Chromium
from Playwright:

| Pieces | Wires | Groups | SVG elements | Cold render ms | Pan frame ms | Zoom frame ms |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 99 | 5 | 4,524 | 2,420 | 33.3 | 49.9 |
| 1000 | 999 | 50 | 45,755 | 245,697 | 1,237 | 1,614 |
| 4000 | 3,999 | 200 | 184,752 | 5,760,638 (96 min) | 14,562 | 28,130 |

How to read the frame numbers: the wait is two animation frames, and this host's headless
Chromium paces them at 60 Hz, so 33.3 ms is the floor of the method (two 16.7 ms intervals), not
work. At 100 pieces the pan frame is at that floor, so it fits one frame; the zoom frame takes one
interval more than that.

Where the cold time goes, from the same probe with parts left out (`--no-wires`, `--no-groups`,
written to `%TEMP%`, not to `board-scale.json`):

| Pieces | Board | Cold ms | Pan frame ms | Zoom frame ms |
| ---: | --- | ---: | ---: | ---: |
| 300 | cards, groups, wires | 17,666 | 99.8 | 167.9 |
| 300 | cards and wires, no groups | 16,205 | 80.6 | 129.1 |
| 300 | cards and groups, no wires | 683 | 33.9 | 65.0 |
| 300 | cards only | 682 | 34.0 | 51.7 |
| 1000 | cards and groups, no wires | 2,402 | 83.3 | 179.3 |
| 4000 | cards and groups, no wires | 19,670 | 334.3 | 737.6 |

### Against the scale gate

The gate's budgets (`_ref-SCALE-GATE.md` section 4, proposed): cold load of the full corpus at
most 10 s, a pan or zoom frame at most 16.7 ms at any zoom band.

- **F0, SVG today, fails at 1000 pieces and fails far worse at 4000.** At 4000 the cold render is
  576 times the budget, the pan frame about 870 times and the zoom frame about 1,680 times. Cold
  time grows as about n^2 to n^2.3 (100 to 1000: x101; 1000 to 4000: x23) and the frame times as
  n^1.8 to n^2.1, so no constant-factor fix to F0 reaches 4000.
- **Most of the cold time is the Wires, not the drawing.** At 300 pieces the Wires take the cold
  render from 0.7 s to 17.7 s. That cost is routing, which is the data side of the gate (section 8
  item 4, "spatial index scoped to each wire's bounding box"), and no frontend removes it. The
  board needs that routing index whichever frontend draws it.
- **Cards alone still put F0 out.** With no Wires, 4000 cards and 200 groups load in 19.7 s (twice
  the budget) and pan in 334 ms and zoom in 738 ms per frame, 20 and 44 times the budget. Without
  Wires the frame cost grows about linearly (1000 to 4000: x4.0 pan, x4.1 zoom): it is the cost of
  a browser restyling and painting 105,000 SVG elements on every camera change.

**What the board needs at 4000 pieces: F1, Canvas2D with declared LOD bands, plus the routing
index on the data side.** My reasoning, from the numbers and the gate's own rules:

1. The gate's decision rule (section 7) is the cheapest pairing that passes, not the fastest. F1
   is cheaper than F2: no shader code, no WebGL context, and it keeps the standalone `index.html`.
2. What F1 must draw in one frame at 4000 pieces is bounded by its LOD bands (section 3). At the
   overview zoom the 4000 cards are a few pixels each, so text, ports and captions drop out and a
   frame is about 4,000 rectangles filled in four batches (one per status) and one stroked path of
   about 4,000 wires. Zoomed in, the viewport query returns only the visible cards. That is two
   orders of magnitude below K=96 (about 240,000 components and 553,000 wires), which is the load
   F2 instancing exists for.
3. atlas-vtt draws its board with PixiJS on WebGL (F2's family), but its pieces are images and
   textures on a map image; a Work Engine board has no images, so the reason it needs WebGL does
   not carry over.

That is an inference, not a measurement: this probe measured F0 only. The step that would settle it
is the same probe pointed at an F1 spike, and the rule for the result is the gate's: if F1 holds
16.7 ms at 4000 pieces, stop there; if it does not, F2 is next.

## Gap entries

In the format of `docs/workengine/gaps.json`.

```json
[
  {
    "id": "B01",
    "capability": "A session (an agent at work) has no kind and no states of its own in the Work Engine notation, so a session piece cannot say whether it is live, has no process of its own, is stale or has ended.",
    "tried": "board_pins.mjs adds one card per live session bound to a task on the board, wired 'works on' to the task.",
    "workaround": "An act card (a circuit symbol) with the label '<seat> session' and the state as subtitle text ('live · subagent'); no status chip, because the notation's statuses (exists, partial, missing, proposed) describe built things, not running ones.",
    "severity": "awkward",
    "source_files": ["data/work-engine.notation.json", "NOTATION-MODEL.md"],
    "task_objective": "Add a session glyph and a second status set for running things (live, idle, stale, ended) to the Work Engine notation, so a session piece draws its state as a chip the way a task does."
  },
  {
    "id": "B02",
    "capability": "A Component carries one status chip; it cannot carry several badges (a status, a rung, a claim, a count) or a hover card naming them.",
    "tried": "Read config.status and config.waitsOn as drawn by src/55-render.js: one chip top right, one 'Waits on' caption under the card.",
    "workaround": "One status chip; everything else goes into the subtitle text or the waitsOn caption.",
    "severity": "awkward",
    "source_files": ["src/55-render.js", "src/05-data-core.js", "formats/schematic.document.schema.json"],
    "task_objective": "Allow an optional config.badges list of {id, label, count?} drawn as small chips along the card's top edge after the status chip, with the full list in the card's tooltip, validated by the data core."
  },
  {
    "id": "B03",
    "capability": "A piece cannot point at the record behind it (its task file, its pull request) so that a reader can open it from the board; the projection's per-field basis sits in meta and nothing shows it.",
    "tried": "ws schematically project writes meta.basis.<id>.<field> = {basis, from, raw}; looked for anything in the editor that reads it, and for a reference kind that links a Component to an outside record.",
    "workaround": "None on the board; the basis is only in the file.",
    "severity": "awkward",
    "source_files": ["src/50-selection.js", "src/05-data-core.js", "formats/schematic.document.schema.json"],
    "task_objective": "Show a selected Component's source in the Inspector: its config.source {label, href} when present, else the document's meta.basis entries for that id (field, basis, from), read-only."
  },
  {
    "id": "B04",
    "capability": "There is no note anchored to a Component: no reference kind holds text with a target, and nothing draws a reference that has one.",
    "tried": "Looked for a reference kind for anchored text (references carry notation and scenario only) and for any drawing of references[].target.",
    "workaround": "A Point whose outside label is the note text, placed beside the Component and wired to its top port with the caption 'waits on' (board_pins.mjs). The text repeats the card's own waitsOn caption, the Point is a model object that takes part in the graph, and the note does not move with its card.",
    "severity": "awkward",
    "source_files": ["src/05-data-core.js", "src/55-render.js", "formats/schematic.document.schema.json"],
    "task_objective": "Add a reference kind note {target: componentId, data: {text, offset}} that the renderer draws as a pin beside its target, follows the target when it moves, and opens its Markdown-lite text on click, with validation that the target exists."
  },
  {
    "id": "B05",
    "capability": "Nothing hides part of the board from one audience; hiding is per entity and for every reader (entity.editor.hidden).",
    "tried": "Read entityEditorState in src/15-editor-kernel.js and the layout views' audience field in src/08-layout-core.js.",
    "workaround": "None; a closed case or a finished task stays on the board for everyone.",
    "severity": "awkward",
    "source_files": ["src/08-layout-core.js", "src/58-layouts.js", "LAYOUT-MODEL.md"],
    "task_objective": "Let a layout view list hidden Component ids (view.hidden), so showing that view hides them and the Wires that end on them, with a test that the main view still shows them."
  },
  {
    "id": "B06",
    "capability": "There is no read-only view for another audience that follows the live document; a layout view's audience is stored and listed but filters nothing, and a picture export does not follow edits.",
    "tried": "Searched src and mcp for audience: it appears only where src/08-layout-core.js creates and lists views.",
    "workaround": "Export a picture (scripts/export_svg.py) and send it again after every change.",
    "severity": "awkward",
    "source_files": ["src/58-layouts.js", "src/75-persistence.js", "src/85-api.js"],
    "task_objective": "Open a document read-only in a named view (for example ?view=<id>&readonly=1): no editing chrome, B05's hidden ids applied, and the document reloaded when the file changes."
  },
  {
    "id": "B07",
    "capability": "No screen-anchored card counts the board's own pieces (tasks by status, live sessions, waiting cards); the legend is the only overlay and it names kinds, not counts.",
    "tried": "Read src/67-legend.js (the derived legend) and the sim clock and schematic.run.* run records, which count a running circuit, not the document's pieces.",
    "workaround": "Count by reading the file.",
    "severity": "awkward",
    "source_files": ["src/67-legend.js", "src/55-render.js"],
    "task_objective": "Give the derived legend an optional count per status of the active notation (and per glyph kind), drawn in the editor and in export_svg.py --legend, with a test on board-sample.sov."
  }
]
```
