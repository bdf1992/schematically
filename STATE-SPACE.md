# State Space · design

**Status: design, settled for slices 1–3.** Nothing here is implemented. Slice 4 (the instrument) has one open question. Each slice becomes an issue; this document is the reference for the concern, like `FORM-MODEL.md`, and changes with it.

Sources: *State Planes for Governed Graph Systems* (2026-09-25); Issue #6 (logic machine); `docs/vision/DATA-DRIVEN-SCHEMATIC-LANGUAGE.md` ("Logic/runtime proof"); the current `src/25-signal.js`; and a review pass (2026-09-25) comparing the design with DEVS and VHDL/SystemC scheduling, Temporal-style replay, W3C PROV, OpenTelemetry and CloudEvents, digital-twin specifications, GUM/VIM metrology, directed graph Laplacians and idempotent effects, plus a red-team pass. The review's accepted suggestions are folded into the text below.

## Purpose

A schematic already says what exists and how it connects. The state space is what the schematic says about **what is true at a moment, and how anyone knows it**: every value is computed from events or measurement, carries its certainty, and records whether observing it changed it.

It serves two uses, built in this order:

1. **Runtime (first).** Schematically executes its own documents: sources change values, Paths carry them, devices evaluate them, receipts record what happened. Issue #6's logic machine is the first consumer.
2. **Instrument (later).** Schematically shows the state of an outside governed graph (a workstation, an agent pipeline): measured records arrive from outside and are laid over a document that models that graph.

Both use the same record, the same fold and the same projections. The instrument adds an import of measured records, a way to bind their subjects to document entities, and the record coordinates only measurement needs.

## Vocabulary

One concept, one word. The source paper's words collide with words the editor already owns, so they are translated here and the paper's words are not used in code, files or UI.

| Paper | Here | Why |
|---|---|---|
| state plane | **state space** | `Plane` is the 2D primitive. |
| state point | **subject** | `Point` is the 0D primitive. A subject may be a Point, but also a Component, a Path, a run. |
| state field | **field** | No collision. |
| control loop | **control** | No collision. |
| measurement / reading | **observation** | Matches the existing OBSERVE symbol. |

**State space is always two words.** `Space` alone keeps its horizon meaning (`HORIZON-SPACE.md`: the coordinate domain and admitted grammar a document lives in). A document lives in a Space; its state space is the state of that document over time. Code names use `stateSpace` / `state-space`, never `space`.

**Logical time is not animation time.** `diagram.meta.timeScale` and per-entity `rate` pace the rendered packets. Logical time is the integer clock of the state space. Changing rate, zoom or geometry may change how long a packet takes on screen; it never changes a logical outcome.

**Replay is not re-run.** A *replay* recomputes a recorded run from its trace and never touches anything outside. A *re-run* is a new run, with a new run id and new effect keys.

**A retry is not a repeat.** An attempt is one try at a step. A later attempt carries observations the earlier one did not have (a CI failure log, a review comment), so it is a different trial, not the same one again.

## Ownership and patterns

The state space does not try to imagine every state, schema and contract a domain will need. It owns the **shape** of state and a small set of **patterns**; domains fill the shape by **instantiating** patterns with data.

| Owner | Owns | Changes |
|---|---|---|
| **Engine** (`07-state-space.js`) | the ledger, the record envelope, logical time, the fold, the invariants, and a small closed set of patterns | rarely, with review |
| **Domain pack** | its vocabulary (observables, units, conditioning keys) and definitions that instantiate patterns with parameters | whenever a domain needs something |
| **Document** | which instances exist, how they are wired, initial values, setpoints | while authoring, often |
| **Run** | its own ledger | once per run |
| **Caches and views** | nothing authoritative; every one is rebuildable from the ledger | at will |

Only the engine appends to a ledger, and only through legal operations. Nothing else writes truth.

A **pattern** is a reusable mechanism with parameters. It declares:

- its **parameter schema**: what an instance must supply;
- its **inputs** and the **state** it reads and writes, if any;
- its **outputs**: the observables it produces, typed from its parameters;
- its **class**: exact (recomputable), estimated or predicted;
- its **blast radius**.

A **definition** instantiates one pattern: "an AND gate is `truth_table` with this table"; "an agent step's pass rate is `rate` over its `pass` observations, conditioned on attempt and feedback"; "a run's chance of success is `compose` over the Path to its goal".

**Contracts are generated, not written.** A definition's contract (the records it reads, the records it writes, and the value type of each) is derived from its pattern and parameters. The engine validates every record's envelope; each observable's declaration types its value. A new domain is new data. Only a new *kind* of mechanism is engine work.

Patterns, by the slice that brings them:

| Pattern | Does | Class | Slice |
|---|---|---|---|
| `truth_table` | combinational logic | exact | 1 |
| `merge` | same-tick arrivals at one port → one value, by a declared combine and order; undeclared order is a recorded seeded draw | exact given the ledger | 1 |
| `pass`, `route` | identity; selector → output | exact | 2 |
| `threshold` | enter / exit cut with hysteresis | exact, stateful | 2 |
| `materialize` | a cache of a fold at a ledger position | exact | 2 |
| `consensus`, `advection` | field operators | exact | 3 |
| `rate` | counts of outcomes → a rate with its confidence, per declared conditioning keys | estimated | 4 |
| `compose` | series, parallel and retry composition of rates | predicted | 5 |
| `transition` | state machines: latches, clocks, edges | exact, stateful | 5 |

## Model

```text
State space
├─ subjects        addressable things state is about (entity + optional point + run)
├─ records         every state claim, one shape (the state record)
├─ event log       the authoritative, ordered inputs of a run
├─ fold            deterministic function: replay key × event log → derived records
├─ caches          observations of the ledger at a position; never authoritative
├─ fields          one observable over all subjects, with a declared operator
├─ observers       who or what produced a record, with class, limits, read/write sets
├─ residuals       differences the state space can learn from
└─ control         observe → estimate → compare → gate or route → act → record
```

### Source of truth

The **event log is authoritative; all other state is a fold over it.** This matches the existing file rule: a `.sov` carries authored truth only and runtime projections are rebuilt, never saved.

- Registered values (a lever's position, an input vector) and observations enter the log.
- Derived records are outputs of the fold and must be recomputable.
- **The replay key** is everything the fold depends on: document revision, the resolved pack and definition versions, the runtime (fold) version, the initial registered values, and the seed. Replaying the same log under the same replay key yields byte-identical derived records (see *Canonical encoding*). That identity is the first golden test. A runtime change is an input like a document change: it may break identity with no document change at all, which is why the runtime version is in every trace.
- **The fold is deterministic given the ledger**, not given the world. A step that is not deterministic (a generative model, a CI job, a human review) is an effect or an observation, and its result is **recorded** in the ledger. Replay reads the recorded result and never regenerates it; only a re-run generates again (see *Generative steps and attempts*).

### Caching

A cache is a **passive observation of the ledger**: its subject is the ledger itself, and its record says "at this ledger position, under these rule versions, the fold's answer was X".

- **The ledger is hash-chained.** Every entry carries the hash of the entry before it, so a ledger position is identified by one hash.
- **Validity is one comparison.** A cache records the chain hash at its position and the `id@version` of the rules it applied. It is valid exactly while the ledger up to that position still hashes the same and the rules are unchanged.
- **Snapshots are caches of the whole state** at one tick. Rebuilding state is "latest valid snapshot + the entries after it", never a replay from the start unless no snapshot is valid.
- **Materialized values** (one derived value held for speed) are the same thing at a smaller scope: keyed by the hashes of their input records plus the rule's `id@version`.
- **A cache owns nothing.** Deleting every cache costs speed, never truth.

### The state record

Every claim has the same coordinates, whether it is a logic level, a gate verdict, a device's memory, a measured latency or (later) a forecast.

| Coordinate | Answers | Values |
|---|---|---|
| `subject` | about what | `{entity, point?, channel?, run, attempt?}`; `point` is a port id |
| `vantage` | seen from where | `space` (Eulerian: the whole graph at a time), `point` (Lagrangian: one subject's history), `relative` (against a `reference`) |
| `observable` | what is measured | a declared observable id, e.g. `logic.level`, `device.state`, `cost` |
| `kind` | how it became true | `registered`, `measured`, `derived`, `predicted` (`estimated` from slice 4) |
| `form` | its shape | `binary`, `continuous`, `categorical` |
| `value` | the value | per `form`, under the numeric policy |
| `time` | when | `{logical, sequence, mode: observed \| predicted}` |
| `certainty` | how sure | `{kind: exact}` until slice 4 |
| `observer` | who produced it | an observer id: a rule, a sensor, a person |
| `provenance` | from what, by which rule | `{rule, inputs: [record ids], threshold?}` |
| `perturbation` | did observing change it | `none`, `disturbed` (with a ledger entry), `created` |

`time.sequence` is **for serialization only**: it gives records a total order in a file, and no outcome may depend on it (see *Two-phase ticks*).

**Units live on the observable declaration**, not on each record: `{id: "latency", unit: "ms", form: "continuous"}`. Every twin standard reviewed carries units, and adding them later would touch every pack.

Draft shape (schema `formats/schematic.state-record.schema.json`):

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

**Instrument coordinates (slice 4, not before).** Measurement needs coordinates an exact deterministic runtime does not: a `quality` status separate from certainty (a value can be exact and stale); `time.source` and `time.receipt` (OPC UA's source and server timestamps) plus `time.wall`; and `certainty` in GUM terms, `{u, k, evaluation: A | B}`. They enter the schema with the first measured records.

### Kinds of state

| Kind | Source | Truth test | Here |
|---|---|---|---|
| registered | written by an authorised act | did the write pass the data core's legality? | a source's value, an input vector, a switch position, a device's initial state |
| measured | read by an observer | is the observer calibrated? | an OBSERVE reading; an imported instrument reading |
| derived | computed by a rule | can it be recomputed from its inputs? | a device output, a device's next state, a field value |
| predicted | projected forward | how did past forecasts score? | deferred |
| estimated *(slice 4)* | assimilated from measurement and prediction | do its residuals stay consistent? | the control loop's estimate step |

Every derived observable is declared with three properties the fold uses to decide whether a value is fresh enough to gate on:

- **update rule**: the rule id and version;
- **blast radius**: `local` (update in place on each event), `regional` (invalidate within k hops, recompute on read), `global` (recompute in batch or approximate);
- **staleness tolerance**: in logical ticks.

### Vantages

- **space** is what the editor paints: the value at every subject at one logical time.
- **point** is what a packet shows: one transition carried along a Path, with its history.
- **relative** is where control lives: the difference across a Path, a run against its baseline, a value against a threshold.

When a subject's value changes, the state space reports which part moved it: the value changed where the subject sits, or the subject moved into a different region (the paper's material derivative). In the runtime these are, respectively, an input changing under a device and a packet arriving somewhere new; the trace names which.

### Signal state and particles

Kept exactly as Issue #6 separates them:

- **Signal state** is the current value on one channel of a port. It is a record with `vantage: space`.
- **A particle** is a transition moving along a Path: value or change, channel, logical departure and arrival, provenance. It is an event in the log and a `vantage: point` view of it.

A device evaluates signal state, never particles, so an AND gate sees both inputs when only one transition arrives. The rendered packet is a projection of a particle; it is never the source of a value.

**Devices read only committed state.** A device reads signal state committed in the update phase of the current tick and its own state committed at the previous tick; it never reads a value written during the evaluate phase it is part of. This is the condition under which VHDL and SystemC scheduling stay deterministic, and SystemC loses it the moment two processes share a variable. No code path in the runtime lets a device read in-flight state.

### Device state

A device with memory keeps it in the log, not in the runtime. Its memory is a `device.state` record (`vantage: point`, `kind: derived`) written at commit; a stateful rule reads its own committed state and its inputs, and nothing else. A device's **initial state** is a registered value declared in the document; a stateful device without one refuses to run.

This is the one mechanism for memory: hysteresis (slice 2) and latches, edges and clocks (slice 5) all mean "a rule that reads its own prior records".

### Assertions: binary as a cut through continuous

A binary verdict is the visible half of a measurement. A threshold device's output is an assertion, which keeps what a bare boolean loses:

| Field | Example |
|---|---|
| predicate | `level_high` |
| value | `0.87` |
| threshold (enter / exit) | `0.80 / 0.75` |
| margin | `+0.07` |
| observer | `rule:gate.threshold@1` |
| rule version | `gate.threshold@1` |
| time | logical 12 |

Two thresholds give hysteresis, so a value near the cut does not chatter. A value inside the dead band is decided by the device's committed state, which is why `threshold` is a stateful rule and needs a declared initial state.

**Margin** is the distance to the *active* threshold: the exit threshold while the assertion holds, the enter threshold while it does not. Pure boolean logic is the degenerate case: value 0 or 1, one threshold, margin ±1. Once measured values carry uncertainty (slice 4), margin divided by the standard uncertainty is a z-score.

### Fields

A field is one observable defined over every subject, including where nothing was measured: samples, a declared operator, an uncertainty that grows with distance from samples, a gradient across each Path, and snapshots so drift in the field itself is visible.

Fields run over the document's connection graph. Write `A` for its weighted adjacency, with `A_ij = w` for a Path from i to j, and `D_in`, `D_out` for the diagonal in- and out-degree matrices. `L = D − A` is ambiguous on directed Paths (libraries choose silently; NetworkX's `laplacian_matrix` uses out-degree), so **every field declares its operator by name**:

- **`consensus`**: `L = D_in − Aᵀ`. Each node pulls toward what feeds it; values even out along the direction of flow. Risk from a failing Component spreads to what depends on it.
- **`advection`**: `L = D_out − Aᵀ`. What leaves a node arrives at its successors, so the total is conserved. Budget consumed and taint from an unverified input need this one.

A step is `x ← x − εLx`. It is stable only for small enough ε: `ε ≤ 1 / max weighted in-degree` for `consensus` (then `I − εL` is row-stochastic) and `ε ≤ 1 / max weighted out-degree` for `advection` (then it is column-stochastic, so the total is conserved). The runtime checks ε against the document's graph at load and refuses a field that would diverge. `consensus` reaches one agreed value only if the graph has a rooted spanning tree; otherwise each part reachable from a separate root settles on its own value, and the field reports which.

Today's colour mixing in `25-signal.js` is an undeclared diffusion with fixed pass counts. It becomes a declared field, `presentation.signal-color`, operator `consensus`, blast radius `regional`: colour follows direction but is not a conserved quantity. The colour on screen then has a rule, a rate and a provenance, and colour stops standing in for signal value.

### Observers and perturbation

Each observer is registered with its **class**, **limits** and **read/write sets**:

- **passive**: reads recorded state and changes nothing. The OBSERVE symbol ("reads evidence from outside the action path") is passive by definition.
- **active**: disturbs the subject: spends budget, pauses a run, consumes context. Every active observation writes a perturbation ledger entry.
- **limits**: resolution, noise, drift, latency. The runtime's own rules are exact, so these matter first for the instrument.
- **read and write sets**: the observables an observer reads and the ones it changes.

For any record, the state space can answer: observed passively, observed actively, or created by the act of observing.

**Paying for observation.** Active observation is paid relative to the observed run and never from an absolute pool. At run start, a declared share of the run's *initial* budget (default 10%) moves into a reserved **observation account**. Active observations debit it through logged events. When it is empty, further active observation is refused with a typed refusal, and the run itself continues. A per-observation cap on "what remains" was rejected because it never reaches zero yet drains the run: at a 10% cap, ten observations would take 1 − 0.9¹⁰ ≈ 65% of the budget, twenty 88%.

**Order.** Passive observers commute with everything. Active observers with disjoint write sets commute. Only observers whose write sets overlap need an order, and the document must declare it; the runtime refuses, at load, a document with an undeclared conflict. No run is needed to find one.

**Inspection is passive by construction.** Painting, hovering, selecting and `schematic.state.query` have no code path to the event log. The outcome of a run never depends on when or whether anyone looked, or replay identity would be gone. A QA suite queries a run while it steps and checks that the trace is unchanged.

**Lineage.** Measurement disturbing the measured system is the *probe effect* (Gait, 1986; McDowell & Helmbold, 1989; Malony, Reed & Wijshoff, 1992), with three standard responses: avoid, compensate, ignore. Passive observers implement *avoid* by construction; the perturbation ledger implements *compensate*, which prior work does after the fact over traces. Handling it per record, inside state, and paying for it from the observed run's own budget have no precedent the review found.

### Collapse and receipts

A consequential effect removes every path in which it did not happen. That is the boundary where possibility becomes recorded fact. An effect has three outcomes:

- **receipt**: it happened;
- **refused**: it did not, and will not;
- **in-doubt**: it was attempted and its outcome is unknown (a timeout, the most common real failure). An in-doubt effect is resolved later by a logged reconciliation event (query by key) into a receipt or a refusal.

RECEIPT and REFUSE are the boundaries in the document; `in-doubt` is a state of the effect, not a symbol. Refusals are recorded with the same fidelity as receipts.

**Effect keys** are derived, never generated: `(run, effect-site entity, logical tick, occurrence index)`. Each key is stored with a fingerprint of the effect's payload; the same key with a different payload is refused with a typed error. Replay returns the recorded outcome instead of acting again, because a collapsed state cannot collapse twice. A re-run has a new run id, so new keys; outside systems dedupe only within their own windows (Stripe prunes keys after 24 hours), which is why the two operations are separate in the API.

Everything upstream of a receipt may stay open or uncertain; everything downstream is fact.

### Residuals

| Residual | Compares | Points to |
|---|---|---|
| policy | intended vs achieved | a document or device that needs revision |
| sensor *(slice 4)* | reading vs estimate | a noisy or miscalibrated observer |
| structural *(slice 4)* | the document's edge set vs the outside graph's reported edge set, as a typed diff | a model whose shape no longer matches the world |
| drift *(slice 4)* | current field vs its baseline | the field itself moved |
| forecast *(later)* | predicted vs actual | a wrong model of the run |

In the runtime the first residual is a policy one: a golden truth table vs a run's result. Once measured records carry uncertainty, sensor residuals are judged normalized by their expected spread (the normalized innovation squared of Kalman consistency checks), so a residual is compared with what is plausible for that observer.

### Predicted success

Prediction is built from evidence, one pattern at a time, and every link is a record:

```text
outcomes (measured) → rate per step (estimated) → chance the run succeeds (predicted) → scored against what happened
```

**Rates come from counts.** The `rate` pattern keeps the count of passes and trials, not just their ratio: 19 of 20 and 950 of 1000 are both 95% and deserve very different confidence. A rate is conditioned on **keys the domain declares**, for example step, attempt number, and the kind of feedback the attempt had. The engine does not know what "feedback" means; the pack names the keys.

**Composition.** The `compose` pattern combines rates over the document's graph: steps in series multiply; alternatives combine as "at least one succeeds"; retries use the rate of *each attempt given the earlier ones failed*, never one rate repeated.

- Ten steps at 95% each, no retries: 0.95¹⁰ ≈ 60%.
- The same, assuming a retry were an independent repeat: each step 1 − 0.05² = 99.75%; ten steps ≈ 97.5%.
- Measured attempts instead of assumed ones, for one step: first attempt 80%; a second attempt, given the first failed and with its CI log in hand, 60%; a third, 40%. The step succeeds within three attempts with probability 1 − (0.2 × 0.4 × 0.6) = 95.2%.

The last line is the one the design commits to. Attempts are not independent: a failure that repeats the same way on the same input makes a retry worthless, and feedback can make a retry better than the first try. Only per-attempt rates, measured separately, capture both.

**Forecasts are scored.** When a run finishes, its forecast residual (predicted vs actual) is recorded. A prediction earns trust from its scored history, never from how sure it sounds.

### Control

```text
observe → estimate → (predict) → compare to setpoint → gate or route → act through a receipt → record
                ↑                                                                              │
                └──────────────────────────────────────────────────────────────────────────────┘
```

Setpoints and thresholds come from the document, so people author behaviour and the runtime enforces it. Hysteresis lives in the compare step. The receipt is where control collapses possibility.

From slice 4, transitions are marked **controllable** or **uncontrollable**, as in supervisory control: a gate can only disable controllable transitions, so the instrument can show which actions in an outside graph were preventable and which could only be observed.

## Execution (the runtime)

A **run** is one replay key (document content hash, resolved definitions, runtime version, initial registered values, seed) plus a budget. The engine is deterministic: no wall clock, no randomness except draws from the declared seed, and every draw is recorded. Anything outside that guarantee enters as a recorded result (see *Generative steps and attempts*).

**Document identity is content, not revision.** The document's `revision` is a counter, and undo restores older content with its older revision, so two different documents can carry the same number. The replay key therefore holds `documentHash`: SHA-256 over the canonical encoding of `compactDocument()` with `revision` and timestamps removed. `revision` stays on the trace as a label for people. The hash must not depend on where the document is held: opening a document in the editor may add runtime defaults, but hashing it must give the same answer as hashing the file. **One normalizer:** every default and every layout constraint (clamping a Plane to its content, placing edge Points, snapping) is applied by the data core's normalize and update, never by the editor alone, so every surface computes the same document from the same input. The saved form is minimal: a value equal to its default is omitted. *(Decided after #50's first round, whose editor-side merge failed on ordinary edits; being implemented in #50.)*

1. A source's registered value changes; the change is an event.
2. The event leaves through a declared port (see *Ports*) and enters a Path.
3. The Path schedules arrival at `logical + path delay`. Path delay is declared on the Path (default 1). Geometry does not set logical delay.
4. Arrival at the destination port is merged with any other same-tick arrivals there (see *Merge and ordering*) and written to that port's signal state.
5. A device evaluates when one of its inputs changed.
6. A changed output is emitted at `logical + device delay`, the delay its definition declares (default 0), onto admitted outgoing Paths. Boundary legality is the data core's; the runtime never reaches through a boundary the editor would refuse.
7. Every step appends to the trace.

Delay lives in both places, as in real circuits: a Path takes time to carry (propagation), a device takes time to respond (device delay). A DELAY or REPEATER is a device whose definition declares a delay and passes its input through. The trace records both delays separately, so a slow run says whether the Path or the device was slow.

**Delay is transport delay.** Every change is carried and delivered, however short the pulse, so every change is visible as a packet. Inertial delay (a pulse shorter than the delay is swallowed, VHDL's default) may later be a parameter of the DELAY pattern; it is not the runtime's default.

### Ports

A port is a declared 0D attachment point on a Component: the only place a Path may carry state into or out of it.

- **Declared, not assumed.** Every Component's ports are data: `{id, side: left | right | top | bottom, t, flow: in | out | control | duplex | trigger, channels, label}`. The `left` / `right` / `top` trio stops being hard-coded in the attachment core: it becomes the declared port set of the typed templates that use it, and a template may declare none, one, or many ports on any side. The stored forms keep their meaning, so no existing file changes: `attachmentDefaults: 'standard'` (explicit or implied) means *the template's declared ports, plus the authored `attachmentPoints` as additions*; `'none'` means *the authored `attachmentPoints` are the complete list*. An edit supplies the complete list it wants, and the data core stores it in the smallest form: as additions when every template port is kept unchanged, otherwise as `'none'` plus the full list. The editor, API, HTTP and MCP add, move, relabel and remove ports through that one data-core path.
- **A Point declares its one port too.** A 0D Component's only port is `self`. It may be declared, to give it channels and merges, as a single `attachmentPoints` entry `{id: 'self', flow?, channels}` with no `side` or `t`, since a Point has no boundary to place it on. The first runtime (slice 1b) stored such an entry with a placeholder `side`; the loader will accept and clean both forms, and the goldens will be regenerated when this lands.
- **Generated from a definition.** A Component bound to a definition gets its ports from the definition's contract: one port per input and per output, ids and flow taken from the pattern (`a`, `b` in, `q` out for `truth_table` with two inputs). Default placement is inputs spread evenly on the left and outputs on the right. Position (`side`, `t`) is presentation and may be moved; the port id is identity and may not be changed while a definition owns it.
- **Channels.** A port carries one or more named **channels**, each with its observable and form; the default is one channel, `main`. A Path carries the channels its two bound ports share, matched by channel id; binding two ports that share no channel is refused, with the same refusal over every surface. Several channels on one port let one Path carry several signals.
- **Direction.** A Path carries only in the direction(s) it declares. `forward` carries a → b; `reverse` carries b → a; `duplex` is two independent channels of the same declared delay, one each way; `none` carries nothing. A direction is carried only where both ports' flows admit it (an `out` or `duplex` port emits; an `in`, `duplex`, `control` or `trigger` port receives), as the editor already draws it: a `duplex` Path from an `out` port to an `in` port carries forward only. A Path none of whose declared directions is admitted by its ports carries nothing and is refused at load (`PATH_DIRECTION_FLOW`). Port `access` (read / write) and a Path's `forwardOperation` / `reverseOperation` stay presentation until a pack gives them meaning.

### Merge and ordering

Several Paths may end on one port, and several arrivals may reach it in the same tick. What happens then is declared, never left to chance, and where it cannot be declared the chance is recorded.

A port (or one of its channels) may declare a **merge**, an instance of the `merge` pattern:

- **combine**: how same-tick arrivals become one value. Order-free: `or`, `and`, `min`, `max`, `sum`. Order-dependent: `first`, `last`, and `queue` (deliver the arrivals one per tick in merge order; the rest wait their turn).
- **order**: for order-dependent combines, where the order comes from:
  - `declared`: a priority list of incoming Paths, highest first;
  - `observed`: the order in which an outside system reported the arrivals (instrument only, slice 4), recorded as a measured record;
  - `stochastic`: the engine draws an order.

**Undeclared means stochastic, and stochastic means recorded.** A port with same-tick fan-in and no merge declared uses `combine: last, order: stochastic`. A declared list that leaves some incoming Paths out orders the listed ones first and draws the rest. Every draw is written to the ledger as an `order` record (subject: the port and channel at that tick; value: the order drawn; observer `engine:merge@1`; provenance: the seed and the draw key). The draw is keyed by `(run seed, tick, port, channel)`, never by evaluation order, so it is reproducible, and replay reads the recorded order and checks that it re-derives. The trace lists every port that used stochastic order, so a reader knows where order was chance rather than design. Order-free combines need no order and record none.

### Two-phase ticks

**Path delay is at least 1**, checked at load. A device's output therefore always arrives at a later tick, even with device delay 0, and no zero-time chain can form. Each tick has two phases:

1. **Update:** gather every arrival scheduled for tick t, merge the arrivals at each port by its merge, apply them to signal state, and commit.
2. **Evaluate:** evaluate every device whose inputs changed, reading only committed state; schedule its outputs; commit its `device.state`.

Same-tick arrivals at one port are resolved by the merge, and nowhere else; within each phase, the order in which the engine processes ports and devices is irrelevant, which is the VHDL delta-cycle guarantee without the delta machinery. `sequence` is assigned afterwards by sorting on stable ids (target entity, target port, channel, source Path) and serves serialization only.

Zero-delay Paths stay forbidden until a domain pack needs them. Allowing them would require full delta rounds and a static check that every cycle has total delay ≥ 1, refusing an "algebraic loop" otherwise.

### Components hosted on a Path

A Component hosted on a Path (`placement.kind: wire`, `wireId + t`) is a **tap**: it reads the value the Path carries and does not interrupt it. This is what the editor does today (`25-signal.js` gives a hosted Component the Path's source value while the Path still delivers end to end). A hosted Component that *interposes*, splitting the Path into segments with the Component as a device between them, needs carriers and Components in one record kind, which is the file-format transition the roadmap already names; it waits for that.

### Runtime semantics (slice 1b)

Decided before building the first runtime, so the contract names outcomes, not choices:

- **Signal state** is kept per `(entity, port, channel)`. Every binary channel starts `false`; the starting state is implied by the document and is not recorded.
- **Power-on.** Tick 0 is always processed, even with no inputs at it. Its evaluate phase evaluates *every* device, whether or not an input changed, from the state committed after tick 0's inputs. Outputs that differ from the starting `false` are recorded and emit as usual. Without this an inverting device (NOT, NAND) would never leave its starting state. *(Found by the customer review of slice 1b.)*
- **Who does what on arrival.** A Component bound to a definition *evaluates*. A Point *relays*: the value its `self` port takes in a tick is emitted onto every Path on that port, in each direction `self` emits, except the Paths that delivered to that port in that tick (so a duplex junction never echoes, even back to a Path whose value lost the merge). Any other Component *absorbs*: it holds the value and emits nothing.
- **Sources are registered inputs.** A run's inputs are `{entity, point, channel?, value, at}`: at tick `at`, the port takes `value` and emits it. An input and a Path arrival (or a queue's arrivals) at the same port and tick: the input wins, and each arrival is recorded as `overridden`. An input on a port a definition owns as an output is refused at start (`INPUT_INVALID`): a device's output is the device's.
- **Emission.** When a port's value changes and the port emits, one arrival is scheduled per bound Path, per direction that Path carries out of this port (see *Ports*), per shared channel, at `t + path delay`.
- **Device delay.** A device evaluates in the evaluate phase of tick `t`. With device delay 0 its output ports change in that phase and emit (arriving at `t + path delay`, which is ≥ `t + 1`). With device delay `d > 0` the output change is scheduled for the update phase of tick `t + d`, and emits then.
- **Time jumps.** One step is the next tick that has scheduled work. Logical time skips empty ticks.
- **Queue merges** keep a per-channel FIFO buffer as state: each tick the port delivers the head, and newly merged arrivals are appended in merge order.
- **Forms.** Slice 1b runs binary channels only. On binary channels `min` is `and` and `max` is `or`; `sum` is refused at run start (`MERGE_FORM`).
- **Budget** counts processed events (inputs, arrivals, output changes). Crossing it refuses the step with `BUDGET_SPENT`. The run stays inspectable.
- **The ledger** holds what a replay cannot recompute:
  - a `start` entry carrying the replay key;
  - each registered input;
  - each stochastic order draw.

  Every entry carries the hash of the one before it; the start entry also carries the run's budget, so it is covered by the chain. A stochastic order draw is a ledger `draw` entry (the ledger is the record of chance), not a state record. Derived records are the fold's output.
- **Traces.** A trace carries `through`, the last tick processed (`null` before any), and `head`, the hash of the last ledger entry. Replay processes exactly the ticks up to `through`, so a trace taken mid-run replays. `records` is optional: when present, replay must reproduce them byte for byte; when absent, the trace is still complete and replay recomputes them. A consistently truncated ledger is only detectable against a head hash held elsewhere, which is why run receipts (slice 1c) return `head`.

### Stepping and settling

One `schematic.run.step` is **one tick**: the smallest unit whose result is deterministic. `schematic.run.settle` steps until one of three typed results:

- **quiet**: the queue is empty;
- **oscillating `{period, subjects}`**: the run has entered a cycle. At each tick the runtime hashes the full state that determines the future: committed signal state, every `device.state`, and the pending queue with arrival times taken relative to the current tick. A repeated hash proves a cycle; committed signal state alone would not, because transitions still in flight can differ between two ticks that look the same. A NOT feeding itself ends here, not in budget exhaustion. Where a cycle passes through a port with stochastic order, draws are keyed by the absolute tick, which the state hash does not hold: `oscillating` then means the state recurred, not that the future is strictly periodic.
- **budget spent**: what was left in the queue. A single `step` over budget is a refusal (`BUDGET_SPENT`); inside `settle` a budget stop is one of settle's three results, not a refusal.

**Runs are addressed by handle.** A run's id is derived from its replay key, so two runs of the same document and inputs share it, and record ids and goldens depend on it. Each start on a surface therefore also gets a unique handle (`<runId>.<n>`), and surfaces address runs by handle: a second client's run never touches the first's. A replay is not registered and has no handle.

### Generative steps and attempts

Some steps will not give the same answer twice: a model generating a change, a CI pipeline, a person reviewing. The engine stays deterministic by treating each such step as an **effect whose result is an observation**:

- The step's **inputs** are recorded when it starts: the context it was given, including every observation it could see.
- Its **result** is recorded when it ends, with its observer (which model, which pipeline, which reviewer) and its outcome (receipt, refused, in-doubt).
- **Replay** reads the recorded result. **Re-run** generates a new one.

**Attempts.** Each try at a step is its own subject, `{entity, run, attempt}`. An attempt's recorded inputs include the observations earlier attempts produced (a CI failure log, review comments, a refusal reason). That difference is the point of a retry, so it is recorded, and it is what the `rate` pattern conditions on.

**Revisions.** When CI/CD status and review drive frequent revisions, each revision of a document or of the observed system is a new replay key: a run belongs to exactly one. Evidence is carried across revisions by **identity**: a step's outcomes are keyed by its entity id and its definition's `id@version`. A step whose definition did not change keeps its history across a revision; a step whose definition changed starts a new history. How much weight the old history carries into the new one is open (see *Open questions*).

### Numeric policy

Byte identity across the browser and `node` fails on floats: sums depend on reduction order, and ECMAScript leaves the precision of `Math.exp`, `Math.sin` and similar functions to the engine. So:

- core packs use integers or fixed-point values;
- reductions (sums over inputs, over edges) run in a fixed order, sorted by stable id;
- engine-provided transcendental functions are excluded from rules unless implemented in software within the runtime.

### Definitions

Behaviour is data, not code. The runtime evaluates **definitions**, each an instance of one pattern (see *Ownership and patterns*); it has no built-in knowledge of AND, DELAY or a threshold device.

A definition (`soveraeign.schematic/definition@0.1`, schema `formats/schematic.definition.schema.json`) declares:

Authored members, the only ones a pack writes:

| Member | Holds |
|---|---|
| `id`, `version` | `logic.and`, `1`; a document binds `logic.and@1` |
| `pattern` | the pattern it instantiates, pinned: `truth_table@1` |
| `parameters` | what the pattern's parameter schema asks for: a truth table, thresholds, conditioning keys, input and output names |
| `delay` | device delay in logical ticks |
| `observer` | for observer definitions: class (passive / active), cost, limits, read and write sets |
| `children` | for compositions: the definitions composed, each pinned `id@version` |
| `ports` | optional placement of the generated ports (`side`, `t`) and labels; presentation only |
| `projection` | glyph and labels; presentation only |

Derived members, generated from `pattern` + `parameters` and never written by hand: `inputs` and `outputs` (port ids, flow, channels, observable and form), `state` (for stateful patterns), and `observables` (unit, form, update rule, blast radius, staleness tolerance). A pack may state a derived member for readability; if it does, the loader refuses the definition unless what is stated equals what is derived. There is one source of truth for a contract, and it is the pattern.

Validation is hand-written, like the data core's: each pattern ships its own parameter validator in `07-state-space.js`, and the `formats/*.schema.json` files document the shapes; no JSON Schema evaluator is added. A pattern declares whether it reads state: `threshold` and `transition` do. A new gate, device or domain is a new definition, never a new code path; NAND, NOR, XNOR and larger devices are definitions or compositions.

Compositions pin their children by `id@version`. A run resolves the full set, children included transitively, and the trace records that resolved set; it is part of the replay key.

Definitions are **domain-driven**: they arrive in domain packs (Issue #4), and a pack is the unit a domain publishes (logic, dataflow, a workstation model, ...). Until #4 defines the pack format, the state space carries a minimal pack envelope (`id`, `version`, `definitions[]`) that #4 will absorb as one member of the full domain pack. The built-in vocabulary (SOURCE, SINK, NOT, AND, OR, XOR, SWITCH, DELAY, threshold GATE) ships as the `core.logic` pack in `data/`, loaded the same way as any other pack, so built-ins have no privileged path.

A document references definitions by `id@version` and records which packs it uses. A `.sovpak` embeds the packs its document references, so a package runs anywhere. A document that references a definition it cannot resolve opens, but refuses to run, with a typed refusal naming the missing definition.

### What `signalMode` becomes

`source` / `relay` / `passive` keep their meaning. The current "active" set in `computeSignalState()` is the **settled state** of a run in which every source is high and every relay passes: the fixpoint the fixed six passes approximate. When the runtime lands, the editor's idle picture is that settled state, computed by the fold, and `25-signal.js` becomes a projection of it instead of its own computation.

## Files

- A `.sov` gains only **authored** state-space data: Path delays, definition references (`id@version`) and the packs they come from, thresholds, device initial states, observable and field declarations, observation-account share and observer order, initial registered values. Nothing a run computes is written to it.
- A `.sov` also gains **declared ports** (`config.attachmentPoints`, with channels) where a Component's ports differ from its template's, and **merge** declarations on ports. `attachmentDefaults` keeps today's two meanings (`standard`: template ports plus additions; `none`: the complete list).
- **Runs are saved.** A run's trace is its own file, `.sovtrace` (`soveraeign.schematic/trace@0.1`, MIME `application/vnd.soveraeign.schematic-trace+json`): the replay key (document id, `documentHash`, resolved definitions, runtime version, trace format version, inputs, seed), the document revision as a label, the budget, the event log (including every recorded order draw), and optionally the derived records for audit. A trace without derived records is still complete, because they are recomputable. A trace is kept apart from the `.sov` so running a document never changes the document, and so one document can have many runs.
- File menu: Save Run / Open Run, owned by `75-persistence.js` like every other file. Opening a trace against a document whose `documentHash` differs opens read-only and says so; it cannot be replayed until the replay key matches.
- A `.sovpak` may carry traces alongside its document and packs (`traces[]`), so a package can ship with its evidence.
- Golden traces live beside the examples they run.
- **Canonical encoding.** `.sovtrace` files, derived records and `documentHash` use RFC 8785 (JSON Canonicalization Scheme), so "byte-identical" has one meaning. Under the numeric policy (integers, strings, booleans, null) RFC 8785 is sorted keys plus `JSON.stringify` values, which is what the engine implements.
- **Hashing is synchronous and portable.** The browser's WebCrypto digest is async-only and the engine is synchronous, so SHA-256 is a small pure-JS implementation in `03-canonical.js`, shared by the data core and the engine and checked against published test vectors.
- The event log is **hash-chained** from slice 1: caches depend on it, and it gives tamper evidence for free. Imported events carry CloudEvents-style `source` + `id` as their dedupe key (slice 4).

## Surfaces

The runtime is transport-neutral and headless, like the data core, so the browser, HTTP, MCP and `node` scripts share one implementation. Operations follow the existing `schematic.<noun>.<verb>` naming:

- `schematic.run.start` (document, registered inputs, budget) → a new run id
- `schematic.run.step` → one tick's records; `schematic.run.settle` → quiet, oscillating, or budget spent
- `schematic.run.replay` (trace) → the recomputed run, or a typed refusal naming the first divergence; never acts outside
- `schematic.state.query` (subject, observable) → records; passive. Time and vantage arguments come when fields and history views need them.
- `schematic.run.trace` → the trace
- slice 4: `schematic.state.observe` (import measured records)

These are not CRUD: `operation@0.1` covers create / read / update / delete on components, wires and references, and its receipt is about document revisions. Run and state operations are **extra tools**, like `schematic.history.*` and `schematic.checkpoint.*` today, with their own receipt, `soveraeign.schematic/run-receipt@0.1` (run id, tick before and after, result or typed refusal). They are listed in `mcp/tools.json` so the parity suite can enumerate them. Refusals do not enter editor history, as for every other operation.

**Standards live at the edges, never in the core record (slice 4).** Export provenance as PROV-JSON (observer → Agent, rule application → Activity, record → Entity, inputs → wasDerivedFrom). Import measured records from OpenTelemetry, with metrics becoming signal state and spans becoming particles, and CloudEvents for discrete events. Each import adapter pins its semantic-convention version; the GenAI conventions are still pre-stable.

## Module ownership

Proposed additions to `MODULES.md`:

- `src/03-canonical.js`: canonical JSON (RFC 8785 for the value set in use), synchronous pure-JS SHA-256, and the seeded draw used by merges. Pure; loaded before `05`, and by `07`, scripts and the MCP server.
- `src/05-data-core.js`: gains `documentHash`, template port sets, the smallest-form storage of port lists, channel matching and the port operations.
- `src/06-attachment-core.js`: point specs come from declared ports only; the hard-coded trio moves to template data.
- `src/07-state-space.js`: the state record, event log, scheduler, fold, patterns (including `merge`), caches, fields and residuals. Pure; no DOM; loadable by `scripts/`, `mcp/server.mjs` and the editor, like `05-data-core.js` and `06-attachment-core.js`.
- `src/25-signal.js`: becomes the projection of settled or current state-space records onto the canvas.
- `src/55-render.js`: packets are driven from trace particles when a run is live.
- `src/75-persistence.js`: Save Run / Open Run and `.sovtrace`, the only place a trace is serialized.
- `data/core.logic.pack.json`: the built-in definitions.
- `formats/schematic.state-record.schema.json`, `formats/schematic.trace.schema.json`, `formats/schematic.definition.schema.json`, `formats/schematic.pattern.schema.json` (the shape of a pattern declaration; the patterns themselves ship with the engine).

## Invariants

What the runtime checks, and where. Each becomes a QA assertion in the slice that introduces it.

At load (typed refusal, the document still opens):
- every Path delay ≥ 1;
- every Path binds two ports that share at least one channel, and at least one of its declared directions is admitted by both ports' flows;
- every referenced definition resolves, children included; its parameters pass its pattern's validator; any derived member it states equals what is derived;
- every port a definition owns exists on its Component with the generated id, flow and channels;
- every declared merge names a known combine, and a `declared` order names only Paths that end on that port;
- every stateful device has a declared initial state;
- every field's ε is within its stability bound;
- no two active observers with overlapping write sets lack a declared order.

At run time:
- devices read only committed state;
- no outcome depends on `sequence` or on the engine's processing order;
- arrival order at a port changes an outcome only through a declared order, an observed order, or a recorded stochastic draw;
- inspection never writes to the event log;
- the same effect key never carries two payloads;
- replay under the same replay key is byte-identical under RFC 8785;
- every ledger entry carries the hash of the one before; a cache is used only while its recorded chain hash matches;
- replay never regenerates a recorded result;
- only the engine appends to a ledger.

## Slices

Each slice ends with its QA suite inside `python scripts/qa.py`.

0. **Foundations (editor and data core; no runtime yet).**
   - **0a Canonical identity:** `03-canonical.js` (canonical JSON, pure SHA-256 against test vectors, seeded draw); `documentHash` in the data core.
   - **0b Declared ports:** every Component's ports are declared data with side, t, flow and channels; templates declare their ports; stored forms keep their meaning; port add / move / relabel / remove through the data core on every surface; channel matching and direction checks on binding. Existing documents and the QA gate stay green.
1. **Record, patterns, definitions and fold**, as three pull requests:
   - **1a Contracts:** state record (subject with optional `attempt` and `channel`), pattern, definition and pack shapes with hand-written validators; channel `merge` and Path `config.delay` stored; the pattern registry with `truth_table@1` and `merge@1`; derived contracts with the "stated equals derived" check; ports generated from a bound definition; the minimal pack envelope and `core.logic` (NOT / AND / OR / XOR); all load checks.
   - **1b Ledger and step:** trace shape and validator; hash-chained event log; replay key with `documentHash`; two-phase ticks with merges; recorded stochastic order draws; numeric policy; RFC 8785 encoding; `run.start`, `run.step` (one tick), `run.trace`, `run.replay`; `A AND B → Q` over all four input vectors with golden `.sovtrace` files; a port fed by two Paths under `declared`, order-free and `stochastic` merges, each with a golden trace; replay identity; nothing written to `.sov`.
   - **1c Settle and surfaces:** run-receipt shape; `run.settle` with quiet / oscillating / budget spent and a NOT loop that settles as oscillating; `state.query` (subject, observable); the run tools in `mcp/tools.json`; API / HTTP / MCP parity.
2. **Visible runtime.** `SOURCE → NOT → DELAY → SWITCH → SINK A / SINK B` from Issue #6; Path and device delays; hosted Components as taps; packets rendered from the trace; Save Run / Open Run; the `materialize` pattern with snapshots and chain-hash validity; the `device.state` record; threshold devices with enter / exit hysteresis, declared initial state and margin; effect outcomes with receipt / refused / in-doubt and derived effect keys; inspection-is-passive QA.
3. **Fields.** `consensus` and `advection` as declared operators with the ε check; signal colour moved onto `presentation.signal-color`; `25-signal.js` reduced to projection.
4. **Instrument.** Observer registry with class, limits and read/write sets; observation account; perturbation ledger; instrument coordinates (quality, source and receipt time, GUM certainty) and the `estimated` kind; sensor, structural and drift residuals; controllability; `schematic.state.observe` with the OpenTelemetry adapter first; PROV-JSON export; intent logging and reconciliation for effects that reach outside; generative steps as recorded effects with attempts and their recorded inputs; the `rate` pattern with declared conditioning keys; evidence carried across revisions by identity.
5. **Later, only when earned.** Latches, clocks and edges (`transition`); the `compose` pattern with per-attempt retries and scored forecasts; possibility sets and ensembles; sensor placement from the uncertainty map; an OPC UA / DTDL adapter if an industrial pack earns it; inertial delay as a DELAY parameter; interposing hosted Components after the carrier/Component record merge.

## Non-goals

Analog or electrical simulation; exact Redstone emulation; HDL synthesis; amplitudes (probabilities narrow by observation and that is enough unless paths must cancel); 3D.

## Settled

1. **Delay** is on both the Path (propagation) and the device (response). *(2026-09-25)*
2. **Behaviour** is definitions as data, delivered in domain packs; built-ins are the `core.logic` pack. *(2026-09-25)*
3. **Runs are saved** as `.sovtrace`, separate from the document. *(2026-09-25)*
4. **Active observation** is paid relative to the observed run: a reserved observation account holding a declared share of the initial budget (default 10%); exhausting it refuses observation, not the run. *(2026-09-25; mechanism amended by review the same day)*
5. **Zero-delay Paths** are forbidden; Path delay ≥ 1 is checked at load. *(2026-09-25)*
6. **Hysteresis** ships in slice 2 on the `device.state` record. *(2026-09-25)*
7. **Scheduling** is two-phase ticks over committed state; `sequence` is serialization only; one step is one tick. *(2026-09-25)*
8. **Intent logging** waits for effects that reach outside (slice 4); until then replay identity is the divergence check. *(2026-09-25)*
9. **The first import standard** is OpenTelemetry. *(2026-09-25)*
10. **Ownership.** The engine owns the shape of state and a small closed set of patterns; domain packs instantiate patterns with data; contracts are generated from pattern and parameters, never hand-written. *(2026-09-25)*
11. **Caches** are passive observations of a hash-chained ledger and own nothing; the hash chain lands in slice 1. *(2026-09-25)*
12. **Generative steps** are effects whose results are recorded; replay reads them, re-run regenerates. The engine stays deterministic given the ledger. *(2026-09-25)*
13. **Retries** are attempts, each its own subject with its own recorded inputs; prediction uses per-attempt rates, never one rate repeated. *(2026-09-25)*
14. **Ports are declared.** Every Component's ports are declared data (side, t, flow, channels); the trio is template data, not engine code; stored forms keep their meaning (`standard` = template ports plus additions, `none` = complete list); a bound definition generates its ports. *(2026-09-25, after the Fable review)*
15. **Merge ships in slice 1.** Same-tick fan-in at a port is resolved by a declared merge; undeclared or undeclarable order is stochastic, drawn from the seed per port and tick, and recorded in the ledger. *(2026-09-25)*
16. **Document identity** in the replay key is a content hash; revision is a label. *(2026-09-25)*
17. **Contracts have one source**: patterns derive inputs, outputs, state and observables; stated-but-different is refused. Validation is hand-written. *(2026-09-25)*
18. **Delay is transport delay**; Paths carry only their declared direction(s); hosted Components are taps until the record merge. *(2026-09-25)*
19. **Hashing** is synchronous pure-JS SHA-256 in `03-canonical.js`; run operations are extra tools with their own receipt. *(2026-09-25)*

## Open questions

1. **Connections for the instrument (slice 4).** When schematically watches an outside system, who says what connects to what? (a) A person draws the model, and outside readings only attach to the drawn entities. (b) The outside system also reports its connections, and those arrive as measured records. Current lean: (a) by default; reported connections arrive as measured records shown as proposals and become part of the document only when someone accepts them, so nothing observed silently rewrites what was authored. The structural residual measures the gap either way.
2. **Evidence across revisions (slice 4).** When a step's definition changes, how much should its old history count? Current lean: an unchanged definition keeps its full history; a changed one starts fresh, with the old rate as a weak prior worth a small, declared number of trials, so the first few new outcomes quickly outweigh it. The drift residual shows whether the change actually moved the rate.
