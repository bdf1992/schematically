# Handoff — scale benchmark, renderer decision, and pending research (2026-09-01)

Written for a fresh Claude Code session picking up where the previous one stopped. Repo: `repos/schematically`, branch `main`. Everything below is uncommitted in the working tree.

## Where this started

Bdo asked whether rasterizing the SVGs would help performance. Answer: no. The renderer rebuilds the whole SVG DOM on most edits, and pan/zoom only changes the viewBox, so paint was never the bottleneck. Bdo then set the product bar: model the largest datacenter floor down to ports (millions of ports), with several dynamics shown over the same model (temperature, voltage, data payload), like Factorio's scale and infinite-zoom canvases' LOD. Failing that bar fails the product.

## What was built and measured

**`tests/scale_benchmark.py`** builds a synthetic datacenter through the real factories (spine switches on the global canvas, rack containers with an authored uplink port, one ToR switch with 8 authored ports and 8 servers per rack, real wires) and escalates until cold render exceeds a cap. Not in the QA gate. Results in `tests/scale-benchmark-results.json`. Headless Chromium:

| components | ports | full render | one-node drag | pan frame |
|---:|---:|---:|---:|---:|
| 101 | 363 | 0.8 s | 0.8 s | 9 ms |
| 252 | 906 | 5.1 s | 4.8 s | 28 ms |
| 504 | 1,812 | 21 s | 20 s | 60 ms |

Render time grows ~n^2.06. The target is ~1.4M ports, ~400k components at this port density. Where the time goes at 500 components:

1. `computeSignalState` in `src/25-signal.js` is ~80% of every render: up to 6 passes, each node scans every wire (`incomingSignals`, line ~13), with linear `nodes.find` inside. Fix: index wires by endpoint, propagate from sources over the graph.
2. `routePoints` in `src/40-routing.js` (line ~278) filters all nodes twice per wire and seeds its candidate grid from every rect on the canvas. Fix: spatial index scoped to the wire's bounding box and canvas.
3. SVG paint: 60 ms per pan frame at 18.6k elements. The real ceiling, but far behind 1 and 2.

**`tests/renderer_spike.html` + `tests/renderer_spike.py`** draw the same synthetic floor three ways with a zoom-band LOD (ports culled below zoom 0.5). Headed browser, RTX 5080, frames measured rAF to rAF, ~7 ms is the monitor's vsync floor. Results in `tests/renderer-spike-results.json`:

| components | port marks | zoom | SVG | Canvas2D | WebGL2 |
|---:|---:|---:|---:|---:|---:|
| 100,000 | 400,000 | 1 | 68 ms | 6.7 ms | 6.8 ms |
| 400,000 | 1,600,000 | 0.25 | not run | 9.4 ms | 6.9 ms |
| 400,000 | 1,600,000 | 1 | not run | 7.0 ms | 6.9 ms |

Caveat: flat rects only, no text, strokes or wires. Canvas2D cost grows with visible detail; WebGL's does not. The WebGL path in the spike is ~60 lines, so no renderer dependency is needed and the standalone no-dependency `index.html` build survives.

Both sets of results and the proposed direction are appended to `PERFORMANCE.md` (two new sections at the bottom, marked as not yet decided).

## Decisions Bdo has made

- SVG is out for the main surface at this bar. A stack change is wanted sooner rather than later.
- A local program is the stronger requirement; web access is wanted too; hosting is an option.
- Bevy was raised. Full Bevy was assessed as costing the whole DOM UI, the MCP server's direct access to the JS data cores, and a heavy WASM web build. Not chosen yet.

## The recommendation on the table (not yet approved)

One Rust core with two front doors:

- Rust core owns the model, spatial index, and dynamics. Uses `bevy_ecs` as a standalone crate (entity storage + parallel systems), not the Bevy engine. Runs in-process on desktop and as a server when hosted, same binary.
- Front end stays the existing JS editor plus a new WebGL2 instanced render layer (bodies, ports, wires, dynamics overlays as per-instance color buffers) and a Canvas2D layer for text and the few hundred detailed items in view. Scene held in structure-of-arrays typed arrays with a spatial index and zoom-band LOD.
- Desktop = Tauri wrapping both (WebView2 on Windows is Chromium, so spike numbers hold). Hosted = same core on a socket, same front end in a browser.
- File formats stay JSON and authoritative. JS data core becomes client-side schema/validator. MCP server talks to the core over the socket instead of importing JS modules.
- SVG kept only for export and for rasterizing symbol glyphs into a mip-mapped texture atlas (the one place rasterization belongs).
- Design rule to lock first: only thousands of entities are ever awake and visible at once (Factorio's rule). Dynamics run as systems over the awake set, per connected network, with dirty flags, not full rescans.

Proposed order, each step keeps the app working and is gated by `tests/scale_benchmark.py`:

1. Structure-of-arrays scene + WebGL2 renderer in JS, plus the signal-engine and routing index fixes. One to two weeks. Needed in every option.
2. Rust core with `bevy_ecs` for dynamics behind a local socket, JS still owning edits. Two to three weeks.
3. Move the model into the core, wrap in Tauri. Two weeks.

## What stopped the previous session

Bdo asked what current (2026) sources say about this class of system: infinite-canvas rendering with simulation of variables over a space, "Figma plus a logic board", and whether we're stitching together concerns that existing products already separate. The `WebSearch` tool failed on every call with:

```
API Error: 400 Thinking may not be enabled when tool_choice forces tool use.
```

This is a harness problem in that session. First thing to do in the new session: run these searches (WebSearch, or WebFetch on specific URLs if search still fails) and report with source URLs, under ~700 words each:

**Research A — rendering.**
1. Figma's renderer: WebGL/WebGPU, tile-based rendering, LOD/zoom handling, C++/WASM core. Their engineering blog.
2. tldraw and Excalidraw: how they render, performance ceilings, culling.
3. Vello (Linebender) GPU vector renderer: 2026 status, WebGPU in browsers, bevy_vello, performance claims.
4. Browser large-graph renderers (Cosmograph / cosmos.gl, Sigma.js, deck.gl, Graphistry): node/edge counts on GPU and how.
5. Rive renderer, Skia/CanvasKit, Zed GPUI: 2025-2026 developments on GPU vector rendering in browsers.
6. 2025-2026 writing on semantic zoom / LOD on infinite canvases (spatial index + culling + LOD bands).

**Research B — simulation + canvas products.**
1. Data center digital twin / DCIM tools modeling floor plan + thermal (CFD) + power + network (Cadence Reality DC, NVIDIA Omniverse DC twins, Sunbird, Nlyte, Schneider EcoStruxure IT, Hyperview): scale, rendering tech, whether simulation is separate from visualization.
2. Browser circuit/logic simulators with canvas editors (Wokwi, CircuitVerse, Falstad CircuitJS, Digital by hneemann, KiCad web): sim/render separation, size limits.
3. "Figma + logic" tools with live simulation on a node canvas (Rive state machines, Unreal Blueprints, Simulink web, Modelica web tools, Cloudcraft, Lucidscale, Isoflow): any with live data overlays at scale.
4. WebGPU compute simulation in browsers 2025-2026: ECS/particle/N-body/diffusion examples at 1M+ entities; browser support status mid-2026.
5. 2025-2026 architecture writing on "simulation engine + spatial index + renderer as separate layers" for digital twins or large diagram tools.

The point of the research is to check the claim made without sources at the end of the last session: DC digital twin tools do floor plan + thermal + power + network but as 3D engines with offline simulation, not editable canvases; infinite-canvas tools solve rendering/LOD with no simulation; browser circuit simulators have simulation but die at a few thousand parts; nothing known does all three at datacenter scale as an editable diagram. Confirm or correct that, then revisit the recommendation above.

## Working tree state

Uncommitted, nothing in `src/` changed:

```
 M PERFORMANCE.md
?? HANDOFF.md
?? tests/renderer-spike-results.json
?? tests/renderer_spike.html
?? tests/renderer_spike.py
?? tests/scale-benchmark-results.json
?? tests/scale_benchmark.py
```

Bdo has not asked for a commit. `LOCAL-SETUP.md` notes that browser suites rewrite tracked byproducts under `tests/`; the new results files are untracked, not rewrites of tracked ones.

## How to rerun

```
cd repos/schematically
python tests/scale_benchmark.py --step-timeout-s 400     # escalates to failure, ~1 min
python tests/renderer_spike.py                            # headed browser window opens, ~1 min
```

Playwright and Chromium are already installed for Python 3.12 on this machine. The Bash tool's working directory does not reliably persist between calls here; use absolute paths or `cd` inside the same command.
