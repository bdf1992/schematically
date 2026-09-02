# SOV Schematic

A compact, AI-native schematic editor. A document is a semantic model — Components, Parts, Wires, Form, boundaries, signals, containment — projected to SVG, not a drawing that pretends to be one. People edit it in the browser; agents edit it through the same data core over a Browser API, HTTP, and MCP.

## The model

- **Point / Path / Plane** — the dimensional basis, and the first three entries in the palette. A 0D Point is an attachment. A 1D Path carries between its two ends. A 2D Plane bounds a region that hosts Points on its boundary and Components in its interior. Each has a minimal default record; the preset lives in `05-data-core.js`.
- **Hosting is attachment** — drop a Point on a Path, on a Plane boundary, or on a Wire and it sticks there parametrically (`placement = {kind: path | edge | wire, t}`), riding along when the host moves or resizes. Drop it inside an open Plane and it is hosted in the interior. A Point on a boundary with face `both` is a crossing.
- **Component** — a typed Plane: a closed boundary with behavior, content, and a Form. Nested Components use the same implementation as root Components.
- **Form** — dimension + Body + Frame + addressable Regions. Dimensions are earned: 0D behaves as an attachable point, 1D as a path/carrier with endpoint topology, 2D as a surface/boundary with addressable boundary attachment points.
- **Attachment points (0D)** — one concern normalizes Port-like behavior everywhere: selection, hit-testing, wiring, color, label, history, and API behavior are identical whether a point lives on a 1D path or a 2D boundary. Built-in boundary points are template data (`config.attachmentDefaults`): typed Components start with left/right/top, a Plane starts with none.
- **Wire = carrier Path** — every Wire is a 1D Form with the carrier role, and each of its two ends is either bound to an attachment point or free in space. Drawing from a port binds both ends; the palette Path drops a carrier with two free ends; an end handle binds when dropped on a Point and frees when dropped elsewhere. Both ends bound and sharing an exposed surface is a connection. Wires can host Components inline (`wireId + t`); duplex Wires carry simultaneous forward/reverse packets.
- **Direction ≠ access ≠ authority** — Ports carry direction (Input / Output / Input + Output / Trigger) and access (None / Read / Write / Read + Write) as independent axes. Read/Write describes the represented effect; it never grants permission.
- **Boundaries are real** — no implicit reach-through. Crossing a Component boundary requires an inside-facing or both-facing Port on that Component, and every surface (UI, API, HTTP, MCP) enforces the same legality.

`ATTACHMENT-POINT-MODEL.md`, `FORM-MODEL.md`, `HOST-SURFACE-MODEL.md`, `CANVAS-MODEL.md`, and `reference/REFERENCE.md` specify these in detail.

## The editor

Semantic undo/redo with gesture compression; named checkpoints persisted in the file; multi-select, marquee, and a semantic clipboard for Component subtrees with their internal Wires; Pin (geometry frozen), Lock (mutation frozen), Hidden (recoverable), Opacity, and per-entity Rate; settle/ghost hosting onto open interiors and Wires with an intentional dwell so growth never creates surprise objects; blank-canvas quick search; light/dark/system appearance with surface-relative ink; a global time scale composed with per-Component and per-Wire rates for packet travel. `EDITOR-KERNEL.md` covers the kernel contract.

## Files and formats

One desktop-style **File** menu: New, Open, Save, Save As, Export SVG, Export Package, Restore Recovery. Editable documents are `.sov`; portable packages are `.sovpak`; browser recovery is deliberately separate from file save. Where the File System Access API exists, Save writes back to the file handle; otherwise it falls back to a download.

- `.sov` → `soveraeign.schematic/document@0.1`
- `.sovpak` → `soveraeign.schematic/package@0.1`
- recovery → `soveraeign.schematic/workspace@0.1`
- CRUD envelopes → `operation@0.1` / `receipt@0.1`

Saved documents carry authored truth only. Runtime projections (local canvas descriptors, boundary/parts, port-level mirrors, realized colors) are rebuilt on load and never written, so a `.sov` is a few lines per entity. Older files that still carry those projections load unchanged.

Schemas live in `formats/`; `DATA-FORMATS.md` explains them.

`python scripts/export_svg.py [file.sov ...] [--out DIR] [--appearance light|dark] [--loop]` renders documents to standalone `.svg` files headlessly (defaults to every example). Computed styles are inlined, so the files render outside the editor, for example as images in markdown. Packet travel times come from path length and rate, so an export animates without ever repeating; `--loop` snaps every animation to a divisor of one period so the file returns to where it began, moving no travel time further than a stated budget. `python scripts/loop_svg.py file.svg --record file.gif` writes one loop as a GIF, animated WebP, or APNG, stepping the SVG clock rather than sleeping between frames. `tests/svg_export_qa.py` keeps the examples exporting and `tests/loop_svg_qa.py` checks that a looped export is actually back at its start after its period. `node scripts/validate_sov.mjs file.sov` validates documents headlessly with the same data core.

## Agent surfaces

`window.SovSchematicAPI` (browser), a REST surface, and an MCP server (`mcp/server.mjs`) all delegate to the same transport-neutral data core — agent-created records cannot bypass editor legality, refusals return receipts without entering history, and history/checkpoints are operable over MCP. See `API.md` and `MCP.md`.

The agent-facing corpus ships with the repository:

- `AGENTS.md` — repository invariants and concern contract
- `skills/author`, `skills/author-offline`, `skills/operator`, `skills/reviewer` — authoring (live and file-only), operating, and reviewing skills
- `examples/` — executable golden documents and a portable reference pack

## Source and build

`index.source.html` + `src/*.js` + `styles/app.css` are the canonical development inputs. `python build.py` produces `index.html`, a deterministic standalone build that opens directly from disk. Module ownership is defined in `MODULES.md`; do not duplicate a concern into another module.

## Quality practice

`python scripts/qa.py` is the single authoritative gate, identical locally and in CI: static checks, browser interaction suites, API/HTTP/MCP parity and conformance, stress and performance watchers, mutation tests, the golden corpus, and syntax checks. Defects found by hand get an issue and, once fixed, a regression suite inside the gate. Pushes to `main` deploy to GitHub Pages only after the gate passes. `LOCAL-SETUP.md` covers machine setup, the local QA loop, and the green-main update pattern; `docs/BRANCHING.md` covers the release flow.

## Direction

The current line stabilizes primitives so future work adds definitions and rules rather than parallel implementations. The concerns ahead, tracked as NEXT issues and sketched in `ROADMAP.md`, `HORIZON-SPACE.md`, and `docs/vision/`:

- a formal Point / Path / Surface cell grammar, with the public Wire concept subsumed into generic 1D Path semantics (primitives, hosted-Point attachment, template attachment defaults, and Wire as a carrier Path with bound-or-free ends have landed; what remains is storing carriers and Components in one record kind, which is a file-format transition);
- data-driven attachment descriptors, domain packs, and data-backed built-ins;
- a small logic machine for particle routing and signal state;
- generalized Spaces — admitted grammars beyond the current 2D canvas, including eventual 3D volume semantics;
- prompt/instruction compilation and richer agent authoring.

Historical acceptance records (`BETA-0.1.md`, `QA-0.1.md`, `RC-0.1.md`, `RC-FINISH-LINE.md`, `PUBLIC-BETA-FREEZE.md`, `MODULE-QA.md`, `contrast-audit.md`) document how past lines were tested and remain as records rather than living documentation.
