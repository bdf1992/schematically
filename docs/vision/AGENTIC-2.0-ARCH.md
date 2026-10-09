# Schematically 2.0: architecture scan and the week's cut

> **Non-authoritative opinion, 2026-10-09.** It goes with `AGENTIC-2.0.md` and is the
> technical reading behind it: what to keep, what to build new, what to bring in, and
> which lessons bind. Scanned `origin/dev` at `c8f196d` (304 commits ahead of `main`),
> `bdos-design` `main` at `2326caa`, and the workstation's task records.

## Verdict

**Do not rewrite the editor. Keep the engine, build a new experience shell beside the
editor, and put one attributed operation log under both.**

- The engine is the asset. It is about 6,500 lines that never touch the DOM, already
  shared by the browser and the Node server, and covered by 155 QA suites.
- The editor shell is the liability. It is about 8,000 lines of one global script whose
  files reference each other in every direction, and its SVG renderer is the measured
  wall: 155 cards is reported as not responsive; 1,000 pieces take 246 s to draw cold.
- What 2.0 adds (four participants, live state, generated surfaces, graph levels, 3D) is
  mostly *above* the engine and *beside* the renderer. It needs neither a rewrite of the
  first nor a fix to the second this week.

## 1. What the scan found

### Two codebases in one repository

| Tier | Modules | Lines | DOM refs | Shape |
| --- | --- | --- | --- | --- |
| **Engine** (DOM-free, loaded by `mcp/server.mjs` too) | `03-canonical`, `03-notation-core`, `04-signal-model`, `05-data-core`, `06-attachment-core`, `07-graph-core`, `07-state-space`, `07-state-surface`, `08-layout-core`, `09-colour-core` | ~6,500 | ~0 | UMD factories on `globalThis`; one door, `applyOperation` |
| **Editor shell** (browser only) | `00-state` … `87-live` (23 files) | ~8,000 | ~760 | one concatenated global script; `00-state` is mutable globals read by 29 files |
| **Server surface** | `mcp/surface.mjs`, `server.mjs`, `store-*.mjs` | ~540 | 0 | runtime-free request core, file store, ~40 MCP tools, `/api/v1/*` |

Editor-shell coupling (a lower-numbered file using a higher one, which only works because
the build concatenates everything into one global scope):

- `10-model` → `15`, `30`, `40`, `55`
- `15-editor-kernel` → 8 later files
- `30-canvas` → `40`, `41`, `50`, `55`, `60`
- `40-routing` uses 17 names from `00-state` (`activeNodeDrag`, `camera`, …) and calls
  `selectNode` and `render`. **Routing cannot be lifted into the engine this week.**

### Where the change has been

| File | Commits on dev | Lines |
| --- | --- | --- |
| `src/55-render.js` | 87 | 1,747 |
| `src/05-data-core.js` | 55 | 1,700 |
| `styles/app.css` | 53 | 597 |
| `src/30-canvas.js` | 38 | 986 |
| `src/75-persistence.js` | 30 | 640 |

Commit-subject themes over 300 commits: one-runtime 34, label 21, redraw 21, bus 17,
colour 13, drag 12. There are no reverts; reversals happened by replacement.

### The 2.0 floor, as it stands on `dev`

- **Live link exists, one way.** The browser pushes a read-only snapshot (revision,
  camera, selection, whole document) to `POST /api/v1/live` at most every 250 ms;
  `schematic.live.get/selection` let an agent see what the person sees. Nothing flows
  back: a server edit still never reaches the open editor. (`src/87-live.js`,
  `mcp/surface.mjs:55-204`)
- **No actor anywhere on edits.** `operation@0.1` is `{id, op, resource, resourceId, value,
  patch, query}` with `additionalProperties: true`; `receipt@0.1` has no actor; editor
  history is `{label, at, document}` from a 320 ms timer. Adding an actor is backward
  compatible.
- **The attribution vocabulary already exists.** `state-record` (the run ledger) carries
  `principal`, `observer`, `provenance`, `vantage`. Use these words for edits; do not
  invent new ones.
- **The served-editor path is queued.** "Opening /editor on a document server shows that
  server's document" (`schematically-one-mcp-surface-any-runtime`) is the first half of
  a shared session.

### bdos-design already holds the generative, stateful UI layer

`AGENTIC-2.0.md` proposed inventing `surface@0.1`. **bdos-design already has it:**

- **Document:** `{catalog, look, brand, data, root tree}`. Each node is `{type, props
  (values or {$bind}), state, slots ($each templates)}`, with a flat A2UI-shaped graph form
  so one node can be updated at a time (`packages/core/src/document.ts`).
- **Painting:** a primer plus named states, each one a merge patch on the data and named
  states per node. "A state is a patch, never a second drawing"
  (`packages/core/src/painting.ts`).
- **Live surfaces API:** `POST /v1/surfaces` → `{id, rev, events, participants}`.
  `PATCH` takes an RFC 7396 merge patch on the data.
  `GET …/events?after=n&wait=s` is a long poll. **Every event names its participant**:
  `{seq, at, participant:{id,name}, type: act|change, node, …}` (`docs/API.md`).
- **Partitions:** `workbench` puts "a tool or conversation beside the material it works
  on". That is the 2.0 screen.
- **Catalog:** 75 primitives and 45 patterns, among them card, tree, table, tabs, sheet,
  drawer, popover, toast, command, thread, message, avatar (with a `presence` prop),
  badge, comparison, viewport.
- **Missing parts:** canvas, node, wire, minimap, presence layer, toolbar, inspector, diff,
  timeline, camera, anything 3D.
- **Delivery:** Lit 3 web components plus `dist/css/tokens.css` (`--bd-*` variables,
  `data-bd-<axis>` attributes, dark by default). It is not published. `dist/` is not
  committed, and there is one tag, `v0.1.0`.

## 2. Priority factors, ranked

Each factor is ranked by how much later work stands on it, how far the record says it
can hurt, and whether it fits in a week.

1. **One authority per document, with attribution (floor).** Everything in the 2.0
   list is a fold over who did what. The record's own warning: two runtimes side by side
   took ten contracts to merge (`docs/residuals/2026-09-26-one-runtime.md`). So
   *replace*, don't run beside. In served mode the server's operation log is the only
   authority, and the editor writes through it. In file mode the editor keeps today's
   history. A document is in one mode at a time; that is two modes, not two authorities.
2. **The renderer wall.** Graph levels, ghosts (which double what is drawn) and planes in
   depth (which multiply it) are all impossible on SVG at today's numbers. The board
   study already recommends Canvas2D with level-of-detail bands
   (`docs/workengine/BOARD-STUDY.md:150-167`), and GLSP showed culling works (54 of 252
   nodes in the DOM). It is a new renderer, read-only first, with no orthogonal routing.
3. **Bring in bdos-design's surface model instead of inventing one.** It already
   carries participants, merge patches, long-poll events and the workbench partition.
   Days of work become an adapter.
4. **The system agent v0 is deterministic.** Layout, clustering (`graph_to_sov`),
   validation (`markers`, `concerns`) and render already exist as verbs. Running them
   under a declared `system-agent` principal makes the seat real today. A model-backed
   system agent is the later step, through a declared binding.
5. **Feedback speed.** CI takes 14–18 minutes on a GitHub-hosted runner, against the
   workstation's runner rule (R-31; its task is queued). A week of iteration needs a
   fast lane: the new shell gets its own suite under a minute, and the full `qa.py` runs
   before merge.
6. **Design tokens in the old chrome.** This is mechanical and contractable: pin the
   built `tokens.css`, map `[data-appearance]` to `data-bd-theme`, and move `app.css`
   values onto `--bd-*`. It is the 53-commit hot spot, so it is worth it; it is not on
   the critical path.
7. **3D.** Planes in depth come almost free once factor 2 exists (the same renderer with
   a z per plane and an orbit camera). Volumes are not this week.

## 3. Greenfield, brownfield, priors, ports

### Greenfield (new code, new place)

| Piece | Where | Why new |
| --- | --- | --- |
| **v2 shell** | `studio/`, ES modules, Vite, the same toolchain as bdos-design | The global script cannot take modules, Lit or a second renderer without making its coupling worse |
| **Map renderer** (Canvas2D, WebGL later) | `studio/map/` | SVG is the wall; read and navigate first, edit later |
| **Planes in depth** | the same renderer: z per plane, orbit and ortho camera | "3D, earned" with real XYZ, a camera and depth hit-testing |
| **Event stream and presence** | `mcp/surface.mjs` route `GET /api/v1/events?after=&wait=` | The missing return path |
| **Proposal record** | server: a held `apply` batch with author and reason; drawn as a ghost | `apply` is already all-or-nothing, so a proposal is a batch not yet committed |
| **Catalog parts Schematically needs** | contributed to bdos-design: stage/canvas, node, wire, minimap, presence layer, ghost, provenance badge, inspector, timeline, camera | Missing from the catalog; built once for every consumer |

### Brownfield (keep and change in place)

| Piece | Change |
| --- | --- |
| `05-data-core` `applyOperation` / batch | Takes `actor` (principal, on-behalf-of, seat) and puts it in the receipt |
| `mcp/surface.mjs` | Operation log becomes server history; per-actor undo; events route; proposal hold, accept and reject |
| `src/87-live.js` | From push-only to push and subscribe: applies server events to the open document |
| Served `/editor` (queued task) | Writes through the server when served |
| `graph_to_sov.py`, `layout_sov.mjs` | Unchanged; the system agent's import verb wraps them |
| Engine cores, 155 QA suites, the SVG editor | Unchanged. The SVG editor stays the precise editing tool |
| `styles/app.css` | Values move to `--bd-*` (contract) |

### Contained priors and legacy lessons (binding)

1. **Operation boundaries, not timers.** History from a 320 ms snapshot timer split
   gestures (d33b28b). Attribution and per-actor undo hang on explicit operations only.
2. **Replace, don't run beside.** The one-runtime merge took ten contracts. A document has
   one authority at a time.
3. **Seats differ only by what the Space admits, never by code path.** This is the
   roadmap's NEVER list, and the attachment refactor paid for aliases.
4. **Every guard is proven by a planted failure.** One guard read `config.labelMode` while
   the product writes `config.presentation.labelMode`; a mutant survived the suite; the
   Tauri shell passed while opening nothing.
5. **No wall-clock assertions.** "Within one second" is tested as a count of events or
   against a baseline taken in the same run (ef1a24b, 3cb9320).
6. **Pin LF and fonts before any byte or picture golden.** CRLF and Windows font metrics
   broke goldens. A root `.gitattributes` is still owed.
7. **Do not send the whole document per tick.** The live link sends the whole document
   every 250 ms. Events carry operations; snapshots are on request only.
8. **Render on the server is a Chromium start per call** (90 s timeout). Agents should
   read the studio's own canvas in the booth, and keep `schematic.render` for proof.
9. **GLSP was spiked and rejected:** it expects undo on the server, there was no
   equivalent for routing or render, and its wire shapes are unpublished. Its lesson
   (cull, and draw only what is on screen) is kept; the framework is not.
10. **Scale budgets already proposed:** cold ≤ 10 s; pan, zoom and drag ≤ 16.7 ms; hit
    test ≤ 4 ms (`spikes/glsp-projection/evidence/_ref-SCALE-GATE.md:105-113`).

### Imports (taken as-is, pinned)

| From | What | How |
| --- | --- | --- |
| bdos-design | `tokens.css`, `tokens.bundle.json` | Built at a named commit, vendored with its SHA and digest; this is the queued `rift` consumer proof |
| bdos-design | `@bdos-design/core` document, painting and check; `@bdos-design/elements` (Lit) | Studio dependency via git SHA; `mount(el, doc, {live})` hosts surfaces |
| bdos-design | surface and events protocol (participants, merge patch, `after`/`wait`) | The wire format of `/api/v1/events` and of surfaces |
| Schematically | `state-record` vocabulary (`principal`, `observer`, `provenance`) | The actor shape on operations |

### Ports (re-implemented here)

| From | What |
| --- | --- |
| system-cartographer `graph_view.py` (WebGL) | Cluster opens by room and interest, cluster naming, plane splitting, curves through group centres, the open-file faults list. Its source is not on this machine; port from its repository |
| Spike B1 (measured, never landed) | Spatial indexing for hit-test and culling (`_ref-SCALE-GATE.md:156`) |
| Foundry scene editor (2fd22cf) | Perspective, orthographic and pixel-grid camera framing |
| bdos-design `claude-chat` bridge | Shape for the later model-backed system agent; not this week |

### Retire

- The schematify fork (mission already says so; registry entry still enabled).
- Snapshot history in served mode.
- Raw colour values in `app.css`.

## 4. The week (five working days from 2026-10-12)

Each day ends on something Bdo can see running (R-30). Items marked *(contract)* are
mapped and decided, and go to a contractor.

| Day | Lands | Proof |
| --- | --- | --- |
| **1. Floor A** | `actor` on operation and receipt; server operation log as history; per-actor undo; `GET /api/v1/events?after=&wait=`. Pin bdos-design tokens *(contract)* | A test with two actors: undo one actor and the other's work remains; a planted unattributed write is refused |
| **2. Floor B** | Served `/editor` (the queued task) writes through the server and applies events; presence both ways from the live link | An MCP edit appears in the open editor, counted by events, not timed |
| **3. Studio** | `studio/` (Vite, Lit, bdos tokens, `workbench` partition): material on one side, surfaces on the other. An agent posts a bdos-design document as a surface; the person acts on it; the event names both. The system agent v0 runs layout, import and validate under its own principal | A booth recording: an agent posts an inspector surface, the person edits through it, and the log shows three actors |
| **4. Map** | Canvas2D map in the studio: a `.sov` drawn read-only with level-of-detail bands, communities as nested hosts that open by room and interest, and proposals drawn as ghosts | 4,000 cards within the proposed budgets (counted frames); `booth-record-graphify.sov` at three zoom levels |
| **5. Depth, then witness** | Planes in depth: z per plane, orbit camera, wires between planes. Chrome tokens in `app.css` *(contract)*. An independent witness, then a live showing to Bdo | A customer review; Bdo's reaction recorded |

**Not this week:** editing in the map renderer, routing in the engine, volumes, a
model-backed system agent, publishing bdos-design.

**Risks, named:**
- Vite and Lit in a repository that has none (mitigation: confined to `studio/`; the
  classic build is untouched).
- bdos-design is unpublished and its typecheck depends on a build step (mitigation: pin
  by SHA, vendor what is built).
- The Day 4 scale target may slip to 1,000 cards (mitigation: the budget is the
  acceptance, the card count is the stretch).
