# Browser API — 0.1

The browser exposes `window.SovSchematicAPI`. UI actions and API mutations share the same document/CRUD core.

## Formats

```js
SovSchematicAPI.formats()
```

Returns the current document, workspace, package, operation, and receipt schema identifiers.

## Whole document

```js
SovSchematicAPI.document.get()
SovSchematicAPI.document.replace(document)
SovSchematicAPI.document.saveRecovery()
SovSchematicAPI.document.restoreRecovery()
```

Recovery is browser-local and separate from normal `.sov` File Save behavior.

## File/package surface

```js
SovSchematicAPI.file.info()
SovSchematicAPI.file.document()
SovSchematicAPI.file.package()
SovSchematicAPI.file.svg({pad: 48})
SovSchematicAPI.file.parse(text)
SovSchematicAPI.file.open(payload, name)
```

`file.package()` returns the same `soveraeign.schematic/package@0.1` payload used by File → Export Package.

`file.svg()` returns standalone SVG with computed theme styles, embedded graphics and content bounds. File → Export SVG and `scripts/export_svg.py` use this same persistence implementation. Every label is drawn at its base size times the document scale (`tokens.scale`, NOTATION-MODEL.md §3) at any camera zoom, as `render.svg()` draws it: the editor's 12 px screen floor is a reading aid for the live canvas and is not in the file.

Component presentation sizes share one admission policy across file loading, browser CRUD, HTTP and MCP: missing width/height default to 112/84, finite numeric values normalize to minima 80/64, and admitted larger sizes have no editor-only ceiling. Plane presets remain 320/220 and a Point retains its fixed footprint. Resize gestures additionally preserve the space required by hosted children.

## CRUD

```js
SovSchematicAPI.list(resource, query)
SovSchematicAPI.get(resource, id)
SovSchematicAPI.create(resource, value)
SovSchematicAPI.update(resource, id, patch)
SovSchematicAPI.delete(resource, id)
SovSchematicAPI.execute(operation)
```

Resources are `component`, `wire`, and `reference`.

Every mutation produces the same revisioned receipt semantics as MCP/HTTP adapters. Wire writes cannot bypass surface/Port reachability.


## Markers

```js
SovSchematicAPI.markers()
```

Returns `{id, severity, message, rule}` for every current `document.get()`/CRUD validation finding, straight from the same check the core runs on write — no separate legality is computed for the view. The renderer draws these as a badge on each carrying element and a total count in the status area.

## Concerns

```js
SovSchematicAPI.concerns.list()                // {notation, rows, answered, open}
SovSchematicAPI.concerns.list({open: true})    // only the open rows; the counts are of every row
SovSchematicAPI.concerns.answer([{concern, target, answer}, ...])   // or answer({answers, ifRevision})
```

`concerns.list` is the data core's `concernReport` over `document.get()`: one row `{concern, applies, target, title, question, answered, answer}` per concern the notation declares for the document (`target: null`), each Component and each Wire (`DATA-FORMATS.md` "Answers"). `concerns.answer` runs the data core's `answerConcerns`: `target` absent or null is the document, else the id of a Component or a Wire; `answer` is a non-empty string to set, `null` to remove. It is all or none and one revision, and goes through the path `apply` uses, so it is one history entry and one undo restores the document. The receipt is `apply`'s with `result.report: {answered, open}`; a refusal (`ANSWER_INVALID`, `ANSWER_TARGET_UNKNOWN`, `ANSWER_UNKNOWN`, `ANSWER_UNDECLARED`, a locked record, a stale revision) changes nothing. MCP serves the same as `schematic.concerns` and `schematic.concerns.answer`, and HTTP as `GET /api/v1/concerns` (`?open=1`; 200) and `POST /api/v1/concerns` (200, 409 for a stale revision, 400 for any other refusal).

## Editor/history API

`window.SovSchematicAPI` additionally exposes `history.list/undo/redo`, `checkpoints.list/create/restore`, semantic selection clipboard helpers, and view appearance/global-rate accessors. MCP exposes history undo/redo and checkpoint list/create/restore for its file-backed document.

### Wave view

```js
SovSchematicAPI.view.waveStyle()            // 'off' | 'string' | 'dots' | 'lanes'
SovSchematicAPI.view.setWaveStyle('string') // {ok: true, waveStyle: 'string'}
```

While a run is live (`clock.*`), the wave view draws each varying source's signal as a faint wave travelling along its wires, from the wire's `a` end, at 120 world units per second. The signal is the run's own spectrum (`sim.spectrum`, six harmonics over the node's last completed period); a source with no period, such as a lever, draws nothing. The four values:

- `off` (the default): nothing is drawn.
- `string`: one 1 px line per wire, displaced across the wire by at most 4 screen px.
- `dots`: 1.5 px dots 3.2 screen px apart, fixed along the wire and displaced across it by the same amount.
- `lanes`: beside the wire, one line per harmonic holding at least 2% of the source's energy (the three largest at most), each wider and more opaque the larger its share.

`setWaveStyle(name)` sets the value, repaints and returns `{ok: true, waveStyle}`. Any other name returns `{ok: false, code: 'WAVE_STYLE_UNKNOWN', message, allowed: ['off', 'string', 'dots', 'lanes']}` and changes nothing.

The setting is the view's. A workspace carries it as `view.waveStyle` (a workspace without the key, or with an unknown value, gives `off`); it is never written to the document, its revision or its fingerprint. Every mark is a child of `#waveLayer`, under the wires, and carries `data-wire-id`; the wires layer is the same for every value, and an exported SVG (`render.svg`, `file.svg`) carries no wave.


### Access axis
Port Connections may carry `access: none | read | write | read-write`. Wire config may carry `forwardOperation` / `reverseOperation: none | read | write`. Direction, access, and authority are independent.


## Attachment IDs

Wire endpoints accept canonical built-in attachment IDs (`self`, `start`, `end`, `left`, `right`, `top`), template-declared attachment IDs, or their document@0.1 compatibility Port IDs at Wire endpoints. Returned Wire records preserve canonical endpoint references in `aAttachment` / `bAttachment` while retaining `aSide` / `bSide` for compatibility.

Wire ends may be free: create with `aAttachment: {kind:'free',x,y}` (and/or `bAttachment`), rebind with `a`/`aSide`, free again with a free attachment. Two bound ends must share an exposed surface.


## Layout buses

```js
SovSchematicAPI.layout.harness({between: ['groupA', 'groupB'], pitch: 6, lanes: 'port', view})   // or harness(['groupA', 'groupB'], {pitch, lanes, view}); lanes: 'port' counts a trunk's and a street's lanes by distinct a ends (default: a lane per wire)
SovSchematicAPI.layout.bus({id, points: [{x, y}, ...], pitch, lanes, label, order}) // or bus(id, {points, ...}); lanes: 'port' gives wires sharing their a end one lane (default: a lane per wire)
SovSchematicAPI.layout.bus({id, remove: true})
SovSchematicAPI.layout.buses({view})                                                // read-only
SovSchematicAPI.layout.route(wireId, {mode: 'bus', buses: [busId, ...]})
```

A bus is a route declared once in a layout; wires name it in their route and ride it on their own lane
(`LAYOUT-MODEL.md` "As built: buses"). Each call runs the shared layout op through `runLayoutOp`, like
`layout.route`, so MCP's `schematic.layout` serves the same ops. A refusal (`BAD_POINTS`, `UNKNOWN_BUS`,
`BUS_GAP`, `GAP_TOO_NARROW`, `STREET_TOO_NARROW`, `BAD_LANES`, ...) comes back with its code and changes nothing. The
harness receipt lists the buses it made and the wires it put on them.

## N-squared layout and port sides per layout

```js
SovSchematicAPI.layout.apply({engine: 'n2', into: 'N2'})            // a new stored layout, shown at once
SovSchematicAPI.layout.apply({engine: 'n2', view: 'n2', scope, gap}) // an existing stored layout; scope: a container; gap: room between cards (96)
```

`n2` puts the cards of a canvas on the diagonal in document order, group by group, and pins each
wire between two of them with one corner on the sender's row and the receiver's column
(`LAYOUT-MODEL.md` "What `n2` does"). It writes a stored layout only and refuses the default layout
with `DEFAULT_LAYOUT`; no component or wire record changes. The receipt is `{view, engine, placed,
order, pitch, frozen, ports, wires: {pinned, forward, feedback, auto}, autoRouted: [{wire, reason,
card?, port?, side?}]}`. MCP's `schematic.layout {op: 'apply', engine: 'n2', into}` is the same op.

The layout also holds the side each wired port is drawn on in it,
`document.layout.views[id].ports[cardId][portId] = {side, t}` (`LAYOUT-MODEL.md` "As built: port
sides per layout"). Every other layout draws the port where the record puts it.

## Runs (state space, slice 1c)

```js
SovSchematicAPI.run.start({inputs, seed, budget})   // every key optional; budget at most 1000000
SovSchematicAPI.run.step(handle)                    // one tick
SovSchematicAPI.run.settle(handle)                  // quiet | oscillating {period, subjects} | budget {left}
SovSchematicAPI.run.trace(handle)                   // the trace in `result`
SovSchematicAPI.run.query(handle, {entity, point, channel, observable})   // point and channel optional
SovSchematicAPI.run.replay(trace)
```

Each returns a run receipt, `soveraeign.schematic/run-receipt@0.1` (`DATA-FORMATS.md`), identical to the one HTTP and
MCP return for the same document and call. Runs live in an in-memory registry beside the document. A start returns
the run's content-derived `runId` and a new `handle`, `<runId>.<n>` with `n` counting this page's starts from 1; step,
settle, trace and query take the handle (`RUN_NOT_FOUND` otherwise, a bare run id included), so two starts with the same
inputs are two runs and never touch each other. A replay is not registered: its receipt has `handle: null`. A run always
starts from the current document (`document.get()`), and replay replays against it. A budget over 1,000,000 is refused
with `INPUT_INVALID` (the engine's `startRun` itself has no cap). A refused receipt's `error.details` carries what the
refusal names (`refusals`, `{tick, left}`, `fields`, `entry`, ...). None of these calls captures history, changes the
document or its revision, or saves recovery. Packs come from the page's `<script type="application/json"
id="sov-packs">`, which `build.py` fills from `data/*.pack.json`; the unbuilt `index.source.html` carries an empty list,
so a start or replay of a document that references a definition there is refused with `PACK_INVALID`, "this page
carries no packs".

The editor fills defaults into a document it opens and advances its revision, so a document opened in the browser
hashes differently from the same file loaded by `node` or the server: a trace recorded against the file does not
replay against the opened document (`REPLAY_KEY_MISMATCH`, `documentHash`).

## Simulation reads: travel and spectrum

```js
SovSchematicAPI.sim.travel()                       // {ok, tickMs, wires: [{id, a, b, forward, reverse, delayTicks, travelMs}]}
SovSchematicAPI.sim.spectrum({fromMs, toMs, stepMs, harmonics, nodes})   // harmonics default 8, nodes default every node with a level
```

Both read the simulation `sim.start` began (`NO_SIMULATION` before it) through the same session as the other `sim.*`
verbs, `schematic.sim.travel` and `schematic.sim.spectrum` over MCP and `POST /api/v1/sim/travel|spectrum` over HTTP,
and give the same JSON on all three. Neither changes the run. `travel` lists every wire in run order with its declared
delay as the run resolved it at start, `delayTicks` (`config.delay` in ticks, else `latencyMs` converted, rounding half
up, never under one tick above 0 ms) and `travelMs = delayTicks * tickMs`; a zero-delay wire reports 0. `spectrum` samples
each node's level every `stepMs` over `[fromMs, toMs)` and gives `{node, periodMs, samples, mean, energy, harmonics:
[{n, amplitude, phase}], rest, parsevalError, reason}`; the model and refusals (`WINDOW_NOT_ELAPSED`, `WINDOW_STEP`,
`WINDOW_TOO_LONG`, `UNKNOWN_NODE`) are in `STATE-SPACE.md`, "Reading a run: travel and spectrum".
