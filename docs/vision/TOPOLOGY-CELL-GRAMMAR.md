# Post-RC topology: Point / Path / Surface cell grammar

> **Classification: AFTER RC MERGE / NEXT.** This is a design horizon, not an acceptance criterion for `0.1.0-rc1`. The RC only needs a clean attachment/hosting implementation that can support this later without another interaction fork.

## Motivation

The current Beta grew from a diagram editor, so `Wire`, `Port`, `Component`, containment, and boundary behavior accumulated overlapping implementation paths.

The post-RC direction is to describe geometry/topology with a smaller dimensional grammar and make specialized concepts data/configuration over that grammar.

## Candidate dimensional basis

```text
0D Point
1D Path
2D Surface
future 3D Volume only after real spatial semantics exist
```

Boundary relationship:

```text
∂(Point)   = ∅
∂(Path)    = endpoint Points
∂(Surface) = boundary Paths
```

The useful algebraic invariant is that an oriented boundary has no further net boundary: `∂ ∘ ∂ = 0`.

This should be treated as a cell/incidence grammar, not a claim that every useful schematic object is a manifold. Junctions, branching paths, shared boundaries, and composite structures must remain representable.

## Component and Part

A `Component` is an addressable modeled entity with form/semantics/state.

A `Part` is an owned addressable subcell/facet of a Component. Parts may represent boundaries **or interiors**.

Examples:

```text
Surface Chassis
├─ Part: NorthWall : Path
├─ Part: SouthWall : Path
├─ Part: Floor     : Surface
└─ Part: HeaderPin : Point stuck_to NorthWall[t=.5]
```

Ownership and topology remain separate relations:

```text
Chassis owns HeaderPin
HeaderPin sticks_to NorthWall[t=.5]
SignalTrace terminates_at HeaderPin
```

## Wire becomes a Path role

`Wire` should not remain a parallel geometric primitive.

Candidate direction:

```text
Path
├─ role: carrier       # historical Wire
├─ role: boundary      # wall/edge of Surface
├─ role: trajectory
└─ role: divider
```

A historical Wire is therefore a `Path` plus carrier/channel/dynamic configuration.

0.1 file compatibility may preserve `Wire` vocabulary during migration; the conceptual/runtime collapse happens after RC.

## Parametric attachment

Whenever stronger structural coordinates exist, prefer them over free world coordinates.

```text
Point sticks_to Path[t=.5]
Path hosted_by Surface/interior
```

`t ∈ [0,1]` survives parent movement, resize, rotation, alternate rendering, agent regeneration, and serialization more robustly than authored world `x/y` coordinates.

World coordinates become a projection/cache where possible rather than the primary relational truth.

## Attachment cardinality

Dimension determines the type of boundary, **not a universal maximum number of addressable attachment points**.

Current Beta defaults such as:

```text
0D Point   → self
1D Path    → start/end
2D Surface → left/right/top default attachment set
```

are templates, not the post-RC ontology.

A Surface may expose arbitrary public Points on one or more boundary Paths; a domain-defined gate may expose multiple input/output Points; a Path may own midpoint taps or junction Parts.

## Dimensional attachment validation

Candidate default compatibility:

```text
Point → Path       legal: parametric attachment
Point → Surface    legal: interior/boundary placement
Path  → Surface    legal: hosted trace/boundary/divider
Surface → Point    not direct without an explicit reduction/hosting relation
```

Rules should be explicit and data-validatable rather than scattered across renderer gestures.

## Boundary access

A boundary/sub-Part can carry interface policy independently of geometry:

```text
visibility/access: internal | public | tunnel
face: inside | outside | both
direction: input | output | duplex | trigger
operation access: none | read | write | read-write
```

An external carrier can only cross a higher-level boundary through an addressable admitted Point/Part.

## Marks

Marks may target any addressable modeled cell, not only whole Components:

```text
Mark → Point
Mark → Path
Mark → Surface/Part
```

This supports local observation, constraints, evidence, measurements, and validation.

## Data/renderer/runtime requirement

The same semantic record should map losslessly across:

```text
compact authored DSL (optional)
        ↕
canonical JSON/IR + API/MCP
        ↕
deterministic spatial/SVG projection
```

The visual projection is never semantic authority.

## First post-RC proof

A useful topology proof after merge:

1. create a 2D Tray Surface;
2. expose its boundary Paths as Parts;
3. attach several Points parametrically to those Paths;
4. create carrier Paths between Points;
5. move/resize the Tray and verify relative topology remains stable;
6. use the same model through editor, file, API, and MCP;
7. add a small data-defined logic gate using multiple attachment Points;
8. validate/render/replay without host-specific implementation branches.

This work should begin from `dev` after the accepted RC merges to `main`.
