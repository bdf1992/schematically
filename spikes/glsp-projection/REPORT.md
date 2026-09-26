# GLSP 2.8.0 projection spike -- report

Scope reached: a real GLSP 2.8.0 Node adapter and server (`adapter.mjs`,
`data-core.mjs`, `routing.mjs`, `server.mjs`) that projects
`examples/08-gated-service.sov` through `src/05-data-core.js` into a GModel,
and a real bundled GLSP 2.8.0 browser client (`client/`, built with
`@eclipse-glsp/client` 2.8.0's own `DEFAULT_MODULES`) that renders it and
drives GLSP operations back through `Data.applyOperation` so the core's own
receipt answers every one of them -- verified end to end in `test.mjs` (the
protocol layer, headless) and `client_qa.py` (the rendered client, via
Playwright), including a real WebSocket round trip and a real
`ExportSvgAction` export. Steps 1-7 were completed against the real upstream
client and server code. Step 8 (the scale fact) used a synthetic fixture at a
comparable node count, not the benchmark's own topology -- see that section
for why.

## Step 2, revised twice

The first revision of this report (still in `evidence/upstream-reference-build.log`)
concluded that "GLSP's own standalone workflow example, unchanged" could not
be built because no such example is `npm install`-able, and cloning the
`eclipse-glsp/glsp-client` GitHub repository was "outside this contract's
permitted commands." That premise no longer holds: this contract's permitted
command list includes `git clone:*`, network access to github.com and
registry.npmjs.org both work from this session, and the clone, `pnpm install`,
and `pnpm build` of the real `eclipse-glsp/glsp-client` monorepo (kept local,
gitignored, under `spikes/glsp-projection/.tools/glsp-client-ref/`) all
succeeded unchanged -- see `evidence/upstream-reference-client-build.log`.
Everything below that needed a real bundled GLSP client (steps 5, 7, 8) was
therefore attempted, and got one: this spike's own `client/`, wired to
`server.mjs` instead of the workflow example's server.

## Projection counts (step 6)

`node test.mjs` asserts, from `examples/08-gated-service.sov`:

| metric | count |
|---|---|
| nodes (all projected components) | 9 |
| edges (wires) | 7 |
| nested (parentId set) | 5 |
| ports (hosted 0D attachment points: permit, ingress, egress) | 3 |

`client_qa.py` independently confirms 9 rendered graphical nodes (6 typed +
3 ports) and 7 rendered edges in a real browser.

## Routing verified (steps 3, 6)

- `changeBounds` on `store` -> `Data.applyOperation({op:'update', resource:'component', ...})`; the resulting document is deep-equal (modulo the independent `meta.updatedAt` timestamp) to calling `Data.applyOperation` directly with the same patch.
- `createEdge` from `req` to `check` (crossing the Service boundary with no exposed shared surface) returns `ok:false` with the core's own message, `Boundary blocks implicit reach-through`, and leaves the document byte-for-byte unchanged.
- `createEdge` from `grant` to `egress` (both reach `canvas:global`, since `egress`'s port has `face:'both'`) succeeds and the new wire appears in the reprojected GModel.
- The same boundary-crossing refusal was also driven over a live WebSocket connection speaking the server's JSON-RPC framing (`initialize` / `initializeClientSession` / `process` notifications), confirmed in `test.mjs`, and again from inside a real rendered GLSP client in `client_qa.py`.
- `adapter.mjs` and `server.mjs` were checked to contain none of the strings `boundary`, `reachab`, `locked` -- no legality is decided outside `src/05-data-core.js`. `client/view-module.mjs` and `client/app.mjs` carry the same property: they register views and dispatch actions, and decide nothing.

## A coordinate bug the client build surfaced (adapter.mjs)

Building a real client exposed a real defect in `adapter.mjs` that
`test.mjs`'s protocol-only assertions could not see: GLSP/sprotty compose a
child element's `position` relative to its *parent's* own origin (the
parent's `<g>` carries a `translate(parent.position)` transform), but the
first version of `projectDocument` emitted every component's document-
absolute `x,y` unconditionally. For top-level components (`grant`, `req`,
`svc`, `log`) that is correct, since their parent is the graph root at
(0,0) -- but `svc`'s nested children (`permit`, `ingress`, `egress`, `check`,
`store`) rendered at their absolute document position *added to* `svc`'s own
offset, pushing them off sprotty's viewport-culling bounds; the client
rendered zero of them (silently -- no error, no `sprotty-missing` fallback,
just absent from the DOM). Fixed by subtracting the immediate host's `x,y`
from a nested child's `position` (`adapter.mjs`, `portFor`/`nodeFor`'s
`hostX,hostY` parameters); `routeOperation` still patches the document's own
absolute coordinates, so this is a rendering-only transform, not a document
or legality change. `node test.mjs` passed both before and after this fix --
it has no assertion that would have caught it, since it never renders
anything. This is exactly the class of defect the contract's step 2 rule
(build the real upstream reference first, so a fault is legible as "ours",
not "the toolchain's") is aimed at making self-evident, one layer further in:
the layer it actually caught was our own adapter, not the toolchain.

## Client (steps 3-5)

`client/app.mjs` bundles `@eclipse-glsp/client` 2.8.0's own `DEFAULT_MODULES`
(rendering, selection, move, create-edge/-node, delete, undo/redo machinery,
markers) via `initializeDiagramContainer`, plus three additions:

- `baseViewModule` -- not itself in `DEFAULT_MODULES`; without it, `graph`,
  `edge` and `port` (all `DefaultTypes` our adapter's types already match)
  have no view bound, and render a `missing "graph" view` placeholder text
  node instead of the diagram.
- `client/view-module.mjs` (19 lines) -- registers `node:<symbolId>` (the six
  symbol ids in the fixture: `authority`, `act`, `plane`, `gate`, `hold`,
  `receipt`) onto GLSP's stock `RectangularNodeView`. No custom rendering.
- `standaloneExportModule` -- also not in `DEFAULT_MODULES`; `exportModule`
  alone wires the export *request* machinery (`RequestExportSvgAction` ->
  captures the rendered SVG) but not a handler for the resulting `exportSvg`
  action, so without this the export pipeline throws `Missing handler for
  action 'exportSvg'` and nothing downloads. The GLSP source comment names
  this precisely: `standaloneExportModule` is "intended for the standalone
  deployment of GLSP (i.e. plain webapp)" -- exactly this spike's shape.

`server.mjs` gained: `serverActions` in its `InitializeResult` (required --
`GLSPModelSource.configureServeActions` throws if the array for the client's
`diagramType` is empty or absent, since that is how the client's local action
dispatcher knows which action kinds to forward to the server instead of
erroring "missing handler"), and two more action kinds it must now answer,
`requestTypeHints` and `requestContextActions`, both dispatched by the
client's own startup sequence before it considers the model ready. Neither
carries a legality decision: type hints just mark every projected type
repositionable/deletable (`Data.validateDocument`, via `requestMarkers`, is
what actually refuses a move or delete), and context actions returns an
empty list -- this spike drives GLSP operations directly through the action
dispatcher (`window.__glsp.dispatch`, exposed by `client/app.mjs` for
`client_qa.py`), not through a tool palette the server would need to
populate with `RequestContextActions` responses (out of scope for this
spike; the palette renders, empty, with no error).

`client_qa.py` (Playwright, headless Chromium) drives the bundled client
against a real `server.mjs` instance and passes all of:

1. 9 graphical nodes (6 typed + 3 ports) and 7 edges render.
2. A `changeBounds` operation dispatched on `grant` (a top-level, non-nested
   node) both re-renders at the new position in the DOM and comes back in
   the server's re-projected `setModel` at that same position -- proof the
   document itself was patched, not just the local view.
3. A boundary-crossing `createEdge` (`req` -> `check`) gets `setMarkers` back
   (never `setModel`), carrying the core's own `Boundary blocks implicit
   reach-through` message; the rendered edge count stays at 7.
4. A legal `createEdge` (`grant` -> `egress`) adds an 8th edge, both in the
   server's response and in the rendered DOM, with a `k<N>` id from the
   server's own `nextWireId` scheme -- never a GLSP-minted id.
5. `UndoAction` (see below) fails with `Missing handler for action
   'glspUndo'`, gracefully caught by the QA script rather than crashing it.

Full run: `python client_qa.py` -- 12 checks pass (see console output; raw
summary in `evidence/client_qa_result.json`).

### Which side owns undo (step 5)

`@eclipse-glsp/protocol`'s `UndoAction`/`RedoAction` (`node_modules/
@eclipse-glsp/protocol/lib/action-protocol/undo-redo.d.ts`) have kind
`glspUndo`/`glspRedo`, distinct from `sprotty-protocol`'s plain `undo`/`redo`,
and are documented as actions the client sends to ask the *server* to undo
its own command history -- GLSP 2.8.0 models the undo/redo state as the
server's, not the client's local sprotty command stack. `server.mjs`
implements no operation history (every `changeBounds`/`createEdge`/etc. call
is a one-shot `Data.applyOperation` against the live document, with nothing
recorded to reverse), so `glspUndo` has nothing to answer: dispatching it
throws "Missing handler for action 'glspUndo'" client-side, no WebSocket
frame is ever sent, and the rendered document is unaffected (8 edges, both
before and after the dispatch attempt). This is the honest answer to "which
side owns the undo state": the server does, by design, and this spike's
server does not implement it.

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
vs. ELK's computed position for the same nodes.

## SVG export comparison (step 7)

`client_qa.py` triggers GLSP's real `ExportSvgAction` (via
`RequestExportSvgAction`, the client-side hidden-render + `file-saver`
download pipeline) on `examples/08-gated-service.sov` and saves the result to
`evidence/glsp-export.svg`. `python scripts/export_svg.py examples/08-gated-service.sov
--out spikes/glsp-projection/evidence` produced `evidence/08-gated-service.svg`
from the same fixture.

| | GLSP `ExportSvgAction` | `scripts/export_svg.py` |
|---|---|---|
| file | `evidence/glsp-export.svg` | `evidence/08-gated-service.svg` |
| size | 3,064 bytes | 31,132 bytes |
| `<g>` | 18 | 41 |
| `<rect>` | 9 | 9 |
| `<path>` | 8 | 69 |
| `<circle>` | 0 | 46 |
| `<text>` | 0 | 26 |
| `<symbol>`/`<use>`/gradients/`<animateMotion>` | 0 | 20 / 5 / 21 / 1 |

GLSP's export is a literal serialization of whatever the generic
`RectangularNodeView`/`GEdgeView` boxes-and-lines rendered: one `<rect>` per
node/port, one `<path>` per edge, nothing else -- it composed entirely from
the projection (`adapter.mjs`'s GModel) plus stock GLSP views, zero bespoke
export code. `scripts/export_svg.py` (176 lines) additionally renders per-
symbol iconography, gradients, labels and an animated signal-flow marker --
that visual language is `src/55-render.js`'s job (out of scope to touch
here, per the contract), and GLSP's generic node/edge views have no
equivalent primitive for any of it. The size/element-count gap is that
difference, not an export-pipeline deficiency on either side.

## Scale fact (step 8)

`tests/scale-benchmark-results.json` and `SCALE-GATE.md` do not exist on
this branch, `dev`, or `main` -- only in one orphaned commit (`b8b41dc`,
outside this contract's history) reachable by `git show`. Reference copies:
`evidence/_ref-scale-benchmark-results.json`, `evidence/_ref-SCALE-GATE.md`,
`evidence/_ref-scale_benchmark.py`. The benchmark itself builds each
topology step synthetically *inside a running browser page* via that app's
own in-memory model factories (`SovSchematicData.makeComponent`/`makeWire`
called directly, not `Data.applyOperation` against a `.sov`); it never
writes a loadable fixture file, so there is nothing at that benchmark's own
scale to load through this spike's GLSP client.

What was done instead: `evidence/gen_scale_fixture.mjs` builds a flat
synthetic `.sov` (252 components in a grid, 225 chained wires, all through
`Data.applyOperation` -- real document objects, not a mock) at the same
node/wire count as the benchmark's own `racks=25` step, saved to
`evidence/scale-fixture.sov`. `evidence/scale_measure.py` loads it through
the real client and server and records wall time:

| | this spike (flat topology) | `racks=25` step, `_ref-scale-benchmark-results.json` |
|---|---|---|
| components | 252 | 252 |
| wires | 225 | 225 |
| cold render (navigate -> `window.__glspReady`) | 214 ms | 427.6 ms (`cold`) |
| rendered nodes in DOM | 54 of 252 | not applicable (different renderer) |
| rendered edges in DOM | 225 of 225 | not applicable |

This spike's flat grid is not the benchmark's nested rack/spine/server
topology (no containment, no ports), so the two numbers are not a strict
apples-to-apples comparison -- recorded here as a data point, not a verdict;
`SCALE-GATE.md` owns the renderer question. One real, unplanned finding from
running it: at 252 nodes, GLSP/sprotty's own viewport culling
(`ShapeView.isVisible`, the same mechanism the coordinate bug above
interacted with) left only 54 of 252 nodes with an actual DOM element -- the
rest are off-screen at default zoom and never get rendered at all, which is
a real, working perf characteristic of the stock client, not a defect
introduced here.

## Leverage tables (step 9)

### 1. What upstream performed our job, module by module

| our module/concern | upstream service that performed it here | notes |
|---|---|---|
| `src/40-routing.js` (wire path routing) | none | ELK computes node *position*, not the obstacle-avoiding wire geometry 40-routing.js produces; no upstream primitive does that job |
| `src/50-selection.js` | `@eclipse-glsp/client`'s `selectModule` (in `DEFAULT_MODULES`) | present and wired in `client/app.mjs`; not directly exercised by `client_qa.py` (no click-to-select assertion), but real and running |
| `src/60-interactions.js` | GLSP's tool/mouse-listener framework (`changeBoundsToolModule`, `edgeCreationToolModule`, `nodeCreationToolModule`, `deletionToolModule`, all in `DEFAULT_MODULES`) | present and wired; `client_qa.py` drives the same operations these tools would produce via direct dispatch rather than mouse simulation (no server-side palette to click through -- see "Client" above) |
| `src/70-editor-controls.js` | GLSP's `UndoRedoCommandStack` concept, real but server-owned (see "Which side owns undo") | this spike's server has no operation history, so undo/redo do not function end to end; the palette (`toolPaletteModule`) renders empty since `server.mjs` returns no context actions |
| `src/55-render.js` | none (not exercised) | GLSP's client renders GModel via sprotty views; `RectangularNodeView`/`GEdgeView` are stock geometric shapes, not this codebase's own symbol iconography -- see the SVG export comparison |
| `scripts/export_svg.py` | `@eclipse-glsp/client`'s `ExportSvgAction`/`standaloneExportModule` for the *mechanism*; none for the *visual content* | see "SVG export comparison" -- GLSP's export composes for free from whatever view code renders; the icon/gradient/label rendering itself is not upstream's to give |
| mcp undo/redo/checkpoint | none | GLSP's node-server framework has no equivalent to file-persisted named checkpoints; undo/redo would be its server-side command history (`glspUndo`/`glspRedo`), not implemented in `server.mjs` |
| `validateDocument` surfacing | `RequestMarkersAction`/`SetMarkersAction` (protocol types) | `markersFor()` in `routing.mjs` maps `Data.validateDocument` errors onto GLSP markers; verified both via direct call and via a real client round trip (a refused `createEdge` produces a live `setMarkers` action) |
| node placement layout | `@eclipse-glsp/layout-elk` (via `elkjs` directly) | ran server-side in Node, no browser needed; see layout table above |
| GModel projection itself | `@eclipse-glsp/graph`'s GModel *shape* (types: graph/node/edge/port) | we wrote `adapter.mjs` (107 lines) to produce that shape; the shape itself, its rendering (real client, not mocked), and its JSON-RPC wire protocol, are upstream's |

### 2. Adapter size and cost

| fact | value |
|---|---|
| lines we wrote, server side (`adapter.mjs` + `data-core.mjs` + `routing.mjs` + `server.mjs` + `layout.mjs`) | 107 + 16 + 122 + 126 + 54 = 425 |
| lines we wrote, client side (`client/app.mjs` + `client/view-module.mjs` + `client/webpack.config.cjs` + `client/index.html`) | 65 + 19 + 19 + 13 = 116 |
| lines in test/QA code (`test.mjs` + `client_qa.py` + `evidence/gen_scale_fixture.mjs` + `evidence/scale_measure.py`) | 138 + 209 + 27 + 76 = 450 |
| upstream concepts the adapter/server/client had to learn | GModel tree shape (graph/node/edge/port, id/position/size/children, **child positions relative to parent, not document-absolute** -- the bug above), GLSP action kinds (`requestModel`, `changeBounds`, `createNode`, `createEdge`, `deleteElement`, `applyLabelEdit`, `requestMarkers`/`setMarkers`, `requestTypeHints`/`setTypeHints`, `requestContextActions`/`setContextActions`, `requestExportSvg`/`exportSvg`, `glspUndo`/`glspRedo`), the JSON-RPC-over-WebSocket session handshake (`initialize` incl. `serverActions`, `initializeClientSession`, `disposeClientSession`, `process` notification carrying `{clientId, action}`), the client DI container shape (`initializeDiagramContainer`, `DEFAULT_MODULES`, and that `baseViewModule`/`standaloneExportModule` are *not* in `DEFAULT_MODULES` despite being required for a plain rendering standalone client) |
| upstream npm packages installed (spike) | `@eclipse-glsp/{client,server,protocol,graph,layout-elk,sprotty}` 2.8.0, plus `inversify`, `reflect-metadata`, `ws`, and (dev) `webpack`, `webpack-cli`, `ts-loader`, `typescript`, `css-loader`, `style-loader` |
| `node_modules` size (spike) | ~92 MB; client bundle output (`client/dist/`) 7.3 MB |
| build wall time | server side: none, plain ESM; client: `npx webpack --config client/webpack.config.cjs` ~1-4s once dependencies are installed; upstream reference monorepo (`.tools/glsp-client-ref/`): `pnpm install` 87s, `pnpm build` (compile + bundle + bundle:browser, including downloading a prebuilt server bundle) a few more seconds |
| Node/tool version required | Node v24.11.1, npm 11.6.2, pnpm 11.7.0 (via `npx`) for the upstream reference monorepo only (`package.json` there requires `pnpm >=11`); the spike itself only needs npm |
| native modules compiled | none observed anywhere (`elkjs`, `esbuild`'s postinstall, everything installed here, are pure JS or prebuilt binaries fetched, not compiled) |
| DI framework actually used | client: yes, real `inversify` container via `@eclipse-glsp/client`'s own `initializeDiagramContainer`; server: no -- `@eclipse-glsp/server`'s inversify-based `GModelDiagramModule`/`ServerModule` scaffolding (used by the real `workflow-server` example) was not stood up; `server.mjs` hand-frames the same JSON-RPC wire messages instead, which is why it is 126 lines and not "unchanged upstream" |

### 3. Upgrade burden

Last four stable `@eclipse-glsp/client` releases (npm registry `time` field):

| version | date | gap from previous |
|---|---|---|
| 2.5.0 | 2025-09-07 | -- |
| 2.6.0 | 2026-02-10 | ~5.1 months |
| 2.7.0 | 2026-06-01 | ~3.7 months |
| 2.8.0 | 2026-08-28 | ~2.9 months |

Roughly quarterly, shortening; a `2.9.0-next.1` prerelease had already landed
(2026-09-02, the day this spike ran) the day after `2.8.0` itself. Every
place this spike touched an upstream internal rather than a documented
extension point:

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
- `adapter.mjs`'s GModel shape (`{id, type, position, size, children}`,
  including the parent-relative position convention the coordinate bug
  above found the hard way) was inferred from `@eclipse-glsp/graph`'s class
  shapes and observed wire traffic, not from a schema doc; a future GModel
  shape change would not be caught by any type system here.
- `client/app.mjs` includes `baseViewModule` and `standaloneExportModule`
  explicitly because reading `default-modules.ts`'s source (not any guide)
  showed they are not part of `DEFAULT_MODULES`; the workflow-standalone
  example doesn't need to do this itself because `@eclipse-glsp-examples/
  workflow-glsp`'s own `createWorkflowDiagramContainer` bundles them
  internally, which is not visible from the public API surface this spike
  actually called.

### 4. What we could plausibly stop owning

| file/function | upstream performed | ours still |
|---|---|---|
| node placement (x,y for an initial or auto-layout view) | `@eclipse-glsp/layout-elk` (`elkjs`) | src's own layout code, if any beyond authored x,y -- not audited beyond this spike |
| `validateDocument` -> marker mapping | GLSP's marker protocol (`RequestMarkersAction`/`SetMarkersAction`), verified live in a real client | `Data.validateDocument` itself: legality logic stays ours, unconditionally |
| move/select/create-edge/create-node/delete UI mechanics | `@eclipse-glsp/client`'s tool modules (real, wired, in `DEFAULT_MODULES`) | nothing of ours currently implements this at all, so there is no "ours" here to retire -- the finding is that a from-scratch client gets these for free, not that an existing one could be replaced |
| — | (nothing else confirmed) | `src/55-render.js` (icons, gradients, labels, animation -- no upstream primitive), `scripts/export_svg.py`'s visual content (same reason), mcp undo/redo/checkpoint (server-side history GLSP's protocol expects but this spike's server never built) |

### 5. The adversarial next load (SVG export) -- see "SVG export comparison" above

Composed from the same primitive (`RequestExportSvgAction` dispatched
through the standard `standaloneExportModule`, added to the container as one
line) for the *mechanism*; needed zero bespoke export code beyond that one
module addition and the one `dispatch()` call in `client/app.mjs`. The
*visual content* of the export is a separate question the mechanism does not
answer -- see the size/element-count gap against `scripts/export_svg.py`.

## Protocol exchange

`evidence/protocol.jsonl` -- the JSON-RPC messages captured in `test.mjs`'s
WebSocket round trip (`initialize`, `initializeClientSession`, then `process`
notifications for `requestModel` -> `setModel` and the boundary-crossing
`createEdge` -> `setMarkers`). `evidence/client_qa_result.json` carries the
equivalent summary for the full rendered-client run.
