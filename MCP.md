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
- `schematic.history.undo`, `schematic.history.redo`
- `schematic.checkpoint.list`, `schematic.checkpoint.create`, `schematic.checkpoint.restore`
- `schematic.run.start` (`inputs?`, `seed?`, `budget?`), `schematic.run.step` (`runId`), `schematic.run.settle`
  (`runId`), `schematic.run.trace` (`runId`), `schematic.state.query` (`runId`, `entity`, `point?`, `channel?`,
  `observable`), `schematic.run.replay` (`trace`)

Resources: `component`, `wire`, `reference`.

## HTTP

`GET /api/v1/formats` advertises document, package, workspace, operation, and receipt schemas.

Runs (state space, slice 1c):

```text
POST /api/v1/runs                  {inputs?, seed?, budget?}       start a run of the current document
POST /api/v1/runs/{id}/step                                        one tick
POST /api/v1/runs/{id}/settle                                      quiet | oscillating | budget
GET  /api/v1/runs/{id}/trace                                       the trace in `result`
POST /api/v1/runs/{id}/query       {entity, point?, channel?, observable}
POST /api/v1/replay                <the trace>                     replay against the current document
```

Every run route and run tool returns a run receipt, `soveraeign.schematic/run-receipt@0.1` (`DATA-FORMATS.md`),
identical to the browser API's; the HTTP status is the only surface-specific field: 201 for a started run, 200 for any
other success, 404 with receipt code `RUN_NOT_FOUND` for an unknown run id, 409 with its receipt for any other refusal.
Over MCP a refused receipt sets `isError`. Runs live in an in-memory registry beside the document, keyed by run id, and
never change the document, its revision, history or the `.sov` file; the server reads `data/*.pack.json` at start.

The server persists the canonical `.sov` document. `.sovpak` is a transport/package format around that same document rather than a second mutable authority.

## Boundary rule

MCP/HTTP Wire writes use the same reachability function as the UI. A child Component cannot use an API mutation to reach an outer Port that is not exposed to its surface.


### Access axis
Port Connections may carry `access: none | read | write | read-write`. Wire config may carry `forwardOperation` / `reverseOperation: none | read | write`. Direction, access, and authority are independent.


## Attachment compatibility

Agent calls may author Wire endpoints with canonical 0D point IDs or legacy Port IDs. The shared data core validates both through the same attachment-point concern; MCP does not have a separate Port legality implementation.

Wire ends may be free: create with `aAttachment: {kind:'free',x,y}` (and/or `bAttachment`), rebind with `a`/`aSide`, free again with a free attachment. Two bound ends must share an exposed surface.
