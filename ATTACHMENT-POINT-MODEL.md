# Attachment Point Model — 0.1

Port is no longer an independent geometry subsystem. The canonical primitive is a **0D attachment point**.

## Cardinality

Connectivity uses the effective dimension of a Component in its current host surface. Dimension constrains host geometry; it does **not** impose a universal attachment-count maximum:

- 0D → one `self` point.
- 1D → `start` + `end` endpoints.
- 2D → `left` + `right` + `top` as the built-in template defaults; a template may declare additional boundary points by `side + t`.
- A richer Component settled onto a 1D Wire is connectivity-constrained to 1D and therefore exposes only `start` and `end`.

## Contract

Every attachment point owns the same contract: face, direction, access, connection slots, label, and color. Geometry is derived from the host topology.

A 0D Component **is** its attachment point. It does not contain another Port.

## Compatibility

0.1 keeps legacy projections so existing `.sov` documents remain readable:

- `config.ports.in/out/control` stores the authored point contract.
- `parts.ports` is a compatibility projection.
- `parts.points` is the authoritative normalized point projection.
- Wire `aSide/bSide` remain compatibility names while `aAttachment/bAttachment.pointId` stores `start/end/self/left/right/top`.

The compatibility layer is intentionally removable in a future file-format transition.


## Interaction authority

A Wire tap is no longer an authoritative `wire.attachments[]` Port. It is an ordinary **0D Component hosted by the Wire**. Legacy Wire Port/point attachments are migrated into hosted 0D Components during document normalization.

This removes the last intentional event-system distinction between a point on a 1D carrier and a point on a 2D boundary: both use Component attachment descriptors, hit testing, selection, wiring, history, and CRUD. Host dimension changes geometry and exposure surfaces only.


## Primitives and hosted Points (dev, 2026-09-01)

Point, Path, and Plane are palette primitives. Their symbol ids are `point`, `path`,
and `plane`; the legacy `port` id normalizes to `point` on load.

The 2D built-in set (`left`/`right`/`top`) is a template default, not a minimum.
`config.attachmentDefaults` is `standard` (typed Components) or `none` (a Plane).
With `none` the surface exposes only its data-declared `config.attachmentPoints`
and whatever Points are hosted on it. A Wire cannot end on a surface that exposes
no point; the refusal is the same over UI, API, HTTP, and MCP.

A hosted Point is an ordinary 0D Component whose placement is parametric on its host:

| Host | `placement` | Exposure of its `self` point |
| --- | --- | --- |
| Wire | `{kind: wire, wireId, t}` | inside → the Wire's 1D surface · outside → the Wire's canvas |
| 1D Path Component | `{kind: path, hostId, t}` | inside → the Path's local surface · outside → the Path's canvas |
| 2D Plane boundary | `{kind: edge, hostId, side, t}` | inside → the Plane's interior · outside → the Plane's canvas |
| 2D Plane interior | `{kind: surface}` with `canvasId` = the Plane's interior | ordinary interior membership |

`t` survives host movement and resize; world `x`/`y` are derived. Boundary-hosted
Points do not constrain the host's minimum size. Turning `attachmentDefaults` off
(or retyping a Component to a primitive) is refused while a Wire still ends on a
built-in point, so a carrier is never orphaned silently.

Gesture on a 0D form: the inner grip moves it (drag) or selects it (click); the
outer ring is the wiring target. Both are on the same `.node`; no second event path.


## Wire as carrier Path (dev, 2026-09-01)

A Wire record is a 1D Path (`form.dimension = 1`, `role = 'carrier'`). Its ends are
`aAttachment` / `bAttachment`, each either

- bound: `{kind: 'attachment-ref', componentId, pointId}` with `a` / `aSide` projected, or
- free: `{kind: 'free', x, y}` with `a` / `aSide` null.

The boundary of a carrier is its two end Points; binding identifies an end Point with a
Component's attachment point. The surface a carrier runs on is shared by two bound ends,
adopted from a single bound end (the current surface is kept when that end exposes it),
or the surface it was dropped on when both ends are free. Binding an end whose partner is
bound is refused when the two points share no surface; the refusal is the same over
gesture, API, HTTP, and MCP. A free end carries no signal, no packets, and no channel
marker.

Storage: carriers still live in `document.wires` and Components in `document.components`.
That split is compatibility debt of the same kind as `config.ports` versus `parts.points`;
folding carriers into one record kind is a file-format transition, not a runtime change.


## Points anywhere on the perimeter (dev, 2026-09-25)

A 2D card's own boundary points (the built-in `left`/`right`/`top`, and data-declared
`config.attachmentPoints`) are no longer fixed to their default side.
`config.ports.<compatId>.boundary = {side, t}` places one anywhere on the perimeter.
- `side` is `left`, `right`, `top` or `bottom`.
- `t` runs along that side, from 0 to 1.

The attachment core (`pointSpecs`) applies the placement and marks the spec `placed`. So
routing, reachability, rendering, the data core and the graph engine all read one
position.

- **Gesture:** Alt-drag a point to slide it round the card, corners included. It uses the
  same edge resolver that hosts a free Point on a boundary. It snaps to eighths of a side;
  holding Shift as well places it freely. One gesture is one history step. A pinned or
  locked card refuses.
- **Agent path:** a CRUD patch such as
  `{config: {ports: {out: {boundary: {side: 'bottom', t: .25}}}}}`. It is the same over
  the Browser API, HTTP and MCP, with the same receipts and lock refusals. Patching
  `boundary: null` returns the point to its default.

## Seamless terminals (dev, 2026-09-25)

- A point sits **on** the boundary, never standing off it, so a wire meets the body edge
  with no gap. The face (internal / external / both) is shown by the point's style.
- A card's symbol axis is its centre line: the glyph is positioned so its terminal axis
  (`INLINE_TERMINAL_Y`) lands at mid-height. An unplaced side point therefore sits on the
  axis for every symbol, and cards aligned by centre are joined by straight wires.
- A wired side point on the axis draws an inner lead from the body edge to the symbol's
  own lead (`.component-lead`). Wire, edge and glyph read as one line.
- A placed point is off the axis and draws no lead.
