# Section Model · proposed (2026-09-25)

Status: **proposed**. Nothing here is implemented yet. It refines `FORM-MODEL.md` and
changes parts of `ATTACHMENT-POINT-MODEL.md`, `CANVAS-MODEL.md` and
`HOST-SURFACE-MODEL.md`. Those changes are listed under "What this changes" below.

## The idea

Today a Form describes its inside with thickness numbers: `frame.mode` and
`frame.thickness`, `body.thickness`, and `regions.interior.state`. A **Section**
replaces them with a structure: **a set of lines, and the regions between them**.

- A 2D Form (a Plane or a Component) has **closed** lines, nested and read from the
  outside in.
- A 1D Form (a Path or a Wire carrier) has **open** lines, running side by side and
  read across the direction of travel.
- Every region has a **fill**, which is either `solid` (material) or `space` (room for
  other things).

Everything else is derived from those three facts: what a region can host, which
surfaces a Point is exposed to, how an end attaches, and how the Form is drawn.

A 0D Point has no Section.

## Words

| Word | Meaning |
| --- | --- |
| **Line** | One boundary curve of a Form. Closed on a 2D Form, open on a 1D Form. Zero thickness. |
| **Band** | The region between two adjacent lines. Has a `thickness` and a `fill`. |
| **Core** | The region inside the innermost line of a closed Section. Has a `fill` but no thickness. It takes whatever size the lines leave. |
| **Fill** | `solid` or `space`. |
| **Skin** | A solid band on a closed Section. A role name only, not a separate kind. |
| **Bore** / **Lane** | A space band on an open Section. A bore carries through a pipe; a lane carries a carrier inside a strip. Role names only. |
| **Mouth** | The span where a multi-line end is bound to a host (see "Ends"). |

## Shape of the record

```text
form.section
├─ closure: closed | open          derived from dimension: 2 → closed, 1 → open
├─ lines:  [L0 … Ln-1]             n ≥ 1; outside → in (closed), left → right (open)
│   └─ { id, weight, style }
├─ bands:  [B1 … Bn-1]             exactly n-1; Bi lies between L(i-1) and Li
│   └─ { id, fill, thickness, role?, depth? }
└─ core:   { fill }                closed Sections only
```

Invariants:

- `bands.length === lines.length - 1`. The normalizer refuses any other count and
  never repairs it silently.
- Line and band ids are stable across edits. Points and placements refer to them by
  id, not by index, so inserting a line does not re-home anything.
- An open Section has no `core`. A closed Section always has one.
- The editor's first UI caps the line count at 4. The model has no cap.

## The shapes

### Closed Sections (nodes)

| Lines | Bands | Core | Name | Example |
| --- | --- | --- | --- | --- |
| 1 | – | solid | **disk** | a filled terminal, a solid body |
| 1 | – | space | **circle** | an open container, the current open Plane |
| 2 | skin (solid) | space | **section** | a cell with a membrane, a room with walls |
| 2 | skin (solid) | solid | **coated** | a wire in cross-section: insulation around a conductor |
| 4 | solid · space · solid | space | **double wall** | a double membrane, a cavity wall |

### Open Sections (edges)

| Lines | Bands | Name | Example |
| --- | --- | --- | --- |
| 1 | – | **line** | today's Wire |
| 2 | solid | **strip** | a flat conductor, a trace, a ribbon |
| 2 | space | **lane strip** | a bus or cable that carries other carriers inside it |
| 4 | solid · space · solid | **pipe** | walls on both sides, with a bore that carries through |

## Hosting: what each region holds

| Region | Fill | Holds | Placement |
| --- | --- | --- | --- |
| Line (any) | – | Points | `{kind: line, hostId, line, t}` |
| Band | solid | embedded Points and Components (a protein in a membrane, a gland in a wall) | `{kind: band, hostId, band, t, s}` |
| Band | space | Components and carriers, freely; a band is a surface | its own surface id (below) |
| Core | space | Components and carriers, freely | `canvas:component:<id>` (unchanged) |
| Core | solid | nothing | – |

In a placement, `t` is the position along the line or band (0…1 around a closed band,
or from end a to end b on an open one). `s` is the position across the band's
thickness (0 at the outer or left line, 1 at the inner or right line).

Every `space` region is a surface. Surface ids:

- the core of a closed Form: `canvas:component:<id>` (unchanged)
- a space band of a closed Form: `canvas:component:<id>:band:<bandId>`
- a single-line carrier: `canvas:wire:<id>` (unchanged; the 1D surface used for inline hosting)
- a space band of an open Form: `canvas:wire:<id>:band:<bandId>` (a surface in path
  coordinates: `t` along, `s` across)

A solid core holds nothing because it has no line to be parametric along and no room to
place things freely. That is the "zero internal" of a disk.

## Exposure: which surfaces a Point can reach

A Point is exposed to the `space` regions that its position touches, and to nothing else.
This replaces the declared `face` wherever the Section gives the Point a real position.

| Where the Point sits | Exposed to |
| --- | --- |
| On line Li | the space region on each side of Li. The side beyond L0 is the containing surface. |
| Embedded in band Bi, not spanning it | nothing (it is inside material) |
| Embedded in band Bi, spanning it (`s` covers 0…1, flag `through: true`) | the space regions on both sides of Bi: a **through-point** |

Worked through for each shape:

- **Section** (2 lines, solid skin, space core):
  - a Point on L0 touches the outside (space) and the skin (solid), so it is exposed
    **outside only**
  - a Point on L1 touches the skin and the core, so it is exposed **inside only**
  - a through-point in the skin is exposed **both** ways. It is the membrane channel.
- **Circle** (1 line): a Point on L0 touches both the outside and the core. The line has
  no thickness, so position cannot pick a side. For this one degenerate case the Point
  keeps a declared `face` (`external` | `internal` | `both`). **`face` is the thickness
  a one-line Form doesn't have.**
- **Disk** (1 line, solid core): a Point on L0 is exposed outside only, since the core
  is solid. Its `face` is forced to `external`.

The invariant stays **no implicit reach-through**, and it gets a basis: each band is
crossed by a point that spans it, one band at a time. To cross a double wall, a
connection needs a through-point in each solid band, and the space band between them
is a real surface where those two points meet.

`portExposedCanvasIds` (`src/05-data-core.js`) and `attachmentHostSurfaces` become
functions of the Section and the placement. The connection rule, "both ends share an
exposed surface", does not change.

## Ends: how an open Section attaches

The end of a 1-line carrier is a point. It binds as it does today:
`{kind: attachment-ref, componentId, pointId}`.

The end of an n-line carrier (n ≥ 2) is a **segment** across its lines. It binds over a
span of the host:

```text
aAttachment: { kind: span-ref, componentId, line, t0, t1 }
```

- The strip's outer lines L0 and Ln-1 meet the host line at `t0` and `t1`. The span's
  width equals the sum of the strip's band thicknesses. Resizing either one keeps
  `t0 < t1`, or the binding is refused.
- The span is the **mouth**. Each space band of the strip is joined to the host
  region(s) the mouth touches, using the same exposure rules as a Point on that line.
  For example, a pipe mouth on the outer line of a single-line circle opens its bore to
  the circle's core only if the mouth is declared `internal` or `both` (the degenerate
  one-line case). On a Section it opens to the skin side, which is solid, so a through
  mouth is required.
- A carrier in a lane continues through the mouth into the joined surface. That is how
  a vessel enters a cell, or a cable enters a cabinet.
- A free multi-line end is a free segment, `{kind: free, x, y, angle}`.

Joins between strips (a T or Y junction of pipes) are **open** and not specified here.

## Geometry and drawing

- **Closed**: L0 is the Form's outline, as today. Each following line is inset from the
  one before by that band's thickness. A resize that would leave the core with no area
  is clamped at `2 × Σ thickness + minCore`.
- **Open**: lines are offsets of the carrier's route. The route is the centreline, so the
  total width is `Σ thickness`, centred on the route.
- Each line is drawn as a stroke with its `weight`. A band or core is filled by its fill
  (`solid` takes the material colour slot, `space` takes the surface colour).
  `depth` on a band keeps today's `frame.depth` bevel.
- A 1-line open Section draws exactly as today's Wire. Its `weight` is today's
  `body.thickness`.

## Migration from the current Form

`normalizeComponentForm` (`src/05-data-core.js`) and `componentForm` (`src/10-model.js`)
derive a Section when a record has none:

| Current Form | Section |
| --- | --- |
| 2D, `frame.mode = none`, interior `closed` | 1 line · core solid (**disk**) |
| 2D, `frame.mode = none`, interior `open` | 1 line · core space (**circle**) |
| 2D, `frame.mode = frame \| shell`, interior `open` | 2 lines · skin solid, thickness = `frame.thickness`, role = `frame.mode`, depth = `frame.depth` · core space |
| 2D, `frame.mode = frame \| shell`, interior `closed` | 2 lines · skin solid, as above · core solid (**coated**) |
| 1D Path or Wire | 1 line, weight = `body.thickness` |

The migration holds some things fixed:

- A point with `face = internal` on a legacy framed Form is placed on L1, one with
  `face = external` on L0. A point with `face = both` becomes a through-point in the
  skin. So every existing connection keeps the same set of exposed surfaces.
- One exception, and why it is safe. On a **disk** or **coated** Form, the core is
  solid, so an `internal` point is exposed to nothing. Its legacy inside surface was a
  closed interior, which hosts nothing, so no connection can end there. No existing
  connection is lost.
- `regions.interior.state`, `frame.*` and `face` are still written, as projections of
  the Section, in the same way `canvas.state` is a projection today. Readers of
  document@0.1 keep working.
- Removing those fields is a file-format transition (document@0.2), not part of this
  change.
- `formats/schematic.document.schema.json` gains a `form.section` definition. The
  schema already allows extra properties, so the change is additive.

## What this changes in the other model docs

- `FORM-MODEL.md`: Frame and Regions become a projection of Section. `body` keeps
  `kind` and `material`.
- `ATTACHMENT-POINT-MODEL.md`: the `edge` placement becomes `line` (with `edge` read as
  L0). The new `band` placement is added, and so is the `span-ref` end binding.
- `CANVAS-MODEL.md`: band surfaces are added. Exposure is derived from position, with
  `face` kept only on one-line Forms.
- `HOST-SURFACE-MODEL.md`: the settle resolver gains line, band and lane hosts, by the
  same proximity rule.

Every surface (UI, Browser API, HTTP, MCP) goes through the one data core, as today. A
refusal (wrong band count, a mouth that doesn't fit, a crossing with no through-point)
is the same on all of them.

## Open

1. **Strip junctions**: how two or more multi-line carriers join each other.
2. **Anything that changes the line count** (a UI control or an `update` op) must
   re-home or refuse the Points on a line or band it removes. The proposal is to refuse
   while anything is hosted there, which matches today's refusal for orphaned carriers.
3. **`frame` vs `shell`**: this proposal keeps the difference only as a presentational
   band `role`. If shell meant something else, it needs saying.
4. **Naming**: "strip" and "lane" are proposed words for 2-line carriers. Plane is
   already the 2D primitive, so a two-line edge is not called a plane.
