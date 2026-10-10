# Work Engine sample: what the model could not say

`sample.sov` draws a small part of the Work Engine map from `gapmap.json`
(`control\sketchbooks\ep-CatalystCoreV2-sandbox-8d673072\gapmap.json` on the workstation, read
2026-09-27): five records, three surfaces, one migration and one port. It was written by hand
with `skills/author-offline`, validated with `node scripts/validate_sov.mjs` and rendered with
`python scripts/export_svg.py` to `sample.svg`. `check_sample.py` checks the files.
`gaps.json` holds the same gaps as data.

Eleven gaps: one blocks authoring the full map, nine make it awkward, and G07 is closed.

| Id | Capability missing or awkward | What the sample uses instead | Severity | Files a fix would change |
| --- | --- | --- | --- | --- |
| G01 | A status (exists, partial, missing, proposed) as data | Subtitle text such as `Record · partial` | awkward | `src/05-data-core.js`, `formats/schematic.document.schema.json`, `src/55-render.js`, `src/67-legend.js` |
| G02 | A domain kind (record, surface, work item) | `hold` for records, `act` for surfaces, colour slots 6/7/8 | awkward | `src/03-notation-core.js`, `src/00-state.js`, `NOTATION-MODEL.md` |
| G03 | A legend in the headless export | None; legend names are in the file but not the picture | awkward | `scripts/export_svg.py`, `src/75-persistence.js`, `src/67-legend.js` |
| G04 | A group that collects cards without being a boundary | Planes named Records and Surfaces; every crossing relation is cut into segments through boundary Points | blocks | `src/05-data-core.js`, `src/30-canvas.js`, `formats/schematic.document.schema.json`, `SECTION-MODEL.md` |
| G05 | A work item (migration) kind with a proposed state | `gate` card, colour slot 8, subtitle `Migration · proposed` | awkward | `src/00-state.js`, `src/03-notation-core.js`, `formats/schematic.document.schema.json` |
| G06 | What a thing waits on (person, rule, decision) | Body text `Waits on Bdo amending rule R-29 (decision D1)` | awkward | `src/05-data-core.js`, `formats/schematic.document.schema.json`, `src/55-render.js` |
| G07 | Named channels (video, event, narration) crossing a boundary Point | **closed**: `rec-port-in` and `sur-port-out` declare `self: {channels: [video, event, narration]}`; `tracks-out`/`tracks-in` no longer carry `main` | closed | `src/06-attachment-core.js`, `src/05-data-core.js`, `src/07-graph-core.js`, `ATTACHMENT-POINT-MODEL.md` |
| G08 | A port as a named thing | A `one-way` card hosted inline on the middle segment; no body drawn, label overlaps the caption | awkward | `src/05-data-core.js`, `src/55-render.js` |
| G09 | One caption per relation across segments | The caption repeated on every segment; two collide at a junction | awkward | `src/55-render.js`, `src/40-routing.js` |
| G10 | Labels fitted to cards in the export | Hand-sized cards; two titles still run past their card, one caption sits under a card | awkward | `src/55-render.js`, `scripts/export_svg.py` |
| G11 | Offline layout and import from a data file | Every coordinate and boundary `t` computed by hand | awkward | `src/08-layout-core.js`, `scripts/export_svg.py`, `skills/author-offline/SKILL.md` |

## What blocks the full map (38 records, 12 surfaces)

One gap still blocks it, because the model cannot hold what the map is meant to say:

- **G04, groups are boundaries.** In the full map most relations run from a record to a surface
  or between groups. Each one has to be cut into three or more Wires through boundary Points, and
  relations that share a boundary Point merge at a junction, so "Surface registration declares
  Delivery broker" stops being one relation in the file. With 50 cards that is both a lot of
  hand work and a loss of meaning.

G07, tracks crossing a boundary, is closed: a boundary Point declares the channels it carries
across the boundary the same way a free Point's `self` does (`resolveSpec` reads it by the
Point's own dimension, not by what hosts it), an undeclared Point still carries only `main`,
and `schematic.graph.query`'s `reach` verb takes an optional `channel` that follows only a Wire
whose two bound ports share it. `sample.sov`'s `rec-port-in` and `sur-port-out` now declare
`video`, `event` and `narration` on `self`, and `tracks-out`/`tracks-in` no longer need `main`.

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

Since 2026-10-05 the map answers the Work Engine notation's questions (NOTATION-MODEL.md "Domain
notation: work-engine"). The document answers its four (what it shows, what it is for, other
readings, smallest slice) with sentences `build_map.py` holds. Each card answers from the gap map's
own fields, as written: a record says what it holds (`meaning`), what in the kernel shows its status
(`evidence`) and which task owns building it (`owner_task`); a surface says what it has authority
over (`authority`) and its `evidence`; a query says which records answer it (`backing`). Groups and
the migration card are asked nothing. `check_map.py` prints `166 answered, 0 open`: 4 for the
document, 3 for each of 38 records, 2 for each of 12 surfaces and 1 for each of 24 queries. No row
is open, because the gap map holds a value for every one of those fields today. A row opens when the
gap map holds no value for it (the field is absent, or empty after trimming): the generator writes
no answer there and never invents one. `node scripts/validate_sov.mjs --concerns
docs/workengine/map.sov` lists the open rows and prints the two counts.

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
- Wire routing, since 2026-10-02: `build_map.py` orders each group's cards by barycentre and gives the
  map two harnesses (`layout.harness`, surfaces to records and records to queries): every wire between
  two groups rides a labelled trunk in the gap and a street in the row gaps, so crossings fall from 665
  on dev to 181, with no wrapped route (`check_map.py --routing`). The harnesses take `lanes: 'port'`
  (wires that leave one port share a lane), so the `backs` trunk carries its 59 wires on 35 lanes, the
  gap it needs is 258, not 402, and QUERY_GAP is 320, not 460; route-overlap is 4, not 23.
- Four backing names in the queries are not records in the gap map (ProcessRecord, Judgement board
  rows, Handoff, Reception), so they have no Wire; `build_map.py` prints them and the document's
  description names them.

## The map runs

Written 2026-10-07. `map.sov` paints each card's status from the gap map and says nothing about
whether a query's status follows from the records behind it. `run_map.py` writes a copy of the map
that the state-space engine (`src/07-state-surface.js`) runs, so the two can be compared. `map.sov`
and `map.svg` are not changed, and no drawing reads the run.

The rule:

- A record is on only when its gap map status is `exists`. `partial` and `missing` are off.
- A query is on only when every record its backing names is on.
- A backing name the gap map holds no record for counts as off.
- A backing name resolves to a record as `build_map.py` resolves it: by `backing_names`, then by the
  record name, then by the part of a record name before its slash (Publication for Publication /
  edition).

In the copy each `we-record` card is an asserted binary signal at 1 or 0. Each `we-specification`
card whose backing names all resolve is a derived binary signal with combine `and` over the `backs`
wires `map.sov` already holds; one with a name that resolves to no record is asserted at 0, because
no wire could carry the missing record. Today that is 8 records on and 30 off, 21 derived queries
and 3 asserted at 0.

The two commands, from the repository root:

- `python docs/workengine/run_map.py --out PATH` writes the copy to PATH, the same bytes every run.
- `python docs/workengine/run_map.py --list` runs the copy (createSimulation, then advance 100 ms)
  and prints one line per query: `agree` or `DISAGREE`, the query id, its painted status, its level
  in the run, and the backing names that are off or are not records. A query disagrees when it is
  painted `exists` and runs at 0, or painted `partial` or `missing` and runs at 1.

The two scenarios stored in the copy (`references`, kind `scenario`):

- `s-as-read`, The gap map as read: advance 100 ms, and every query is at the level the rule gives.
- `s-all-records-exist`, Every record exists: set each of the 30 records that is not `exists` to 1,
  advance 100 ms, and every derived query is at 1 while the three asserted ones stay at 0.

`tests/work_engine_map_run_qa.py` computes the rule from `source/gapmap.json` on its own and checks
the copy, both scenarios, the levels of a run, one query turning on when its off record is set, and
the listing.

The disagreement lines on 2026-10-07, 2 of 24:

```
DISAGREE spec-02-live painted=exists run=0 off=Video track,Event track
DISAGREE spec-23-inbox painted=exists run=0 off=Handoff,Reception
disagreements: 2 of 24
```

Both are queries painted `exists` that the rule turns off. "Stream the current frame and the newest
subtitle lines for one booth" names Video track and Event track, which the gap map marks `partial`.
"List handoffs I must receive and their residuals" names only Handoff and Reception, which the gap
map has no record for. No query painted `partial` or `missing` runs at 1; only one query runs at 1
(spec-20-profile, Session and Event).

## Notes

- The contract names no status for the port "Web booth feeds Recording". The sample marks it
  `partial`. That is an inference: both ends are partial in `gapmap.json`, and its Web booth entry
  says the booth already records video and actions but has no recording id.
- The MCP surface was read (`MCP.md`) but not called; the contract's commands are the validator,
  the exporter and the check. G11's claim that the layered layout would help is therefore untested.
- A caption on a Wire exists (`config.label`), so captions are not a missing feature; how they
  behave on split relations is G09.
