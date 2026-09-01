# Browser API — 0.1

The browser exposes `window.SovSchematicAPI`. UI actions and API mutations share the same document/CRUD core. Terms follow `GLOSSARY.md`.

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

## Direction, access, operation

Port connection slots carry `flow` and `access`; Wire config carries `forwardOperation` / `reverseOperation`. `DATA-FORMATS.md` defines the fields and values. None of them grants authority.

## Port ids at Wire endpoints

Wire endpoints accept a built-in Port id (`self`, `start`, `end`, `left`, `right`, `top`), a template-declared Port id, or a document@0.1 compatibility id (`in`, `out`, `control`). Returned Wire records carry the canonical id in `aAttachment.pointId` / `bAttachment.pointId` and keep `aSide` / `bSide` for compatibility.
