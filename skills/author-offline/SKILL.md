# SOV Schematic Offline Author Skill — 0.1

## Purpose

Write a `.sov` schematic by hand, from a description of a system, with no editor, browser API, HTTP server, or MCP session. The output is a file. Two scripts stand in for the editor: one validates the file with the same data core the editor runs, and one renders it to a standalone SVG so the drawing can be seen.

Use `skills/author` instead when a live editor or API is available; it has history, checkpoints, and refusals at every step. Use this skill when the only thing you can do is write a file.

## What a schematic says

A document is a semantic model, not a drawing. The renderer projects it, so the file has to say what things are, not how they look.

- A **Component** is a bounded 2D region with a type from the palette (`symbolId`), a label, and up to three built-in attachment points: `in` on the left, `out` on the right, `control` on the top.
- A **Plane** is a bare bounded region. It has no built-in points. It hosts Components in its interior and Points on its boundary.
- A **Point** is a 0D attachment. Hosted on a Plane boundary with face `both`, it is the one legal way a Wire crosses that boundary.
- A **Wire** carries between two attachment points. Both ends must be exposed on one shared surface. There is no reach-through: a Wire cannot start inside a region and end outside it without passing through a boundary Point.
- **Direction, access, and authority are separate axes.** A wire's direction says which way packets go. A port's access (`read`, `write`, `read-write`, `none`) says which operations are representable. Neither grants permission. Permission is a thing in the drawing: an `authority` Component feeding a `control` port.

## Surfaces and ids

Every record lives on a surface. The top level is `canvas:global`. Each Component or Plane with id `X` owns a local surface `canvas:component:X`. A record placed inside `X` carries both `"canvasId": "canvas:component:X"` and `"parentId": "X"`.

Wires carry a `canvasId` too, and the file loader does not fill it in. A wire between two things inside `X` must say `"canvasId": "canvas:component:X"` or it is routed and drawn as if it were on the global canvas. Top-level wires say `"canvasId": "canvas:global"`.

Coordinates are absolute canvas units, and `x`/`y` is the record's centre. A typed Component defaults to 112 by 84. A Point occupies a fixed 24-unit footprint. The default view is about 1200 by 760, but the renderer fits to content, so use whatever extent the drawing needs.

## The authored form

The file loader fills defaults for anything not written: palette presets, port contracts, form body, editor flags. So a record can be short. A preset fills a field only where the record says nothing, so anything you write wins.

Document envelope:

```json
{
  "schema": "soveraeign.schematic/document@0.1",
  "id": "my-schematic",
  "revision": 0,
  "meta": {"title": "What this drawing is"},
  "components": [],
  "wires": [],
  "references": []
}
```

Typed Component on the global canvas:

```json
{"id": "req", "symbolId": "act", "x": 160, "y": 430,
 "config": {"label": "Requester", "signalMode": "source"}}
```

`signalMode` is `source` (emits), `relay` (passes on, the default for most palette entries), or `passive`.

Plane. The preset gives it an open interior, no built-in points, no glyph, no label, and a 320 by 220 size. Write `presentation.size` when the children need more room; write the rest only to override:

```json
{"id": "svc", "symbolId": "plane", "x": 640, "y": 360,
 "config": {"label": "Service", "presentation": {"size": {"w": 560, "h": 260}}}}
```

If you write `form` yourself, write the whole block including `"regions": {"interior": {"state": "open"}}`, because a written `form` replaces the preset form rather than merging with it. The same goes for `presentation`: writing it replaces the preset, so include `"graphic": {"kind": "none"}` and `"labelMode": "none"` alongside the size. A Plane draws no label; the label is for readers of the file.

Point hosted on a Plane boundary. `placement.side` is `left`, `right`, `top`, or `bottom`; `t` runs 0 to 1 along that side. Set `x`/`y` to the matching spot on the edge so the file reads consistently. `face: "both"` is what makes it a crossing:

```json
{"id": "ingress", "symbolId": "point", "x": 360, "y": 425,
 "canvasId": "canvas:component:svc", "parentId": "svc",
 "placement": {"kind": "edge", "hostId": "svc", "side": "left", "t": 0.75},
 "config": {"label": "ingress", "ports": {"out": {"face": "both"}}}}
```

A Point has one attachment point, always addressed as `out`, whichever way packets go through it.

Component hosted inside a Plane. Its centre must lie inside the Plane's rectangle with room to spare:

```json
{"id": "check", "symbolId": "gate", "x": 560, "y": 400,
 "canvasId": "canvas:component:svc", "parentId": "svc", "config": {"label": "Check"}}
```

Wire. `aSide`/`bSide` name the attachment point on each end: `in`, `out`, or `control` on a Component, `out` on a Point:

```json
{"id": "k7", "a": "egress", "aSide": "out", "b": "log", "bSide": "in", "canvasId": "canvas:global",
 "config": {"forwardOperation": "write", "label": "record"}}
```

Wire `config` fields, all optional: `direction` (`forward` default, `reverse`, `duplex`, `none`), `reciprocity` (`none` default, `expected`, `required`), `forwardOperation` and `reverseOperation` (`none` default, `read`, `write`), `label`.

Port override on a Component, for access or face. Write the whole port record; the loader keeps an authored port as-is:

```json
{"id": "rec", "symbolId": "receipt", "x": 800, "y": 300,
 "config": {"label": "RECORD",
            "ports": {"in": {"face": "external", "label": "", "connectionCount": 1, "activeConnection": 0,
                             "connections": [{"id": "connection-1", "colorSlot": 0, "flow": "in", "access": "write"}]}}}}
```

`face` is `external` (reachable from the containing surface, the default), `internal` (reachable from the Component's own interior only), or `both`. A Component that hosts children and needs a wire from a child to the outside gives that port face `internal` or `both`, as in `examples/04-boundary-port.sov`.

## Palette

`symbolId` values and what each means. The full list with verbs and properties is `SYMBOLS` in `src/00-state.js`.

| symbolId | Meaning |
| --- | --- |
| `act` | Transforms input into output. Activity does not grant authority. |
| `hold` | Keeps bounded state. |
| `buffer` | Holds flow temporarily, then releases it. |
| `gate` | Passes or refuses flow using a declared condition. |
| `switch` | Opens or closes a path from explicit control. |
| `limit` | Restricts a flow dimension without judgement. |
| `one-way` | Allows flow in one direction. |
| `return` | Requires a matching return path. |
| `join` | Paths are connected. |
| `cross` | Paths cross but do not connect. |
| `observe` | Reads evidence from outside the action path. |
| `receipt` | Durable evidence emitted by a crossing or action. |
| `authority` | Typed, scoped permission supplied as a control input. |
| `ground` | Reference point used to resolve meaning, state, or authority. |
| `refuse` | Ends an attempted path explicitly. |
| `plane` | Bounded 2D region that hosts Points on its boundary and Components inside. |
| `point` | 0D attachment on a Path, a Plane boundary, or a Wire. |
| `path` | 1D route with start and end that hosts Points. |
| `blank` | Incomplete component whose type is still to be chosen. Do not author these. |

## Layout rules

- Flow runs left to right. Sources on the left, evidence and sinks on the right, control from above or from the upper left.
- Keep at least 200 units between the centres of neighbouring Components on the same row. The router needs room for labels and packets.
- Keep at least 100 units between a Plane boundary Point and the nearest hosted Component edge. Shorter interior wires collapse to stubs that read as missing.
- Size a Plane so every hosted centre is at least 100 units from its edge horizontally and 60 vertically.
- Put boundary Points at `t` values between 0.2 and 0.8 so they do not sit in the corners.
- Wire labels are short. Put the meaning in the Component types and the shape, not in prose on wires.
- One idea per drawing. A file with more than about eight top-level records is usually two drawings.

## Procedure

1. Write the topology as a list before any JSON: each record with its type and role, each wire as `a.side → b.side`, and which surface each wire is on.
2. Decide the regions. Anything that is "inside" something else gets a Plane host and boundary Points for every crossing.
3. Place records on a grid: rows for flow, columns for stage. Compute Plane sizes from their children.
4. Write the file in the authored form above. Set `canvasId` on every wire.
5. Validate: `node scripts/validate_sov.mjs my.sov`. Fix every line it prints. It uses the same checks the editor runs at load, plus the wire `canvasId` check.
6. Render: `python scripts/export_svg.py my.sov --out out/`. Look at the SVG. Check that every wire is visible end to end, nothing overlaps, and hosted records sit inside their host. The export lifts wires inside a Plane above the Plane body; in the editor those wires show when the Plane is entered.
7. Repeat 5 and 6 until the drawing says what the description says. Then hand over the `.sov` and the `.svg` together.

## Anti-patterns

Each pair shows a record that is wrong, what the validator or renderer does with it, and the fix.

**Reaching through a boundary.** A child inside `outer` wired straight to something outside. Refused at load with `Boundary blocks implicit reach-through`.

```sov-refused Boundary blocks implicit reach-through
{"schema": "soveraeign.schematic/document@0.1", "id": "bad-reach", "revision": 0, "references": [],
 "components": [
  {"id": "outer", "symbolId": "buffer", "x": 400, "y": 300, "form": {"dimension": 2, "regions": {"interior": {"state": "open"}}}, "config": {"label": "Outer", "presentation": {"size": {"w": 300, "h": 200}}}},
  {"id": "inner", "symbolId": "act", "x": 400, "y": 300, "canvasId": "canvas:component:outer", "parentId": "outer", "config": {"label": "Inner"}},
  {"id": "ext", "symbolId": "receipt", "x": 800, "y": 300, "config": {"label": "Outside"}}],
 "wires": [{"id": "k1", "a": "inner", "aSide": "out", "b": "ext", "bSide": "in", "canvasId": "canvas:global"}]}
```

Fix: give `outer` a port with face `internal` or `both`, wire `inner.out → outer.<port>` on `canvas:component:outer`, then `outer.<port> → ext.in` on `canvas:global`. `examples/04-boundary-port.sov` shows the Component form; `examples/08-gated-service.sov` shows the Plane form with hosted Points.

**A Plane with a partial `form` or `presentation`.** Writing `"form": {"dimension": 2}` replaces the preset form, so the interior comes out closed and the Plane cannot host anything; writing `"presentation": {"size": ...}` alone drops the preset's `graphic: none` and `labelMode: none`, so the Plane grows a glyph and a label. Not refused. Fix: either omit the block and take the preset, or write it whole.

**Wiring to a bare Plane.** A Plane with `attachmentDefaults: "none"` and no hosted Points exposes nothing, so a Wire ending on it has no surface. Refused at load.

```sov-refused Boundary blocks implicit reach-through
{"schema": "soveraeign.schematic/document@0.1", "id": "bad-bare-plane", "revision": 0, "references": [],
 "components": [
  {"id": "src", "symbolId": "act", "x": 160, "y": 300, "config": {"label": "Source"}},
  {"id": "pl", "symbolId": "plane", "x": 600, "y": 300, "form": {"dimension": 2, "regions": {"interior": {"state": "open"}}},
   "config": {"label": "Region", "attachmentDefaults": "none", "presentation": {"graphic": {"kind": "none"}, "labelMode": "none", "size": {"w": 320, "h": 220}}}}],
 "wires": [{"id": "k1", "a": "src", "aSide": "out", "b": "pl", "bSide": "in", "canvasId": "canvas:global"}]}
```

Fix: host a Point on the Plane's boundary and end the Wire on the Point's `out`.

**A boundary Point without `face: "both"`.** The Point is reachable from outside only, so the interior wire from it to a hosted Component is refused with the reach-through message. Fix: `"ports": {"out": {"face": "both"}}` on the Point.

**Interior wires without `canvasId`.** Not refused. The wire is treated as global, routed around the outside of the Plane, and mostly hidden under it. The validator reports `canvasId missing; both ends are on canvas:component:X`. Fix: set it.

**Hosted record with only one of `canvasId` and `parentId`.** Loads inconsistently: the record may render on the wrong surface or fail to move with its host. Always write both.

**Cramped interior.** Hosted Components placed within 60 units of the boundary Point they connect to. Legal, but the wire is a stub and the reader thinks it is missing. Fix: layout rules above.

**Encoding permission in a wire.** Labelling a wire "allowed" or setting `access` to mean "permitted". Access describes what operations the drawing represents; it never grants. Fix: an `authority` Component wired into the `control` port of the thing it permits, as `examples/08-gated-service.sov` does.

**Data-declared boundary points for interior routing.** `config.attachmentPoints` on a Plane is legal and renders, but wires from those points into the interior route around the outside. Prefer hosted Point records when the wire continues inside.

**Ids reused across kinds, or a wire to a missing id.** Validation reports `duplicate component id` or `missing endpoint component`. Ids are plain strings; keep them short and stable, since wires and hosts refer to them.

## Golden examples

Every file in `examples/` validates and exports. Read the one closest to what you are drawing before writing.

| File | Shows |
| --- | --- |
| `01-source-hold.sov` | Two Components, one forward wire. The smallest drawing. |
| `02-duplex-buffer.sov` | A duplex wire with `reciprocity: expected`. |
| `03-contained-stage.sov` | A Component hosted inside another Component's open interior. |
| `04-boundary-port.sov` | Crossing a Component boundary through an inside-facing port. |
| `05-rate-chain.sov` | Per-record rates composing with the global rate. |
| `06-read-write-evidence.sov` | `write` into a record and `read` by a witness; access without authority. |
| `07-plane-with-points.sov` | A Plane with boundary Points carrying a chain across it. Full saved form. |
| `08-gated-service.sov` | The authored form end to end: a Plane, three boundary Points, an authority into a gate's control, a receipt. Written by hand with this skill. |

## Checks

```
node scripts/validate_sov.mjs file.sov            # exit 0 when valid; prints every problem
node scripts/validate_sov.mjs --compact file.sov  # also prints the compact saved form
python scripts/export_svg.py file.sov --out out/  # standalone SVG, light theme; --appearance dark
```

`tests/author_offline_qa.py` validates every fenced document in this file and every example, and checks the palette table against the source of truth.

## Read/write axis

Treat direction, access, and authority as separate. `direction ≠ access ≠ authority`. A Port access value constrains representable Read/Write packet operations; it does not grant authority.
