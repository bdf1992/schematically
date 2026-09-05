# 0.1 Beta.24 — concern QA estimate

Engineering release estimate grounded in the current automated suite and manual QA. This is evidence, not a claim of bug-free correctness.

| Concern | LOC | Risk | Status | Owns | Current evidence | Residual concern |
|---|---:|---|---|---|---|---|
| `00-state.js` | 288 | Medium | **GREEN** | runtime state + palette/color kernel | theme + performance + mutation | — |
| `05-data-core.js` | 446 | High | **GREEN** | formats, canonical CRUD, boundary/lock legality | file, boundary, Browser/HTTP/MCP golden, mutation | compatibility projections remain for 0.1 |
| `06-attachment-core.js` | 102 | High | **GREEN** | canonical 0D topology + aliases + data-declared 2D attachment defaults | point/parity/cardinality/mutation | full cell/facet grammar is post-RC |
| `10-model.js` | 510 | High | **GREEN** | component normalization + attachment configuration + host surfaces | host, R/W, attachment suites | compatibility `config.ports` still projected |
| `15-editor-kernel.js` | 240 | High | **GREEN** | history/checkpoints/clipboard/object state | editor + delete/undo + agent history | — |
| `20-ui.js` | 334 | Medium | **GREEN** | contextual UI projection | browser/manual suites | — |
| `25-signal.js` | 94 | High | **GREEN** | liveness/diffusion/access gating | duplex, R/W, mutation | future logic machine intentionally deferred |
| `30-canvas.js` | 702 | High | **GREEN** | camera/grid/host geometry/point geometry | grid, host, configurable attachments | geometry surface is large; watch coupling |
| `40-routing.js` | 497 | High | **YELLOW** | carrier route geometry/cache/terminal identity | host, terminal identity, visual, performance | scaling beyond small/medium diagrams |
| `50-selection.js` | 100 | Medium | **GREEN** | selection + inspector projection | editor + point parity | Wire selection remains index-backed internally |
| `55-render.js` | 498 | High | **YELLOW** | SVG projection, packet/mark/tag geometry, themes | visual, R/W, performance, render-idempotence | whole-scene SVG projection scales with graph size |
| `60-interactions.js` | 447 | High | **YELLOW** | pointer gestures, drag/settle/growth | 46-drag stress, attachment growth/parity | historically intermittent; watchdog retained |
| `70-editor-controls.js` | 173 | Medium | **GREEN** | UI→semantic mutation bindings | editor/file suites | — |
| `75-persistence.js` | 384 | High | **GREEN** | save/open/recovery/packages/runtime replacement | file + render-idempotence | — |
| `80-bootstrap.js` | 224 | Low | **GREEN** | global event/bootstrap bindings | all browser smoke | — |
| `85-api.js` | 59 | High | **GREEN** | Browser API adapter | Browser/API/MCP golden | policy intentionally delegated to data core |
| `mcp/server.mjs` | 106 | High | **GREEN-local** | MCP + HTTP transport/history | agent golden + syntax | fresh GitHub runner CI still must reproduce |
| `scripts/qa.py` + browser helper | — | High | **GREEN-local** | one RC QA command + browser runtime selection | explicit Chromium full suite | managed Playwright browser install not reproducible in this container due external DNS; GitHub CI pending |

## Current regression gate

- dimensional form: **PASS**
- pre-repo hardening: **PASS — 26 checks**
- 0D attachment refactor + 1D/2D parity: **PASS**
- configurable attachment-default seam: **PASS**
- canonical growth direction + canonical/legacy terminal identity: **PASS**
- boundary legality + Read/Write: **PASS**
- inline/host/tray settle: **PASS**
- delete/Undo/Redo/checkpoint + Grid: **PASS**
- editor kernel + extended utilities + file surface: **PASS**
- Browser API / HTTP / MCP agent golden: **PASS**
- render semantic idempotence: **PASS**
- drag lifecycle stress: **PASS — 46 repeated drags**
- Light/Dark + duplex visual: **PASS**
- golden corpus: **PASS — 7/7 documents**
- mutation watcher: **PASS — 9/9 targeted mutants killed**
- JavaScript/MCP syntax: **PASS**

## Performance gate

Latest local headless measurements:

- 5 Components / 4 Wires — cold `38.8 ms`, warm `13.8 ms`, wire-only `10.9 ms`, signal `3.3 ms`.
- 10 Components / 9 Wires — cold `26.6 ms`, warm `32.9 ms`, wire-only `23.8 ms`, signal `9.8 ms`.

The catastrophic small-diagram regression remains fixed by memoized palette realization. Medium diagrams are near/over a 16.7 ms frame budget under full projection, so routing/render stay YELLOW; incremental/dirty rendering is post-RC optimization unless manual QA exposes a blocker.

## Mutation gate

Killed mutants cover:

1. access always permits Read/Write;
2. signal skips access checks;
3. boundaries become implicitly porous;
4. palette performance cache disappears;
5. terminal identity compares raw canonical/legacy aliases;
6. blank growth skips canonical attachment resolution;
7. locked update/delete policy disappears from shared core;
8. locked endpoint carrier admission disappears;
9. dimensional defaults become a hard attachment-cardinality ceiling.

## Current release risks

1. **Repository settlement:** the GitHub RC branch still does not contain the exact Beta.24 runtime/test tree.
2. **Fresh-runner CI:** workflow/harness are corrected locally, but GitHub Actions must prove them on the exact branch. Local managed Chromium installation was blocked by container DNS, while explicit system Chromium passes.
3. **Routing/render scaling:** largest known performance debt; not currently a correctness blocker at the tested small/medium scale.
4. **Pointer lifecycle:** stress evidence is strong, but this remains historically high-risk and should stay under manual QA.
5. **Compatibility debt:** legacy Port/Wire aliases remain 0.1 serialization projections by design; post-RC topology work must migrate them deliberately.
