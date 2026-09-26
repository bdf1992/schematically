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
- `schematic.run.start` (`inputs?`, `seed?`, `budget?`), `schematic.run.step` (`handle`), `schematic.run.settle`
  (`handle`), `schematic.run.trace` (`handle`), `schematic.state.query` (`handle`, `entity`, `point?`, `channel?`,
  `observable`), `schematic.run.replay` (`trace`), `schematic.run.drop` (`handle`)

Resources: `component`, `wire`, `reference`.

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
DELETE /api/v1/runs/{handle}                                           drop a run
```

Every run route and run tool returns a run receipt, `soveraeign.schematic/run-receipt@0.1` (`DATA-FORMATS.md`),
identical to the browser API's. A start returns the run's content-derived `runId` and a new `handle`, `<runId>.<n>`
with `n` counting the server's starts from 1; runs are addressed by handle only (URL-encoded in a path), so two clients
starting the same document and inputs get two runs that never touch each other. A replay is not registered
(`handle: null`). A budget over 1,000,000 is refused with `INPUT_INVALID`. The server holds at most 64 runs: a start
beyond that is refused with `RUN_LIMIT` (HTTP 409) and nothing is evicted; `schematic.run.drop` / `DELETE
/api/v1/runs/{handle}` removes a run and returns its receipt as it stood (`result` null, `operation`
`schematic.run.drop`), after which a start succeeds. A refused receipt's `error.details` carries
what the refusal names. The HTTP status is the only surface-specific field: 201 for a started run, 200 for any other
success, 404 with receipt code `RUN_NOT_FOUND` for an unknown handle, 400 with receipt code `INPUT_INVALID` for a body
that is not JSON or a handle in the path that does not decode, 409 with its receipt for any other refusal
(`RUN_LIMIT` among them). Over MCP a
refused receipt sets `isError`. Runs live in an in-memory registry beside the document and never change the document,
its revision, history or the `.sov` file; the server reads `data/*.pack.json` at start.

The server persists the canonical `.sov` document. `.sovpak` is a transport/package format around that same document rather than a second mutable authority.

## Boundary rule

MCP/HTTP Wire writes use the same reachability function as the UI. A child Component cannot use an API mutation to reach an outer Port that is not exposed to its surface.


### Access axis
Port Connections may carry `access: none | read | write | read-write`. Wire config may carry `forwardOperation` / `reverseOperation: none | read | write`. Direction, access, and authority are independent.


## Attachment compatibility

Agent calls may author Wire endpoints with canonical 0D point IDs or legacy Port IDs. The shared data core validates both through the same attachment-point concern; MCP does not have a separate Port legality implementation.

Wire ends may be free: create with `aAttachment: {kind:'free',x,y}` (and/or `bAttachment`), rebind with `a`/`aSide`, free again with a free attachment. Two bound ends must share an exposed surface.
