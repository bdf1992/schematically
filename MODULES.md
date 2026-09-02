# Module ownership — 0.1

- `00-state.js` — runtime state and DOM references.
- `05-data-core.js` — transport-neutral documents, packages, validation, CRUD, reachability, primitive template presets, and compact serialization (`compactDocument`).
- `10-model.js` — Component/Wire/Port semantic normalization.
- `20-ui.js` — panels, palette/grid UI helpers.
- `25-signal.js` — derived signal state.
- `30-canvas.js` — camera, spatial movement, world angle (`componentHostAngle`: a hosted form's pose, otherwise its own authored `presentation.angle`) and Form-region containment.
- `40-routing.js` — Wire geometry.
- `50-selection.js` — selection projection.
- `55-render.js` — SVG projection.
- `60-interactions.js` — pointer/drag gestures.
- `70-editor-controls.js` — selection/form editing controls.
- `75-persistence.js` — File lifecycle, `.sov`/`.sovpak`, recovery, rehydration.
- `80-bootstrap.js` — global controls/keyboard/startup.
- `85-api.js` — browser API adapter.
- `87-live.js` — live link: publishes a read-only snapshot of this editor session (file, revision, camera, selection, document) to a local server. Off unless started; no other module talks to the link.

File lifecycle belongs in `75-persistence.js`; no other concern should independently serialize, download, open, or replace schematic files.

The desktop shell lives under `desktop/` (a Tauri crate wrapping the same standalone `index.html`); it does not duplicate file lifecycle. It calls the `opened_document` Tauri command and hands the result to `75-persistence.js` through the same `parseFilePayload` / `applyOpenedPayload` seam file Open already uses — the document-open seam stays in `75-persistence.js`.

- `src/15-editor-kernel.js` — history, checkpoints, semantic clipboard, multi-selection, settle hosting, Pin/Lock/Hidden/Opacity, search/Objects, appearance and rate.

`SURFACE_DIMENSION` is 2: the dimension at which a form bounds a region. A 3D Pod is
a surface too, so every "is this a surface" test asks for 2-or-more, never exactly 2.
`Attachment.boundaryDimension` is `min(effectiveDimension, SURFACE_DIMENSION)`, which
is how 3D borrows the Plane's boundary until volume semantics are earned.

### `src/06-attachment-core.js`
Pure 0D attachment-point topology, dimensional cardinality, host-dimensional projection, and legacy Port/Wire endpoint compatibility mapping. No DOM or rendering authority.
