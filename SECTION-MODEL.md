# Section Model · proposed (2026-09-25)

**Built so far (v1, 2026-09-25):**
- the record (`form.section`)
- presets
- validation
- the legacy projection
- drawing
- settings controls

**Also built:** exposure by position.

**Not yet built:**
- hosting in bands
- span ends
- carriers in lanes

See "As built" at the end of this doc.

Status: **v1 built**. The record, the presets, the drawing and the settings controls
exist, and so does exposure by position. Band hosting and span ends are still proposed. It refines `FORM-MODEL.md` and
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

## Groups (reading only)

Built 2026-10-01. Some regions on a drawing are there for the reader, not for the model:
"these three are records, these two are surfaces". A Plane is the wrong tool for that. A
Plane is a boundary, so every relation that leaves it has to be cut into segments through
boundary Points. A group is a separate kind that collects Components without being a
boundary.

**The kind.** `symbolId: 'group'` is a 2D Component that collects other Components for
reading. It is a primitive (no type caption, no legend entry) and is not in the palette:
it is authored as data. Its preset is
`{form: {dimension: 2}, attachmentDefaults: 'none', presentation: {graphic: {kind: 'none'}, size: {w: 320, h: 220}}}`.
Its interior stays closed and it is not a surface: it hosts nothing, it has no ports, and
no Wire ends on it.

**Membership.** `config.members` is an array of distinct Component ids:

```
{"id": "records", "symbolId": "group", "canvasId": "canvas:global",
 "config": {"label": "Records", "members": ["case", "recording", "anchor"]}}
```

A member stays where it is. It keeps its own canvas, its own ports and its own Wires. A
Wire between members of different groups, or between a member and a card in no group, is
one Wire on the canvas they share, joining the two cards directly. No boundary Point is
involved, because there is no boundary to cross.

**Rules.** The data core (`src/05-data-core.js`) checks them in one place,
`groupFindings`. `validateDocument` reports each one at load as
`component <id>: <CODE>: ...`. `create` and `update` refuse an edit that would add one,
with an Error whose message starts with the code, and the document is left unchanged.

| Code | When |
| --- | --- |
| `GROUP_MEMBER_UNKNOWN` | a member names no Component, or `config.members` is not an array |
| `GROUP_MEMBER_CANVAS` | a member's `canvasId` differs from the group's |
| `GROUP_MEMBER_HOSTED` | a member rides on a host: placement kind `edge`, `wire` or `path` |
| `GROUP_MEMBER_GROUP` | a member is itself a group (groups do not nest) |
| `GROUP_MEMBER_TWICE` | one Component is listed by two groups (or twice by one) |
| `GROUP_PORTS` | a group carries `config.attachmentPoints`, or `attachmentDefaults: 'standard'` |
| `GROUP_HOST` | a Component's `placement.hostId` is a group, or its `canvasId` is `canvas:component:<group id>` |

Deleting a Component removes its id from every group's `members` in the same operation.

**Selection.** A click on a group's title or on its ground (any part of its region that no
card or wire covers) selects the group, and the Inspector shows it. A drag from its ground
pans the canvas, as a drag from the blank canvas does. The arrow keys do not move a selected
group, because its region is the union of its members: it follows its cards. QA:
`tests/group_select_qa.py`.

**Geometry.** A group has no geometry of its own while it has members.
`groupRect(doc, groupId, sizeOf)` is the union of the members' rectangles (each centred
on its `x, y`, sized by `sizeOf(component)`), padded `space.regionInset` (24) on each side and `space.regionTitle` (28) more on top
for the title band; both are tokens of the document's resolved notation (the schematic
notation declares 24 and 28, `src/03-notation-core.js`). A child that comes closer than
`regionInset` to its region's edge, or closer than `regionTitle` below its head, is
reported as `region-inset` (LAYOUT-MODEL.md); the renderer never grows a region to fit. It is returned centred like a Component, `{x, y, w, h}`, with its
edges `{l, r, t, b}`. A group with no members is its own `x, y` and `presentation.size`.

**Drawing** (`src/55-render.js`). On each canvas, groups are drawn before every other
node and every wire, so they sit behind them. On the global canvas they are in their own
layer (`#groupLayer`) just before the wire layer; on a Component's interior they sit
directly after the host, before the wires drawn there and the host's children. A group is
`<g class="node group" data-id="<id>">` holding:

- `<rect class="group-region">`: the `groupRect` above with the editor's
  `componentSize`, corner radius `radius.card`, no stroke, the inset filter (see Borders), and
  `pointer-events: none`. It is filled with the group's colour slot at 10
  percent opacity when `config.colorSlot` names a slot other than 0. Slot 0 is the colour
  every record is given, so it reads as unset and the region has no fill.
- `<text class="group-title">`: `config.label` in the title text role, 12 in from the
  left and inside the 28 title band. Its ink is the muted ink, darkened only as far as it
  needs to reach 4.5:1 on the region, the same rule card text follows.

Nothing in a group carries the class `body`. The region follows its members while they
are dragged. A group or plane with `config.intake: true` also holds a
`<rect class="group-outline">` (a group) or draws a dashed body (a plane); see Borders.

**Borders.** What a region's edge is says what the region is, and a picture draws each in one way:

- *No outline, with a soft inset* is grouping only. A group draws no stroke; its region carries an
  inner shadow (the SVG filter `region-inset`, or `region-inset-bare` when the region has no fill
  of its own), offset 1 down and blurred 3 (a Gaussian deviation of 1.5) at the level-1 elevation
  opacity of the appearance. The filter is part of the picture, so an export carries it.
- *Solid* is a boundary that refuses: a plane, a container and a gate card draw a solid outline.
- *Dashed* is open or provisional, and means nothing else. A group or plane with
  `config.intake: true` is an open region and draws its outline dashed `6 4` in the muted ink at the
  structure stroke width. A card whose status declares `outline: dashed` (a missing or proposed
  status) keeps its dashed outline. An unplaced card (`.node.unplaced`) is faded to opacity .42 and
  is not dashed.

These are declared, not written into the renderer: the `schematic` notation's `kinds` list holds five
region kinds, `group` (dash `none`), `plane`, `container` and `gate` (`solid`) and `intake` (`dashed`,
open), and the renderer reads the dash of a region's border from them by id (`regionDash` in
`src/55-render.js`; NOTATION-MODEL.md "Kinds"). A wire kind is declared in the same list.

`config.intake` is a boolean on a group or a plane. Any other value, or intake on any other kind of
Component, is refused on create and update and reported on load with `INTAKE_INVALID`
(`intakeProblems`, `src/05-data-core.js`). QA: `tests/region_border_qa.py`.

**Never an obstacle.** Routing (`src/40-routing.js`) leaves groups out of the obstacles
a route avoids. The layout metrics (`src/57-layout-metrics.js`) leave them out of
`node-overlap`, `route-through-node`, the text-over-a-node check, cramped labels and route
wrapping. The group title is still text, so it counts in `text-collision` against other
text. The layered layout (`src/08-layout-core.js`) does not place groups as cards: it places
each group's members as one block, laid out on its own and padded as the region is drawn, so
the group's region is the block (LAYOUT-MODEL.md "What `layered` does").

The invariant from `CANVAS-MODEL.md` is unchanged: there is no implicit reach-through
across a Component boundary. A group does not weaken it, because a group is not a
boundary. Real containment still gets a Plane with boundary Points.

Golden example: `examples/work-engine/groups.sov`. QA: `tests/group_region_qa.py`.

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

### Card shapes

A card whose outline is one line may declare the shape that line is drawn in:
`config.presentation.shape` is `rect` (the default, also when absent), `cylinder` or `parallelogram`
(`DATA-FORMATS.md` "Card shape"; `shapeProblems` in `src/05-data-core.js` refuses anything else with
`SHAPE_INVALID`). The shape belongs to a 2D Component that is not a group and has a closed interior.
A sectioned Form (two or more lines) keeps the rectangle, as does a card with no backdrop.

The body keeps class `body` and is a `<path>` for the two shapes (`componentShapeGeometry`,
`src/30-canvas.js`), in the card's frame, w x h its bounding rectangle:

- **cylinder**: the bounding rectangle with its top and bottom replaced by the two halves of an
  ellipse `cap = min(0.18 h, 18)` tall and w wide. The near half of the top ellipse is drawn as a
  second line in the outline colour (`<path class="body-rim">`). The inner rectangle is w wide, from
  `cap` below the top to `cap / 2` above the bottom.
- **parallelogram**: skew `s = min(0.2 w, 0.25 h, 24)`; the top edge runs from `-w/2 + s` to `w/2`,
  the bottom edge from `-w/2` to `w/2 - s`. The inner rectangle is `w - 2 s` wide and h tall.

Fill, outline, a status's dashed outline and fade, the elevation shadow and a solid core's bevel
follow the rectangle's rules. The title, the glyph, the status chip and the badges keep to the inner
rectangle. A glyph whose terminals are its points keeps the card's own size, because its ports
follow its scale.

Ports stay on the bounding sides, and routing and every layout metric keep the bounding rectangle
(`componentBounds`, `componentPortLocalPosition`). Where the drawn outline is set back from the
bounding side (a parallelogram's slanted sides, a cylinder's curves away from the centre), a wired
port draws a lead straight in from the port to the outline: `<path class="component-lead shape-lead"
data-point="<id>">`, in the outline colour at the structure stroke width. QA: `tests/card_shapes_qa.py`.

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


## As built (v1, 2026-09-25)

### Record and validation (data core, shared by every surface)

- `form.section = {lines, bands, core?}` is **authored or derived**.
  - `componentSection(c)` reads an authored section, or derives one from the legacy
    `frame` / `regions.interior` fields without writing anything.
  - An authored section is the authority. `frame.mode`, `frame.thickness`,
    `frame.depth` and `regions.interior.state` are written as its projection, so
    document@0.1 readers keep working.
- A band count other than `lines − 1` is **refused** by `validateDocument` for components
  and wires alike. It is never repaired.

### Presets

`sectionPreset(name, dimension)`:

| For | Preset | Structure |
| --- | --- | --- |
| cards | `disk` | one line, solid |
| cards | `circle` | one line, space |
| cards | `section` | a solid skin around space |
| cards | `coated` | a solid skin around solid |
| cards | `double-wall` | 4 lines: solid · space · solid, around space |
| wires | `line` | one line |
| wires | `strip` | a solid band |
| wires | `lanes` | a space band |
| wires | `pipe` | 4 lines: wall · bore · wall |

### Drawing

**Cards.** A closed section draws each inner line as an inset boundary.
- Each region is filled as what it is: solid is the material, space is a wash.
- A band's `depth` keeps the frame's bevel.
- A solid core (a disk, a coated core) is bevelled inside its innermost line, lit from the top
  left, so a solid body does not read as a blank card. Its label is lifted clear of the shade.
- A label and the container guide sit inside the innermost line.

**Wires.** An open section is drawn as nested strokes along the route, outside in, so a
strip or pipe follows every bend. It is drawn symmetric about the route. A wire label is
lifted clear of the section.

### Editing

- The Form settings have a **Section** select for 2D cards.
- The wire settings have a **Section** select for wires.
- Each change is one history step.

`examples/11-sections.sov` shows every preset. `tests/sections_qa.py` covers the whole
of v1.

### Exposure by position (built 2026-09-25)

**Declaring a position.**
- A point on a multi-line boundary declares where it sits: `at: {line}` or
  `at: {through}` (an id or an index).
  - A card's own port takes it on `config.ports.<id>.at`.
  - A boundary Point takes it on `placement.at`.
- Without a declaration, the **face places it**, which is the migration: `external` on
  the outer line, `internal` on the inner line, `both` through the outer band. Every
  legacy document keeps its exposure.

**Exposure** comes from `portExposedCanvasIds` in the data core. Every surface uses it,
so reachability, wire refusals, the simulation and the ACL all follow.
- A point is exposed to the space regions its position touches.
- The region beyond the outer line is the containing surface.
- A space core is the interior surface.
- A through-point on a coated card reaches only the outside, because its core is solid.
- A space band has no surface of its own yet, so crossing a double wall is not
  possible in v1.

**Drawing.**
- A point on an inner line is drawn on that line.
- A through-point is drawn at its band's middle, as a capsule spanning the band.
- The interior fence for routes is the core, so wires stay inside the skin. A route's
  own ends may sit in the skin.

**Editing.** Position selects appear in the port settings (a card's own port) and in the
component settings (a boundary Point). They offer each line and each band, and each
change is one history step.

**The audit** now also refuses a child whose body crosses its container's skin.

`examples/12-membrane.sov` shows it: a channel and a pore through the skin, and a receptor
on the outer line that cannot reach inside. It is covered by `tests/section_exposure_qa.py`.

### Not yet built

- **Hosting in bands**, and space bands as surfaces.
- **Span ends** (`span-ref`) and mouths.
- **Carriers routed inside lanes.**
- **Asymmetric open sections.**
