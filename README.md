# SOV Schematic

A compact, AI-native schematic editor. A document is a semantic model — Components, Parts, Wires, Form, boundaries, signals, containment — projected to SVG, not a drawing that pretends to be one. People edit it in the browser; agents edit it through the same data core over a Browser API, HTTP, and MCP.

## The model

- **Component** — a closed boundary with behavior, content, and a Form. Nested Components use the same implementation as root Components.
- **Form** — dimension + Body + Frame + addressable Regions. Dimensions are earned: 0D behaves as an attachable point, 1D as a path/carrier with endpoint topology, 2D as a surface/boundary with addressable boundary attachment points.
- **Attachment points (0D)** — one concern normalizes Port-like behavior everywhere: selection, hit-testing, wiring, color, label, history, and API behavior are identical whether a point lives on a 1D path or a 2D boundary. Attachment counts are template data, not a renderer rule.
- **Wire** — an open 1D carrier connecting attachment points that share an exposed surface. Wires can host Components inline (`wireId + t`); duplex Wires carry simultaneous forward/reverse packets.
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

Schemas live in `formats/`; `DATA-FORMATS.md` explains them.

## Agent surfaces

`window.SovSchematicAPI` (browser), a REST surface, and an MCP server (`mcp/server.mjs`) all delegate to the same transport-neutral data core — agent-created records cannot bypass editor legality, refusals return receipts without entering history, and history/checkpoints are operable over MCP. See `API.md` and `MCP.md`.

The agent-facing corpus ships with the repository:

- `AGENTS.md` — repository invariants and concern contract
- `skills/author`, `skills/operator`, `skills/reviewer` — authoring, operating, and reviewing skills
- `skills/steward` — installation, onboarding, channels, and the release/quality process
- `examples/` — executable golden documents and a portable reference pack

## Source and build

`index.source.html` + `src/*.js` + `styles/app.css` are the canonical development inputs. `python build.py` produces `index.html`, a deterministic standalone build that opens directly from disk. Module ownership is defined in `MODULES.md`; do not duplicate a concern into another module.

## Quality practice

`python scripts/qa.py` is the single authoritative gate, identical locally and in CI: static checks, browser interaction suites, API/HTTP/MCP parity and conformance, stress and performance watchers, mutation tests, the golden corpus, and syntax checks. Defects found by hand get an issue and, once fixed, a regression suite inside the gate. Pushes to `main` deploy to GitHub Pages only after the gate passes. `LOCAL-SETUP.md` covers machine setup, the local QA loop, and the green-main update pattern; `docs/BRANCHING.md` covers the release flow.

## Direction

The current line stabilizes primitives so future work adds definitions and rules rather than parallel implementations. The concerns ahead, tracked as NEXT issues and sketched in `ROADMAP.md`, `HORIZON-SPACE.md`, and `docs/vision/`:

- a formal Point / Path / Surface cell grammar, with the public Wire concept subsumed into generic 1D Path semantics;
- data-driven attachment descriptors, domain packs, and data-backed built-ins;
- a small logic machine for particle routing and signal state;
- generalized Spaces — admitted grammars beyond the current 2D canvas, including eventual 3D volume semantics;
- prompt/instruction compilation and richer agent authoring.

Historical acceptance records (`BETA-0.1.md`, `QA-0.1.md`, `RC-0.1.md`, `RC-FINISH-LINE.md`, `PUBLIC-BETA-FREEZE.md`, `MODULE-QA.md`, `contrast-audit.md`) document how past lines were tested and remain as records rather than living documentation.
