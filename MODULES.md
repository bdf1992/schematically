# Module ownership — 0.1

- `00-state.js` — runtime state and DOM references.
- `05-data-core.js` — transport-neutral documents, packages, validation, CRUD, reachability, primitive template presets, and compact serialization (`compactDocument`).
- `10-model.js` — Component/Wire/Port semantic normalization.
- `20-ui.js` — panels, palette/grid UI helpers.
- `22-select-menu.js` — the editor's own dropdown lists. A `<select>` popup is a browser window, not part of the page, so the list is drawn in the document instead; the `<select>` keeps the value and keeps firing `change`. Opened by delegation, so a runtime-built list is covered without registration.
- `25-signal.js` — derived signal state.
- `30-canvas.js` — camera, spatial movement, world angle (`componentHostAngle`: a hosted form's pose, otherwise its own authored `presentation.angle`) and Form-region containment.
- `40-routing.js` — Wire geometry.
- `45-patterns.js` — Patterns: the seven kinds, the Pattern palette section, and the record layer over them — `addPattern`, `selectPattern`, `togglePatternOpen`, `releasePattern`, `renamePattern` and the hulls. A Pattern is a record in `document.patterns`; a Component or Wire belongs to one by naming it in `patternId`. Building one runs the ordinary creation and hosting paths, so the parts are ordinary forms.
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

A free 0D form has no side, so it has no normal and gets no stub: `stubPos` returns
the point itself and a Wire leaves it in whatever direction the route wants. A Point
hosted on a boundary, a Path or a Wire keeps a stub, because there the host has the
normal, not the Point. `pointBodyRadius` is the one radius the body, the grip and the
hit area are all derived from.

`SURFACE_DIMENSION` is 2: the dimension at which a form bounds a region. A 3D Pod is
a surface too, so every "is this a surface" test asks for 2-or-more, never exactly 2.
`Attachment.boundaryDimension` is `min(effectiveDimension, SURFACE_DIMENSION)`, which
is how 3D borrows the Plane's boundary until volume semantics are earned.

### `src/06-attachment-core.js`
Pure 0D attachment-point topology, dimensional cardinality, host-dimensional projection, and legacy Port/Wire endpoint compatibility mapping. No DOM or rendering authority.
