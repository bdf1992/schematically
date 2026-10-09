# MCP + HTTP surface — 0.1

`mcp/server.mjs` is restored to the distributable package and imports the same `src/05-data-core.js` used by the browser.

Default durable server file: `data/schematic.sov`.

## One surface, any runtime

`mcp/surface.mjs` is the whole request-handling core: every MCP tool, every `/api/v1` route,
history, checkpoints, runs and the root description, behind `createSurface({store, packs, render,
readText, describe, editorHtml}) -> {handle(request)}`. It imports nothing from `node:` (no
`node:http`, `node:fs`, `node:path`, `node:child_process`, `node:url`); it reads the cores
(`SovSchematicData`, `SovSchematicGraph`, `SovSchematicStateSpace`, `SovSchematicLayout`) from
`globalThis`, which an entrypoint loads first. `request` is `{method, path, query (an object of
strings), headers (lower-case keys), body (a string or null)}`; `handle` resolves to `{status,
headers, body}` with `body` a string or a `Uint8Array`.

Two stores ship beside it: `mcp/store-file.mjs` (`createFileStore(file)`, the durable `.sov` file
on disk) and `mcp/store-memory.mjs` (`createMemoryStore(text)`, in-memory with a `writes` counter,
for a test or a hosted entrypoint with nowhere durable to write).

`mcp/server.mjs` is the Node entrypoint: it parses arguments, loads the cores and `guide.mjs` by
file URL, reads `data/*.pack.json`, builds the spawn-based `render` function and a file store, and
adapts `http.createServer` to `surface.handle` — reading the request body (the same 5,000,000
character limit), calling `handle`, and writing back `status`, `headers` and `body`. A hosted
entrypoint for another runtime supplies a store, packs, a transport adapter over `handle`, and
optionally `render`; render tools and routes answer `RENDERER_UNAVAILABLE` (503 over HTTP) when it
is absent. No second copy of the request logic exists anywhere in the package.

## MCP

```text
POST /mcp
```

Tools:

- `schematic.list`
- `schematic.get`
- `schematic.create`
- `schematic.update`
- `schematic.delete`
- `schematic.document.get`
- `schematic.document.replace`
- `schematic.history.undo`, `schematic.history.redo`
- `schematic.checkpoint.list`, `schematic.checkpoint.create`, `schematic.checkpoint.restore`
- `schematic.run.start` (`inputs?`, `seed?`, `budget?`), `schematic.run.step` (`handle`), `schematic.run.settle`
  (`handle`), `schematic.run.trace` (`handle`), `schematic.state.query` (`handle`, `entity`, `point?`, `channel?`,
  `observable`), `schematic.run.replay` (`trace`)
- `schematic.markers`
- `schematic.concerns` (`open?`), `schematic.concerns.answer` (`answers`, `ifRevision?`)
- `schematic.axes.set` (`axes`, `ifRevision?`)

Graph and simulation (`GRAPH-MODEL.md`, read-only over the document; the `sim.*` tools run over the
state-space engine through `src/07-state-surface.js`, `STATE-SPACE.md`, since contract 10 of the
one-runtime plan, 2026-10-03):

- `schematic.graph.query` — `{verb, args}`: junctions, reach, paths, cycles, order, cut, boundary, untyped, blocked, acl, signals, export (jgf | dot | graphml)
- `schematic.sim.set` / `at` / `advance` / `tick` — levels and time (asserted set, scheduled operations, the clock); `at`'s time and `advance`'s ms are milliseconds, carried over the engine's own ticks at the declared `tickMs` (default 1 ms per tick)
- `schematic.sim.start` / `stop` / `inject` / `step` / `run` / `resume` / `reconcile` / `inspect` / `scenario` / `scenarios` — `step` counts ticks, not milliseconds; `run`'s `until` is ms, like `advance`
- `schematic.sim.travel` / `spectrum` — pure reads of the run (`STATE-SPACE.md`, "Reading a run: travel and spectrum"). `travel` `{}` gives `{ok, tickMs, wires: [{id, a, b, forward, reverse, delayTicks, travelMs}]}`: each wire's declared delay as the run resolved it (`config.delay` in ticks, else `latencyMs` converted). `spectrum` `{fromMs, toMs, stepMs, harmonics = 8, nodes}` gives, per node, `{node, periodMs, samples, mean, energy, harmonics: [{n, amplitude, phase}], rest, parsevalError, reason}` over a window that has elapsed; refusals `WINDOW_NOT_ELAPSED`, `WINDOW_STEP`, `WINDOW_TOO_LONG`, `UNKNOWN_NODE`

HTTP: `GET|POST /api/v1/graph/<verb>`, `POST /api/v1/sim/<action>`, `GET /api/v1/sim/inspect?what=…&id=…`.

Arranging (`LAYOUT-MODEL.md`, "As built: layouts"): `schematic.layout {op, …}`.
- Read-only ops: `list`, `unplaced`.
- Views: `create`, `rename`, `delete`, `set-default`.
- Placement: `move`, `place`, `align`, `distribute`.
- `route` sets `auto`, `guided` or `pinned`.
- `apply` runs the `layered` engine, with `scope` and `into`.

Refusals are typed (`PINNED`, `LOCKED`, `HOSTED`, `UNPLACED`, `UNKNOWN_*`). Arranging never
changes what the document means.

Seeing and measuring (`LAYOUT-MODEL.md` §4–5). These need Python with Playwright and a
Chromium browser (`SOV_RENDER_PYTHON` selects the interpreter). Without them the call is
refused with `RENDERER_UNAVAILABLE`: over MCP as an error result, over HTTP as a 503.

- `schematic.render`
  - `{format: 'svg'}` returns the editor's own standalone SVG as text.
  - `{format: 'png', scale}` returns the picture as MCP **image content**, followed by
    the score as text.
- `schematic.layout.metrics` returns the 0–10 score and every finding.

HTTP: `GET /api/v1/render.svg`, `GET /api/v1/render.png?appearance=dark&scale=2`,
`GET /api/v1/layout/metrics`.

Resources: `component`, `wire`, `reference`.

`schematic.markers` returns `{id, severity, message, rule}` for each current validation finding, delegating to the same `Data.markersFor` the browser API uses — the tool invents no legality of its own.

## Concerns

A notation declares the questions a schematic should answer (`NOTATION-MODEL.md` "Concerns"); a
document carries the answers (`DATA-FORMATS.md` "Answers"). Two tools put that on this surface, and
both delegate to the data core (`Data.concernReport`, `Data.answerConcerns`): the surface holds no
rule about answers.

- `schematic.concerns {open?}` returns the report `{notation, rows, answered, open}`: one row
  `{concern, applies, target, title, question, answered, answer}` per declared concern for the
  document (`target: null`), each component and each wire. `open: true` returns only the open rows;
  the two counts stay those of every row. An open row is information, never an error.
- `schematic.concerns.answer {answers, ifRevision?}` sets or removes answers. `answers` is a
  non-empty list of `{concern, target?, answer}`: `target` absent or null is the document, else the
  id of a component or a wire; `answer` is a non-empty string to set, `null` to remove. All or
  none, one revision, one history entry (`schematic.history.undo` restores the document before
  it), one receipt in `schematic.apply`'s shape with `result.report: {answered, open}` after the
  write. Refusals, each changing nothing and setting `isError`: `ANSWER_INVALID`,
  `ANSWER_TARGET_UNKNOWN`, `ANSWER_UNKNOWN`, `ANSWER_UNDECLARED`, a locked record, and a stale
  `ifRevision`; `error.index` names the entry.

```text
GET  /api/v1/concerns            200 the report
GET  /api/v1/concerns?open=1     200 the report with only the open rows
POST /api/v1/concerns            {answers, ifRevision?}   200 the receipt; 409 a stale revision; 400 any other refusal
```

The file is saved only on 200. The guide's `concerns` step (`schematic.guide {step: 'concerns'}`,
between `palette` and `apply`) tells an agent when to read and when to answer.

## Axes

A document may declare up to three ordered axes, and a component or a wire stores its value on each
in `config.axis` (`DATA-FORMATS.md` "Axes"). One tool writes the document's list, and it delegates to
the data core (`Data.setAxes`): the surface holds no rule about axes.

- `schematic.axes.set {axes, ifRevision?}` writes the whole list: at most 3 entries
  `{id, name?, values: [{id, name?}]}`, in order; `null` or an empty list removes the axes. All or
  none, one revision, one history entry (`schematic.history.undo` restores the document before it),
  one receipt whose `result.axes` is the list after the write with every name filled in (an unnamed
  axis is `Layer`, `Phase` or `Depth` by position; an unnamed value is its axis's name and its
  position, `Layer 1`). Refusals, each changing nothing and setting `isError`: `AXIS_INVALID` (the
  list breaks a rule; the message names the entry), `AXIS_UNKNOWN` and `AXIS_VALUE_UNKNOWN` (the list
  drops an axis or a value a component or a wire still names; the message names the record), and a
  stale `ifRevision`.
- A record's own value is `config.axis: {axisId: valueId}`, written with `schematic.create`,
  `schematic.update` and `schematic.apply` (`axis: {id: null}` removes one axis, `axis: null` the
  key) and returned by `schematic.get`, `schematic.read` and `schematic.document.get`.
  `schematic.read` also returns `axes`, the named list, when the document declares any.

```text
POST /api/v1/axes                {axes, ifRevision?}      200 the receipt; 409 a stale revision; 400 any other refusal
```

The file is saved only on 200.

## Live link

The browser editor can publish a read-only snapshot of what its operator is looking at — file
identity, revision, camera, appearance, the current selection with the selected record, and the
in-browser document — so an agent can see what the person has selected without the two ever
sharing authority. The editor must be asked to publish: open it with `?live=1` (same origin when
served from `/editor`, otherwise `http://127.0.0.1:8787`), `?live=http://host:port` to name one, or
call `window.SovSchematicLive.start()`. It pushes on every selection and revision change (at most
every 250 ms), plus a 5 s heartbeat, backs off 5 s after a failed push, and stops with
`SovSchematicLive.stop()`. Pushing never mutates the server's document, its revision or its file.

```text
POST /api/v1/live      # editor -> server, schema soveraeign.schematic/live@0.1
GET  /api/v1/live      # {connected, ageMs, receivedAt, stale, snapshot}
GET  /api/v1/live?selection=1   # the snapshot without the document body
GET  /editor           # the built editor, served from this origin so the push is same-origin
```

MCP: `schematic.live.get` (the full snapshot) and `schematic.live.selection` (the selection, no
document body). Both answer `connected:false` when no editor is pushing, and carry `ageMs` and
`stale` (after 15 s) so an old snapshot is never mistaken for a live one. A snapshot in another
schema is refused with 400. The snapshot is the **unsaved editor state**, a different document
from the `.sov` file this server owns; `schematic.document.get` still reads the server's file.

`GET /editor` and `GET /index.html` serve the built `index.html` with `cache-control: no-store`,
or 404 naming `python build.py` when no build exists. `/editor` carries the document of the server in a
`sov-served-document` script tag (JSON, every `<` escaped) and opens it at start; an `open` parameter in the
address wins over it. `/index.html` is the blank build, with no tag. The root description's `editor` field is
`/editor`.

## HTTP

`GET /api/v1/formats` advertises document, package, workspace, operation, and receipt schemas.

Runs (state space, slice 1c):

```text
POST /api/v1/runs                      {inputs?, seed?, budget?}       start a run of the current document
POST /api/v1/runs/{handle}/step                                        one tick
POST /api/v1/runs/{handle}/settle                                      quiet | oscillating | budget
GET  /api/v1/runs/{handle}/trace                                       the trace in `result`
POST /api/v1/runs/{handle}/query       {entity, point?, channel?, observable}
POST /api/v1/replay                    <the trace>                     replay against the current document
```

Every run route and run tool returns a run receipt, `soveraeign.schematic/run-receipt@0.1` (`DATA-FORMATS.md`),
identical to the browser API's. A start returns the run's content-derived `runId` and a new `handle`, `<runId>.<n>`
with `n` counting the server's starts from 1; runs are addressed by handle only (URL-encoded in a path), so two clients
starting the same document and inputs get two runs that never touch each other. A replay is not registered
(`handle: null`). A budget over 1,000,000 is refused with `INPUT_INVALID`. A refused receipt's `error.details` carries
what the refusal names. The HTTP status is the only surface-specific field: 201 for a started run, 200 for any other
success, 404 with receipt code `RUN_NOT_FOUND` for an unknown handle, 400 with receipt code `INPUT_INVALID` for a body
that is not JSON or a handle in the path that does not decode, 409 with its receipt for any other refusal. Over MCP a
refused receipt sets `isError`. Runs live in an in-memory registry beside the document and never change the document,
its revision, history or the `.sov` file; the server reads `data/*.pack.json` at start.

The server persists the canonical `.sov` document. `.sovpak` is a transport/package format around that same document rather than a second mutable authority.

### Optimistic concurrency

`schematic.create`, `schematic.update`, and `schematic.delete` accept an optional `ifRevision` (number): the document revision the caller last observed. It is optional — omit it and the write applies unconditionally, as before. When present and it does not match the document's current revision, the write is refused: the tool call returns `ok:false` with `error.message` of the form `Stale revision: expected <ifRevision>, document is at <current>`, and nothing is mutated.

## Boundary rule

MCP/HTTP Wire writes use the same reachability function as the UI. A child Component cannot use an API mutation to reach an outer Port that is not exposed to its surface.


### Access axis
Port Connections may carry `access: none | read | write | read-write`. Wire config may carry `forwardOperation` / `reverseOperation: none | read | write`. Direction, access, and authority are independent.


## Attachment compatibility

Agent calls may author Wire endpoints with canonical 0D point IDs or legacy Port IDs. The shared data core validates both through the same attachment-point concern; MCP does not have a separate Port legality implementation.

Wire ends may be free: create with `aAttachment: {kind:'free',x,y}` (and/or `bAttachment`), rebind with `a`/`aSide`, free again with a free attachment. Two bound ends must share an exposed surface.
