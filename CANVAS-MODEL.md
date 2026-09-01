# Canvas model — 0.1 Beta.7

Canvas is a **model property**, not a UI mode. There is no persistent Canvas mode or context badge in the toolbar.

## Surfaces

- `canvas:global` — root 2D surface.
- `canvas:component:<id>` — local 2D surface exposed when a Component canvas state is `open`.
- `canvas:wire:<id>` — local 1D surface for Wire Parts.

A Component carries `canvasId`, meaning **the surface it currently lives on**. Dragging a Component into an open Component changes `canvasId` automatically. No “enter canvas” action is required.

## Boundary reachability

Ports are exposed to surfaces:

- `outside`/`external` → Component's containing canvas.
- `inside`/`internal` → Component's own local canvas.
- `both` → both surfaces.

A Wire may only be created when its two endpoint Ports are exposed to at least one identical canvas. The Wire is assigned to that shared canvas.

Therefore a child Component cannot wire directly to its container's outside Port. It must use an inside-facing Port (or a `both` Port) exposed to the child's local surface.

**Invariant:** no implicit reach-through across a Component boundary.
