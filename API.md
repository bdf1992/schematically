# Browser API — 0.1 Beta.24

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


## Editor/history API (Beta.24)

`window.SovSchematicAPI` additionally exposes `history.list/undo/redo`, `checkpoints.list/create/restore`, semantic selection clipboard helpers, and view appearance/global-rate accessors. MCP exposes history undo/redo and checkpoint list/create/restore for its file-backed document.


### Beta.24 access axis
Port Connections may carry `access: none | read | write | read-write`. Wire config may carry `forwardOperation` / `reverseOperation: none | read | write`. Direction, access, and authority are independent.


## Attachment IDs

Beta.24 accepts canonical built-in attachment IDs (`self`, `start`, `end`, `left`, `right`, `top`), template-declared attachment IDs, or their document@0.1 compatibility Port IDs at Wire endpoints. Returned Wire records preserve canonical endpoint references in `aAttachment` / `bAttachment` while retaining `aSide` / `bSide` for compatibility.
