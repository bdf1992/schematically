# Module ownership — 0.1

- `04-form-core.js` — the Form spine: dimension, the boundary relation, and Mode. Loads before every other module and depends on none.
- `00-state.js` — runtime state and DOM references.
- `05-data-core.js` — transport-neutral documents, packages, validation, CRUD, reachability, primitive template presets, and compact serialization (`compactDocument`).
- `10-model.js` — Component/Wire/Port semantic normalization.
- `20-ui.js` — panels, palette/grid UI helpers.
- `25-signal.js` — derived signal state.
- `30-canvas.js` — camera, spatial movement and Form-region containment.
- `40-routing.js` — Wire geometry.
- `50-selection.js` — selection projection.
- `55-render.js` — SVG projection.
- `60-interactions.js` — pointer/drag gestures.
- `70-editor-controls.js` — selection/form editing controls.
- `75-persistence.js` — File lifecycle, `.sov`/`.sovpak`, recovery, rehydration.
- `80-bootstrap.js` — global controls/keyboard/startup.
- `85-api.js` — browser API adapter.

File lifecycle belongs in `75-persistence.js`; no other concern should independently serialize, download, open, or replace schematic files.

The desktop shell lives under `desktop/` (a Tauri crate wrapping the same standalone `index.html`); it does not duplicate file lifecycle. It calls the `opened_document` Tauri command and hands the result to `75-persistence.js` through the same `parseFilePayload` / `applyOpenedPayload` seam file Open already uses — the document-open seam stays in `75-persistence.js`.

- `src/15-editor-kernel.js` — history, checkpoints, semantic clipboard, multi-selection, settle hosting, Pin/Lock/Hidden/Opacity, search/Objects, appearance and rate.

### `src/04-form-core.js`
The dimensional spine. Owns one relation — the boundary of a dimension-N Form is an ordered set of dimension-(N-1) Forms — and the Mode vocabulary that says how an instance is configured where it sits. Every built-in attachment point in the editor is that relation projected down to 0D, so a Path's endpoints, a Plane's edges and a Plane's boundary points are one system at three depths rather than three systems. Pure: no DOM, routing, rendering, or editor state, and no dependency on any other module.

### `src/06-attachment-core.js`
Pure 0D attachment-point topology, dimensional cardinality, host-dimensional projection, and legacy Port/Wire endpoint compatibility mapping. Built-in point specs are derived from `04-form-core.js`; this module adds only the legacy per-side `in`/`out`/`control` contract and the authored 2D extras. No DOM or rendering authority.
