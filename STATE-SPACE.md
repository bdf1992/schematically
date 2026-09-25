# State Space · design

**Status: design, not yet accepted.** Nothing here is implemented. This document fixes the model before code is written; once accepted, the slices at the end become issues and it becomes the living reference for the concern, like `FORM-MODEL.md`.

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

### Kinds of state

| Kind | Source | Truth test | Here |
|---|---|---|---|
| registered | written by an authorised act | did the write pass the data core's legality? | a source's value, an input vector, a switch position |
| measured | read by an observer | is the observer calibrated? | an OBSERVE reading; an imported instrument reading |
| derived | computed by a rule | can it be recomputed from its inputs? | a gate output, a field value, a Component's active state |
| predicted | projected forward | how did past forecasts score? | deferred |

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

### Fields

A field is one observable defined over every subject, including where nothing was measured: samples, a declared spread rule, an uncertainty that grows with distance from samples, a gradient across each Path, and snapshots so drift in the field itself is visible.

Spread rules run over the graph Laplacian `L = D − A` of the document's connection graph:

- **diffusion**: values spread along Paths and even out (risk from a failing Component to what depends on it);
- **advection**: values travel with directed flow (budget consumed, taint from an unverified input).

Today's colour mixing in `25-signal.js` is an undeclared diffusion with fixed pass counts. It becomes a declared field (`presentation.signal-color`, diffusion, `regional`) so the colour on screen has a rule, a rate and a provenance, and colour stops standing in for signal value.

### Observers and perturbation

Each observer is registered with its **class** and **limits**:

- **passive**: reads recorded state and changes nothing. The OBSERVE symbol ("reads evidence from outside the action path") is passive by definition.
- **active**: disturbs the subject: spends budget, pauses a run, consumes context. Active observations go through the same budget as any other work and write a perturbation ledger entry.
- limits: resolution, noise, drift, latency. Recorded per observer; the runtime's own rules are exact, so these matter first for the instrument.

For any record, the state space can answer: observed passively, observed actively, or created by the act of observing.

**Order matters for non-commuting observations.** Two active observers whose order changes the outcome must have that order fixed by the document; the fold flags any pair it sees give different results when swapped.

### Collapse and receipts

A consequential effect removes every path in which it did not happen. That is the boundary where possibility becomes recorded fact. RECEIPT and REFUSE are those boundaries: an effect crossing one writes a receipt keyed by an idempotency key, and replaying the log returns the recorded outcome instead of acting again. Everything upstream of a receipt may stay open or uncertain; everything downstream is fact.

### Residuals

| Residual | Compares | Points to |
|---|---|---|
| sensor | reading vs estimate | a noisy or miscalibrated observer |
| forecast | predicted vs actual | a wrong model of the run (deferred with prediction) |
| policy | intended vs achieved | a document or gate that needs revision |
| drift | current field vs its baseline | the field itself moved |

In the runtime the first residual is a policy one: a golden truth table vs a run's result.

### Control

```text
observe → estimate → (predict) → compare to setpoint → gate or route → act through a receipt → record
                ↑                                                                              │
                └──────────────────────────────────────────────────────────────────────────────┘
```

Setpoints and thresholds come from the document, so people author behaviour and the runtime enforces it. Hysteresis lives in the compare step. The receipt is where control collapses possibility.

## Execution (the runtime)

A **run** is: one document revision + an initial set of registered values + a budget. Runs are deterministic: no wall clock, no randomness without a declared seed.

1. A source's registered value changes; the change is an event.
2. The event enters a Path through a 0D attachment Point.
3. The Path schedules arrival at `logical + delay`, where `delay` is declared on the Path (default 1). Geometry does not set logical delay.
4. Arrival writes the destination Point's signal state.
5. Hosted logic evaluates when one of its inputs changes.
6. A changed output emits new events onto admitted outgoing Paths. Boundary legality is the data core's; the runtime never reaches through a boundary the editor would refuse.
7. Every step appends to the trace.

The queue is ordered by `(logical, sequence)`, so equal-time events are deterministic. A run stops when the queue is empty (quiet) or the budget is spent (a typed refusal naming what was left).

Gate behaviour is data, not code: a definition names inputs, outputs and a rule (truth table first), exactly the shape Issue #6 gives. NAND, NOR, XNOR and larger devices are definitions or compositions.

### What `signalMode` becomes

`source` / `relay` / `passive` keep their meaning. The current "active" set in `computeSignalState()` is the **settled state** of a run in which every source is high and every relay passes: the fixpoint the fixed six passes approximate. When the runtime lands, the editor's idle picture is that settled state, computed by the fold, and `25-signal.js` becomes a projection of it instead of its own computation.

## Files

- A `.sov` gains only **authored** state-space data: declared delays on Paths, gate definitions or references, thresholds, observable and field declarations, initial registered values. Nothing a run computes is written to it.
- A run's trace is its own format, `soveraeign.schematic/trace@0.1`: document id and revision, the input set, budget, the event log, and (optionally, for audit) the derived records. A trace without derived records is complete, because they are recomputable.
- Golden traces live beside the examples they run.

## Surfaces

The runtime is transport-neutral and headless, like the data core, so the browser, HTTP, MCP and `node` scripts share one implementation. Proposed operations, following the existing `schematic.<noun>.<verb>` naming:

- `schematic.run.start` (document, registered inputs, budget) → run id
- `schematic.run.step` / `schematic.run.settle` → records emitted
- `schematic.state.query` (subject, observable, time, vantage) → records
- `schematic.run.trace` → the trace
- later: `schematic.state.observe` (import measured records; instrument use)

Refusals return receipts and do not enter editor history, as for every other operation.

## Module ownership

Proposed additions to `MODULES.md`:

- `src/07-state-space.js`: the state record, event log, scheduler, fold, rule evaluation, fields and residuals. Pure; no DOM; loadable by `scripts/`, `mcp/server.mjs` and the editor, like `05-data-core.js` and `06-attachment-core.js`.
- `src/25-signal.js`: becomes the projection of settled or current state-space records onto the canvas.
- `src/55-render.js`: packets are driven from trace particles when a run is live.
- `formats/schematic.state-record.schema.json`, `formats/schematic.trace.schema.json`.

## Slices

Each slice ends with its QA suite inside `python scripts/qa.py`.

1. **Record and fold.** State record schema and validator; event log; `(logical, sequence)` scheduler with budget; truth-table rules for NOT / AND / OR / XOR as data; `A AND B → Q` run over all four input vectors with golden traces; replay identity; API / HTTP / MCP parity; nothing written to `.sov`.
2. **Visible runtime.** `SOURCE → NOT → DELAY → SWITCH → SINK A / SINK B` from Issue #6; declared Path delays; packets rendered from the trace; assertions with enter/exit thresholds on a continuous input.
3. **Fields.** Laplacian diffusion and advection as declared fields; signal colour moved onto a declared field; `25-signal.js` reduced to projection.
4. **Measurement.** Observer registry (passive / active, limits); perturbation ledger; sensor and policy residuals; `schematic.state.observe` for importing measured records (the instrument).
5. **Later, only when earned.** Stateful devices (latch, clock, edge); predicted state, possibility sets and ensembles; sensor placement from the uncertainty map.

## Non-goals

Analog or electrical simulation; exact Redstone emulation; HDL synthesis; amplitudes (probabilities narrow by observation and that is enough unless paths must cancel); 3D.

## Open questions

1. **Delay authoring.** Is delay a property of the Path (carrier), of the gate (device), or both, as in real circuits? The draft puts it on the Path.
2. **Where gate definitions live.** In the document, as built-in data, or in a domain pack (Issue #4)? The draft allows a reference so the answer can move to packs without a format change.
3. **Trace persistence.** Is a trace a file a person saves (`.sovtrace`, next to the document) or only an API/MCP result and a test fixture?
4. **Active observation budget.** When the instrument arrives: does an active observer spend the observed run's budget or a separate one?
5. **Relation graph for the instrument.** In the runtime, edges are registered (authored). When records come from outside, are the edges still authored in the document, or measured from the outside graph?
