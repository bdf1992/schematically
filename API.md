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


## Markers

```js
SovSchematicAPI.markers()
```

Returns `{id, severity, message, rule}` for every current `document.get()`/CRUD validation finding, straight from the same check the core runs on write — no separate legality is computed for the view. The renderer draws these as a badge on each carrying element and a total count in the status area.

## Editor/history API

`window.SovSchematicAPI` additionally exposes `history.list/undo/redo`, `checkpoints.list/create/restore`, semantic selection clipboard helpers, and view appearance/global-rate accessors. MCP exposes history undo/redo and checkpoint list/create/restore for its file-backed document.


### Access axis
Port Connections may carry `access: none | read | write | read-write`. Wire config may carry `forwardOperation` / `reverseOperation: none | read | write`. Direction, access, and authority are independent.


## Attachment IDs

Wire endpoints accept canonical built-in attachment IDs (`self`, `start`, `end`, `left`, `right`, `top`), template-declared attachment IDs, or their document@0.1 compatibility Port IDs at Wire endpoints. Returned Wire records preserve canonical endpoint references in `aAttachment` / `bAttachment` while retaining `aSide` / `bSide` for compatibility.

Wire ends may be free: create with `aAttachment: {kind:'free',x,y}` (and/or `bAttachment`), rebind with `a`/`aSide`, free again with a free attachment. Two bound ends must share an exposed surface.
