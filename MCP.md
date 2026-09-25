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

Graph and simulation (`GRAPH-MODEL.md`, read-only over the document):

- `schematic.graph.query` — `{verb, args}`: junctions, reach, paths, cycles, order, cut, boundary, untyped, blocked, acl, signals, export (jgf | dot | graphml)
- `schematic.sim.set` / `at` / `advance` / `tick` — levels and time (asserted set, scheduled operations, the clock)
- `schematic.sim.start` / `stop` / `inject` / `step` / `run` / `resume` / `reconcile` / `inspect` / `scenario` / `scenarios`

HTTP: `GET|POST /api/v1/graph/<verb>`, `POST /api/v1/sim/<action>`, `GET /api/v1/sim/inspect?what=…&id=…`.

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

## HTTP

`GET /api/v1/formats` advertises document, package, workspace, operation, and receipt schemas.

The server persists the canonical `.sov` document. `.sovpak` is a transport/package format around that same document rather than a second mutable authority.

## Boundary rule

MCP/HTTP Wire writes use the same reachability function as the UI. A child Component cannot use an API mutation to reach an outer Port that is not exposed to its surface.


### Access axis
Port Connections may carry `access: none | read | write | read-write`. Wire config may carry `forwardOperation` / `reverseOperation: none | read | write`. Direction, access, and authority are independent.


## Attachment compatibility

Agent calls may author Wire endpoints with canonical 0D point IDs or legacy Port IDs. The shared data core validates both through the same attachment-point concern; MCP does not have a separate Port legality implementation.

Wire ends may be free: create with `aAttachment: {kind:'free',x,y}` (and/or `bAttachment`), rebind with `a`/`aSide`, free again with a free attachment. Two bound ends must share an exposed surface.
