# Scale gate — contracts and engine bakeoff

This document is authoritative for **two things**:

1. the **data contract** and **render contract** that any engine pairing must satisfy before a local
   release may claim it models an entire code repository or an enterprise-class data center;
2. the **bakeoff** that decides which backend/frontend pairing we ship — by measurement against those
   contracts, on one corpus and one trace, not by argument.

No stack is presumed. The current JS/SVG implementation is the control, not the incumbent.

`RC-FINISH-LINE.md` remains authoritative for `0.1.0-rc1`. This gate sits after it and is independent.

Budgets marked **(proposed)** are engineering suggestions. Bdo sets the final numbers.

## 1. The corpora

Both are real, published, and citable. Neither is invented for convenience.

### 1.1 Data center — OCP K-Array Clos fat tree

From *Colocation Facility Guidelines for Deployment of Open Racks* v4.1, Appendix E.2.1
(Open Compute Project, CC BY-SA 4.0). Vendored at `reference/datacenter/ocp-colo-facility-guidelines.pdf`.
A K-port switch supports K³/4 servers.

| K | Servers | Access sw | Aggregation sw | Core sw | Total switches | Total ports | Total channels |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 48 | 27,648 | 1,152 | 1,152 | 576 | 2,880 | 138,240 | 69,120 |
| 64 | 65,536 | 2,048 | 2,048 | 1,024 | 5,120 | 327,680 | 163,840 |
| **96** | **221,184** | **4,608** | **4,608** | **2,304** | **11,520** | **1,105,920** | **552,960** |
| 128 | 524,288 | 8,192 | 8,192 | 4,096 | 20,480 | 2,621,440 | 1,310,720 |

**Gate target: K=96.** K=128 is headroom. K=48 and K=64 are the intermediate rungs the bakeoff
escalates through, so a candidate that fails is scored on where it failed.

Derived model size at K=96, with racks and server NICs:

- **~240,000 components** (221,184 servers + 11,520 switches + ~7,400 racks at 30 servers/rack
  + ~310 pods at 24 racks per pod, per §7.1 of the same document)
- **~1,550,000 ports** (1,105,920 switch + ~442,000 server NIC)
- **552,960 wires**

Cross-check: a 100 MW hyperscale building runs 750–8,000 racks and 31,500–336,000 servers, so K=96
sits at the top of the published range and K=128 exceeds any single building.

Port density is violently skewed — a 96-port switch and a 2-port server in one model. Any candidate
that assumes uniform port density per component is measuring a corpus that does not exist.

### 1.2 Code repository — file resolution

Linux ~57,000 files · **Chromium ~246,000 files (gate target)** · Windows ~3,500,000 files (headroom).

Opposite shape to the data center: more entities, sparse relationships, large uniform regions that
are never individually distinguished. This is the corpus that tests implied entities; the data center
is where they pay least, because most switch ports really are cabled.

## 2. Data contract (backend)

This is not a new API. It is `window.SovSchematicAPI` as documented in `API.md`, plus complexity
bounds it does not currently state, plus two operations it does not currently have.

A backend satisfies the data contract when every operation below holds its bound **at K=96 and at
Chromium scale**, verified by the doubling test in §2.2.

| Operation | Bound | Status today |
|---|---|---|
| `get(resource, id)` | O(1) | O(n) — `find(n => n.id === …)`, 50 sites |
| `list(resource, query)` scoped to a canvas | O(result) | O(n) full scan |
| wires at (component, port) | O(degree) | O(W) full wire scan |
| viewport query (rect, canvas, zoom band) | O(result) | **does not exist** |
| `childrenOf(id)` / `membersOf(canvasId)` | O(result) | O(n) filter |
| `create` / `update` / `delete` / `execute` | O(affected), returns a dirty set | O(n) rerender, no dirty set |
| dynamics recompute after one edit | O(awake + affected edges) | O(passes × N × (N+W)) |
| `materialize(template, index)` → stable id | O(1) | **does not exist** |
| serialize / deserialize | O(n) once, implied entities not expanded | O(n), no implied entities |

Two hard requirements beyond the table:

- **No operation may require the whole model to be materialized to answer a scoped question.**
  `document.get()` and unscoped `list()` remain as bulk exports; nothing on the hot path may use them.
- **Identity survives materialization.** An implied port that gets wired keeps the id it would have
  had, and that id round-trips through `.sov` unchanged. This is a model decision and it blocks every
  candidate equally — see §8.

### 2.2 The doubling test

For each hot-path operation: hold the viewport fixed, double the corpus (K=48 → 64 → 96), and the
per-operation cost must not change. This is the contract's real form. The budgets in §4 are symptoms;
this is the disease.

## 3. Render contract (frontend)

A frontend satisfies the render contract when, given a viewport, a zoom level, and a dirty set:

- it draws a frame within the §4 budget without reading entities outside the viewport;
- **hit testing returns the same entity and port the model says is there**, within the same budget;
- its **LOD bands are declared, not emergent** — the zoom thresholds at which ports, port labels,
  component text, wires, and dynamics overlays appear or drop are written down and testable.
  Starting point from `tests/renderer_spike.py`: ports culled below zoom 0.5;
- text is drawn from a rasterized glyph atlas, not per-item text nodes;
- dynamics overlays (temperature, voltage, payload) are per-instance attributes over the same
  geometry, not a second scene;
- it renders from the backend's viewport query alone, never from a full materialization.

## 4. Budgets **(proposed)**

Reference machine, production build, both corpora:

- cold load of the full corpus from `.sov`: **≤ 10 s**
- pan/zoom frame at any zoom band: **≤ 16.7 ms**
- single-component drag, press to first painted frame: **≤ 16.7 ms**
- dynamics recompute after one edit: **≤ 16.7 ms**
- hit test: **≤ 4 ms**

Memory must stay inside browser limits including the single-allocation ceiling, which caps individual
typed-array buffers well below total heap. No candidate may assume one buffer can exceed it.

## 5. The trace

Every candidate runs the **same scripted workload** on the same corpus. Without this it is six demos,
not a bakeoff.

1. cold load from `.sov`
2. fit to extents, then pan one viewport width at zoom band 0 (overview)
3. zoom in through every declared LOD band to 1:1
4. hit test 100 known ports at 1:1 and verify each against the model
5. drag one component 200 px
6. wire two ports on different racks
7. dynamics recompute; read back 100 known component states
8. undo the wire, undo the drag
9. save to `.sov`, reload, verify round-trip identity including implied entities

Each step reports its own timing. A candidate that fails mid-trace is scored on the step it reached.

## 6. Candidates

**Backends**

- **B0** current JS arrays — control
- **B1** JS structure-of-arrays + indexes, in-process
- **B2** Rust core + `bevy_ecs`, in-process via WASM
- **B3** Rust core + `bevy_ecs`, out-of-process over a local socket

**Frontends**

- **F0** current SVG DOM — control
- **F1** Canvas2D + LOD
- **F2** WebGL2 instanced
- **F3** WebGPU instanced, compute shaders for dynamics, WebGL2 fallback, one shader source

**Pairings that run** — six, not sixteen:

| # | Pairing | What it answers |
|---|---|---|
| 1 | B0 × F0 | Control. Ceiling was 504 components / 1,812 ports. |
| 2 | **B1 × F0** | **How much of the n² was data, not rendering?** — **RUN, 2026-09-01.** Answer: most of it, to a point. Ceiling 504 → 4,025 components (14,475 ports); cold render at 504 from 21,000 ms to 1,086 ms; growth n^2.06 → n^1.80. Signal recompute went from ~80% of render to ~5%. SVG untouched, all 30 QA suites green. Results in `tests/scale-benchmark-results.json`. Still 60x short of K=96, and what remains is the renderer plus a warm re-render pathology (n^2.54) that run 1 was too slow to expose. |
| 3 | B1 × F2 | Does JS + WebGL2 clear K=96 with no new language? |
| 4 | B1 × F3 | Does WebGPU compute buy enough on dynamics to justify it? |
| 5 | B2 × F3 | Does a Rust core in WASM beat B1, and by how much? |
| 6 | B3 × F3 | Does the socket shape hold the budgets, and what does it cost? |

Run 2 first. It is a few days of work, needs no renderer decision, changes no visual output, and is
covered by the existing QA gate.

## 7. Scoring

Performance is necessary, not sufficient. Each candidate is scored on both axes.

**Passes** — contracts in §2 and §3, budgets in §4, full trace in §5, at K=96 and Chromium.

**Costs**, recorded per candidate:

| Cost | Why it matters |
|---|---|
| Standalone no-dependency `index.html` survives? | `build.py` inlines everything today. B3 breaks this. |
| MCP keeps direct access to the data cores? | B3 moves MCP onto a socket. |
| Existing 38 QA suites reusable? | 19 reach into the SVG DOM; F1–F3 delete what they query. |
| Golden PNGs reusable? | 15 goldens; GPU antialiasing will not match SVG pixel-for-pixel. |
| New toolchain or build dependency? | B2 and B3 add Rust; B3 adds a process. |
| One codebase serves local **and** hosted? | The actual product requirement behind B2/B3. |

**Correctness oracle.** F0 is retained as a second frontend permanently, selected by entity count or
flag. Below the switch threshold the existing QA suites pass unmodified; above it, a parity test
drives one model through two frontends and compares topology, selection, hit testing, and geometry.
The visual projection may differ. The model behavior may not.

**Decision rule.** The **cheapest** pairing that passes both contracts at K=96 and Chromium wins —
not the fastest. If B1 × F2 passes, then B2 and B3 are decided on the local-program and hosting
requirements alone, on their own merits, and not by this gate.

## 8. Blocking work

In dependency order. Items 1–4 are shared by every candidate and are not a bet on any of them.

1. **Identity rule for implied entities** (§2, end). Design only. Blocks all six pairings.
2. **Harness.** Extend `tests/scale_benchmark.py` to build the K-Array corpora from the §1.1 table
   and the Chromium corpus, and to run the §5 trace with per-step timings and per-candidate results.
3. **Entity indexing.** id→row accessor plus canvas membership, wire endpoint, parent→children, and
   the awake/visible set. Covers ~75 of the 80 array scans in `src/`. Gives run 2.
4. **Signal engine and routing index.** Propagation from sources over an endpoint index; spatial
   index scoped to each wire's bounding box and canvas. Completes run 2.
5. Runs 3–6, in order, stopping at the first pairing that passes §7.

## 9. Not in scope

- 3D, CFD, or physical thermal simulation. Dynamics here means values propagated over the model
  graph, not a physics solver.
- Vello, while it remains alpha and Firefox/Safari WebGPU is experimental in Linebender's own docs.

## 10. Sources

- Open Compute Project, *Colocation Facility Guidelines for Deployment of Open Racks* v4.1,
  Appendix E.2.1 (K-Array metrics), §7.1 (pod architecture). CC BY-SA 4.0.
  Vendored at `reference/datacenter/ocp-colo-facility-guidelines.pdf`.
- Cisco, *Massively Scalable Data Center Network Fabric Design and Operation*:
  https://www.cisco.com/c/en/us/products/collateral/switches/nexus-9000-series-switches/white-paper-c11-743245.html
- Racks and servers per 100 MW facility: https://solartechonline.com/blog/how-much-electricity-data-center-use-guide/
- Repository file counts: https://devblogs.microsoft.com/bharry/the-largest-git-repo-on-the-planet/
- Renderer precedents behind §3 and the F0-retention rule: `RESEARCH-2026-09-01.md`
- Current API surface the data contract binds to: `API.md`
