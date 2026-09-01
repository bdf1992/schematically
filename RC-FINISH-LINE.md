# 0.1 RC finish line

This document is authoritative for **what must be true before `0.1.0-rc1` may merge**. It is intentionally narrower than the post-RC product vision.

## RC NOW

The RC is a stabilization and primitive-correction line. It does not add the post-RC language/runtime agenda.

### 1. One primitive, one implementation

- 0D attachment points are authoritative for Port-like behavior.
- 1D-hosted and 2D-hosted attachment points use the same selection, hit-testing, wiring, direction/access, color, label, history, and API/MCP behavior.
- Root, nested, and Path/Wire-hosted Components do not fork into separate implementations.
- Wire taps are ordinary hosted 0D points/components, not a second Port event system.
- Legacy `config.ports`, `parts.ports`, `wire.attachments`, and `a/aSide/b/bSide` are compatibility/migration projections only.

### 2. Earned dimensional behavior

- 0D behaves as an attachable point.
- 1D behaves as a path/carrier and exposes endpoint topology.
- 2D behaves as a surface/boundary and exposes addressable boundary attachment points.
- No 3D claim exists in 0.1.
- A form changing host/dimension does not retain invalid controls or attachment behavior from another dimension.
- The current built-in templates may default to `0D=1`, `1D=2`, and the current `2D=left/right/top` set, but **dimension is not a hard maximum attachment-count rule**. The RC must not freeze `dimension + 1` as ontology.
- Attachment descriptors must be capable of becoming data-driven after RC without another renderer/interaction implementation path.

### 3. Interaction correctness

- Component drag, settle, detach, Path/Wire-hosting, and boundary crossing are deterministic.
- Attachment points always win hit testing over transform/body gestures.
- Growth has intentional dwell/ghost behavior and never creates surprise Components.
- Undo/redo restores destructive operations, hosting changes, and topology changes correctly.
- Grid, appearance, selection, clipboard, pin/lock, and file operations have one state authority each.

### 4. Topology and semantics agree

- Carriers terminate exactly at committed attachment geometry.
- Inline Components cut/bridge a carrier without gaps or hidden overlap.
- Duplex may carry valid simultaneous forward/reverse packets.
- Direction, access (Read/Write), channel, and authority remain independent axes.
- Inside/outside boundary exposure prevents implicit reach-through.
- The visual projection cannot invent attachment topology not present in the model.

### 5. Data/API/MCP parity

- The editor, Browser API, HTTP/MCP adapter, save files, and golden examples observe the same authoritative model.
- Agent-created records cannot bypass editor legality rules.
- Serialization is deterministic and migrations are explicit.
- `.sov` and `.sovpak` round-trip without semantic loss for the supported 0.1 model.

### 6. Quality gates

- Manual QA defects are tracked as Issues.
- Each fixed defect gains a regression test when practical.
- Golden corpus passes.
- API/MCP golden runs pass.
- Mutation tests kill the targeted semantic mutants.
- Performance watcher catches known catastrophic regressions.
- Light/dark visual checks cover major projection surfaces.
- Repeated drag/gesture stress tests do not strand editor state.
- No known release-blocking console/runtime errors remain.

### 7. Repository settlement

- Exact tested RC source, docs, schemas, skills, examples, tests, and CI are committed.
- Open RC blockers are fixed or explicitly accepted as non-blocking debt.
- RC PR accurately represents the candidate being tested.
- License and public-beta release metadata are deliberately chosen.

## Current RC issue class

RC issues currently include:

- #1 — dimensional/form controls, label override, destructive-history correctness;
- #2 — Grid visibility state authority;
- #3 — 0D/Port/attachment-point unification;
- #5 — 1D/2D attachment interaction parity.

These issues may be closed only after their tested fixes are committed and reproduced from repository state.

## Why continue polishing the RC

The purpose is **not** to make 0.1 feature-complete or bug-free.

We continue polishing because the post-RC architecture depends on trustworthy primitive boundaries. The RC should remove **accidental distinctions** while preserving **intentional distinctions**.

Intentional examples:

- Point vs Path vs Surface geometry;
- Input vs Output vs Read vs Write semantics;
- inside vs outside exposure.

Accidental examples that must not survive the RC:

- different pointer/wiring code because a point is hosted by a Wire;
- API-created attachments behaving differently from UI-created attachments;
- nested Components using separate movement/selection logic;
- theme/view controls with multiple state authorities;
- attachment count being accidentally hard-coded by renderer geometry.

A good RC foundation means post-RC work can add definitions and rules rather than another implementation path.

## Explicitly AFTER RC MERGE

The following do **not** block `0.1.0-rc1`:

- formal cell-complex / boundary-operator grammar;
- redefining `Part` as a generic addressable owned subcell/facet;
- subsuming the public `Wire` concept into generic `1D Path` semantics;
- arbitrary parametric `stick_to(path[t])` authoring beyond the current hosting implementation;
- generalized trays/surfaces with arbitrary boundary parts;
- small Boolean/Redstone-like logic runtime;
- generalized signal-state/event scheduler;
- domain-pack installation and data-backed built-ins;
- technical SVG shape-language research and authoring skills;
- Space/admitted-grammar abstraction;
- prompt/instruction compilation;
- generalized 3D Space/camera/volume semantics;
- eliminating every compatibility field from the 0.1 file format.

Those begin from merged `main` on the post-RC development line. They must not be pulled into the RC merely because they are architecturally compelling.
