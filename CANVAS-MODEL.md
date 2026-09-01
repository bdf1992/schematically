# Canvas model — 0.1

Canvas is a **model property**, not a UI mode. In prose this document and `GLOSSARY.md` call it a surface.

## Surfaces

- `canvas:global` — root 2D surface.
- `canvas:component:<id>` — local 2D surface exposed when a Component canvas state is `open`.
- `canvas:wire:<id>` — local 1D surface for Wire Parts.

A Component carries `canvasId`, meaning **the surface it currently lives on**. Dragging a Component into an open Component changes `canvasId` automatically. No “enter canvas” action is required.

## Boundary reachability

Ports are exposed to surfaces:

- `external` (Outside) → the Component's containing surface.
- `internal` (Inside) → the Component's own interior surface.
- `both` → both surfaces.

A Wire may only be created when its two endpoint Ports are exposed to at least one shared surface. The Wire is assigned to that surface.

Therefore a child Component cannot wire directly to its container's outside Port. It must use a parent Port whose face is Inside or Both, which is exposed to the child's surface.

**Invariant:** no implicit reach-through across a Component boundary.
