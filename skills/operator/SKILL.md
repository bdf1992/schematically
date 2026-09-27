# SOV Schematic Operator Skill — 0.1

## Purpose

Operate SOV Schematic through its public data, browser API, HTTP, and MCP surfaces.

## Canonical formats

- `.sov` = `soveraeign.schematic/document@0.1`
- `.sovpak` = `soveraeign.schematic/package@0.1`
- browser recovery = `workspace@0.1`
- mutation envelope = `operation@0.1`
- mutation result = `receipt@0.1`

## Browser API

Use `window.SovSchematicAPI`.

Primary operations:
- `list(resource)`
- `get(resource,id)`
- `create(resource,value)`
- `update(resource,id,patch)`
- `delete(resource,id)`
- `document.get()` / `document.replace(doc)`
- `history.list()` / `undo()` / `redo()`
- `checkpoints.list()` / `create(name)` / `restore(id)`
- `selection.copy()` / `paste()` / `duplicate()`
- `view.setAppearance(mode)` / `setGlobalRate(value)`
- `view.legend()` / `view.setLegend(open)` — the legend derived from what the document uses; `render.svg({legend: true})` puts it below a picture
- `view.narration()` / `view.narrate(i)` — the narration track (`document.narration`, scenario steps with `say`); `render.svg({narration: i})` puts line `i` below a picture
- `view.colour()` / `view.setColour({theme, palette})` / `view.paletteAudit()` — the colour engine (default palette `okabe-ito`, colour-blind safe) and the palette measured as realised
- `layout.list()` / `active()` / `switch(id)` / `create({name, from, empty})` / `rename` / `delete` / `setDefault` / `unplaced()` / `move(id, {x, y | dx, dy})` / `place(id, {relation, of, gap})` / `align(ids, {axis})` / `distribute(ids, {axis, gap})` / `route(wireId, {mode, points | via})` / `apply({into, scope})` — arrange for a reader without changing meaning
- `render.svg(options)` / `render.png(options)` (a promise of a data URL) / `layout.metrics()` / `layout.contrast()` — the picture, its measured quality, and WCAG 2.2 contrast of every label and mark against what is painted beneath it
- `clock.play()` / `pause()` / `step()` / `advance(ms)` / `toggle(lever)` / `send(node)` / `resume(parkId, decision)` / `state()` / `inspect(what, id)` — the canvas control plane
- `graph.query(verb, args)` / `graph.verbs()` — read-only: junctions, reach, paths, cycles, order, cut, boundary, untyped, blocked, acl, signals, export
- `sim.set(node, value)` / `at(time, {set|toggle|inject})` / `advance(ms)` / `tick(n)` — time is the driver: clocks, asserted levels and scheduled operations
- `sim.start({handlers, scenarioId})` / `inject(node, {channel, payload, principal})` / `step(n)` / `run({until})` / `resume(parkId, {decision})` / `reconcile(effectKey, {confirmed})` / `inspect(what, id)` / `scenario(id)` / `scenarios()` / `stop()`

Resources in 0.1: `component`, `wire`, `reference`. Ports and Wire Parts remain owned nested records.

## MCP

Discover tools with `tools/list`. CRUD tools share the same transport-neutral data core as the browser and HTTP adapters.

Additional server tools:
- `schematic.history.undo`
- `schematic.history.redo`
- `schematic.checkpoint.list`
- `schematic.checkpoint.create`
- `schematic.checkpoint.restore`
- `schematic.layout` (`op: list | unplaced | create | rename | delete | set-default | move | place | align | distribute | route | apply`) — layouts and placement; `schematic.render` takes `view` to see a layout
- `schematic.render` (`format: svg | png`) / `schematic.layout.metrics` — see the diagram as the editor draws it, and measure it: check your layout before you report it done
- `schematic.graph.query` — read-only graph queries (`GRAPH-MODEL.md` §5)
- `schematic.sim.set` / `at` / `advance` / `tick` — assert a level, schedule an operation, drive time
- `schematic.sim.start` / `inject` / `step` / `run` / `resume` / `reconcile` / `inspect` / `scenario` / `scenarios` / `stop` — the message simulation (`GRAPH-MODEL.md` §6). It reads the document and never mutates it; a node naming a handler nobody registered refuses its messages.

HTTP mirrors these: `GET|POST /api/v1/graph/<verb>`, `POST /api/v1/sim/<action>`, `GET /api/v1/sim/inspect?what=…&id=…`.

## Mutation discipline

1. Read current state/revision.
2. Apply one coherent semantic mutation.
3. Inspect the receipt.
4. Re-read when topology/reachability may have changed.
5. Use checkpoints for named durable milestones.

Do not treat successful transport as semantic validity. A valid Wire must still satisfy Port/surface reachability.


## Read/write axis
Treat direction, access, and authority as separate. `direction ≠ access ≠ authority`. A Port access value constrains representable Read/Write packet operations; it does not grant authority.
