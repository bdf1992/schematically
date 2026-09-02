# Module ownership — 0.1

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

- `src/15-editor-kernel.js` — history, checkpoints, semantic clipboard, multi-selection, settle hosting, Pin/Lock/Hidden/Opacity, search/Objects, appearance and rate.

### `src/06-attachment-core.js`
Pure 0D attachment-point topology, dimensional cardinality, host-dimensional projection, and legacy Port/Wire endpoint compatibility mapping. No DOM or rendering authority.
