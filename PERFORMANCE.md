# Performance — 0.1

## Decision

Keep vanilla JavaScript + SVG for the 0.1 line. The severe small-diagram lag was a repeated-computation defect rather than evidence that the stack itself must be replaced.

## Current regression measurements

- 5 Components / 4 Wires: warm full render **8.3 ms**, wire-only **9.2 ms**.
- 10 Components / 9 Wires: warm full render **18.0 ms**, wire-only **17.1 ms**.

Measurements are environment-sensitive and are regression guards, not product guarantees.

## Known scaling boundary

The renderer still rebuilds whole SVG projections and all Wires for several mutation paths. Larger diagrams therefore cross the frame budget. The next performance upgrade should be dirty-object/incremental projection before any framework, Canvas2D, or WebGL rewrite is justified.

## Scale benchmark — 2026-09-01

`python tests/scale_benchmark.py` builds a synthetic datacenter (spine switches, rack containers, one ToR with 8 authored ports and 8 servers per rack) through the real factories and escalates until cold render exceeds a cap. It is not in the QA gate. Results land in `tests/scale-benchmark-results.json`.

| racks | components | wires | ports | SVG elems | cold ms | warm ms | signal ms | drag ms | pan frame ms |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 11 | 9 | 39 | 366 | 40 | 21 | 10 | 18 | 1.5 |
| 5 | 51 | 45 | 183 | 1,794 | 224 | 233 | 160 | 216 | 5.4 |
| 10 | 101 | 90 | 363 | 3,624 | 804 | 833 | 633 | 789 | 9.2 |
| 25 | 252 | 225 | 906 | 9,135 | 4,878 | 5,115 | 4,048 | 4,808 | 28 |
| 50 | 504 | 450 | 1,812 | 18,631 | 20,340 | 21,349 | 17,308 | 20,314 | 60 |

Render time grows as roughly n^2.06 in component count. Product bar for a full datacenter floor is ~1.4M ports, ~400k components at this topology's port density; the fitted curve puts a single render there in the order of years.

Where the time goes at 500 components:

1. `computeSignalState` (25-signal.js) is ~80% of every render. Each of up to 6 passes calls `incomingSignals` per node, which scans every wire, and `nodes.find` inside. Cost is passes × components × wires. Fix: index wires by endpoint once per render and propagate from sources over the graph, not by repeated full scans.
2. `routePoints` (40-routing.js) filters all nodes twice per wire and seeds its candidate grid from every rect on the canvas, so per-wire routing cost grows with total component count. Fix: spatial index / only consider obstacles within the wire's bounding box, and route per canvas.
3. SVG paint itself: a pan frame at 18.6k elements is 60 ms (need 16 ms). This is the real ceiling of retained-mode SVG and shows up only after 1 and 2 are fixed. Beyond a few thousand visible elements the renderer needs visibility culling and semantic zoom (draw racks as blocks until zoomed in), and past that a Canvas2D/WebGL layer.

Rasterizing the SVGs would address none of the three.

## Renderer spike — 2026-09-01

`python tests/renderer_spike.py` (headed, RTX 5080) draws the same synthetic floor three ways with a zoom-band LOD (ports culled below zoom 0.5). Frame times are rAF to rAF; ~7 ms is this monitor's vsync floor.

| components | port marks | zoom | SVG frame ms | Canvas2D frame ms | WebGL2 frame ms |
|---:|---:|---:|---:|---:|---:|
| 10,000 | 40,000 | 1 | 7.2 | 6.8 | 7.0 |
| 100,000 | 400,000 | 0.25 | 17.9 | 9.1 | 6.9 |
| 100,000 | 400,000 | 1 | 67.8 | 6.7 | 6.8 |
| 400,000 | 1,600,000 | 0.25 | not run | 9.4 | 6.9 |
| 400,000 | 1,600,000 | 1 | not run | 7.0 | 6.9 |

SVG is out for the main surface at the datacenter bar. Both immediate-mode options hold vsync at the target with flat rects; the spike has no text, strokes, or wires, which is where Canvas2D cost grows with visible detail and WebGL does not.

Proposed direction for 0.2 (not yet decided): scene held in typed arrays with a spatial index and zoom-band LOD; WebGL2 instanced geometry for bodies, ports, wires and dynamics overlays (per-instance colour); a Canvas2D layer on top for text and the few hundred detailed items in view; SVG retained only for export and for rasterizing symbol glyphs into a mip-mapped texture atlas. No renderer dependency needed — the spike's WebGL path is ~60 lines.
