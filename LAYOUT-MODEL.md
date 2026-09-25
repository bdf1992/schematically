# Layout Model · proposed (2026-09-25)

Status: **proposed**. Nothing here is implemented. The goal: one semantic document with
several **layouts**, each suited to a reader. Routes can be pinned. Snapping and dragging
are verbs an agent can call and understand. And the system can *show* its own layout (as
SVG or PNG) and *measure* it, so a person or an agent can judge whether it presents well.

## What exists today

- Positions (`x`, `y`, `w`, `h`) live on each Component record. There is **one layout**
  per document.
- **Routes are never saved.** `routeCache` (`src/00-state.js:130`) is runtime state,
  keyed by the **wire's index**, not its id. The router (`src/40-routing.js`) re-derives
  every route on load and after drags. A route cannot be pinned. `ROUTE_SNAP_GRID = 12`
  makes route channels move in coarse steps.
- **Pin** freezes a Component's geometry. Wires have no pin.
- **Snapping:**
  - grid snap (visible, snap on/off, size)
  - port snap while drawing a wire (`findSnapTarget`)
  - end snap while rebinding a carrier end (`findCarrierSnapTarget`)
  - the settle resolver for hosting (open interior → Wire → world, with a dwell)
  
  All of these are pointer gestures. None is a verb an agent can call with a
  candidate list.
- **Rendering:** the editor's `Export SVG` menu item, and `scripts/export_svg.py`
  (headless Chromium, fits the camera, inlines computed styles). Neither is available
  on the Browser API, HTTP or MCP, so an agent cannot ask to see the diagram.
- `document.layout` is **reserved** (normalized to `{}`) and unused.

## Words

| Word | Meaning |
| --- | --- |
| **Layout** | A named projection of the document: positions, routes, collapse state, visibility and camera. It holds no semantics. |
| **Audience** | Who or what a layout is for, e.g. `overview`, `ops`, `agent`. Declared on the layout. |
| **Route** | The drawn path of one carrier in one layout: `auto`, `guided` or `pinned`. |
| **Unplaced** | An entity that exists in the document but has no position in a given layout. It is reported, never put at (0, 0). |
| **Metric** | A measured property of a rendered layout (crossings, overlaps…). Observed, never declared. |

## 1. Semantics and layout are separate

| Semantic (in the entity record, the same in every layout) | Layout (per layout) |
| --- | --- |
| identity, type, Form, Section, config, signals | `x`, `y`, `w`, `h` |
| which surface or host an entity lives on (`canvasId`, `placement.kind`, `hostId`, `wireId`) | `t` along a host; the side of a boundary point |
| carrier ends and their bindings | the route: waypoints, pins, lane offset |
| groups, definitions | collapsed subgraphs, hidden groups, styling by group, camera |

Hosting is semantic, because *which* host decides reachability. Where along the host an
entity sits is layout.

```text
document.layout
├─ default: <layoutId>
└─ views: {
     <layoutId>: {
       name, audience, engine?,           engine: the layout engine that last arranged it
       nodes:  { <componentId>: {x, y, w, h, t?, side?} },
       routes: { <wireId>: {mode: auto | guided | pinned, via?: [{x,y}], points?: [{x,y}], lane?} },
       collapsed: [componentId…],
       hidden:    { groups: [groupId…], entities: [id…] },
       camera:    {x, y, zoom}
     }
   }
```

- Routes are keyed by **wire id**. That fixes the index keying that is fragile today.
- **Migration:** today's positions become `views.main`, which is the default. Entity
  `x`/`y`/`w`/`h` are still written as a projection of the default view, so
  document@0.1 readers keep working (the same pattern as `canvas.state` today).
- The workspace (local, not in the file) remembers which layout each viewer has open.
  The file only records the default.
- **An entity created while one layout is open** is placed in that layout. In every
  other layout it is **unplaced**:
  - `layout.unplaced(layoutId)` lists such entities
  - the renderer draws them in a marked tray, not at an arbitrary spot
  - `layout.apply` with a place-new option places them with that layout's engine

## 2. Routes and pins

| Mode | Meaning | When the ends move |
| --- | --- | --- |
| `auto` | derived by the router, as today | re-routed |
| `guided` | must pass through the `via` points, in order; the router fills in between | only the segments touching a moved end are re-routed |
| `pinned` | `points` saved exactly | the pinned interior stays; only the first and last lead are re-laid to meet a moved end. If that lead would cross an obstacle, the route is flagged **stale** in metrics, not silently re-routed |

- Pinning a route is the same verb as pinning a Component (`editor.pinned`), applied
  to a carrier in a given layout. Lock still freezes semantic changes. Pin freezes
  geometry.
- The router treats pinned routes as fixed obstacles for auto routes, so that pinning
  one route does not make its neighbours cross it.
- Lanes: carriers inside a lane strip (`SECTION-MODEL.md`) route in the strip's
  coordinates, with `lane` as their offset across it.

## 3. Placement verbs for agents

An agent should say *what relation it wants*, not compute coordinates and replay a drag.
Every verb:
- takes a `layoutId` (default: the document's default)
- supports `dryRun`
- returns a receipt with **what actually happened**: final geometry, what was snapped
  or settled to, and what was refused and why

| Verb | Does |
| --- | --- |
| `layout.move(id, {x, y} \| {dx, dy})` | moves an entity; the result reports any snap applied (grid, alignment) |
| `layout.place(id, relation)` | `right-of` / `left-of` / `above` / `below` another entity with a `gap`, or `inside` a container at `{row, col}` |
| `layout.align(ids, {axis, to})` | aligns left / centre / right / top / middle / bottom |
| `layout.distribute(ids, {axis, gap?})` | spaces the entities evenly |
| `layout.fit(containerId, {padding})` | grows or shrinks a container to fit its contents |
| `layout.attach(pointId, hostId, {t, side?})` | hosts a Point on a host without a drag: the same resolver as settle, called directly |
| `layout.candidates(id, at)` | **what a drop at `at` would do**: ranked hosts, snap targets and ports, each with its distance and whether it is admissible. This is the dwell/ghost state as data. |
| `layout.route(wireId, {mode, via?, points?})` | sets or pins a route |
| `layout.apply(engine, {scope?, options, into?})` | runs a layout engine over the document or a subgraph, either in place or into a new layout |
| `layout.create / copy / delete / rename / setDefault` | manages layouts |
| `layout.unplaced(layoutId)` | lists the entities with no position there |

Pointer gestures go through the same resolvers. A person dropping a Point and an agent
calling `layout.attach` get the same result and the same refusal, like every other
parity rule already in `AGENTS.md`.

**Engines** for `layout.apply` must be deterministic for a given seed:

| Engine | Use |
| --- | --- |
| `layered` | flow left to right by carrier direction; minimises crossings |
| `orthogonal` | compacts an existing arrangement onto the grid, keeping its topology |
| `tree` | hierarchies and fan-outs |
| `radial` | one hub and its neighbours |
| `force` | undirected structure; exploration only |
| `nested` | lays out each open container's interior on its own, then its parent |

Pinned Components and pinned routes are constraints every engine must respect.

## 4. Seeing the result: render verbs

| Verb | Returns |
| --- | --- |
| `render.svg({layoutId, scope?, appearance?, fit?, loop?})` | a self-contained SVG (the `export_svg.py` pipeline: fitted `viewBox`, inlined styles) |
| `render.png({…, scale})` | a raster, for multimodal agents and for posting in chat or pull requests |
| `render.compare(layoutA, layoutB)` | the two renders side by side, with both sets of metrics |

- `scope` can be a subgraph, a group, or a list of ids, so an agent can inspect one
  region at readable size.
- These are served on the Browser API, HTTP (`GET /api/v1/layouts/<id>/render.svg`) and
  MCP (`schematic.render`). Headless rendering uses the existing Chromium runtime in
  `tests/browser_runtime.py`, or its Node equivalent in the server.

## 5. Measuring the result: layout metrics

`layout.metrics(layoutId, {scope?})` measures the rendered geometry. Each metric has a
threshold, and a metric over its threshold is a **finding** with a suggested next verb:

| Metric | Measures | Suggested verb when over |
| --- | --- | --- |
| `crossings` | carrier–carrier crossings, excluding declared `CROSS` points | `layout.apply('layered', {scope})` |
| `overlaps.node` | node–node overlap area | `layout.distribute` |
| `overlaps.label` | a label overlapping a node, a carrier or another label | `layout.move` |
| `throughNode` | a carrier passing through a node it doesn't touch | `layout.route(auto)` |
| `bends` | average and maximum bends per route | `layout.route(guided)` |
| `length` | total and maximum route length relative to straight-line distance | `layout.place` |
| `flowConsistency` | the share of directed carriers running in the layout's main direction | `layout.apply('layered')` |
| `spacing` | gaps below the minimum clearance | `layout.distribute` |
| `offGrid` | entities not on the grid while grid snap is on | `layout.apply('orthogonal')` |
| `legibility` | the smallest label size on screen at `fit` zoom | a larger scope, or collapse |
| `stale` | pinned routes whose leads now cross something | `layout.route` |
| `unplaced` | entities with no position | `layout.apply(…, {placeNew})` |

- A person and an agent get the same numbers. `render.compare` shows them next to each
  other.
- A "good layout" check is then a threshold set that CI can run over the examples, as
  the golden QA runs today.

## As built: measuring (2026-09-25)

`layout.metrics({static})` (`src/57-layout-metrics.js`, Browser API `layout.metrics()`)
measures the rendered SVG in world coordinates. `scripts/layout_audit.py` runs it over
documents the way the SVG export sees them, and `tests/layout_quality_qa.py` holds every
example at 9.5/10 or above.

The score is `10 - Σ min(cap, count × penalty)` over these kinds:

| Kind | Penalty (cap) |
| --- | --- |
| text-overflow | .5 (3) |
| text-truncated | .3 (2) |
| text-collision (with text, a body, or a container's border) | .5 (3) |
| placeholder-text | .1 (2) |
| ghost-mark (an unused point drawn at rest) | .1 (2) |
| faint-structure (a junction or boundary Point drawn under 0.5 opacity) | .5 (2) |
| route-escape | 1 (4) |
| route-through-node | 1 (4) |
| route-jog (a step under 12px between bends) | .25 (2) |
| crossing | .25 (2) |
| node-overlap | 1 (4) |

The rubric is a declared heuristic, not a truth. Each finding names the ids it measured,
so a person or an agent can check it against the picture.

Baseline on 2026-09-25, before the fixes: mean 7.1. Example 09 scored 0, and 07 and 08
scored about 4. After the fixes: 10 on every example.

Still not measured:
- arrowheads on short segments
- label legibility at fit zoom
- a card crowding its container's interior guide

## As built: layouts (2026-09-25)

`src/08-layout-core.js` (`SovSchematicLayout`) has no DOM and is shared by the editor and
the server. It implements §1–3 and the `layered` engine.

### Storage

- The **default** layout is the components' own `x`/`y`/`size`, so a reader that knows
  nothing of layouts sees the default.
- Every other layout is stored at `document.layout.views[id]` as
  `{name, audience, nodes: {id: {x, y, w, h} | {side, t}}, routes: {wireId: route}}`.
- A boundary Point's `{side, t}` is stored per layout, since where it sits along its host's
  edge is layout.
- `default` can move with `set-default`. The old default's geometry is then kept as a
  stored layout.
- An entity with no position in a layout is **unplaced**. It is listed, shown faint and
  dashed where the default has it, and placed by Arrange or by moving it.

### In the editor

- `src/58-layouts.js` shows another layout by projecting it onto the components and
  stashing the default.
- Files, history and every API snapshot see the canonical document through
  `canonicalDiagram()`. Undo, open and checkpoints re-show the active layout.
- The workspace remembers which layout was on screen. The file only knows its default.

**Toolbar layout menu:**
- switch layout
- new layout (a copy of this one)
- Arrange left to right
- rename
- make default
- delete

**Routes.**
- A route is `auto` (routed), `pinned` (the interior points kept) or `guided` (via
  points).
- A pinned or guided route re-lays only its end leads, orthogonally, when terminals move.
- A wire's **Pin** in the settings freezes its rendered route in the layout on screen. A
  straight wire refuses, since there is nothing to pin.

### Verbs

Available on the Browser API (`layout.*`) and MCP (`schematic.layout` with `op`):
- `list`, `unplaced`
- `create`, `rename`, `delete`, `set-default`
- `move`, `place` (`right-of` / `left-of` / `above` / `below` another, with a gap), `align`,
  `distribute`
- `route`
- `apply` with `engine: layered`, `scope` and `into`

Refusals are typed: `PINNED`, `LOCKED`, `HOSTED` (move the host instead), `UNPLACED`,
`UNKNOWN_*`. `schematic.render` takes `view`, so an agent can see any layout.

### What `layered` does

- It lays out left to right by wire direction:
  - cycles are broken
  - layers come from the longest path
  - order within a layer comes from barycentre sweeps
  - each node is pulled level with its predecessors, for straight chains
- A container is laid out inside first and fitted to its contents, then placed as one
  node of its parent.
- A column gap widens to fit the widest wire label that crosses it.
- Afterwards, boundary Points slide to meet what they connect to inside. A Point wired to
  a top or bottom port aims clear of that card. Points sharing a side keep 40px apart.
- A single-connection neighbour outside moves level with its Point when nothing is in the
  way.
- Pinned and locked components stay put.

Every example, arranged, scores 10 on the audit (`tests/layouts_qa.py`).

**Not yet built:**
- `layout.candidates` (settling as data)
- engines other than `layered`
- collapse and hidden groups per layout, which need groups from `GRAPH-MODEL.md`
- a `stale` metric for pinned routes

## As built: seeing (2026-09-25)

`renderStandaloneSvg()` (`src/75-persistence.js`) is the one picture of a document, with
styles inlined and the view fitted to the diagram. The same function serves:
- File → Export SVG
- the Browser API: `render.svg`, and `render.png` via a canvas
- `scripts/export_svg.py`
- the server, through `scripts/render_service.py`: MCP `schematic.render` (a PNG comes
  back as image content), `schematic.layout.metrics`, and HTTP `/api/v1/render.svg`,
  `/api/v1/render.png` and `/api/v1/layout/metrics`

An agent with only MCP can therefore see the diagram and its score before it reports
the work done.

## As built: presentation (2026-09-25)

**Colour carries meaning, not decoration.** There are two accents:
- **amber** (`--accent-out`) is out and rising (`+`)
- **blue** (`--accent-in`) is in and falling (`−`)

Where they are used:
- A wired point gets a short terminal mark on the card edge: amber where work leaves,
  blue where it arrives, both halves for a two-way point, muted for control.
- The live clock uses the same two colours: a high level and a rising edge are amber, a
  falling edge is blue.

**Surfaces.**
- The canvas is warm (`#F6F5F0`).
- A card is a near-white tint of its palette slot (0.955), with a soft shadow.
- A container is a lighter wash (0.975), so it holds its children without a gray mass.

Dark mode has its own values for the accents and the shadow.

## 6. Order of work

1. `document.layout.views` with a `main` view migrated from entity geometry. Route
   cache keyed by wire id.
2. `render.svg` / `render.png` on the Browser API, HTTP and MCP, from the existing
   export pipeline.
3. `layout.metrics`.
4. Route modes and pinning.
5. Placement verbs and `layout.candidates` (settle as data).
6. Layout engines: `layered` and `orthogonal` first.
7. Multiple layouts in the UI: a switcher, create and copy, the unplaced tray. Collapse
   per layout, once groups and definitions from `GRAPH-MODEL.md` exist.

## Open

1. **Should `t` be layout or semantic?** A Point's position along a boundary affects
   nothing semantic today. But in `SECTION-MODEL.md` which *line or band* it sits on is
   semantic. Proposal: line and band are semantic, `t` and `s` are layout.
2. **Layout engine source:** write our own, or vendor one (ELK, dagre) under a pinned
   version. ELK's layered algorithm handles ports and nesting well, but it is large.
3. **Metric thresholds:** one global set, or per audience (an `agent` layout may accept
   density a person wouldn't).
