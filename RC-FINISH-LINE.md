# 0.1 RC finish line

This document separates **what the RC must satisfy** from **why continued polishing matters**. It is intentionally narrower than the post-RC product vision.

## RC needs

The 0.1 RC is ready to land when all of the following are true.

### 1. One primitive, one implementation

- 0D attachment points are authoritative for Port-like behavior.
- 1D-hosted and 2D-hosted attachment points use the same selection, hit-testing, wiring, direction/access, color, label, history, and API/MCP behavior.
- Root, nested, and Wire-hosted Components do not fork into separate implementations.
- Legacy `config.ports`, `parts.ports`, and `a/aSide/b/bSide` are compatibility projections only.

### 2. Earned dimensional behavior

- 0D behaves as an attachable point.
- 1D behaves as a path/carrier and exposes its endpoint topology.
- 2D behaves as a surface/boundary and exposes its canonical boundary points.
- No 3D claim exists in 0.1.
- A form changing host/dimension does not retain invalid controls or attachment behavior from another dimension.

### 3. Interaction correctness

- Component drag, settle, detach, Wire-hosting, and boundary crossing are deterministic.
- Ports/attachment points always win hit testing over transform/body gestures.
- Wire growth has intentional dwell/ghost behavior and never creates surprise Components.
- Undo/redo restores destructive operations, hosting changes, and topology changes correctly.
- Grid, appearance, selection, clipboard, pin/lock, and file operations have one state authority each.

### 4. Topology and semantics agree

- Wires terminate exactly at committed attachment geometry.
- Inline Components cut/bridge a carrier without gaps or hidden overlap.
- Duplex may carry valid simultaneous forward/reverse packets.
- Direction, access (Read/Write), channel, and authority remain independent axes.
- Inside/outside boundary exposure prevents implicit reach-through.

### 5. Data/API/MCP parity

- The editor, Browser API, HTTP/MCP adapter, save files, and golden examples observe the same authoritative model.
- Agent-created records cannot bypass editor legality rules.
- Serialization is deterministic and migrations are explicit.
- `.sov` and `.sovpak` round-trip without semantic loss for the supported 0.1 model.

### 6. Quality gates

- Manual QA defects are tracked as Issues rather than disappearing into chat history.
- Each fixed defect gains a regression test when practical.
- Golden corpus passes.
- API/MCP golden runs pass.
- Mutation tests kill the targeted semantic mutants.
- Performance watcher catches known catastrophic regressions.
- Light/dark visual checks cover major projection surfaces.
- No known release-blocking console/runtime errors remain.

### 7. Repository settlement

- Exact RC source, docs, schemas, skills, examples, tests, and CI are committed.
- Open RC blockers are either fixed or explicitly accepted as non-blocking debt.
- RC PR accurately represents the candidate being tested.
- License and public-beta release metadata are deliberately chosen.

## Why continue polishing the RC

The purpose is **not** to make 0.1 feature-complete or bug-free.

We continue polishing because the next architecture depends on the RC having trustworthy primitive boundaries.

If 1D attachment points and 2D attachment points still have different hidden interaction implementations, a future data-driven domain pack cannot safely describe an attachment point once and expect it to work everywhere. Every new domain would inherit special cases.

The RC should therefore remove **accidental distinctions** while preserving **intentional distinctions**.

Examples:

- intentional: Point vs Path vs Surface geometry;
- accidental: different pointer/wiring code for a point because it lives on a Wire;
- intentional: Input vs Output vs Read vs Write semantics;
- accidental: API-created attachments behaving differently from UI-created attachments;
- intentional: inside vs outside boundary exposure;
- accidental: nested Components using separate movement/selection logic.

A good RC foundation means the post-RC system can become more data-driven by adding definitions rather than adding another implementation path.

## Explicitly not required for RC

The following are not 0.1 completion criteria:

- generalized 3D Space/camera/volume semantics;
- arbitrary domain-pack installation;
- automatic domain research and glyph generation;
- prompt/instruction compilation;
- a universal technical symbol library;
- complete simulation of every configured dynamic;
- eliminating every compatibility field from the 0.1 file format.

Those are post-RC opportunities. The RC only needs to be clean enough that pursuing them does not require undoing its primitive model.
