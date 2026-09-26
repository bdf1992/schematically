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

`window.SovSchematicAPI` additionally exposes `history.list/undo/redo`, `checkpoints.list/create/restore`, semantic selection clipboard helpers, and view appearance/global-rate/zoom accessors (`view.zoom()`, `view.setZoom(z)`). MCP exposes history undo/redo and checkpoint list/create/restore for its file-backed document.


## Logic API

A document whose components declare `config.logic` runs as a circuit (the shared runtime `src/07-logic-core.js`, equal to `scripts/logic_sov.py`).

- `logic.run({vector})` or `logic.run({steps: [{set, pulse?}], record?})`: stateless. Returns `{ok, inputs, levels, outputs, steps: [{set, outputs, settle, transitions, time}], wires: {id: {value, a, b}}, events?}` or a typed refusal `{ok: false, refused, reason, next_operation}`. MCP's `schematic.logic.run` returns the same.
- `logic.live.start(vector)`, `.set(vector)`, `.pulse(clock, vector)`, `.state()`, `.stop()`: draw the circuit's state on the canvas and keep it (flip-flops, latches) between steps. Inputs a vector does not name start at 0 and are then named in `state().vector`. A move keeps the state; a change to the logic rebuilds the circuit from power-on with the current inputs (`state().rebuilt` counts). While live, a bit input's chip is its switch.
- `logic.composites.add(name, document)`, `.list()`, `.remove(name)`: documents that `{"composite": name}` parts resolve to, by file name. Without one, a composite part is refused `NO_COMPOSITE`.


### Access axis
Port Connections may carry `access: none | read | write | read-write`. Wire config may carry `forwardOperation` / `reverseOperation: none | read | write`. Direction, access, and authority are independent.


## Attachment IDs

Wire endpoints accept canonical built-in attachment IDs (`self`, `start`, `end`, `left`, `right`, `top`), template-declared attachment IDs, or their document@0.1 compatibility Port IDs at Wire endpoints. Returned Wire records preserve canonical endpoint references in `aAttachment` / `bAttachment` while retaining `aSide` / `bSide` for compatibility.

Wire ends may be free: create with `aAttachment: {kind:'free',x,y}` (and/or `bAttachment`), rebind with `a`/`aSide`, free again with a free attachment. Two bound ends must share an exposed surface.
