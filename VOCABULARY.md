# Vocabulary

Seven words. Two ladders, and the break between them is deliberate: the first four
answer *what spatial thing is this*, the last three answer *how are these arranged,
what do they do, and under what reading do they mean anything*. They are not one
axis, and the vocabulary does not pretend they are.

## Form

| | | bounded by |
|---|---|---|
| **Point** | where | — |
| **Path** | through | Points |
| **Plane** | across | Paths |
| **Pod** | within | Planes |

0D, 1D, 2D, 3D. The boundary column is the ladder read downwards: a Pod is bounded
by Planes, a Plane by Paths, a Path by Points, and a Point has no lower-dimensional
boundary to be made of. The palette is this table, one rung per row.

## Composition

| | |
|---|---|
| **Pattern** | together |
| **Program** | behaves |
| **Paradigm** | means |

A Pattern is an arrangement of forms. A Program is a Pattern that does something. A
Paradigm is a set of Programs with settings and instances, held across versions and
differences, that says what any of it means.

Read as roles: Point is identity and location, Path is relation, Plane is context,
Pod is enclosure; Pattern is composition, Program is evolution, Paradigm is
interpretation.

## What exists today

Point, Path, Plane and Pod are the whole palette. Pod is real but flat-bound; the
composition ladder is named and not built, and this document is the only place some
of it exists:

- **Pod** is built as far as a flat canvas allows. It is dimension 3 and it is
  thick: the preset gives it a shell frame and body depth, so it reads as a volume
  rather than a Plane wearing a label. Its boundary is not yet spatial - a Pod
  borrows the Plane's attachment rules through `boundaryDimension`, which is
  `min(dimension, 2)` - so a Point still lands on its edge as if it were 2D. What
  is missing is volume semantics: faces, depth-ordering, and a Pod bounded by
  Planes the way a Plane is bounded by Paths.
- **Pattern** has a palette section and seven entries (`src/45-patterns.js`): PAIR,
  CHAIN, HUB, RAIL, CARRIER, BLOCK, NEST. Each is an arrangement rather than a type.
  Dropping one runs the same creation and hosting paths a person's gestures run, so
  what lands is ordinary forms and Wires; nothing on the record says it came from a
  Pattern, and there is no way to edit one as a unit afterwards. That would be a
  Program.
  BLOCK is the honest replacement for a typed Component: a Plane that came with
  somewhere to attach. The eight typed ids - `act`, `hold`, `buffer`, `gate`,
  `switch`, `limit`, `receipt`, `observe` - are still in `GROUPS.Components` and
  still reachable from the selection bar's type control, so existing documents keep
  working, but they are not offered anywhere in the palette. Re-authoring them is
  open work, and the logic several of them declare today is wrong.
- **Program** and **Paradigm** have no implementation and no record type. Naming
  them here fixes the words so later work does not invent a third vocabulary for
  the same distinctions.

`FORM-MODEL.md` specifies dimension, Body, Frame and Regions.
`ATTACHMENT-POINT-MODEL.md` specifies how a Point attaches to any of them.
