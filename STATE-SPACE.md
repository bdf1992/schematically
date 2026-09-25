# State Space · design

**Status: design, not yet accepted.** Nothing here is implemented. This document fixes the model before code is written; once accepted, the slices at the end become issues and it becomes the living reference for the concern, like `FORM-MODEL.md`.

**Review pass (2026-09-25).** Inline notes below come from a standards comparison (DEVS and VHDL/SystemC scheduling, Temporal-style replay, W3C PROV, OpenTelemetry and CloudEvents, digital-twin specs, GUM/VIM metrology, directed graph Laplacians, idempotent effects) plus a red-team pass over it. Two markers are used:

- **Suggestion** — a proposed design change, with the slice it belongs to.
- **Review question** — something the design or the code review has to answer before the section is accepted.

The model holds up. Most suggestions are determinism details for slice 1; instrument-facing additions are held back to slice 4 so the core record stays small.

Sources: *State Planes for Governed Graph Systems* (2026-09-25), Issue #6 (logic machine), `docs/vision/DATA-DRIVEN-SCHEMATIC-LANGUAGE.md` ("Logic/runtime proof"), and the current `src/25-signal.js`.

## Purpose

A schematic already says what exists and how it connects. The state space is what the schematic says about **what is true at a moment, and how anyone knows it**: every value is computed from events or measurement, carries its certainty, and records whether observing it changed it.

It serves two uses, built in this order:

1. **Runtime (first).** Schematically executes its own documents: sources change values, Paths carry them, gates evaluate them, receipts record what happened. Issue #6's logic machine is the first consumer.
2. **Instrument (later).** Schematically shows the state of an outside governed graph (a workstation, an agent pipeline): measured records arrive from outside and are laid over a document that models that graph.

Both use the same record, the same fold and the same projections. The instrument adds nothing but an import of measured records and a way to bind their subjects to document entities.

## Vocabulary

One concept, one word. The source paper's words collide with words the editor already owns, so they are translated here and the paper's words are not used in code, files or UI.

| Paper | Here | Why |
|---|---|---|
| state plane | **state space** | `Plane` is the 2D primitive. |
| state point | **subject** | `Point` is the 0D primitive. A subject may be a Point, but also a Component, a Path, a run. |
| state field | **field** | No collision. |
| control loop | **control** | No collision. |
| measurement / reading | **observation** | Matches the existing OBSERVE symbol. |

**State space is always two words.** `Space` alone keeps its horizon meaning (`HORIZON-SPACE.md`: the coordinate domain and admitted grammar a document lives in). The two relate: a document lives in a Space; its state space is the state of that document over time. Code names use `stateSpace` / `state-space`, never `space`.

**Logical time is not animation time.** `diagram.meta.timeScale` and per-entity `rate` pace the rendered packets. Logical time is the integer clock of the state space. Changing rate, zoom or geometry may change how long a packet takes on screen; it never changes a logical outcome.

## Model

```text
State space
├─ subjects        addressable things state is about (entity + optional point + run)
├─ records         every state claim, one shape (the state record)
├─ event log       the authoritative, ordered inputs of a run
├─ fold            deterministic function: document × event log → derived records
├─ fields          one observable over all subjects, with a declared spread rule
├─ observers       who or what produced a record, with calibration and class
├─ residuals       differences the state space can learn from
└─ control         observe → estimate → compare → gate or route → act → record
```

### Source of truth

The **event log is authoritative; all other state is a fold over it.** This matches the existing file rule: a `.sov` carries authored truth only and runtime projections are rebuilt, never saved.

- Registered values (a lever's position, an input vector) and observations enter the log.
- Derived records are outputs of the fold and must be recomputable: replaying the log against the same document revision yields byte-identical derived records. That identity is the first golden test.
- A cached derived value is **materialized** state. It is allowed only with the inputs it stands in for, so the state space always knows what would invalidate it.

> **Suggestion (slice 1).** The replay key is larger than the document revision. Replay identity holds only against the same *document revision + pack versions + runtime (fold) version + initial registered values + seed*. The fold is an input like the document is; a runtime change can break byte identity with no document change at all.
>
> **Suggestion (slice 1).** Log effect *intents* as well as their outcomes. On replay, recompute the intent and compare it to the logged one; a mismatch is a typed nondeterminism refusal, the way Temporal fails a replay instead of silently diverging.
>
> **Review question.** Is a materialized value keyed by the hashes of its input records plus rule id@version? That makes invalidation a hash comparison instead of a dependency walk.

### The state record

Every claim has the same coordinates, whether it is a logic level, a gate verdict, a measured latency or (later) a forecast.

| Coordinate | Answers | Values |
|---|---|---|
| `subject` | about what | `{entity, point?, run}` |
| `vantage` | seen from where | `space` (Eulerian: the whole graph at a time), `point` (Lagrangian: one subject's history), `relative` (against a `reference`) |
| `observable` | what is measured | a declared observable id, e.g. `logic.level`, `cost`, `latency` |
| `kind` | how it became true | `registered`, `measured`, `derived`, `predicted` |
| `form` | its shape | `binary`, `continuous`, `categorical` |
| `value` | the value | per `form` |
| `time` | when | `{logical, sequence}`; `wall` optional (instrument use); `mode: observed \| predicted` |
| `certainty` | how sure | `{kind: exact}` first; distributions later |
| `observer` | who produced it | an observer id: a rule, a sensor, a person |
| `provenance` | from what, by which rule | `{rule, inputs: [record ids], threshold?}` |
| `perturbation` | did observing change it | `none`, `disturbed` (with a ledger entry), `created` |

Draft shape (the schema will be `formats/schematic.state-record.schema.json`):

```json
{
  "format": "soveraeign.schematic/state-record@0.1",
  "id": "sr-000017",
  "subject": {"entity": "c-and1", "point": "q", "run": "run-1"},
  "vantage": "point",
  "observable": "logic.level",
  "kind": "derived",
  "form": "binary",
  "value": true,
  "time": {"logical": 4, "sequence": 17, "mode": "observed"},
  "certainty": {"kind": "exact"},
  "observer": "rule:logic.and@1",
  "provenance": {"rule": "logic.and@1", "inputs": ["sr-000012", "sr-000015"]},
  "perturbation": "none"
}
```

> **Suggestion (slice 1).** Put `unit` on the observable declaration (not on every record). Units are the one record extension worth taking early; every twin standard reviewed (DTDL, OPC UA, AAS) carries them, and adding them later touches every pack.
>
> **Suggestion (slice 4, not before).** The instrument will need more coordinates: a `quality` status separate from certainty (a value can be exact and stale), `time.source` vs `time.receipt` (OPC UA's source and server timestamps), and `certainty` in GUM terms (`{u, k, evaluation: A|B}`). None of these mean anything in an exact deterministic runtime, so they stay out of the core schema until measured records exist.
>
> **Review question.** Is `time.sequence` semantic or serialization only? After the execution changes below, it should be serialization only: equal-time outcomes must not depend on it.

### Kinds of state

| Kind | Source | Truth test | Here |
|---|---|---|---|
| registered | written by an authorised act | did the write pass the data core's legality? | a source's value, an input vector, a switch position |
| measured | read by an observer | is the observer calibrated? | an OBSERVE reading; an imported instrument reading |
| derived | computed by a rule | can it be recomputed from its inputs? | a gate output, a field value, a Component's active state |
| predicted | projected forward | how did past forecasts score? | deferred |

> **Suggestion (slice 4).** Add `estimated` as a fifth kind when the instrument lands: a value assimilated from measurement plus prediction is neither measured, derived by an exact rule, nor predicted. The control loop already has an estimate step with no kind to record it.

Every derived observable is declared with three properties the fold uses to decide whether a value is fresh enough to gate on:

- **update rule**: the rule id and version;
- **blast radius**: `local` (update in place on each event), `regional` (invalidate within k hops, recompute on read), `global` (recompute in batch or approximate);
- **staleness tolerance**: in logical ticks.

### Vantages

- **space** is what the editor paints: the value at every subject at one logical time.
- **point** is what a packet shows: one transition carried along a Path, with its history.
- **relative** is where control lives: the difference across a Path, a run against its baseline, a value against a threshold.

When a subject's value changes, the state space reports which part moved it: the value changed where the subject sits, or the subject moved into a different region (the paper's material derivative). In the runtime these are, respectively, an input changing under a gate and a packet arriving somewhere new; the trace names which.

### Signal state and particles

Kept exactly as Issue #6 separates them:

- **Signal state** is the current value at an attachment Point or channel. It is a record with `vantage: space`.
- **A particle** is a transition moving along a Path: value or change, channel, logical departure and arrival, provenance. It is an event in the log and a `vantage: point` view of it.

A gate evaluates signal state, never particles, so an AND gate sees both inputs when only one transition arrives. The rendered packet is a projection of a particle; it is never the source of a value.

> **Review question.** Does every gate read signal state *committed at the end of the previous tick*, and never a value written in the tick it is evaluating? Delta-cycle determinism in VHDL and SystemC holds only when processes communicate through committed signals; SystemC loses it the moment two processes share a variable. Any code path in `07-state-space.js` that lets a device read in-flight state recreates that shared variable.

### Assertions: binary as a cut through continuous

A binary verdict is the visible half of a measurement. A GATE's output is an assertion, which keeps what a bare boolean loses:

| Field | Example |
|---|---|
| predicate | `level_high` |
| value | `0.87` |
| threshold (enter / exit) | `0.80 / 0.75` |
| margin | `+0.07` |
| observer | `rule:gate.threshold@1` |
| rule version | `gate.threshold@1` |
| time | logical 12 |

Two thresholds give hysteresis, so a value near the cut does not chatter. Pure boolean logic is the degenerate case: value is 0 or 1, one threshold, margin ±1.

> **Suggestion (slice 2).** Hysteresis needs memory: a value inside the dead band is decided by which side the gate was on. Keep that memory in the log. A device's memory is an explicit `state` record (`vantage: point`, observable `device.state`) written at commit; the threshold rule reads its own committed state and nothing else. Latches, edges and clocks in slice 5 then reuse the same mechanism, so "stateful device" means "a rule that reads its own prior records."
>
> **Suggestion (slice 2).** A threshold gate requires a declared initial state as a registered value in the document. Without it, the first output inside the dead band is undefined.
>
> **Review question.** Slice 2 ships enter/exit thresholds but stateful devices are deferred to slice 5. Either the `state` record moves into slice 2 (recommended; it is one record type), or slice 2 ships single-threshold gates and hysteresis moves to slice 5.
>
> **Review question.** Define margin as distance to the *active* threshold (enter or exit, depending on state). Once uncertainty exists (slice 4), margin divided by standard uncertainty gives a z-score.

### Fields

A field is one observable defined over every subject, including where nothing was measured: samples, a declared spread rule, an uncertainty that grows with distance from samples, a gradient across each Path, and snapshots so drift in the field itself is visible.

Spread rules run over the graph Laplacian `L = D − A` of the document's connection graph:

- **diffusion**: values spread along Paths and even out (risk from a failing Component to what depends on it);
- **advection**: values travel with directed flow (budget consumed, taint from an unverified input).

Today's colour mixing in `25-signal.js` is an undeclared diffusion with fixed pass counts. It becomes a declared field (`presentation.signal-color`, diffusion, `regional`) so the colour on screen has a rule, a rate and a provenance, and colour stops standing in for signal value.

> **Suggestion (slice 3).** `L = D − A` is ambiguous on directed Paths. Each field declares its operator by name:
>
> - `consensus` — in-degree Laplacian; nodes pull toward what feeds them.
> - `advection` — `L_adv = D_out − A_in`; flow into a node equals flow out, so the total is conserved. Budget and taint need this one.
>
> Libraries choose silently (NetworkX's `laplacian_matrix` uses out-degree), so the declaration is the only safe source.
>
> **Suggestion (slice 3).** An explicit step `x ← x − εLx` is stable only for ε below a bound set by the graph's maximum degree. Validate ε against the document's graph at load, or a field blows up deterministically.
>
> **Review question.** Which operator does `presentation.signal-color` use? Colour follows direction but is not a conserved quantity, which suggests `consensus` along Paths.

### Observers and perturbation

Each observer is registered with its **class** and **limits**:

- **passive**: reads recorded state and changes nothing. The OBSERVE symbol ("reads evidence from outside the action path") is passive by definition.
- **active**: disturbs the subject: spends budget, pauses a run, consumes context. Active observations write a perturbation ledger entry and are paid **relative to the subject observed**: each one draws from the observed run's own budget, capped by a share its definition declares (for example, at most 10% of what remains). There is no separate absolute pool for looking; the more a run has left, the harder it may be looked at, and a run near exhaustion cannot be drained by observing it.
- limits: resolution, noise, drift, latency. Recorded per observer; the runtime's own rules are exact, so these matter first for the instrument.

For any record, the state space can answer: observed passively, observed actively, or created by the act of observing.

**Order matters for non-commuting observations.** Two active observers whose order changes the outcome must have that order fixed by the document; the fold flags any pair it sees give different results when swapped.

> **Suggestion (slice 4).** The budget rule leaks. "At most 10% of what remains" per observation never reaches zero, but the cumulative share is 1 − 0.9ⁿ: ten observations take 65% of the run's budget, twenty take 88%. Replace it with a **reserved observation account**: at run start a declared share of the *initial* budget moves into an observation ledger; active observations debit it through logged events; exhausting it is a typed refusal *for observation*, and the run continues. This amends Settled #4 in its mechanism, and keeps its intent (relative to the run, never an absolute pool).
>
> **Suggestion (slice 4).** Replace pairwise swap checks with declared read/write sets on observers. Passive observers commute with everything; active observers with disjoint write sets commute; only overlapping write sets need a declared order. The fold then flags *undeclared* conflicts statically instead of running counterfactual folds.
>
> **Suggestion (docs).** Cite the lineage. Measurement disturbing the measured system is the *probe effect* (Gait, 1986; McDowell & Helmbold, 1989; Malony, Reed & Wijshoff, 1992), with three standard responses: avoid, compensate, ignore. Passive observers here implement *avoid* by construction; the perturbation ledger implements *compensate*, which prior work does after the fact on traces. Handling it per record, inside state, is the novel part, and the relative observation budget has no precedent found.
>
> **Review question.** Is editor inspection (paint, hover, `schematic.state.query`) passive by construction, with no code path from UI inspection to the event log? If the outcome of a run can depend on when someone looked, replay identity is gone.

### Collapse and receipts

A consequential effect removes every path in which it did not happen. That is the boundary where possibility becomes recorded fact. RECEIPT and REFUSE are those boundaries: an effect crossing one writes a receipt keyed by an idempotency key, and replaying the log returns the recorded outcome instead of acting again. Everything upstream of a receipt may stay open or uncertain; everything downstream is fact.

> **Suggestion (slice 2 for the model, slice 4 for real effects).** Add a third outcome: `in-doubt`. A timed-out effect is neither RECEIPT nor REFUSE, and it is the most common real failure. An in-doubt effect is resolved later by a logged reconciliation event (query by key) into a receipt or a refusal.
>
> **Suggestion.** Derive idempotency keys deterministically from `(run, effect site entity, logical tick, occurrence index)`, store a fingerprint of the effect payload with the key, and refuse same-key/different-payload with a typed error. Record REFUSE outcomes with the same fidelity as receipts.
>
> **Review question.** Replay never touches the outside world, and a *re-run* is a new run with new keys. Is that distinction explicit in the API, given that outside dedupe windows are finite (Stripe's keys can be pruned after 24 hours)?

### Residuals

| Residual | Compares | Points to |
|---|---|---|
| sensor | reading vs estimate | a noisy or miscalibrated observer |
| forecast | predicted vs actual | a wrong model of the run (deferred with prediction) |
| policy | intended vs achieved | a document or gate that needs revision |
| drift | current field vs its baseline | the field itself moved |

In the runtime the first residual is a policy one: a golden truth table vs a run's result.

> **Suggestion (slice 4).** Add a **structural** residual: the model's shape against the world's reported shape, computed as a typed diff of edge sets. It gives Open question 1 a measurable output. It lines up with ISO 23247's distinction between a driving twin (model-led) and a driven twin (measurement-led), which names the difference but offers no metric for it.
>
> **Suggestion (slice 4).** Once measured records carry uncertainty, judge sensor residuals normalized by their expected spread (the normalized innovation squared used in Kalman consistency checks), so a residual is compared with what is plausible for that observer.

### Control

```text
observe → estimate → (predict) → compare to setpoint → gate or route → act through a receipt → record
                ↑                                                                              │
                └──────────────────────────────────────────────────────────────────────────────┘
```

Setpoints and thresholds come from the document, so people author behaviour and the runtime enforces it. Hysteresis lives in the compare step. The receipt is where control collapses possibility.

> **Suggestion (slice 4).** Mark transitions `controllable` or `uncontrollable`, as supervisory control does. A gate can only disable controllable transitions; the instrument can then show which actions in an outside AI graph were preventable and which could only be observed.

## Execution (the runtime)

A **run** is: one document revision + an initial set of registered values + a budget. Runs are deterministic: no wall clock, no randomness without a declared seed.

1. A source's registered value changes; the change is an event.
2. The event enters a Path through a 0D attachment Point.
3. The Path schedules arrival at `logical + path delay`. Path delay is declared on the Path (default 1). Geometry does not set logical delay.
4. Arrival writes the destination Point's signal state.
5. Hosted logic evaluates when one of its inputs changes.
6. A changed output is emitted at `logical + device delay`, the delay its definition declares (default 0), onto admitted outgoing Paths. Boundary legality is the data core's; the runtime never reaches through a boundary the editor would refuse.
7. Every step appends to the trace.

The queue is ordered by `(logical, sequence)`, so equal-time events are deterministic. A run stops when the queue is empty (quiet) or the budget is spent (a typed refusal naming what was left).

Delay lives in both places, as in real circuits: a Path takes time to carry (propagation), a device takes time to respond (gate delay). A DELAY or REPEATER is then simply a device whose definition declares a delay and passes its input through. Both delays show in the trace separately, so a slow run says whether the wire or the device was slow.

> **Suggestion (slice 1).** Two-phase ticks. Because every Path delay is at least 1, a device's output always lands at a later tick, and zero-time chains cannot form. The only same-tick hazard is several arrivals at one device. One rule covers it:
>
> 1. **Update:** apply every arrival scheduled for tick t to signal state.
> 2. **Evaluate:** evaluate every device whose inputs changed, reading only committed state.
>
> Within each phase order is irrelevant, which is the VHDL delta-cycle guarantee without the full delta machinery. `sequence` is then assigned by sorting on stable ids (target entity, target point, source Path) and serves serialization only.
>
> **Suggestion (slice 1).** Make "Path delay ≥ 1" an invariant checked at load. If zero-delay Paths are ever allowed, the scheduler needs full delta rounds and a static check that every cycle has total delay ≥ 1 (typed "algebraic loop" refusal otherwise).
>
> **Suggestion (slice 1).** Loops need a result other than budget exhaustion. A NOT feeding itself oscillates forever and never goes quiet. `settle` hashes committed state at each tick; a repeated hash returns a typed `oscillating{period, subjects}` result, which reads very differently from "ran out."
>
> **Suggestion (slice 1).** Numeric policy. Byte identity across browser and `node` fails on floats: sums depend on reduction order, and ECMAScript leaves `Math.exp` and `Math.sin` precision to the engine. Core packs use integers or fixed-point, reductions use a fixed order, and engine-provided transcendental functions are excluded unless implemented in software.

### Definitions

Behaviour is data, not code. The runtime evaluates **definitions**; it has no built-in knowledge of AND, DELAY or a threshold gate.

A definition (`soveraeign.schematic/definition@0.1`, schema `formats/schematic.definition.schema.json`) declares:

| Member | Holds |
|---|---|
| `id`, `version` | `logic.and`, `1`; a document binds `logic.and@1` |
| `kind` | `combinational`, `temporal`, `stateful`, `observer`, `field` |
| `inputs`, `outputs` | named attachment Points, each with its observable and form |
| `rule` | one of a closed set of rule forms: `truth_table`, `threshold` (enter / exit), `pass` (identity), `route` (selector → output); later `transition` (state machine) |
| `delay` | device delay in logical ticks |
| `observables` | derived observables it produces, each with update rule, blast radius, staleness tolerance |
| `observer` | for observer definitions: class (passive / active), cost, limits |
| `projection` | glyph and labels; presentation only |

The rule forms are the only runtime code. A new gate, device or domain is a new definition, never a new code path; NAND, NOR, XNOR and larger devices are definitions or compositions of definitions.

Definitions are **domain-driven**: they arrive in domain packs (Issue #4), and a pack is the unit a domain publishes (logic, dataflow, a workstation model, ...). Until #4 defines the pack format, the state space carries a minimal pack envelope (`id`, `version`, `definitions[]`) that #4 will absorb as one member of the full domain pack. The built-in vocabulary (SOURCE, SINK, NOT, AND, OR, XOR, SWITCH, DELAY, threshold GATE) ships as the `core.logic` pack in `data/`, loaded the same way as any other pack, so built-ins have no privileged path.

A document references definitions by `id@version` and records which packs it uses. A `.sovpak` embeds the packs its document references, so a package runs anywhere. A document that references a definition it cannot resolve opens, but refuses to run, with a typed refusal naming the missing definition.

> **Review question.** Composed definitions reference other definitions. Does a composition pin its children by `id@version`, and does the trace record the full resolved set, including transitive pins?
>
> **Review question.** Once hysteresis reads its own state record, the `threshold` rule form belongs to kind `stateful`. Does the definition schema let a rule form declare the state it reads?

### What `signalMode` becomes

`source` / `relay` / `passive` keep their meaning. The current "active" set in `computeSignalState()` is the **settled state** of a run in which every source is high and every relay passes: the fixpoint the fixed six passes approximate. When the runtime lands, the editor's idle picture is that settled state, computed by the fold, and `25-signal.js` becomes a projection of it instead of its own computation.

## Files

- A `.sov` gains only **authored** state-space data: Path delays, definition references (`id@version`) and the packs they come from, thresholds, observable and field declarations, initial registered values. Nothing a run computes is written to it.
- **Runs are saved.** A run's trace is its own file, `.sovtrace` (`soveraeign.schematic/trace@0.1`, MIME `application/vnd.soveraeign.schematic-trace+json`): document id and revision, the pack versions used, the input set, budget, the event log, and optionally the derived records for audit. A trace without derived records is still complete, because they are recomputable. A trace is kept apart from the `.sov` so running a document never changes the document, and so one document can have many runs.
- File menu: Save Run / Open Run, owned by `75-persistence.js` like every other file. Opening a trace against a document of a different revision opens read-only and says so; it cannot be replayed until the revisions match.
- A `.sovpak` may carry traces alongside its document and packs (`traces[]`), so a package can ship with its evidence.
- Golden traces live beside the examples they run.

> **Suggestion (slice 1).** "Byte-identical" needs a canonical encoding. Use RFC 8785 (JSON Canonicalization Scheme) for `.sovtrace` and derived records, and record the runtime version and trace format version in every trace.
>
> **Suggestion (later).** Hash-chain the event log for tamper evidence, and carry CloudEvents-style `source` + `id` on every imported event (slice 4) as its dedupe key.

## Surfaces

The runtime is transport-neutral and headless, like the data core, so the browser, HTTP, MCP and `node` scripts share one implementation. Proposed operations, following the existing `schematic.<noun>.<verb>` naming:

- `schematic.run.start` (document, registered inputs, budget) → run id
- `schematic.run.step` / `schematic.run.settle` → records emitted
- `schematic.state.query` (subject, observable, time, vantage) → records
- `schematic.run.trace` → the trace
- later: `schematic.state.observe` (import measured records; instrument use)

Refusals return receipts and do not enter editor history, as for every other operation.

> **Review question.** What is one `schematic.run.step`: one event, or one tick? With two-phase ticks, a tick is the smallest unit whose result is deterministic, which makes it the natural step.
>
> **Suggestion (slice 4, at the edges only).** Standards adoption lives in import and export, never in the core record: PROV-JSON export of provenance (observer → Agent, rule application → Activity, record → Entity, inputs → wasDerivedFrom); OpenTelemetry and CloudEvents import for measured records, with metrics becoming signal state and spans becoming particles. Pin the semantic-convention version per import adapter; the GenAI conventions are still pre-stable.

## Module ownership

Proposed additions to `MODULES.md`:

- `src/07-state-space.js`: the state record, event log, scheduler, fold, rule evaluation, fields and residuals. Pure; no DOM; loadable by `scripts/`, `mcp/server.mjs` and the editor, like `05-data-core.js` and `06-attachment-core.js`.
- `src/25-signal.js`: becomes the projection of settled or current state-space records onto the canvas.
- `src/55-render.js`: packets are driven from trace particles when a run is live.
- `src/75-persistence.js`: Save Run / Open Run and `.sovtrace`, the only place a trace is serialized.
- `data/core.logic.pack.json`: the built-in definitions.
- `formats/schematic.state-record.schema.json`, `formats/schematic.trace.schema.json`, `formats/schematic.definition.schema.json`.

## Slices

Each slice ends with its QA suite inside `python scripts/qa.py`.

1. **Record, definitions and fold.** State record, definition and trace schemas with validators; the minimal pack envelope and `core.logic` with NOT / AND / OR / XOR as truth-table data; event log; `(logical, sequence)` scheduler with budget; `A AND B → Q` run over all four input vectors with golden `.sovtrace` files; replay identity; API / HTTP / MCP parity; nothing written to `.sov`.
2. **Visible runtime.** `SOURCE → NOT → DELAY → SWITCH → SINK A / SINK B` from Issue #6; Path and device delays; packets rendered from the trace; Save Run / Open Run; assertions with enter/exit thresholds on a continuous input.
3. **Fields.** Laplacian diffusion and advection as declared fields; signal colour moved onto a declared field; `25-signal.js` reduced to projection.
4. **Measurement.** Observer registry (passive / active, limits); perturbation ledger; sensor and policy residuals; `schematic.state.observe` for importing measured records (the instrument).
5. **Later, only when earned.** Stateful devices (latch, clock, edge); predicted state, possibility sets and ensembles; sensor placement from the uncertainty map.

> **Suggestion.** Slice 1 grows by the determinism items above: the replay key, two-phase ticks with canonical ordering, the Path delay invariant, the typed oscillation result, the numeric policy, canonical encoding, and intent logging. Slice 2 adds the device `state` record for hysteresis. The instrument-facing record extensions (quality, dual timestamps, GUM certainty, `estimated`, structural residual, controllability) collect in slice 4.

## Non-goals

Analog or electrical simulation; exact Redstone emulation; HDL synthesis; amplitudes (probabilities narrow by observation and that is enough unless paths must cancel); 3D.

## Settled

1. **Delay** is on both the Path (propagation) and the device (response). *(2026-09-25)*
2. **Behaviour** is definitions as data, delivered in domain packs; built-ins are the `core.logic` pack. *(2026-09-25)*
3. **Runs are saved** as `.sovtrace`, separate from the document. *(2026-09-25)*
4. **Active observation** is paid relative to the observed run's own budget, capped by a declared share. *(2026-09-25)*

## Open questions

1. **Connections for the instrument.** When schematically watches an outside system, who says what connects to what? (a) A person draws the model, and outside readings only attach to the drawn entities. (b) The outside system also reports its connections, and those arrive as measured records. The draft's lean: (a) by default; reported connections may arrive as measured records shown as proposals, and become part of the document only when someone accepts them, so nothing observed silently rewrites what was authored. This only matters at slice 4.

2. **Zero-delay Paths.** Forbid them (two-phase ticks stay sufficient), or allow them (full delta rounds plus algebraic-loop checks)? The review leans toward forbidding them until a domain pack needs them.
3. **Hysteresis timing.** Move the device `state` record into slice 2, or ship single-threshold gates in slice 2 and defer hysteresis to slice 5?
4. **Observation account.** Confirm the reserved-account mechanism as the amendment to Settled #4, and pick the default share.
5. **First import standard.** For slice 4, which lands first: OpenTelemetry (closest to AI agent pipelines) or OPC UA / DTDL (closest to industrial twins)?
