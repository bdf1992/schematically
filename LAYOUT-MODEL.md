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
| text-contrast (a label under WCAG 2.2's 4.5:1, or 3:1 for large text, against what is painted beneath it) | .5 (3) |
| mark-contrast (a wire, arrow, outline, terminal or junction under 3:1) | .25 (2) |
| code-label (capitals ending in ? or !, shown as if it were words) | 1 (2) |
| cramped-label (clear of a line or a foreign card by under 0.6 of its font size) | .5 (2) |
| route-wraps (a route running outside every card it connects) | 1.5 (3) |
| empty-container (children filling under 20% of the interior) | 1.5 (3) |

Reported in counts and findings, with no weight in the score:

| Kind | Measures |
| --- | --- |
| route-hugs-node | a route segment other than its first and last running parallel to an edge of a 2D card (not a container, not a group), outside it and under 8 from that edge, for an overlap of 16 or more |
| group-overlap | two shown groups on one canvas whose regions (`groupRect`) overlap by more than 1; the detail names each card both groups list |

A card hosted on a wire (drawn inline on the line) is not counted by route-through-node or
route-hugs-node against its own host wire.

The rubric is a declared heuristic, not a truth. Each finding names the ids it measured,
so a person or an agent can check it against the picture.

Baseline on 2026-09-25, before the fixes: mean 7.1. Example 09 scored 0, and 07 and 08
scored about 4. After the fixes: 10 on every example.

The last six kinds came from the first layout review (docs/reviews/2026-09-25-examples.md).
The audit still scored every example 10 while the pictures read 6 to 9. `scripts/layout_review.py`
(skills/layout-review) now puts the audit beside the reviewer's own reading. The reviewer scores
the pictures in a cast reader's voice, and names each disagreement as a rule; the rule becomes a
kind here with a planted case. Contrast is `layout.contrast()` (`src/59-contrast.js`, measured
against the painted backdrop) and `scripts/contrast_audit.py`, which regenerates contrast-audit.md.

Still not measured:
- label legibility at fit zoom: labels hold their screen size, so a small diagram fitted and exported draws them at 4 to 6 world pixels
- a control mark fainter than the in and out marks on its card
- marks crowding marks (a chevron against a junction dot)
- a join drawn as a splice before a gate's single port
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
- A group on the canvas (SECTION-MODEL.md "Groups (reading only)") is placed the same way,
  as one block. Its members in scope on that canvas are laid out by these same steps over the
  wires among them only. The block's box is the members' extent padded 24 on the left, right
  and bottom and 24 + 28 on top, which is the region `groupRect` draws, so placed blocks never
  overlap. Ungrouped cards stay single nodes. A group with no member in scope is left out. A
  canvas with no group runs exactly the steps above, so a document with no groups lays out as
  it did before blocks.
- Blocks are ordered over the groups first, then within each group, as the clustered layered
  drawing does: Graphviz dot clusters (Gansner, Koutsofios, North and Vo 1993: a cluster stays
  contiguous in every rank), ELK Layered hierarchy handling `SEPARATE_CHILDREN` (each cluster
  laid out on its own, then placed as one node), and Forster, "Applying crossing reduction
  strategies to layered compound graphs" (GD 2002: barycentre over clusters, then within). The
  canvas pass runs its barycentre sweeps over blocks and ungrouped cards, with a wire between
  two groups, or between a member and an ungrouped card, as one edge between their nodes. Each
  block is then laid out again with each layer starting in the order of the mean height of the
  cards its members are wired to outside the block (a member with no such wire keeps its place,
  ties keep document order), and the canvas is placed again with the new block boxes.
  `docs/workengine/build_map.py` `order_by_barycentre` did the same by hand.
- Wires between groups route through the column and row gaps the blocks leave. Those gaps
  follow the rules below, so the wires crossing a gap between blocks widen it as they widen a
  gap between cards. The router is unchanged and treats cards, not groups, as obstacles.
- A card listed by two groups (`GROUP_MEMBER_TWICE`, reported by `validateDocument`) is placed
  in the block of the first group in document order that lists it, the one `groupFindings`
  names. The later group's region then reaches into that block and `group-overlap` counts the
  pair. `layered` does not refuse.
- **Rows for a wide grouped canvas.** After the second canvas placement, a canvas that has at
  least one group block and is placed more than 2.5 times wider than tall is placed again in
  rows. Any other canvas keeps the placement above, and a canvas with no group never reaches
  this step. The rule is shelf packing, next-fit, as ELK packs disconnected components into rows
  (`SimpleRowGraphPlacer`, steered by its `aspectRatio` option) and Graphviz `pack` does in array
  mode (`packmode="array"`):
  - the items are the canvas's top-level nodes (group blocks and ungrouped cards) in the order
    the canvas pass placed them, by x (layer), then by y;
  - each row fills left to right; a new row starts when the next item would pass the row width;
    items are top-aligned in their row, and rows stack top to bottom;
  - the gap between items and between rows is `G = max(200, 48 + 6n + 16(L - 1))`, `n` the most
    wires between any two groups of the canvas and `L` the distinct labels among the wires between
    groups: room for a harness's trunks (24 margin each side, 6 a lane, 16 between trunks);
  - the candidate row widths are `W_k = max(widest item, sqrt(A) × (1 + 0.05k))` for `k` 0 to 20,
    `A` the sum over items of `(w + G)(h + G)`; the packing kept is the one whose width / height
    is nearest 1.0, ties to the smaller `k`. The target is square, not ELK's default 1.6: on the
    booth-record fixture only packings near square halved the long horizontal runs (a prototype
    of this rule, 2026-10-03, aspect: runs 0.73: 55, 0.96: 69, 1.14: 72, 1.34: 87, 1.99: 105).
  - Street room: on a packed canvas each group block is laid out again, both block passes, with
    `G` between its rows instead of 56, so a harness street fits under or over a row
    (`STREET_DROP` 36 + its lanes + `STREET_ROOM` 12). Blocks on a canvas that is not packed keep 56.
  - The packing of the top-level canvas keeps its grid: the item ids of each row in packing order
    and the gap `G` it used, for the channels below.
- **Origin.** A top-level layout keeps the diagram where it was: the new layout's top-left card
  corner lands on the old one. The canvas is written at the old corner less the laid-out canvas's
  own top-left card corner, found through group blocks with the offsets the blocks are written at
  (24 right, 24 + 28 down of a block's corner). A canvas with no group has its corner at (0, 0), so
  its layout is unchanged; laying a grouped document out again no longer moves every card by
  (24, 52). A `scope` layout is written inside its container as before.
- **Stale buses.** Before a top-level `layered` lays out a canvas holding two or more groups, it
  deletes every bus of the view whose id starts with `channel-` or whose `between` names two groups
  of that canvas, and every route with mode `bus` that names one of them (those wires return to
  auto). A bus made by hand (no `between`, an id not starting `channel-`) is kept. So an earlier
  layout's buses neither narrow label gaps nor reach bundling, and a grouped document laid out
  twice comes out the same.
- **Channels for a packed canvas.** When the top-level canvas was packed in rows, the wires between
  its items ride channel buses, and the pair bundling below does not run (neither does the
  harness). This is VLSI global routing over a channel intersection graph (Sherwani, *Algorithms
  for VLSI Physical Design Automation*, chapter 6; channel routing, Hashimoto and Stevens 1971),
  drawn with the ordinary bus records, as yFiles' `ChannelEdgeRouter` routes in the channels
  between groups:
  - items are the grid's ids; an item's rect is its group's region (`Data.groupRect`) or its card's
    box; each row's items are sorted by left edge. Row band `k` runs from its least item top to its
    greatest item bottom;
  - channel lines: `Hy[0]` = band 0 top − G/2, `Hy[k]` = midway between band `k−1` bottom and band
    `k` top, `Hy[n]` = last band bottom + G/2; in row `k`, `Vx[k][0]` = first item's left − G/2,
    `Vx[k][j]` = midway between item `j−1`'s right and item `j`'s left, `Vx[k][m]` = last item's
    right + G/2;
  - buses, pitch 6, no `between`, no label, written only when a route names them:
    `channel-row-<k>` horizontal at `Hy[k]` from the least to the greatest x of the gap buses its
    routes join it from or leave it to; `channel-gap-<k>-<j>` vertical at `Vx[k][j]` from `Hy[k]`
    to `Hy[k+1]`;
  - wires: every wire with its two ends on different items (an end's item is the first group in
    document order listing it, else the card itself when it is an item) whose route is absent or
    auto. The sender is `a`, or `b` when `config.direction` is `reverse`. It leaves by the gap right
    of its item (row `ka`, gap `ja + 1`) and enters by the gap left of the receiver's (row `kb`, gap
    `jb`). One gap when they are the same; in one row, exit, `channel-row-<ka+1>`, entry; down the
    grid, exit, `channel-row-<ka+1>`, then for each row in between the gap nearest the entry's x
    (ties to the lower `j`) and the row line below it, entry; up the grid the same with the row
    line above;
  - streets: a member with another member of its group between it and its gap inside its row band
    (the harness's direct test, toward the right for a sender and the left for a receiver) reaches
    the gap along `channel-street-<group>-<row>` under its member row (sending) or
    `channel-street-<group>-<row>-above` over it (receiving), placed as a harness street is
    (first or last lane 36 from the cards), running from the farthest card centre that uses it to
    the gap;
  - each wire gets `{mode: 'bus', buses: [send street?, chain..., receive street?]}` when every
    consecutive pair of its buses meets; otherwise it is left to the router and counted skipped.
  - Two passes. The first lays out and routes with the packing's gaps. Then the grid gap becomes
    `max(G, 2 × 24 + 6 × the most routes naming one channel-row or channel-gap bus)`, and each
    group's row gap the largest, over its member-row gaps, of `STREET_ROOM` 12 plus
    `36 + 6(s − 1) + 4` for `s` wires on the send street under the row and `36 + 6(r − 1) + 4` for
    `r` wires on the receive street over the next (each term only when not 0), never less than `G`.
    The canvas is laid out again with those gaps (items, rows and the area estimate spaced by the
    new grid gap) and routed again; the second pass is kept. On booth-record the first pass needs
    570 (one gap carries 87 wires); at the packing's 200, 34 bus routes ran through cards.
- **Bundles between groups.** At the end of a top-level `layered` (no `scope`) on a canvas holding
  two or more groups that was not packed, the wires between each pair of groups are offered to the
  harness (see "As built: buses" > "Harness"). Pairs are unordered (the harness carries both
  directions on one trunk per label); each pair with 2 or more wires between its members is taken
  in order of wire count descending, then group ids ascending. A pair is skipped when any of its
  wires is pinned, guided, or rides a bus whose `between` is not this pair (`ROUTED_ELSEWHERE`).
  Otherwise the view's buses and routes are kept aside, `harness(doc, view, {between: [a, b]})`
  runs exactly as the harness op runs it, and its result stays only when:
  1. it returns ok (otherwise the reason is the harness's refusal code);
  2. no bus it made meets a third group's region (the bus points' bounding box against
     `groupRect`; `THIRD_GROUP`);
  3. on vertical trunks, every wire it routed flows from the left group to the right one, the
     sending end being `a`, or `b` when `config.direction` is `reverse` (`AGAINST_FLOW`: a lead
     sent right to left leaves its out port on the right and turns back through its own card).
  Otherwise the buses and routes kept aside are put back.
- **Receipt.** `apply` returns `bundles: [{between: [a, b], wires, kept, reason?}]` when bundling
  ran, `channels: {buses, streets, wires, skipped, gap}` when channel routing ran (`gap` the grid
  gap of the second pass; there is then no `bundles`), and `packed: {rows, aspect}` (width /
  height, 2 places) when packing ran; a document with fewer than two groups gets no `bundles`.
  `scripts/layout_sov.mjs` prints, after its `ok` line, `bundled <kept> of <n> group pairs` and
  one line per pair, `<a>,<b>: <n> wires <kept|reason>`; or, when channels ran,
  `channels: <wires> wires on <buses> buses (<streets> streets), gap <gap>`, with
  `, <skipped> skipped` when any was.
- Measured on `tests/fixtures/booth-record-graphify.sov` (113 cards, 9 groups, 262 wires;
  `tests/group_rows_qa.py`, `tests/channel_buses_qa.py`): at dev a902dca the group regions span
  17554 × 2342, aspect 7.50, with 154 horizontal runs of 1000 px or more drawn by cross-group
  wires. At dev 3f3aa75 (packed, pairs bundled): 3 rows, 6840 × 7128, aspect 0.96, 3 of 13 pairs
  bundled carrying 35 of 116 cross-group wires (7 refused as `THIRD_GROUP`, 2 as `AGAINST_FLOW`),
  73 long runs (70 wire runs and 3 buses). With channels (2026-10-03): 2 rows, 10544 × 9572,
  aspect 1.10, 0 region pairs overlapping, 116 of 116 cross-group wires on 47 channel buses (36
  streets) at gap 570, 29 long runs (26 buses and 3 tap legs, none off buses), no bus route
  through a card, no bus band over a card. The seeded fixture of `tests/layered_groups_qa.py`
  (region aspect 5.19 at a902dca) packs too: 40 crossings against 79 laid out group-blind.
  `docs/workengine/map.sov` (aspect 0.47) and `examples/work-engine/groups.sov` (2.01) are not
  packed; their pairs are bundled. All four lay out the same when laid out again.
- A column gap widens to fit the widest wire label that crosses it, or that has an end on
  either side of it: `characters × the notation's caption size × 0.6 + 2 × labelMargin`
  (`labelMargin`, an `apply` option, default 16). A row gap in a column widens the same way
  when a labelled wire joins two cards in different rows of that column, to the caption line
  height plus `2 × labelMargin`. A wire whose label a bus on its route carries draws no label
  of its own (see "As built: buses"), so it widens neither.
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

## As built: crossings (2026-09-25)

A crossing never reads as a junction.

- **Hops.** Where two wires that share no end cross, the later one hops over the earlier with a
  half circle (radius 6.5). The earlier wire runs straight through. It is always the same side:
  over the top going right, and to the right going down.
- **Wires that share an end** (a fan-out or a fan-in) never hop each other. They part at a
  junction dot.
- **Arrowheads** keep 24 clear of every crossing and junction, on both wires.
- **The router** keeps unrelated wires off one track: a collinear touching run costs 260. It
  also keeps them apart when they run side by side closer than 16 for a real stretch, which
  costs 70.
- **The audit** counts `route-overlap` (two unrelated wires on one track).
- A multi-line wire (strip, lanes, pipe) is a band and does not hop.

Tests: `tests/wire_crossing_qa.py`.

## As built: routes clear of cards (2026-10-02)

A wire never runs through a card or along its edge.

- **Obstacles.** Every visible card that is not a group and not a container holding both ends,
  padded by the clearance 12, and the wire's own end cards padded 8 (`routeObstacleSet` in
  `src/40-routing.js`). A card hosted on the wire itself sits on the line and is not in the way.
- **Leads.** The one part of a route allowed inside its own card's padding is each end's lead,
  the stub from the port to its first bend.
- **Search.** The router first tries straight, L, HVH and VHV shapes through the channel lines
  (card edges plus and minus 18, the ends, the midpoints, the lane offset). When none clears, it
  runs A* over the grid of those channel lines from one lead's end to the other's, along grid
  edges that enter no padded obstacle, at cost length + 46 per bend + the crossing (90),
  shared-track (5 per unit) and crowding (260 one track, 70 beside) terms against the routes
  already drawn. This is orthogonal connector routing over a visibility grid (Wybrow, Marriott
  and Stuckey, GD 2009; libavoid; the yFiles EdgeRouter).
- **Blocked.** Only when the grid has no clear route is the old perimeter route drawn, and the
  route is recorded as blocked (`routeBlockedAt(index)`); its wire group carries
  `data-route-blocked="true"`.
- **The cached route** a drag keeps is held to the same rule: a rebuilt route that enters any
  padded obstacle, its own end cards included and leads excepted, is dropped for a fresh one.

Tests: `tests/route_clear_of_cards_qa.py` (the Miro parity frames 4 and 5, a 4 x 4 grid with
12 wires, a row of three, and a pocket only the search clears).

## As built: track gap (2026-10-04)

Two wires that run side by side stand a track apart, so each can be followed by eye.

- **The rule.** `TRACK_GAP` = 10 world units (`src/40-routing.js`), the step `routePoints` already
  uses for a wire's private lane. It is wider than a bus's lane pitch (6, clamped 4 to 16) because
  bus lanes are drawn inside a band and auto-routed wires are not. Two auto-routed wires whose
  parallel middle segments overlap for 24 or more are at least `TRACK_GAP` apart when they share no
  end. When they share an end (a fan-out or a fan-in) they are either on one line (under 0.5 apart:
  one trunk, which the junction dot marks where they part) or at least `TRACK_GAP` apart, never
  between.
- **What never moves.** End leads (a port's stub to its first bend), pinned and guided routes, bus
  routes (lanes and taps), routes frozen by a drag and carriers with two free ends. They are fixed
  segments the others keep the rule against. A move may lengthen or shorten a lead along its own
  line, never below 4 (or what it was), never across.
- **Jogs.** A jog is a middle segment shorter than 10 joining two parallel legs. The leg that is not
  an end lead moves onto the other leg's line (the shorter leg first when neither is a lead), and
  the jog is gone. The move is kept only when the route enters no padded obstacle it was not
  already in (the rule of "Routes clear of cards"), stays in its interior's fence, makes no new
  crossing and leaves no new pair breaking the rule. When both legs are end leads (two ports under
  10 out of line) the jog stays. Jogs go before nudging.
- **Nudging** (`nudgeRoutes(routes, fixed, obstacles)`, called once in `renderWires` after every
  route is drawn and before hops; this is the nudging phase of orthogonal connector routing:
  Wybrow, Marriott and Stuckey, GD 2009; libavoid's nudging and centring; ELK's
  `OrthogonalRoutingGenerator` slots). Segments that break the rule are grouped by channel. Within
  a channel, wires on one line that share an end are one slot and move together; a slot holding a
  fixed segment is an anchor. The free slots are ordered by where their wires come from and go to
  at the two ends of the channel (metro-line ordering: an arm leaving inside another segment's
  span puts its segment on the side the arm goes, so it adds no crossing), then spread `TRACK_GAP`
  apart, centred where they were, kept a gap from the anchors. Each route stays connected: the
  neighbouring segments stretch. A spread is kept only when the routes enter no new padded
  obstacle, keep every segment's direction, make no new crossing, and the channel breaks the rule
  less than before; otherwise the spread is shifted, then narrowed a unit at a time down to 2.
- **Cramped.** When a channel has no room for its group, it is spread as far as the room allows.
  The wires still closer than `TRACK_GAP` carry `data-track-cramped="true"` on their wire group.
- **Off switch.** `window.ROUTE_NUDGE=false` turns jogs and nudging off, for tests only.
- **The audit** counts `route-close-parallel`: two wires, not both inside one bus band, with middle
  segments 0.5 to under `TRACK_GAP` apart overlapping 24 or more, end leads left out, shared end or
  not. It has no weight in `LAYOUT_RUBRIC`. `route-overlap` and `route-jog` keep their definitions.

Measured (static metrics after `fitDiagram`), before then after: before is `window.ROUTE_NUDGE=false`,
which draws dev e509171's routes, so `route-close-parallel` can be counted on them too:

| Document | route-overlap | route-close-parallel | route-jog | crossing |
| --- | --- | --- | --- | --- |
| `tests/fixtures/mixed-waves.sov` (the H3 case) | 0, 0 | 0, 0 | 1, 0 | 1, 1 |
| `tests/fixtures/task-lifecycle.sov` | 0, 0 | 2, 0 | 0, 0 | 0, 0 |
| `tests/fixtures/work-engine-sample.sov` | 0, 0 | 0, 0 | 0, 0 | 0, 0 |
| `docs/workengine/map.sov` | 23, 23 | 0, 0 | 2, 2 | 185, 185 |

On the H3 case w5's 8 px jog under the saw trunk is gone and w5 shares w3's trunk from saw:out to
x 368. On the order-only map (`check_map.py --routing`) crossing goes 208 to 207 and route-overlap
21 to 18.

Tests: `tests/track_gap_qa.py`.

## As built: wire labels (2026-10-04)

A wire's label sits beside its wire, clear of everything else drawn, or says that it could not.
The method is line-feature label placement by candidate positions slid along the line, nearest
the preferred position first (Christensen, Marks and Shieber, "An Empirical Study of Algorithms
for Point-Feature Label Placement", 1995; map renderers place road names the same way).

- **Where.** `placeWireLabels` (`src/55-render.js`) runs after every wire is drawn and again on
  every zoom, pan and resize. It moves labels only: no route changes and no label is hidden or cut.
- **Screen units.** A label holds a screen size (12 to 16 px), so its size in world units changes
  with the zoom. The clearance (6) and the slide step (12) are screen pixels too.
- **Candidates, in order.** First the wire's midpoint and the midpoint of each segment, on both
  sides of the line, nearest the wire's midpoint first. Then, on every straight run at least as
  long as the label plus twice the clearance, a place every 12 px on both sides, outward from the
  run's middle and never past its ends less the clearance, nearest the wire's midpoint first.
- **What a label meets.** A card body (a card drawn on a wire counts by its bounds), a container
  border (a label lies wholly inside a container or wholly outside), a status chip or marker
  badge, other text (titles, subtitles, port labels, group titles, bus labels, end tags, labels
  already placed) and another wire's segment.
- **Three tiers.** The label takes the first place, in the order above, whose box padded by the
  clearance meets nothing. With no such place, a place whose box with no padding meets nothing
  (of those, the one that meets least when padded, the earliest on a tie). With none of those,
  the place of least overlap with no padding.
- **Crowded.** `data-label-crowded="true"` is on a label whose final place truly overlaps
  something in the list above, with no padding. A label that only misses the clearance does not
  carry it. A label already at its place is not rewritten, so placing twice gives the same
  coordinates.
- **Two drawings.** The picture (`renderStandaloneSvg`) and static metrics draw labels at their
  base size; the fitted view on screen holds the 12 px floor, so on a wide document its labels are
  several times larger in world units and more of them are crowded. The mark describes the
  drawing it is read in.
- **What it cannot do.** A label longer than every straight run of its wire has only the midpoint
  places, and a wire shorter than its label between two close cards has no clear place.

Measured at 1600 x 1000 after `fitDiagram`, before then after. A label collision is a
text-collision finding of static metrics that names the label's wire and quotes its text; the
marks in the picture are read in the same drawing (`withPictureLabels`):

| Document | Labels | Label collisions | Crowded in the picture | Crowded in the fitted view (zoom) |
| --- | --- | --- | --- | --- |
| `tests/fixtures/task-lifecycle.sov` | 9 | 1, 1 | not marked, 1 | not marked, 2 (0.28) |
| `tests/fixtures/work-engine-sample.sov` | 13 | 1, 0 | not marked, 0 | not marked, 5 (0.32) |
| 12 act cards and 14 labelled wires laid out by `layered` | 14 | 0, 0 | not marked, 0 | not marked, 6 (0.44) |
| `docs/workengine/map.sov` | 1 | 0, 0 | not marked, 0 | not marked, 0 (0.24) |

Known residual: on task-lifecycle 'push, through the broker' (w5) still overlaps Commits and is
marked crowded. Its wire, from Commits to GitHub's border, is 130 world units and the label is 137
wide at base size, so no label move clears it; it needs a wider gap. Held by task
`schematically-a-wire-label-has-room-on-its-wire`.

Tests: `tests/wire_label_placement_qa.py`, `tests/wire_label_clearance_qa.py`.

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

## As built: buses (2026-10-02)

At map scale (`docs/workengine/map.sov`, about 70 cards) every wire finding its own path makes a
tangle. A **bus** is a route declared once in a layout; wires name it instead of each finding a
path. This is the yFiles bus descriptor model (the bus is the record, a wire only names it), and
the harness below is VLSI standard-cell channel routing (cards in rows, wires in the channels
between them). Routing stays presentation: a bus is a layout record, never a Wire or a Path in
`doc.wires`, it hosts nothing, and no wire's ends, ports, surface or config change.

### Record

```text
document.layout.views[<layoutId>].buses[<busId>] = {
  points: [{x, y}, ...],    2 or more; every step horizontal or vertical
  pitch:  4..16 (6),        distance between lanes
  label?, between?: [groupA, groupB], order?: [wireId, ...]
}
document.layout.views[<layoutId>].routes[<wireId>] = {mode: 'bus', buses: [busId, ...]}
```

`ensure()` keeps `buses` an object on every view, the default included, drops an `order` entry
naming a wire that is gone, and drops a route that names a bus that is gone (the wire returns to
`auto`). A new layout copied from another copies its buses with its routes.

### Ops

`schematic.layout` (`src/08-layout-core.js`), the Browser API `layout.*` (`src/85-api.js`, through
`runLayoutOp`) and MCP serve the same ops:

| Op | Does |
| --- | --- |
| `bus {id, points, pitch?, label?, order?}` | sets one bus |
| `bus {id, remove: true}` | removes it; every wire that named it returns to `auto` and is listed in the receipt |
| `buses {view?}` | read-only: every bus with the wires that name it |
| `route {wireId, mode: 'bus', buses}` | puts a wire on buses, in the order it rides them |
| `harness {between: [groupA, groupB], pitch?}` | builds the buses between two groups and routes their wires on them (below) |

`scripts/layout_sov.mjs file.sov --no-arrange --harness groupA,groupB [--harness ...]` runs harnesses
from the command line, after any arranging, in order, printing each receipt. With `--no-arrange` the
file is written as it was read with only its `layout` replaced.

### Harness

Between two groups (SECTION-MODEL.md "Groups"), using their regions from `Data.groupRect`:

- **Wires**: those with one end a member of each group, except wires whose route is pinned or guided.
- **Trunks**: one per distinct wire label, sorted by label, id `harness-<groupA>-<groupB>-<label slug>`,
  carrying its label. Side by side groups get vertical trunks centred in the gap, spanning both regions
  (and any street below or above them); stacked groups get horizontal ones. Trunks sit 16 apart.
- **Direct line**: a member has one when no other member of its group lies between it and the trunk
  inside its row band (its card's vertical extent, for a vertical trunk).
- **Streets**: a sending member without a direct line gets a street in the gap under its row, its first
  lane 36 below the row's lowest card edge, running from the group's far edge to the farthest trunk it
  needs, id `street-<group>-<row>`. A receiving member's street is in the gap above its row, its last
  lane 36 above the row's top edge, id `street-<group>-<row>-above` (the suffix keeps a group that both
  sends and receives from naming two streets alike). An id another harness already holds takes `-2`.
- Each wire gets `{mode: 'bus', buses: [sending street?, trunk, receiving street?]}`. Running the
  harness again for the same pair replaces its buses.
- `layered` runs the harness itself, between each pair of groups on the top-level canvas, after
  laying it out, and keeps a pair's buses only on the three conditions in "What `layered` does"
  (Bundles between groups). `tests/group_rows_qa.py` measures it on the booth-record fixture.
- A packed canvas uses channel buses instead ("What `layered` does", Channels for a packed
  canvas): `channel-row-*`, `channel-gap-*` and `channel-street-*` records with no `between`,
  drawn as any bus is. `tests/channel_buses_qa.py` measures them on the booth-record fixture.

### Refusals

| Code | When | Carries |
| --- | --- | --- |
| `BAD_POINTS` | a bus with fewer than 2 points or a diagonal step | |
| `UNKNOWN_BUS` | a route or a removal names a bus not on the layout | |
| `BUS_GAP` | two consecutive buses of a route neither cross nor touch | `buses` |
| `GAP_TOO_NARROW` | the gap is narrower than the trunks (lanes × pitch each, 16 between) plus 24 each side | `need`, `have` |
| `STREET_TOO_NARROW` | a street's last lane plus 12 does not fit before the next row (or after the previous one) | `need`, `have`, `street` |
| `UNKNOWN_GROUP`, `BAD_BETWEEN`, `NO_WIRES` | the harness has no two groups, or nothing to route | |

A refusal changes nothing.

### Drawing (`src/41-buses.js`, `src/55-render.js`)

- **Lanes**: on a bus with n wires, lane offset = (index − (n − 1) / 2) × pitch, perpendicular to each segment.
- **Tap on**: the end of the source lead (the router's `routeLead`) is projected onto the first bus's
  centreline, clamped to its extent and offset by the wire's lane, and joined by one orthogonal L whose
  first leg continues the lead. The wire rides each bus on its lane and turns once where two buses meet,
  where the two lanes meet. **Tap off** is the mirror of tap on.
- **Lane order**, once per render, before any auto route: a bus's own `order` when it has one. Otherwise
  wires start in the order they leave the bus (ties by where they join, then wire id); that order and its
  reverse are both measured and the one with fewer crossing pairs is kept; then up to 8 passes of adjacent
  swaps keep a swap only when the crossing pairs among that bus's wires strictly drop (the greedy form of
  the slot ordering in ELK's `OrthogonalRoutingGenerator`). Two wires sharing no end that run on one track
  count as a crossing pair.
- Bus routes go into `occupied` before any auto route, so auto routes keep clear of them. A pinned or
  guided route still wins; a bus route that cannot be built falls back to the router, and its wire group
  carries `data-bus-fallback`.
- Each bus is a band in `#groupLayer` after the group regions: width n × pitch + 8, rounded ends, the
  muted ink at about 6%, its edge in the structure stroke at low opacity (`.bus-band`, `data-bus-id`;
  light and dark in `styles/app.css`). A labelled bus draws its label once (`.bus-label`) beyond its
  start, reading along it.
- Two wires on one bus draw no hop where they cross inside that bus's band; every other hop is unchanged.
- A wire's own label is not drawn when a bus it rides carries the same text; the label stays in the data
  and the API. Wires keep their own paths, arrows, colours and packets.

The rubric (`LAYOUT_RUBRIC`, `src/57-layout-metrics.js`) is unchanged and judges the result.
Tests: `tests/routing_buses_qa.py`; `python docs/workengine/check_map.py --routing` on the map.

**Measured on the Work Engine map** (`scripts/layout_audit.py`): on dev at 8dfde33, 665 crossings,
110 route-overlap, 7 route-wraps, 22 route-through-node and 80 text-collision. With card order alone
(barycentre, `build_map.py --no-buses`): 207 crossings, 29 route-overlap, 2 route-wraps, 5
route-through-node, 80 text-collision. With order and both harnesses: 185, 23, 0, 0, 75.
Text-collision follows the fitted zoom more than the routes: labels keep their screen size, so a
wider picture is fitted smaller and titles crowd their subtitles.

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
