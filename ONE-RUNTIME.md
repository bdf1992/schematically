# One runtime · design (proposed 2026-09-26)

**Status: design, proposed.** Maps the five runtime and logic-gate lines that exist today into one design space, names what each keeps, what each gives up, and the bounded work that gets `dev` to one engine. It changes nothing in the code. The reference for the engine itself is `STATE-SPACE.md` (branch `claude/state-measurement-runtime-wv5sbt`, #43); this document is the reference for the *reconciliation* and retires when the last line below has landed or been closed.

Sources: `STATE-SPACE.md` and #43 (slices 0a, 0b-1, 1a, 1b, 1c landed on the state space branch at `6a39efd`); `GRAPH-MODEL.md`, `NOTATION-MODEL.md` and PR #42 (merged to `dev` at `2cd2b76`, follow-ups in `docs/residuals/2026-09-26-graph-primitives.md`); PR #33 and `LOGIC-RUNTIME.md` (`feature/logic-memory-runner`, draft); `docs/vision/RESIDUALS.md` and `docs/vision/LOGIC-GATES.md` on `claude/linear-nonlinear-optimization-xz7t48`; PR #41 (`astra/work-graph-foundation`); `src/25-signal.js` on `main` and `dev`; Issue #6; the review on PR #42 (2026-09-26) and Bdo's decision the same day that **state space is the canonical runtime**.

## Purpose

A schematic says what exists and how it connects. A runtime says what is true at a moment and how it got there. Five pieces of work, four of them written in the same three days, each answer the second question with their own clock, their own gate vocabulary, their own ledger and their own tools. They do not disagree about what a gate is; they disagree about **where behaviour lives, what time is, and who may write truth**. This document settles those three questions once, and turns every remaining difference into a definition, a pattern, a projection, or a piece of bounded work.

The rule it applies is the roadmap's own: *do not fork implementations for root/nested/1D-hosted/agent-authored variants of the same primitive* (`ROADMAP.md`, NEVER). A second scheduler is that fork.

## What exists

| Line | Where | Engine | Time | Behaviour | Truth and replay | Surfaces | Standing |
|---|---|---|---|---|---|---|---|
| **A. Signal picture** | `src/25-signal.js`, `src/55-render.js` on `main` and `dev` | none: a fixpoint over `signalMode` (`source` / `relay` / `passive`) computed at render, colour mixed by five passes of diffusion | animation seconds: `packetTravelSeconds(pathLength) / rate`, rate = `meta.timeScale` × source rate × wire rate, clamped 0.1–8 | none; `SYMBOLS` (GATE, SWITCH, HOLD, BUFFER, LIMIT, ONE-WAY, ACT) are vocabulary with a `meaning` and no evaluation | none; nothing is recorded | none | on `main` and `dev`; the 6-pass ceiling became a per-node bound on `dev` |
| **B. Logic runner** | `src/07-logic-core.js`, `src/90-logic-panel.js`, `LOGIC-RUNTIME.md` (PR #33, draft, based on `dev` at `30b9edf`) | event runner over table definitions in `document.meta.logic`; a Component opts in with `config.logic.definition` | integer ticks, `(time, sequence)`; transport delay; `config.logic.delay` per Component, Path delay default 1 | tables `[inputs, priorState, outputs, nextState]`, ≤ 8 bits, `kind: source \| table` | `.sovrun` (diagram + session); restore re-executes the recorded inputs and must agree; "layout edits may continue a run" | `runtime.execute({action: start \| input \| step \| run \| get \| replay \| restore})` on browser, HTTP, MCP; server sidecar `<file>.run.json` | open draft; not reviewed; `dev`'s `ROADMAP.md` and `POST-RC-INDEX.md` still call it "the runtime proposal" |
| **C. Graph engine** | `src/07-graph-core.js` (706 lines), `src/65-sim-control.js`, `src/66-narration.js`, `GRAPH-MODEL.md` §6 and "Signals, time and the clock" (PR #42, on `dev`) | message simulation plus levels, one clock | real time: `latencyMs` per wire (default `DEFAULT_LATENCY_MS`), clocks in `periodMs`; `sim.advance(ms)`, `sim.tick()`, `sim.at(time, …)` | per-symbol code (BUFFER queues, GATE calls a handler, SWITCH follows control, LIMIT) plus `config.signal = {mode: derived, combine: or \| and \| not \| max \| min \| mean \| sum, threshold}`; a glyph's `signal.combine` sets the card's default; junction policies `fanout \| distribute \| merge \| join \| select`; human pauses; `config.acl` on a Plane with principals | snapshot / restore; effect keys `<node>:<value>`; saved scenarios with checks; edges `{at, node, from, to, polarity, cause}`; a missing signal is asserted 1 | 14 `schematic.sim.*` tools, `schematic.graph.query`, browser `sim`, `clock`, `graph`; the canvas control plane (play, pause, step, reset, speed, levers, send, approve / reject) | merged; its own residual log accepts state space as canonical and names the migration |
| **D. State space** | `src/03-canonical.js`, `src/07-state-space.js` (971 lines), `src/05-data-core.js`, `src/06-attachment-core.js`, `data/core.logic.pack.json`, `formats/schematic.{definition,pack,pattern,state-record,trace,run-receipt}.schema.json`, `STATE-SPACE.md` (branch `claude/state-measurement-runtime-wv5sbt`, based on `main`) | deterministic fold over a hash-chained ledger; two-phase ticks; devices read only committed state | integer logical ticks; Path `delay` ≥ 1, device `delay` ≥ 0; "geometry does not set logical delay" | definitions in packs, each an instance of a pattern (`truth_table@1`, `merge@1`; `pass`, `route`, `threshold`, `materialize`, `consensus`, `advection`, `rate`, `compose`, `transition` by later slice); a Component binds one by `config.definition: "logic.and@1"` and its ports are generated from the contract; declared ports `{id, side, t, flow, channels}` (0b-1, #45) | replay key (`documentHash`, resolved definitions, runtime version, inputs, seed); `.sovtrace`; every same-tick order draw recorded; a stateful device without a declared initial state refuses (R-02) | `schematic.run.start \| step \| settle \| replay \| trace`, `schematic.state.query`; parity on browser, HTTP, MCP; the Ports panel | slice 1 complete (`6a39efd`); open: #47 bind-only, #48 residue, #49, #50 `documentHash` in the editor, #52 quadratic `step()`; **not on `dev`** |
| **E. Logic on state space** | `data/logic.gates.pack.json`, `data/logic.glyphs.json`, `examples/logic/`, `src/57-state-view.js`, `scripts/run_state.mjs`, `scripts/plot_run.mjs`, `docs/vision/LOGIC-GATES.md` (branch `claude/linear-nonlinear-optimization-xz7t48`, stacked on D at 1b, merged with `dev`) | none of its own since `c4fce0a`: it retired a fifth runtime (`scripts/logic_sov.py`, `src/07-logic-core.js`, `src/04-logic-pack.js`, `src/57-logic-live.js`) and builds on D | D's | twelve more `truth_table@1` definitions (buffer, nand, nor, xnor, the four implications, majority, mux, half and full adder) with IEC glyphs; tested specifications for the stateful gates that `threshold` and `transition` will carry | D's; plus `simulate_sov.py` / `.sav` keeps its own clock and log beside D's (its residual U7) | a passive state view of a replayed trace on the canvas; a run page | branch; its residual log names the landing order (D3) and the `dev`-versus-D conflicts it already resolved (E7) |

Two more facts bear on the map:

- **PR #41** (`astra/work-graph-foundation`) carries a `src/07-graph-core.js` of its own: a 143-line *read-only* graph profile with "no scheduler, authority evaluator, CRUD implementation, or network access". Same path as C's 706-line engine, different content. It is the shape C's query half should end in.
- **The trunk is `dev`** (`docs/GIT.md` in the workstation; `docs/BRANCHING.md` here). D is based on `main`. Merging D into `dev` conflicts in `index.source.html`, `index.html`, `src/05-data-core.js` (`normalizeComponentSize` beside the port checks) and needs `examples/09-proposed-service-review.sov`'s Plane to state `attachmentDefaults: "none"`; E resolved all of it once at `32bbacc`.

## The design space

Three settlements, then everything else is placement.

1. **Behaviour is data.** A gate, a clock, a junction policy, a delay, a switch is a *definition* in a pack, an instance of a *pattern* the engine ships. The engine's pattern set is closed and grows by review. No module other than `07-state-space.js` evaluates behaviour, and it evaluates only definitions. A glyph is the `projection` member of a definition, never the owner of behaviour.
2. **Time is the engine's integer clock.** One logical tick. Path delay and device delay are declared in ticks. Wall-clock time touches exactly one place: the editor's transport, which maps ticks to seconds for playback. Animation pacing (`meta.timeScale`, per-entity `rate`) is presentation and can never change a logical outcome.
3. **Truth is the ledger.** Only the engine appends to a run's ledger, through legal operations. Everything shown (a level, a lit wire, a packet, a narration line, the idle signal colour) is a projection of records, and every projection is rebuildable from the ledger. The document file carries authored state only; a run is its own file.

### Typology: one owner per concern

| Concern | Owner | Record it produces | Who reads it |
|---|---|---|---|
| Identity | `03-canonical.js`: canonical JSON, SHA-256, seeded draw | `documentHash`, chain hashes | data core, engine, traces |
| Topology and legality | `05-data-core.js`, `06-attachment-core.js`: declared ports, channels, direction, boundary crossing, principals | refusals with codes; the compact document | editor, API, engine (it never reaches through a boundary the data core would refuse) |
| Behaviour | packs of definitions (`data/*.pack.json`) over engine patterns | contracts (generated ports, observables) | engine; the Ports panel; glyph rendering |
| Time and evaluation | `07-state-space.js`: ledger, two-phase ticks, fold, patterns, settle | state records, particles, order draws, receipts | every projection; `state.query` |
| Runs as files | `75-persistence.js` | `.sovtrace`; traces in `.sovpak` | Open Run, goldens, replay |
| Surfaces | `85-api.js`, `mcp/server.mjs`, `mcp/tools.json` | `run-receipt@0.1` | browser, HTTP, MCP, scripts |
| Projection on the canvas | `25-signal.js` (idle colour), `55-render.js` (packets), `57-state-view.js` (levels and chips), `65-sim-control.js` (transport), `66-narration.js` | nothing authoritative | people |
| Read-only graph questions | the query half of `07-graph-core.js` (reach, paths, cycles, order, cut, boundary, untyped, blocked, acl, export) | answers, no records | agents, layout, review |

### Topology: how the parts relate

```text
.sov (authored)  ──load──▶  data core  ──legality──▶  engine: fold over ledger  ──▶  records
   │  declared ports, delays,            ▲                 │  run.start / step / settle       │
   │  definition refs, initial values    │                 │  every draw recorded             │
   │                                     │                 ▼                                  ▼
packs (definitions ◀─ patterns)  ────────┘            .sovtrace (replay key + event log)   projections
                                                                                            ├─ idle signal colour (25)
transport (65) ── ticks ⇄ seconds ── run.step ─────────────────────────────────────────────├─ packets (55)
                                                                                            ├─ state view (57)
                                                                                            ├─ narration (66)
                                                                                            └─ legend, run page
```

Nothing on the right writes to anything on the left. The transport is the one arrow that carries a person's gesture (play, a lever, approve) into the engine, and it does so only as a registered input at a tick.

## Placing each line

### A. The signal picture becomes a projection

- `computeSignalState()`'s active set is the settled state of a run in which every source is high and every relay passes. The idle canvas shows that settled state, computed by the fold (`run.settle` with every source registered high), and `25-signal.js` reads records instead of iterating itself. The per-node pass bound on `dev` becomes unnecessary.
- The five-pass colour diffusion becomes the declared field `presentation.signal-color`, operator `consensus`, when the `consensus` pattern lands (slice 3). Until then the mixing stays as it is, marked as presentation.
- Packets are driven from trace particles while a run is live; when no run is live they keep today's animation. `packetTravelSeconds / rate` is pacing. The open rate question (#40, workstation task `schematically-timescale-document-rate-wins-over-view`) is decided in these terms: the document's authored `timeScale` wins over the view's, zero means paused, one admission rule on file, API and view; none of it reaches the engine.
- `SYMBOLS` keep their words and meanings. GATE, SWITCH, ONE-WAY, HOLD, BUFFER, LIMIT and DELAY get definitions in `core.logic` where a pattern carries them (GATE as `threshold`, SWITCH as `route`, HOLD as `transition`, BUFFER and LIMIT as `merge` with `queue` and a capacity), and until then are vocabulary with no behaviour, as today. A symbol never grows a code path.

### B. PR #33 closes; its lessons are already kept

D keeps what B established: integer time with a serialization-only sequence, transport delay, tables as data, a run kept apart from the document, restore that verifies replay. What B did that D does differently, D does deliberately: definitions live in packs rather than `meta.logic`; state lives in `device.state` records rather than in the table row; the file is `.sovtrace` rather than `.sovrun`; the replay key holds a content hash rather than a compiled program. Nothing in B needs to be ported. The PR is closed with that said on it, and `dev`'s `ROADMAP.md` and `docs/vision/POST-RC-INDEX.md` stop naming it as the runtime proposal.

### C. The graph engine splits: queries stay, simulation is re-expressed

| In C | In the one runtime |
|---|---|
| `latencyMs` on a wire; `DEFAULT_LATENCY_MS` | Path `config.delay` in ticks, ≥ 1, declared; no default latency |
| `config.signal = {mode: derived, combine, threshold}` and a glyph's `signal.combine` | `config.definition: "<id>@<v>"`; `and`, `or`, `not`, `xor` from `core.logic`; `max`, `min`, `mean`, `sum` and `threshold` wait for continuous channels and the `threshold` pattern (slice 2) |
| asserted level, `sim.set`, `sim.at`, a `{set}` or `{toggle}` payload | a registered value at a tick (`run.start` inputs; a scheduled input is an input at a later tick) |
| a missing signal is asserted 1 | refused (R-02): a source declares its initial value or the run refuses |
| continuous 0..1 with `epsilon` | binary now; continuous under the numeric policy (fixed point) when slice 1b's follow-up lands (E's residual E6) |
| edges `+` / `−`, `config.signal.on` emitting a message | a transition is a particle; "emit on edge" is a `transition` definition whose output is the particle |
| clocks `{periodMs, phaseMs, duty, wave, sampleMs, cycles}` | a `transition@1` definition with period, phase, duty and cycles in ticks (slice 5); `saw`, `triangle`, `sine` wait for continuous channels |
| junction `fanout` | Path semantics: a Point relays to every outgoing Path except the ones that delivered to it this tick (decided in 1b) |
| junction `merge`, `join` | `merge@1` combines (`or`, `and`, `min`, `max`, `sum`, `first`, `last`, `queue`); `join` (wait until every input has arrived) is a pattern ask |
| junction `distribute`, `select`; SWITCH | `route@1` (slice 2): selector chooses an output |
| BUFFER queues, LIMIT | `merge@1` with `queue` plus a capacity parameter: a pattern ask |
| GATE calls a handler | a definition, or an effect (below); never a handler in the engine |
| human pause, `resume`, approve / reject | an attempt whose result is recorded: the run parks at the step, the person's answer enters the ledger as a registered value, and replay reads it (STATE-SPACE.md, *Generative steps and attempts*) |
| mediated effect keyed `<node>:<value>`, reconcile | effect keys `(run, entity, tick, occurrence)` with a payload fingerprint; the same key with a different payload is refused (*Collapse and receipts*) |
| snapshot / restore | a cache of the fold at a ledger position; `.sovtrace` |
| saved scenario with checks | a set of registered inputs at ticks plus assertions over `state.query`; stored as a golden trace beside the example |
| `config.acl`, principals, enter / exit / read / write | a data-core legality check at the boundary crossing, the same place `endpointAllowsAccess` already decides read / write. A particle carries a `principal`; the engine asks the data core at every crossing and records a refusal in the ledger. The ACL stays authored data on the Plane |
| a message with a payload (`caseId`) | a particle whose value has the `categorical` form (an id) and whose payload is fingerprinted for effect keys; a structured payload form is a pattern-schema ask |
| `65-sim-control.js` driving `07-graph-core.js` | the same transport driving `run.step` / `run.settle`, with a declared ticks-per-second as its only clock |
| `66-narration.js` following `latencyMs` time | narration lines keyed by logical tick |
| `schematic.sim.*` (14 tools), browser `sim`, `clock` | `schematic.run.*` and `schematic.state.query`; browser `run` and `state` |
| `graph.query(...)`, JGF / DOT / GraphML export | kept as is; the query half of `07-graph-core.js`, which is the shape PR #41's read-only `07-graph-core.js` already has |
| examples 09, 10, 13 and `tests/graph_core_qa.py`, `sim_control_qa.py`, `notation_qa.py`, `access_panel_qa.py` | rewritten against the engine, each with a golden trace; the Print AI scenarios of example 09 become traces with their assertions |
| load position `07` shared with `07-state-space.js` | the simulation half is deleted; the query half takes a number of its own |

### D. State space lands on `dev` and closes its own follow-ups

The engine does not move; the trunk moves under it. E's resolution at `32bbacc` is the map for the merge. Then #47, #50, #52 close on `dev`. #50's normal form is decided together with E's question E2 (below).

### E. Its packs and view join the engine; its second clock does not

- `logic.gates` and `logic.glyphs.json` move beside `core.logic` in `data/`, one pack set; the `logic` notation's IEEE 91 glyphs become the `projection` of those definitions, so a glyph and its behaviour cannot disagree because they are one record.
- `57-state-view.js` is the canvas projection of a trace and the natural home of C's level dots, meters and lit wires.
- `simulate_sov.py` and `.sav` (U7) express unit progress as observables and the completion gate as a definition, so a `.sav` is a run's snapshot; whether `.sav` and `.sovtrace` are one family is decided with the engine's owners. This is E's work and is filed as its own task, not on the critical path.

### Ports and glyph terminals are one thing

D declares ports as data with side, t, flow and channels, and generates a bound Component's ports from its definition's contract. C's notation gives a wired glyph one attachment point per terminal, aligned by `at`, with the terminal's role as flow. These are the same fact from two ends. The rule: **a definition's contract names the ports; a glyph's terminals name where on the card they sit.** A glyph whose terminals do not match the definition it projects is refused at pack load. The `left` / `right` / `top` trio stays template data, as 0b-1 made it.

## Words

One concept, one word, and it is the product's word. Renames on the way in:

| Elsewhere | Here |
|---|---|
| node, junction, hyperedge | Component, Point, Path |
| edge (a level transition) | transition, or particle when it travels |
| level, signal (a value) | signal state (a record on one channel of a port) |
| merge (any input passes) | a Point's relay; `merge` is the pattern that resolves same-tick arrivals |
| latency | delay, in ticks |
| scenario | a golden trace |
| session, `.sovrun`, `.sav` | run, `.sovtrace` |
| `meta.logic`, `config.logic.definition`, `config.signal.combine` | `config.definition` |
| runtime (in `25-signal.js`'s sense: the editor's live objects) | editor state; *runtime* is the engine |

## Gaps this space still has

Each is a pattern ask or a decision, not a second engine.

- **`transition@1`** (clocks, edges, latches, flip-flops, the C-element): specified with tests in `docs/vision/LOGIC-GATES.md`, "Waiting for patterns". Unblocks C's clocks and example 10.
- **`route@1`**, a `queue` capacity on `merge@1`, and a `join` combine: unblock C's junction policies, SWITCH, BUFFER and LIMIT.
- **Continuous channels** under the numeric policy: unblock C's meters and waves, `threshold`, and E's level views.
- **A structured payload form** and a **principal on a particle**: unblock C's messages and access control.
- **Composition** (`children` in a definition): named in `STATE-SPACE.md`, not built; adders are single tables meanwhile.
- **`documentHash` normal form** (#50 with E2): the hash must be the same in a file and in the editor, and it should cover exactly what the fold depends on.

## Decisions owed (Bdo)

| # | Question | Recommendation |
|---|---|---|
| 1 | Landing order: D is based on `main`; the trunk is `dev` (E's D3) | Land D on `dev` first, by one merge that reuses E's resolution; E and C's migration follow. Everything below stacks on it |
| 2 | Does `documentHash` cover geometry? (#50, E2; B allowed layout edits to continue a run) | No. The replay key is "everything the fold depends on", and geometry does not set logical delay, so the hash is over the fold's input: topology, ports, channels, delays, definition references, initial values. That one normal form closes #50 and E2 together, and a drag no longer invalidates a shown run |
| 3 | PR #33 | Close, with the note above; nothing to port |
| 4 | C's simulation half: migrate or hold | Migrate in the order of the tasks below; hold nothing, because every held week is a week `dev` has two clocks |
| 5 | Rate policy (#40) | As written under A: the document's rate wins, zero is paused, one admission rule, and rate is pacing only |
| 6 | Messages, human steps and access control: engine patterns, or a layer that waits | Patterns and data-core legality, as mapped under C. A waiting layer is the second engine under another name |

## Bounded work

Filed in the workstation as tasks charged to the mission *One runtime: state space serves every signal, gate and clock*. Order is dependency order; each task's acceptance is the full gate (`python scripts/qa.py`) plus what is named.

1. **This design lands on `dev`** as `ONE-RUNTIME.md`; `POST-RC-INDEX.md` points at it.
2. **State space lands on `dev`.** One merge of `claude/state-measurement-runtime-wv5sbt`, conflicts resolved as at `32bbacc`; the gate green with every suite from both sides. Decision 1.
3. **`documentHash` is the fold's input normal form.** Equal for `load(file)` and `open-in-editor(file)` on every example; `and.11.sovtrace` replays in the browser; a moved Component keeps a shown run. Closes #50 and E2. Decision 2.
4. **`step()` keeps an undo record, not a queue copy.** Closes #52.
5. **A definition is bound only by binding.** Closes #47.
6. **Gates are definitions on `dev`.** `config.signal.combine` and the glyph's `signal.combine` give way to `config.definition`; `logic.gates` and the glyph file join `core.logic` in `data/`; the `logic` notation projects definitions; a glyph whose terminals disagree with its definition is refused; example 13 rebuilt with a golden trace.
7. **`transition@1`.** Clocks, edges, latches and flip-flops from the specifications in `LOGIC-GATES.md`; example 10 rebuilt with a golden trace.
8. **`route@1`, a queue capacity, and `join`.** C's junction policies, SWITCH, BUFFER and LIMIT as definitions.
9. **Particles carry a principal and a payload; crossing is data-core legality.** C's ACL re-expressed; refusals in the ledger; effect keys with payload fingerprints; human steps as recorded attempts; example 09's five scenarios as golden traces with assertions.
10. **One control plane.** The transport, narration and the state view drive and read the engine; ticks-per-second is the transport's only clock; packets follow trace particles while a run is live.
11. **The graph engine's simulation half retires.** `schematic.sim.*` and browser `sim` / `clock` go; queries stay and take their own module number (PR #41's read-only shape); C's words renamed; C's four suites rewritten against the engine.
12. **`25-signal.js` is a projection.** The idle picture is the settled fold; rate is pacing with the #40 rule. Decision 5.
13. **PR #33 closes and the docs stop naming it.** Decision 3.
14. **E's units simulation runs on the engine** (U7, U8). E's owners; not on the critical path.

## Invariants this adds

Beyond `STATE-SPACE.md`'s, each to become a QA assertion when its task lands:

- exactly one module on `dev` schedules ticks, and it is `07-state-space.js`;
- no engine code path reads a wall clock, `latencyMs`, `timeScale` or `rate`;
- no symbol, glyph or notation carries behaviour; every behaviour on the canvas resolves to a definition reference;
- every run tool on every surface is a `schematic.run.*` or `schematic.state.*` tool, and `mcp/tools.json` lists no other runtime tool;
- every example that runs has a golden trace beside it, and every golden replays byte-identical.
