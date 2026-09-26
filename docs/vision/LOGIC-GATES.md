# Logic gates on state space

> **Non-authoritative horizon.** The logic domain as data for the state space runtime (`STATE-SPACE.md`, #43), which is the one runtime. This document says which gates exist as definitions, which examples run them, and what the stateful gates need from the patterns still to come. It changes nothing in the engine.

## Where this stands

State space is canonical (decided 2026-09-26). Behaviour is **definitions in packs**, each an instance of a pattern; a Component runs one by binding it (`config.definition: "logic.and@1"`). This branch had carried its own runtime (`scripts/logic_sov.py`, a JavaScript port, a `logic.*` editor API and an MCP tool). They are retired. What they taught is kept below.

- **`data/core.logic.pack.json`** (the engine's): NOT, AND, OR, XOR.
- **`data/logic.gates.pack.json`**: the other combinational gates and two adders, as `truth_table@1` definitions. Written by `scripts/build_logic_pack.py`, which enumerates each table from a plain function of the inputs.
- **`data/logic.glyphs.json`**: one glyph per definition, keyed by reference (`logic.and@1`), written by `scripts/logic_glyphs.py`. Presentation only.
- **`examples/logic/`**: eight state space documents, written by `scripts/build_logic_examples.py`, with a golden trace `adder4.carry.sovtrace`.
- **`scripts/run_state.mjs`**: runs a document on the engine to quiet from scripts.
- **`tests/logic_examples_qa.py`**: every example passes the engine's load checks and computes what it claims, against oracles written in the test.

## Definitions

| Pack | Definition | Inputs → outputs | Glyph |
| --- | --- | --- | --- |
| `core.logic` | `logic.not`, `logic.and`, `logic.or`, `logic.xor` | a (, b) → q | shape |
| `logic.gates` | `logic.buffer`, `logic.nand`, `logic.nor`, `logic.xnor` | a (, b) → q | shape |
| `logic.gates` | `logic.imply`, `logic.nimply`, `logic.cimply`, `logic.ncimply` | a, b → q | IEC ⇒ ⇏ ⇐ ⇍ |
| `logic.gates` | `logic.majority` | a, b, c → q | IEC ≥2 |
| `logic.gates` | `logic.mux` | s, a, b → q (a when s = 0) | IEC MUX |
| `logic.gates` | `logic.half_adder` | a, b → s, c | IEC HA |
| `logic.gates` | `logic.full_adder` | a, b, cin → s, cout | IEC FA |

Constants are not definitions: `truth_table@1` takes one to eight inputs, and a source is a Point whose value a run registers. With `buffer` and `not`, the ten two-input tables cover all sixteen Boolean functions of two inputs except the two constants.

## Examples

Sources are Points marked `signalMode: source`; outputs are Points; every Wire carries forward with delay 1.

| Document | Built from | Checked by the engine's run |
| --- | --- | --- |
| `gates.sov` | every definition on sources A, B, C | all 8 vectors against each gate's Boolean function |
| `half-adder.sov` | XOR, AND | all 4 vectors |
| `full-adder.sov` | two `half_adder` devices, OR | all 8 vectors |
| `adder4.sov` | four `full_adder` devices | all 512 vectors: S + 16·Cout = A + B + Cin |
| `adder8.sov` | eight `full_adder` devices | 64 seeded vectors |
| `add-sub4.sov` | four XORs and four `full_adder` devices | all 512: A − B mod 16 with SUB, carry out = no borrow |
| `xor-nand.sov` | four NANDs | all 4: equals XOR |
| `mux2.sov` | NOT, two ANDs, OR | all 8: equals `logic.mux` |

**The carry ripples.** Delay is transport delay and every Wire takes a tick, so 7 + 0 → 7 + 1 passes through **6, 4 and 0** before 8, one full adder at a time. The golden trace `adder4.carry.sovtrace` records it, replays byte for byte, and is the gallery's timing picture (`docs/visual/timing-adder-carry.svg`). A change that needs no carry (0 + 0 → 1 + 0) shows no transient.

A half adder is a device here, not a document inside a document: state space has no composition pattern yet (`children` in a definition is named in STATE-SPACE.md, not built). A full adder made of two `half_adder` devices keeps the teaching shape without it.

## Waiting for patterns

These gates ran under the retired runtime and are specified here so the patterns that will carry them start from a tested definition. None is invented as a pattern here; the engine's set is closed and grows by review.

**For `threshold` (slice 2): a binary cut through a continuous value.** Needs continuous channels (slice 1b runs binary only).

| Gate | Parameters | Rule | State |
| --- | --- | --- | --- |
| compare | θ = 0.5 | q = x ≥ θ | none (chatters on noise near θ) |
| threshold | weights (1, 1, 1), θ = 2 | q = Σ wᵢ·xᵢ ≥ θ (defaults: majority; θ 1: OR; θ 3: AND) | none |
| Schmitt | low 0.4, high 0.6, initial 0 | on at x ≥ high, off at x ≤ low, hold between | one bit, declared initial |

Under the old runtime a comparator driven by a slow swing plus noise flipped more than four times as often as the Schmitt trigger, which flipped once per real crossing. That is the QA the `threshold` pattern should inherit, with STATE-SPACE.md's margin.

**For `transition` (slice 5): state machines, latches, clocks and edges.** Each is a next-state table over (state, inputs) and an output table over state, with a declared initial state; clocked ones step only on the declared edge.

| Gate | Inputs | Clock | Next state (state \| inputs → state) | Outputs |
| --- | --- | --- | --- | --- |
| D flip-flop | d | clk, rising | q ← d | q, q̄ |
| T flip-flop | t | clk, rising | q ← q xor t | q, q̄ |
| JK flip-flop | j, k | clk, rising | 00 hold, 01 reset, 10 set, 11 toggle | q, q̄ |
| SR latch | s, r | none | 00 hold, 01 reset, 10 set, 11 reset (reset wins) | q, q̄ |
| D latch | d, en | none | q ← d while en, hold otherwise | q, q̄ |
| C-element | a, b | none | q ← a when a = b, hold when they differ | q |

With those, the examples that were retired come back as documents: a 4-bit register, an accumulator (adder plus register fed back), ripple and synchronous counters, the completion pair, the window comparator and the reorder rule.

**Lessons from the retired runtime**, for whoever builds them:
- **Power-on.** A stateful gate must show its declared initial state before anything runs; otherwise a flip-flop's q̄ rising at power-on reads as a clock edge to the next stage (the first ripple counter jumped to 15). Nothing without declared state gets a default. STATE-SPACE.md already requires a declared initial state and evaluates every device at tick 0.
- **Races.** Two cross-coupled NORs declare no state; released from S = R = 1 they oscillate. STATE-SPACE.md's `run.settle` (slice 1c) reports that as *oscillating* with its period, which is the right answer, where the old runtime could only refuse on its event budget.
- **Ripple against synchronous.** A ripple counter's outputs change one after another (7 → 8 passes 6, 4, 0); a synchronous counter's change in one tick. The timing view's transient marking is built to show exactly this.
- **Completion.** AND says "both are done now" and drops when either resets; the C-element says "both have finished" and holds until both reset. The second is the completion detector of self-timed circuits, and the one `WHOLE-UNITS-AND-STATE.md` needs when completion must survive a reset.

## Other gates worth having

Mapped to what would carry them:

- **As `truth_table@1` data now:** decoder, encoder and priority encoder (a priority encoder is the simulator's "nearest the market first" dispatch rule), parity, magnitude comparator, a small ALU slice. All are tables of up to eight inputs.
- **As compositions** (when `children` lands): carry-lookahead adder, barrel shifter, wider ALUs. Carry-lookahead is the first gate-count-against-delay problem for `optimize_sov.py`: gates as material, delay as time.
- **As `transition`:** shift registers, counters with enable, load and reset, generic Moore and Mealy machines, edge detector and one-shot, debouncer (hysteresis in time), arbiter (closes the simulator's contention residual in `WHOLE-UNITS-AND-STATE.md`).
- **As `threshold`:** window comparator, dead band, clamp, quantizer.
- **Beyond binary:** three-valued logic with X would say "unknown" where the NOR latch races and where a tri-state bus has no driver; it needs a categorical form, which STATE-SPACE.md's record already has (`form: categorical`).

## Residuals

| Gap | What closes it |
| --- | --- |
| The editor's copy of a document hashes differently from the file (`documentHash` includes defaults the editor fills in), so a trace made from a file cannot be replayed on it open in the editor; the engine's own `and.11.sovtrace` shows it | the engine hashing the document's authored truth, invariant under the editor's projection (STATE-SPACE.md: "document identity is content") |
| Stateful gates, levels, composition | the `threshold`, `transition` and composition patterns, above |
| A run shows only in a picture or on the canvas from the API | the run surfaces of slice 1c (`schematic.run.*`) and Save Run / Open Run (slice 2) |
| Buses are naming conventions (`A0`..`A3`) | a bus as a carrier of width n, or several channels on one port (STATE-SPACE.md "Channels") |

## Try it

```
python scripts/record_run.py logic examples/logic/adder4.sov --sequence 'A=7:4,B=0:4,Cin=0;B0=1' --bus S --out carry.json
node scripts/plot_run.mjs carry.json --page carry.html
python scripts/export_svg.py examples/logic/adder4.sov --run 'A=7:4,B=0:4,Cin=0;B0=1' --tick 23
python tests/logic_examples_qa.py
```
