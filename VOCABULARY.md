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

Point, Path and Plane are built and are the whole palette. Everything below that
line is named, not built, and this document is the only place some of it exists:

- **Pod** is declared in `DIMENSIONAL_LADDER` (`src/00-state.js`) with
  `available:false`. It appears in the palette dimmed and cannot be dragged, so the
  ladder reads whole while being honest about what it can do. Building it means
  3D form semantics, not a new palette shape.
- **Pattern** is where the typed Components go. `act`, `hold`, `buffer`, `gate`,
  `switch`, `limit`, `receipt` and `observe` are still in `GROUPS.Components` and
  still reachable from the selection bar's type control, so existing documents keep
  working, but they are no longer offered in the palette: they are compositions of
  the primitives, not siblings of them. Re-authoring each one as a configured form
  is open work, and the logic several of them declare today is wrong.
- **Program** and **Paradigm** have no implementation and no record type. Naming
  them here fixes the words so later work does not invent a third vocabulary for
  the same distinctions.

`FORM-MODEL.md` specifies dimension, Body, Frame and Regions.
`ATTACHMENT-POINT-MODEL.md` specifies how a Point attaches to any of them.
