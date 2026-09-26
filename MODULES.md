# Module ownership — 0.1

- `00-state.js` — runtime state and DOM references.
- `05-data-core.js` — transport-neutral documents, packages, validation, CRUD, reachability, primitive template presets, and compact serialization (`compactDocument`).
- `10-model.js` — Component/Wire/Port semantic normalization.
- `20-ui.js` — panels, palette/grid UI helpers.
- `25-signal.js` — derived signal state.
- `30-canvas.js` — camera, spatial movement and Form-region containment.
- `40-routing.js` — Wire geometry.
- `50-selection.js` — selection projection.
- `55-render.js` — SVG projection and measured wire-label clearance. Canvas scale changes call its placement pass; routing and document geometry remain inputs.
- `65-sim-control.js` — the canvas control plane: one clock drives the graph engine over the live document; projects levels, edges and waiting steps; never writes the document.
- `07-graph-core.js` — graph queries, signals and clocks, access control, and the message simulation (DOM-free; shared with the server).
- `08-layout-core.js` — layouts: views, per-view geometry, placement verbs, routes, the layered engine (DOM-free; shared with the server).
- `58-layouts.js` — layouts in the editor: projection of the layout on screen, the canonical document for files and history, the layout menu, route pinning.
- `57-layout-metrics.js` — measured quality of the rendered projection (`layout.metrics()`); reads the DOM, mutates nothing.
- `60-interactions.js` — pointer/drag gestures.
- `70-editor-controls.js` — selection/form editing controls.
- `75-persistence.js` — File lifecycle, `.sov`/`.sovpak`, shared standalone SVG serialization, recovery, rehydration. The headless SVG script delegates here through the browser API.
- `80-bootstrap.js` — global controls/keyboard/startup.
- `85-api.js` — browser API adapter.

File lifecycle belongs in `75-persistence.js`; no other concern should independently serialize, download, open, or replace schematic files.

The desktop shell lives under `desktop/` (a Tauri crate wrapping the same standalone `index.html`); it does not duplicate file lifecycle. It calls the `opened_document` Tauri command and hands the result to `75-persistence.js` through the same `parseFilePayload` / `applyOpenedPayload` seam file Open already uses — the document-open seam stays in `75-persistence.js`.

- `src/15-editor-kernel.js` — history, checkpoints, semantic clipboard, multi-selection, settle hosting, Pin/Lock/Hidden/Opacity, search/Objects, appearance and rate.

### `src/06-attachment-core.js`
Pure 0D attachment-point topology, dimensional cardinality, host-dimensional projection, and legacy Port/Wire endpoint compatibility mapping. No DOM or rendering authority.
