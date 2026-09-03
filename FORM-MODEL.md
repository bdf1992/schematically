# Form Model

## Field · Form · Model · Mode

Four layers, and every entity in a schematic has all four. Keeping them apart is what stops
the editor from growing a new subsystem each time someone wants a new kind of thing.

| Layer | Answers | Where it lives |
|---|---|---|
| **Field** | what space is it in | `canvasId`, `canvas.dimension`, `placement` |
| **Form** | what dimensional structure is it | `form.dimension` (0–3), `form.body.kind`, `src/04-form-core.js` |
| **Model** | what is it, what does it do | `boundary.inside.type`, `symbolId`, `config.signalMode` |
| **Mode** | how is this instance configured here | `self` · `endpoint` · `boundary` · `carrier` · `port` · `edge` · `face` |

### Field is one thing

A canvas and a gradient are the same primitive. A canvas is a Field whose value is membership —
you are in it or you are not. A gradient is a Field whose value falls off from a source Form. A
field of fields on a field: the global canvas is a Field, the things in it source their own, and
those sit inside it.

They are not split, and the reason is worth keeping: telling them apart would mean making space
itself an authored thing, which is the 3D commitment and not paid for yet. One Field, different
Models, costs nothing now.

The discipline that comes with that: membership decides whether a Wire may connect
(`connectionReachability`). A falloff decides nothing. Reachability must keep reading only the
membership kind, or a gradient silently starts governing what can connect to what.

Standing: only the membership kind is built. A Field carrying a value with a falloff from a
source Form is not implemented. When it is, it should absorb the influence radii that are
currently written out one at a time — `SNAP_RADIUS`, the 24-unit reach for snapping a Point to a
carrier, the 20-unit reach for a Plane edge.

### Mode

Mode is the one that keeps the others small. A Point is one Form. Standing alone it is in
`self` Mode; terminating a Path it is in `endpoint` Mode; sitting on a Plane's boundary it is
in `boundary` Mode. These are not three kinds of object with three implementations — they are
one object, configured three ways. The same holds a dimension up: a Path in `carrier` Mode is
a wire.

```text
Entity
├─ Field   canvasId · placement
├─ Form
│  ├─ dimension: 0 | 1 | 2 | 3
│  ├─ Body: kind (point · path · surface · volume) · material · thickness
│  ├─ Frame: none | frame | shell · thickness · depth
│  └─ Regions
│     └─ interior.state: closed | open
├─ Model   type · behavior · signal
└─ Mode    self | endpoint | boundary | carrier | port | edge | face
```

`interior.state = open` means that region may host Entities. Existing `canvas.state` is
compatibility-only.

## The boundary relation

The Form layer enumerates one relation and derives everything else from it:

> The boundary of a dimension-N Form is an ordered set of dimension-(N-1) Forms.

Applied recursively it bottoms out at 0D, and it is the whole of the dimensional model:

```text
3D volume ──boundary──> 2D faces ──boundary──> 1D edges ──boundary──> 0D points
```

So a Plane's `left` attachment point is not its own species of thing. It is a 0D Point sampled
at the midpoint of the 1D Path that bounds the Plane on its left — and that bounding Path has
its own 0D boundary, the two corners. The point records where it came from in `via`.

Every built-in attachment point in the editor is this relation projected down to 0D:

| Form | Bounded by | Built-in points are |
|---|---|---|
| 0D Point | nothing | itself — `self`, in `self` Mode |
| 1D Path | two 0D points | those two ends — `start`, `end` |
| 2D Plane | four 1D edges | the midpoint of each edge — `left`, `right`, `top` by default |
| 3D Volume | six 2D faces | a point on each face |

The 2D row exposes three of its four edges as a template default. That is a configuration
choice, not a claim about the geometry — `bottom` stays available to authored points, and
`config.attachmentDefaults = 'none'` exposes none of them.

Adding a dimension adds one row to `BOUNDARY` in `src/04-form-core.js`. It does not add a new
kind of thing, a new renderer, or a new attachment system. `tests/form_spine_qa.py` asserts
that: it checks the derived specs against the exact 0.1 contract, walks the 3D→0D descent, and
fails if any dimension's points are re-enumerated by hand.

Examples: painting = 2D / surface / material=canvas; wire = 1D / path / `carrier` Mode;
enclosure = 3D / volume / shell.

## A 1D Form's geometry is its two points

Because the boundary of a 1D Form is its two 0D points, those points *are* its geometry.
`form.geometry.points` holds them as local offsets from the entity's centre, kept antipodal so
the centre stays the midpoint. Length and heading are read back off them:

```text
length = |end - start|        angle = atan2(end - start)        centre = midpoint
```

None of those three is stored anywhere. A derived direction cannot be reset, cannot disagree
with where the points are, and cannot be lost by a cache — which is what used to happen, since
orientation lived only in the runtime pose cache and was dropped whenever the entity moved.
`presentation.size.w` is now a compatibility projection of the derived length.

Dragging either end reshapes the Path: the inner grip moves the point, the ring around it stays
the wiring target — the same split a 0D Point already used for move-versus-wire. A Path settled
onto a host is the exception: there the host imposes the axis, the group is rotated into the
host's frame, and the Path's own points sit on the local x axis.

## Standing

0D, 1D and 2D are authored in the editor. 3D is carried by the Form spine — its boundary
descent, terminal points and Mode assignment all resolve — but no 3D body is drawn or offered
in the palette yet. That is a release gate in `06-attachment-core.js` (`VALID_DIMENSIONS`) and
the editor UI, not a gap in the model.
