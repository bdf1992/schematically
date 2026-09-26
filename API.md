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
SovSchematicAPI.file.parse(text)
SovSchematicAPI.file.open(payload, name)
```

`file.package()` returns the same `soveraeign.schematic/package@0.1` payload used by File → Export Package.

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


## Editor/history API

`window.SovSchematicAPI` additionally exposes `history.list/undo/redo`, `checkpoints.list/create/restore`, semantic selection clipboard helpers, and view appearance/global-rate accessors. MCP exposes history undo/redo and checkpoint list/create/restore for its file-backed document.


### Access axis
Port Connections may carry `access: none | read | write | read-write`. Wire config may carry `forwardOperation` / `reverseOperation: none | read | write`. Direction, access, and authority are independent.


## Attachment IDs

Wire endpoints accept canonical built-in attachment IDs (`self`, `start`, `end`, `left`, `right`, `top`), template-declared attachment IDs, or their document@0.1 compatibility Port IDs at Wire endpoints. Returned Wire records preserve canonical endpoint references in `aAttachment` / `bAttachment` while retaining `aSide` / `bSide` for compatibility.

Wire ends may be free: create with `aAttachment: {kind:'free',x,y}` (and/or `bAttachment`), rebind with `a`/`aSide`, free again with a free attachment. Two bound ends must share an exposed surface.


## Runs (state space, slice 1c)

```js
SovSchematicAPI.run.start({inputs, seed, budget})   // every key optional; budget at most 1000000
SovSchematicAPI.run.step(handle)                    // one tick
SovSchematicAPI.run.settle(handle)                  // quiet | oscillating {period, subjects} | budget {left}
SovSchematicAPI.run.trace(handle)                   // the trace in `result`
SovSchematicAPI.run.query(handle, {entity, point, channel, observable})   // point and channel optional
SovSchematicAPI.run.replay(trace)
SovSchematicAPI.run.drop(handle)                    // remove a run; its receipt as it stood, result null
```

Each returns a run receipt, `soveraeign.schematic/run-receipt@0.1` (`DATA-FORMATS.md`), identical to the one HTTP and
MCP return for the same document and call. Runs live in an in-memory registry beside the document. A start returns
the run's content-derived `runId` and a new `handle`, `<runId>.<n>` with `n` counting this page's starts from 1; step,
settle, trace and query take the handle (`RUN_NOT_FOUND` otherwise, a bare run id included), so two starts with the same
inputs are two runs and never touch each other. A replay is not registered: its receipt has `handle: null`. A run always
starts from the current document (`document.get()`), and replay replays against it. A budget over 1,000,000 is refused
with `INPUT_INVALID` (the engine's `startRun` itself has no cap). The registry holds at most 64 runs: a start beyond
that is refused with `RUN_LIMIT` and nothing is evicted; `drop(handle)` removes a run (`RUN_NOT_FOUND` for an unknown
handle), after which a start succeeds. A refused receipt's `error.details` carries what the
refusal names (`refusals`, `{tick, left}`, `fields`, `entry`, ...). None of these calls captures history, changes the
document or its revision, or saves recovery. Packs come from the page's `<script type="application/json"
id="sov-packs">`, which `build.py` fills from `data/*.pack.json`; the unbuilt `index.source.html` carries an empty list,
so a start or replay of a document that references a definition there is refused with `PACK_INVALID`, "this page
carries no packs".

A document is the same document wherever it is held. The editor fills runtime defaults into the records it holds,
but `document.get()` (and so every run, and every file it saves) carries the document as authored: opened and not
edited, it equals `compactDocument` of the same file loaded by `node` or the server, its `documentHash` is the file's,
and opening does not change its revision. A trace recorded against the file therefore replays against the opened
document, and one recorded in the browser replays on the server.
