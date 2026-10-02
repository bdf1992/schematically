# Work Engine sample: what the model could not say

`sample.sov` draws a small part of the Work Engine map from `gapmap.json`
(`control\sketchbooks\ep-CatalystCoreV2-sandbox-8d673072\gapmap.json` on the workstation, read
2026-09-27): five records, three surfaces, one migration and one port. It was written by hand
with `skills/author-offline`, validated with `node scripts/validate_sov.mjs` and rendered with
`python scripts/export_svg.py` to `sample.svg`. `check_sample.py` checks the files.
`gaps.json` holds the same gaps as data.

Eleven gaps: two block authoring the full map, nine make it awkward.

| Id | Capability missing or awkward | What the sample uses instead | Severity | Files a fix would change |
| --- | --- | --- | --- | --- |
| G01 | A status (exists, partial, missing, proposed) as data | Subtitle text such as `Record · partial` | awkward | `src/05-data-core.js`, `formats/schematic.document.schema.json`, `src/55-render.js`, `src/67-legend.js` |
| G02 | A domain kind (record, surface, work item) | `hold` for records, `act` for surfaces, colour slots 6/7/8 | awkward | `src/03-notation-core.js`, `src/00-state.js`, `NOTATION-MODEL.md` |
| G03 | A legend in the headless export | None; legend names are in the file but not the picture | awkward | `scripts/export_svg.py`, `src/75-persistence.js`, `src/67-legend.js` |
| G04 | A group that collects cards without being a boundary | Planes named Records and Surfaces; every crossing relation is cut into segments through boundary Points | blocks | `src/05-data-core.js`, `src/30-canvas.js`, `formats/schematic.document.schema.json`, `SECTION-MODEL.md` |
| G05 | A work item (migration) kind with a proposed state | `gate` card, colour slot 8, subtitle `Migration · proposed` | awkward | `src/00-state.js`, `src/03-notation-core.js`, `formats/schematic.document.schema.json` |
| G06 | What a thing waits on (person, rule, decision) | Body text `Waits on Bdo amending rule R-29 (decision D1)` | awkward | `src/05-data-core.js`, `formats/schematic.document.schema.json`, `src/55-render.js` |
| G07 | Named channels (video, event, narration) crossing a boundary Point | `main` added to both end ports; track names only in a caption | blocks | `src/06-attachment-core.js`, `src/05-data-core.js`, `ATTACHMENT-POINT-MODEL.md` |
| G08 | A port as a named thing | A `one-way` card hosted inline on the middle segment; no body drawn, label overlaps the caption | awkward | `src/05-data-core.js`, `src/55-render.js` |
| G09 | One caption per relation across segments | The caption repeated on every segment; two collide at a junction | awkward | `src/55-render.js`, `src/40-routing.js` |
| G10 | Labels fitted to cards in the export | Hand-sized cards; two titles still run past their card, one caption sits under a card | awkward | `src/55-render.js`, `scripts/export_svg.py` |
| G11 | Offline layout and import from a data file | Every coordinate and boundary `t` computed by hand | awkward | `src/08-layout-core.js`, `scripts/export_svg.py`, `skills/author-offline/SKILL.md` |

## What blocks the full map (38 records, 12 surfaces)

Two gaps block it, because the model cannot hold what the map is meant to say:

- **G04, groups are boundaries.** In the full map most relations run from a record to a surface
  or between groups. Each one has to be cut into three or more Wires through boundary Points, and
  relations that share a boundary Point merge at a junction, so "Surface registration declares
  Delivery broker" stops being one relation in the file. With 50 cards that is both a lot of
  hand work and a loss of meaning.
- **G07, tracks cannot cross a boundary.** Every surface in `gapmap.json` lists its tracks. A
  typed channel stops at the first boundary Point, so the full map could only name tracks in
  captions, and no query could ask which tracks reach a record.

The other nine make it awkward but not impossible: status, kind, work items, holders and ports
can all be carried as text, colour and borrowed symbols (G01, G02, G05, G06, G08); the picture
needs hand fixing and a spoken legend (G03, G09, G10); and 50 cards laid out by hand is slow
(G11).

## The full map

Written 2026-10-01. `map.sov` is the whole gap map: 38 records, 12 surfaces and 24 screen queries
from `source/gapmap.json`, plus one proposed migration (D1, continuity records to SQLite). It is
generated, not hand-written: `python docs/workengine/build_map.py` writes it, and
`python docs/workengine/check_map.py` checks that every record, surface and query appears once with
the gap map's status, that `node scripts/validate_sov.mjs` passes and that no two cards overlap.
`map.svg` is `python scripts/export_svg.py docs/workengine/map.sov --legend`.

What the map says directly, using features added since the sample:

- Status is data (`config.status` from the Work Engine notation's statuses), so G01 is closed.
- Records, surfaces and queries are `we-record`, `we-surface` and `we-specification` cards from the
  notation carried in `references[]` (G02, G05 closed; the D1 migration is a `we-migration` card).
- Records, surfaces and queries are reading-only groups, and every relation is one direct Wire with
  no boundary Points (G04 closed).
- Open decisions are `waitsOn` entries `{kind: decision, id: D<n>}` (G06 closed). A decision goes
  on each card whose evidence contains one of the phrases in `DECISION_PHRASES` in `build_map.py`;
  that table is my reading of the gap map, not data in it. D13 (federation) and D15 (the fps
  discrepancy) are named by no card's evidence and are attached to none. Only D1 and D2 carry ids
  in the gap map; D3 to D15 are numbered by their position in `open_decisions`.
- A surface's tracks are the channels of its `tracks-out` port (video, event, narration, artifact)
  and Recording's `tracks-in` declares all four, so each "feeds tracks" Wire carries them as
  channels (G07 closed for this map).
- The legend is in the export (`--legend`, G03 closed).

What the full map still works around:

- **G08, a port as a named thing.** The surface-to-Recording ports are Wires between declared
  ports, with no card of their own; their status is not drawn.
- **G09 and G10, captions.** Titles and subtitles fit their cards (the generator sizes each card
  from its title and subtitle). One pair of identical "registered by" captions still overlap
  (Workstation control store and Artifact mirror), which the renderer places, not the generator.
  Moving cards to clear it moved the problem to three other captions.
- **G11, layout.** The generator places the three groups as grids itself. The layered engine
  (`scripts/layout_sov.mjs`) does not place groups and orders columns by wire direction, so records
  with no incoming wire share column 0 with the surfaces and the group regions would overlap.
- Wire routing: with 80 Wires, many routes leave a card on its fixed right-hand terminal and run
  around the grid. The picture is complete but busy; a reader follows a relation in the editor
  more easily than in `map.svg`.
- Four backing names in the queries are not records in the gap map (ProcessRecord, Judgement board
  rows, Handoff, Reception), so they have no Wire; `build_map.py` prints them and the document's
  description names them.

## Notes

- The contract names no status for the port "Web booth feeds Recording". The sample marks it
  `partial`. That is an inference: both ends are partial in `gapmap.json`, and its Web booth entry
  says the booth already records video and actions but has no recording id.
- The MCP surface was read (`MCP.md`) but not called; the contract's commands are the validator,
  the exporter and the check. G11's claim that the layered layout would help is therefore untested.
- A caption on a Wire exists (`config.label`), so captions are not a missing feature; how they
  behave on split relations is G09.
