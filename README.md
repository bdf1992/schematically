# SOV Schematic — 0.1 Beta.24

A compact AI-native schematic editor exploring Components, Parts, Wires, Form, boundaries, signals, containment, and transport-neutral CRUD.

## File model

Beta.24 replaces the scattered Save / Load / Clear / Export / Data buttons with one desktop-style **File** menu:

- New
- Open…
- Save
- Save As…
- Export SVG…
- Export Package (`.sovpak`)
- Restore Recovery

Normal editable files use `.sov`. Portable packages use `.sovpak`. Browser recovery is deliberately separate from File Save.

When the browser supports the File System Access API, Save writes back to the selected file handle. Otherwise Save/Save As falls back to a normal browser download with the correct extension.

## Formats

- `.sov` → `soveraeign.schematic/document@0.1`
- `.sovpak` → `soveraeign.schematic/package@0.1`
- browser recovery → `soveraeign.schematic/workspace@0.1`
- CRUD → `operation@0.1` / `receipt@0.1`

See `DATA-FORMATS.md` and `formats/`.

## Source/build contract

The package once again includes its modular development source:

- `index.source.html`
- `styles/app.css`
- `src/*.js`
- `build.py`

`index.html` is the deterministic standalone build and remains directly openable without a web server.

## Beta.24 corner transform grip

- Grouped the three transform controls into a single bottom-right corner grip.
- Right resize, down resize, and diagonal resize now live together so they are less intrusive around the component edges.
- This reduces interference with ports while keeping the same transform behaviors.


## Beta.24 editor utility kernel

Beta.24 establishes the editing utilities required before the public-beta freeze:

- settle/host ghosting with normal parent-child movement after release;
- semantic undo/redo history with gesture and typing compression;
- persisted named checkpoints inside `.sov`;
- Shift multi-select and Shift-drag marquee selection;
- semantic cut/copy/paste/duplicate of Component subtrees and internal Wires;
- Pin, Lock, Hidden, Opacity, and per-entity Rate;
- double-click focus;
- blank-canvas quick typing for object/command search with non-match desaturation;
- Objects fallback panel, including recovery of hidden objects;
- Light / Dark / System editor appearance;
- `?` shortcut disclosure;
- global time scale plus Component/Wire relative rate applied to packet travel;
- effectful Form rendering for material, body thickness, and frame depth.

The quality line for the repository/public Beta is now this utility kernel plus the existing document/API/MCP contracts.

## Public-beta reference corpus

The freeze candidate includes agent-facing skills and executable examples:

- `AGENTS.md` — repository invariant/concern contract
- `skills/author/SKILL.md` — semantic authoring
- `skills/operator/SKILL.md` — Browser API / HTTP / MCP operation
- `skills/reviewer/SKILL.md` — independent structural review
- `reference/REFERENCE.md` — compact language reference
- `examples/01-source-hold.sov` through `05-rate-chain.sov` — classic executable examples
- `examples/classic-reference.sovpak` — portable reference pack
- `PUBLIC-BETA-FREEZE.md` — contracts and known Beta limits


## Beta.24 pre-repo hardening

- Empty-space Wire growth now requires a 360 ms settle dwell. A ghost Component fades in only after the pointer remains stable; releasing before the ghost creates nothing.
- Component drag cleanup is now exception-safe and has missed-release / stale-pointer / runtime-error recovery paths.
- Dark appearance now uses a dark canvas and grid, dark editor surfaces, and paired dark-surface palette realizations.
- Mono has explicit light-surface and dark-surface ramps; semantic palette slot IDs remain unchanged in saved documents.
- Removed the palette Contrast readout. Contrast enforcement remains automatic and is verified by the release audit instead of exposed as a low-value UI meter.

## Beta.24 visual hardening

- Light mode now has an explicitly light, low-contrast canvas grid; dark grid tokens cannot leak into the light canvas.
- Canvas labels, packet tags, endpoint markers, reciprocity marks, ghosts, and badges now use surface-relative ink/halo tokens instead of fixed black/white values.
- Duplex Wires normalize their bound endpoint Connections to `Input + Output`, so a duplex relationship can visibly carry live packets in both directions while remaining explicit in the Port data.
- Light and dark builds are browser-screenshot checked before release.

## Beta.24 host surfaces

Components can settle onto open Component interiors (2D) or Wires (1D) through the same host resolver. Wire-hosted Components retain the same Component record, use normalized `placement.t`, and `backdrop:auto` removes the box. See `HOST-SURFACE-MODEL.md`.


## Beta.24 direction + access

Ports now have two orthogonal behavioral axes:

- **Direction**: Input / Output / Input + Output / Trigger.
- **Access**: None / Read / Write / Read + Write.

Wires keep direction as topology and now declare a concrete per-direction packet operation (`Signal`, `Read`, or `Write`). Read/Write packets render a compact `R` or `W` inside the moving packet. A packet operation is live only when endpoint directions permit the crossing and both bound endpoint Connections permit that access operation.

Invariant: **direction ≠ access ≠ authority**. Read/Write describes the effect being represented; it does not grant permission to perform it.


## Beta.24 — inline Wire anchoring

Wire-hosted Components now anchor and orient as true 1-D residents. After the settle dwell, the ghost aligns to the Wire tangent; release stores `wireId + t`, while world pose is derived. Built-in horizontal-terminal symbols connect exactly to the carrier with no visual gap. Tray adoption now requires the settle ghost for a new host, preventing accidental drops.

## Beta.24 — earned dimensions

3D is removed from 0.1. 1D is a real line form. 0D is a Port-like point attachable to 1D surfaces and 2D edges. See `HORIZON-SPACE.md` for the post-Beta Space direction.


## Beta.24 RC correctness pass

- Built-in dimensional attachment defaults are 0D=`self`, 1D=`start/end`, and the current 2D template=`left/right/top`; these are defaults, **not a universal `dimension + 1` maximum**. 2D templates may declare extra boundary attachment points as data (`side + t`).
- 1D Paths no longer expose a 2D resize grip.
- Snap targeting and wire legality use only the canonical Port set; legacy endpoint references migrate when dimensionality changes.
- A custom Component label replaces the standard type label.
- Delete commits history synchronously, and document edit shortcuts work even after a contextual toolbar disappears.
- Undo, Redo, and Checkpoint are persistent quick actions in the header.

## Beta.24 grid visibility

Fixed a theme-specific CSS override that caused Light appearance to redraw the grid even when `Show grid` was unchecked. Grid visibility is now a single workspace state respected across appearance changes and save/load.

## Beta.24 — 0D attachment-point refactor

Ports are now normalized through one 0D attachment-point concern. See `ATTACHMENT-POINT-MODEL.md`.
