# GLSP 2.8.0 projection spike -- report

Scope actually reached: a real GLSP 2.8.0 Node adapter and server (`adapter.mjs`,
`data-core.mjs`, `routing.mjs`, `server.mjs`) that projects
`examples/08-gated-service.sov` through `src/05-data-core.js` into a GModel, and
routes GLSP operations back through `Data.applyOperation` so the core's own
receipt answers both a legal update and a boundary-crossing wire create --
verified end to end in `test.mjs`, including one real WebSocket round trip
through the server's own wire-protocol framing. No bundled GLSP browser
client was built (see "What did not get built" below); everything that needs
one -- rendering in a real client, SVG export via `ExportSvgAction`, the
scale-benchmark load -- was not obtained, for the reason logged in
`evidence/upstream-reference-build.log` and `evidence/toolchain-refusal.log`.

## Projection counts (step 6)

`node test.mjs` asserts, from `examples/08-gated-service.sov`:

| metric | count |
|---|---|
| nodes (all projected components) | 9 |
| edges (wires) | 7 |
| nested (parentId set) | 5 |
| ports (hosted 0D attachment points: permit, ingress, egress) | 3 |

## Routing verified (steps 3, 6)

- `changeBounds` on `store` -> `Data.applyOperation({op:'update', resource:'component', ...})`; the resulting document is deep-equal (modulo the independent `meta.updatedAt` timestamp) to calling `Data.applyOperation` directly with the same patch.
- `createEdge` from `req` to `check` (crossing the Service boundary with no exposed shared surface) returns `ok:false` with the core's own message, `Boundary blocks implicit reach-through`, and leaves the document byte-for-byte unchanged.
- `createEdge` from `grant` to `egress` (both reach `canvas:global`, since `egress`'s port has `face:'both'`) succeeds and the new wire appears in the reprojected GModel.
- The same boundary-crossing refusal was also driven over a live WebSocket connection speaking the server's JSON-RPC framing (`initialize` / `initializeClientSession` / `process` notifications), confirmed in `test.mjs`.
- `adapter.mjs` and `server.mjs` were checked to contain none of the strings `boundary`, `reachab`, `locked` -- no legality is decided outside `src/05-data-core.js`.

## Server-side layout (step 4)

`layout.mjs` runs the projected GModel through `elkjs` (the layout engine
`@eclipse-glsp/layout-elk` wraps; the GLSP module itself is a thin
inversify-DI adapter around it, not stood up here) with the `layered`
algorithm:

| id | authored x,y | ELK layered x,y |
|---|---|---|
| grant | 160,290 | 12,116 |
| req | 160,430 | 12,12 |
| svc | 640,360 | 152,14 |
| check | 560,400 | 12,12 |
| store | 760,400 | 144,12 |
| log | 1120,360 | 448,26 |

Full ELK output: `evidence/elk-layout.json`. `src/40-routing.js` is wire-path
routing (obstacle-avoiding edge geometry between authored, fixed node
positions), not a node-placement layout -- so there is no like-for-like
"layout vs layout" comparison to make; the table above is authored position
vs. ELK's computed position for the same nodes. No screenshot comparison was
made: that needs the renderer (present) next to a rendered GLSP client
(absent -- see below).

## What did not get built, and why

Step 2 calls for building "GLSP's own standalone workflow example, unchanged"
before writing spike code, specifically so a toolchain fault could be told
apart from a spike-code fault. `npm`/`node` work normally in this session
(confirmed: `npm --version` -> 11.6.2, dependencies installed cleanly,
~92 MB under `node_modules`). But no such example is npm-installable at
2.8.0: `@eclipse-glsp-examples/workflow-glsp` is a diagram DI module for a
host app, not a runnable page; `workflow-server` / `workflow-server-bundled`
are Node servers, not browser clients. The actual runnable standalone browser
example lives only as source in the `eclipse-glsp/glsp-client` GitHub
repository, which is outside both `npm install` and this contract's permitted
git commands (local-only: worktree list, checkout, branch, stash, rev-parse,
show -- no clone of an external remote). Full detail and the confirming
`npm view`/`npm search` output: `evidence/upstream-reference-build.log`. What
that log does confirm, unchanged and running: the bundled upstream Node
server itself starts cleanly on this machine.

Because of that, steps 5, 7 and 8 -- the Playwright client QA, the
`ExportSvgAction` vs. `scripts/export_svg.py` comparison, and loading a
scale fixture through the GLSP client -- were not attempted; each needs a
real bundled GLSP client, which this session could not obtain without either
network access to clone an external repository or writing a from-scratch
sprotty/GLSP client bootstrap (DI container, action dispatcher, SVG views per
element type, tool palette, undo/redo command stack) that would not be
"GLSP's own... unchanged," defeating the point of the comparison. `test.mjs`
substitutes a direct WebSocket client speaking the same action protocol,
which verifies the server and routing but not rendering, the palette, or the
command stack.

## Leverage tables (step 9)

### 1. What upstream performed our job, module by module

| our module/concern | upstream service that performed it here | notes |
|---|---|---|
| `src/40-routing.js` (wire path routing) | none | ELK computes node *position*, not the obstacle-avoiding wire geometry 40-routing.js produces; no upstream primitive does that job |
| `src/50-selection.js` | none (not exercised) | would be `@eclipse-glsp/client`'s SelectionService if a client were built; not verified here |
| `src/60-interactions.js` | none (not exercised) | would be GLSP's tool/mouse-listener framework (`@eclipse-glsp/client`) in a built client |
| `src/70-editor-controls.js` | none (not exercised) | GLSP has an UndoRedoCommandStack + tool palette; neither was stood up |
| `src/55-render.js` | none (not exercised) | GLSP's client renders GModel via sprotty views; not built |
| `scripts/export_svg.py` | none demonstrated | GLSP has `ExportSvgAction`; step 7 (the comparison) was not run |
| mcp undo/redo/checkpoint | none | GLSP's node-server framework has no equivalent to file-persisted named checkpoints; undo/redo would be its `UndoRedoCommandStack`, not exercised |
| `validateDocument` surfacing | `RequestMarkersAction`/`SetMarkersAction` (protocol types) | `markersFor()` in `routing.mjs` maps `Data.validateDocument` errors onto GLSP markers; verified via direct call, not via a rendered marker in a client |
| node placement layout | `@eclipse-glsp/layout-elk` (via `elkjs` directly) | ran server-side in Node, no browser needed; see table above |
| GModel projection itself | `@eclipse-glsp/graph`'s GModel *shape* (types: graph/node/edge/port) | we wrote `adapter.mjs` (101 lines) to produce that shape; the shape itself, and its JSON-RPC wire protocol, are upstream's |

### 2. Adapter size and cost

| fact | value |
|---|---|
| lines we wrote (`adapter.mjs` + `data-core.mjs` + `routing.mjs` + `server.mjs` + `layout.mjs`) | 101 + 16 + 122 + 89 + 54 = 382 |
| lines in `test.mjs` | 128 |
| upstream concepts the adapter/server had to learn | GModel tree shape (graph/node/edge/port, id/position/size/children), GLSP action kinds (`requestModel`, `changeBounds`, `createNode`, `createEdge`, `deleteElement`, `applyLabelEdit`, `requestMarkers`/`setMarkers`), the JSON-RPC-over-WebSocket session handshake (`initialize`, `initializeClientSession`, `disposeClientSession`, `process` notification carrying `{clientId, action}`) |
| upstream npm packages installed | `@eclipse-glsp/{client,server,protocol,graph,layout-elk,sprotty}` 2.8.0, plus `inversify`, `reflect-metadata`, `ws`, and (dev) `webpack`, `webpack-cli`, `ts-loader`, `typescript`, `css-loader`, `style-loader` |
| `node_modules` size | ~92 MB |
| build wall time | none needed for what was actually run -- `adapter.mjs`/`server.mjs`/`routing.mjs`/`layout.mjs` are plain ESM, no bundling step; `npm install` itself took under a minute per `evidence/npm-install.log` |
| Node/tool version required | Node v24.11.1, npm 11.6.2 (this session's versions; upstream's own package.json engines were not separately audited) |
| native modules compiled | none observed (`elkjs` and everything installed here are pure JS) |
| DI framework actually used | none -- `@eclipse-glsp/server`'s inversify-based `GModelDiagramModule`/`ServerModule` scaffolding (used by the real `workflow-server` example, see `evidence/upstream-reference-build.log`) was not stood up; `server.mjs` hand-frames the same JSON-RPC wire messages instead, which is why it is 89 lines and not "unchanged upstream" |

### 3. Upgrade burden

Recent `@eclipse-glsp/server` publish dates (from the live npm registry):

| version | date |
|---|---|
| 2.9.0-next.1 | 2026-09-02 |
| 2.8.0 | 2026-08-28 |
| 2.8.0-next.12 | 2026-08-27 |
| 2.8.0-next.10 | 2026-08-26 |

A `next` prerelease every 1-2 days, with a numbered release roughly monthly
(2.9.0-next.1 landed the day after 2.8.0 itself). Every place this spike
touched an upstream internal rather than a documented extension point:

- `server.mjs` hand-frames the JSON-RPC method names and the `process`
  notification shape read directly out of `@eclipse-glsp/protocol`'s
  `glsp-jsonrpc-client.js` source (`InitializeRequest`, `ActionMessageNotification`
  = `'process'`), rather than using the published `@eclipse-glsp/server`
  `SocketServerLauncher`/`WebSocketServerLauncher` classes the real
  `workflow-server` example uses -- because those classes require the full
  inversify `ServerModule`/`GModelDiagramModule` DI wiring this spike did not
  stand up. That wire-shape is not a published, versioned public API; it is
  read out of the current package's compiled source.
- `layout.mjs` calls `elkjs` directly rather than through
  `@eclipse-glsp/layout-elk`'s `ElkLayoutModule`, again to avoid the DI
  container. `@eclipse-glsp/layout-elk` is the documented extension point;
  calling `elkjs` under it directly is not.
- `adapter.mjs`'s GModel shape (`{id, type, position, size, children}`) was
  inferred from `@eclipse-glsp/graph`'s class shapes and the workflow
  example's JSON fixtures, not from a schema doc; a future GModel shape
  change would not be caught by any type system here.

### 4. What we could plausibly stop owning

| file/function | upstream performed | ours still |
|---|---|---|
| node placement (x,y for an initial or auto-layout view) | `@eclipse-glsp/layout-elk` (`elkjs`) | src's own layout code, if any beyond authored x,y -- not audited beyond this spike |
| `validateDocument` -> marker mapping | GLSP's marker protocol (`RequestMarkersAction`/`SetMarkersAction`) carries it to a client | `Data.validateDocument` itself: legality logic stays ours, unconditionally |
| — | (nothing else confirmed; see "What did not get built") | `src/40-routing.js`, `src/50-selection.js`, `src/60-interactions.js`, `src/70-editor-controls.js`, `src/55-render.js`, `scripts/export_svg.py`, mcp undo/redo/checkpoint -- none of these were exercised against an upstream equivalent in this spike, so none can be marked "upstream performed this" on the evidence gathered here |

### 5. The adversarial next load (SVG export)

Not run. Step 7 required triggering GLSP's `ExportSvgAction` from a bundled
client, which this spike does not have (see "What did not get built"). No
line-count or composed-vs-bespoke comparison can be reported honestly without
having run it.

## Scale fact (step 8)

Not obtained, and not solely for the client-wall reason above: there is no
static fixture file to load. `tests/scale-benchmark-results.json` (present
only on an unmerged branch, `b8b41dc` -- read via `git show` for reference,
saved to `evidence/_ref-scale-benchmark-results.json`) is the *output* of
`tests/scale_benchmark.py`, which builds each topology step synthetically
inside a live browser page via direct model-factory calls
(`SovSchematicData.makeComponent`/`makeWire`), not from a saved `.sov`. The
largest step it reached before stopping (racks=400: cold render 32,603 ms
exceeded the 10,000 ms cap) was 4,025 components / 3,600 wires / 14,475
ports / 146,788 SVG elements -- recorded here as the control number, not
loaded through anything, since there is no client to load it into.

## Protocol exchange

`evidence/protocol.jsonl` — the JSON-RPC messages captured in `test.mjs`'s
WebSocket round trip (`initialize`, `initializeClientSession`, then `process`
notifications for `requestModel` -> `setModel` and the boundary-crossing
`createEdge` -> `setMarkers`).
