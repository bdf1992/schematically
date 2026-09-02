# MCP + HTTP surface — 0.1

`mcp/server.mjs` is restored to the distributable package and imports the same `src/05-data-core.js` used by the browser.

Default durable server file: `data/schematic.sov`.

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

Resources: `component`, `wire`, `reference`.

### Live link (read-only)

- `schematic.live.selection` — what the browser editor currently has selected: kind (`component` / `wire` / `point` / `none`), the ids, and the selected record. No document body.
- `schematic.live.get` — the whole editor snapshot: file name and revision, dirty flag, counts, camera and appearance, selection, and the in-browser document.

Both answer `connected:false` when no editor is pushing, and carry `ageMs` and `stale` so an old snapshot is never mistaken for a live one. The snapshot is the **unsaved editor state**, which is a different document from the `.sov` file this server owns; `schematic.document.get` still reads the server's file.

The editor must be asked to publish: open it with `?live=1` (or `?live=http://host:port`), or call `window.SovSchematicLive.start()`. It pushes on every selection and revision change, plus a heartbeat, and stops with `SovSchematicLive.stop()`. Pushing never mutates the server document.

```text
POST /api/v1/live      # editor -> server, schema soveraeign.schematic/live@0.1
GET  /api/v1/live      # full snapshot with age
GET  /api/v1/live?selection=1   # same without the document body
```


## HTTP

`GET /api/v1/formats` advertises document, package, workspace, operation, and receipt schemas.

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
