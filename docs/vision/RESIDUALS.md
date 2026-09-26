# Residual log: optimization, units, logic and visuals

> **Non-authoritative log.** Everything still owed by the work on branch `claude/linear-nonlinear-optimization-xz7t48` (2026-09-25 to 2026-09-26): solvers, whole units and `.sav`, logic on state space, the visual language, and the integration and review found on the way. Each row names who can close it. The design docs keep their own residual tables; this log gathers them in one place and adds what was found only in the working session. Written 2026-09-26 at commit `c4fce0a`.

## Decisions owed (Bdo)

| # | Residual | Options, and what it blocks |
| --- | --- | --- |
| D1 | Where the run views (timing, landscape, search, timeline) live in the editor | a panel beside the canvas (recommended: the canvas stays the document, the panel shows a run of it), a second tab, or a mode of the canvas. Blocks the views' editor, API and MCP surfaces. `scripts/plot_run.mjs` is already plain JavaScript with no dependencies |
| D2 | Whether to report the engine's `documentHash` finding (E1) on #43 | not posted; the finding and its evidence are below |
| D3 | Landing order: this branch now stacks on the state space branch (`claude/state-measurement-runtime-wv5sbt`, merged at `32bbacc`), which is based on `main`, not `dev` | land state space on `dev` first, then this branch; or land both together. Either way the dev-versus-state-space conflicts resolved here (E7) recur there |
| D4 | #33 (draft, `feature/logic-memory-runner`): a second logic runtime with its own run format, replay and panel | close it, or re-express it on state space; not reviewed or commented on |
| D5 | #42's split: presentation work retargeted to `dev`, its simulation engine re-expressed on state space | the PR author's call; review posted: https://github.com/bdf1992/schematically/pull/42#issuecomment-5841735922 |

## For the state space engine (#43 owners)

| # | Residual | Evidence, and what closes it |
| --- | --- | --- |
| E1 | **The same document hashes differently in a file and in the editor.** `documentHash` covers defaults the editor fills in on open (component `editor`, `canvasId`, presentation size and slots), so a trace made from a file cannot be replayed on that file open in the editor | the engine's own `examples/state/and.sov`: `816c9631…` from the file, `34caf87f…` once the editor holds it; `and.11.sovtrace` carries the first, so replaying it in the editor is refused `REPLAY_KEY_MISMATCH`. Closes with a hash over authored truth, invariant under the editor's projection (STATE-SPACE.md: document identity is content). Until then this branch's export and tests run the engine in the page (`export_svg.py --run`) |
| E2 | The hash covers layout, so moving a Component invalidates a run shown in the editor (`DOCUMENT_CHANGED` in `src/57-state-view.js`) | a design question for the engine: whether a layout edit may keep a run, as #33 allowed. Follows the engine's rule until then |
| E3 | Stateful and level gates have no pattern: compare, threshold and Schmitt (`threshold`, slice 2, with continuous channels); D, T and JK flip-flops, SR and D latches, the C-element (`transition`, slice 5) | their tested specifications and the lessons from the retired runtime (power-on, races, ripple against synchronous) are in `LOGIC-GATES.md`, "Waiting for patterns" |
| E4 | No composition: `children` in a definition is named in STATE-SPACE.md, not built | half and full adders are single `truth_table@1` devices meanwhile; carry-lookahead and wider parts need it |
| E5 | No run surfaces: `schematic.run.*` (slice 1c) and Save Run / Open Run (slice 2) | the editor shows a trace (`view.stateSpace`) but cannot start one except through the engine's own API; flipping an input from the canvas waits for these |
| E6 | Continuous channels (1b runs binary only) | blocks levels, the level trace and transfer loop views, the reorder and window examples |
| E7 | The state space branch is based on `main`; merging it with `dev` conflicts in `index.source.html`, `index.html` and `src/05-data-core.js` (dev's `normalizeComponentSize` beside the port checks), and dev's `examples/09-proposed-service-review.sov` fails the round-trip rule until its Plane states `attachmentDefaults: "none"` | resolved on this branch at `32bbacc` (both sides kept; the example made canonical); the same resolution is needed wherever state space lands |
| E8 | A data-core save stamps `meta.updatedAt`, so a generated example is not byte-stable | `scripts/build_logic_examples.py` strips it; an example-writing path without the stamp would remove the workaround |

## This branch: optimization

From `LINEAR-NONLINEAR-SYSTEMS.md` §5, still open:

| # | Residual | What closes it |
| --- | --- | --- |
| O1 | Setup cost, minimum batch (nonconvex, discontinuous) | an on/off binary per stage over the existing branch and bound |
| O2 | Optimistic error on nonconvex bends between breakpoints | breakpoints on whole units, or a refine-until-the-true-curve-agrees loop |
| O3 | Branch and bound re-solves the dense LP at every node (about 7 s at 32 segments) | warm start from the parent's basis (dual simplex), cuts, a rounding heuristic |
| O4 | Local search uses finite differences and first-order steps | analytic gradients from `curve()`, quasi-Newton or SQP |
| O5 | Local search is fractional | a whole-unit local search to set against branch and bound |
| O6 | Starts are corners, centre and random | Latin hypercube, or starts at the linear relaxation's vertices |
| O7 | Time is a budget, not a sequence (makespan, precedence) | a time-indexed or event-based model; state space's logical time is the natural host |
| O8 | Wire rates as decisions under a latency target | a geometric program (log space) |
| O9 | Stochastic arrivals, queueing delay | a `congestion` curve ρ/(1 − ρ), convex, fits now |
| O10 | Quantities live in a sidecar (`.opt.json`), not the document | a file-format decision, with the carrier/Component record merge |
| O11 | No editor, API or MCP surface for solving | one data-core operation served to all three, after the model settles |
| O12 | Dense tableau: tens to a few hundred variables | sparse or revised simplex, or an optional external solver |
| O13 | A three-decision model has many near-equal optima along a ridge (found, genuine, not a defect) | a note for readers of `workshop3`; no change needed |

## This branch: whole units and `.sav`

From `WHOLE-UNITS-AND-STATE.md`, plus one found today:

| # | Residual | What closes it |
| --- | --- | --- |
| U1 | One worker; every stage shares one clock | stations or workers as resources with their own clocks |
| U2 | A fixed dispatch rule (nearest the market first) | dispatch as declared policy data; the optimizer's sequencing once time is a decision (O7) |
| U3 | Partial pulls can deadlock two stages competing for one input | reservation (a full kit or nothing), or explicit priority; an arbiter (`transition`, E3) |
| U4 | A learning curve restarts each horizon | curve index across horizons, if learning should persist |
| U5 | The event log is most of a `.sav` (70 KB a week) | snapshot and log as separate members, or logs as receipts beside the save |
| U6 | The completion gate is AND only | the gate as a state space definition (`truth_table@1` now; the C-element when `transition` lands) |
| U7 | **`simulate_sov.py` keeps its own clock, event log and saved state beside state space's logical time, ledger and `.sovtrace`** (found 2026-09-26) | express unit progress as state space observables and the completion gate as a definition, so a `.sav` becomes a run's snapshot; decide with the engine owners whether `.sav` and `.sovtrace` are one family |
| U8 | No editor, API or MCP surface for simulation | the runtime in the data core with parity; after U7 |

## This branch: logic and visuals

From `LOGIC-GATES.md` and `VISUAL-LANGUAGE.md`, plus what was found while building:

| # | Residual | What closes it |
| --- | --- | --- |
| V1 | Level trace and transfer loop views, and the ripple and synchronous counter pictures, left with the retired runtime | E3 and E6; the view code is in commit `9332839` |
| V2 | Three wires share one run in `full-adder.sov`'s picture, so which goes where is ambiguous | routing (`40-routing.js`) or the example's layout |
| V3 | Buses are naming conventions (`A0`..`A3`) | a bus as a carrier of width n, or several channels on one port |
| V4 | No X (unknown) value | three-valued logic as a categorical form |
| V5 | More gates worth having (decoder, encoders, parity, comparator, ALU slice as tables now; shift registers, FSMs, debouncer, arbiter with `transition`; window comparator, clamp, quantizer with `threshold`) | listed in `LOGIC-GATES.md`, "Other gates worth having" |
| V6 | The editor's state view reads channel `main` only | multi-channel chips when ports carry several channels |
| V7 | The run page (`plot_run.mjs --page`) is a standalone file, not an artifact or an editor view | D1 |

## Editor runtime: efficiency candidates

Found during the inventory in `LINEAR-NONLINEAR-SYSTEMS.md`; none changed:

| # | Candidate |
| --- | --- |
| R1 | `computeSignalState` stops after 6 passes and `diffuse` after 5, silently truncating deeper chains; a worklist would be exact and usually faster. STATE-SPACE.md plans `25-signal.js` as a projection of state space, which supersedes this |
| R2 | Diffusion is a linear system solved by fixed iteration; its fixed point can be solved directly (STATE-SPACE.md's declared `consensus` field, slice 3) |
| R3 | Routing is greedy per wire in index order; a second pass re-routing each wire against the others would lower crossings (also V2) |
| R4 | `choose_period` scans 2,100 grid points × every duration; candidate periods change only at P = (k ± ½)·d |

## Process and tooling

| # | Residual | What closes it |
| --- | --- | --- |
| P1 | `python scripts/qa.py` rewrites tracked files on every run (`tests/beta17-read-write.png`, `tests/beta18-inline-wire.png`, `tests/file-menu.png`, `tests/performance-results.json`, `tests/saved-test.sov`, `tests/saved-test.sovpak`); one run's copies were committed by accident and restored in `b77b67d` | write those outputs to a temporary or ignored directory, or ignore them |
| P2 | The workstation kernel (`ws`) cannot run in a cloud container (Python 3.11, no pydantic), so this session could not file workstation tasks for the rows above | logged in the workstation's `control/FRICTIONS.md`; file tasks from this log on the machine |
| P3 | `docs/visual/live-state-full-adder*.svg` are exported by hand, not by `build_visual_gallery.py`, so its `--check` does not hold them | add them to the gallery build (it would need a browser) |

## Retired on this branch (for the record, not owed)

This branch's own logic runtime and everything that served it: `scripts/logic_sov.py`, `src/07-logic-core.js`, `src/04-logic-pack.js`, `src/57-logic-live.js`, `scripts/logic_run.mjs`, `scripts/build_logic_pack_js.py`, `packs/logic/gates.json`, the `logic.*` editor API, the MCP tool `schematic.logic.run`, and their tests. Superseded by state space (decided 2026-09-26) in `c4fce0a`.
